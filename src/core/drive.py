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
from typing import Dict, Iterator, List, Optional, Tuple
from src.core.logger import log

# Where Linux desktops put removable media: udisks2 uses /run/media/<user>/ on
# Fedora and its relatives and /media/<user>/ on Debian and its relatives, and
# /mnt is where people mount things by hand.
LINUX_MOUNT_ROOTS = ("/media", "/run/media", "/mnt")

MOUNTINFO_PATH = "/proc/self/mountinfo"
PROC_MOUNTS_PATH = "/proc/mounts"

# Kernel bookkeeping that can turn up under those roots. None of it can hold an
# ISO, and an autofs placeholder in particular reports a capacity that has
# nothing to do with the drive it stands in for.
PSEUDO_FILESYSTEMS = frozenset({
    "autofs", "binfmt_misc", "bpf", "cgroup", "cgroup2", "configfs", "debugfs",
    "devpts", "devtmpfs", "efivarfs", "fuse.gvfsd-fuse", "fuse.portal",
    "fusectl", "hugetlbfs", "mqueue", "proc", "pstore", "ramfs", "rpc_pipefs",
    "securityfs", "selinuxfs", "sysfs", "tracefs",
})


@dataclass(frozen=True)
class MountPoint:
    """One line of the kernel's mount table."""
    path: str
    source: str
    fstype: str
    read_only: bool = False


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


_OCTAL_ESCAPE = re.compile(r"\\([0-7]{3})")


def _unescape_mount_field(field: str) -> str:
    """Undo the octal escaping the kernel applies to space, tab and backslash."""
    if "\\" not in field:
        return field
    return _OCTAL_ESCAPE.sub(lambda m: chr(int(m.group(1), 8)), field)


def _read_table_lines(path: str) -> List[str]:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            return handle.read().splitlines()
    except OSError as e:
        log.debug(f"No mount table at {path}: {e}")
        return []


def _parse_mountinfo_line(line: str) -> Optional[MountPoint]:
    """Parse one /proc/self/mountinfo line.

        36 35 98:0 / /mnt/usb rw,noatime shared:1 - exfat /dev/sdb1 rw
         0  1   2  3     4        5       [opt..] ^   -1     -2     -3

    The optional fields between the mount options and the "-" separator vary in
    number, so everything after the separator is indexed from it.
    """
    fields = line.split(" ")
    if len(fields) < 10:
        return None
    try:
        separator = fields.index("-", 6)
    except ValueError:
        return None
    if len(fields) < separator + 4:
        return None

    options = f"{fields[5]},{fields[separator + 3]}".split(",")
    return MountPoint(
        path=_unescape_mount_field(fields[4]),
        source=_unescape_mount_field(fields[separator + 2]),
        fstype=fields[separator + 1],
        read_only="ro" in options,
    )


def _parse_proc_mounts_line(line: str) -> Optional[MountPoint]:
    """Parse one /proc/mounts line: source, mount point, type, options."""
    fields = line.split(" ")
    if len(fields) < 4:
        return None
    return MountPoint(
        path=_unescape_mount_field(fields[1]),
        source=_unescape_mount_field(fields[0]),
        fstype=fields[2],
        read_only="ro" in fields[3].split(","),
    )


def read_mount_table(mountinfo_path: str = MOUNTINFO_PATH,
                     mounts_path: str = PROC_MOUNTS_PATH) -> Dict[str, MountPoint]:
    """Everything the kernel currently has mounted, keyed by mount point.

    Empty when there is no table to read -- on Windows and macOS, or on a Linux
    system without /proc -- which callers take as "fall back to ismount()".
    """
    table: Dict[str, MountPoint] = {}
    for line in _read_table_lines(mountinfo_path):
        entry = _parse_mountinfo_line(line)
        if entry:
            # Mounting over an existing mount point is legal; the last one wins,
            # and it is the one whose free space you would actually be using.
            table[entry.path] = entry
    if table:
        return table

    for line in _read_table_lines(mounts_path):
        entry = _parse_proc_mounts_line(line)
        if entry:
            table[entry.path] = entry
    return table


def mount_at_path(path: str, table: Dict[str, MountPoint]) -> Optional[MountPoint]:
    """The mount rooted exactly at `path`, or None if nothing is mounted there.

    This is the check that keeps empty directories out of the drive list. With
    no mount table to consult it falls back to os.path.ismount(), which also
    rejects symlinks -- /Volumes/Macintosh HD on macOS is one.
    """
    if table:
        return table.get(path) or table.get(os.path.realpath(path))
    try:
        if os.path.ismount(path):
            return MountPoint(path=os.path.realpath(path), source="", fstype="")
    except OSError:
        pass
    return None


def mount_for_path(path: str, table: Dict[str, MountPoint]) -> Optional[MountPoint]:
    """The mount a path lives on: the longest mount point containing it.

    Unlike mount_at_path() this answers for any directory, mount point or not,
    so a folder the user browsed to still reports its filesystem.
    """
    resolved = os.path.realpath(path)
    best: Optional[MountPoint] = None
    for entry in table.values():
        if resolved == entry.path or resolved.startswith(entry.path.rstrip("/") + "/"):
            if best is None or len(entry.path) > len(best.path):
                best = entry
    return best


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
    def inspect_path(path_str: str,
                     mount_table: Optional[Dict[str, MountPoint]] = None) -> Optional[DriveInfo]:
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
            read_only = False
            system = platform.system()
            if system == "Windows":
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
            elif system == "Linux":
                table = read_mount_table() if mount_table is None else mount_table
                mount = mount_for_path(str(p), table)
                if mount:
                    fs_name = mount.fstype
                    read_only = mount.read_only

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
    def _linux_mounted_dirs(table: Dict[str, MountPoint]) -> Iterator[Tuple[str, MountPoint]]:
        """Directories under the media roots that really do have a drive on them."""
        for root in LINUX_MOUNT_ROOTS:
            for child in _list_subdirs(root):
                mount = mount_at_path(child, table)
                if mount is not None:
                    yield child, mount
                    continue
                # Nothing is mounted on this one, but it may be the per-user
                # directory udisks2 creates -- /run/media/<user>/<label> -- so
                # look one level in before writing it off. Going by the
                # directories present rather than $USER also covers a session
                # where that variable is unset or belongs to someone else.
                for grandchild in _list_subdirs(child):
                    nested = mount_at_path(grandchild, table)
                    if nested is not None:
                        yield grandchild, nested

    @staticmethod
    def _get_linux_drives() -> List[DriveInfo]:
        drives = []
        table = read_mount_table()
        seen = set()

        for path, mount in DriveDetector._linux_mounted_dirs(table):
            if mount.fstype in PSEUDO_FILESYSTEMS:
                continue
            resolved = os.path.realpath(path)
            if resolved in seen:  # reachable from more than one root
                continue
            seen.add(resolved)

            info = DriveDetector.inspect_path(path, table)
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
            if mount_at_path(path, {}) is None:
                continue
            info = DriveDetector.inspect_path(path)
            if info and info.total_gb > 0.2:
                drives.append(info)

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
