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

    # Ubuntu has the longest list in the catalog.
    combo = view_page.rows["ubuntu"].combo
    assert combo.count() == 7
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
