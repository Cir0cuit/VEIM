"""Tiny Core and Puppy resolution against captured directory listings.

Runs offline. Both recipes used to name a release folder outright - "15.x",
"10.0.12" - which is a version number by another route: it kept working, and
kept reporting the release that was current when it was written. Tiny Core
went on to 17.1 while the recipe still said 15.0, so a drive holding 16.2 was
offered a downgrade as an update.
"""
import pytest

from src.core.recipe_base import ScrapeError
from src.recipes.lightweight import PuppyRecipe, TinyCoreRecipe
from tests.test_stale_recipes import _listing, _with


TINYCORE = {
    "http://tinycorelinux.net/downloads.html": _listing(
        "17.x/x86/release/Core-current.iso", "17.x/x86/release/TinyCore-current.iso",
        "17.x/x86/release/CorePlus-current.iso"),
    "http://tinycorelinux.net/17.x/x86/release/": _listing(
        "../", "Core-17.1.iso", "Core-current.iso", "CorePlus-17.0.iso", "CorePlus-17.1.iso",
        "CorePlus-current.iso", "TinyCore-17.1.iso", "TinyCore-current.iso"),
    "http://tinycorelinux.net/17.x/x86_64/release/": _listing(
        "../", "TinyCorePure64-17.2.iso", "CorePure64-17.1.iso", "CorePure64-current.iso"),
    # Still on the server, and what the recipe used to be pinned to.
    "http://tinycorelinux.net/15.x/x86/release/": _listing("CorePlus-15.0.iso"),
    "http://tinycorelinux.net/15.x/x86_64/release/": _listing("CorePure64-15.0.iso"),
}


@pytest.fixture
def tinycore(monkeypatch):
    return _with(monkeypatch, TinyCoreRecipe(), TINYCORE)


@pytest.mark.parametrize("flavor,filename", [
    ("coreplus", "CorePlus-17.1.iso"),
    ("tinycore", "TinyCore-17.1.iso"),
    ("corepure64", "CorePure64-17.1.iso"),
])
def test_tinycore_follows_the_series_the_project_links_to(tinycore, flavor, filename):
    recipe, session = tinycore
    info = recipe.fetch_download_info(flavor)

    assert info.version == "17.1"
    assert info.filename == filename
    assert info.url.endswith("/17.x/" + ("x86_64" if flavor == "corepure64" else "x86")
                             + "/release/" + filename)
    assert not any("15.x" in url for url in session.asked)


def test_tinycore_does_not_mistake_tinycorepure64_for_corepure64(tinycore):
    """"CorePure64-" is also how "TinyCorePure64-" ends; the listing above
    gives that one a higher version to make the mix-up visible."""
    recipe, _ = tinycore
    assert recipe.fetch_download_info("corepure64").filename == "CorePure64-17.1.iso"


def test_tinycore_refuses_to_guess_a_series(tinycore):
    recipe, session = tinycore
    session.pages["http://tinycorelinux.net/downloads.html"] = _listing("welcome.html")

    with pytest.raises(ScrapeError):
        recipe.fetch_download_info("coreplus")


PUPPY_BASE = "https://distro.ibiblio.org/puppylinux/"
PUPPY = {
    PUPPY_BASE + "puppy-bookwormpup/BookwormPup64/": _listing(
        "../", "10.0.10/", "10.0.12/", "10.0.8/", "10.0.9/", "build_files/", "BookwormPup64.htm"),
    PUPPY_BASE + "puppy-bookwormpup/BookwormPup64/10.0.12/": _listing(
        "../", "BookwormPup64_10.0.12.iso", "devx_BookwormPup64_10.0.12.iso"),
    PUPPY_BASE + "puppy-trixie/TrixiePup64/": _listing(
        "../", "11.1.1/", "11.2/", "11.4/", "2606%20version/", "build_files/"),
    PUPPY_BASE + "puppy-trixie/TrixiePup64/11.4/wayland/": _listing(
        "../", "Trixiepup64_Wayland-11.4.iso"),
    PUPPY_BASE + "puppy-fossa/": _listing("../", "fossapup64-9.5.iso"),
}


@pytest.fixture
def puppy(monkeypatch):
    return _with(monkeypatch, PuppyRecipe(), PUPPY)


@pytest.mark.parametrize("flavor,version,filename", [
    # 10.0.12, not 10.0.9 - which is what sorting the folders as text picks.
    ("bookworm", "10.0.12", "BookwormPup64_10.0.12.iso"),
    ("trixie", "11.4", "Trixiepup64_Wayland-11.4.iso"),
    ("fossa", "9.5", "fossapup64-9.5.iso"),
])
def test_puppy_finds_the_newest_release_folder(puppy, flavor, version, filename):
    recipe, _ = puppy
    info = recipe.fetch_download_info(flavor)

    assert (info.version, info.filename) == (version, filename)
    assert info.url.endswith(filename)


def test_puppy_picks_up_a_release_published_later(puppy):
    recipe, session = puppy
    parent = PUPPY_BASE + "puppy-bookwormpup/BookwormPup64/"
    session.pages[parent] = _listing("../", "10.0.12/", "10.1/")
    session.pages[parent + "10.1/"] = _listing("BookwormPup64_10.1.iso")

    assert recipe.fetch_download_info("bookworm").version == "10.1"
