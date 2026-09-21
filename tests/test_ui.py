"""UI behaviour tests.

These construct real widgets on an offscreen Qt platform. They cover the
presentation bugs that were visible in the old build - a clipped drive path, a
doubled download percentage, catalog filtering - so they cannot come back
unnoticed.
"""
import os

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QLabel

from src.core.downloader import DownloadTask
from src.core.inventory import InventoryItem
from src.recipes.registry import registry


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def themed(qapp):
    from src.ui.theme import theme_manager
    theme_manager.set_theme("Dark Modern")
    return theme_manager


# --------------------------------------------------------------- components

def test_elide_shortens_long_text(themed):
    from src.ui.components import elide
    label = QLabel()
    long_path = r"C:\Users\somebody\AppData\Local\Temp\a\very\deep\ventoy\mount\point"
    elide(label, long_path, 180)

    assert label.text() != long_path, "long path was not shortened"
    assert "…" in label.text() or "..." in label.text()
    assert label.toolTip() == long_path, "full path should stay available on hover"


def test_capacity_bar_clamps_out_of_range(themed):
    from src.ui.components import CapacityBar
    bar = CapacityBar()
    bar.resize(100, 6)

    bar.set_used_fraction(1.8)
    assert bar._ratio == 1.0
    bar.set_used_fraction(-3)
    assert bar._ratio == 0.0


def test_capacity_bar_warns_when_nearly_full(themed):
    from src.ui.components import CapacityBar
    bar = CapacityBar()
    bar.set_used_fraction(0.5)
    assert bar._fill.objectName() == "capacityFill"
    bar.set_used_fraction(0.97)
    assert bar._fill.objectName() == "capacityFillWarn"


# ------------------------------------------------------------ download rows

def _task(done_mb, total_mb, speed=10.0, eta=30):
    t = DownloadTask("https://example.invalid/x.iso", "x.iso")
    t.downloaded_bytes = int(done_mb * 1024 ** 2)
    t.total_bytes = int(total_mb * 1024 ** 2)
    t.speed_mbps = speed
    t.eta_seconds = eta
    return t


def test_download_row_states_percent_once(themed):
    """Regression: the percentage used to appear twice, once detached.

    The bar itself must carry no text; the numbers belong in the meta line.
    """
    from src.ui.downloading_card import DownloadingCard
    card = DownloadingCard("ubuntu", "Ubuntu", "Desktop")
    card.update_progress(_task(1056, 4800))

    assert card.progress.isTextVisible() is False
    assert card.progress.value() == 22
    assert card.meta.text().count("22%") == 1


def test_download_row_handles_unknown_total(themed):
    from src.ui.downloading_card import DownloadingCard
    card = DownloadingCard("debian", "Debian", "Netinst")
    card.update_progress(_task(50, 0))
    # Indeterminate rather than a misleading 0%.
    assert card.progress.minimum() == 0 and card.progress.maximum() == 0


def test_download_row_error_offers_dismiss(themed):
    from src.ui.downloading_card import DownloadingCard
    card = DownloadingCard("kali", "Kali Linux", "Live")
    card.show_error("Couldn't find a current release - mirror timed out")

    assert card.btn_action.text() == "Dismiss"
    assert "mirror timed out" in card.meta.text()


# ------------------------------------------------------------ installed row

def _item(**kw):
    base = dict(key="arch", flavor_id="standard", display_name="Arch Linux",
                version="2026.09.01", filename="a.iso", size_bytes=900 * 1024 ** 2)
    base.update(kw)
    return InventoryItem(**base)


def test_installed_row_reports_up_to_date(themed):
    from src.ui.distro_card import DistroCard
    card = DistroCard(_item(), lambda *a: None, lambda *a: None, lambda *a: None)
    card.set_status_result("2026.09.01", "https://example.invalid/a.iso")

    assert card.status.text() == "Up to date"
    assert card.btn_update.isHidden()


def test_installed_row_offers_update(themed):
    from src.ui.distro_card import DistroCard
    card = DistroCard(_item(), lambda *a: None, lambda *a: None, lambda *a: None)
    card.show()
    card.set_status_result("2026.10.01", "https://example.invalid/a.iso")

    assert "2026.10.01" in card.status.text()
    assert not card.btn_update.isHidden()


def test_installed_row_surfaces_unavailable_distinctly(themed):
    """A recipe that refused to serve a stale build must not read 'up to date'."""
    from src.ui.distro_card import DistroCard
    card = DistroCard(_item(), lambda *a: None, lambda *a: None, lambda *a: None)
    card.set_status_result("Unavailable", "")

    assert card.status.text() == "No current release"
    assert card.btn_update.isHidden()


def test_installed_row_never_offers_a_downgrade(themed):
    """Regression: any different version counted as an update. The Tiny Core
    recipe was stuck on 15.0, so a drive holding 16.2 was offered "Update to
    15.0" - and the button would have replaced the newer ISO with the older."""
    from src.ui.distro_card import DistroCard
    card = DistroCard(_item(key="tinycore", flavor_id="corepure64", version="16.2"),
                      lambda *a: None, lambda *a: None, lambda *a: None)
    card.show()
    card.set_status_result("15.0", "https://example.invalid/CorePure64-15.0.iso")

    assert card.btn_update.isHidden(), "a downgrade was offered as an update"
    assert not card.update_available
    assert card.status.text() == "Newer than 15.0"

    # And the real thing is still an update.
    card.set_status_result("17.1", "https://example.invalid/CorePure64-17.1.iso")
    assert not card.btn_update.isHidden()
    assert card.status.text() == "Update to 17.1"


@pytest.mark.parametrize("latest,installed,older", [
    ("15.0", "16.2", True),
    ("10.0.9", "10.0.12", True),                 # not by text, where "9" > "1"
    ("20260705-resolute", "20260913-resolute", True),
    ("44 (2026-08-01)", "44 (2026-09-02)", True),
    ("18", "18.1", True),
    ("17.1", "16.2", False),
    ("16.2", "16.2", False),
    ("2026.2a", "2026.2", False),                # same numbers: left to inequality
    ("Tumbleweed", "Tumbleweed", False),         # nothing to compare
    ("Stable", "44", False),
])
def test_is_older(latest, installed, older):
    from src.core.recipe_base import is_older
    assert is_older(latest, installed) is older


# ----------------------------------------------------------------- catalog

def test_catalog_lists_every_recipe(themed):
    from src.ui.catalog_view import CatalogView
    view = CatalogView(on_install=lambda r, f: None)
    assert len(view.rows) == len(registry.get_all_recipes())


def test_catalog_search_filters(themed):
    from src.ui.catalog_view import CatalogView
    view = CatalogView(on_install=lambda r, f: None)
    view.show()

    # Search spans descriptions too, so "fedora" legitimately also matches
    # Bazzite ("built on Fedora Atomic") - that is useful, not a false positive.
    view.search.setText("fedora")
    visible = [k for k, r in view.rows.items() if not r.isHidden()]
    assert "fedora" in visible
    assert len(visible) < len(view.rows)

    view.search.setText("zzzz-no-such-distro")
    assert all(r.isHidden() for r in view.rows.values())

    view.search.setText("")
    visible = [k for k, r in view.rows.items() if not r.isHidden()]
    assert len(visible) == len(view.rows)


def test_catalog_category_filter(themed):
    from src.ui.catalog_view import CatalogView
    view = CatalogView(on_install=lambda r, f: None)
    view.show()

    view._set_category("Rescue & Diagnostics")
    visible = {k for k, r in view.rows.items() if not r.isHidden()}
    expected = {r.key for r in registry.get_by_category("Rescue & Diagnostics")}
    assert visible == expected


def test_catalog_marks_installed_flavor(themed):
    from src.ui.catalog_view import CatalogView
    view = CatalogView(on_install=lambda r, f: None,
                       installed_lookup=lambda k: {"standard"} if k == "arch" else set())
    row = view.rows["arch"]
    assert row.btn.text() == "Reinstall"
    assert view.rows["debian"].btn.text() == "Download"


def test_catalog_install_passes_selected_flavor(themed):
    from src.ui.catalog_view import CatalogView
    captured = []
    view = CatalogView(on_install=lambda r, f: captured.append((r.key, f)))

    row = view.rows["fedora"]
    assert row.combo is not None, "Fedora has multiple flavors and needs a selector"
    row.combo.setCurrentIndex(1)
    row._install()

    assert captured == [("fedora", row.combo.currentData())]


# ------------------------------------------------------------- icon chips

def test_icon_chip_fills_its_box(themed, qapp):
    """Regression: logos rendered at half size inside a large chip.

    QPixmap.scaled() works in device pixels and carries the source pixmap's
    devicePixelRatio onto the result, so passing a logical size to a 2x pixmap
    produced an icon half the intended size.
    """
    from PySide6.QtGui import QPixmap
    from src.ui.components import IconChip

    expected = 44 * IconChip.FILL

    # The drawn size must be the same whatever resolution the source was
    # cached at - that is exactly what the old code got wrong, rendering the
    # 2x pixmap at half the size of the 1x one.
    sizes = {}
    for dpr in (1.0, 2.0, 3.0):
        source = QPixmap(int(44 * dpr * 2), int(44 * dpr * 2))
        source.fill()
        source.setDevicePixelRatio(dpr)

        chip = IconChip(44)
        chip.set_icon(source)
        # Read the logical size: QLabel.pixmap() hands back a 1x copy only when
        # the screen itself is 1x, so size() alone is display-dependent.
        sizes[dpr] = chip.pixmap().deviceIndependentSize().width()

    for dpr, width in sizes.items():
        assert width == pytest.approx(expected, abs=1), (
            f"a {dpr}x source drew {width}px inside a 44px chip, expected ~{expected:.0f}px"
        )


def test_icon_chip_plates_only_dark_logos(themed, qapp):
    """The chip follows the theme; a light plate is for logos that need one."""
    from src.core.icons import icon_manager
    from src.ui.components import IconChip

    chip = IconChip(44)

    chip.set_backdrop(False)
    assert chip.objectName() == "iconChip"
    chip.set_backdrop(True)
    assert chip.objectName() == "iconChipPlate"

    # TUXEDO is solid black on transparency; Fedora is a coloured mark.
    if os.path.exists(os.path.join(icon_manager.cache_dir, "tuxedo.png")):
        assert icon_manager.needs_light_backdrop("tuxedo")
    if os.path.exists(os.path.join(icon_manager.cache_dir, "fedora.png")):
        assert not icon_manager.needs_light_backdrop("fedora")


# ----------------------------------------------------------------- layout

def test_header_buttons_are_not_flush_against_each_other(themed, qapp, tmp_path):
    """Regression: a nested layout inherits its parent's spacing.

    The page root sets spacing(0), so the header row silently came out with a
    0px gap and 'Check All Updates' sat flush against 'Add Distribution'.
    """
    from src.ui.dashboard import DashboardView

    view = DashboardView(drive_path=str(tmp_path), on_change_drive=lambda: None)
    view.resize(1000, 700)
    view.show()
    qapp.processEvents()

    left = view.btn_check_all.geometry()
    right = view.btn_add.geometry()
    gap = right.x() - (left.x() + left.width())
    assert gap >= 6, f"only {gap}px between the header buttons"


def test_eliding_label_fits_the_width_it_is_given(themed, qapp):
    """The drive path used to be measured against a guessed width and overflow."""
    from src.ui.components import ElidingLabel

    label = ElidingLabel()
    label.setObjectName("rowTitle")
    label.resize(160, 20)
    long_path = r"C:\Users\somebody\AppData\Local\Temp\veim\mounted\ventoy\drive"
    label.setFullText(long_path)

    assert label.fullText() == long_path
    assert label.toolTip() == long_path
    width = label.fontMetrics().horizontalAdvance(label.text())
    assert width <= label.width(), f"text is {width}px wide in a {label.width()}px label"


def test_category_chips_wrap_instead_of_running_off_the_edge(themed, qapp):
    """Regression: seven chips need ~866px and the page has 632px at the app's
    minimum window width, so the last two were cut off at the viewport edge."""
    from src.ui.catalog_view import CatalogView

    view = CatalogView(on_install=lambda r, f: None)
    chips = view._chip_group.buttons()

    seen_rows = set()
    for width in (1180, 900, 700, 560):
        view.resize(width, 700)
        view.show()
        for _ in range(3):
            qapp.processEvents()

        limit = view.width() - 28          # page's right margin
        rows = {c.geometry().y() for c in chips}
        seen_rows.add(len(rows))

        for chip in chips:
            assert chip.width() >= chip.sizeHint().width(), (
                f"{chip.text()!r} squeezed below its label at {width}px"
            )
            assert chip.geometry().right() <= limit, (
                f"{chip.text()!r} overflows the page at {width}px"
            )

    assert max(seen_rows) > 1, "chips never wrapped at any width"


def test_flow_layout_reports_a_taller_height_when_narrower(themed, qapp):
    """heightForWidth is what lets the surrounding layout reserve the extra row."""
    from PySide6.QtWidgets import QWidget, QPushButton
    from src.ui.components import FlowLayout

    host = QWidget()
    layout = FlowLayout(host, h_spacing=8, v_spacing=8)
    for i in range(6):
        btn = QPushButton(f"Category {i}")
        btn.setMinimumWidth(120)
        layout.addWidget(btn)

    assert layout.hasHeightForWidth()
    wide = layout.heightForWidth(1200)
    narrow = layout.heightForWidth(300)
    assert narrow > wide, f"narrow ({narrow}px) should need more rows than wide ({wide}px)"


# ------------------------------------------------- downloading from catalog

@pytest.fixture
def workspace(themed, qapp, tmp_path, monkeypatch):
    """A real Workspace whose downloads never leave the machine.

    _on_catalog_install_request spawns a worker that resolves the recipe and
    starts a genuine transfer; without this stub these tests would hit live
    mirrors and pull down multi-gigabyte ISOs.
    """
    from src.ui.dashboard import DashboardView
    from src.ui.workspace import Workspace

    monkeypatch.setattr(DashboardView, "_worker_fetch_and_start_download",
                        lambda *a, **kw: None)

    ws = Workspace(drive_path=str(tmp_path), on_change_drive=lambda: None)
    ws.resize(1180, 760)
    ws.show()
    qapp.processEvents()
    return ws


def _progress(done_mb, total_mb, speed=12.4, eta=38):
    t = DownloadTask("https://example.invalid/x.iso", "x.iso")
    t.downloaded_bytes = int(done_mb * 1024 ** 2)
    t.total_bytes = int(total_mb * 1024 ** 2)
    t.speed_mbps, t.eta_seconds = speed, eta
    return t


def test_downloading_keeps_you_in_the_catalog(workspace, qapp):
    """Regression: starting a download used to switch to the Installed page.

    That threw you out of the catalog every time, so queueing three
    distributions meant navigating back twice.
    """
    ws = workspace
    ws.go_to("catalog")
    qapp.processEvents()

    ws.catalog.rows["debian"]._on_button()
    qapp.processEvents()

    assert ws.stack.currentWidget() is ws.catalog, "download navigated away from the catalog"


def test_catalog_row_shows_progress_for_its_own_download(workspace, qapp):
    ws = workspace
    row = ws.catalog.rows["debian"]
    flavor = row.current_flavor()

    assert row.btn.text() == "Download"
    assert row.progress.isHidden()

    row._on_button()
    qapp.processEvents()

    assert row.is_downloading(flavor)
    assert not row.progress.isHidden(), "no progress indicator appeared"
    assert row.btn.text() == "Cancel", "the row offers no way to stop the transfer"
    # Size is not known until the response headers arrive.
    assert row.progress.maximum() == 0

    ck = ws.library.inventory_mgr._composite_key("debian", flavor)
    ws.library._on_progress_slot(ck, _progress(231, 700))
    qapp.processEvents()

    assert row.progress.value() == 33
    assert "33%" in row.note.text()
    assert "12.4 MB/s" in row.note.text()


def test_cancel_from_the_catalog_stops_the_transfer(workspace, qapp):
    ws = workspace
    ws.go_to("catalog")
    qapp.processEvents()

    row = ws.catalog.rows["debian"]
    flavor = row.current_flavor()

    row._on_button()
    qapp.processEvents()
    assert len(ws.library.download_cards) == 1

    row._on_button()          # now reads "Cancel"
    qapp.processEvents()

    assert not row.is_downloading(flavor)
    assert row.btn.text() == "Download"
    assert row.progress.isHidden()
    assert ws.library.download_cards == {}, "the transfer was left running"
    assert ws.stack.currentWidget() is ws.catalog


def test_progress_belongs_to_the_selected_flavor_only(workspace, qapp):
    """Switching editions must not show another edition's progress bar."""
    ws = workspace
    row = ws.catalog.rows["debian"]
    assert row.combo is not None
    downloading = row.current_flavor()

    row._on_button()
    qapp.processEvents()
    assert row.btn.text() == "Cancel"

    row.combo.setCurrentIndex(1)
    qapp.processEvents()
    assert row.current_flavor() != downloading
    assert row.btn.text() == "Download", "a different edition looked like it was downloading"
    assert row.progress.isHidden()

    row.combo.setCurrentIndex(0)
    qapp.processEvents()
    assert row.btn.text() == "Cancel", "the downloading edition lost its state"
    assert not row.progress.isHidden()


def test_failed_download_leaves_its_reason_on_the_row(workspace, qapp):
    """A failure must not vanish the instant the progress bar disappears."""
    ws = workspace
    row = ws.catalog.rows["debian"]
    flavor = row.current_flavor()

    row._on_button()
    qapp.processEvents()

    ck = ws.library.inventory_mgr._composite_key("debian", flavor)
    ws.library._on_error_slot(ck, "Couldn't find a current release - mirror timed out")
    qapp.processEvents()

    assert not row.is_downloading(flavor)
    assert row.btn.text() == "Download"
    assert "mirror timed out" in row.note.text()
    assert not row.note.isHidden()

    # Starting again clears the stale message.
    row._on_button()
    qapp.processEvents()
    assert "mirror timed out" not in row.note.text()


def test_completed_download_marks_the_row_installed(workspace, qapp, tmp_path):
    ws = workspace
    row = ws.catalog.rows["debian"]
    flavor = row.current_flavor()

    row._on_button()
    qapp.processEvents()

    # Stand in for the worker finishing: the inventory is written by the slot.
    ck = ws.library.inventory_mgr._composite_key("debian", flavor)
    managed = tmp_path / "Managed_ISOs"
    managed.mkdir(exist_ok=True)
    iso = managed / "debian-13.2.0-amd64-netinst.iso"
    iso.write_bytes(b"iso")

    task = DownloadTask("https://example.invalid/d.iso", str(iso))
    task._distro_meta = dict(key="debian", flavor_id=flavor, display_name="Debian Netinst",
                             version="13.2.0", filename=iso.name, sha256="",
                             url="https://example.invalid/d.iso")
    ws.library.active_tasks[ck] = task
    ws.library._on_complete_slot(ck, True, "Success")
    qapp.processEvents()

    assert not row.is_downloading(flavor)
    assert row.progress.isHidden()
    assert row.btn.text() == "Reinstall"
    assert not row.badge.isHidden(), "the Installed badge did not appear"


# ------------------------------------------- updating an installed ISO

@pytest.fixture
def installed(workspace, qapp, tmp_path):
    """The workspace with Arch and Debian already on the drive."""
    ws = workspace
    managed = tmp_path / "Managed_ISOs"
    managed.mkdir(exist_ok=True)
    for key, flavor, name, version, fname in (
        ("arch", "standard", "Arch Linux", "2026.09.01", "archlinux-2026.09.01-x86_64.iso"),
        ("debian", "netinst", "Debian Netinst", "13.1.0", "debian-13.1.0-amd64-netinst.iso"),
    ):
        (managed / fname).write_bytes(b"iso")
        ws.library.inventory_mgr.add_or_update(
            key=key, flavor_id=flavor, display_name=name, version=version,
            filename=fname, size_bytes=3)
    ws.library.refresh_installed_list()
    qapp.processEvents()
    return ws


def _update(ws, qapp, ck="arch::standard", latest="2026.10.01"):
    """Find an update for a row and press its Update button."""
    card = ws.library.cards[ck]
    card.set_status_result(latest, "https://example.invalid/new.iso")
    card.btn_update.click()
    qapp.processEvents()
    return card


def test_update_progress_stays_on_the_row_being_updated(installed, qapp):
    """Regression: an update ran in a new row pinned to the top of the page,
    while the row it belonged to sat unchanged, still offering "Update"."""
    ws = installed
    card = _update(ws, qapp)

    assert ws.library.download_cards == {}, "the update got a separate row"
    assert ws.library.lbl_downloads.isHidden()
    assert card.is_downloading
    assert not card.progress.isHidden()
    assert card.btn_update.isHidden(), "still offering the update that is running"
    assert card.btn_remove.isHidden()
    assert not card.btn_cancel.isHidden(), "no way to stop the update"

    ws.library._on_progress_slot("arch::standard", _progress(231, 700))
    assert card.progress.value() == 33
    assert "33%" in card.meta.text()

    # The other row is not involved.
    assert not ws.library.cards["debian::netinst"].is_downloading


def test_finished_update_returns_the_row_to_normal(installed, qapp, tmp_path):
    ws = installed
    card = _update(ws, qapp)

    iso = tmp_path / "Managed_ISOs" / "archlinux-2026.10.01-x86_64.iso"
    iso.write_bytes(b"newer iso")
    task = DownloadTask("https://example.invalid/new.iso", str(iso))
    task._distro_meta = dict(key="arch", flavor_id="standard", display_name="Arch Linux",
                             version="2026.10.01", filename=iso.name, sha256="",
                             url="https://example.invalid/new.iso")
    ws.library.active_tasks["arch::standard"] = task
    ws.library._on_complete_slot("arch::standard", True, "Success")
    qapp.processEvents()

    assert ws.library.cards["arch::standard"] is card, "the row was rebuilt"
    assert not card.is_downloading
    assert card.progress.isHidden()
    assert card.status.text() == "Updated"
    assert "2026.10.01" in card.meta.text()
    assert card.btn_update.isHidden()
    assert not card.btn_remove.isHidden()


def test_cancelled_update_offers_the_update_again(installed, qapp):
    ws = installed
    card = _update(ws, qapp)

    card.btn_cancel.click()
    qapp.processEvents()

    assert "arch::standard" not in ws.library.active_tasks
    assert not card.is_downloading
    assert card.progress.isHidden()
    assert "2026.10.01" in card.status.text()
    assert not card.btn_update.isHidden()
    assert "2026.09.01" in card.meta.text()


def test_failed_update_says_why_on_its_row(installed, qapp):
    ws = installed
    card = _update(ws, qapp)

    ws.library._on_complete_slot("arch::standard", False, "Mirror timed out")
    qapp.processEvents()

    assert not card.is_downloading
    assert card.status.text() == "Download failed"
    assert "Mirror timed out" in card.meta.text()
    assert not card.btn_update.isHidden(), "a failed update cannot be retried"

    # Using the row again clears the message.
    card.btn_update.click()
    qapp.processEvents()
    assert card.is_downloading
    assert "Mirror timed out" not in card.meta.text()


def test_one_finished_download_keeps_other_rows_check_results(installed, qapp, tmp_path):
    """Regression: every completion rebuilt the whole list, which wiped the
    "Update to ..." pill and the Update button from every other row."""
    ws = installed
    arch = ws.library.cards["arch::standard"]
    arch.set_status_result("2026.10.01", "https://example.invalid/new.iso")

    ws.catalog.rows["fedora"]._on_button()
    qapp.processEvents()
    assert ws.library.cards["arch::standard"] is arch
    ck = next(iter(ws.library.download_cards))
    ws.library._cancel_download(ck)
    qapp.processEvents()

    assert ws.library.cards["arch::standard"] is arch
    assert "2026.10.01" in arch.status.text()
    assert not arch.btn_update.isHidden()


def test_failed_download_can_be_retried_from_the_catalog(workspace, qapp):
    """Regression: the failed row kept hold of the key until it was dismissed,
    so pressing Download again did nothing at all."""
    ws = workspace
    row = ws.catalog.rows["debian"]
    ck = ws.library.inventory_mgr._composite_key("debian", row.current_flavor())

    row._on_button()
    qapp.processEvents()
    ws.library._on_error_slot(ck, "mirror timed out")
    qapp.processEvents()
    failed = ws.library.download_cards[ck]

    row._on_button()
    qapp.processEvents()

    assert row.is_downloading(row.current_flavor()), "the retry was ignored"
    assert ws.library.download_cards[ck] is not failed
    assert ws.library.download_layout.count() == 1


def test_cancel_while_starting_does_not_start_the_download(workspace, qapp, tmp_path):
    """Regression: cancelling during "Starting…" removed the row, and the
    worker then started the transfer anyway, with nothing left to stop it."""
    ws = workspace
    row = ws.catalog.rows["debian"]
    ck = ws.library.inventory_mgr._composite_key("debian", row.current_flavor())

    row._on_button()
    qapp.processEvents()
    token = ws.library._download_tokens[ck]
    row._on_button()          # Cancel
    qapp.processEvents()

    started = []
    task = DownloadTask("https://example.invalid/d.iso", str(tmp_path / "d.iso"))
    task.start_async = lambda **kw: started.append(kw)
    ws.library._on_ready_slot(ck, token, task)

    assert started == []
    assert ck not in ws.library.active_tasks


def _adopt_everything(ws):
    """Say yes to every candidate, the way the adoption dialog would."""
    from src.ui.adopt_dialog import ADOPT
    candidates = ws.library._adoptable()
    ws.library._apply_adoption(candidates, {c.filename: ADOPT for c in candidates})


def test_remove_deletes_the_iso_of_the_row_that_was_clicked(workspace, qapp, tmp_path, monkeypatch):
    """Regression: with two ISOs of one distro on the drive, Remove on the
    second row asked about the second and then deleted the first."""
    from PySide6.QtWidgets import QMessageBox

    ws = workspace
    managed = tmp_path / "Managed_ISOs"
    managed.mkdir(exist_ok=True)
    first = managed / "archlinux-2026.03.01-x86_64.iso"
    second = managed / "archlinux-2026.09.01-x86_64.iso"
    first.write_bytes(b"iso")
    second.write_bytes(b"iso")
    _adopt_everything(ws)
    assert len(ws.library.cards) == 2

    from src.ui.dashboard import DashboardView
    monkeypatch.setattr(DashboardView, "_ask_removal", lambda self, item: "delete")
    card = next(c for c in ws.library.cards.values() if c.item.filename == second.name)
    card.btn_remove.click()
    qapp.processEvents()

    assert not second.exists()
    assert first.exists(), "Remove deleted a different ISO than the one clicked"
    assert [c.item.filename for c in ws.library.cards.values()] == [first.name]


@pytest.fixture
def two_arch_isos(workspace, qapp, tmp_path):
    """Two ISOs that are both arch::standard; the second gets a longer key."""
    ws = workspace
    managed = tmp_path / "Managed_ISOs"
    managed.mkdir(exist_ok=True)
    first = managed / "archlinux-2026.03.01-x86_64.iso"
    second = managed / "archlinux-2026.09.01-x86_64.iso"
    first.write_bytes(b"iso")
    second.write_bytes(b"iso")
    _adopt_everything(ws)
    qapp.processEvents()
    keys = {c.item.filename: ck for ck, c in ws.library.cards.items()}
    return ws, first, second, keys[first.name], keys[second.name]


def test_update_runs_on_and_replaces_the_row_that_was_clicked(two_arch_isos, qapp, tmp_path):
    """Regression: Update on the second of two ISOs of one distro showed its
    progress on the first row, then deleted the first row's file."""
    ws, first, second, first_ck, second_ck = two_arch_isos
    lib = ws.library

    card = _update(ws, qapp, ck=second_ck)
    assert card.is_downloading
    assert not lib.cards[first_ck].is_downloading, "the update ran on the other row"

    iso = tmp_path / "Managed_ISOs" / "archlinux-2026.10.01-x86_64.iso"
    iso.write_bytes(b"newer iso")
    task = DownloadTask("https://example.invalid/new.iso", str(iso))
    task._distro_meta = dict(key="arch", flavor_id="standard", display_name="Arch Linux",
                             version="2026.10.01", filename=iso.name, sha256="",
                             url="https://example.invalid/new.iso")
    lib.active_tasks[second_ck] = task
    lib._on_complete_slot(second_ck, True, "Success")
    qapp.processEvents()

    assert first.exists(), "the update deleted a different ISO"
    assert not second.exists(), "the replaced ISO was left on the drive"
    assert lib.cards[first_ck].item.filename == first.name
    assert lib.cards[second_ck] is card
    assert card.item.filename == iso.name
    assert card.status.text() == "Updated"


def test_cancel_stops_the_update_of_the_row_that_was_clicked(two_arch_isos, qapp):
    ws, _, _, first_ck, second_ck = two_arch_isos
    card = _update(ws, qapp, ck=second_ck)
    assert second_ck in ws.library.active_tasks

    card.btn_cancel.click()
    qapp.processEvents()

    assert second_ck not in ws.library.active_tasks
    assert not card.is_downloading


def test_catalog_cancel_stops_a_download_started_from_any_row(two_arch_isos, qapp):
    """The catalog shows one bar per flavor, whichever row is fetching it."""
    ws, _, _, first_ck, second_ck = two_arch_isos
    card = _update(ws, qapp, ck=second_ck)
    assert ws.catalog.rows["arch"].is_downloading("standard")

    ws.catalog.rows["arch"]._on_button()      # now reads "Cancel"
    qapp.processEvents()

    assert not card.is_downloading, "Cancel in the catalog left the transfer running"
    assert ws.library.active_tasks == {}


def test_two_rows_cannot_download_the_same_file_at_once(two_arch_isos, qapp, tmp_path):
    ws, _, _, first_ck, second_ck = two_arch_isos
    lib = ws.library
    dest = str(tmp_path / "Managed_ISOs" / "archlinux-2026.10.01-x86_64.iso")

    _update(ws, qapp, ck=first_ck)
    running = DownloadTask("https://example.invalid/new.iso", dest)
    lib.active_tasks[first_ck] = running

    second = _update(ws, qapp, ck=second_ck)
    started = []
    task = DownloadTask("https://example.invalid/new.iso", dest)
    task.start_async = lambda **kw: started.append(kw)
    lib._on_ready_slot(second_ck, lib._download_tokens[second_ck], task)

    assert started == []
    assert not second.is_downloading
    assert "already being downloaded" in second.meta.text()
    assert lib.cards[first_ck].is_downloading


# ------------------------------------------------------------- adoption

@pytest.fixture
def drive_with_loose_isos(workspace, qapp, tmp_path):
    """The kind of drive that prompted this: official ISOs next to a customised
    Clonezilla and images the catalog knows nothing about."""
    ws = workspace
    managed = tmp_path / "Managed_ISOs"
    managed.mkdir(exist_ok=True)
    for name in ("archlinux-2026.05.01-x86_64.iso",
                 "clonezilla-live-20260705-resolute-amd64.iso",
                 "clonezilla-live-galaxybook-20260808.iso",
                 "Win11_25H2_English_x64.iso"):
        (managed / name).write_bytes(b"iso")
    (tmp_path / "debian-13.4.0-amd64-netinst.iso").write_bytes(b"iso")
    ws.library.refresh_installed_list()
    qapp.processEvents()
    return ws


def test_nothing_is_adopted_without_being_asked(drive_with_loose_isos):
    """Regression: every ISO found became a row - rows nothing could update,
    and a customised Clonezilla offered an update that would overwrite it."""
    lib = drive_with_loose_isos.library

    assert lib.cards == {}
    assert not lib.btn_adopt.isHidden()
    assert lib.btn_adopt.text() == "Adopt ISOs (3)"


def test_adoption_dialog_offers_only_what_the_catalog_can_update(drive_with_loose_isos):
    from src.ui.adopt_dialog import AdoptDialog

    lib = drive_with_loose_isos.library
    candidates = lib._adoptable(include_excluded=True)
    dialog = AdoptDialog(candidates, {c.filename: lib._display_name(c) for c in candidates})

    offered = sorted(row.candidate.filename for row in dialog.rows)
    assert offered == ["archlinux-2026.05.01-x86_64.iso",
                       "clonezilla-live-20260705-resolute-amd64.iso",
                       "debian-13.4.0-amd64-netinst.iso"]
    assert all(choice == "" for choice in dialog.choices().values()), "an answer was pre-selected"

    row = dialog.rows[0]
    row.btn_adopt.click()
    assert row.choice() == "adopt"
    row.btn_exclude.click()
    assert row.choice() == "exclude", "both answers were left pressed"
    row.btn_exclude.click()
    assert row.choice() == ""


def test_adopting_and_excluding_from_the_dialog(drive_with_loose_isos, qapp, tmp_path):
    from src.ui.adopt_dialog import ADOPT, EXCLUDE

    lib = drive_with_loose_isos.library
    clonezilla = "clonezilla-live-20260705-resolute-amd64.iso"
    lib._apply_adoption(lib._adoptable(), {
        "archlinux-2026.05.01-x86_64.iso": ADOPT,
        "debian-13.4.0-amd64-netinst.iso": ADOPT,
        clonezilla: EXCLUDE,
    })
    qapp.processEvents()

    assert sorted(lib.cards) == ["arch::standard", "debian::netinst"]
    assert lib.cards["arch::standard"].item.version == "2026.05.01"
    assert (tmp_path / "Managed_ISOs" / "debian-13.4.0-amd64-netinst.iso").exists()
    assert (tmp_path / "Managed_ISOs" / clonezilla).exists(), "an excluded ISO was removed"

    # Nothing is waiting, but the dialog stays reachable to undo the exclusion.
    assert lib.btn_adopt.text() == "Excluded ISOs"
    assert not lib.btn_adopt.isHidden()
    assert [c.filename for c in lib._adoptable(include_excluded=True)] == [clonezilla]

    # The three that are left alone are mentioned once, not given rows.
    assert not lib.lbl_unmanaged.isHidden()
    assert lib.lbl_unmanaged.text().startswith("3 other ISOs")
    assert "galaxybook" in lib.lbl_unmanaged.toolTip()


def test_adopted_isos_are_not_offered_for_adoption_again(drive_with_loose_isos, qapp, monkeypatch):
    """Regression: the dialog also listed what had already been adopted, so
    opening it after adopting showed the same ISOs again, as if it had not taken."""
    from src.ui import dashboard

    lib = drive_with_loose_isos.library
    _adopt_everything(drive_with_loose_isos)
    assert len(lib.cards) == 3

    assert lib.btn_adopt.isHidden(), "nothing is waiting and nothing is excluded"
    opened = []
    monkeypatch.setattr(dashboard, "AdoptDialog", lambda *a, **kw: opened.append(a))
    lib._open_adopt_dialog()
    assert opened == []


def test_remove_can_keep_the_file_and_stop_managing_it(drive_with_loose_isos, qapp, tmp_path, monkeypatch):
    """Deleting was the only way off the list - no way out for a customised
    ISO under an official name, or one adopted by mistake."""
    from src.ui.dashboard import DashboardView

    lib = drive_with_loose_isos.library
    _adopt_everything(drive_with_loose_isos)
    monkeypatch.setattr(DashboardView, "_ask_removal", lambda self, item: "release")

    lib.cards["arch::standard"].btn_remove.click()
    qapp.processEvents()

    assert sorted(lib.cards) == ["clonezilla::alternative", "debian::netinst"]
    assert (tmp_path / "Managed_ISOs" / "archlinux-2026.05.01-x86_64.iso").exists()
    # Left alone for good, and the way back is labelled for what it holds.
    assert lib._adoptable() == []
    assert lib.btn_adopt.text() == "Excluded ISOs"
    assert not lib.btn_adopt.isHidden()


def test_adopt_all_respects_an_exclusion(drive_with_loose_isos):
    from src.ui.adopt_dialog import AdoptDialog

    lib = drive_with_loose_isos.library
    lib.inventory_mgr.set_excluded("clonezilla-live-20260705-resolute-amd64.iso", True)
    candidates = lib._adoptable(include_excluded=True)
    dialog = AdoptDialog(candidates, {})

    dialog.btn_all.click()

    choices = dialog.choices()
    assert choices["clonezilla-live-20260705-resolute-amd64.iso"] == "exclude"
    assert choices["archlinux-2026.05.01-x86_64.iso"] == "adopt"


def test_root_isos_the_boot_menu_cannot_see_can_be_moved_in(drive_with_loose_isos, qapp, tmp_path):
    """Regression: "Adopt Root ISOs" used to move every root ISO into
    Managed_ISOs, the one folder VEIM lets Ventoy search. Once only adopted
    ISOs moved, an ISO the catalog does not know stayed in the root, missing
    from the boot menu, with nothing in the app to say so or fix it."""
    lib = drive_with_loose_isos.library
    (tmp_path / "HBCD_PE_x64.iso").write_bytes(b"iso")
    _adopt_everything(drive_with_loose_isos)      # saves, which writes ventoy.json
    qapp.processEvents()

    assert not lib.hidden_notice.isHidden()
    assert lib.lbl_hidden.text().startswith("1 ISO in the drive root is missing")
    assert "HBCD_PE_x64.iso" in lib.hidden_notice.toolTip()

    lib.btn_move_in.click()
    qapp.processEvents()

    assert (tmp_path / "Managed_ISOs" / "HBCD_PE_x64.iso").exists()
    assert lib.hidden_notice.isHidden()
    assert len(lib.cards) == 3, "moving an ISO in made a row of it"
    assert "HBCD_PE_x64.iso" in lib.lbl_unmanaged.toolTip()


# ------------------------------------------------------ check all updates

@pytest.fixture
def held_checks(monkeypatch):
    """Update checks that wait to be answered by the test."""
    from src.ui.dashboard import DashboardView

    asked = []
    monkeypatch.setattr(
        DashboardView, "_handle_single_check",
        lambda self, item, card: asked.append(self._key_of(card)))
    return asked


def test_check_all_shows_that_it_is_checking(held_checks, installed, qapp):
    ws = installed
    lib = ws.library

    lib.btn_check_all.click()
    qapp.processEvents()

    assert sorted(held_checks) == ["arch::standard", "debian::netinst"]
    assert lib.btn_check_all.text() == "Checking…"
    assert not lib.btn_check_all.isEnabled()
    for card in lib.cards.values():
        assert card.status.text() == "Checking…"
        assert not card.btn_check.isEnabled()

    lib._on_check_slot("arch::standard", "2026.10.01", "https://example.invalid/a.iso")
    assert lib.btn_check_all.text() == "Checking…", "one row is still waiting"

    lib._on_check_slot("debian::netinst", "13.1.0", "https://example.invalid/d.iso")
    assert lib.btn_check_all.text() == "Check All Updates"
    assert lib.btn_check_all.isEnabled()
    assert "1 update available" in lib.subtitle.text()


def test_checking_all_again_visibly_checks_again(held_checks, installed, qapp):
    """Regression: a second press left every row reading "Up to date"
    throughout, so there was no sign that anything had been asked."""
    ws = installed
    lib = ws.library

    lib.btn_check_all.click()
    lib._on_check_slot("arch::standard", "2026.09.01", "")
    lib._on_check_slot("debian::netinst", "13.1.0", "")
    assert all(c.status.text() == "Up to date" for c in lib.cards.values())
    assert "all up to date" in lib.subtitle.text()

    del held_checks[:]
    lib.btn_check_all.click()
    qapp.processEvents()

    assert len(held_checks) == 2, "the second press did not check anything"
    assert all(c.status.text() == "Checking…" for c in lib.cards.values())
    assert lib.btn_check_all.text() == "Checking…"


def test_check_all_leaves_a_row_that_is_updating_alone(held_checks, installed, qapp):
    ws = installed
    card = _update(ws, qapp)

    ws.library.btn_check_all.click()
    qapp.processEvents()

    assert held_checks == ["debian::netinst"]
    assert card.is_downloading

    ws.library._on_check_slot("debian::netinst", "13.1.0", "")
    assert ws.library.btn_check_all.isEnabled(), "still waiting on a row it never asked"


def test_row_without_a_recipe_does_not_hang_check_all(installed, qapp, tmp_path):
    ws = installed
    # A record whose recipe has since left the catalog.
    (tmp_path / "Managed_ISOs" / "retired.iso").write_bytes(b"iso")
    ws.library.inventory_mgr.add_or_update(
        key="custom", flavor_id="default", display_name="Retired", version="1",
        filename="retired.iso", url="https://example.invalid/retired.iso")
    ws.library.refresh_installed_list()
    custom = ws.library.cards["custom::default"]

    # Only the row with no recipe: it answers on the spot, no thread involved.
    ws.library._pending_checks.add("custom::default")
    custom.start_check()

    assert custom.status.text() == "Check failed"
    assert ws.library.btn_check_all.text() == "Check All Updates"
    assert ws.library.btn_check_all.isEnabled()


# ------------------------------------------------------------- dropdowns

def _open(combo, qapp):
    combo.showPopup()
    for _ in range(6):
        qapp.processEvents()
    return combo.view(), combo.view().window()


def test_dropdown_shows_every_option_without_scrolling(themed, qapp):
    """Regression: Fusion's menu-style popup capped the height and added
    hover-scroll arrows. Seven Ubuntu flavors did not fit in the 171px it
    allowed, so options hid behind an interaction nothing here needs."""
    from src.ui.catalog_view import CatalogView

    view_page = CatalogView(on_install=lambda r, f: None)
    view_page.resize(1000, 700)
    view_page.show()
    qapp.processEvents()

    # Whichever entry has the longest list: the promise is about that one.
    combo = max((row.combo for row in view_page.rows.values() if row.combo is not None),
                key=lambda c: c.count())
    assert combo.count() >= 12
    listview, container = _open(combo, qapp)

    needed = combo.count() * listview.sizeHintForRow(0)
    assert listview.height() >= needed, (
        f"list is {listview.height()}px for {needed}px of rows - it scrolls"
    )

    scrollers = [c for c in container.children()
                 if c.isWidgetType() and c is not listview]
    assert not scrollers, f"popup still has scroller widgets: {scrollers}"
    assert not listview.verticalScrollBar().isVisible()
    combo.hidePopup()


def test_dropdown_draws_a_single_box(themed, qapp):
    """Regression: the container's stylesheet said `QFrame`, and QListView is a
    QFrame - so the list drew its own border inside the container's."""
    from src.ui.catalog_view import CatalogView

    page = CatalogView(on_install=lambda r, f: None)
    page.resize(1000, 700)
    page.show()
    qapp.processEvents()

    combo = page.rows["fedora"].combo
    listview, container = _open(combo, qapp)

    # frameWidth covers border plus padding; the list carries padding only.
    assert listview.frameWidth() <= 4, (
        f"list has a frame of {listview.frameWidth()}px - it is drawing a second border"
    )
    # The list fills the container apart from its border, so no halo shows
    # around it. The bug this guards against left a 6px band top and bottom;
    # a couple of pixels of border is both expected and invisible, because the
    # container and the list are painted the same colour.
    slack_h = container.height() - listview.height()
    slack_w = container.width() - listview.width()
    assert slack_h <= 4 and slack_w <= 4, (
        f"container {container.size().toTuple()} vs list {listview.size().toTuple()}: "
        f"{slack_w}x{slack_h}px of container is showing around the list"
    )
    combo.hidePopup()


def test_dropdown_survives_a_theme_change(themed, qapp):
    """The popup frame is restyled on open, so it must follow the palette."""
    from src.ui.theme import theme_manager
    from src.ui.catalog_view import CatalogView

    page = CatalogView(on_install=lambda r, f: None)
    page.show()
    qapp.processEvents()
    combo = page.rows["fedora"].combo

    _, container = _open(combo, qapp)
    assert theme_manager.current.bg_card in container.styleSheet()
    combo.hidePopup()

    theme_manager.set_theme("Solarized Light")
    try:
        _, container = _open(combo, qapp)
        assert theme_manager.current.bg_card in container.styleSheet()
        combo.hidePopup()
    finally:
        theme_manager.set_theme("Dark Modern")
