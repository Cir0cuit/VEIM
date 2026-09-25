import os
from dataclasses import dataclass
from typing import Callable, List, Dict
from PySide6.QtWidgets import QPushButton, QMenu
from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor, QActionGroup

CHEVRON_DOWN_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "assets", "icons", "chevron_down.png")
).replace("\\", "/")


def _mix(base: str, over: str, amount: float) -> str:
    """`over` laid on `base` at `amount` opacity, as a #rrggbb colour."""
    a, b = (tuple(int(c[i:i + 2], 16) for i in (1, 3, 5)) for c in (base, over))
    return "#" + "".join(f"{round(x + (y - x) * amount):02x}" for x, y in zip(a, b))


def _rgba(colour: str, alpha: int) -> str:
    """A #rrggbb colour at `alpha` (0-255), in stylesheet syntax."""
    r, g, b = (int(colour[i:i + 2], 16) for i in (1, 3, 5))
    return f"rgba({r}, {g}, {b}, {alpha})"


@dataclass
class ThemeColors:
    name: str
    mode: str
    bg_main: str
    bg_card: str
    bg_card_hover: str
    bg_input: str
    border: str
    border_focus: str
    text_primary: str
    text_secondary: str
    text_muted: str
    accent: str
    accent_hover: str
    accent_text: str
    success: str
    warning: str
    danger: str
    info: str

    # Derived in __post_init__ when not given.
    bg_sidebar: str = ""
    bg_elevated: str = ""
    row_hover: str = ""
    accent_soft: str = ""
    # The accent as text on a surface, where a fill colour can be too dark.
    accent_fg: str = ""
    icon_chip: str = ""
    icon_plate: str = ""

    def __post_init__(self):
        self.bg_sidebar = self.bg_sidebar or self.bg_card
        self.bg_elevated = self.bg_elevated or self.bg_card_hover
        self.row_hover = self.row_hover or self.bg_card_hover
        # Tinted with the accent. Falling back to bg_card_hover, as row_hover
        # does, made a selected item look like a hovered one.
        self.accent_soft = self.accent_soft or _mix(self.bg_main, self.accent, 0.16)
        self.accent_fg = self.accent_fg or self.accent
        self.icon_chip = self.icon_chip or self.bg_elevated
        # Logos that are dark shapes on transparency need a light backdrop to
        # stay visible; see IconManager.needs_light_backdrop.
        self.icon_plate = self.icon_plate or (
            "#e8edf4" if self.mode == "Dark" else self.icon_chip
        )

THEMES: Dict[str, ThemeColors] = {
    "Dark Modern": ThemeColors(
        name="Dark Modern",
        mode="Dark",
        bg_main="#0d1117",
        bg_card="#161b22",
        bg_card_hover="#1d2430",
        bg_input="#0b0f15",
        border="#283039",
        border_focus="#58a6ff",
        text_primary="#e6edf3",
        text_secondary="#b6c2cf",
        text_muted="#7d8590",
        accent="#1f6feb",
        accent_hover="#388bfd",
        accent_text="#ffffff",
        success="#3fb950",
        warning="#d29922",
        danger="#f85149",
        info="#58a6ff",
        bg_sidebar="#0f141b",
        accent_fg="#58a6ff",
    ),
    "Amoled Black": ThemeColors(
        name="Amoled Black",
        mode="Dark",
        bg_main="#000000",
        bg_card="#0b0b0d",
        bg_card_hover="#161619",
        bg_input="#000000",
        border="#232327",
        border_focus="#c4c4cc",
        # Grey, not white: white on #000000 is 20:1 and glares.
        text_primary="#d4d4d8",
        text_secondary="#909099",
        text_muted="#6b6b75",
        accent="#c4c4cc",
        accent_hover="#dcdce2",
        accent_text="#08080a",
        success="#3fa45c",
        warning="#c99a2e",
        danger="#d9534f",
        info="#4a9fd4",
        bg_sidebar="#000000",
        accent_soft="#1a1a1e",
        icon_chip="#141416",
    ),
    "Gruvbox Dark": ThemeColors(
        name="Gruvbox Dark",
        mode="Dark",
        bg_main="#1d2021",
        bg_card="#282828",
        bg_card_hover="#32302f",
        bg_input="#1d2021",
        border="#504945",
        border_focus="#fabd2f",
        text_primary="#ebdbb2",
        text_secondary="#d5c4a1",
        text_muted="#a89984",
        accent="#d79921",
        accent_hover="#fabd2f",
        accent_text="#1d2021",
        success="#b8bb26",
        warning="#fe8019",
        danger="#fb4934",
        info="#83a598",
        bg_sidebar="#1d2021",
    ),
    "Solarized Light": ThemeColors(
        name="Solarized Light",
        mode="Light",
        bg_main="#eee8d5",
        bg_card="#fdf6e3",
        bg_card_hover="#f7f0dc",
        bg_input="#fdf6e3",
        border="#ded8c4",
        border_focus="#268bd2",
        text_primary="#073642",
        text_secondary="#586e75",
        # base00: base0 is a dark-background tone, 2.6:1 on this page.
        text_muted="#657b83",
        # Darker than Solarized blue, which is a foreground colour: as a button
        # fill it only reaches 3.7:1.
        accent="#1b6fa8",
        accent_hover="#176089",
        accent_text="#ffffff",
        success="#859900",
        warning="#b58900",
        danger="#dc322f",
        info="#2aa198",
        bg_sidebar="#fdf6e3",
        icon_chip="#f0e9d4",
        accent_soft="#dfe8f0",
        accent_fg="#176089",
    ),
    "Cyberpunk": ThemeColors(
        name="Cyberpunk",
        mode="Dark",
        bg_main="#080611",
        bg_card="#120f1f",
        bg_card_hover="#1b172d",
        bg_input="#0b0917",
        border="#2b2247",
        border_focus="#ff2bd1",
        text_primary="#f0f9ff",
        text_secondary="#a5f3fc",
        text_muted="#7c6f9e",
        accent="#00e5ff",
        accent_hover="#5cf2ff",
        accent_text="#06121a",
        success="#00ffa3",
        warning="#ffd000",
        danger="#ff2e63",
        info="#00e5ff",
        accent_soft="#1d2b3d",
    ),
    "Nord": ThemeColors(
        name="Nord",
        mode="Dark",
        bg_main="#242933",
        bg_card="#2e3440",
        bg_card_hover="#3b4252",
        bg_input="#272c36",
        border="#434c5e",
        border_focus="#88c0d0",
        text_primary="#eceff4",
        text_secondary="#d8dee9",
        text_muted="#8792a6",
        accent="#88c0d0",
        accent_hover="#a3d2de",
        accent_text="#2e3440",
        success="#a3be8c",
        warning="#ebcb8b",
        danger="#bf616a",
        info="#5e81ac",
        bg_sidebar="#2b303b",
    ),
    "Dracula": ThemeColors(
        name="Dracula",
        mode="Dark",
        bg_main="#21222c",
        bg_card="#282a36",
        bg_card_hover="#343746",
        bg_input="#1e1f29",
        border="#44475a",
        border_focus="#bd93f9",
        text_primary="#f8f8f2",
        text_secondary="#d8d8d2",
        text_muted="#6272a4",
        accent="#bd93f9",
        accent_hover="#d0b0fb",
        accent_text="#21222c",
        success="#50fa7b",
        warning="#f1fa8c",
        danger="#ff5555",
        info="#8be9fd",
        bg_sidebar="#242530",
    ),
    "Clean Light": ThemeColors(
        name="Clean Light",
        mode="Light",
        bg_main="#f6f8fa",
        bg_card="#ffffff",
        bg_card_hover="#f2f6fa",
        bg_input="#ffffff",
        border="#e0e6ed",
        border_focus="#2563eb",
        text_primary="#111827",
        text_secondary="#374151",
        text_muted="#6b7280",
        accent="#2563eb",
        accent_hover="#1d4ed8",
        accent_text="#ffffff",
        success="#059669",
        warning="#b45309",
        danger="#dc2626",
        info="#2563eb",
        bg_sidebar="#ffffff",
        icon_chip="#f2f6fa",
        accent_soft="#e8eefb",
        accent_fg="#1d4ed8",
    ),
}

def generate_stylesheet(c: ThemeColors) -> str:
    return f"""
    * {{
        font-family: 'Atkinson Hyperlegible Next', 'Segoe UI', sans-serif;
    }}
    QToolTip {{
        background-color: {c.bg_elevated};
        color: {c.text_primary};
        border: 1px solid {c.border};
        padding: 5px 8px;
        font-size: 12px;
    }}
    QMainWindow, QDialog {{
        background-color: {c.bg_main};
        color: {c.text_primary};
    }}
    QWidget {{
        color: {c.text_primary};
    }}
    QScrollArea {{
        background-color: transparent;
        border: none;
    }}
    QScrollArea > QWidget > QWidget {{
        background-color: transparent;
    }}
    QScrollBar:vertical {{
        background: transparent;
        width: 8px;
        margin: 4px 2px 4px 2px;
        border-radius: 4px;
    }}
    QScrollBar::handle:vertical {{
        background: {c.border};
        min-height: 24px;
        border-radius: 4px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {c.accent};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
        border: none;
        background: none;
    }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
        background: none;
    }}
    QLineEdit {{
        background-color: {c.bg_input};
        color: {c.text_primary};
        border: 1px solid {c.border};
        border-radius: 8px;
        padding: 8px 14px;
        font-size: 13px;
        selection-background-color: {c.accent};
        selection-color: {c.accent_text};
    }}
    QLineEdit:focus {{
        border: 1.5px solid {c.border_focus};
    }}
    QPushButton {{
        background-color: {c.bg_card};
        color: {c.text_primary};
        border: 1px solid {c.border};
        border-radius: 8px;
        padding: 8px 16px;
        font-size: 13px;
        font-weight: 600;
    }}
    QPushButton:hover {{
        background-color: {c.bg_card_hover};
        border-color: {c.border_focus};
    }}
    QPushButton:pressed {{
        background-color: {c.border};
    }}
    QPushButton:disabled {{
        background-color: {c.bg_input};
        color: {c.text_muted};
        border-color: {c.border};
    }}
    /* Buttons take focus from the keyboard only (see make_button), so this
       ring appears for someone tabbing through and never after a click. */
    QPushButton:focus {{
        border-color: {c.border_focus};
    }}
    QPushButton#primaryBtn {{
        background-color: {c.accent};
        color: {c.accent_text};
        border: 1px solid {c.accent};
        font-weight: 700;
    }}
    QPushButton#primaryBtn:hover {{
        background-color: {c.accent_hover};
        border-color: {c.accent_hover};
    }}
    QPushButton#primaryBtn:focus {{
        border-color: {c.text_primary};
    }}
    QMenu {{
        background-color: {c.bg_card};
        color: {c.text_primary};
        border: 1px solid {c.border};
        border-radius: 8px;
        padding: 6px;
    }}
    QMenu::item {{
        padding: 8px 24px 8px 16px;
        border-radius: 6px;
        font-size: 13px;
        font-weight: 500;
    }}
    QMenu::item:selected {{
        background-color: {c.bg_card_hover};
        color: {c.accent};
    }}
    QMenu::separator {{
        height: 1px;
        background-color: {c.border};
        margin: 4px 8px;
    }}
    /* The background is restated so the button keeps its colour while its
       menu is open, which Qt draws as :pressed. */
    QPushButton#themeBtn {{
        background-color: {c.bg_card};
        padding: 6px 14px;
    }}
    QPushButton#themeBtn:hover {{
        background-color: {c.bg_card_hover};
    }}
    QPushButton#themeBtn::menu-indicator {{
        subcontrol-origin: padding;
        subcontrol-position: center right;
        right: 8px;
    }}
    QComboBox {{
        background-color: {c.bg_input};
        color: {c.text_primary};
        border: 1px solid {c.border};
        border-radius: 8px;
        padding: 6px 32px 6px 14px;
        font-size: 13px;
        font-weight: 500;
        min-height: 26px;
    }}
    QComboBox:hover {{
        border-color: {c.accent};
        background-color: {c.bg_card_hover};
    }}
    QComboBox::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: center right;
        width: 28px;
        border: none;
        background: transparent;
    }}
    QComboBox::down-arrow {{
        image: url("{CHEVRON_DOWN_PATH}");
        width: 12px;
        height: 12px;
    }}
    /* The frame belongs to the popup container, not the list; see
       FlavorCombo.showPopup. */
    QComboBox QAbstractItemView {{
        background-color: transparent;
        color: {c.text_primary};
        border: none;
        padding: 4px;
        outline: none;
        selection-background-color: {c.bg_card_hover};
        selection-color: {c.accent};
    }}
    QComboBox QAbstractItemView::item {{
        min-height: 32px;
        padding: 6px 12px;
        border-radius: 6px;
    }}
    QComboBox QAbstractItemView::item:selected {{
        background-color: {c.bg_card_hover};
        color: {c.accent};
        font-weight: 600;
    }}
    QProgressBar {{
        background-color: {c.bg_input};
        border: 1px solid {c.border};
        border-radius: 4px;
        height: 8px;
        text-align: center;
    }}
    QProgressBar::chunk {{
        background-color: {c.accent};
        border-radius: 3px;
    }}
    """ + _component_stylesheet(c)


def _component_stylesheet(c: ThemeColors) -> str:
    """Styling for the app's own components, keyed on objectName."""
    return f"""
    /* ---------- Shell ---------- */
    QWidget#sidebar {{
        background-color: {c.bg_sidebar};
        border-right: 1px solid {c.border};
    }}
    QLabel#brandMark {{
        color: {c.accent_fg};
        font-size: 20px;
        font-weight: 700;
        letter-spacing: 1px;
    }}
    QLabel#brandVersion {{
        color: {c.text_muted};
        font-size: 11px;
        font-weight: 600;
        padding-bottom: 3px;
    }}
    QLabel#brandSub {{
        color: {c.text_muted};
        font-size: 12px;
    }}

    /* ---------- Sidebar navigation ---------- */
    QPushButton#navItem {{
        background-color: transparent;
        color: {c.text_secondary};
        border: 1px solid transparent;
        border-radius: 8px;
        padding: 9px 12px;
        font-size: 14px;
        font-weight: 500;
        text-align: left;
    }}
    QPushButton#navItem:hover {{
        background-color: {c.row_hover};
        color: {c.text_primary};
    }}
    QPushButton#navItem:checked {{
        background-color: {c.accent_soft};
        color: {c.text_primary};
        font-weight: 700;
    }}
    QPushButton#navItem:focus {{
        border-color: {c.border_focus};
    }}

    /* ---------- Content surfaces ---------- */
    QLabel#pageTitle {{
        color: {c.text_primary};
        font-size: 26px;
        font-weight: 700;
    }}
    QLabel#pageSubtitle {{
        color: {c.text_muted};
        font-size: 13px;
    }}
    /* With the rows unboxed, the heading is what divides one list from the
       next, so it outweighs a row title. */
    QLabel#sectionLabel {{
        color: {c.text_primary};
        font-size: 14px;
        font-weight: 700;
        padding: 12px 0 4px 0;
    }}

    /* ---------- Rows ----------
       A list, not a stack of cards: rows sit on the page and only the one
       under the pointer, or one with a transfer running, gets a surface. */
    QFrame#row {{
        background-color: transparent;
        border: 1px solid transparent;
        border-radius: 10px;
    }}
    QFrame#row:hover {{
        background-color: {c.row_hover};
    }}
    QFrame#rowActive {{
        background-color: {c.bg_card};
        border: 1px solid {c.accent};
        border-radius: 10px;
    }}
    QFrame#driveCard, QFrame#notice {{
        background-color: {c.bg_card};
        border: 1px solid {c.border};
        border-radius: 10px;
    }}
    QFrame#driveCard:hover {{
        background-color: {c.row_hover};
        border-color: {c.border_focus};
    }}
    QLabel#rowTitle {{
        color: {c.text_primary};
        font-size: 15px;
        font-weight: 600;
    }}
    QLabel#rowMeta {{
        color: {c.text_muted};
        font-size: 12px;
    }}
    QLabel#rowDesc {{
        color: {c.text_secondary};
        font-size: 12px;
    }}
    QWidget#driveMap {{
        font-size: 12px;
    }}
    QProgressBar#rowProgress {{
        background-color: {c.bg_input};
        border: none;
        border-radius: 2px;
        height: 5px;
        max-height: 5px;
        text-align: center;
    }}
    QProgressBar#rowProgress::chunk {{
        background-color: {c.accent};
        border-radius: 2px;
    }}
    QLabel#iconChip {{
        background-color: {c.icon_chip};
        border: 1px solid {c.border};
        border-radius: 10px;
    }}
    QLabel#iconChipPlate {{
        background-color: {c.icon_plate};
        border: 1px solid {c.border};
        border-radius: 10px;
    }}

    /* ---------- Buttons ----------
       Filled for the one action a screen is about, tonal for an action every
       row repeats, bordered for page-level secondaries, bare for the rest. */
    QPushButton#ghostBtn, QPushButton#quietBtn, QPushButton#quietDanger,
    QPushButton#subtleDanger, QPushButton#tonalBtn {{
        background-color: transparent;
        border: 1px solid transparent;
        border-radius: 8px;
        padding: 7px 14px;
        font-size: 12px;
        font-weight: 600;
    }}
    QPushButton#ghostBtn {{
        color: {c.text_secondary};
        border-color: {c.border};
    }}
    QPushButton#ghostBtn:hover {{
        background-color: {c.row_hover};
        color: {c.text_primary};
        border-color: {c.border_focus};
    }}
    QPushButton#ghostBtn:disabled {{
        color: {c.text_muted};
        border-color: {c.border};
    }}
    QPushButton#quietBtn, QPushButton#subtleDanger {{
        color: {c.text_secondary};
        padding: 7px 10px;
    }}
    QPushButton#quietBtn:hover {{
        background-color: {c.bg_card_hover};
        color: {c.text_primary};
    }}
    QPushButton#quietBtn:disabled {{
        background-color: transparent;
        color: {c.text_muted};
    }}
    QPushButton#subtleDanger:hover {{
        color: {c.danger};
    }}
    QPushButton#quietDanger {{
        color: {c.danger};
    }}
    QPushButton#quietDanger:hover {{
        background-color: {c.danger};
        color: #ffffff;
        border-color: {c.danger};
    }}
    QPushButton#tonalBtn {{
        background-color: {c.accent_soft};
        color: {c.accent_fg};
        font-weight: 700;
    }}
    QPushButton#tonalBtn:hover {{
        background-color: {c.accent};
        color: {c.accent_text};
        border-color: {c.accent};
    }}
    QPushButton#ghostBtn:focus, QPushButton#quietBtn:focus,
    QPushButton#quietDanger:focus, QPushButton#subtleDanger:focus,
    QPushButton#tonalBtn:focus {{
        border-color: {c.border_focus};
    }}

    /* ---------- Chips / pills ---------- */
    QPushButton#filterChip {{
        background-color: transparent;
        color: {c.text_secondary};
        border: 1px solid {c.border};
        border-radius: 14px;
        padding: 5px 14px;
        font-size: 12px;
        font-weight: 600;
    }}
    QPushButton#filterChip:hover {{
        border-color: {c.border_focus};
        color: {c.text_primary};
    }}
    QPushButton#filterChip:checked {{
        background-color: {c.accent_soft};
        border-color: {c.accent_fg};
        color: {c.accent_fg};
    }}
    QPushButton#filterChip:focus {{
        border-color: {c.border_focus};
    }}
    /* Colour is kept for what wants attention. A current release reads as
       plain text; a failure is filled; an update carries the accent. */
    QLabel#statusPill, QLabel#okPill, QLabel#warnPill, QLabel#accentPill {{
        border-radius: 10px;
        padding: 3px 10px;
        font-size: 12px;
        font-weight: 600;
    }}
    /* Weight 400, unlike the bare buttons beside them: these are answers,
       not things to press. */
    QLabel#statusPill {{
        color: {c.text_muted};
        font-weight: 400;
    }}
    QLabel#okPill {{
        color: {c.text_muted};
        font-weight: 400;
    }}
    QLabel#accentPill {{
        background-color: {c.accent_soft};
        color: {c.accent_fg};
        font-weight: 700;
    }}
    /* A wash and an edge rather than a fill: readable in every palette, and
       never mistaken for the filled primary button beside it (Gruvbox's accent
       and warning are neighbouring golds). */
    QLabel#warnPill {{
        background-color: {_rgba(c.warning, 40)};
        border: 1px solid {c.warning};
        color: {c.text_primary};
        font-weight: 700;
    }}
    QLabel#errorText {{
        color: {c.danger};
        font-size: 12px;
        font-weight: 600;
    }}

    /* ---------- Drive capacity ---------- */
    QFrame#capacityTrack, QFrame#capacityFill, QFrame#capacityReserved,
    QFrame#capacityFillWarn {{
        border: none;
        border-radius: 3px;
    }}
    /* The same code as the drive map: an outlined track, the accent, and a
       paler accent for space downloads have spoken for. */
    QFrame#capacityTrack {{
        background-color: {c.border};
    }}
    QFrame#capacityFill {{
        background-color: {c.accent};
    }}
    QFrame#capacityReserved {{
        background-color: {_rgba(c.accent, 110)};
    }}
    QFrame#capacityFillWarn {{
        background-color: {c.warning};
    }}

    /* ---------- Empty state ---------- */
    QFrame#emptyState {{
        background-color: transparent;
        border: 1.5px dashed {c.border};
        border-radius: 14px;
    }}
    QLabel#emptyTitle {{
        color: {c.text_primary};
        font-size: 17px;
        font-weight: 700;
    }}
    QLabel#emptyBody {{
        color: {c.text_muted};
        font-size: 13px;
    }}
    """

class ThemeManager:
    def __init__(self):
        self.pref_file = os.path.join(os.path.expanduser("~"), ".veim_theme")
        self.selected_theme = "Dark Modern"
        self._load_pref()
        self.current: ThemeColors = self._resolve_theme(self.selected_theme)
        self.listeners: List[Callable[[ThemeColors], None]] = []

    def _get_system_mode(self) -> str:
        try:
            import darkdetect
            sys_dark = darkdetect.isDark()
            return "Dark" if sys_dark else "Light"
        except Exception:
            return "Dark"

    def _resolve_theme(self, theme_name: str) -> ThemeColors:
        if theme_name == "System":
            sys_mode = self._get_system_mode()
            return THEMES["Clean Light"] if sys_mode == "Light" else THEMES["Dark Modern"]
        return THEMES.get(theme_name, THEMES["Dark Modern"])

    def _load_pref(self):
        if os.path.exists(self.pref_file):
            try:
                with open(self.pref_file, "r", encoding="utf-8") as f:
                    val = f.read().strip()
                    if val in THEMES or val == "System":
                        self.selected_theme = val
            except Exception:
                pass

    def _save_pref(self):
        try:
            with open(self.pref_file, "w", encoding="utf-8") as f:
                f.write(self.selected_theme)
        except Exception:
            pass

    def set_theme(self, theme_name: str):
        if theme_name in THEMES or theme_name == "System":
            self.selected_theme = theme_name
            self.current = self._resolve_theme(theme_name)
            self._save_pref()
            self._notify()

    def add_listener(self, cb: Callable[[ThemeColors], None]):
        self.listeners.append(cb)

    def _notify(self):
        for cb in self.listeners:
            try:
                cb(self.current)
            except Exception:
                pass

theme_manager = ThemeManager()

class ThemeButton(QPushButton):
    """Menu button listing every theme in THEMES, plus System Match."""
    def __init__(self, parent=None):
        super().__init__("Theme", parent)
        self.setObjectName("themeBtn")
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setFixedHeight(34)
        self.setFixedWidth(96)
        self._build_menu()

    def _build_menu(self):
        menu = QMenu(self)
        menu.setObjectName("themeMenu")
        # Exclusive by default: checking one theme unchecks the rest.
        group = QActionGroup(menu)
        for key in [*THEMES, "System"]:
            if key == "System":
                menu.addSeparator()
            act = menu.addAction("System Match" if key == "System" else key)
            act.setCheckable(True)
            act.setChecked(key == theme_manager.selected_theme)
            act.triggered.connect(lambda _=False, k=key: theme_manager.set_theme(k))
            group.addAction(act)
        self.setMenu(menu)
