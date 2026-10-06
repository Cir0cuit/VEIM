"""Freshness Cases for the community and modern desktops (community_desktop.py,
modern_desktop.py). See tests/freshness.py for what each Case has to hold."""
import json
from datetime import date

import pytest

from src.core.iso_identity import identify
from src.recipes.community_desktop import (
    ElementaryRecipe, MageiaRecipe, NixOSRecipe, OpenSUSERecipe, TuxedoRecipe)
from src.recipes.modern_desktop import KDENeonRecipe, LinuxLiteRecipe, PopOSRecipe, ZorinRecipe
from src.core.recipe_base import ScrapeError
from tests.freshness import Case, Resp, assert_newest, assert_no_fallback, use


def _links(*hrefs):
    return "<html><body>" + "".join(f'<a href="{h}">{h.split("/")[-1]}</a>' for h in hrefs) + "</body></html>"


def _jsontable(*names):
    return json.dumps({"data": [{"name": n} for n in names]})


def _rss(*paths):
    return "<rss><channel>" + "".join(
        f"<item><title><![CDATA[{p}]]></title></item>" for p in paths) + "</channel></rss>"


# ----------------------------------------------------------------- openSUSE

SUSE = "https://download.opensuse.org/"
TW = SUSE + "tumbleweed/iso/?jsontable"
LEAP_PAGE = "https://get.opensuse.org/leap/"
LEAP16 = SUSE + "distribution/leap/16.0/offline/?jsontable"
SUSE_PAGES = {
    TW: _jsontable(
        "openSUSE-Tumbleweed-DVD-x86_64-Current.iso",
        "openSUSE-Tumbleweed-DVD-x86_64-Snapshot20260912-Media.iso",
        "openSUSE-Tumbleweed-DVD-x86_64-Snapshot20261003-Media.iso",
        "openSUSE-Tumbleweed-DVD-x86_64-Snapshot20261003-Media.iso.sha256",
        "openSUSE-MicroOS-DVD-x86_64-Snapshot20261005-Media.iso",
        "openSUSE-Tumbleweed-KDE-Live-x86_64-Snapshot20261001-Media.iso",
        "openSUSE-Tumbleweed-KDE-Live-x86_64-Snapshot20261003-Media.iso",
        "openSUSE-Tumbleweed-KDE-Live-x86_64-Current.iso",
        "openSUSE-Tumbleweed-DVD-x86_64-Snapshot20260919-Media.iso"),
    # A redirect to the current release; 16.1 is linked, and linked more
    # often, while it is a release candidate.
    LEAP_PAGE: ('<meta http-equiv="refresh" content="0; url=/leap/16.0/" />'
                + _links("/leap/16.1/", "/leap/16.0/", "/leap/16.1/#rc", "/leap/15.6/")),
    LEAP16: _jsontable(
        "Leap-16.0-offline-installer-x86_64-Build178.9.install.iso",
        "Leap-16.0-offline-installer-x86_64-Build178.27.install.iso",
        "Leap-16.0-offline-installer-x86_64.install.iso",
        "Leap-16.0-offline-installer-x86_64-Build178.3.install.iso",
        "Leap-16.0-online-installer-x86_64-Build178.9.install.iso",
        "Leap-16.0-online-installer-x86_64-Build178.27.install.iso",
        "Leap-16.0-online-installer-x86_64-Build178.10.install.iso"),
    SUSE + "distribution/leap/16.1/offline/?jsontable": _jsontable(
        "Leap-16.1-offline-installer-x86_64-Build53.1.install.iso"),
    SUSE + "distribution/leap/15.6/iso/?jsontable": _jsontable("openSUSE-Leap-15.6-DVD-x86_64-Current.iso"),
}

SUM = "5e" * 32

# ---------------------------------------------------------------- NixOS

NIX = "https://channels.nixos.org/nixos-{}/latest-nixos-{}-x86_64-linux.iso"
NIX_REAL = "https://releases.nixos.org/nixos/{c}/nixos-{v}.{h}/nixos-{f}-{v}.{h}-x86_64-linux.iso"


def _nix(flavor):
    def real(channel, version, h="6d663c0533ff"):
        return Resp(url=NIX_REAL.format(c=channel, v=version, h=h, f=flavor))
    return {
        # Branched off, not released: the channel serves betas.
        NIX.format("26.11", flavor): real("26.11", "26.11beta186", "2fecba995209"),
        NIX.format("26.05", flavor): real("26.05", "26.05.11275"),
        NIX.format("25.11", flavor): real("25.11", "25.11.9001"),
        NIX.format("25.05", flavor): real("25.05", "25.05.8002"),
        **_nix_sum("26.05", "26.05.11275.6d663c0533ff", flavor),
    }


def _nix_sum(channel, build, flavor):
    """The .sha256 beside the build "latest-..." redirects to."""
    name = f"nixos-{flavor}-{build}-x86_64-linux.iso"
    url = f"https://releases.nixos.org/nixos/{channel}/nixos-{build}/{name}.sha256"
    return {url: f"{SUM}  {name}\n"}


_CHANNELS = NixOSRecipe._candidate_channels
# The channels are worked out from today's date; pin it to late November,
# when a beta channel exists, so the Case does not change with the calendar.
NIX_PATCH = {"_candidate_channels": staticmethod(lambda today=None: _CHANNELS(date(2026, 11, 20)))}

# ------------------------------------------------------------ elementary OS

ELEM = "https://elementary.io/"
ELEM_HOST = "https://dl.elementaryos.org/MTc5MDgxMjk0Mw=="
ELEM_PAGE = _links(
    f"{ELEM_HOST}/elementaryos-8.1-stable-amd64.20260107.iso",
    f"{ELEM_HOST}/elementaryos-8.1-stable-arm64.20260301.iso",
    f"{ELEM_HOST}/elementaryos-8.1-stable-amd64.20260219.iso",
    # An older series rebuilt later is still the older series.
    f"{ELEM_HOST}/elementaryos-7.1-stable-amd64.20260220.iso",
    f"{ELEM_HOST}/elementaryos-9.0-daily-amd64.20261001.iso",
    f"{ELEM_HOST}/elementary-stable-amd64-latest.iso",
)

# ------------------------------------------------------------- TUXEDO OS

TUX = "https://os.tuxedocomputers.com/"
TUX_PAGE = _links("TUXEDO-OS-202512181030.iso", "TUXEDO-OS-202609161651.iso",
                  "TUXEDO-OS-202609161651.iso.torrent", "TUXEDO-OS_current.iso",
                  "TUXEDO-OS-202604011200.iso", "checksums/")

# ---------------------------------------------------------------- Mageia

MAGEIA = "https://distrib-coffee.ipsl.jussieu.fr/pub/linux/Mageia/iso/"


def _mageia_release(v):
    return _links(f"Mageia-{v}-Live-GNOME-x86_64/", f"Mageia-{v}-Live-Plasma-x86_64/",
                  f"Mageia-{v}-Live-Xfce-x86_64/", f"Mageia-{v}-i686/", f"Mageia-{v}-x86_64/", "torrents/")


MAGEIA_PAGES = {
    # 9 above 10 as text; a point release, as 4.1 to 7.1 were.
    MAGEIA: _links("/pub/linux/Mageia/", "9/", "10/", "10.1/", "8/", "cauldron/", "11-beta1/"),
    MAGEIA + "10.1/": _mageia_release("10.1"),
    MAGEIA + "10/": _mageia_release("10"),
    MAGEIA + "9/": _mageia_release("9"),
}

# --------------------------------------------------------------- Pop!_OS

POP = "https://system76.com/pop/download/"
POP_API = "https://api.pop-os.org/builds/{}/{}"


def _pop_build(release, channel, build):
    url = f"https://iso.pop-os.org/{release}/amd64/{channel}/{build}/pop-os_{release}_amd64_{channel}_{build}.iso"
    return json.dumps({"version": release, "url": url, "build": str(build), "sha_sum": "a" * 64,
                       "channel": channel})


POP_PAGES = {
    # The script lines the page fetches its buttons with, one a line.
    POP: "\n".join([
        "const legacy = await fetchRelease('22.04', 'intel', 'amd64');",
        "const release = await fetchRelease('24.04', 'generic', 'amd64');",
        "const nvidia = await fetchRelease('24.04', 'nvidia', 'amd64');",
        "const arm = await fetchRelease('24.04', 'generic', 'arm64');",
        "const raspi = await fetchRelease('22.04', 'raspi', 'arm64');",
    ]),
    POP_API.format("24.04", "generic"): _pop_build("24.04", "generic", 28),
    POP_API.format("24.04", "nvidia"): _pop_build("24.04", "nvidia", 28),
    # The channel the page dropped, still answering with its last build.
    POP_API.format("24.04", "intel"): _pop_build("24.04", "intel", 20),
    POP_API.format("22.04", "intel"): _pop_build("22.04", "intel", 58),
    # A beta the API serves before the page offers it.
    POP_API.format("26.04", "generic"): _pop_build("26.04", "generic", 3),
}

# --------------------------------------------------------------- KDE neon

NEON = "https://neon.kde.org/download"
NEON_FILES = "https://files.kde.org/neon/images/"
NEON_PAGE = _links(
    f"{NEON_FILES}desktop/user/20260601-1200/neon-user-desktop-20260601-1200.iso",
    f"{NEON_FILES}desktop/user/20260903-0454/neon-user-desktop-20260903-0454.iso",
    f"{NEON_FILES}desktop/user/20260903-0454/neon-user-desktop-20260903-0454.iso.sig",
    f"{NEON_FILES}desktop/user/current/neon-user-desktop-current.iso",
    f"{NEON_FILES}desktop/testing/20260905-0146/neon-testing-desktop-20260905-0146.iso",
    f"{NEON_FILES}mobile/user/20260910-0514/neon-user-mobile-20260910-0514.iso",
    f"{NEON_FILES}desktop/user/20251212-0300/neon-user-desktop-20251212-0300.iso",
)


def _neon_sum(ver):
    name = f"neon-user-desktop-{ver}"
    return {f"{NEON_FILES}desktop/user/{ver}/{name}.sha256sum": f"{SUM}  {name}.iso\n"}

# ----------------------------------------------------------------- Zorin OS

ZORIN = "https://zorin.com/os/download/"
ZMIRROR = "https://mirrors.edge.kernel.org/zorinos-isos/18/"


def _zorin(edition, *names):
    return "<html>" + "".join(f'<a href="{ZMIRROR}Zorin-OS-{n.format(e=edition)}.iso">' for n in names) + "</html>"


ZORIN_PAGES = {
    # 9 above 18 as text.
    ZORIN: _links("/os/download/#core", "/os/download/17/core/", "/os/download/18/core/",
                  "/os/download/18/education/", "/os/download/9/"),
    ZORIN + "18/core/": _zorin("Core", "18-{e}-64-bit-r3", "18.1-{e}-64-bit-r1", "18.1-{e}-64-bit-r2",
                               "18.1-{e}-64-bit", "18.2-{e}-Beta-64-bit", "18-{e}-64-bit"),
    ZORIN + "18/education/": _zorin("Education", "18-{e}-64-bit", "18.1-{e}-64-bit",
                                    "18-{e}-64-bit-r3", "18.2-{e}-Beta-64-bit-r1"),
    ZORIN + "17/core/": _zorin("Core", "17.3-{e}-64-bit-r2", "17.3-{e}-64-bit"),
}

# --------------------------------------------------------------- Linux Lite

LL = "https://sourceforge.net/projects/linux-lite/rss?limit=100"
LL_PAGE = _rss("/8.2/rc1/linux-lite-8.2-rc1-64bit.iso", "/8.2/rc1/linux-lite-8.2-rc1-64bit.iso.sha256",
               "/7.8/linux-lite-7.8-64bit.iso", "/8.0/linux-lite-8.0-64bit.iso",
               "/8.0/linux-lite-8.0-64bit.iso.torrent", "/8.0/rc2/linux-lite-8.0-rc2-64bit.iso",
               "/7.10/linux-lite-7.10-64bit.iso", "/readme.markdown")


def _ll_sum(ver):
    name = f"linux-lite-{ver}-64bit.iso"
    return {f"https://downloads.sourceforge.net/project/linux-lite/{ver}/{name}.sha256": f"{SUM}  {name}\n"}


CASES = {
    "opensuse": [
        Case(pages=SUSE_PAGES, flavor="tumbleweed-dvd", newest="20261003",
             filename="openSUSE-Tumbleweed-DVD-x86_64-Snapshot20261003-Media.iso", newest_urls=(TW,)),
        Case(pages=SUSE_PAGES, flavor="tumbleweed-kde", newest="20261003",
             filename="openSUSE-Tumbleweed-KDE-Live-x86_64-Snapshot20261003-Media.iso", newest_urls=(TW,)),
        Case(pages=SUSE_PAGES, flavor="leap-dvd", newest="16.0 (Build 178.27)",
             filename="Leap-16.0-offline-installer-x86_64-Build178.27.install.iso",
             newest_urls=(LEAP_PAGE, LEAP16)),
        Case(pages=SUSE_PAGES, flavor="leap-net", newest="16.0 (Build 178.27)",
             filename="Leap-16.0-online-installer-x86_64-Build178.27.install.iso",
             newest_urls=(LEAP_PAGE, LEAP16)),
    ],
    "nixos": [
        Case(pages=_nix(f), flavor=f, newest="26.05.11275",
             filename=f"nixos-{f}-26.05.11275.6d663c0533ff-x86_64-linux.iso",
             newest_urls=(NIX.format("26.11", f), NIX.format("26.05", f)),
             extra={"patch": NIX_PATCH, "sha256": SUM})
        for f in ("graphical", "minimal")
    ],
    "elementary": Case(pages={ELEM: ELEM_PAGE}, flavor="stable", newest="8.1 (20260219)",
                       filename="elementaryos-8.1-stable-amd64.20260219.iso", newest_urls=(ELEM,)),
    "tuxedo": Case(pages={TUX: TUX_PAGE}, flavor="standard", newest="202609161651",
                   filename="TUXEDO-OS-202609161651.iso", newest_urls=(TUX,)),
    "mageia": [
        Case(pages=MAGEIA_PAGES, flavor="classic-dvd", newest="10.1", filename="Mageia-10.1-x86_64.iso",
             newest_urls=(MAGEIA, MAGEIA + "10.1/")),
        Case(pages=MAGEIA_PAGES, flavor="live-plasma", newest="10.1",
             filename="Mageia-10.1-Live-Plasma-x86_64.iso", newest_urls=(MAGEIA, MAGEIA + "10.1/")),
    ],
    "popos": [
        Case(pages=POP_PAGES, flavor="intel", newest="24.04 (Build 28)",
             filename="pop-os_24.04_amd64_generic_28.iso",
             newest_urls=(POP, POP_API.format("24.04", "generic"))),
        Case(pages=POP_PAGES, flavor="nvidia", newest="24.04 (Build 28)",
             filename="pop-os_24.04_amd64_nvidia_28.iso",
             newest_urls=(POP, POP_API.format("24.04", "nvidia"))),
    ],
    "kde_neon": Case(pages={NEON: NEON_PAGE, **_neon_sum("20260903-0454")}, flavor="user",
                     newest="20260903-0454", filename="neon-user-desktop-20260903-0454.iso", newest_urls=(NEON,),
                     extra={"sha256": SUM}),
    "zorin": [
        Case(pages=ZORIN_PAGES, flavor="core", newest="18.1 r2", filename="Zorin-OS-18.1-Core-64-bit-r2.iso",
             newest_urls=(ZORIN, ZORIN + "18/core/")),
        # "18 r3" is older than 18.1, though 3 is more than 1.
        Case(pages=ZORIN_PAGES, flavor="education", newest="18.1",
             filename="Zorin-OS-18.1-Education-64-bit.iso", newest_urls=(ZORIN, ZORIN + "18/education/")),
    ],
    "linuxlite": [
        Case(pages={LL: LL_PAGE, **_ll_sum("8.0")}, flavor="standard", newest="8.0",
             filename="linux-lite-8.0-64bit.iso", newest_urls=(LL,), extra={"sha256": SUM}),
        # 8.8 above 8.10 as text.
        Case(pages={LL: _rss("/8.8/linux-lite-8.8-64bit.iso", "/8.12/rc1/linux-lite-8.12-rc1-64bit.iso",
                             "/8.10/linux-lite-8.10-64bit.iso", "/8.9/linux-lite-8.9-64bit.iso"),
                    **_ll_sum("8.10")},
             flavor="standard", newest="8.10", filename="linux-lite-8.10-64bit.iso", newest_urls=(LL,)),
    ],
}
EXEMPT = {}

RECIPES = {cls.key: cls for cls in (OpenSUSERecipe, NixOSRecipe, ElementaryRecipe, TuxedoRecipe, MageiaRecipe,
                                    PopOSRecipe, KDENeonRecipe, ZorinRecipe, LinuxLiteRecipe)}


def _cases():
    for key, cases in CASES.items():
        for i, case in enumerate(cases if isinstance(cases, list) else [cases]):
            yield pytest.param(key, case, id=f"{key}-{case.flavor}-{i}")


def _patched(monkeypatch, key, case):
    for name, value in case.extra.get("patch", {}).items():
        monkeypatch.setattr(RECIPES[key], name, value)
    return RECIPES[key]


@pytest.mark.parametrize("key,case", list(_cases()))
def test_reports_the_newest_release_in_any_page_order(monkeypatch, key, case):
    assert_newest(monkeypatch, _patched(monkeypatch, key, case), case)


@pytest.mark.parametrize("key,case", list(_cases()))
def test_refuses_rather_than_falling_back(monkeypatch, key, case):
    assert_no_fallback(monkeypatch, _patched(monkeypatch, key, case), case)


@pytest.mark.parametrize("key,case", [p for p in _cases() if p.values[1].filename])
def test_iso_identity_reads_the_filename_back(key, case):
    found = identify(case.filename)
    assert found is not None, f"{case.filename} is not recognised"
    assert (found.key, found.flavor_id, found.version) == (key, case.flavor, case.newest)


@pytest.mark.parametrize("key,case", [p for p in _cases() if p.values[1].extra.get("sha256")])
def test_the_published_checksum_comes_with_it(monkeypatch, key, case):
    recipe, _ = use(monkeypatch, _patched(monkeypatch, key, case)(), case.pages)
    assert recipe.fetch_download_info(case.flavor).sha256 == case.extra["sha256"]


# What each project publishes next: the pages that change, and what must be reported then.
NEWER = {
    "opensuse-leap": (CASES["opensuse"][2], {
        LEAP_PAGE: '<meta http-equiv="refresh" content="0; url=/leap/16.1/" />' + _links("/leap/16.0/"),
        SUSE + "distribution/leap/16.1/offline/?jsontable": _jsontable(
            "Leap-16.1-offline-installer-x86_64-Build61.4.install.iso",
            "Leap-16.1-offline-installer-x86_64-Build53.1.install.iso")}, "16.1 (Build 61.4)"),
    "opensuse-tumbleweed": (CASES["opensuse"][0], {TW: _jsontable(
        "openSUSE-Tumbleweed-DVD-x86_64-Snapshot20261003-Media.iso",
        "openSUSE-Tumbleweed-DVD-x86_64-Snapshot20261006-Media.iso")}, "20261006"),
    "nixos": (CASES["nixos"][1], {NIX.format("26.11", "minimal"): Resp(url=NIX_REAL.format(
        c="26.11", v="26.11.100", h="abcdef012345", f="minimal")),
        **_nix_sum("26.11", "26.11.100.abcdef012345", "minimal")}, "26.11.100"),
    "elementary": (CASES["elementary"], {ELEM: ELEM_PAGE + _links(
        f"{ELEM_HOST}/elementaryos-8.1-stable-amd64.20260612.iso")}, "8.1 (20260612)"),
    "tuxedo": (CASES["tuxedo"], {TUX: TUX_PAGE + _links("TUXEDO-OS-202610051200.iso")}, "202610051200"),
    "mageia": (CASES["mageia"][0], {MAGEIA: MAGEIA_PAGES[MAGEIA] + _links("11/"),
                                    MAGEIA + "11/": _mageia_release("11")}, "11"),
    "popos": (CASES["popos"][0], {POP: POP_PAGES[POP] + "\nfetchRelease('26.04', 'generic', 'amd64')"},
              "26.04 (Build 3)"),
    "kde_neon": (CASES["kde_neon"], {NEON: NEON_PAGE + _links(
        f"{NEON_FILES}desktop/user/20261001-0101/neon-user-desktop-20261001-0101.iso"),
        **_neon_sum("20261001-0101")}, "20261001-0101"),
    "zorin": (CASES["zorin"][0], {ZORIN + "18/core/": ZORIN_PAGES[ZORIN + "18/core/"]
                                  + _zorin("Core", "18.2-{e}-64-bit")}, "18.2"),
    "linuxlite": (CASES["linuxlite"][0], {LL: _rss("/8.2/linux-lite-8.2-64bit.iso") + LL_PAGE,
                                          **_ll_sum("8.2")}, "8.2"),
}


@pytest.mark.parametrize("name", NEWER)
def test_a_newer_release_is_reported_once_it_appears(monkeypatch, name):
    case, changed, newest = NEWER[name]
    key = name.split("-")[0]
    recipe, session = use(monkeypatch, _patched(monkeypatch, key, case)(), {**case.pages, **changed})
    assert recipe.fetch_download_info(case.flavor).version == newest
    assert not session.missing


def test_mageia_refuses_a_release_directory_that_has_no_images_yet(monkeypatch):
    pages = {**MAGEIA_PAGES, MAGEIA: MAGEIA_PAGES[MAGEIA] + _links("11/"), MAGEIA + "11/": _links("torrents/")}
    recipe, _ = use(monkeypatch, MageiaRecipe(), pages)
    with pytest.raises(ScrapeError, match="no Mageia-11-x86_64 image"):
        recipe.fetch_download_info("classic-dvd")


def test_kde_neon_never_reports_a_label(monkeypatch):
    page = _links(f"{NEON_FILES}desktop/user/current/neon-user-desktop-current.iso")
    recipe, _ = use(monkeypatch, KDENeonRecipe(), {NEON: page})
    with pytest.raises(ScrapeError, match="no dated user-edition ISO"):
        recipe.fetch_download_info("user")


@pytest.mark.parametrize("today,first", [
    (date(2026, 10, 31), "26.05"), (date(2026, 11, 1), "26.11"),
    (date(2026, 12, 31), "26.11"), (date(2027, 1, 1), "27.05"), (date(2027, 5, 31), "27.05"),
])
def test_nixos_tries_the_release_due_next_first(today, first):
    channels = NixOSRecipe._candidate_channels(today)
    assert channels[0] == first and len(channels) == 4
