"""Inventory bookkeeping tests.

The dashboard renders one card per inventory entry, so any bookkeeping slip
here shows up directly as a wrong or duplicated card in the UI.
"""
import os

from src.core.inventory import InventoryManager, InventoryItem


def adopt_all(inv):
    for candidate in inv.find_candidates():
        assert inv.adopt(candidate, candidate.filename)


def test_untracked_iso_is_offered_not_adopted(drive_root, make_iso):
    """An ISO found on the drive is a candidate. Tracking it is the user's call."""
    make_iso("archlinux-2026.03.01-x86_64.iso", 4096)

    inv = InventoryManager(drive_root)

    assert inv.get_all_items() == []
    [candidate] = inv.find_candidates()
    assert (candidate.identity.key, candidate.identity.version) == ("arch", "2026.03.01")
    assert not candidate.in_root

    assert inv.adopt(candidate, "Arch Linux")
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
    assert len(inv.unmanaged_files()) == 3


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
    assert candidate.in_root
    assert inv.adopt(candidate, "Debian Netinst")

    assert os.path.exists(os.path.join(managed_dir, fname))
    assert not os.path.exists(os.path.join(drive_root, fname))
    assert os.path.exists(os.path.join(drive_root, "my-remaster.iso")), "an unrecognised ISO was touched"
    assert inv.get_item("debian", "netinst").version == "13.4.0"


def test_inventory_from_an_older_version_is_cleaned_up_on_load(drive_root, make_iso, managed_dir):
    """What the old adopt-everything sweep wrote: a customised image filed as
    Clonezilla, an ISO nothing can update, and a real one with a placeholder
    version. Only the last belongs in the list - with its real version."""
    import json

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
    assert inv.items["zorin::core"].version == "18"
    assert [c.filename for c in inv.find_candidates()] == ["grml-full-2026.04-amd64.iso"]
    # Nothing on the drive was touched.
    assert len(os.listdir(managed_dir)) == 6
