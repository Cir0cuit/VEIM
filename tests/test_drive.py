"""Drive detection.

The regression these guard against: every directory under /mnt and /media was
offered as a drive whether or not anything was mounted on it. An empty
leftover directory reports the root filesystem's capacity through
shutil.disk_usage(), so the picker filled up with phantom drives all claiming
the system disk's free space.
"""
import os

import pytest

from src.core import drive as drive_mod
from src.core.drive import (
    DriveDetector,
    MountPoint,
    mount_at_path,
    mount_for_path,
    read_mount_table,
)

# The mount table is a Linux artefact and so are the paths in it: these tests
# feed POSIX paths through os.path.realpath(), which on Windows turns /mnt/usb
# into C:\mnt\usb. The scan they cover never runs there - get_drives() hands
# Windows off to the drive-letter branch - so they are skipped rather than
# rewritten in a path flavour the code never sees.
posix_paths = pytest.mark.skipif(
    os.name != "posix", reason="Linux mount-table paths",
)

# A udisks2-mounted Ventoy stick, with optional fields before the separator.
VENTOY_LINE = (
    "36 35 8:33 / /run/media/ana/VENTOY rw,nosuid,nodev,relatime "
    "shared:1 - exfat /dev/sdc1 rw,uid=1000"
)
# The same thing without optional fields, which is equally legal.
PLAIN_LINE = "41 35 8:17 / /mnt/usb rw,relatime - vfat /dev/sdb1 rw"


# --------------------------------------------------------------- mount table

def test_mountinfo_line_is_parsed_past_the_optional_fields():
    entry = drive_mod._parse_mountinfo_line(VENTOY_LINE)

    assert entry == MountPoint(
        path="/run/media/ana/VENTOY", source="/dev/sdc1",
        fstype="exfat", read_only=False,
    )


def test_mountinfo_line_without_optional_fields_is_parsed():
    entry = drive_mod._parse_mountinfo_line(PLAIN_LINE)

    assert entry.path == "/mnt/usb"
    assert entry.fstype == "vfat"


def test_mountinfo_unescapes_octal_in_paths():
    line = "36 35 8:33 / /media/ana/My\\040Backup\\040Drive rw - ext4 /dev/sdc1 rw"

    assert drive_mod._parse_mountinfo_line(line).path == "/media/ana/My Backup Drive"


@pytest.mark.parametrize("line", [
    "36 35 8:33 / /mnt/usb ro,relatime - exfat /dev/sdc1 rw",   # mount options
    "36 35 8:33 / /mnt/usb rw,relatime - exfat /dev/sdc1 ro",   # superblock
])
def test_mountinfo_notices_read_only_mounts(line):
    assert drive_mod._parse_mountinfo_line(line).read_only is True


@pytest.mark.parametrize("line", [
    "",
    "not a mount table line",
    "36 35 8:33 / /mnt/usb rw,relatime shared:1 exfat /dev/sdc1 rw",  # no separator
    "36 35 8:33 / /mnt/usb rw,relatime - exfat",                      # truncated
])
def test_unparsable_mountinfo_lines_are_dropped(line):
    assert drive_mod._parse_mountinfo_line(line) is None


def test_read_mount_table_keys_by_mount_point(tmp_path):
    mountinfo = tmp_path / "mountinfo"
    mountinfo.write_text(f"{VENTOY_LINE}\n{PLAIN_LINE}\n")

    table = read_mount_table(str(mountinfo), str(tmp_path / "absent"))

    assert set(table) == {"/run/media/ana/VENTOY", "/mnt/usb"}
    assert table["/mnt/usb"].source == "/dev/sdb1"


def test_a_mount_over_an_existing_mount_point_wins(tmp_path):
    mountinfo = tmp_path / "mountinfo"
    mountinfo.write_text(
        "41 35 8:17 / /mnt/usb rw,relatime - vfat /dev/sdb1 rw\n"
        "42 35 8:33 / /mnt/usb rw,relatime - exfat /dev/sdc1 rw\n"
    )

    table = read_mount_table(str(mountinfo), str(tmp_path / "absent"))

    assert table["/mnt/usb"].source == "/dev/sdc1"


def test_read_mount_table_falls_back_to_proc_mounts(tmp_path):
    mounts = tmp_path / "mounts"
    mounts.write_text("/dev/sdc1 /media/ana/VENTOY exfat rw,nosuid 0 0\n")

    table = read_mount_table(str(tmp_path / "absent"), str(mounts))

    assert table["/media/ana/VENTOY"].fstype == "exfat"
    assert table["/media/ana/VENTOY"].read_only is False


def test_read_mount_table_is_empty_without_proc(tmp_path):
    assert read_mount_table(str(tmp_path / "a"), str(tmp_path / "b")) == {}


def test_mount_at_path_only_answers_for_the_mount_point_itself(tmp_path):
    root = os.path.realpath(str(tmp_path))
    table = {root: MountPoint(path=root, source="/dev/sdc1", fstype="exfat")}

    assert mount_at_path(root, table) is not None
    assert mount_at_path(os.path.join(root, "sub"), table) is None


def test_mount_at_path_falls_back_to_ismount_without_a_table(tmp_path, monkeypatch):
    mounted = str(tmp_path / "mounted")
    os.makedirs(mounted)
    monkeypatch.setattr(drive_mod.os.path, "ismount", lambda p: p == mounted)

    assert mount_at_path(mounted, {}) is not None
    assert mount_at_path(str(tmp_path), {}) is None


@posix_paths
def test_mount_for_path_picks_the_longest_containing_mount():
    table = {
        "/": MountPoint(path="/", source="/dev/sda2", fstype="btrfs"),
        "/mnt": MountPoint(path="/mnt", source="/dev/sdb1", fstype="ext4"),
        "/mnt/usb": MountPoint(path="/mnt/usb", source="/dev/sdc1", fstype="exfat"),
    }

    assert mount_for_path("/mnt/usb/Managed_ISOs", table).fstype == "exfat"
    assert mount_for_path("/mnt/other", table).fstype == "ext4"
    assert mount_for_path("/home/ana", table).fstype == "btrfs"


# -------------------------------------------------------------- linux drives

HOST_TOTAL = 250 * 1024 ** 3
HOST_FREE = 100 * 1024 ** 3


@pytest.fixture
def linux_media(tmp_path, monkeypatch):
    """Stand-ins for /media, /run/media and /mnt, plus the mount table.

    Every path reports the host filesystem's capacity, which is exactly what an
    unmounted directory does in real life.
    """
    if os.name != "posix":
        pytest.skip("Linux mount-table paths")

    roots = []
    for name in ("media", "run-media", "mnt"):
        path = tmp_path / name
        path.mkdir()
        roots.append(str(path))

    table = {}
    monkeypatch.setattr(drive_mod, "LINUX_MOUNT_ROOTS", tuple(roots))
    monkeypatch.setattr(drive_mod, "read_mount_table", lambda: table)
    monkeypatch.setattr(drive_mod.platform, "system", lambda: "Linux")
    monkeypatch.setattr(
        drive_mod.shutil, "disk_usage",
        lambda _path: (HOST_TOTAL, HOST_TOTAL - HOST_FREE, HOST_FREE),
    )
    return roots, table


def _directory(root, *parts):
    path = os.path.join(root, *parts)
    os.makedirs(path, exist_ok=True)
    return path


def _mount(table, root, *parts, fstype="exfat", read_only=False, source="/dev/sdc1"):
    path = os.path.realpath(_directory(root, *parts))
    table[path] = MountPoint(path=path, source=source, fstype=fstype,
                             read_only=read_only)
    return path


def test_unmounted_directories_are_not_drives(linux_media):
    """The reported bug: empty folders under /mnt listed as drives."""
    (media, run_media, mnt), table = linux_media
    _directory(mnt, "usb")
    _directory(mnt, "backup")
    _directory(media, "cdrom")
    mounted = _mount(table, mnt, "ventoy")

    drives = DriveDetector.get_drives()

    assert [d.path for d in drives] == [mounted]


def test_a_mounted_drive_reports_its_filesystem(linux_media):
    (_media, _run_media, mnt), table = linux_media
    _mount(table, mnt, "ventoy", fstype="exfat")

    drive = DriveDetector.get_drives()[0]

    assert drive.filesystem == "exfat"
    assert drive.total_gb == pytest.approx(250, abs=0.1)
    assert drive.warning == ""


def test_per_user_media_directories_are_searched(linux_media):
    """udisks2 mounts at /run/media/<user>/<label>; the middle directory is
    not itself a mount."""
    (_media, run_media, _mnt), table = linux_media
    _directory(run_media, "ana")
    drive_dir = _mount(table, run_media, "ana", "VENTOY")

    assert [d.path for d in DriveDetector.get_drives()] == [drive_dir]


def test_pseudo_filesystems_are_not_drives(linux_media):
    (media, _run_media, mnt), table = linux_media
    _mount(table, media, "nas", fstype="autofs")
    _mount(table, mnt, "cgroup", fstype="cgroup2")

    assert DriveDetector.get_drives() == []


def test_a_drive_reachable_from_two_roots_is_listed_once(linux_media, monkeypatch):
    (media, _run_media, _mnt), table = linux_media
    drive_dir = _mount(table, media, "VENTOY")
    # The same directory offered under a second root, as /media and
    # /media/<user> overlap on a Debian desktop.
    monkeypatch.setattr(drive_mod, "LINUX_MOUNT_ROOTS",
                        (media, os.path.dirname(media)))

    assert [d.path for d in DriveDetector.get_drives()] == [drive_dir]


def test_ventoy_drives_are_listed_first(linux_media):
    (_media, _run_media, mnt), table = linux_media
    plain = _mount(table, mnt, "photos")
    ventoy = _mount(table, mnt, "stick")
    os.makedirs(os.path.join(ventoy, "ventoy"))

    assert [d.path for d in DriveDetector.get_drives()] == [ventoy, plain]


def test_read_only_mount_is_listed_with_a_warning(linux_media):
    """Hiding it would be worse: a dirty exFAT partition gets mounted
    read-only, and the user needs to be told why VEIM cannot write to it."""
    (_media, _run_media, mnt), table = linux_media
    _mount(table, mnt, "ventoy", read_only=True)

    drive = DriveDetector.get_drives()[0]

    assert "read-only" in drive.warning


# -------------------------------------------------------------- inspect_path

def test_inspect_path_reports_the_filesystem_it_sits_on(linux_media):
    (_media, _run_media, mnt), table = linux_media
    mounted = _mount(table, mnt, "ventoy", fstype="btrfs")
    inside = _directory(mounted, "Managed_ISOs")

    assert DriveDetector.inspect_path(inside, table).filesystem == "btrfs"


def test_inspect_path_still_describes_a_browsed_folder(linux_media, tmp_path):
    """Browse Folder... may point anywhere; an unknown filesystem is not an
    error, it just goes unnamed."""
    folder = _directory(str(tmp_path), "isos")

    info = DriveDetector.inspect_path(folder, {})

    assert info is not None
    assert info.filesystem == ""
    assert info.total_gb == pytest.approx(250, abs=0.1)


def test_inspect_path_rejects_what_is_not_a_directory(tmp_path):
    missing = tmp_path / "nowhere"

    assert DriveDetector.inspect_path(str(missing)) is None
