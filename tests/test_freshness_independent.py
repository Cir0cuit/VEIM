"""Freshness Cases for the independent and lightweight distributions.

Void, Slackware, Puppy, Tiny Core and Alpine, read from captured shapes of
what each project publishes. See tests/freshness.py for what a Case must hold.
"""
import pytest

from src.core.iso_identity import identify
from src.core.recipe_base import ScrapeError
from src.recipes.independent import SlackwareRecipe, VoidRecipe
from src.recipes.lightweight import AlpineRecipe, PuppyRecipe, TinyCoreRecipe
from tests.freshness import Case, Resp, assert_newest, assert_no_fallback, use


def _listing(*names):
    return "<html><body>" + "".join(f'<a href="{n}">{n}</a>' for n in names) + "</body></html>"


def _rss(folder, *names):
    return "<rss><channel>" + "".join(
        f"<item><title><![CDATA[/{folder}/{n}]]></title></item>" for n in names) + "</channel></rss>"


# ---------------------------------------------------------------------- Void

VOID = "https://repo-default.voidlinux.org/live/current/"
# Dates are all eight digits, so text and number order agree: no trap to set.
# The enterprise image stands in for something dated above the release.
VOID_PAGES = {VOID: _listing(
    "../", "sha256sum.txt",
    "void-live-x86_64-20240314-base.iso", "void-live-x86_64-20240314-xfce.iso",
    "void-live-x86_64-20250202-base.iso", "void-live-x86_64-20250202-xfce.iso",
    "void-live-x86_64-20250401-enterprise.iso",
    "void-live-x86_64-musl-20240314-base.iso", "void-live-x86_64-musl-20250202-base.iso",
    "void-live-x86_64-musl-20250202-xfce.iso", "void-live-x86_64-musl-20240314-xfce.iso",
    "void-live-aarch64-20250202-base.iso", "void-x86_64-ROOTFS-20250202.tar.xz")}


def _void(flavor, fname):
    return Case(pages=VOID_PAGES, flavor=flavor, newest="20250202", filename=fname,
                newest_urls=(VOID,))


# ----------------------------------------------------------------- Slackware

SLACK = "https://mirrors.slackware.com/slackware/slackware-iso/"
SLACK_PAGES = {
    SLACK: _listing("/slackware/", "slackware-14.2-iso/", "slackware-15.0-iso/",
                    "slackware64-13.1-iso/", "slackware64-13.37-iso/", "slackware64-14.2-iso/",
                    "slackware64-15.0-iso/", "slackware64-14.0-iso/", "slackware64-14.1-iso/"),
    SLACK + "slackware64-15.0-iso/": _listing(
        "/slackware/slackware-iso/", "slackware64-15.0-install-dvd.iso",
        "slackware64-15.0-install-dvd.iso.asc", "slackware64-15.0-install-dvd.iso.md5"),
    SLACK + "slackware64-14.2-iso/": _listing("slackware64-14.2-install-dvd.iso"),
}
# Slackware numbers no pre-releases (they live in -current, which has no ISO
# folder); a 15.10 beside 15.9 is the text-order trap its numbering allows.
SLACK_FUTURE = {
    SLACK: _listing("slackware64-15.9-iso/", "slackware64-15.10-iso/", "slackware64-15.0-iso/"),
    SLACK + "slackware64-15.10-iso/": _listing("slackware64-15.10-install-dvd.iso"),
    SLACK + "slackware64-15.9-iso/": _listing("slackware64-15.9-install-dvd.iso"),
    SLACK + "slackware64-15.0-iso/": _listing("slackware64-15.0-install-dvd.iso"),
}


# --------------------------------------------------------------------- Puppy

PUP = "https://distro.ibiblio.org/puppylinux/"
BOOKWORM = PUP + "puppy-bookwormpup/BookwormPup64/"
FOSSA = PUP + "puppy-fossa/"
TRIXIE = "https://sourceforge.net/projects/pb-gh-releases/rss?path=/TrixiePup64Wayland_release"

PUPPY_PAGES = {
    # 10.0.9 above 10.0.12 is what sorting the folders as text picks.
    BOOKWORM: _listing("../", "10.0.10/", "10.0.12/", "10.0.8/", "10.0.9/", "10.1-rc1/",
                       "build_files/", "BookwormPup64.htm"),
    BOOKWORM + "10.0.12/": _listing(
        "../", "BookwormPup64_10.0.12.iso", "BookwormPup64_10.0.12.iso-checksum.txt",
        "devx_BookwormPup64_10.0.12.sfs", "devx_BookwormPup64_10.0.13.iso"),
    BOOKWORM + "10.0.10/": _listing("BookwormPup64_10.0.10.iso"),
    BOOKWORM + "10.0.9/": _listing("BookwormPup64_10.0.9.iso"),
    BOOKWORM + "10.1-rc1/": _listing("BookwormPup64_10.1-rc1.iso"),
    FOSSA: _listing("../", "fossapup64-9.0.iso", "fossapup64-9.5.iso", "fossapup64-9.6rc1.iso",
                    "devx_fossapup64_9.5.sfs", "fossapup64-9.5.iso.md5.txt", "fossapup64-9.5.iso.sha256.txt"),
    # Each image's own checksum file, each named its own way.
    BOOKWORM + "10.0.12/BookwormPup64_10.0.12.iso-checksum.txt": f"{'b0' * 32}  BookwormPup64_10.0.12.iso",
    FOSSA + "fossapup64-9.5.iso.sha256.txt": f"{'f0' * 32}  fossapup64-9.5.iso",
    # Series and build date are fixed width, so text and number order agree.
    TRIXIE: _rss("TrixiePup64Wayland_release",
                 "nlsx_dpupt64w_2606.sfs", "SHA512checksums.txt",
                 "TrixiePup64-Wayland-2606-260801.iso", "TrixiePup64-Wayland-2606-261003.iso",
                 "TrixiePup64-Wayland-ghtest-2612-261101.iso", "TrixiePup64-Wayland-2601-260502.iso",
                 "TrixiePup64-Wayland-2606-260901.iso", "README.txt"),
}


# ----------------------------------------------------------------- Tiny Core

TC = "http://tinycorelinux.net/"
TC_X86 = TC + "17.x/x86/release/"
TC_X64 = TC + "17.x/x86_64/release/"
TC_PAGES = {
    # 9 above 17 is what sorting the series as text picks.
    TC + "downloads.html": _listing(
        "9.x/x86/release/Core-current.iso", "16.x/x86/release/CorePlus-16.2.iso",
        "17.x/x86/release/Core-current.iso", "17.x/x86_64/release/CorePure64-current.iso",
        "17.x/x86/release/CorePlus-current.iso"),
    TC_X86: _listing(
        "../", "distribution_files/", "Core-17.0.iso", "Core-17.1.iso", "Core-current.iso",
        "CorePlus-17.0.iso", "CorePlus-17.1.iso", "CorePlus-17.1.iso.md5.txt", "CorePlus-17.2rc1.iso",
        "CorePlus-current.iso", "TinyCore-17.0.iso", "TinyCore-17.1.iso", "TinyCore-current.iso"),
    # "CorePure64-" is the tail of "TinyCorePure64-", which is numbered higher
    # here to show a mix-up; 17.9 and 17.10 are the text-order trap.
    TC_X64: _listing(
        "../", "TinyCorePure64-17.9.iso", "CorePure64-17.0.iso", "TinyCorePure64-17.10.iso",
        "CorePure64-17.1.iso", "CorePure64-current.iso", "TinyCorePure64-17.11rc1.iso",
        "TinyCorePure64-current.iso"),
    TC + "16.x/x86/release/": _listing("CorePlus-16.2.iso", "Core-16.2.iso", "TinyCore-16.2.iso"),
    TC + "9.x/x86/release/": _listing("Core-9.0.iso"),
}


def _tc(flavor, version, fname):
    return Case(pages=TC_PAGES, flavor=flavor, newest=version, filename=fname,
                newest_urls=(TC + "downloads.html", TC_X64 if "64" in flavor else TC_X86))


# -------------------------------------------------------------------- Alpine

ALPINE = "https://alpinelinux.org/downloads/"
CDN = "https://dl-cdn.alpinelinux.org/alpine/"
STD = CDN + "v3.24/releases/x86_64/alpine-standard-3.24.2-x86_64.iso"
STD_SUM = "20c026e3a788bfb75fc8b50a54bcc12aee85e3c75909740bba6a6f4563d63296"
ALPINE_PAGES = {
    # 3.9.6 above 3.24.2 is what sorting as text picks; the rc is above both.
    # The page encodes its slashes, as alpinelinux.org does.
    ALPINE: _listing(*(u.replace("/", "&#x2F;") for u in (
        CDN + "v3.9/releases/x86_64/alpine-standard-3.9.6-x86_64.iso",
        STD, STD + ".sha256", STD + ".asc",
        CDN + "v3.25/releases/x86_64/alpine-standard-3.25.0_rc1-x86_64.iso",
        CDN + "v3.24/releases/x86_64/alpine-extended-3.24.2-x86_64.iso",
        CDN + "v3.23/releases/x86_64/alpine-standard-3.23.4-x86_64.iso",
        CDN + "v3.24/releases/x86_64/alpine-netboot-3.24.2-x86_64.tar.gz"))),
    STD + ".sha256": f"{STD_SUM}  alpine-standard-3.24.2-x86_64.iso\n",
}


CASES = {
    "void": [
        _void("base", "void-live-x86_64-20250202-base.iso"),
        _void("xfce", "void-live-x86_64-20250202-xfce.iso"),
        _void("musl-base", "void-live-x86_64-musl-20250202-base.iso"),
        _void("musl-xfce", "void-live-x86_64-musl-20250202-xfce.iso"),
    ],
    "slackware": [
        Case(pages=SLACK_PAGES, flavor="install-dvd", newest="15.0",
             filename="slackware64-15.0-install-dvd.iso",
             newest_urls=(SLACK, SLACK + "slackware64-15.0-iso/")),
        Case(pages=SLACK_FUTURE, flavor="install-dvd", newest="15.10",
             filename="slackware64-15.10-install-dvd.iso",
             newest_urls=(SLACK, SLACK + "slackware64-15.10-iso/")),
    ],
    "puppy": [
        Case(pages=PUPPY_PAGES, flavor="bookworm", newest="10.0.12",
             filename="BookwormPup64_10.0.12.iso", newest_urls=(BOOKWORM, BOOKWORM + "10.0.12/")),
        Case(pages=PUPPY_PAGES, flavor="fossa", newest="9.5",
             filename="fossapup64-9.5.iso", newest_urls=(FOSSA,)),
        Case(pages=PUPPY_PAGES, flavor="trixie", newest="2606-261003",
             filename="TrixiePup64-Wayland-2606-261003.iso", newest_urls=(TRIXIE,)),
    ],
    "tinycore": [
        _tc("coreplus", "17.1", "CorePlus-17.1.iso"),
        _tc("tinycore", "17.1", "TinyCore-17.1.iso"),
        _tc("core", "17.1", "Core-17.1.iso"),
        _tc("corepure64", "17.1", "CorePure64-17.1.iso"),
        _tc("tinycorepure64", "17.10", "TinyCorePure64-17.10.iso"),
    ],
    "alpine": [
        Case(pages=ALPINE_PAGES, flavor="standard", newest="3.24.2",
             filename="alpine-standard-3.24.2-x86_64.iso", newest_urls=(ALPINE,)),
    ],
}

EXEMPT = {
    "gentoo": "reads the latest-*.txt file Gentoo signs and publishes for each image, "
              "which names the one current build",
}

RECIPES = {cls.key: cls for cls in (VoidRecipe, SlackwareRecipe, PuppyRecipe, TinyCoreRecipe,
                                     AlpineRecipe)}


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


@pytest.mark.parametrize("key,case", [p for p in _cases() if p.values[1].filename])
def test_iso_identity_reads_the_filename_back(key, case):
    found = identify(case.filename)
    assert found and (found.key, found.flavor_id, found.version) == (key, case.flavor, case.newest)


# A release published after the fixture was captured: (key, flavor, pages, version).
NEWER = [
    ("void", "base", {VOID: VOID_PAGES[VOID].replace("</body>", (
        '<a href="void-live-x86_64-20261001-base.iso">x</a></body>'))}, "20261001"),
    ("slackware", "install-dvd", {
        SLACK: SLACK_PAGES[SLACK].replace("</body>", '<a href="slackware64-15.1-iso/">x</a></body>'),
        SLACK + "slackware64-15.1-iso/": _listing("slackware64-15.1-install-dvd.iso")}, "15.1"),
    ("puppy", "bookworm", {
        BOOKWORM: _listing("10.0.12/", "10.1/"),
        BOOKWORM + "10.1/": _listing("BookwormPup64_10.1.iso"),
        BOOKWORM + "10.1/BookwormPup64_10.1.iso-checksum.txt": Resp("", 404)}, "10.1"),
    ("puppy", "trixie", {TRIXIE: PUPPY_PAGES[TRIXIE].replace(
        "</channel>", "<item><title><![CDATA[/TrixiePup64Wayland_release/"
                      "TrixiePup64-Wayland-2612-261201.iso]]></title></item></channel>")},
     "2612-261201"),
    ("tinycore", "coreplus", {
        TC + "downloads.html": _listing("18.x/x86/release/CorePlus-current.iso"),
        TC + "18.x/x86/release/": _listing("CorePlus-18.0.iso", "CorePlus-current.iso")}, "18.0"),
    ("alpine", "standard", {
        ALPINE: ALPINE_PAGES[ALPINE].replace("</body>", (
            f'<a href="{CDN}v3.25/releases/x86_64/alpine-standard-3.25.0-x86_64.iso">x</a></body>')),
        CDN + "v3.25/releases/x86_64/alpine-standard-3.25.0-x86_64.iso.sha256": Resp("", 404)},
     "3.25.0"),
]
_BASE_PAGES = {"void": VOID_PAGES, "slackware": SLACK_PAGES, "puppy": PUPPY_PAGES,
               "tinycore": TC_PAGES, "alpine": ALPINE_PAGES}


@pytest.mark.parametrize("key,flavor,pages,version", NEWER, ids=[f"{n[0]}-{n[1]}" for n in NEWER])
def test_picks_up_a_release_published_later(monkeypatch, key, flavor, pages, version):
    recipe, _ = use(monkeypatch, RECIPES[key](), {**_BASE_PAGES[key], **pages})
    assert recipe.fetch_download_info(flavor).version == version


def test_slackware_refuses_while_the_newest_dvd_is_not_up(monkeypatch):
    """The folder can be there before the image; 14.2 is not the answer then."""
    recipe, _ = use(monkeypatch, SlackwareRecipe(), {
        **SLACK_PAGES, SLACK + "slackware64-15.0-iso/": _listing("slackware64-15.0-install-dvd.iso.md5")})
    with pytest.raises(ScrapeError):
        recipe.fetch_download_info("install-dvd")


@pytest.mark.parametrize("flavor,sha256", [("bookworm", "b0" * 32), ("fossa", "f0" * 32), ("trixie", "")])
def test_puppy_supplies_the_published_checksum(monkeypatch, flavor, sha256):
    """TrixiePup64 publishes SHA-512 only, which is not one."""
    recipe, _ = use(monkeypatch, PuppyRecipe(), PUPPY_PAGES)
    assert recipe.fetch_download_info(flavor).sha256 == sha256


def test_alpine_supplies_the_published_checksum(monkeypatch):
    recipe, _ = use(monkeypatch, AlpineRecipe(), ALPINE_PAGES)
    info = recipe.fetch_download_info("standard")
    assert (info.url, info.sha256) == (STD, STD_SUM)


def test_alpine_refuses_a_page_with_only_a_release_candidate(monkeypatch):
    """It used to report the label "Latest" for a version it could not read."""
    recipe, _ = use(monkeypatch, AlpineRecipe(), {ALPINE: _listing(
        CDN + "v3.25/releases/x86_64/alpine-standard-3.25.0_rc1-x86_64.iso")})
    with pytest.raises(ScrapeError):
        recipe.fetch_download_info("standard")
