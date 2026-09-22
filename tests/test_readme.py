"""The README describes the catalog that is actually registered."""
import os
import sys

import pytest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "tools"))

import readme_catalog  # noqa: E402


@pytest.fixture(scope="module")
def readme() -> str:
    with open(os.path.join(BASE_DIR, "README.md"), encoding="utf-8") as handle:
        return handle.read()


def test_catalog_section_is_generated_from_the_registry(readme):
    """Regenerate with: python tools/readme_catalog.py --write"""
    assert readme_catalog.render(readme) == readme


def test_counts_line_matches_the_registry(readme):
    assert readme_catalog.counts() in readme


def test_every_registered_entry_is_listed(readme):
    for recipe in readme_catalog.registry.get_all_recipes():
        assert f"- **{recipe.name}** — " in readme
        for flavor in recipe.get_flavors():
            assert flavor.name in readme, f"{recipe.name}: {flavor.name}"


def test_every_screenshot_exists(readme):
    import re
    for path in re.findall(r"docs/images/[\w.-]+\.png", readme):
        assert os.path.isfile(os.path.join(BASE_DIR, path)), path
