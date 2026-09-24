"""Drive detection.

The regression these guard against: every directory under /mnt and /media was
offered as a drive whether or not anything was mounted on it. An empty
leftover directory reports the root filesystem's capacity through
shutil.disk_usage(), so the picker filled up with phantom drives all claiming
the system disk's free space.
"""
import os
from types import SimpleNamespace

import pytest

from src.core import drive as drive_mod
from src.core.drive import DriveDetector

# Mount points are a Linux artefact and so are the paths below: these tests
# feed POSIX paths through os.path.realpath(), which on Windows turns /mnt/usb
# into C:\mnt\usb. The scan they cover never runs there - get_drives() hands
# Windows off to the drive-letter branch - so they are skipped rather than
# rewritten in a path flavour the code never sees.
posix_paths = pytest.mark.skipif(
    os.name != "posix", reason="Linux mount-table paths",
)


# ------------------------------------------------------------- mount points

@posix_paths
def test_only_a_mount_point_is_a_volume(tmp_path):
    """Asked about a directory that is not a mount point, Qt answers for the
    mount it lives on; that answer must not pass for a drive."""
    assert drive_mod._volume_at("/") is not None
    assert drive_mod._volume_at(str(tmp_path)) is None


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

    table = {}  # mount point -> (fstype, read_only)

    def volume(path):
        """QStorageInfo over `table`: the longest mount point holding `path`."""
        path = os.path.realpath(path)
        root = max((m for m in table if path == m or path.startswith(m + os.sep)),
                   key=len, default="")
        fstype, read_only = table.get(root, ("", False))
        return SimpleNamespace(isValid=lambda: bool(root), rootPath=lambda: root,
                               fileSystemType=lambda: fstype.encode(),
                               isReadOnly=lambda: read_only, name=lambda: "")

    mountinfo = tmp_path / "mountinfo"
    mountinfo.write_text("")

    monkeypatch.setattr(drive_mod, "LINUX_MOUNT_ROOTS", tuple(roots))
    monkeypatch.setattr(drive_mod, "MOUNTINFO_PATH", str(mountinfo))
    monkeypatch.setattr(drive_mod, "QStorageInfo", volume)
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


def _mount(table, root, *parts, fstype="exfat", read_only=False):
    path = os.path.realpath(_directory(root, *parts))
    table[path] = (fstype, read_only)
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


def test_an_automount_point_is_never_asked_about(linux_media, monkeypatch):
    """statfs() on an autofs mount point mounts the share behind it, and blocks
    the picker for the mount timeout when that share is unreachable."""
    (media, _run_media, mnt), table = linux_media
    trap = os.path.realpath(_directory(mnt, "my nas", "inside"))
    nested = os.path.realpath(_directory(media, "ana", "share"))
    fired = _mount(table, mnt, "backup", fstype="nfs4")
    with open(drive_mod.MOUNTINFO_PATH, "w") as mountinfo:
        for path in (os.path.dirname(trap), nested, fired):
            escaped = path.replace(" ", "\\040")
            mountinfo.write(f"40 25 0:40 / {escaped} rw,relatime shared:9 - autofs systemd-1 rw,fd=45\n")
        mountinfo.write(f"41 40 0:41 / {fired} rw,relatime shared:10 - nfs4 nas:/backup rw\n")
    asked = []
    volume = drive_mod.QStorageInfo
    monkeypatch.setattr(drive_mod, "QStorageInfo", lambda path: asked.append(os.path.realpath(path)) or volume(path))

    assert [d.path for d in DriveDetector.get_drives()] == [fired]
    assert not [p for p in asked if p.startswith((os.path.dirname(trap), nested))]


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

    assert DriveDetector.inspect_path(inside).filesystem == "btrfs"


def test_inspect_path_still_describes_a_browsed_folder(linux_media, tmp_path):
    """Browse Folder... may point anywhere; an unknown filesystem is not an
    error, it just goes unnamed."""
    folder = _directory(str(tmp_path), "isos")

    info = DriveDetector.inspect_path(folder)

    assert info is not None
    assert info.filesystem == ""
    assert info.total_gb == pytest.approx(250, abs=0.1)


def test_inspect_path_rejects_what_is_not_a_directory(tmp_path):
    missing = tmp_path / "nowhere"

    assert DriveDetector.inspect_path(str(missing)) is None
