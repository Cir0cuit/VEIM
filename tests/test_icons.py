"""Icon coverage.

A missing ICON_URLS entry is silent: the catalog just renders a generic
placeholder, which is how tuxedo and hackeros shipped without real logos.
"""
import os

from src.core.icons import ICON_URLS, BUNDLED_PREFIX, BRANDING_DIR
from src.recipes.registry import registry


def test_every_recipe_has_an_icon():
    keys = {r.key for r in registry.get_all_recipes()}
    missing = sorted(keys - set(ICON_URLS))
    assert not missing, f"no icon configured for: {missing}"


def test_no_orphan_icon_entries():
    keys = {r.key for r in registry.get_all_recipes()}
    orphans = sorted(set(ICON_URLS) - keys)
    assert not orphans, f"icon entries with no matching recipe: {orphans}"


def test_icon_sources_are_https_or_bundled():
    """Every source is either a fetchable https URL or a file that ships with us.

    Tails is the bundled case: the only published files are wordmarks with a
    baked white background, so the mark-only logo travels with the app.
    """
    bad = sorted(k for k, u in ICON_URLS.items()
                 if not (u.startswith("https://") or u.startswith(BUNDLED_PREFIX)))
    assert not bad, f"icon sources must be https or bundled: {bad}"


def test_bundled_icons_actually_ship():
    """A bundled entry pointing at a missing file draws a placeholder forever."""
    missing = []
    for key, url in ICON_URLS.items():
        if not url.startswith(BUNDLED_PREFIX):
            continue
        path = os.path.join(BRANDING_DIR, url[len(BUNDLED_PREFIX):])
        if not os.path.exists(path):
            missing.append(f"{key} -> {path}")
    assert not missing, f"bundled icon files are absent: {missing}"
