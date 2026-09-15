"""Palette invariants.

Every theme is rendered through one stylesheet keyed on objectName, so a theme
missing a token or carrying an unreadable pairing breaks the whole app rather
than one screen. These checks run over all of them.
"""
import re

import pytest

pytest.importorskip("PySide6")

from src.ui.theme import THEMES, ThemeColors, generate_stylesheet

HEX = re.compile(r"^#[0-9a-fA-F]{6}$")

COLOR_FIELDS = [
    "bg_main", "bg_card", "bg_card_hover", "bg_input", "border", "border_focus",
    "text_primary", "text_secondary", "text_muted", "accent", "accent_hover",
    "accent_text", "success", "warning", "danger", "info",
    "bg_sidebar", "bg_elevated", "row_hover", "accent_soft", "icon_chip",
    "icon_plate",
]


def _rgb(value: str):
    v = value.lstrip("#")
    return int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16)


def _relative_luminance(value: str) -> float:
    def channel(c):
        c /= 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(c) for c in _rgb(value))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    la, lb = _relative_luminance(a), _relative_luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


@pytest.mark.parametrize("name", list(THEMES))
def test_every_colour_is_a_hex_triplet(name):
    theme = THEMES[name]
    for field in COLOR_FIELDS:
        value = getattr(theme, field)
        assert HEX.match(value), f"{name}.{field} is not a #rrggbb colour: {value!r}"


@pytest.mark.parametrize("name", list(THEMES))
def test_body_text_is_readable_on_its_surfaces(name):
    """WCAG AA for body text is 4.5:1; these are large-ish UI strings, so 4:1."""
    theme = THEMES[name]
    for surface in ("bg_main", "bg_card"):
        ratio = contrast(theme.text_primary, getattr(theme, surface))
        assert ratio >= 4.0, f"{name}: text_primary on {surface} is only {ratio:.1f}:1"


@pytest.mark.parametrize("name", list(THEMES))
def test_primary_button_label_is_readable(name):
    """accent_text is painted directly on accent - the pairing must hold up."""
    theme = THEMES[name]
    ratio = contrast(theme.accent_text, theme.accent)
    assert ratio >= 4.0, f"{name}: accent_text on accent is only {ratio:.1f}:1"


@pytest.mark.parametrize("name", list(THEMES))
def test_muted_text_stays_distinguishable(name):
    theme = THEMES[name]
    ratio = contrast(theme.text_muted, theme.bg_card)
    assert ratio >= 2.5, f"{name}: text_muted on bg_card is only {ratio:.1f}:1"


@pytest.mark.parametrize("name", list(THEMES))
def test_rows_are_distinguishable_from_their_background(name):
    """A card the same colour as the page makes the list vanish."""
    theme = THEMES[name]
    assert theme.bg_card != theme.bg_main, f"{name}: cards are invisible against the page"
    assert theme.bg_card_hover != theme.bg_card, f"{name}: hover state is a no-op"
    # The border used to equal the hover surface in Nord and Dracula, so a
    # hovered row lost its outline entirely.
    assert theme.border != theme.bg_card_hover, f"{name}: hovered rows lose their border"


@pytest.mark.parametrize("name", list(THEMES))
def test_stylesheet_renders_without_leftover_placeholders(name):
    qss = generate_stylesheet(THEMES[name])
    assert "{" in qss and "None" not in qss
    assert "#iconChip" in qss and "#iconChipPlate" in qss


def test_amoled_black_is_actually_black():
    """The point of the theme is switched-off OLED pixels, not 'very dark'."""
    theme = THEMES["Amoled Black"]
    assert theme.bg_main == "#000000"
    assert theme.bg_sidebar == "#000000"
    assert theme.bg_input == "#000000"


def test_icon_chip_follows_the_palette():
    """The chip behind a logo used to be hardcoded white on every dark theme."""
    chips = {name: t.icon_chip for name, t in THEMES.items()}
    assert "#ffffff" not in {c.lower() for c in chips.values()}, chips
    for name, theme in THEMES.items():
        if theme.mode != "Dark":
            continue
        # A dark theme's chip belongs to the dark end of its own palette.
        assert _relative_luminance(theme.icon_chip) < 0.25, \
            f"{name}: icon chip is a bright box, not a themed surface"


def test_dark_themes_still_offer_a_light_plate():
    """Solid-dark logos (TUXEDO, Debian) need a light backing to stay visible."""
    for name, theme in THEMES.items():
        if theme.mode != "Dark":
            continue
        assert contrast("#000000", theme.icon_plate) >= 7.0, \
            f"{name}: a black logo would disappear on the plate"


def test_derived_surfaces_default_without_being_restated():
    minimal = ThemeColors(
        name="T", mode="Dark",
        bg_main="#000000", bg_card="#111111", bg_card_hover="#222222",
        bg_input="#000000", border="#333333", border_focus="#4444ff",
        text_primary="#ffffff", text_secondary="#dddddd", text_muted="#888888",
        accent="#4444ff", accent_hover="#6666ff", accent_text="#ffffff",
        success="#00ff00", warning="#ffff00", danger="#ff0000", info="#00ffff",
    )
    assert minimal.bg_sidebar == "#111111"
    assert minimal.icon_chip == "#222222"     # derived from bg_elevated
    assert minimal.icon_plate != minimal.icon_chip
