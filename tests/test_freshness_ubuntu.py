"""Freshness Cases for Ubuntu, Linux Mint, Debian and the Debian family.

Shapes captured from each project on 2026-10-06; version numbers are moved
where a trap needs them (Debian 13.9.0 against 13.10.0, Q4OS 6.9 against
6.10), so that a recipe sorting text, or taking the first or last link, fails.
"""
import pytest

from src.core.iso_identity import identify
from src.core.recipe_base import ScrapeError
from src.recipes.debian import LIVE_DIR, NETINST_DIR, TREES, DebianRecipe
from src.recipes.debian_family import (
    AntiXRecipe, DevuanRecipe, GrmlRecipe, MXLinuxRecipe, Q4OSRecipe)
from src.recipes.mint import MintRecipe
from src.recipes.ubuntu import META_RELEASE, UbuntuRecipe
from tests.freshness import Case, Resp, assert_newest, assert_no_fallback, use


def _listing(*names):
    return "<html><body>" + "".join(f'<a href="{n}">{n}</a>' for n in names) + "</body></html>"


def _rss(*paths, project=""):
    """A SourceForge feed; with `project`, each item carries its file page link."""
    def item(p):
        link = f"<link>https://sourceforge.net/projects/{project}/files{p}/download</link>" if project else ""
        return f"<item><title><![CDATA[{p}]]></title>{link}</item>"
    return "<rss><channel>" + "".join(item(p) for p in paths) + "</channel></rss>"


# ------------------------------------------------------------------ Ubuntu

UB = "https://releases.ubuntu.com/"


def _meta(*series):
    """changelogs.ubuntu.com/meta-release: one stanza per series, oldest first."""
    return "\n".join(f"Dist: {dist}\nName: {dist.title()}\nVersion: {version}\n"
                     f"Date: Thu, 01 January 2026 00:00:00 UTC\nSupported: {supported}\n"
                     f"Description: This is the {version} release\nRelease-File: "
                     f"http://archive.ubuntu.com/ubuntu/dists/{dist}-updates/Release\n"
                     for dist, version, supported in series)


# 25.10 is past end of life; 26.10 is not listed until its release day.
META = _meta(("karmic", "9.10", 0), ("noble", "24.04.5 LTS", 1), ("questing", "25.10", 0),
             ("resolute", "26.04.1 LTS", 1))
# Stanzas are blocks of lines: shuffling the lines would mix two series.
KEEP_META = {"keep_order": (META_RELEASE,)}


def _sums(*names):
    """A SHA256SUMS in Ubuntu's layout, a different hash for each name."""
    return "".join(f"{format(i, 'x') * 64} *{n}\n" for i, n in enumerate(names, 1))

UB_INDEX = _listing("../", "24.04/", "24.04.5.1/", "25.10/", "26.04.1/", "26.04/", "26.10/",
                    "9.10/", "noble/", "resolute/")


def _ubuntu_series(*versions, extra=()):
    """A releases.ubuntu.com series directory: it holds the .0 images beside
    those of the latest point release."""
    names = []
    for v in versions:
        names += [f"ubuntu-{v}-desktop-amd64.iso", f"ubuntu-{v}-desktop-amd64.iso.torrent",
                  f"ubuntu-{v}-live-server-amd64.iso", f"ubuntu-{v}-wsl-amd64.wsl"]
    return _listing("SHA256SUMS", *names, *extra)


UB_PAGES = {
    META_RELEASE: META,
    UB: UB_INDEX,
    # Only betas so far, so the series is not out.
    UB + "26.10/": _listing("SHA256SUMS", "ubuntu-26.10-beta-desktop-amd64.iso",
                            "ubuntu-26.10-beta-live-server-amd64.iso"),
    UB + "26.10/release/": Resp("", 404),
    UB + "26.04.1/": _ubuntu_series("26.04", "26.04.1"),
    UB + "26.04.1/SHA256SUMS": _sums("ubuntu-26.04-desktop-amd64.iso", "ubuntu-26.04.1-desktop-amd64.iso",
                                     "ubuntu-26.04.1-live-server-amd64.iso"),
    UB + "26.04/": _ubuntu_series("26.04", "26.04.1"),
    UB + "25.10/": _ubuntu_series("25.10"),
    UB + "24.04.5.1/": _ubuntu_series("24.04.5", extra=("ubuntu-24.04.5.1-desktop-amd64.iso",)),
    UB + "24.04/": _ubuntu_series("24.04.4", "24.04.5"),
}

KU = "https://cdimage.ubuntu.com/kubuntu/releases/"


def _kubuntu(*versions):
    return _listing("/kubuntu/releases/", "SHA256SUMS",
                    *[f"kubuntu-{v}-desktop-amd64{ext}" for v in versions for ext in (".iso", ".iso.zsync")])


KU_PAGES = {
    META_RELEASE: META,
    KU: _listing("/kubuntu/", "24.04.5/", "25.10/", "26.04.1/", "26.04/", "26.10/", "9.10/", "noble/"),
    KU + "26.10/": _listing("/kubuntu/releases/", "release/"),
    # Snapshots sit in their own directories; one placed beside the finals
    # must still not count as a release.
    KU + "26.10/release/": _listing("/kubuntu/releases/26.10/", "snapshot-3/", "snapshot-4/",
                                    "kubuntu-26.10-snapshot4-desktop-amd64.iso",
                                    "kubuntu-26.10-beta-desktop-amd64.iso"),
    KU + "26.04.1/": _listing("/kubuntu/releases/", "release/"),
    KU + "26.04.1/release/": _kubuntu("26.04", "26.04.1"),
    KU + "26.04.1/release/SHA256SUMS": _sums("kubuntu-26.04-desktop-amd64.iso", "kubuntu-26.04.1-desktop-amd64.iso"),
    KU + "26.04/": _listing("/kubuntu/releases/", "release/"),
    KU + "26.04/release/": _kubuntu("26.04"),
    KU + "25.10/": _listing("/kubuntu/releases/", "release/"),
    KU + "25.10/release/": _kubuntu("25.10"),
}

MA = "https://cdimage.ubuntu.com/ubuntu-mate/releases/"


def _mate(*versions):
    return _listing("/ubuntu-mate/releases/", "SHA256SUMS",
                    *[f"ubuntu-mate-{v}-desktop-amd64.iso" for v in versions])


# Ubuntu MATE built no 26.04: its newest final, 25.10, is past end of life.
MA_PAGES = {
    META_RELEASE: META,
    MA: _listing("/ubuntu-mate/", "16.04/", "22.04.5/", "24.04.4/", "24.04.5/", "24.04/", "25.10/",
                 "26.10/", "noble/", "questing/"),
    MA + "26.10/": _listing("/ubuntu-mate/releases/", "release/"),
    MA + "26.10/release/": _listing("/ubuntu-mate/releases/26.10/", "ubuntu-mate-26.10-beta-desktop-amd64.iso"),
    MA + "25.10/": _listing("/ubuntu-mate/releases/", "release/"),
    MA + "25.10/release/": _mate("25.10"),
    MA + "24.04.5/": _listing("/ubuntu-mate/releases/", "release/"),
    MA + "24.04.5/release/": _mate("24.04.5"),
    MA + "24.04.5/release/SHA256SUMS": _sums("ubuntu-mate-24.04.5-desktop-amd64.iso"),
    MA + "24.04.4/": _listing("/ubuntu-mate/releases/", "release/"),
    MA + "24.04.4/release/": _mate("24.04.4"),
}

# ------------------------------------------------------------------- Mint

MINT = "https://www.linuxmint.com/download_all.php"
MINT_MIRROR = "https://mirrors.edge.kernel.org/linuxmint/stable/"


def _mint_rows(*releases):
    """download_all.php: one row per edition, the version cell spanning them."""
    rows = []
    for version, base in releases:
        rows.append(f'<tr><td rowspan="3">{version}</td><td rowspan="3">Name</td>'
                    f'<td><a href="edition.php?id=1">Cinnamon </a></td>'
                    f'<td rowspan="3">{base}</td><td rowspan="3">LTS</td></tr>')
        rows += [f'<tr><td><a href="edition.php?id=2">{e} </a></td></tr>' for e in ("MATE", "Xfce")]
    return ('<table><thead><tr><th>Version</th><th>Codename</th></tr></thead><tbody>'
            + "".join(rows) + "</tbody></table>")


def _mint_sums(version):
    return "".join(f"{'%02d' % i * 32} *linuxmint-{version}-{e}-64bit.iso\n"
                   for i, e in enumerate(("cinnamon", "mate", "xfce")))


# LMDE 7 is in the same table: "7" sorts above "22.3" as text.
MINT_RELEASES = (("22.1", "Ubuntu Noble"), ("22.3", "Ubuntu Noble"), ("7", "Debian Trixie"),
                 ("22.2", "Ubuntu Noble"), ("21.3", "Ubuntu Jammy"))
MINT_PAGES = {
    MINT: _mint_rows(*MINT_RELEASES),
    MINT_MIRROR + "22.3/sha256sum.txt": _mint_sums("22.3"),
    MINT_MIRROR + "22.2/sha256sum.txt": _mint_sums("22.2"),
    MINT_MIRROR + "22.1/sha256sum.txt": _mint_sums("22.1"),
}

# ----------------------------------------------------------------- Debian

DEB_CD, DEB_GET = TREES


def _debian_pages():
    netinst = DEB_CD + NETINST_DIR
    live = DEB_CD + LIVE_DIR
    return {
        # Mid-update, the directory carries two point releases.
        netinst: _listing("../", "debian-13.9.0-amd64-netinst.iso", "debian-13.10.0-amd64-netinst.iso",
                          "debian-13.10.0-amd64-netinst.iso.torrent",
                          "debian-forky-DI-alpha1-amd64-netinst.iso", "debian-13.8.0-amd64-netinst.iso",
                          "SHA256SUMS"),
        netinst + "SHA256SUMS": "".join(f"{c * 64}  debian-13.{n}.0-amd64-netinst.iso\n"
                                        for c, n in (("a", 8), ("b", 9), ("c", 10))),
        live: _listing("../", "debian-live-13.9.0-amd64-kde.iso", "debian-live-13.10.0-amd64-kde.iso",
                       "debian-live-13.10.0-amd64-gnome.iso", "debian-live-forky-DI-alpha1-amd64-kde.iso",
                       "debian-live-13.8.0-amd64-kde.iso", "SHA256SUMS"),
        live + "SHA256SUMS": f"{'d' * 64}  debian-live-13.10.0-amd64-kde.iso\n",
        # get.debian.org serves the same tree, so reading it after cdimage
        # fails is not a fallback to an older release. It is down here, so a
        # failure on cdimage has nowhere to go but a refusal.
        DEB_GET + NETINST_DIR: Resp("", 503),
        DEB_GET + LIVE_DIR: Resp("", 503),
    }

# --------------------------------------------------------------- MX Linux

MX = "https://sourceforge.net/projects/mx-linux/rss?path=/Final"
MX_PAGES = {MX: _rss(
    "/Final/README.txt",
    "/Final/Xfce/MX-25.9_Xfce_x64.iso",
    "/Final/Xfce/MX-25.9_Xfce_ahs_x64.iso",
    "/Final/Xfce/MX-25.10_Xfce_x64.iso",
    "/Final/Xfce/MX-25.10_Xfce_x64.iso.sha256",
    "/Final/Xfce/MX-26_beta1_Xfce_x64.iso",
    "/Final/Xfce/MX-26_RC1_Xfce_ahs_x64.iso",
    "/Final/Xfce/MX-25.10_Xfce_ahs_x64.iso",
    "/Final/Xfce/MX-25.10_Xfce_ahs_x64.iso.sha256",
    "/Final/KDE/MX-25.10_KDE_x64.iso",
    # 23.x named its Xfce image without the edition.
    "/Final/Xfce/MX-23.6_x64.iso",
    "/Final/Xfce/mx25.10_rpi_respin_arm64.zip",
    project="mx-linux"),
    **{f"https://sourceforge.net/projects/mx-linux/files/Final/Xfce/MX-25.10_{e}_x64.iso.sha256":
       f"{h * 64}  MX-25.10_{e}_x64.iso\n" for e, h in (("Xfce", "a"), ("Xfce_ahs", "b"))}}

# ------------------------------------------------------------------ antiX

ANTIX = "https://antixlinux.com/download/"
_SF_ANTIX = "https://sourceforge.net/projects/antix-linux/files/Final/"
ANTIX_PAGES = {ANTIX: "<html><body>" + "".join(
    f'<a href="{_SF_ANTIX}{folder}/{name}/download">{name}</a>' for folder, name in (
        ("antiX-23.2", "antiX-23.2_x64-full.iso"),
        ("antiX-26.1", "antiX-26.1_386-full.iso"),
        ("antiX-26.1", "antiX-26.1_x64-full.iso"),
        ("antiX-26.1", "antiX-26.1_x64-core.iso"),
        ("Testing", "antiX-27_b1_x64-full.iso"),
        ("antiX-26.1", "antiX-26.1-runit_x64-full.iso"),
        ("antiX-26", "antiX-26_x64-full.iso"),
        ("antiX-8.5", "antiX-8.5_x64-full.iso"),
    )) + "</body></html>"}

# ----------------------------------------------------------------- Devuan

DEV = "https://files.devuan.org/"
DEV_PAGES = {
    # "jessie" sorts after "excalibur": the codename's own order means nothing.
    DEV: _listing("devuan_chimaera/", "devuan_daedalus/", "devuan_excalibur/", "devuan_freia/",
                  "devuan_jessie/", "devuan_ascii/"),
    DEV + "devuan_ascii/installer-iso/": Resp("", 404),
    DEV + "devuan_jessie/installer-iso/": _listing("devuan_jessie_1.0.0_amd64_NETINST.iso",
                                                   "devuan_jessie_1.0.0_amd64_DVD.iso"),
    DEV + "devuan_chimaera/installer-iso/": _listing(
        *[f"devuan_chimaera_4.0.3_amd64_{f}.iso" for f in ("netinstall", "server", "desktop")]),
    DEV + "devuan_daedalus/installer-iso/": _listing(
        *[f"devuan_daedalus_5.0.1_{a}_{f}.iso" for a in ("amd64", "i386")
          for f in ("netinstall", "server", "desktop")]),
    DEV + "devuan_excalibur/installer-iso/": _listing(
        *[f"devuan_excalibur_6.1.1_amd64_{f}.iso" for f in ("cd2", "desktop", "netinstall", "server")],
        "SHA256SUMS.txt"),
    DEV + "devuan_excalibur/installer-iso/SHA256SUMS.txt": "".join(
        f"{h * 64}  devuan_excalibur_6.1.1_amd64_{f}.iso\n" for h, f in (("a", "netinstall"), ("b", "server"))),
    DEV + "devuan_excalibur/desktop-live/devuan_excalibur_6.1.1_amd64_desktop-live.iso.sha256":
        f"{'c' * 64}  devuan_excalibur_6.1.1_amd64_desktop-live.iso\n",
    DEV + "devuan_excalibur/desktop-live/": _listing(
        "../", "README_desktop-live.txt", "devuan_excalibur_6.1.1_amd64_desktop-live.iso",
        "devuan_excalibur_6.1.1_amd64_desktop-live.iso.sha256"),
    # Testing: a dated build that is not a release.
    DEV + "devuan_freia/installer-iso/": _listing("devuan_freia_7.0-202610030111_amd64_netinstall.iso"),
}

# ------------------------------------------------------------------- Q4OS

Q4 = "https://sourceforge.net/projects/q4os/rss?path=/stable"
Q4_PAGES = {Q4: _rss(
    "/stable/md5sum.txt",
    "/stable/q4os-5.10-i386-instcd.r1.iso",
    "/stable/q4os-6.9-x64.r1.iso",
    "/stable/q4os-6.9-x64-tde.r1.iso",
    "/stable/q4os-6.10-x64.r9.iso",
    "/stable/q4os-6.10-x64.r10.iso",
    "/stable/q4os-6.10-x64-tde.r1.iso",
    "/stable/q4os-6.10-x64-instcd.r1.iso",
    "/stable/q4os-6.9-x64-instcd.r1.iso",
    # Testing builds live in /testing; one that strayed into /stable is still
    # not a release.
    "/stable/q4os-7.0-x64-plasma.r8-testing.iso",
    project="q4os")}

# ------------------------------------------------------------------- Grml

GRML = "https://grml.org/download/"
GRML_SUMS = "https://ftp-master.grml.org/SHA256SUMS-2026.09"
GRML_PAGES = {GRML_SUMS: "".join(f"{h * 64}  grml-{f}-2026.09-{a}.iso\n" for h, f, a in (
    ("a", "full", "amd64"), ("b", "full", "arm64"), ("c", "small", "amd64"))), GRML: "<html><body><h1>Download Grml 2026.09</h1>" + "".join(
    f"<a href={u}>{u.rsplit('/', 1)[-1]}</a>" for u in (
        "/changelogs/README-grml-2026.09/",
        "https://download.grml.org/grml-full-2026.09-arm64.iso",
        "https://download.grml.org/grml-full-2026.09-amd64-netboot.tar",
        "https://download.grml.org/grml-full-2026.09-amd64.iso",
        "https://download.grml.org/devel/grml-full-2026.12-rc1-amd64.iso",
        "https://download.grml.org/grml-small-2026.09-amd64.iso",
        "https://download.grml.org/grml-full-2026.04-amd64.iso",
        GRML_SUMS, GRML_SUMS + ".gpg",
    )) + "</body></html>"}
# Releases are dated with a zero-padded month, so text and number order agree
# here; there is no pair to disagree.


CASES = {
    "ubuntu": [
        Case(UB_PAGES, "desktop", "26.04.1", "ubuntu-26.04.1-desktop-amd64.iso",
             newest_urls=(META_RELEASE, UB, UB + "26.04.1/", UB + "26.10/", UB + "26.10/release/"),
             extra={**KEEP_META, "sha256": "2" * 64,
                    "newer": ({UB + "26.10/": _ubuntu_series("26.10")}, "26.10")}),
        Case(UB_PAGES, "server", "26.04.1", "ubuntu-26.04.1-live-server-amd64.iso",
             newest_urls=(UB, UB + "26.04.1/"), extra={**KEEP_META, "sha256": "3" * 64}),
        Case(KU_PAGES, "kubuntu", "26.04.1", "kubuntu-26.04.1-desktop-amd64.iso",
             newest_urls=(META_RELEASE, KU, KU + "26.04.1/", KU + "26.04.1/release/", KU + "26.10/release/"),
             extra={**KEEP_META, "sha256": "2" * 64,
                    "newer": ({KU + "26.10/release/": _kubuntu("26.10")}, "26.10")}),
        Case(MA_PAGES, "mate", "24.04.5", "ubuntu-mate-24.04.5-desktop-amd64.iso",
             newest_urls=(META_RELEASE, MA, MA + "24.04.5/", MA + "24.04.5/release/", MA + "26.10/release/"),
             extra={**KEEP_META, "sha256": "1" * 64}),
    ],
    "mint": [
        Case(MINT_PAGES, flavor, "22.3", f"linuxmint-22.3-{flavor}-64bit.iso",
             newest_urls=(MINT, MINT_MIRROR + "22.3/sha256sum.txt"),
             extra={"newer": ({MINT: _mint_rows(("23", "Ubuntu Resolute"), *MINT_RELEASES),
                               MINT_MIRROR + "23/sha256sum.txt": _mint_sums("23")}, "23")})
        for flavor in ("cinnamon", "xfce")
    ],
    "debian": [
        Case(_debian_pages(), "netinst", "13.10.0", "debian-13.10.0-amd64-netinst.iso",
             newest_urls=(DEB_CD + NETINST_DIR,)),
        Case(_debian_pages(), "kde", "13.10.0", "debian-live-13.10.0-amd64-kde.iso",
             newest_urls=(DEB_CD + LIVE_DIR,)),
    ],
    "mxlinux": [
        Case(MX_PAGES, "xfce", "25.10", "MX-25.10_Xfce_x64.iso", newest_urls=(MX,), extra={"sha256": "a" * 64}),
        Case(MX_PAGES, "xfce-ahs", "25.10", "MX-25.10_Xfce_ahs_x64.iso", newest_urls=(MX,),
             extra={"sha256": "b" * 64}),
    ],
    "antix": [
        Case(ANTIX_PAGES, "full", "26.1", "antiX-26.1_x64-full.iso", newest_urls=(ANTIX,)),
        Case(ANTIX_PAGES, "core", "26.1", "antiX-26.1_x64-core.iso", newest_urls=(ANTIX,)),
    ],
    "devuan": [
        Case(DEV_PAGES, "netinstall", "6.1.1", "devuan_excalibur_6.1.1_amd64_netinstall.iso",
             newest_urls=(DEV, DEV + "devuan_excalibur/installer-iso/",
                          DEV + "devuan_daedalus/installer-iso/", DEV + "devuan_freia/installer-iso/"),
             extra={"sha256": "a" * 64}),
        Case(DEV_PAGES, "desktop-live", "6.1.1", "devuan_excalibur_6.1.1_amd64_desktop-live.iso",
             newest_urls=(DEV + "devuan_excalibur/installer-iso/", DEV + "devuan_excalibur/desktop-live/"),
             extra={"sha256": "c" * 64}),
    ],
    "q4os": [
        Case(Q4_PAGES, "plasma", "6.10", "q4os-6.10-x64.r10.iso", newest_urls=(Q4,)),
        Case(Q4_PAGES, "trinity", "6.10", "q4os-6.10-x64-tde.r1.iso", newest_urls=(Q4,)),
        Case(Q4_PAGES, "instcd", "6.10", "q4os-6.10-x64-instcd.r1.iso", newest_urls=(Q4,)),
    ],
    "grml": [
        Case(GRML_PAGES, "full", "2026.09", "grml-full-2026.09-amd64.iso", newest_urls=(GRML,),
             extra={"sha256": "a" * 64}),
        Case(GRML_PAGES, "small", "2026.09", "grml-small-2026.09-amd64.iso", newest_urls=(GRML,),
             extra={"sha256": "c" * 64}),
    ],
}
EXEMPT = {}

RECIPES = {cls.key: cls for cls in (UbuntuRecipe, MintRecipe, DebianRecipe, MXLinuxRecipe,
                                    AntiXRecipe, DevuanRecipe, Q4OSRecipe, GrmlRecipe)}


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


@pytest.mark.parametrize("key,case", list(_cases()))
def test_iso_identity_reads_the_filename_back(key, case):
    found = identify(case.filename)
    assert found and (found.key, found.flavor_id, found.version) == (key, case.flavor, case.newest)


@pytest.mark.parametrize("key,case", [p for p in _cases() if "newer" in p.values[1].extra])
def test_a_newer_release_is_reported_once_it_appears(monkeypatch, key, case):
    pages, version = case.extra["newer"]
    recipe, _ = use(monkeypatch, RECIPES[key](), {**case.pages, **pages})
    assert recipe.fetch_download_info(case.flavor).version == version


@pytest.mark.parametrize("key,case", [p for p in _cases() if p.values[1].extra.get("sha256")])
def test_the_published_checksum_comes_with_the_image(monkeypatch, key, case):
    recipe, _ = use(monkeypatch, RECIPES[key](), case.pages)
    assert recipe.fetch_download_info(case.flavor).sha256 == case.extra["sha256"]


# ------------------------------------------------- what each fix is about

def _fetch(monkeypatch, cls, pages, flavor):
    recipe, _ = use(monkeypatch, cls(), pages)
    return recipe.fetch_download_info(flavor)


@pytest.mark.parametrize("status", (403, 429))
def test_ubuntu_refuses_a_newest_series_it_was_not_let_read(monkeypatch, status):
    """Regression: any status but 200 passed over the series, and 26.04 was
    served as current while 26.04.1 answered 429."""
    with pytest.raises(ScrapeError):
        _fetch(monkeypatch, UbuntuRecipe, {**KU_PAGES, KU + "26.04.1/release/": Resp("", status)},
               "kubuntu")


def test_ubuntu_refuses_a_release_whose_image_is_named_another_way(monkeypatch):
    """Regression: a released series whose image was renamed read as not out
    yet, and the previous release was served."""
    cin = "https://cdimage.ubuntu.com/ubuntucinnamon/releases/"
    with pytest.raises(ScrapeError, match="ubuntu-cinnamon-26.10"):
        _fetch(monkeypatch, UbuntuRecipe, {
            META_RELEASE: META,
            cin: _listing("26.04.1/", "26.10/"),
            cin + "26.10/": _listing("release/"),
            cin + "26.10/release/": _listing("ubuntu-cinnamon-26.10-desktop-amd64.iso"),
            cin + "26.04.1/": _listing("release/"),
            cin + "26.04.1/release/": _listing("ubuntucinnamon-26.04.1-desktop-amd64.iso"),
        }, "cinnamon")


def test_ubuntu_takes_a_respin_when_it_is_the_newest(monkeypatch):
    pages = {META_RELEASE: META, UB: _listing("24.04.5/", "24.04.5.1/"),
             UB + "24.04.5.1/": _ubuntu_series("24.04.5", extra=("ubuntu-24.04.5.1-desktop-amd64.iso",))}
    assert _fetch(monkeypatch, UbuntuRecipe, pages, "desktop").filename == "ubuntu-24.04.5.1-desktop-amd64.iso"


def test_ubuntu_passes_over_a_series_past_end_of_life(monkeypatch):
    """Regression: Ubuntu MATE 25.10, past end of life, was served as current
    because it is the newest series Ubuntu MATE built."""
    recipe, session = use(monkeypatch, UbuntuRecipe(), MA_PAGES)
    assert recipe.fetch_download_info("mate").version == "24.04.5"
    assert not [u for u in session.asked if "25.10" in u]
    # While it was supported, it was the current one.
    supported = META.replace("Supported: 0\nDescription: This is the 25.10",
                             "Supported: 1\nDescription: This is the 25.10")
    assert supported != META
    assert _fetch(monkeypatch, UbuntuRecipe, {**MA_PAGES, META_RELEASE: supported}, "mate").version == "25.10"


@pytest.mark.parametrize("failure", (Resp("", 404), "<html>Moved</html>", TimeoutError("timed out")))
def test_ubuntu_refuses_when_the_support_status_cannot_be_read(monkeypatch, failure):
    """Without meta-release, a series past end of life cannot be told apart."""
    with pytest.raises(ScrapeError, match="meta-release"):
        _fetch(monkeypatch, UbuntuRecipe, {**MA_PAGES, META_RELEASE: failure}, "mate")


def test_mint_takes_the_checksum_and_refuses_an_image_the_mirror_lacks(monkeypatch):
    info = _fetch(monkeypatch, MintRecipe, MINT_PAGES, "mate")
    assert info.sha256 == "01" * 32
    # Announced on linuxmint.com before the mirror has it, or without an edition.
    lacking = {**MINT_PAGES, MINT_MIRROR + "22.3/sha256sum.txt": Resp("", 404)}
    with pytest.raises(ScrapeError):
        _fetch(monkeypatch, MintRecipe, lacking, "mate")
    dropped = {**MINT_PAGES, MINT_MIRROR + "22.3/sha256sum.txt": _mint_sums("22.3").replace("mate", "lxqt")}
    with pytest.raises(ScrapeError):
        _fetch(monkeypatch, MintRecipe, dropped, "mate")


def test_mx_refuses_a_newer_final_named_another_way(monkeypatch):
    renamed = {MX: _rss("/Final/Xfce/MX-25.3_Xfce_x64.iso", "/Final/Xfce/MX-26.0_Xfce-x64.iso")}
    with pytest.raises(ScrapeError, match="MX-26.0_Xfce-x64.iso"):
        _fetch(monkeypatch, MXLinuxRecipe, renamed, "xfce")


def test_antix_reports_no_beta_when_only_a_beta_is_newer(monkeypatch):
    """Regression: antiX-27_b1 was read as release 27, under a filename with
    the beta marker dropped."""
    info = _fetch(monkeypatch, AntiXRecipe, ANTIX_PAGES, "full")
    assert info.url == _SF_ANTIX + "antiX-26.1/antiX-26.1_x64-full.iso"


@pytest.mark.parametrize("failure", (Resp("", 403), TimeoutError("timed out")))
def test_devuan_refuses_when_any_codename_cannot_be_read(monkeypatch, failure):
    """Regression: an unreadable excalibur listing was skipped, and daedalus
    5.0.1 served as current."""
    with pytest.raises(ScrapeError):
        _fetch(monkeypatch, DevuanRecipe, {**DEV_PAGES, DEV + "devuan_excalibur/installer-iso/": failure},
               "netinstall")


def test_q4os_follows_the_7_0_names(monkeypatch):
    """Regression: the whole-project feed was read, so 6.9 would have gone on
    matching from /oldstable once 7.0 named its images -plasma and -trinity."""
    pages = {Q4: _rss("/stable/q4os-6.9-x64.r1.iso", "/stable/q4os-7.0-x64-plasma.r1.iso",
                      "/stable/q4os-7.0-x64-trinity.r1.iso", "/stable/q4os-6.9-x64-tde.r1.iso")}
    assert _fetch(monkeypatch, Q4OSRecipe, pages, "plasma").filename == "q4os-7.0-x64-plasma.r1.iso"
    assert _fetch(monkeypatch, Q4OSRecipe, pages, "trinity").filename == "q4os-7.0-x64-trinity.r1.iso"
    # 7.0 with no install CD: 6.9's is not current.
    with pytest.raises(ScrapeError):
        _fetch(monkeypatch, Q4OSRecipe, {Q4: _rss("/stable/q4os-6.9-x64-instcd.r1.iso",
                                                  "/stable/q4os-7.0-x64-plasma.r1.iso")}, "instcd")


def test_grml_reads_the_release_from_grml_org_not_a_mirror(monkeypatch):
    """Regression: download.grml.org redirects to a mirror of its choosing,
    which may not have synced the newest release."""
    recipe, session = use(monkeypatch, GrmlRecipe(), GRML_PAGES)
    info = recipe.fetch_download_info("full")
    assert session.asked == [GRML, GRML_SUMS]
    assert info.url == "https://download.grml.org/grml-full-2026.09-amd64.iso"
