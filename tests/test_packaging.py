"""The branding assets and the release build.

Neither is exercised by running the app, so nothing else notices when one of
them rots — and a broken build is only discovered at tag time, when it is most
expensive.
"""
import os
import re

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRANDING = os.path.join(ROOT, "src", "assets", "branding")
PACKAGING = os.path.join(ROOT, "packaging")
WORKFLOW = os.path.join(ROOT, ".github", "workflows", "release.yml")

PNG_SIZES = (16, 24, 32, 48, 64, 128, 256, 512, 1024)
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)


def read(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as handle:
        return handle.read()


# --- branding --------------------------------------------------------------

def test_master_svg_exists():
    assert os.path.exists(os.path.join(BRANDING, "veim.svg"))


@pytest.mark.parametrize("size", PNG_SIZES)
def test_rendered_png_exists(size):
    path = os.path.join(BRANDING, f"veim-{size}.png")
    assert os.path.exists(path), f"run tools/build_icons.py to regenerate {path}"
    assert os.path.getsize(path) > 100


def test_ico_carries_every_size():
    from PIL import Image

    with Image.open(os.path.join(BRANDING, "veim.ico")) as image:
        assert sorted(image.ico.sizes()) == [(s, s) for s in ICO_SIZES]


def test_icns_is_a_well_formed_container():
    with open(os.path.join(BRANDING, "veim.icns"), "rb") as handle:
        header = handle.read(8)
        body = handle.read()
    assert header[:4] == b"icns"
    assert int.from_bytes(header[4:8], "big") == len(body) + 8


def test_app_icon_loads(qapp):
    from src.core.branding import app_icon

    icon = app_icon()
    assert not icon.isNull()
    assert icon.availableSizes()


# --- what the frozen build has to carry ------------------------------------

def test_spec_bundles_the_assets_the_app_reads_at_runtime():
    """A missing chevron leaves every dropdown with no arrow, silently, and
    missing logos leave every catalog row waiting on a network fetch."""
    spec = read(PACKAGING, "veim.spec")
    assert '"assets", "icons"' in spec
    assert "branding" in spec


def test_every_distribution_ships_a_logo():
    """Fetching these on first run left rows blank until fifty requests
    finished, and blank for good without a network."""
    from src.core.icons import ICON_URLS
    from src.recipes.registry import registry

    icon_dir = os.path.join(ROOT, "src", "assets", "icons")
    for recipe in registry.get_all_recipes():
        assert recipe.key in ICON_URLS, f"{recipe.name} has no ICON_URLS entry"
        path = os.path.join(icon_dir, f"{recipe.key}.png")
        assert os.path.exists(path), \
            f"{recipe.name}: run tools/fetch_icons.py and commit {recipe.key}.png"


@pytest.mark.parametrize("name", sorted(
    f for f in os.listdir(os.path.join(ROOT, "src", "assets", "icons"))
    if f.endswith(".png") and not f.startswith("chevron")))
def test_shipped_logo_is_not_blank(name):
    """Qt renders a subset of SVG and fails silently on the rest, writing a
    transparent image rather than none."""
    from PIL import Image

    with Image.open(os.path.join(ROOT, "src", "assets", "icons", name)) as image:
        rgba = image.convert("RGBA")
        width, height = rgba.size
        opaque = sum(1 for pixel in rgba.getdata() if pixel[3] > 8)

    assert width >= 32 and height >= 32, f"{name} is {width}x{height}"
    assert opaque > width * height * 0.01, f"{name} rendered blank"


def test_logos_resolve_without_a_writable_cache(tmp_path, qapp):
    """The frozen app's cache directory starts empty; the shipped set has to
    carry it until, and if, anything is ever downloaded."""
    from src.core.icons import IconManager
    from src.recipes.registry import registry

    manager = IconManager()
    manager.cache_dir = str(tmp_path)          # a fresh install's empty cache
    manager.pixmap_cache.clear()

    for recipe in registry.get_all_recipes():
        assert manager._icon_path(recipe.key), f"no logo resolves for {recipe.name}"
        assert manager.get_pixmap(recipe.key) is not None, \
            f"{recipe.name} renders no pixmap"


def test_spec_excludes_are_not_imported_anywhere():
    """Excluding a module the app actually imports only fails at runtime."""
    spec = read(PACKAGING, "veim.spec")
    excluded = set(re.findall(r'"([A-Za-z_][\w.]*)"', spec.split("excludes = [")[1]
                              .split("]")[0]))
    sources = []
    for folder, dirs, files in os.walk(os.path.join(ROOT, "src")):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        sources += [read(folder, f) for f in files if f.endswith(".py")]
    sources.append(read(ROOT, "main.py"))

    for module in excluded:
        package, _, leaf = module.rpartition(".")
        patterns = [rf"^\s*import {re.escape(module)}\b",
                    rf"^\s*from {re.escape(module)}[\s.]"]
        if package:
            patterns.append(rf"^\s*from {re.escape(package)} import [^\n]*\b{re.escape(leaf)}\b")
        for text in sources:
            for pattern in patterns:
                assert not re.search(pattern, text, re.M), \
                    f"spec excludes {module}, but src imports it"


def test_runtime_writes_go_somewhere_writable():
    """A frozen build runs from a read-only bundle; nothing may write into it."""
    from src.core import paths

    assert paths.icon_cache_dir()
    assert paths.log_path()
    assert paths.user_data_dir().endswith("VEIM")


# --- the release pipeline ---------------------------------------------------

def test_every_packaging_script_referenced_by_the_workflow_exists():
    workflow = read(WORKFLOW)
    for path in set(re.findall(r"packaging/[\w./-]+", workflow)):
        assert os.path.exists(os.path.join(ROOT, path)), path


def test_workflow_builds_all_three_platforms():
    workflow = read(WORKFLOW)
    for target in ("windows", "linux", "macos-arm64", "macos-x86_64"):
        assert f"target: {target}" in workflow


def test_the_declared_version_is_a_release_number():
    from packaging.version import Version

    from src import __version__

    assert Version(__version__)
    assert f'version = "{__version__}"' in read(ROOT, "pyproject.toml")


def test_the_update_check_reads_releases_not_a_branch():
    """Comparing against a branch would flag every commit as a new version."""
    source = read(ROOT, "src", "core", "app_update.py")
    assert "releases/latest" in source
    assert "Cir0cuit/VEIM" in source


def test_nothing_in_packaging_formats_a_drive():
    for folder, dirs, files in os.walk(PACKAGING):
        for name in files:
            assert not re.search(r"\b(mkfs|diskpart|dd\s+if=)\b", read(folder, name))


def test_window_title_is_not_doubled():
    """Qt appends the application display name to every window title, so
    setting it produces "VEIM - Ventoy Easy ISO Manager - VEIM"."""
    assert "setApplicationDisplayName(" not in read(ROOT, "main.py")


def test_the_program_is_named_consistently():
    for path in ("README.md", "pyproject.toml", "main.py",
                 "src/ui/app.py", "src/ui/sidebar.py"):
        assert "Ventoy Enhanced ISO Manager" not in read(ROOT, path)
