"""elementary OS resolution against a captured shape of elementary.io.

Runs offline. The recipe used to answer "8.1" whenever it could not read a
version out of the download link - a number that would have gone on being
reported as the latest release for as long as the page stayed unreadable.
"""
import pytest

from src.core.recipe_base import ScrapeError
from src.recipes.community_desktop import ElementaryRecipe
from tests.test_stale_recipes import _with


def _recipe(monkeypatch, page):
    return _with(monkeypatch, ElementaryRecipe(), {"https://elementary.io/": page})[0]


def test_version_comes_from_the_download_link(monkeypatch):
    page = '<a href="//ams3.dl.elementary.io/download/abc=/elementaryos-8.1-stable-amd64.20260219.iso">'
    info = _recipe(monkeypatch, page).fetch_download_info("stable")

    assert info.version == "8.1 (20260219)"
    assert info.filename == "elementaryos-8.1-stable-amd64.20260219.iso"


def test_a_link_with_no_version_is_not_answered_with_a_guess(monkeypatch):
    page = '<a href="//ams3.dl.elementary.io/download/abc=/elementary-stable-amd64-latest.iso">'

    with pytest.raises(ScrapeError):
        _recipe(monkeypatch, page).fetch_download_info("stable")


def test_link_on_the_dl_elementaryos_org_mirror(monkeypatch):
    """Regression: the mirror moved to dl.elementaryos.org/<token>/, with no
    /download/ in the path, and the row read "No current release"."""
    host = "https://dl.elementaryos.org/MTc5MDgxMjk0Mw=="
    page = (
        '<a href="magnet:?xt=urn:btih:90b3&dn=elementaryos-8.1-stable-arm64.20260219.iso'
        '&ws=https%3A%2F%2Fdl.elementaryos.org%2FMTc5MDgxMjk0Mw%3D%3D%2Felementaryos-8.1-stable-arm64.20260219.iso">'
        f'<a href="{host}/elementaryos-8.1-stable-arm64.20260219.iso">'
        f'<a href="{host}/elementaryos-8.1-stable-amd64.20260219.iso">'
    )
    info = _recipe(monkeypatch, page).fetch_download_info("stable")

    assert info.version == "8.1 (20260219)"
    assert info.url == f"{host}/elementaryos-8.1-stable-amd64.20260219.iso"
    assert info.filename == "elementaryos-8.1-stable-amd64.20260219.iso"
