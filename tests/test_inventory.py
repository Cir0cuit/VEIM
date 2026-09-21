"""Inventory bookkeeping tests.

The dashboard renders one card per inventory entry, so any bookkeeping slip
here shows up directly as a wrong or duplicated card in the UI.
"""
import os

from src.core.inventory import InventoryManager, InventoryItem


def test_auto_discovers_untracked_iso(drive_root, make_iso):
    make_iso("archlinux-2026.03.01-x86_64.iso", 4096)

    inv = InventoryManager(drive_root)

    items = inv.get_all_items()
    assert len(items) == 1
    assert items[0].key == "arch"
    assert items[0].size_bytes == 4096


def test_one_entry_per_file_when_flavor_id_differs(drive_root, make_iso):
    """Regression: the same ISO must never occupy two inventory slots.

    sync_filesystem() guesses a flavor_id from the filename. If a later
    add_or_update() supplies a different flavor_id for that same file, the
    naive implementation keys them separately and the dashboard draws two
    cards for one ISO - one of them with a bogus 0.0 MB size.
    """
    fname = make_iso("archlinux-2026.03.01-x86_64.iso", 4096)
    inv = InventoryManager(drive_root)

    # Auto-discovery guessed flavor "standard"; now claim the same file under
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


def test_two_isos_guessing_same_key_both_survive(drive_root, make_iso):
    """Regression: distinct ISOs that guess to one key must not overwrite.

    Both of these resolve to key "fedora"; the naive implementation keyed them
    identically and the first silently vanished from the drive listing.
    """
    make_iso("Fedora-Workstation-Live-x86_64-44.iso", 1024)
    make_iso("Fedora-Workstation-Live-x86_64-43.iso", 2048)

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
    by_file = {item.filename: ck for ck, item in inv.items.items()}
    assert len(by_file) == 2

    assert inv.remove_entry(by_file[second])

    assert not os.path.exists(os.path.join(managed_dir, second))
    assert os.path.exists(os.path.join(managed_dir, first)), "the other ISO was deleted"
    assert [i.filename for i in inv.get_all_items()] == [first]
