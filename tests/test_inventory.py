"""Inventory bookkeeping tests.

The dashboard renders one card per inventory entry, so any bookkeeping slip
here shows up directly as a wrong or duplicated card in the UI.
"""
import json
import time
import os

import pytest

from src.core.inventory import InventoryItem, InventoryManager, UnmanagedImage
from src.core.iso_identity import identify
from src.core.ventoy_config import VentoyConfig


def adopt_all(inv):
    for candidate in inv.find_candidates():
        assert inv.adopt(candidate, candidate.filename) == ""


def test_untracked_iso_is_offered_not_adopted(drive_root, make_iso):
    """An ISO found on the drive is a candidate. Tracking it is the user's call."""
    make_iso("archlinux-2026.03.01-x86_64.iso", 4096)

    inv = InventoryManager(drive_root)

    assert inv.get_all_items() == []
    [candidate] = inv.find_candidates()
    assert (candidate.identity.key, candidate.identity.version) == ("arch", "2026.03.01")
    assert candidate.in_managed

    assert inv.adopt(candidate, "Arch Linux") == ""
    items = inv.get_all_items()
    assert len(items) == 1
    assert items[0].key == "arch"
    assert items[0].version == "2026.03.01"
    assert items[0].size_bytes == 4096
    assert inv.find_candidates() == []


def test_one_entry_per_file_when_flavor_id_differs(drive_root, make_iso):
    """Regression: the same ISO must never occupy two inventory slots.

    An adopted ISO takes its flavor_id from the filename. If a later
    add_or_update() supplies a different flavor_id for that same file, the
    naive implementation keys them separately and the dashboard draws two
    cards for one ISO - one of them with a bogus 0.0 MB size.
    """
    fname = make_iso("archlinux-2026.03.01-x86_64.iso", 4096)
    inv = InventoryManager(drive_root)
    adopt_all(inv)

    # Adoption filed it as flavor "standard"; now claim the same file under
    # a different flavor, the way a catalog download would.
    inv.add_or_update(
        key="arch",
        flavor_id="base",
        display_name="Arch Linux",
        version="2026.03.01",
        filename=fname,
        size_bytes=890 * 1024 * 1024,
    )

    items = inv.get_all_items()
    assert len(items) == 1, f"expected one entry for one ISO, got {[i.display_name for i in items]}"
    assert items[0].flavor_id == "base"
    assert items[0].size_bytes == 890 * 1024 * 1024


def test_replacing_version_deletes_old_iso(drive_root, make_iso):
    old = make_iso("archlinux-2026.03.01-x86_64.iso", 2048)
    inv = InventoryManager(drive_root)
    inv.add_or_update("arch", "standard", "Arch Linux", "2026.03.01", old, 2048)

    new = make_iso("archlinux-2026.09.01-x86_64.iso", 2048)
    inv.add_or_update("arch", "standard", "Arch Linux", "2026.09.01", new, 2048)

    assert not os.path.exists(os.path.join(drive_root, "Managed_ISOs", old))
    assert len(inv.get_all_items()) == 1
    assert inv.get_all_items()[0].version == "2026.09.01"


def test_missing_file_is_dropped_on_reload(drive_root, make_iso):
    fname = make_iso("debian-13.7.0-amd64-netinst.iso", 1024)
    inv = InventoryManager(drive_root)
    inv.add_or_update("debian", "netinst", "Debian", "13.7.0", fname, 1024)

    os.remove(os.path.join(drive_root, "Managed_ISOs", fname))

    reloaded = InventoryManager(drive_root)
    assert reloaded.get_all_items() == []


def test_size_is_backfilled_from_disk(drive_root, make_iso):
    fname = make_iso("alpine-standard-3.24.1-x86_64.iso", 7777)
    inv = InventoryManager(drive_root)
    inv.add_or_update("alpine", "standard", "Alpine Linux", "3.24.1", fname, size_bytes=0)

    reloaded = InventoryManager(drive_root)
    assert reloaded.get_all_items()[0].size_bytes == 7777


def test_roundtrip_preserves_fields():
    item = InventoryItem(
        key="fedora", flavor_id="kde", display_name="Fedora 44 KDE",
        version="44", filename="f.iso", size_bytes=123, sha256="abc", url="https://x",
    )
    assert InventoryItem.from_dict(item.to_dict()).to_dict() == item.to_dict()


def test_a_record_writes_the_keys_existing_drives_carry():
    """Drives in the field hold inventories written by every earlier release."""
    item = InventoryItem(key="arch", flavor_id="", display_name="Arch Linux",
                         version="2026.09.01", filename="a.iso")
    assert list(item.to_dict()) == ["key", "flavor_id", "display_name", "version",
                                    "filename", "size_bytes", "sha256", "url",
                                    "installed_at"]


def test_two_isos_of_one_distro_and_flavor_both_survive(drive_root, make_iso):
    """Regression: distinct ISOs that resolve to one key must not overwrite.

    Both of these are Fedora Workstation; the naive implementation keyed them
    identically and the first silently vanished from the drive listing.
    """
    make_iso("Fedora-Workstation-Live-44-1.7.x86_64.iso", 1024)
    make_iso("Fedora-Workstation-Live-x86_64-41-1.4.iso", 2048)

    inv = InventoryManager(drive_root)
    adopt_all(inv)

    # And across a restart, which used to collapse them again.
    inv = InventoryManager(drive_root)

    names = sorted(i.filename for i in inv.get_all_items())
    assert len(names) == 2, f"an ISO was dropped: {names}"


def test_removing_a_second_iso_of_the_same_distro_removes_that_one(drive_root, make_iso, managed_dir):
    """Regression: two ISOs can guess to the same distro and flavor, and the
    second is filed under a longer key. Removing it by distro and flavor found
    the first ISO instead, and deleted the wrong file."""
    first = make_iso("archlinux-2026.03.01-x86_64.iso")
    second = make_iso("archlinux-2026.09.01-x86_64.iso")
    inv = InventoryManager(drive_root)
    adopt_all(inv)
    by_file = {item.filename: ck for ck, item in inv.items.items()}
    assert len(by_file) == 2

    assert inv.remove_entry(by_file[second])

    assert not os.path.exists(os.path.join(managed_dir, second))
    assert os.path.exists(os.path.join(managed_dir, first)), "the other ISO was deleted"
    assert [i.filename for i in inv.get_all_items()] == [first]


def test_updating_a_second_iso_of_the_same_distro_replaces_that_one(drive_root, make_iso, managed_dir):
    """Regression: the update was recorded by distro and flavor, which is the
    first ISO's record - so the first ISO's file was deleted and the one that
    was actually updated kept its old file."""
    first = make_iso("archlinux-2026.03.01-x86_64.iso")
    second = make_iso("archlinux-2026.09.01-x86_64.iso")
    inv = InventoryManager(drive_root)
    adopt_all(inv)
    by_file = {item.filename: ck for ck, item in inv.items.items()}

    new = make_iso("archlinux-2026.10.01-x86_64.iso")
    inv.add_or_update("arch", "standard", "Arch Linux", "2026.10.01", new, 1024,
                      ck=by_file[second])

    assert os.path.exists(os.path.join(managed_dir, first)), "the other ISO was deleted"
    assert not os.path.exists(os.path.join(managed_dir, second))
    assert inv.items[by_file[first]].filename == first
    assert inv.items[by_file[second]].filename == new
    assert len(inv.items) == 2


# ----------------------------------------------------------------- adoption

def test_customised_iso_is_never_a_candidate(drive_root, make_iso):
    """Regression: "clonezilla" in the name was enough to file a customised
    image as the official release, with the version "Live" - so it was always
    offered an update, and taking it overwrote the customisation."""
    make_iso("clonezilla-live-galaxybook-20260808.iso")
    make_iso("Win11_25H2_English_x64.iso")
    make_iso("netboot.xyz.iso")             # official, but names no version

    inv = InventoryManager(drive_root)

    assert inv.get_all_items() == []
    assert inv.find_candidates() == []
    assert len(inv.unmanaged_images()) == 3


def test_excluded_iso_is_not_offered_again(drive_root, make_iso):
    fname = make_iso("clonezilla-live-20260705-resolute-amd64.iso")
    inv = InventoryManager(drive_root)
    inv.set_excluded(fname, True)

    reloaded = InventoryManager(drive_root)
    assert reloaded.find_candidates() == []
    [kept] = reloaded.find_candidates(include_excluded=True)
    assert kept.excluded
    assert reloaded.get_all_items() == []

    reloaded.set_excluded(fname, False)
    assert [c.filename for c in InventoryManager(drive_root).find_candidates()] == [fname]


def test_adopting_from_the_drive_root_moves_the_iso(drive_root, managed_dir):
    fname = "debian-13.4.0-amd64-netinst.iso"
    for name in (fname, "my-remaster.iso"):
        with open(os.path.join(drive_root, name), "wb") as fh:
            fh.write(b"iso")
    inv = InventoryManager(drive_root)

    [candidate] = inv.find_candidates()
    assert not candidate.in_managed
    assert inv.adopt(candidate, "Debian Netinst") == ""

    assert os.path.exists(os.path.join(managed_dir, fname))
    assert not os.path.exists(os.path.join(drive_root, fname))
    assert os.path.exists(os.path.join(drive_root, "my-remaster.iso")), "an unrecognised ISO was touched"
    assert inv.get_item("debian", "netinst").version == "13.4.0"


def test_inventory_from_an_older_version_is_cleaned_up_on_load(drive_root, make_iso, managed_dir):
    """What the old adopt-everything sweep wrote: a customised image filed as
    Clonezilla, an ISO nothing can update, and a real one with a placeholder
    version. Only the last belongs in the list - with its real version."""
    def record(key, flavor, version, filename, url=""):
        return dict(key=key, flavor_id=flavor, display_name=filename, version=version,
                    filename=make_iso(filename), url=url)

    records = {
        "clonezilla::alternative": record("clonezilla", "alternative", "Live",
                                          "clonezilla-live-galaxybook-20260808.iso"),
        "custom::default": record("custom", "default", "Manual", "Win11_25H2_English_x64.iso"),
        "zorin::core": record("zorin", "core", "Latest", "Zorin-OS-18-Core-64-bit-r3.iso"),
        # Downloaded by VEIM: kept whatever it is called.
        "netboot::standard": record("netboot", "standard", "3.0.3", "netboot.xyz.iso",
                                    url="https://example.invalid/netboot.xyz.iso"),
        # Filed as "custom" before, but it is a Grml: offered, not silently kept.
        "custom::default::grml-full-2026.04-amd64": record(
            "custom", "default", "Manual", "grml-full-2026.04-amd64.iso"),
    }
    with open(os.path.join(managed_dir, "veim_inventory.json"), "w", encoding="utf-8") as fh:
        json.dump(records, fh)

    inv = InventoryManager(drive_root)

    assert sorted(inv.items) == ["netboot::standard", "zorin::core"]
    assert inv.items["zorin::core"].version == "18.0 r3"
    assert [c.filename for c in inv.find_candidates()] == ["grml-full-2026.04-amd64.iso"]
    # Nothing on the drive was touched.
    assert len(os.listdir(managed_dir)) == 6


# ------------------------------------------------- where Ventoy looks

def test_the_search_root_veim_used_to_write_is_removed_on_opening(drive_root, managed_dir):
    """VEIM before 1.2 confined Ventoy to Managed_ISOs, hiding every image
    anywhere else on the stick. Opening the drive undoes that and nothing else."""
    _ventoy_json(drive_root,
                 control=[{"VTOY_DEFAULT_SEARCH_ROOT": "/Managed_ISOs"},
                          {"VTOY_MENU_TIMEOUT": "10"}],
                 password={"bootpwd": "txt#secret"})

    InventoryManager(drive_root)

    data = json.load(open(os.path.join(drive_root, "ventoy", "ventoy.json"), encoding="utf-8"))
    assert data["control"] == [{"VTOY_MENU_TIMEOUT": "10"}]
    assert data["password"] == {"bootpwd": "txt#secret"}


def test_a_search_root_the_user_chose_stays_and_is_where_images_are_listed(
        drive_root, managed_dir):
    _ventoy_json(drive_root, control=[{"VTOY_DEFAULT_SEARCH_ROOT": "/ISO"}])
    _put(drive_root, "ISO/win.iso")
    _put(drive_root, "elsewhere.iso")

    inv = InventoryManager(drive_root)

    assert inv.ventoy_config.search_root() == "/ISO"
    assert [i.ventoy_path for i in inv.unmanaged_images()] == ["/ISO/win.iso"]


def test_veim_never_restricts_the_search(drive_root, make_iso):
    inv = InventoryManager(drive_root)
    inv.add_or_update("arch", "standard", "Arch Linux", "2026.09.01",
                      make_iso("archlinux-2026.09.01-x86_64.iso"), url="https://example.invalid/a.iso")

    data = json.load(open(os.path.join(drive_root, "ventoy", "ventoy.json"), encoding="utf-8"))
    assert "control" not in data
    assert VentoyConfig(drive_root).search_root() == ""


def test_a_fedora_spin_installed_before_the_split_keeps_working(drive_root, make_iso, managed_dir):
    """Fedora became four catalog entries. A Cinnamon spin recorded under
    "fedora" has to follow its flavor to "fedora_spins", or its row could no
    longer be checked - the Fedora entry has no such flavor any more."""

    fname = make_iso("Fedora-Cinnamon-Live-44-1.7.x86_64.iso")
    kde = make_iso("Fedora-KDE-Desktop-Live-44-1.7.x86_64.iso")
    records = {
        "fedora::cinnamon": dict(key="fedora", flavor_id="cinnamon", display_name="Fedora Cinnamon",
                                 version="44", filename=fname, url="https://example.invalid/c.iso"),
        "fedora::kde": dict(key="fedora", flavor_id="kde", display_name="Fedora KDE",
                            version="44", filename=kde),
    }
    with open(os.path.join(managed_dir, "veim_inventory.json"), "w", encoding="utf-8") as fh:
        json.dump(records, fh)

    inv = InventoryManager(drive_root)

    assert sorted(inv.items) == ["fedora::kde", "fedora_spins::cinnamon"]
    assert inv.items["fedora_spins::cinnamon"].key == "fedora_spins"


# ------------------------------------------------ images VEIM does not manage


def _put(folder, relpath, size=16):
    full = os.path.join(folder, *relpath.split("/"))
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "wb") as fh:
        fh.write(b"\0" * size)
    return full


def _ventoy_json(drive_root, **data):
    os.makedirs(os.path.join(drive_root, "ventoy"), exist_ok=True)
    with open(os.path.join(drive_root, "ventoy", "ventoy.json"), "w", encoding="utf-8") as fh:
        json.dump(data, fh)


def test_walk_finds_what_ventoy_lists(managed_dir):
    for rel in ("top.iso", "a/win.WIM", "a/b/disk.vhd.vtoy", "a/b/c/deep.efi",
                "notes.txt", "a/b/half.iso.part"):
        _put(managed_dir, rel)
    _put(managed_dir, "skipped/hidden.iso")
    _put(managed_dir, "skipped/.ventoyignore")
    _put(managed_dir, "a/b/ign/nested/x.iso")
    _put(managed_dir, "a/b/ign/.ventoyignore")

    walk = InventoryManager._walk_images
    assert walk(managed_dir, None) == ["a/b/c/deep.efi", "a/b/disk.vhd.vtoy",
                                       "a/win.WIM", "top.iso"]
    assert walk(managed_dir, 0) == ["top.iso"]
    assert walk(managed_dir, 1) == ["a/win.WIM", "top.iso"]


def test_walk_skips_what_ventoy_skips(drive_root):
    """As Ventoy's ventoy_cmd.c does: a .ventoyignore matched by prefix and
    only below the search root, trash folders compared case and all, and the
    helpers of its WIM and VHD plugins."""
    for rel in ("top.iso", ".ventoyignore",                # not below the root
                "notepad/x.iso", "notepad/.ventoyignore.txt",
                "$RECYCLE.BIN/S-1-5-21/$R1.iso", ".Trashes/501/a.iso",
                ".trash-0/files/b.iso", ".Trash-1000/files/listed.iso",
                "ventoy/ventoy_wimboot.img", "ventoy/ventoy_vhdboot.img", "ventoy/mine.img"):
        _put(drive_root, rel)

    walk = InventoryManager._walk_images
    assert walk(drive_root) == [".Trash-1000/files/listed.iso", "top.iso", "ventoy/mine.img"]
    assert "$RECYCLE.BIN/S-1-5-21/$R1.iso" in walk(drive_root, skip_trash=False)


def test_walk_of_a_missing_folder_finds_nothing(drive_root):
    assert InventoryManager._walk_images(os.path.join(drive_root, "nope"), None) == []


def test_unmanaged_images_lists_what_ventoy_boots_and_veim_does_not_track(drive_root, managed_dir, make_iso):
    tracked = make_iso("archlinux-2026.09.01-x86_64.iso", 100)
    inv = InventoryManager(drive_root)
    inv.add_or_update("arch", "standard", "Arch Linux", "2026.09.01", tracked, 100,
                      url="https://example.invalid/a.iso")
    _put(managed_dir, "debian-13.4.0-amd64-netinst.iso", 30)
    _put(drive_root, "tools/shellx64.efi", 20)
    _put(drive_root, "Win11_25H2_English_x64.iso")
    _put(managed_dir, "old/" + tracked)            # same name, different file: untracked
    _put(drive_root, "deep/er/clonezilla-live-20260705-resolute-amd64.iso")
    _put(drive_root, "ignored/.ventoyignore")
    _put(drive_root, "ignored/skipped.iso")
    inv.set_excluded("clonezilla-live-20260705-resolute-amd64.iso", True)
    VentoyConfig(drive_root).set_alias("/tools/shellx64.efi", "Shell")

    images = {i.ventoy_path: i for i in InventoryManager(drive_root).unmanaged_images()}

    assert sorted(images) == [
        "/Managed_ISOs/debian-13.4.0-amd64-netinst.iso",
        "/Managed_ISOs/old/" + tracked,
        "/Win11_25H2_English_x64.iso",
        "/deep/er/clonezilla-live-20260705-resolute-amd64.iso",
        "/tools/shellx64.efi",
    ]
    deb = images["/Managed_ISOs/debian-13.4.0-amd64-netinst.iso"]
    assert (deb.identity.key, deb.size_bytes, deb.excluded, deb.kind) == \
        ("debian", 30, False, "ISO image")
    efi = images["/tools/shellx64.efi"]
    assert (efi.path, efi.filename, efi.alias, efi.kind, efi.identity) == \
        ("tools/shellx64.efi", "shellx64.efi", "Shell", "EFI application", None)
    deep = images["/deep/er/clonezilla-live-20260705-resolute-amd64.iso"]
    assert deep.excluded and deep.identity.key == "clonezilla"


@pytest.mark.parametrize("level, listed", [
    ("0", ["top.iso"]),
    ("1", ["Managed_ISOs/mine.iso", "top.iso"]),
    ("2", ["Managed_ISOs/mine.iso", "Managed_ISOs/sub/deep.iso", "top.iso"]),
])
def test_unmanaged_images_honour_the_search_level(drive_root, managed_dir, level, listed):
    """Counted from the drive root, where Ventoy starts."""
    _put(drive_root, "top.iso")
    _put(managed_dir, "mine.iso")
    _put(managed_dir, "sub/deep.iso")
    _ventoy_json(drive_root, control=[{"VTOY_MAX_SEARCH_LEVEL": level}])
    assert [i.path for i in InventoryManager(drive_root).unmanaged_images()] == listed


@pytest.mark.parametrize("name, kind", [
    ("a.iso", "ISO image"), ("a.wim", "Windows image"), ("a.img", "disk image"),
    ("a.vhdx", "virtual disk"), ("a.vhd.vtoy", "virtual disk"), ("A.EFI", "EFI application"),
])
def test_kind(name, kind):
    assert UnmanagedImage(name, 0, None, False, "").kind == kind


def _only(inv, path):
    [image] = [i for i in inv.unmanaged_images() if i.ventoy_path == path]
    return image


def test_delete_image_removes_the_file_and_its_alias(drive_root, managed_dir):
    full = _put(managed_dir, "sub/mine.img")
    inv = InventoryManager(drive_root)
    inv.set_image_alias(_only(inv, "/Managed_ISOs/sub/mine.img"), "Mine")

    assert inv.delete_image(_only(inv, "/Managed_ISOs/sub/mine.img")) == ""

    assert not os.path.exists(full)
    assert VentoyConfig(drive_root).data["menu_alias"] == []


def test_delete_of_a_vanished_image_reports_it(drive_root, managed_dir):
    inv = InventoryManager(drive_root)
    assert inv.delete_image(UnmanagedImage("gone.iso", 0, None, False, ""))


def test_a_managed_iso_is_named_for_what_it_is_and_renamed_by_updates(
        drive_root, managed_dir, make_iso):
    old = make_iso("archlinux-2026.03.01-x86_64.iso")
    inv = InventoryManager(drive_root)
    inv.add_or_update("arch", "standard", "Arch Linux", "2026.03.01", old,
                      url="https://example.invalid/a.iso")
    assert VentoyConfig(drive_root).alias_for("/Managed_ISOs/" + old) == "Arch Linux 2026.03.01"

    new = make_iso("archlinux-2026.09.01-x86_64.iso")
    inv.add_or_update("arch", "standard", "Arch Linux", "2026.09.01", new,
                      url="https://example.invalid/a.iso")
    cfg = VentoyConfig(drive_root)
    assert cfg.alias_for("/Managed_ISOs/" + new) == "Arch Linux 2026.09.01"
    assert cfg.alias_for("/Managed_ISOs/" + old) == ""


def test_a_record_with_an_alias_from_a_development_build_loads(
        drive_root, managed_dir, make_iso):
    named = make_iso("debian-13.4.0-amd64-netinst.iso")
    with open(os.path.join(managed_dir, "veim_inventory.json"), "w", encoding="utf-8") as fh:
        json.dump({"debian::netinst": dict(key="debian", flavor_id="netinst",
                                           display_name="Debian Netinst", version="13.4.0",
                                           filename=named, url="https://x", alias="Mine")}, fh)

    inv = InventoryManager(drive_root)
    inv.save()

    assert list(inv.items) == ["debian::netinst"]
    assert VentoyConfig(drive_root).alias_for("/Managed_ISOs/" + named) == "Debian Netinst 13.4.0"


def test_adopting_from_a_subfolder_moves_it_up_and_names_it(drive_root, managed_dir):
    fname = "debian-13.4.0-amd64-netinst.iso"
    _put(managed_dir, "isos/" + fname, 64)
    inv = InventoryManager(drive_root)
    inv.set_image_alias(_only(inv, "/Managed_ISOs/isos/" + fname), "My Debian")

    assert inv.adopt(_only(inv, "/Managed_ISOs/isos/" + fname), "Debian Netinst") == ""

    assert os.path.getsize(os.path.join(managed_dir, fname)) == 64
    assert not os.path.exists(os.path.join(managed_dir, "isos", fname))
    item = InventoryManager(drive_root).get_item("debian", "netinst")
    assert (item.display_name, item.version) == ("Debian Netinst", "13.4.0")
    cfg = VentoyConfig(drive_root)
    assert cfg.alias_for("/Managed_ISOs/" + fname) == "Debian Netinst 13.4.0"
    assert cfg.alias_for("/Managed_ISOs/isos/" + fname) == ""
    assert inv.unmanaged_images() == []


def test_adopting_from_a_subfolder_never_overwrites(drive_root, managed_dir):
    fname = "debian-13.4.0-amd64-netinst.iso"
    _put(managed_dir, "isos/" + fname, 64)
    _put(managed_dir, fname, 8)                 # a different file of the same name
    inv = InventoryManager(drive_root)
    inv.set_excluded(fname, True)               # not taken in by its top-level twin
    image = _only(inv, "/Managed_ISOs/isos/" + fname)

    assert inv.adopt(image, "Debian Netinst")

    assert inv.get_all_items() == []
    assert os.path.getsize(os.path.join(managed_dir, "isos", fname)) == 64
    assert os.path.getsize(os.path.join(managed_dir, fname)) == 8


def test_unknown_images_are_not_adoptable(drive_root):
    inv = InventoryManager(drive_root)
    _put(drive_root, "Managed_ISOs/custom.iso")
    [image] = inv.unmanaged_images()
    assert inv.adopt(image, "x")
    assert inv.get_all_items() == []


def test_any_bootable_file_is_seen_in_the_root(drive_root, make_iso):
    """Ventoy boots EFI applications and disk images as well as ISOs."""
    inv = InventoryManager(drive_root)
    inv.add_or_update("arch", "standard", "Arch Linux", "2026.09.01",
                      make_iso("archlinux-2026.09.01-x86_64.iso"), url="https://example.invalid/a.iso")
    for name in ("shellx64.efi", "win.vhdx", "readme.txt", "memtest86plus-8.10-x86_64.iso"):
        _put(drive_root, name)

    assert sorted(i.path for i in inv.unmanaged_images()) == [
        "memtest86plus-8.10-x86_64.iso", "shellx64.efi", "win.vhdx"]
    assert [c.filename for c in inv.find_candidates()] == ["memtest86plus-8.10-x86_64.iso"]


def test_adopting_replaces_a_name_chosen_before_with_the_automatic_one(
        drive_root, managed_dir, make_iso):
    fname = make_iso("debian-13.4.0-amd64-netinst.iso")
    inv = InventoryManager(drive_root)
    inv.set_image_alias(_only(inv, "/Managed_ISOs/" + fname), "My Debian")

    [candidate] = inv.find_candidates()
    assert inv.adopt(candidate, "Debian Netinst") == ""

    assert VentoyConfig(drive_root).alias_for("/Managed_ISOs/" + fname) == "Debian Netinst 13.4.0"


def test_adopting_from_the_root_leaves_no_name_behind(drive_root, managed_dir):
    fname = "debian-13.4.0-amd64-netinst.iso"
    _put(drive_root, fname)
    _ventoy_json(drive_root, menu_alias=[{"image": "/" + fname, "alias": "Root Debian"}])
    inv = InventoryManager(drive_root)

    [candidate] = inv.find_candidates()
    assert inv.adopt(candidate, "Debian Netinst") == ""

    cfg = VentoyConfig(drive_root)
    assert cfg.alias_for("/Managed_ISOs/" + fname) == "Debian Netinst 13.4.0"
    assert cfg.alias_for("/" + fname) == ""


@pytest.mark.parametrize("control, ok", [
    ([], True),
    ([{"VTOY_MAX_SEARCH_LEVEL": "1"}], True),
    ([{"VTOY_MAX_SEARCH_LEVEL": "0"}], False),
    ([{"VTOY_DEFAULT_SEARCH_ROOT": "/ISO"}], False),
    ([{"VTOY_DEFAULT_SEARCH_ROOT": "/Managed_ISOs/"}, {"VTOY_MAX_SEARCH_LEVEL": "0"}], True),
])
def test_nothing_is_adopted_into_a_folder_the_boot_menu_does_not_list(
        drive_root, managed_dir, control, ok):
    """Moving it into Managed_ISOs would take it out of the menu, quietly."""
    _put(drive_root, "ISO/debian-13.4.0-amd64-netinst.iso")
    _put(drive_root, "debian-13.4.0-amd64-netinst.iso")
    _ventoy_json(drive_root, control=control)
    inv = InventoryManager(drive_root)

    assert inv.managed_in_menu() == ok
    if not ok:
        image = UnmanagedImage("ISO/debian-13.4.0-amd64-netinst.iso", 1,
                               identify("debian-13.4.0-amd64-netinst.iso"), False, "")
        assert "boot menu" in inv.adopt(image, "Debian Netinst")
        assert os.path.exists(os.path.join(drive_root, "ISO", "debian-13.4.0-amd64-netinst.iso"))
        assert inv.items == {}


def test_a_tracked_iso_renamed_only_in_case_is_not_unmanaged(drive_root, managed_dir, make_iso):
    fname = make_iso("ubuntu-24.04.2-desktop-amd64.iso")
    inv = InventoryManager(drive_root)
    inv.add_or_update("ubuntu", "desktop", "Ubuntu", "24.04.2", fname, url="https://x/y.iso")
    os.rename(os.path.join(managed_dir, fname), os.path.join(managed_dir, "tmp.iso"))
    os.rename(os.path.join(managed_dir, "tmp.iso"), os.path.join(managed_dir, fname.upper()))

    inv = InventoryManager(drive_root)
    if not inv.items:
        pytest.skip("case-sensitive filesystem: the record no longer finds its file")
    assert inv.unmanaged_images() == []
    assert inv.find_candidates() == []


def test_a_file_tracked_meanwhile_is_neither_deleted_nor_adopted_again(drive_root, managed_dir, make_iso):
    fname = make_iso("ubuntu-24.04.2-desktop-amd64.iso")
    inv = InventoryManager(drive_root)
    stale = _only(inv, "/Managed_ISOs/" + fname)
    # A download lands on that name while a dialog about it is open.
    inv.add_or_update("ubuntu", "desktop", "Ubuntu", "24.04.2", fname, url="https://x/y.iso")

    assert inv.delete_image(stale)
    assert inv.adopt(stale, "Ubuntu")
    assert os.path.exists(os.path.join(managed_dir, fname))
    assert len(inv.items) == 1


@pytest.mark.skipif(os.name != "nt", reason="NTFS junctions")
def test_walk_does_not_follow_a_junction(managed_dir, tmp_path_factory):
    import subprocess
    outside = str(tmp_path_factory.mktemp("elsewhere"))
    _put(outside, "not-on-the-drive.iso")
    link = os.path.join(managed_dir, "link")
    if subprocess.run(["cmd", "/c", "mklink", "/J", link, outside],
                      capture_output=True).returncode:
        pytest.skip("could not create a junction")

    assert InventoryManager._walk_images(managed_dir) == []


# ------------------------------------------- Managed_ISOs holds only VEIM's

# Files a test has just written look as if they were still arriving.
_LATER = time.time() + 3600


def _names_for_catalog(image):
    return {"debian": "Debian Netinst", "grml": "Grml Full"}.get(image.identity.key)


def test_a_drive_from_an_earlier_version_is_sorted_out(drive_root, managed_dir, make_iso):
    """Earlier versions kept everything in Managed_ISOs. Now what VEIM can
    update is adopted where it lies, and the rest goes to the drive root."""
    tracked = make_iso("archlinux-2026.09.01-x86_64.iso")
    inv = InventoryManager(drive_root)
    inv.add_or_update("arch", "standard", "Arch Linux", "2026.09.01", tracked,
                      url="https://example.invalid/a.iso")
    make_iso("debian-13.4.0-amd64-netinst.iso")
    make_iso("clonezilla-live-20260705-resolute-amd64.iso")
    inv.set_excluded("clonezilla-live-20260705-resolute-amd64.iso", True)
    make_iso("custom.iso")
    _put(drive_root, "custom.iso", 3)                    # the root has one already
    make_iso("memtest86plus-8.10-x86_64.iso")            # recognised, edition not offered
    _put(managed_dir, "readme.txt")
    _put(managed_dir, "tools/shellx64.efi")
    _put(managed_dir, "isos/grml-full-2026.09-amd64.iso", 77)
    _put(managed_dir, "ubuntu-24.04.2-desktop-amd64.iso.part")
    VentoyConfig(drive_root).set_alias("/Managed_ISOs/tools/shellx64.efi", "Shell")

    done = {d.name: d for d in inv.tidy_managed(_names_for_catalog, now=_LATER)}

    assert {n for n, d in done.items() if d.outcome == "adopted"} == {
        "debian-13.4.0-amd64-netinst.iso", "isos/grml-full-2026.09-amd64.iso"}
    assert done["custom.iso"].detail == "/custom (2).iso"
    assert "not recognised" in done["custom.iso"].reason
    assert "leave it alone" in done["clonezilla-live-20260705-resolute-amd64.iso"].reason
    assert "no longer offers" in done["memtest86plus-8.10-x86_64.iso"].reason
    assert done["readme.txt"].reason == "not a bootable image"
    assert done["tools"].detail == "/tools"
    assert all(d.outcome != "stayed" for d in done.values())

    assert sorted(os.listdir(managed_dir), key=str.lower) == [
        tracked, "debian-13.4.0-amd64-netinst.iso", "grml-full-2026.09-amd64.iso",
        "ubuntu-24.04.2-desktop-amd64.iso.part", "veim_inventory.json"]
    assert os.path.getsize(os.path.join(drive_root, "custom.iso")) == 3
    assert os.path.exists(os.path.join(drive_root, "tools", "shellx64.efi"))
    assert VentoyConfig(drive_root).alias_for("/tools/shellx64.efi") == "Shell"
    reloaded = InventoryManager(drive_root)
    assert sorted(reloaded.items) == ["arch::standard", "debian::netinst", "grml::full"]
    assert reloaded.tidy_managed(_names_for_catalog, now=_LATER) == [], "a second pass has nothing to do"


def test_tidying_leaves_a_download_in_flight_alone(drive_root, managed_dir, make_iso):
    make_iso("debian-13.4.0-amd64-netinst.iso")      # just written, not yet recorded
    inv = InventoryManager(drive_root)

    assert inv.tidy_managed(_names_for_catalog, busy={"debian-13.4.0-amd64-netinst.iso"},
                             now=_LATER) == []
    assert inv.items == {}


def test_keeping_the_file_moves_it_to_the_drive_root(drive_root, managed_dir, make_iso):
    fname = make_iso("archlinux-2026.09.01-x86_64.iso")
    inv = InventoryManager(drive_root)
    inv.add_or_update("arch", "standard", "Arch Linux", "2026.09.01", fname,
                      url="https://example.invalid/a.iso")

    assert inv.release("arch::standard", exclude=True) == "/" + fname

    assert os.path.exists(os.path.join(drive_root, fname))
    assert not os.path.exists(os.path.join(managed_dir, fname))
    assert [i.ventoy_path for i in inv.unmanaged_images()] == ["/" + fname]


def test_an_image_of_an_edition_being_downloaded_waits(drive_root, managed_dir, make_iso):
    """Adopted now, it would be taken for the release the download replaces -
    and deleted when the download lands."""
    make_iso("ubuntu-24.04.1-desktop-amd64.iso")
    inv = InventoryManager(drive_root)

    assert inv.tidy_managed(_names_for_catalog, busy_editions={("ubuntu", "desktop")},
                            now=_LATER) == []
    assert os.path.exists(os.path.join(managed_dir, "ubuntu-24.04.1-desktop-amd64.iso"))


def test_an_unreadable_inventory_stops_everything(drive_root, managed_dir, make_iso):
    make_iso("debian-13.4.0-amd64-netinst.iso")
    make_iso("custom.iso")
    with open(os.path.join(managed_dir, "veim_inventory.json"), "w", encoding="utf-8") as fh:
        fh.write('{"arch::standard": {"key": "ar')          # pulled out mid-write
    inv = InventoryManager(drive_root)

    assert inv.unreadable
    assert inv.tidy_managed(_names_for_catalog, now=_LATER) == []
    inv.save()
    with open(os.path.join(managed_dir, "veim_inventory.json"), encoding="utf-8") as fh:
        assert fh.read().startswith('{"arch::')
    assert os.path.exists(os.path.join(managed_dir, "custom.iso"))


def test_tidying_reads_the_inventory_as_it_is_now(drive_root, managed_dir, make_iso):
    """Another window, or another stick under the same letter, may have
    recorded files since this one was opened."""
    inv = InventoryManager(drive_root)
    other = InventoryManager(drive_root)
    fname = make_iso("ubuntu_desktop.iso")                 # no identity rule
    other.add_or_update("ubuntu", "desktop", "Ubuntu Desktop", "26.04", fname,
                        url="https://example.invalid/u.iso")

    assert inv.tidy_managed(_names_for_catalog, now=_LATER) == []
    assert os.path.exists(os.path.join(managed_dir, fname))


@pytest.mark.parametrize("arriving", ["sibling", "empty", "fresh"])
def test_a_file_still_arriving_is_left_alone(drive_root, managed_dir, arriving):
    path = _put(managed_dir, "custom.iso", 0 if arriving == "empty" else 16)
    if arriving == "sibling":
        _put(managed_dir, "custom.iso.crdownload")
    now = time.time() + 5 if arriving == "fresh" else _LATER

    assert InventoryManager(drive_root).tidy_managed(_names_for_catalog, now=now) == []
    assert os.path.exists(path)


def test_os_litter_and_a_managed_images_vcfg_stay(drive_root, managed_dir, make_iso):
    fname = make_iso("archlinux-2026.09.01-x86_64.iso")
    inv = InventoryManager(drive_root)
    inv.add_or_update("arch", "standard", "Arch Linux", "2026.09.01", fname,
                      url="https://example.invalid/a.iso")
    for name in ("Thumbs.db", ".DS_Store", "desktop.ini", "._custom.iso", fname + ".vcfg"):
        _put(managed_dir, name)

    assert inv.tidy_managed(_names_for_catalog, now=_LATER) == []


def test_an_image_moved_out_takes_its_vcfg_and_its_plugin_entries(drive_root, managed_dir):
    _put(managed_dir, "custom.iso")
    _put(managed_dir, "custom.iso.vcfg")
    _ventoy_json(drive_root, persistence=[{"image": "/Managed_ISOs/custom.iso",
                                            "backend": "/persistence.dat"}],
                 menu_alias=[{"image": "/Managed_ISOs/custom.iso", "alias": "Mine"}])

    [done] = InventoryManager(drive_root).tidy_managed(_names_for_catalog, now=_LATER)

    assert (done.name, done.detail) == ("custom.iso", "/custom.iso")
    assert os.path.exists(os.path.join(drive_root, "custom.iso.vcfg"))
    with open(os.path.join(drive_root, "ventoy", "ventoy.json"), encoding="utf-8") as fh:
        data = json.load(fh)
    assert data["persistence"] == [{"image": "/custom.iso", "backend": "/persistence.dat"}]
    assert data["menu_alias"] == [{"image": "/custom.iso", "alias": "Mine"}]


def test_a_folder_moved_out_says_why_what_was_inside_was_not_adopted(drive_root, managed_dir):
    _put(managed_dir, "old/debian-13.4.0-amd64-netinst.iso")
    InventoryManager(drive_root).set_excluded("debian-13.4.0-amd64-netinst.iso", True)

    [done] = InventoryManager(drive_root).tidy_managed(_names_for_catalog, now=_LATER)

    assert done.name == "old" and done.outcome == "moved"
    assert "debian-13.4.0-amd64-netinst.iso: you chose to leave it alone" in done.reason


def test_a_released_iso_loses_the_name_veim_gave_it(drive_root, managed_dir, make_iso):
    fname = make_iso("archlinux-2026.09.01-x86_64.iso")
    inv = InventoryManager(drive_root)
    inv.add_or_update("arch", "standard", "Arch Linux", "2026.09.01", fname,
                      url="https://example.invalid/a.iso")

    inv.release("arch::standard", exclude=True)

    cfg = VentoyConfig(drive_root)
    assert cfg.alias_for("/" + fname) == "" and cfg.alias_for("/Managed_ISOs/" + fname) == ""


def test_saving_leaves_no_temporary_file(drive_root, managed_dir, make_iso):
    inv = InventoryManager(drive_root)
    inv.add_or_update("arch", "standard", "Arch Linux", "2026.09.01",
                      make_iso("archlinux-2026.09.01-x86_64.iso"), url="https://x/a.iso")
    assert not [n for n in os.listdir(managed_dir) if n.endswith(".tmp")]
    assert not [n for n in os.listdir(os.path.join(drive_root, "ventoy")) if n.endswith(".tmp")]


def test_a_recipe_writing_versions_differently_offers_no_update_to_the_same_file(
        drive_root, managed_dir, make_iso):
    """elementary went from "8.1" to "8.1 (20260219)"; a row VEIM downloaded
    under the old form must read as the release it is, not as out of date."""
    fname = make_iso("elementaryos-8.1-stable-amd64.20260219.iso")
    with open(os.path.join(managed_dir, "veim_inventory.json"), "w", encoding="utf-8") as fh:
        json.dump({"elementary::stable": dict(
            key="elementary", flavor_id="stable", display_name="elementary OS Stable",
            version="8.1", filename=fname, url="https://example.invalid/e.iso")}, fh)

    item = InventoryManager(drive_root).items["elementary::stable"]

    assert item.version == identify(fname).version != "8.1"
