"""Freshness Cases for src/recipes/specialized.py: Artix, Sparky, Tails, FydeOS,
HackerOS and AlmaLinux. See tests/freshness.py for what a Case must hold.

Until 2026-10 four of these took the first link on the page (Sparky, Tails,
FydeOS) or let a testing build through (Artix), and were right only because
each page then listed a single release.
"""
import json

import pytest

from src.core.iso_identity import identify
from src.core.recipe_base import ScrapeError
from src.recipes.specialized import (
    AlmaLinuxRecipe, ArtixRecipe, FydeOSRecipe, HackerOSRecipe, SparkyRecipe, TailsRecipe)
from tests.freshness import Case, Resp, assert_newest, assert_no_fallback, use


def _links(*urls):
    return "<html><body>" + "".join(f'<a href="{u}">{u.split("/")[-1]}</a>\n' for u in urls) + "</body></html>"


def _rss(*paths):
    return "<rss><channel>" + "".join(
        f"<item><title><![CDATA[{p}]]></title>"
        f"<link>https://sourceforge.net/projects/hackeros/files{p}/download</link></item>"
        for p in paths) + "</channel></rss>"


# ------------------------------------------------------------------- Artix

ARTIX = "https://download.artixlinux.org/iso/"
_A = "https://download.artixlinux.org"

ARTIX_LINKS = (
    f"{_A}/iso/artix-plasma-openrc-20260407-x86_64.iso",
    "https://mirror3.artixlinux.org/iso/artix-plasma-openrc-20251230-x86_64.iso",
    f"{_A}/iso/artix-plasma-openrc-20260813-x86_64.iso",
    # Test builds, newer than the release and in other directories.
    f"{_A}/weekly-iso/artix-plasma-openrc-20261001-x86_64.iso",
    "https://iso.artixlinux.org/testing-iso/artix-plasma-openrc-20261002-x86_64.iso",
    # Another init system's image of the same desktop.
    f"{_A}/iso/artix-plasma-dinit-20260901-x86_64.iso",
    f"{_A}/iso/artix-base-runit-20260101-x86_64.iso",
)
ARTIX_SUM = "ae" * 32
# One list for the directory; the .sig beside each image is listed too.
ARTIX_SUMS = (f"{'0f' * 32}  artix-plasma-openrc-20260407-x86_64.iso\n"
              f"{ARTIX_SUM}  artix-plasma-openrc-20260813-x86_64.iso\n"
              f"{'1e' * 32}  artix-plasma-openrc-20260813-x86_64.iso.sig\n")

# ------------------------------------------------------------------ Sparky

SPARKY_STABLE = SparkyRecipe.STABLE_PAGE
SPARKY_ROLLING = SparkyRecipe.ROLLING_PAGE
_IA, _SF = "https://archive.org/download/sparkylinux", "https://sourceforge.net/projects/sparkylinux/files"

SPARKY_STABLE_LINKS = (
    f"{_IA}/sparkylinux-8.9-x86_64-xfce.iso",
    f"{_SF}/xfce/sparkylinux-8.9-x86_64-xfce.iso/download",
    f"{_IA}/sparkylinux-8.10-x86_64-xfce.iso",
    f"{_SF}/xfce/sparkylinux-8.10-x86_64-xfce.iso.sig/download",
    f"{_SF}/xfce/sparkylinux-8.10-x86_64-xfce.iso/download",
    f"{_SF}/torrents/sparkylinux-8.10-x86_64-xfce.iso.torrent/download",
    f"{_IA}/sparkylinux-7.8-x86_64-xfce.iso",
    # The rolling line's image, linked from the stable page: numbered above
    # every stable release, and not one.
    "https://archive.org/download/sparkylinux-testing/sparkylinux-2026.09-x86_64-xfce.iso",
    f"{_IA}/sparkylinux-8.10-x86_64-kde.iso",
)

SPARKY_ROLLING_LINKS = (
    f"{_IA}-testing/sparkylinux-2026.06-x86_64-minimalgui.iso",
    f"{_IA}-testing/sparkylinux-2026.09-x86_64-minimalgui.iso",
    # Another desktop on the same base; its name only starts like this one's.
    f"{_IA}-testing/sparkylinux-2026.12-x86_64-minimalgui-labwc.iso",
    f"{_IA}-testing/sparkylinux-2025.12-x86_64-minimalgui.iso",
    f"{_IA}/sparkylinux-8.10-x86_64-minimalgui.iso",
    # Special editions: SourceForge only, a quarter behind the base images.
    f"{_SF}/gameover/sparkylinux-2026.03-x86_64-gameover.iso/download",
    f"{_SF}/gameover/sparkylinux-2026.06-x86_64-gameover.iso/download",
    f"{_SF}/gameover/sparkylinux-2026.06-x86_64-gameover.iso.sig/download",
    f"{_SF}/gameover/sparkylinux-2025.12-x86_64-gameover.iso/download",
    f"{_SF}/torrents/sparkylinux-2026.09-x86_64-gameover.iso.torrent",
)

# ------------------------------------------------------------------- Tails

TAILS = "https://tails.net/install/download/"
_T = "https://download.tails.net/tails"


def _tails(*versions, extra=()):
    return _links(*[f"{_T}/stable/tails-amd64-{v}/tails-amd64-{v}.iso" for v in versions], *extra)


TAILS_LATEST = "https://tails.net/install/v2/Tails/amd64/stable/latest.json"
TAILS_SHA = "a49ab6a8" + "0" * 56


def _tails_latest(version, sha=TAILS_SHA):
    """latest.json as Tails publishes it: each image of one release, with its hash."""
    base = f"{_T}/stable/tails-amd64-{version}/tails-amd64-{version}"
    return json.dumps({"installations": [{"version": version, "installation-paths": [
        {"type": "img", "target-files": [{"url": base + ".img", "sha256": "1" * 64}]},
        {"type": "iso", "target-files": [{"url": base + ".iso", "sha256": sha}]}]}]})


TAILS_PAGE = _tails("7.9", "7.14", "7.10", extra=(
    f"{_T}/stable/tails-amd64-7.14/tails-amd64-7.14.img",
    f"{_T}/alpha/tails-amd64-8.0~rc1/tails-amd64-8.0~rc1.iso",
))

# ------------------------------------------------------------------ FydeOS

FYDEOS = "https://fydeos.io/download/pc/intel-iris/"
_F = "https://download.fydeos.io"

FYDEOS_LINKS = (
    f"{_F}/v22.1/FydeOS_for_PC_iris_v22.1-io.bin.zip",
    f"{_F}/v23.0-SP1/FydeOS_for_PC_iris_v23.0-SP1-io.bin.zip",
    f"{_F}/v24.0-beta/FydeOS_for_PC_iris_v24.0-beta-io.bin.zip",
    f"{_F}/latest/FydeOS_for_PC_iris.zip",
    f"{_F}/v23.0/FydeOS_for_PC_iris_v23.0-io.bin.zip",
    f"{_F}/v9.2/FydeOS_for_PC_iris_v9.2-io.bin.zip",
)

# ---------------------------------------------------------------- HackerOS

HACKEROS_GAMING = "https://sourceforge.net/projects/hackeros/rss?path=/GAMING"
HACKEROS_OFFICIAL = "https://sourceforge.net/projects/hackeros/rss?path=/OFFICIAL"

HACKEROS_GAMING_PATHS = (
    "/GAMING/HackerOS-V4.7-Gaming.iso",
    "/GAMING/HackerOS-V4.10-Gaming.iso",
    "/GAMING/DEV/HackerOS-V5.1-Gaming.iso",
    "/GAMING/HackerOS-v4.8-Gaming.iso",
    "/GAMING/README.md",
    "/GAMING/HackerOS-V4.9-Gaming.iso",
)

HACKEROS_OFFICIAL_PATHS = (
    "/OFFICIAL/HackerOS-V4.9.iso",
    "/OFFICIAL/GNOME/HackerOS-V5.1-Gnome.iso",
    "/OFFICIAL/HackerOS-V5.0.iso",
    "/OFFICIAL/ARCHIVED/HackerOS-V.0.9.iso",
    "/OFFICIAL/HackerOS-V4.8.iso",
)

# As SourceForge listed them on 2026-10-06: 5.0 is out for Official and LTS;
# Cybersecurity is at 4.9 and Gaming, on its x.3/x.7 schedule, at 4.7.
HACKEROS_TODAY = {
    HACKEROS_OFFICIAL: _rss(*HACKEROS_OFFICIAL_PATHS),
    HACKEROS_GAMING: _rss("/GAMING/HackerOS-V4.7-Gaming.iso"),
    "https://sourceforge.net/projects/hackeros/rss?path=/LTS": _rss(
        "/LTS/HackerOS-V5.0-LTS.iso", "/LTS/HackerOS-V4.1-LTS.iso"),
    "https://sourceforge.net/projects/hackeros/rss?path=/CYBERSECURITY": _rss(
        "/CYBERSECURITY/HackerOS-V4.9-Cybersecurity.iso", "/CYBERSECURITY/HackerOS-V4.8-Cybersecurity.iso",
        "/CYBERSECURITY/HackerOS-V4.7-Cybersecurity.iso"),
}

# --------------------------------------------------------------- AlmaLinux

ALMA = AlmaLinuxRecipe.ROOT
ALMA_10 = f"{ALMA}10/isos/x86_64/"
ALMA_9 = f"{ALMA}9/isos/x86_64/"


def _dirs(*names):
    return "<html><body><pre>" + "".join(f'<a href="{n}/">{n}/</a>\n' for n in names) + "</pre></body></html>"


ALMA_ROOT_PAGE = _dirs("8", "9", "9.6", "10", "10.10", "11-beta", "8.10")
ALMA_10_LINKS = (
    "AlmaLinux-10.9-x86_64-minimal.iso",
    "AlmaLinux-10.10-x86_64-minimal.iso",
    "AlmaLinux-10.11-beta-1-x86_64-minimal.iso",
    "AlmaLinux-10-latest-x86_64-minimal.iso",
    "AlmaLinux-10.10-x86_64-dvd.iso",
    "AlmaLinux-10.2-x86_64-minimal.iso",
)
ALMA_9_PAGE = _links("AlmaLinux-9.6-x86_64-minimal.iso", "AlmaLinux-9-latest-x86_64-minimal.iso")


CASES = {
    "artix": [
        Case(pages={ARTIX: _links(*ARTIX_LINKS), ARTIX + "sha256sums": ARTIX_SUMS}, flavor="plasma-openrc",
             newest="20260813", filename="artix-plasma-openrc-20260813-x86_64.iso", newest_urls=(ARTIX,),
             extra={"sha256": ARTIX_SUM,
                    "newer": ({ARTIX: _links(*ARTIX_LINKS, f"{_A}/iso/artix-plasma-openrc-20261105-x86_64.iso")}, "20261105")}),
    ],
    "sparky": [
        Case(pages={SPARKY_STABLE: _links(*SPARKY_STABLE_LINKS)}, flavor="xfce", newest="8.10",
             filename="sparkylinux-8.10-x86_64-xfce.iso", newest_urls=(SPARKY_STABLE,),
             extra={"newer": ({SPARKY_STABLE: _links(*SPARKY_STABLE_LINKS, f"{_SF}/xfce/sparkylinux-9.0-x86_64-xfce.iso/download")}, "9.0")}),
        Case(pages={SPARKY_ROLLING: _links(*SPARKY_ROLLING_LINKS)}, flavor="rolling-minimalgui", newest="2026.09",
             filename="sparkylinux-2026.09-x86_64-minimalgui.iso", newest_urls=(SPARKY_ROLLING,)),
        Case(pages={SPARKY_ROLLING: _links(*SPARKY_ROLLING_LINKS)}, flavor="rolling-gameover", newest="2026.06",
             filename="sparkylinux-2026.06-x86_64-gameover.iso", newest_urls=(SPARKY_ROLLING,),
             extra={"newer": ({SPARKY_ROLLING: _links(*SPARKY_ROLLING_LINKS, f"{_SF}/gameover/sparkylinux-2026.09-x86_64-gameover.iso/download")}, "2026.09")}),
    ],
    "tails": [
        Case(pages={TAILS: TAILS_PAGE, TAILS_LATEST: _tails_latest("7.14")},
             flavor="standard", newest="7.14",
             filename="tails-amd64-7.14.iso", newest_urls=(TAILS,),
             extra={"newer": ({TAILS: _tails("7.9", "7.14", "7.10", "7.15")}, "7.15"),
                    "pre_only": ({TAILS: _tails("7.13", extra=(
                        f"{_T}/alpha/tails-amd64-8.0~rc1/tails-amd64-8.0~rc1.iso",))}, "7.13")}),
    ],
    "fydeos": [
        Case(pages={FYDEOS: _links(*FYDEOS_LINKS)}, flavor="iris", newest="23.0-SP1",
             filename="FydeOS_for_PC_iris_v23.0-SP1-io.bin.zip", newest_urls=(FYDEOS,),
             extra={"newer": ({FYDEOS: _links(*FYDEOS_LINKS, f"{_F}/v23.1/FydeOS_for_PC_iris_v23.1-io.bin.zip")}, "23.1"),
                    "pre_only": ({FYDEOS: _links(
                        f"{_F}/v23.0/FydeOS_for_PC_iris_v23.0-io.bin.zip",
                        f"{_F}/v24.0-beta/FydeOS_for_PC_iris_v24.0-beta-io.bin.zip")}, "23.0")}),
    ],
    "hackeros": [
        Case(pages={HACKEROS_GAMING: _rss(*HACKEROS_GAMING_PATHS)},
             flavor="gaming", newest="4.10", filename="HackerOS-V4.10-Gaming.iso",
             newest_urls=(HACKEROS_GAMING,),
             extra={"newer": ({HACKEROS_GAMING: _rss(*HACKEROS_GAMING_PATHS, "/GAMING/HackerOS-v5.0-Gaming.iso")}, "5.0")}),
        Case(pages={HACKEROS_OFFICIAL: HACKEROS_TODAY[HACKEROS_OFFICIAL]},
             flavor="official", newest="5.0", filename="HackerOS-V5.0.iso",
             newest_urls=(HACKEROS_OFFICIAL,)),
    ],
    "almalinux": [
        Case(pages={ALMA: ALMA_ROOT_PAGE, ALMA_10: _links(*ALMA_10_LINKS), ALMA_9: ALMA_9_PAGE},
             flavor="minimal", newest="10.10", filename="AlmaLinux-10.10-x86_64-minimal.iso",
             newest_urls=(ALMA, ALMA_10),
             extra={"newer": ({ALMA_10: _links(*ALMA_10_LINKS, "AlmaLinux-10.11-x86_64-minimal.iso")}, "10.11")}),
    ],
}

EXEMPT = {}

RECIPES = {cls.key: cls for cls in (
    ArtixRecipe, SparkyRecipe, TailsRecipe, FydeOSRecipe, HackerOSRecipe, AlmaLinuxRecipe)}


def _cases():
    for key, cases in CASES.items():
        for i, case in enumerate(cases if isinstance(cases, list) else [cases]):
            yield pytest.param(key, case, id=f"{key}-{case.flavor}-{i}")


@pytest.mark.parametrize("key,case", list(_cases()))
def test_reports_the_newest_release_in_any_page_order(monkeypatch, key, case):
    assert_newest(monkeypatch, RECIPES[key], case)


@pytest.mark.parametrize("key,case", list(_cases()))
def test_refuses_rather_than_falling_back(monkeypatch, key, case):
    assert_no_fallback(monkeypatch, RECIPES[key], case)


@pytest.mark.parametrize("key,case", [p for p in _cases() if p.values[1].extra.get("newer")])
def test_a_newer_release_is_reported_once_it_appears(monkeypatch, key, case):
    patch, version = case.extra["newer"]
    recipe, _ = use(monkeypatch, RECIPES[key](), {**case.pages, **patch})
    assert recipe.fetch_download_info(case.flavor).version == version


@pytest.mark.parametrize("key,case", [p for p in _cases() if p.values[1].extra.get("pre_only")])
def test_a_pre_release_alone_above_the_final_is_not_taken(monkeypatch, key, case):
    patch, version = case.extra["pre_only"]
    recipe, _ = use(monkeypatch, RECIPES[key](), {**case.pages, **patch})
    assert recipe.fetch_download_info(case.flavor).version == version


@pytest.mark.parametrize("key,case", [p for p in _cases() if p.values[1].extra.get("sha256")])
def test_the_published_checksum_comes_with_it(monkeypatch, key, case):
    recipe, _ = use(monkeypatch, RECIPES[key](), case.pages)
    assert recipe.fetch_download_info(case.flavor).sha256 == case.extra["sha256"]


@pytest.mark.parametrize("key,case", [p for p in _cases() if p.values[1].filename
                                      and not p.values[1].filename.endswith(".zip")])
def test_iso_identity_reads_the_filename_back(key, case):
    found = identify(case.filename)
    assert found is not None, case.filename
    assert (found.key, found.flavor_id, found.version) == (key, case.flavor, case.newest)


# ------------------------------------------------------------- refusals

def test_fydeos_refuses_a_page_that_links_only_an_unversioned_image(monkeypatch):
    """It used to report "Latest", a label no later check can compare."""
    recipe, _ = use(monkeypatch, FydeOSRecipe(), {FYDEOS: _links(f"{_F}/latest/FydeOS_for_PC_iris.zip")})
    with pytest.raises(ScrapeError):
        recipe.fetch_download_info("iris")


def test_hackeros_refuses_an_image_whose_name_it_cannot_read(monkeypatch):
    """A renamed newer build skipped would leave 4.10 reported as current."""
    feed = _rss(*HACKEROS_GAMING_PATHS, "/GAMING/HackerOS-V5.0-Gaming-Edition.iso")
    recipe, _ = use(monkeypatch, HackerOSRecipe(), {HACKEROS_GAMING: feed})
    with pytest.raises(ScrapeError) as err:
        recipe.fetch_download_info("gaming")
    assert "Gaming-Edition" in err.value.reason


@pytest.mark.parametrize("flavor,version", [
    ("official", "5.0"), ("lts", "5.0"), ("cybersecurity", "4.9"), ("gaming", "4.7")])
def test_hackeros_editions_keep_their_own_schedules(monkeypatch, flavor, version):
    """Gaming ships with x.3 and x.7 and Cybersecurity follows Debian Stable:
    each edition's newest build is its current one, not a lapsed release,
    and its next build is offered as an update when it lands."""
    recipe, session = use(monkeypatch, HackerOSRecipe(), HACKEROS_TODAY)
    assert recipe.fetch_download_info(flavor).version == version
    assert not session.missing


def test_hackeros_no_longer_offers_the_frozen_nvidia_edition(monkeypatch):
    assert "nvidia" not in {f.id for f in HackerOSRecipe().get_flavors()}
    recipe, _ = use(monkeypatch, HackerOSRecipe(), HACKEROS_TODAY)
    with pytest.raises(ScrapeError):
        recipe.fetch_download_info("nvidia")


@pytest.mark.parametrize("key,url,flavor", [
    ("tails", TAILS, "standard"), ("fydeos", FYDEOS, "iris"), ("artix", ARTIX, "plasma-openrc")])
def test_a_refused_page_is_named_not_called_empty(monkeypatch, key, url, flavor):
    recipe, _ = use(monkeypatch, RECIPES[key](), {url: Resp("Just a moment...", 403)})
    with pytest.raises(ScrapeError) as err:
        recipe.fetch_download_info(flavor)
    assert "403" in err.value.reason


def test_tails_supplies_the_hash_published_for_that_very_image(monkeypatch):
    recipe, _ = use(monkeypatch, TailsRecipe(), {TAILS: TAILS_PAGE, TAILS_LATEST: _tails_latest("7.14")})
    assert recipe.fetch_download_info("standard").sha256 == TAILS_SHA


def test_tails_never_checks_an_image_against_another_releases_hash(monkeypatch):
    """latest.json already on 7.15 while the page still links 7.14: no hash,
    rather than one that would fail the good 7.14 download."""
    recipe, _ = use(monkeypatch, TailsRecipe(), {TAILS: TAILS_PAGE, TAILS_LATEST: _tails_latest("7.15")})
    info = recipe.fetch_download_info("standard")
    assert (info.version, info.sha256) == ("7.14", "")


@pytest.mark.parametrize("failure", [TimeoutError("timed out"), Resp("", 503), Resp("not json")])
def test_tails_without_its_latest_json_still_resolves(monkeypatch, failure):
    recipe, _ = use(monkeypatch, TailsRecipe(), {TAILS: TAILS_PAGE, TAILS_LATEST: failure})
    info = recipe.fetch_download_info("standard")
    assert (info.version, info.sha256) == ("7.14", "")
