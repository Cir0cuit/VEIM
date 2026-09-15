import os
import sys
import shutil
import platform
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
from src.core.logger import log

@dataclass
class DriveInfo:
    path: str
    label: str
    filesystem: str
    total_gb: float
    free_gb: float
    used_gb: float
    free_pct: float
    is_ventoy: bool
    is_removable: bool
    has_managed_folder: bool
    warning: str = ""

class DriveDetector:
    """
    Cross-platform removable and Ventoy drive detector.
    Supports Windows, Linux, and macOS.
    """

    @staticmethod
    def get_drives() -> List[DriveInfo]:
        system = platform.system()
        if system == "Windows":
            return DriveDetector._get_windows_drives()
        elif system == "Linux":
            return DriveDetector._get_linux_drives()
        elif system == "Darwin":
            return DriveDetector._get_macos_drives()
        else:
            return []

    @staticmethod
    def inspect_path(path_str: str) -> Optional[DriveInfo]:
        """Inspects any given directory path and returns DriveInfo."""
        p = Path(path_str)
        if not p.exists() or not p.is_dir():
            return None

        try:
            total, used, free = shutil.disk_usage(str(p))
            total_gb = round(total / (1024**3), 2)
            free_gb = round(free / (1024**3), 2)
            used_gb = round(used / (1024**3), 2)
            free_pct = round((free / total * 100), 1) if total > 0 else 0.0

            has_ventoy_dir = (p / "ventoy").exists()
            has_managed = (p / "Managed_ISOs").exists()
            label = p.name or str(p)

            fs_name = ""
            is_removable = False
            if platform.system() == "Windows":
                try:
                    import ctypes
                    k32 = ctypes.windll.kernel32
                    drive_root = str(p).split(":")[0] + ":\\"
                    vol_buf = ctypes.create_unicode_buffer(1024)
                    fs_buf = ctypes.create_unicode_buffer(1024)
                    k32.GetVolumeInformationW(drive_root, vol_buf, 1024, None, None, None, fs_buf, 1024)
                    label = vol_buf.value or label
                    fs_name = fs_buf.value
                    dtype = k32.GetDriveTypeW(drive_root)
                    is_removable = (dtype == 2)  # DRIVE_REMOVABLE
                except Exception:
                    pass

            is_ventoy = has_ventoy_dir or "ventoy" in label.lower() or has_managed
            warning = ""
            if total_gb < 0.5:
                warning = "Small partition (possibly EFI/VTOYEFI). Select Ventoy Data partition instead."

            return DriveInfo(
                path=str(p.resolve()),
                label=label,
                filesystem=fs_name,
                total_gb=total_gb,
                free_gb=free_gb,
                used_gb=used_gb,
                free_pct=free_pct,
                is_ventoy=is_ventoy,
                is_removable=is_removable,
                has_managed_folder=has_managed,
                warning=warning
            )
        except Exception as e:
            log.warning(f"Failed to inspect path {path_str}: {e}")
            return None

    @staticmethod
    def _get_windows_drives() -> List[DriveInfo]:
        import ctypes
        k32 = ctypes.windll.kernel32
        drives = []

        # Bitmask of available drives
        bitmask = k32.GetLogicalDrives()
        for letter in "DEFGHIJKLMNOPQRSTUVWXYZABC":  # Check removable / secondary first
            idx = ord(letter) - ord('A')
            if bitmask & (1 << idx):
                drive_str = f"{letter}:\\"
                dtype = k32.GetDriveTypeW(drive_str)
                if dtype in (2, 3):  # Check removable and fixed drives (USBs can be either)
                    info = DriveDetector.inspect_path(drive_str)
                    if info:
                        # Exclude small VTOYEFI EFI partition (< 100MB) from primary suggestions
                        if info.total_gb > 0.2:
                            drives.append(info)

        # Sort: Ventoy drives first, then removable drives, then by free space desc
        drives.sort(key=lambda d: (d.is_ventoy, d.has_managed_folder, d.is_removable), reverse=True)
        return drives

    @staticmethod
    def _get_linux_drives() -> List[DriveInfo]:
        drives = []
        user = os.environ.get("USER", "")
        candidate_roots = [
            f"/media/{user}",
            f"/run/media/{user}",
            "/mnt",
            "/media"
        ]

        for root in candidate_roots:
            if os.path.exists(root):
                try:
                    for entry in os.listdir(root):
                        full_path = os.path.join(root, entry)
                        if os.path.isdir(full_path):
                            info = DriveDetector.inspect_path(full_path)
                            if info and info.total_gb > 0.2:
                                drives.append(info)
                except Exception as e:
                    log.warning(f"Error scanning {root}: {e}")

        drives.sort(key=lambda d: (d.is_ventoy, d.has_managed_folder), reverse=True)
        return drives

    @staticmethod
    def _get_macos_drives() -> List[DriveInfo]:
        drives = []
        vol_root = "/Volumes"
        if os.path.exists(vol_root):
            try:
                for entry in os.listdir(vol_root):
                    full_path = os.path.join(vol_root, entry)
                    if os.path.isdir(full_path) and not entry.startswith("."):
                        info = DriveDetector.inspect_path(full_path)
                        if info and info.total_gb > 0.2:
                            drives.append(info)
            except Exception as e:
                log.warning(f"Error scanning macOS /Volumes: {e}")

        drives.sort(key=lambda d: (d.is_ventoy, d.has_managed_folder), reverse=True)
        return drives

    @staticmethod
    def init_ventoy_drive(drive_path: str) -> str:
        """
        Initializes the target drive directory:
        Ensures `Managed_ISOs` and `ventoy/` exist.
        Returns the path to `Managed_ISOs`.
        """
        managed_dir = os.path.join(drive_path, "Managed_ISOs")
        os.makedirs(managed_dir, exist_ok=True)
        
        ventoy_dir = os.path.join(drive_path, "ventoy")
        os.makedirs(ventoy_dir, exist_ok=True)
        
        return managed_dir
