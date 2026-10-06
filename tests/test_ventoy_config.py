"""ventoy.json bookkeeping.

The boot menu's names live in ventoy.json, shared with whatever the user put
there by hand. Every slip here either renames an image the user named
themselves or leaves a menu entry pointing at nothing.
"""
import json
import os

import pytest

from src.core.ventoy_config import VentoyConfig, is_bootable


@pytest.mark.parametrize("name", [
    "a.iso", "B.ISO", "win.wim", "disk.img", "x.vhd", "x.VHDX", "netboot.xyz.efi",
    "win11.vhd.vtoy",
])
def test_ventoy_boots_these(name):
    assert is_bootable(name)


@pytest.mark.parametrize("name", [
    "a.iso.part", "a.iso.zip", "readme.txt", "veim_inventory.json", ".ventoyignore", "iso",
])
def test_ventoy_does_not_boot_these(name):
    assert not is_bootable(name)


def _write(drive_root, data):
    os.makedirs(os.path.join(drive_root, "ventoy"), exist_ok=True)
    with open(os.path.join(drive_root, "ventoy", "ventoy.json"), "w", encoding="utf-8") as fh:
        json.dump(data, fh)


@pytest.mark.parametrize("value, level", [
    ("0", 0), ("2", 2), ("max", None), ("-1", None), ("", None),
])
def test_max_search_level(drive_root, value, level):
    _write(drive_root, {"control": [{"VTOY_DEFAULT_SEARCH_ROOT": "/ISO"},
                                    {"VTOY_MAX_SEARCH_LEVEL": value}]})
    assert VentoyConfig(drive_root).max_search_level() == level


def test_dropping_the_old_search_root_keeps_a_depth_limit_reaching_as_deep(drive_root):
    """Counted from Managed_ISOs before, from the drive root after."""
    _write(drive_root, {"control": [{"VTOY_DEFAULT_SEARCH_ROOT": "/Managed_ISOs"},
                                    {"VTOY_MAX_SEARCH_LEVEL": "0"}]})
    cfg = VentoyConfig(drive_root)
    assert cfg.dropped_old_defaults
    assert cfg.search_root() == "" and cfg.max_search_level() == 1


def test_no_search_level_means_unlimited(drive_root):
    assert VentoyConfig(drive_root).max_search_level() is None


def test_alias_set_read_moved_and_removed(drive_root):
    cfg = VentoyConfig(drive_root)
    cfg.set_alias("/Managed_ISOs/a.iso", "Mine")
    assert VentoyConfig(drive_root).alias_for("/Managed_ISOs/a.iso") == "Mine"

    cfg.set_alias("/Managed_ISOs/a.iso", "Renamed")
    assert [a["alias"] for a in cfg.data["menu_alias"]] == ["Renamed"]

    cfg.move_alias("/Managed_ISOs/a.iso", "/Managed_ISOs/b.iso")
    reread = VentoyConfig(drive_root)
    assert reread.alias_for("/Managed_ISOs/a.iso") == ""
    assert reread.alias_for("/Managed_ISOs/b.iso") == "Renamed"

    cfg.set_alias("/Managed_ISOs/b.iso", "")
    assert VentoyConfig(drive_root).data["menu_alias"] == []


def test_non_ascii_alias_is_written_as_utf8_and_reads_back(drive_root):
    """Ventoy reads ventoy.json as UTF-8; a \\u escape would show as itself."""
    cfg = VentoyConfig(drive_root)
    cfg.set_alias("/Managed_ISOs/a.iso", "Système Łódź")

    with open(cfg.config_file, "rb") as fh:
        raw = fh.read()
    assert "Système Łódź".encode("utf-8") in raw
    assert b"\\u" not in raw
    assert VentoyConfig(drive_root).alias_for("/Managed_ISOs/a.iso") == "Système Łódź"


def test_sync_rewrites_tracked_keeps_untracked_and_drops_missing(drive_root, managed_dir):
    """Regression: every alias under /Managed_ISOs/ was thrown away on each
    save, so a menu name given to an image VEIM does not track lasted until
    the next download finished."""
    for name in ("tracked.iso", "theirs.iso"):
        open(os.path.join(managed_dir, name), "wb").close()
    sub = os.path.join(managed_dir, "sub")
    os.makedirs(sub)
    open(os.path.join(sub, "deep.wim"), "wb").close()
    dir_entry = {"dir": "/Managed_ISOs/sub", "alias": "A folder"}
    elsewhere = {"image": "/Other/gone.iso", "alias": "Not ours to judge"}
    _write(drive_root, {"menu_alias": [
        {"image": "/Managed_ISOs/tracked.iso", "alias": "Old name"},
        {"image": "/Managed_ISOs/theirs.iso", "alias": "My own"},
        {"image": "/Managed_ISOs/sub/deep.wim", "alias": "Deep"},
        {"image": "/Managed_ISOs/deleted.iso", "alias": "Gone"},
        dir_entry,
        elsewhere,
    ]})

    cfg = VentoyConfig(drive_root)
    cfg.sync_aliases([
        {"filename": "tracked.iso", "display_name": "Arch Linux", "version": "2026.09.01"},
    ])

    entries = VentoyConfig(drive_root).data["menu_alias"]
    assert {"image": "/Managed_ISOs/tracked.iso", "alias": "Arch Linux 2026.09.01"} in entries
    assert {"image": "/Managed_ISOs/theirs.iso", "alias": "My own"} in entries
    assert {"image": "/Managed_ISOs/sub/deep.wim", "alias": "Deep"} in entries
    assert dir_entry in entries and elsewhere in entries
    images = [e.get("image") for e in entries]
    assert "/Managed_ISOs/deleted.iso" not in images
    assert images.count("/Managed_ISOs/tracked.iso") == 1

    # An update renames it.
    cfg.sync_aliases([
        {"filename": "tracked.iso", "display_name": "Arch Linux", "version": "2026.10.01"},
    ])
    assert VentoyConfig(drive_root).alias_for("/Managed_ISOs/tracked.iso") == "Arch Linux 2026.10.01"


def test_a_bom_is_read_and_the_file_kept(drive_root):
    path = os.path.join(drive_root, "ventoy", "ventoy.json")
    os.makedirs(os.path.dirname(path))
    with open(path, "w", encoding="utf-8-sig") as fh:
        json.dump({"password": {"bootpwd": "x"}, "menu_alias": []}, fh)

    cfg = VentoyConfig(drive_root)
    cfg.set_alias("/Managed_ISOs/a.iso", "A")

    data = json.load(open(path, encoding="utf-8"))
    assert data["password"] == {"bootpwd": "x"}
    assert data["menu_alias"] == [{"image": "/Managed_ISOs/a.iso", "alias": "A"}]


@pytest.mark.parametrize("content", ["{ not json", "[1, 2]"])
def test_an_unreadable_file_is_never_written_over(drive_root, content):
    path = os.path.join(drive_root, "ventoy", "ventoy.json")
    os.makedirs(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)

    cfg = VentoyConfig(drive_root)
    cfg.set_alias("/Managed_ISOs/a.iso", "A")
    cfg.sync_aliases([{"filename": "b.iso", "display_name": "B"}])

    assert cfg.unreadable and cfg.search_root() == ""
    assert open(path, encoding="utf-8").read() == content


def test_a_new_ventoy_json_holds_menu_names_and_nothing_else(drive_root):
    cfg = VentoyConfig(drive_root)
    cfg.set_alias("/Managed_ISOs/a.iso", "A")

    data = json.load(open(os.path.join(drive_root, "ventoy", "ventoy.json"), encoding="utf-8"))
    assert data == {"menu_alias": [{"image": "/Managed_ISOs/a.iso", "alias": "A"}]}
    assert VentoyConfig(drive_root).search_root() == ""


OLD_THEME = {"file": "/ventoy/theme/theme.txt", "gfxmode": "1920x1080",
             "display_mode": "GUI", "ventoy_color": "#1e1e2e"}


def test_the_theme_veim_used_to_write_goes_unless_its_file_is_there(drive_root):
    _write(drive_root, {"theme": OLD_THEME, "menu_alias": []})
    assert VentoyConfig(drive_root).dropped_old_defaults
    assert "theme" not in VentoyConfig(drive_root).data

    os.makedirs(os.path.join(drive_root, "ventoy", "theme"))
    open(os.path.join(drive_root, "ventoy", "theme", "theme.txt"), "w").close()
    assert VentoyConfig(drive_root).data["theme"] == OLD_THEME


def test_a_theme_of_the_users_own_stays(drive_root):
    theme = dict(OLD_THEME, gfxmode="1024x768")
    _write(drive_root, {"theme": theme})
    cfg = VentoyConfig(drive_root)
    assert not cfg.dropped_old_defaults and cfg.data["theme"] == theme


def test_sync_keeps_fuzzy_entries(drive_root):
    fuzzy = {"image": "/Managed_ISOs/ubuntu-*.iso", "alias": "Some Ubuntu"}
    _write(drive_root, {"menu_alias": [fuzzy]})

    cfg = VentoyConfig(drive_root)
    cfg.sync_aliases([])

    assert fuzzy in cfg.data["menu_alias"]


def test_a_deleted_ventoy_json_is_not_written_back_from_memory(drive_root):
    _write(drive_root, {"password": {"bootpwd": "x"}})
    cfg = VentoyConfig(drive_root)
    os.remove(os.path.join(drive_root, "ventoy", "ventoy.json"))

    cfg.set_alias("/a.iso", "A")

    with open(os.path.join(drive_root, "ventoy", "ventoy.json"), encoding="utf-8") as fh:
        assert json.load(fh) == {"menu_alias": [{"image": "/a.iso", "alias": "A"}]}


@pytest.mark.parametrize("control, root, level, trash", [
    ([{"VTOY_DEFAULT_SEARCH_ROOT": "ISO"}], "", None, True),           # no leading "/"
    ([{"VTOY_MAX_SEARCH_LEVEL": 2}], "", None, True),                  # not a string
    ([{"VTOY_MAX_SEARCH_LEVEL": "1"}, {"VTOY_MAX_SEARCH_LEVEL": "3"}], "", 3, True),  # last wins
    ([{"VTOY_FILT_TRASH_DIR": "0"}], "", None, False),
    ([{"VTOY_FILT_TRASH_DIR": " 0"}], "", None, True),                 # exactly "0" only
    ([{"VTOY_MENU_TIMEOUT": "5", "VTOY_DEFAULT_SEARCH_ROOT": "/ISO"}], "", None, True),  # first key
])
def test_control_options_are_read_the_way_ventoy_reads_them(drive_root, control, root, level, trash):
    _write(drive_root, {"control": control})
    cfg = VentoyConfig(drive_root)
    assert (cfg.search_root(), cfg.max_search_level(), cfg.filters_trash()) == (root, level, trash)
