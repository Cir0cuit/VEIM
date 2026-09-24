"""Finding the drive VEIM manages.

The Linux half is deliberately paranoid about what counts as a drive. Desktops
leave empty directories lying around under /mnt and /media, and
`shutil.disk_usage()` on one of those answers for whatever filesystem the
directory itself lives on -- so an unused /mnt/usb would otherwise be listed as
a drive advertising the root filesystem's free space. Only paths the kernel
says are mount points are offered.
"""
import os
import re
import shutil
import platform
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, List, Optional, Set, Tuple
from PySide6.QtCore import QStorageInfo
from src.core.logger import log

# Where Linux desktops put removable media: udisks2 uses /run/media/<user>/ on
# Fedora and its relatives and /media/<user>/ on Debian and its relatives, and
# /mnt is where people mount things by hand.
LINUX_MOUNT_ROOTS = ("/media", "/run/media", "/mnt")

MOUNTINFO_PATH = "/proc/self/mountinfo"

# Kernel bookkeeping that can turn up under those roots. None of it can hold an
# ISO, and an autofs placeholder in particular reports a capacity that has
# nothing to do with the drive it stands in for.
PSEUDO_FILESYSTEMS = frozenset({
    "autofs", "binfmt_misc", "bpf", "cgroup", "cgroup2", "configfs", "debugfs",
    "devpts", "devtmpfs", "efivarfs", "fuse.gvfsd-fuse", "fuse.portal",
    "fusectl", "hugetlbfs", "mqueue", "proc", "pstore", "ramfs", "rpc_pipefs",
    "securityfs", "selinuxfs", "sysfs", "tracefs",
})


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


def _volume_at(path: str) -> Optional[QStorageInfo]:
    """The volume mounted exactly at `path`, or None if nothing is mounted there.

    This is the check that keeps empty directories out of the drive list: Qt
    reads the kernel's mount table and answers for any other directory with the
    mount it lives on.
    """
    volume = QStorageInfo(path)
    if volume.isValid() and volume.rootPath() == os.path.realpath(path):
        return volume
    return None


def _automount_points() -> Set[str]:
    """Mount points where an automount (autofs) has not fired yet.

    Nothing may ask about one: QStorageInfo's statfs(), like opening it, mounts
    the share behind it, and waits out the mount timeout (90 s under systemd)
    when that share is unreachable. The kernel's mount table says which they are
    without touching them.
    """
    top = {}
    try:
        with open(MOUNTINFO_PATH, encoding="utf-8", errors="replace") as table:
            for line in table:
                # 36 25 0:52 / /mnt/nas rw,relatime shared:9 - autofs systemd-1 rw
                if " - " in line:
                    # A later line for the same path is a mount on top of it:
                    # once the automount has fired, the share is a drive.
                    top[line.split(" ")[4]] = line.split(" - ", 1)[1].split(" ")[0]
    except OSError:
        return set()
    # The kernel writes a space, tab or backslash in a path as octal ("\040").
    return {re.sub(r"\\([0-7]{3})", lambda m: chr(int(m.group(1), 8)), path)
            for path, fstype in top.items() if fstype == "autofs"}


def _list_subdirs(root: str) -> List[str]:
    """Immediate subdirectories of `root`; empty when it cannot be read."""
    try:
        with os.scandir(root) as entries:
            return sorted(entry.path for entry in entries if entry.is_dir())
    except OSError as e:
        # A missing root is normal; another user's 0700 media directory is not
        # worth a warning either.
        if os.path.isdir(root):
            log.debug(f"Could not scan {root}: {e}")
        return []


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

            # The volume the path lives on, mount point or not, so a folder the
            # user browsed to still reports its filesystem.
            volume = QStorageInfo(str(p))
            fs_name = bytes(volume.fileSystemType()).decode()
            read_only = volume.isReadOnly()
            is_removable = False
            if platform.system() == "Windows":
                import ctypes
                label = volume.name() or label
                dtype = ctypes.windll.kernel32.GetDriveTypeW(volume.rootPath())
                is_removable = (dtype == 2)  # DRIVE_REMOVABLE

            is_ventoy = has_ventoy_dir or "ventoy" in label.lower() or has_managed
            warning = ""
            if total_gb < 0.5:
                warning = "Small partition (possibly EFI/VTOYEFI). Select Ventoy Data partition instead."
            elif read_only:
                warning = "Mounted read-only. Remount it writable before adding ISOs."

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
    def _linux_mounted_dirs() -> Iterator[Tuple[str, QStorageInfo]]:
        """Directories under the media roots that really do have a drive on them."""
        automounts = _automount_points()

        def subdirs(path):
            return [d for d in _list_subdirs(path) if os.path.realpath(d) not in automounts]

        for root in LINUX_MOUNT_ROOTS:
            for child in subdirs(root):
                volume = _volume_at(child)
                if volume is not None:
                    yield child, volume
                    continue
                # Nothing is mounted on this one, but it may be the per-user
                # directory udisks2 creates -- /run/media/<user>/<label> -- so
                # look one level in before writing it off. Going by the
                # directories present rather than $USER also covers a session
                # where that variable is unset or belongs to someone else.
                for grandchild in subdirs(child):
                    nested = _volume_at(grandchild)
                    if nested is not None:
                        yield grandchild, nested

    @staticmethod
    def _get_linux_drives() -> List[DriveInfo]:
        drives = []
        seen = set()

        for path, volume in DriveDetector._linux_mounted_dirs():
            if bytes(volume.fileSystemType()).decode() in PSEUDO_FILESYSTEMS:
                continue
            resolved = os.path.realpath(path)
            if resolved in seen:  # reachable from more than one root
                continue
            seen.add(resolved)

            info = DriveDetector.inspect_path(path)
            if info and info.total_gb > 0.2:
                drives.append(info)

        drives.sort(key=lambda d: (d.is_ventoy, d.has_managed_folder), reverse=True)
        return drives

    @staticmethod
    def _get_macos_drives() -> List[DriveInfo]:
        drives = []
        for path in _list_subdirs("/Volumes"):
            if os.path.basename(path).startswith("."):
                continue
            # /Volumes/Macintosh HD is a symlink to /, and an unclean eject can
            # leave an empty directory behind. Neither is a mounted volume.
            if not os.path.ismount(path):
                continue
            info = DriveDetector.inspect_path(path)
            if info and info.total_gb > 0.2:
                drives.append(info)

        drives.sort(key=lambda d: (d.is_ventoy, d.has_managed_folder), reverse=True)
        return drives
