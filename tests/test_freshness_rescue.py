"""Freshness Cases for src/recipes/rescue.py: Clonezilla, GParted Live,
Rescuezilla, ShredOS, netboot.xyz, SystemRescue, Memtest86+, Super GRUB2 Disk
and hrmpf. See tests/freshness.py for what a Case must hold.

Until 2026-10 GParted and Clonezilla took the first image their page named,
Rescuezilla and ShredOS the first matching asset in GitHub's alphabetical
order (for Rescuezilla 2.6.2 that was the noble ISO, not the resolute one
upstream recommends), and SystemRescue and Super GRUB2 Disk took the newest
of the images named as today's are, which a renamed next release would have
left on the previous one.

The GitHub recipes read /releases/latest, a pointer upstream sets, so their
Cases cannot hold older releases or a pre-release: what they pin is the asset
chosen from the release, in any asset order.
"""
import hashlib
import json

import pytest

from src.core.iso_identity import identify
from src.core.recipe_base import ScrapeError
from src.recipes.rescue import (
    ClonezillaRecipe, GPartedRecipe, HrmpfRecipe, MemtestRecipe, NetbootRecipe, RescuezillaRecipe,
    ShredOSRecipe, SuperGrub2Recipe, SystemRescueRecipe)
from tests.freshness import Case, Resp, assert_newest, assert_no_fallback, use


def _rss(*paths):
    return "<rss><channel>" + "".join(
        f"<item><title><![CDATA[{p}]]></title></item>" for p in paths) + "</channel></rss>"


def _checksums(*names):
    """A CHECKSUMS.TXT as Clonezilla and GParted publish one: a block per
    algorithm. B3SUMS are 64 hex digits too, and must not be read as SHA-256."""
    out = []
    for algo, width in (("MD5SUMS", 32), ("SHA1SUMS", 40), ("SHA256SUMS", 64), ("B3SUMS", 64)):
        out.append(f"### {algo}:")
        out += [f"{_hash(algo, n, width)}  {n}" for n in names]
        out.append("")
    return "\n".join(out) + "\n"


def _hash(algo, name, width):
    return hashlib.sha256(f"{algo} {name}".encode()).hexdigest()[:width]


def _release(tag, *names, body=""):
    return json.dumps({"tag_name": tag, "body": body, "assets": [
        {"name": n, "browser_download_url": f"https://github.com/x/releases/download/{tag}/{n}",
         "digest": "sha256:" + _hash("gh", n, 64)} for n in names]})


# -------------------------------------------------------------- Clonezilla

CZ_STABLE = "https://clonezilla.org/downloads/stable/data/CHECKSUMS.TXT"
CZ_ALT = "https://clonezilla.org/downloads/alternative/data/CHECKSUMS.TXT"
# Each branch's file names that branch's build, so the testing builds
# (3.3.4-5, 20261005-resolute) live in files the recipe never reads. These
# list older builds too, which upstream's do not, so that the first line
# is not the answer: 3.3.3-9 sorts above 3.3.3-37 as text.
CZ_STABLE_TXT = _checksums("clonezilla-live-3.3.3-9-amd64.iso", "clonezilla-live-3.3.3-37-amd64.iso",
                           "clonezilla-live-3.3.3-37-amd64.zip", "clonezilla-live-3.2.2-15-amd64.iso")
CZ_ALT_TXT = _checksums("clonezilla-live-20260705-resolute-amd64.iso",
                        "clonezilla-live-20260913-resolute-amd64.iso",
                        "clonezilla-live-20260913-resolute-amd64.zip",
                        "clonezilla-live-20251124-oracular-amd64.iso")

# ----------------------------------------------------------------- GParted

GPARTED = "https://gparted.org/gparted-live/stable/CHECKSUMS.TXT"
GPARTED_TXT = _checksums("gparted-live-1.8.0-2-amd64.iso", "gparted-live-1.8.1-12-amd64.iso",
                         "gparted-live-1.8.1-12-amd64.zip", "gparted-live-1.8.1-6-amd64.iso")

# ------------------------------------------------------------- Rescuezilla

RZ = "https://api.github.com/repos/rescuezilla/rescuezilla/releases/latest"
RZ_NOTES = ("**Download the 64-bit version of the Rescuezilla 2.6.2 version: "
            "[rescuezilla-2.6.2-64bit.resolute.iso](https://github.com/rescuezilla/rescuezilla/"
            "releases/download/2.6.2/rescuezilla-2.6.2-64bit.resolute.iso)**\r\n\r\n"
            "If you have a blank screen, try the alternative ISO image.")
RZ_JSON = _release("2.6.2", "MD5SUM", "rescuezilla-2.6.2-64bit.noble.iso",
                   "rescuezilla-2.6.2-64bit.oracular.iso", "rescuezilla-2.6.2-64bit.questing.iso",
                   "rescuezilla-2.6.2-64bit.resolute.iso", "rescuezilla_2.6.2-1_all.deb",
                   "SHA1SUM", "SHA256SUM", body=RZ_NOTES)

# ----------------------------------------------------------------- ShredOS

SHREDOS = "https://api.github.com/repos/PartialVolume/shredos.x86_64/releases/latest"
_S = "shredos-2025.11_31_{}_v0.42_20260716{}"
SHREDOS_JSON = _release("v2025.11_31_x86-64_0.42", *[
    _S.format(arch, tail) for arch, tail in (
        ("i686", "_lite.img"), ("i686", "_lite.img.sha1"), ("i686", "_lite.iso"),
        ("i686", "_lite_plus-partition.iso"),
        ("x86-64", ".img"), ("x86-64", ".img.sha1"), ("x86-64", ".iso"), ("x86-64", ".iso.sha1"),
        ("x86-64", "_lite.img"), ("x86-64", "_lite.iso"), ("x86-64", "_plus-partition.iso"),
        # Not published yet; would sort ahead of the plain .img ("-" < ".").
        ("x86-64", "-nomodeset.img"))])
# 0.37 as it was published: no "v" before the number, and a Buildroot point
# release for a base. A release named so again must still be found.
_S37 = "shredos-2024.02.2_26.0_{}_0.37_20240610{}"
SHREDOS_037_JSON = _release("v2024.02.2_26.0_x86-64_0.37", *[
    _S37.format(arch, tail) for arch, tail in (
        ("i686", ".img"), ("i686", "_lite.img"), ("x86-64", ".img"), ("x86-64", ".img.sha1"),
        ("x86-64", ".iso"), ("x86-64", "_lite.img"))])

# ------------------------------------------------------------- netboot.xyz

NETBOOT = "https://api.github.com/repos/netbootxyz/netboot.xyz/releases/latest"
NETBOOT_SUMS = "https://github.com/x/releases/download/3.0.3/netboot.xyz-sha256-checksums.txt"
NETBOOT_JSON = _release("3.0.3", "netboot.xyz-arm64.efi", "netboot.xyz-sb.iso", "netboot.xyz.iso",
                        "netboot.xyz-snp.efi", "netboot.xyz.efi", "netboot.xyz-snponly.efi",
                        "netboot.xyz-sha256-checksums.txt")
NETBOOT_SUMS_TXT = "".join(f"{_hash('nb', n, 64)}  {n}\n" for n in (
    "netboot.xyz-sb.iso", "netboot.xyz.iso", "netboot.xyz.efi"))

# ------------------------------------------------------------ SystemRescue

SYSRESC = "https://sourceforge.net/projects/systemrescuecd/rss?path=/sysresccd-x86"
_SR_DL = "https://downloads.sourceforge.net/project/systemrescuecd/sysresccd-x86"


def _sysresc(*versions):
    return [f"/sysresccd-x86/{v}/systemrescue-{v}-amd64.iso{ext}" for v in versions for ext in ("", ".sha256")]


# 9.06 sorts above 13.02 as text; 13.03-beta1 is a pre-release in the same tree.
SYSRESC_PATHS = _sysresc("12.03", "9.06", "13.02", "13.03-beta1", "10.00")
SYSRESC_FEED = _rss(*SYSRESC_PATHS)
SYSRESC_SHA = f"{_SR_DL}/13.02/systemrescue-13.02-amd64.iso.sha256"

# ---------------------------------------------------------------- Memtest86+

MEMTEST = "https://www.memtest.org/"
MEMTEST_SUMS = "https://www.memtest.org/download/v8.10/sha256sum.txt"


def _memtest_links(*versions):
    return "<html><body>" + "".join(
        f'<a href="/download/v{v}/mt86plus_{v}_{s}.iso.zip">{s}</a>\n'
        for v in versions for s in ("x86_64", "x86_64.grub", "i586")) + "</body></html>"


# 8.9 sorts above 8.10 as text; 8.20b1 is a beta named the way the project
# named its last ones.
MEMTEST_PAGE = _memtest_links("8.00", "8.10", "8.9").replace("</body>", (
    '<a href="/download/v8.20b1/mt86plus_8.20b1_x86_64.iso.zip">beta</a>\n</body>'))
MEMTEST_SUMS_TXT = "".join(f"{_hash('mt', n, 64)}  v8.10/{n}\n" for n in (
    "mt86plus_8.10.binaries.zip", "mt86plus_8.10_x86_64.grub.iso.zip", "mt86plus_8.10_x86_64.iso.zip"))

# ------------------------------------------------------------ Super GRUB2

SG2 = "https://sourceforge.net/projects/supergrub2/rss?limit=100"


def _sg2(ver, *platforms):
    folder = f"/{ver}/super_grub2_disk_{ver}/"
    return [folder + f"supergrub2-classic-{ver}-{p}-CD.iso" for p in platforms] + [
        folder + f"supergrub2-classic-{ver}-x86_64_efi-STANDALONE.EFI", f"/{ver}/SHA256SUMS"]


_ALL = ("multiarch", "x86_64_efi", "i386_pc", "i386_efi")
# s4 sorts above s10 as text; a beta of the next series is above both.
SG2_PATHS = [*_sg2("2.06s4", *_ALL), *_sg2("2.06s10", *_ALL), *_sg2("2.08s1-beta1", *_ALL),
             *_sg2("2.06s3", *_ALL)]
SG2_FEED = _rss(*SG2_PATHS)
SG2_SUMS = "https://downloads.sourceforge.net/project/supergrub2/2.06s10/SHA256SUMS"
SG2_SUMS_TXT = "".join(f"{_hash('sg', p, 64)}  ./super_grub2_disk_2.06s10/supergrub2-classic-2.06s10-{p}-CD.iso\n"
                       for p in _ALL)

# ------------------------------------------------------------------- hrmpf

HRMPF = "https://api.github.com/repos/leahneukirchen/hrmpf/releases/latest"
HRMPF_JSON = _release("hrmpf-20251231", "hrmpf-aarch64-20251231.iso", "hrmpf-aarch64-20251231.iso.torrent",
                      "hrmpf-x86_64-20251231.iso", "hrmpf-x86_64-20251231.iso.torrent")


CASES = {
    "clonezilla": [
        Case(pages={CZ_STABLE: CZ_STABLE_TXT}, flavor="stable", newest="3.3.3-37",
             filename="clonezilla-live-3.3.3-37-amd64.iso", newest_urls=(CZ_STABLE,)),
        Case(pages={CZ_ALT: CZ_ALT_TXT}, flavor="alternative", newest="20260913-resolute",
             filename="clonezilla-live-20260913-resolute-amd64.iso", newest_urls=(CZ_ALT,)),
    ],
    "gparted": Case(pages={GPARTED: GPARTED_TXT}, flavor="standard", newest="1.8.1-12",
                    filename="gparted-live-1.8.1-12-amd64.iso", newest_urls=(GPARTED,)),
    "rescuezilla": Case(pages={RZ: RZ_JSON}, flavor="standard", newest="2.6.2",
                        filename="rescuezilla-2.6.2-64bit.resolute.iso", newest_urls=(RZ,)),
    "shredos": [
        Case(pages={SHREDOS: SHREDOS_JSON}, flavor="standard", newest="2025.11_31_x86-64_0.42",
             filename="shredos-2025.11_31_x86-64_v0.42_20260716.img", newest_urls=(SHREDOS,)),
        Case(pages={SHREDOS: SHREDOS_037_JSON}, flavor="standard", newest="2024.02.2_26.0_x86-64_0.37",
             filename="shredos-2024.02.2_26.0_x86-64_0.37_20240610.img", newest_urls=(SHREDOS,)),
    ],
    "netboot": [
        Case(pages={NETBOOT: NETBOOT_JSON, NETBOOT_SUMS: NETBOOT_SUMS_TXT}, flavor=f, newest="3.0.3",
             filename=name, newest_urls=(NETBOOT,))
        for f, name in (("standard", "netboot.xyz-3.0.3.iso"), ("efi", "netboot.xyz-3.0.3.efi"),
                        ("snp", "netboot.xyz-snp-3.0.3.efi"))
    ],
    "systemrescue": Case(pages={SYSRESC: SYSRESC_FEED, SYSRESC_SHA: "ab" * 32 + " *systemrescue-13.02-amd64.iso\n"},
                         flavor="standard", newest="13.02", filename="systemrescue-13.02-amd64.iso",
                         newest_urls=(SYSRESC,)),
    "memtest": [
        Case(pages={MEMTEST: MEMTEST_PAGE, MEMTEST_SUMS: MEMTEST_SUMS_TXT}, flavor=f, newest="8.10",
             filename=name, newest_urls=(MEMTEST,))
        for f, name in (("x86_64", "memtest86plus-8.10-x86_64.iso"),
                        ("grub", "memtest86plus-8.10-x86_64.grub.iso"))
    ],
    "supergrub2": [
        Case(pages={SG2: SG2_FEED, SG2_SUMS: SG2_SUMS_TXT}, flavor=f, newest="2.06s10",
             filename=f"supergrub2-classic-2.06s10-{p}-CD.iso", newest_urls=(SG2,))
        for f, p in (("multiarch", "multiarch"), ("x86_64-efi", "x86_64_efi"), ("i386-pc", "i386_pc"))
    ],
    "hrmpf": Case(pages={HRMPF: HRMPF_JSON}, flavor="standard", newest="20251231",
                  filename="hrmpf-x86_64-20251231.iso", newest_urls=(HRMPF,)),
}

EXEMPT = {}

RECIPES = {cls.key: cls for cls in (
    ClonezillaRecipe, GPartedRecipe, RescuezillaRecipe, ShredOSRecipe, NetbootRecipe,
    SystemRescueRecipe, MemtestRecipe, SuperGrub2Recipe, HrmpfRecipe)}


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
    assert found is not None, f"no rule reads {case.filename}"
    assert (found.key, found.flavor_id, found.version) == (key, case.flavor, case.newest)


def test_the_recipes_here_are_the_whole_module():
    import src.recipes.rescue as module
    from src.core.recipe_base import DistroRecipe
    defined = {c.key for c in vars(module).values()
               if isinstance(c, type) and issubclass(c, DistroRecipe) and c is not DistroRecipe}
    assert defined == set(RECIPES) == set(CASES) | set(EXEMPT)


# ------------------------------------------------ a newer release appears

def _newer(key):
    """(pages, flavor, version) with a release newer than the Case's added."""
    if key == "clonezilla":
        return {CZ_STABLE: _checksums("clonezilla-live-3.3.3-37-amd64.iso",
                                      "clonezilla-live-3.3.4-2-amd64.iso")}, "stable", "3.3.4-2"
    if key == "gparted":
        return {GPARTED: _checksums("gparted-live-1.8.1-12-amd64.iso",
                                    "gparted-live-1.9.0-1-amd64.iso")}, "standard", "1.9.0-1"
    if key == "systemrescue":
        return ({SYSRESC: _rss(*_sysresc("13.10"), *SYSRESC_PATHS),
                 f"{_SR_DL}/13.10/systemrescue-13.10-amd64.iso.sha256": ""}, "standard", "13.10")
    if key == "memtest":
        return ({MEMTEST: _memtest_links("8.10", "8.11"),
                 "https://www.memtest.org/download/v8.11/sha256sum.txt": ""}, "x86_64", "8.11")
    if key == "supergrub2":
        return ({SG2: _rss(*_sg2("2.06s11", *_ALL), *SG2_PATHS),
                 "https://downloads.sourceforge.net/project/supergrub2/2.06s11/SHA256SUMS": ""},
                "multiarch", "2.06s11")
    raise KeyError(key)



@pytest.mark.parametrize("key", ["clonezilla", "gparted", "systemrescue", "memtest", "supergrub2"])
def test_a_newer_release_is_reported_as_soon_as_it_is_listed(monkeypatch, key):
    pages, flavor, version = _newer(key)
    recipe, session = use(monkeypatch, RECIPES[key](), pages)
    assert recipe.fetch_download_info(flavor).version == version
    assert not session.missing


# ------------------------------------------------------ recipe by recipe

def test_clonezilla_and_gparted_take_the_sha256_not_the_blake3_sum(monkeypatch):
    recipe, _ = use(monkeypatch, ClonezillaRecipe(), {CZ_STABLE: CZ_STABLE_TXT})
    info = recipe.fetch_download_info("stable")
    assert info.sha256 == _hash("SHA256SUMS", "clonezilla-live-3.3.3-37-amd64.iso", 64)

    recipe, _ = use(monkeypatch, GPartedRecipe(), {GPARTED: GPARTED_TXT})
    assert recipe.fetch_download_info("standard").sha256 == \
        _hash("SHA256SUMS", "gparted-live-1.8.1-12-amd64.iso", 64)


def test_clonezilla_refuses_a_flavor_it_does_not_offer(monkeypatch):
    recipe, session = use(monkeypatch, ClonezillaRecipe(), {})
    with pytest.raises(ScrapeError):
        recipe.fetch_download_info("testing")
    assert session.asked == []


def test_rescuezilla_takes_the_iso_the_release_notes_recommend(monkeypatch):
    # 2.6.1 recommended oracular while also shipping plucky, a newer base:
    # upstream's pick, not the newest codename.
    notes = "**Download the 64-bit version: [rescuezilla-2.6.1-64bit.oracular.iso](https://x/y.iso)**"
    recipe, _ = use(monkeypatch, RescuezillaRecipe(), {RZ: _release(
        "2.6.1", "rescuezilla-2.6.1-32bit.bionic.iso", "rescuezilla-2.6.1-64bit.focal.iso",
        "rescuezilla-2.6.1-64bit.oracular.iso", "rescuezilla-2.6.1-64bit.plucky.iso", body=notes)})
    info = recipe.fetch_download_info("standard")
    assert info.filename == "rescuezilla-2.6.1-64bit.oracular.iso"
    assert info.sha256 == _hash("gh", "rescuezilla-2.6.1-64bit.oracular.iso", 64)


@pytest.mark.parametrize("body", ["", "Download [rescuezilla-2.6.2-64bit.trixie.iso](https://x/y.iso)"])
def test_rescuezilla_refuses_when_the_notes_name_no_iso_it_carries(monkeypatch, body):
    recipe, _ = use(monkeypatch, RescuezillaRecipe(), {RZ: _release(
        "2.6.2", "rescuezilla-2.6.2-64bit.noble.iso", "rescuezilla-2.6.2-64bit.resolute.iso", body=body)})
    with pytest.raises(ScrapeError):
        recipe.fetch_download_info("standard")


def test_netboot_refuses_a_release_candidate_and_an_unknown_flavor(monkeypatch):
    recipe, _ = use(monkeypatch, NetbootRecipe(), {NETBOOT: NETBOOT_JSON.replace('"3.0.3"', '"3.0.4-RC"')})
    with pytest.raises(ScrapeError, match="3.0.4-RC"):
        recipe.fetch_download_info("standard")
    with pytest.raises(ScrapeError, match="unknown"):
        recipe.fetch_download_info("pxe")


def test_systemrescue_refuses_a_newest_release_whose_image_it_cannot_find(monkeypatch):
    # 14.00 renamed its image: the previous release, still in the feed under
    # the old name, is not the answer.
    feed = _rss("/sysresccd-x86/14.00/systemrescue-14.00-x86_64.iso", *SYSRESC_PATHS)
    recipe, session = use(monkeypatch, SystemRescueRecipe(), {SYSRESC: feed})
    with pytest.raises(ScrapeError, match="14.00"):
        recipe.fetch_download_info("standard")
    assert not session.missing


def test_super_grub2_refuses_a_newest_release_without_the_image(monkeypatch):
    # 2.12s1 ships its multiarch ISO under the non-classic name only.
    feed = _rss("/2.12s1/super_grub2_disk_2.12s1/supergrub2-2.12s1-multiarch-CD.iso", "/2.12s1/SHA256SUMS",
                *_sg2("2.06s10", *_ALL))
    recipe, session = use(monkeypatch, SuperGrub2Recipe(), {SG2: feed})
    with pytest.raises(ScrapeError, match="2.12s1"):
        recipe.fetch_download_info("multiarch")
    assert not session.missing


def test_super_grub2_and_systemrescue_take_the_published_sha256(monkeypatch):
    recipe, _ = use(monkeypatch, SuperGrub2Recipe(), {SG2: SG2_FEED, SG2_SUMS: SG2_SUMS_TXT})
    assert recipe.fetch_download_info("i386-pc").sha256 == _hash("sg", "i386_pc", 64)

    recipe, _ = use(monkeypatch, SystemRescueRecipe(), {
        SYSRESC: SYSRESC_FEED, SYSRESC_SHA: "AB" * 32 + " *systemrescue-13.02-amd64.iso\n"})
    assert recipe.fetch_download_info("standard").sha256 == "ab" * 32


def test_a_checksum_that_cannot_be_read_leaves_the_download_unverified(monkeypatch):
    recipe, _ = use(monkeypatch, MemtestRecipe(), {MEMTEST: MEMTEST_PAGE, MEMTEST_SUMS: Resp("", 503)})
    info = recipe.fetch_download_info("x86_64")
    assert (info.version, info.sha256) == ("8.10", "")


def test_memtest_checks_the_zip_upstream_summed(monkeypatch):
    recipe, _ = use(monkeypatch, MemtestRecipe(), {MEMTEST: MEMTEST_PAGE, MEMTEST_SUMS: MEMTEST_SUMS_TXT})
    info = recipe.fetch_download_info("grub")
    assert info.archive == "zip"
    assert info.sha256 == _hash("mt", "mt86plus_8.10_x86_64.grub.iso.zip", 64)
