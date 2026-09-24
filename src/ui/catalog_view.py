"""Distribution catalog.

Previously a modal dialog of ~280px cards, which showed roughly four of the 34
distributions per screen and offered no way to narrow the list even though the
registry has always exposed categories. Now a first-class page: search,
category chips, and rows compact enough to scan.
"""
from typing import Callable, Dict, List, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QScrollArea,
    QFrame, QComboBox, QButtonGroup, QPushButton, QProgressBar
)
from PySide6.QtCore import Qt

from src.core.recipe_base import DistroRecipe, FlavorInfo
from src.recipes.registry import registry
from src.ui.components import (
    Row, Pill, FlowLayout, FlavorCombo, make_button, fmt_eta, EmptyState)


class CatalogRow(Row):
    """One distribution, with an optional flavor selector."""

    def __init__(self, recipe: DistroRecipe,
                 on_install: Callable[[DistroRecipe, str], None],
                 installed_flavors: Optional[set] = None,
                 on_cancel: Optional[Callable[[DistroRecipe, str], None]] = None,
                 parent=None):
        super().__init__(parent)
        self.recipe = recipe
        self.on_install = on_install
        self.on_cancel = on_cancel or (lambda r, f: None)
        self._installed = installed_flavors or set()

        self.icon.set_distro(recipe.key)
        self.title.setText(recipe.name)

        desc = QLabel(recipe.description)
        desc.setObjectName("rowDesc")
        desc.setWordWrap(True)
        self.text_col.addWidget(desc)
        self.meta.hide()

        self.flavors: List[FlavorInfo] = recipe.get_flavors() or []

        self.combo: Optional[QComboBox] = None
        if len(self.flavors) > 1:
            self.combo = FlavorCombo()
            self.combo.setMinimumWidth(210)
            for f in self.flavors:
                self.combo.addItem(f.name, f.id)
            self.combo.currentIndexChanged.connect(self._sync_state)
            self.add_action(self.combo)

        self.badge = Pill("Installed", "ok")
        self.badge.hide()
        self.add_action(self.badge)

        self.btn = make_button("Download", "primary", self._on_button)
        self.btn.setMinimumWidth(118)
        self.add_action(self.btn)

        # Progress for a transfer started from this row, so queueing one does
        # not mean leaving the catalog to watch it.
        self.progress = QProgressBar()
        self.progress.setObjectName("rowProgress")
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(5)
        self.progress.hide()
        self.text_col.addWidget(self.progress)

        self.note = QLabel()
        self.note.setObjectName("rowMeta")
        self.note.hide()
        self.text_col.addWidget(self.note)

        # flavor id -> (percent, MB/s, seconds remaining). Keyed per flavor so
        # the selector always shows the state of the edition on screen.
        self._downloading: Dict[str, tuple] = {}

        self._sync_state()

    # -- helpers ----------------------------------------------------------

    def current_flavor(self) -> str:
        if self.combo is not None:
            return self.combo.currentData()
        return self.flavors[0].id if self.flavors else ""

    def _sync_state(self):
        flavor = self.current_flavor()

        if flavor in self._downloading:
            pct, mbps, eta = self._downloading[flavor]
            self.badge.hide()
            self.progress.show()
            if pct < 0:
                # Size not known yet - indeterminate beats a misleading 0%.
                self.progress.setRange(0, 0)
                self.note.setText("Starting…")
            else:
                self.progress.setRange(0, 100)
                self.progress.setValue(pct)
                bits = [f"Downloading {pct}%"]
                if mbps > 0:
                    bits.append(f"{mbps:.1f} MB/s")
                if eta > 0:
                    bits.append(f"{fmt_eta(eta)} left")
                self.note.setText("  ·  ".join(bits))
            self.note.setObjectName("rowMeta")
            self.note.show()
            self.btn.setText("Cancel")
            self.btn.setObjectName("quietDanger")
            self._repolish(self.btn)
            return

        self.progress.hide()
        self.btn.setObjectName("primaryBtn")
        self._repolish(self.btn)

        is_installed = flavor in self._installed
        self.badge.setVisible(is_installed)
        self.btn.setText("Reinstall" if is_installed else "Download")
        # An error note stays up until the row is used again.
        self.note.setVisible(bool(self.note.text()))

    @staticmethod
    def _repolish(widget):
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    def set_installed_flavors(self, flavors: set):
        self._installed = flavors
        self._sync_state()

    # -- download state ---------------------------------------------------

    def set_downloading(self, flavor_id: str, pct: int = -1,
                        mbps: float = 0.0, eta: int = 0):
        self._downloading[flavor_id] = (pct, mbps, eta)
        if flavor_id == self.current_flavor():
            self.note.setText("")
            self._sync_state()

    def clear_downloading(self, flavor_id: str, message: str = ""):
        self._downloading.pop(flavor_id, None)
        self.note.setText(message)
        self.note.setObjectName("errorText" if message else "rowMeta")
        self._repolish(self.note)
        self._sync_state()

    def is_downloading(self, flavor_id: str) -> bool:
        return flavor_id in self._downloading

    # -- actions ----------------------------------------------------------

    def _on_button(self):
        flavor = self.current_flavor()
        if flavor in self._downloading:
            self.on_cancel(self.recipe, flavor)
        else:
            self.note.setText("")
            self.on_install(self.recipe, flavor)

    def _install(self):
        """Kept for tests and callers that want to start a download directly."""
        self.on_install(self.recipe, self.current_flavor())

    # -- filtering --------------------------------------------------------

    def matches(self, query: str, category: str) -> bool:
        if category != "All" and self.recipe.category != category:
            return False
        if not query:
            return True
        q = query.lower()
        haystack = " ".join([
            self.recipe.name, self.recipe.key, self.recipe.category,
            self.recipe.description,
            " ".join(f.name for f in self.flavors),
        ]).lower()
        return q in haystack


class CatalogView(QWidget):
    """Browsable catalog page."""

    def __init__(self, on_install: Callable[[DistroRecipe, str], None],
                 installed_lookup: Optional[Callable[[str], set]] = None,
                 on_cancel: Optional[Callable[[DistroRecipe, str], None]] = None,
                 parent=None):
        super().__init__(parent)
        self.on_install = on_install
        self.on_cancel = on_cancel or (lambda r, f: None)
        self.installed_lookup = installed_lookup or (lambda key: set())
        self.rows: Dict[str, CatalogRow] = {}
        self._category = "All"
        self._build_ui()
        self._populate()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 20)
        root.setSpacing(0)

        header = QHBoxLayout()
        header.setSpacing(10)   # see the note in dashboard.py's _build_ui

        titles = QVBoxLayout()
        titles.setSpacing(3)

        title = QLabel("Browse Catalog")
        title.setObjectName("pageTitle")
        titles.addWidget(title)

        self.subtitle = QLabel("")
        self.subtitle.setObjectName("pageSubtitle")
        titles.addWidget(self.subtitle)

        header.addLayout(titles)
        header.addStretch()

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search distributions…")
        self.search.setFixedWidth(280)
        self.search.setMinimumHeight(36)
        self.search.textChanged.connect(self._apply_filter)
        self.search.setClearButtonEnabled(True)
        header.addWidget(self.search, 0, Qt.AlignmentFlag.AlignVCenter)

        root.addLayout(header)
        root.addSpacing(16)

        # Seven chips need ~866px in a row and the page has 632px at the
        # minimum window width, so they wrap.
        chips_host = QWidget()
        policy = chips_host.sizePolicy()
        policy.setHeightForWidth(True)
        chips_host.setSizePolicy(policy)
        self.chips = FlowLayout(chips_host, h_spacing=8, v_spacing=8)

        self._chip_group = QButtonGroup(self)
        self._chip_group.setExclusive(True)
        for cat in registry.get_categories():
            # Qt reads "&" in button text as a mnemonic marker.
            chip = QPushButton(cat.replace("&", "&&"))
            chip.setObjectName("filterChip")
            chip.setCheckable(True)
            chip.setCursor(Qt.CursorShape.PointingHandCursor)
            chip.clicked.connect(lambda _=False, c=cat: self._set_category(c))
            # A squeezed chip elides its label and stops naming its filter.
            chip.setMinimumWidth(chip.sizeHint().width())
            self._chip_group.addButton(chip)
            self.chips.addWidget(chip)
            if cat == "All":
                chip.setChecked(True)
        root.addWidget(chips_host)
        root.addSpacing(14)

        # --- list ---------------------------------------------------------
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.host = QWidget()
        self.list_layout = QVBoxLayout(self.host)
        self.list_layout.setContentsMargins(0, 0, 6, 0)
        self.list_layout.setSpacing(8)
        self.list_layout.addStretch()
        self.scroll.setWidget(self.host)
        root.addWidget(self.scroll, 1)

        self.empty = EmptyState("No matches", "Try a different search term or category.")
        self.empty.hide()
        root.addWidget(self.empty)

    def _populate(self):
        recipes = sorted(registry.get_all_recipes(), key=lambda r: r.name.lower())
        for recipe in recipes:
            row = CatalogRow(recipe, self.on_install, self.installed_lookup(recipe.key),
                             on_cancel=self.on_cancel)
            self.rows[recipe.key] = row
            self.list_layout.insertWidget(self.list_layout.count() - 1, row)
        self._apply_filter()

    # -- filtering --------------------------------------------------------

    def _set_category(self, category: str):
        self._category = category
        self._apply_filter()

    def _apply_filter(self):
        query = self.search.text().strip()
        visible = 0
        for row in self.rows.values():
            show = row.matches(query, self._category)
            row.setVisible(show)
            visible += int(show)

        self.empty.setVisible(visible == 0)
        self.scroll.setVisible(visible > 0)
        total = len(self.rows)
        self.subtitle.setText(
            f"{total} distributions and rescue tools"
            if visible == total else f"Showing {visible} of {total}"
        )

    def refresh_installed(self):
        for key, row in self.rows.items():
            row.set_installed_flavors(self.installed_lookup(key))

    # -- download reporting ------------------------------------------------

    def on_download_started(self, key: str, flavor_id: str):
        row = self.rows.get(key)
        if row:
            row.set_downloading(flavor_id)

    def on_download_progress(self, key: str, flavor_id: str, pct: int,
                             mbps: float, eta: int):
        row = self.rows.get(key)
        if row:
            row.set_downloading(flavor_id, pct, mbps, eta)

    def on_download_ended(self, key: str, flavor_id: str, ok: bool, message: str):
        row = self.rows.get(key)
        if row:
            # A failure keeps its reason on the row; success says nothing,
            # because the Installed badge already says it.
            row.clear_downloading(flavor_id, "" if ok else message)
