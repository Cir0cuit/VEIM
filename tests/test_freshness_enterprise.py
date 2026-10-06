"""Freshness Cases for src/recipes/enterprise.py: Rocky, Proxmox, Qubes, FreeBSD,
IPFire, Oracle Linux, Talos, CentOS Stream, XCP-ng and openEuler. See
tests/freshness.py for what a Case must hold.

Until 2026-10 three of these could serve an older release as the current one
without a word: Rocky moved on to the previous major when the newest one's
images could not be listed, XCP-ng skipped a series whose first installer
carries no build date - which is how every XCP-ng series has started - and
openEuler skipped a release whose ISOs it did not recognise by name. Talos
trusted GitHub's "latest" flag, which a backport published on an older branch
takes unless upstream says otherwise.
"""
import json

import pytest

from src.core.iso_identity import identify
from src.core.recipe_base import ScrapeError
from src.recipes.enterprise import (
    CentOSStreamRecipe, FreeBSDRecipe, IPFireRecipe, OpenEulerRecipe, OracleLinuxRecipe,
    ProxmoxRecipe, QubesRecipe, RockyLinuxRecipe, TalosRecipe, XCPngRecipe)
from tests.freshness import Case, Resp, assert_newest, assert_no_fallback, use

SHA = "ab" * 32
NONE = Resp("", 404)


def _links(*urls):
    return "<html><body><pre>" + "".join(f'<a href="{u}">{u.split("/")[-1]}</a>\n' for u in urls) + "</pre></body></html>"


def _dirs(*names):
    return _links(*(f"{n}/" for n in names))


# -------------------------------------------------------------------- Rocky

ROCKY = RockyLinuxRecipe.ROOT
ROCKY_10, ROCKY_9 = f"{ROCKY}10/isos/x86_64/", f"{ROCKY}9/isos/x86_64/"
# Rocky publishes no pre-release major in this tree; a bare "11/" with no
# images is refused rather than skipped (see the test below).
ROCKY_ROOT = _dirs("9", "10.9", "8", "10", "10.10", "9.8", "8.10")
ROCKY_10_LINKS = (
    "Rocky-10.9-x86_64-dvd1.iso",
    "Rocky-10.10-x86_64-dvd1.iso",
    "Rocky-10.11-beta-x86_64-dvd1.iso",
    "Rocky-10-latest-x86_64-dvd.iso",
    "Rocky-10.2-x86_64-dvd1.iso",
    "Rocky-10.10-x86_64-boot.iso",
)
ROCKY_PAGES = {
    ROCKY: ROCKY_ROOT,
    ROCKY_10: _links(*ROCKY_10_LINKS),
    ROCKY_10 + "Rocky-10.10-x86_64-dvd1.iso.CHECKSUM":
        "# Rocky-10.10-x86_64-dvd1.iso: 10226171904 bytes\n"
        f"SHA256 (Rocky-10.10-x86_64-dvd1.iso) = {SHA}\n",
    ROCKY_9: _links("Rocky-9.8-x86_64-dvd1.iso"),
}

# ------------------------------------------------------------------ Proxmox

PVE = "https://enterprise.proxmox.com/iso/"
PVE_NAMES = (
    "proxmox-ve_9.9-1.iso",
    "proxmox-mail-gateway_9.0-1.iso",
    "proxmox-ve_9.10-1.iso",
    "proxmox-ve_9.10-1-arm64.iso",          # the same release for another architecture
    "proxmox-ve_10.0-BETA-1.iso",
    "proxmox-mail-gateway_9.1-1.iso",
    "proxmox-mail-gateway_8.2-1.iso",
    "proxmox-mailgateway_7.3-1.iso",        # the name it had until 8.0
    "proxmox-backup-server_4.2-1.iso",
    "proxmox-ve_8.4-1.iso",
)
PVE_PAGES = {
    PVE: _links(*(f"./{n}" for n in PVE_NAMES), *(f"./{n}.sha256" for n in PVE_NAMES)),
    PVE + "SHA256SUMS": "".join(f"{('%02x' % i) * 32}  {n}\n" for i, n in enumerate(PVE_NAMES)),
}

# -------------------------------------------------------------------- Qubes

QUBES = "https://ftp.qubes-os.org/iso/"
QUBES_NAMES = (
    "Qubes-R4.9.1-x86_64.iso",
    "Qubes-R4.10.0-rc1-x86_64.iso",
    "Qubes-R4.10.0-x86_64.iso",
    "Qubes-R4.10.1-rc1-x86_64.iso",
    "Qubes-R4.2.4-x86_64.iso",
)
QUBES_PAGE = _links(*(f"{n[:-4]}/" for n in QUBES_NAMES), *QUBES_NAMES, *(f"{n}.DIGESTS" for n in QUBES_NAMES))
QUBES_DIGESTS = (f"{'cd' * 64} *Qubes-R4.10.0-x86_64.iso\n"
                 f"{SHA} *Qubes-R4.10.0-x86_64.iso\n")

# ------------------------------------------------------------------ FreeBSD

FB = FreeBSDRecipe.ROOT
FB_PAGES = {
    # "9.3" sorts above "15.1" as text.
    FB: _dirs("14.5", "15.1", "9.3", "15.2", "10.4"),
    FB + "15.2/": _links("FreeBSD-15.2-BETA1-amd64-disc1.iso", "FreeBSD-15.2-BETA1-amd64-dvd1.iso"),
    FB + "15.1/": _links("FreeBSD-15.1-RELEASE-amd64-bootonly.iso", "FreeBSD-15.1-RELEASE-amd64-disc1.iso",
                         "FreeBSD-15.1-RELEASE-amd64-dvd1.iso", "CHECKSUM.SHA256-FreeBSD-15.1-RELEASE-amd64"),
    FB + "15.1/CHECKSUM.SHA256-FreeBSD-15.1-RELEASE-amd64":
        f"SHA256 (FreeBSD-15.1-RELEASE-amd64-bootonly.iso) = {'ef' * 32}\n"
        f"SHA256 (FreeBSD-15.1-RELEASE-amd64-disc1.iso) = {SHA}\n",
    FB + "14.5/": _links("FreeBSD-14.5-RELEASE-amd64-disc1.iso"),
    FB + "14.5/CHECKSUM.SHA256-FreeBSD-14.5-RELEASE-amd64": "",
    FB + "10.4/": _links("FreeBSD-10.4-RELEASE-amd64-disc1.iso"),
    FB + "10.4/CHECKSUM.SHA256-FreeBSD-10.4-RELEASE-amd64": "",
    FB + "9.3/": _links("FreeBSD-9.3-RELEASE-amd64-disc1.iso"),
    FB + "9.3/CHECKSUM.SHA256-FreeBSD-9.3-RELEASE-amd64": "",
}

# ------------------------------------------------------------------- IPFire

IPFIRE = "https://www.ipfire.org/downloads"
_IPF = "https://downloads.ipfire.org/releases/ipfire-2.x"
IPFIRE_LINKS = (
    f"{_IPF}/2.29-core99/ipfire-2.29-core99-x86_64.iso",
    f"{_IPF}/2.29-core203/ipfire-2.29-core203-aarch64.iso",
    f"{_IPF}/2.29-core203/ipfire-2.29-core203-x86_64.iso",
    # A Core Update in testing is built on nightly.ipfire.org, not released.
    "https://nightly.ipfire.org/next/latest/x86_64/ipfire-2.29-core204-x86_64.iso",
    f"{_IPF}/2.9-core300/ipfire-2.9-core300-x86_64.iso",     # 2.9 is older than 2.29
    f"{_IPF}/2.27-core180/ipfire-2.27-core180-x86_64.iso",
)

# ------------------------------------------------------------------- Oracle

ORACLE = "https://yum.oracle.com/oracle-linux-isos.html"
_OL = "https://yum.oracle.com/ISOS/OracleLinux"
ORACLE_LINKS = (
    f"{_OL}/OL9/u9/x86_64/OracleLinux-R9-U9-x86_64-dvd.iso",
    f"{_OL}/OL10/u2/x86_64/OracleLinux-R10-U2-x86_64-boot.iso",
    f"{_OL}/OL10/u10/x86_64/OracleLinux-R10-U10-x86_64-dvd.iso",
    f"{_OL}/OL11/u0/x86_64/OracleLinux-R11-U0-Beta-x86_64-dvd.iso",
    f"{_OL}/OL10/u9/x86_64/OracleLinux-R10-U9-x86_64-dvd.iso",
    f"{_OL}/OL10/u2/x86_64/OracleLinux-R10-U2-x86_64-dvd.iso",
    f"{_OL}/OL8/u10/x86_64/OracleLinux-R8-U10-x86_64-dvd.iso",
)

# -------------------------------------------------------------------- Talos

TALOS = TalosRecipe.RELEASES
_GH = "https://github.com/siderolabs/talos/releases/download"


def _talos(tag, prerelease=False, draft=False, iso=True):
    names = ["metal-arm64.iso", "talosctl-linux-amd64"] + (["metal-amd64.iso"] if iso else [])
    return {"tag_name": tag, "prerelease": prerelease, "draft": draft,
            "assets": [{"name": n, "browser_download_url": f"{_GH}/{tag}/{n}"} for n in names]}


TALOS_RELEASES = [
    _talos("v1.13.11"),                 # a backport published after the newest final
    _talos("v1.14.3", draft=True),
    _talos("v1.14.2"),
    _talos("v1.15.0-alpha.0", prerelease=True),
    _talos("v1.9.6"),                   # sorts above 1.14 as text
    _talos("v1.14.1"),
]

# ------------------------------------------------------------ CentOS Stream

CENTOS = CentOSStreamRecipe.ROOT
CENTOS_10 = f"{CENTOS}10-stream/BaseOS/x86_64/iso/"
CENTOS_9 = f"{CENTOS}9-stream/BaseOS/x86_64/iso/"
# A stream that has no images yet is refused rather than skipped, so there is
# no pre-release stream here; the "9" vs "10" pair is the text trap.
CENTOS_10_LINKS = (
    "CentOS-Stream-10-20260831.0-x86_64-dvd1.iso",
    "CentOS-Stream-10-20260930.0-x86_64-dvd1.iso",
    "CentOS-Stream-10-latest-x86_64-dvd1.iso",
    "CentOS-Stream-10-20260914.0-x86_64-dvd1.iso",
    "CentOS-Stream-10-20260930.0-x86_64-boot.iso",
)
CENTOS_PAGES = {
    CENTOS: _dirs("SIGs", "9-stream", "10-stream", "8-stream"),
    CENTOS_10: _links(*CENTOS_10_LINKS),
    CENTOS_10 + "CentOS-Stream-10-20260930.0-x86_64-dvd1.iso.SHA256SUM":
        f"# CentOS-Stream-10-20260930.0-x86_64-dvd1.iso: 8 bytes\n"
        f"SHA256 (CentOS-Stream-10-20260930.0-x86_64-dvd1.iso) = {SHA}\n",
    CENTOS_9: _links("CentOS-Stream-9-20260929.0-x86_64-dvd1.iso"),
}

# ------------------------------------------------------------------- XCP-ng

XCP = XCPngRecipe.ROOT
XCP_83 = (
    "old/", "SHA256SUMS",
    "xcp-ng-8.3.0-20250606-netinstall.iso",
    "xcp-ng-8.3.0-20250606.2.iso",
    "xcp-ng-8.3.0-20260806.iso",
    "xcp-ng-8.3.0-20250606.iso",
    "xcp-ng-8.3.0-20260806-netinstall.iso",
)
XCP_PAGES = {
    XCP: _dirs("7.6", "8.2", "9.0", "8.3", "drivers"),
    # A series opens with its betas: 8.3 did, for over a year, under 8.2.
    XCP + "9.0/": _links("SHA256SUMS", "xcp-ng-9.0.0-beta1.iso", "xcp-ng-9.0.0-beta1-netinstall.iso",
                         "xcp-ng-9.0.0-rc1.iso", "xcp-ng-9.0.0-rc1-netinstall.iso"),
    XCP + "8.3/": _links(*XCP_83),
    XCP + "8.3/SHA256SUMS": f"{'01' * 32}  xcp-ng-8.3.0-20250606.iso\n{SHA}  xcp-ng-8.3.0-20260806.iso\n",
    XCP + "8.2/": _links("xcp-ng-8.2.0.iso", "xcp-ng-8.2.1-20231130.iso", "xcp-ng-8.2.1.iso"),
    XCP + "8.2/SHA256SUMS": "",
}
# Ten years on: "9.0" sorts above "10.0" as text, and 10.0's first image is
# undated, as 8.0, 8.2 and 8.3's were.
XCP_LATER = {
    XCP: _dirs("9.0", "10.0", "8.3", "10.1"),
    XCP + "10.1/": _links("xcp-ng-10.1.0-rc1.iso", "xcp-ng-10.1.0-rc1-netinstall.iso"),
    XCP + "10.0/": _links("xcp-ng-10.0.0-beta1.iso", "xcp-ng-10.0.0.iso", "xcp-ng-10.0.0-rc2.iso",
                          "xcp-ng-10.0.0-netinstall.iso"),
    XCP + "10.0/SHA256SUMS": NONE,
    XCP + "9.0/": _links("xcp-ng-9.0.0.iso", "xcp-ng-9.0.2-20300101.iso", "xcp-ng-9.0.0-netinstall.iso"),
    XCP + "9.0/SHA256SUMS": "",
    XCP + "8.3/": _links(*XCP_83),
    XCP + "8.3/SHA256SUMS": "",
}

# ---------------------------------------------------------------- openEuler

EULER = OpenEulerRecipe.ROOT


def _euler_iso(release, *extra):
    names = (f"openEuler-{release}-x86_64-dvd.iso", f"openEuler-{release}-netinst-x86_64-dvd.iso",
             f"openEuler-{release}-everything-x86_64-dvd.iso")
    return _links(*names, *(f"{n}.sha256sum" for n in names), f"openEuler-{release}-x86_64.rpmlist", *extra)


EULER_PAGES = {
    EULER: _dirs("openEuler-22.03-LTS-SP4", "openEuler-22.03-LTS-64kb", "openEuler-24.03-LTS",
                 "openEuler-24.03-LTS-SP9", "openEuler-25.09", "openEuler-24.03-LTS-SP10",
                 "openEuler-26.09", "openEuler-26.03-LTS", "openEuler-25.03", "openEuler-27.03",
                 "openEuler-Embedded-26.03", "openEuler-preview"),
    # Announced: the folder is up, the ISO folder empty or not there yet.
    EULER + "openEuler-26.03-LTS/ISO/x86_64/": _links("baseos_bin_2_src.csv"),
    EULER + "openEuler-27.03/ISO/x86_64/": NONE,
    EULER + "openEuler-24.03-LTS-SP10/ISO/x86_64/": _euler_iso("24.03-LTS-SP10"),
    EULER + "openEuler-24.03-LTS-SP10/ISO/x86_64/openEuler-24.03-LTS-SP10-x86_64-dvd.iso.sha256sum":
        f"{SHA}  openEuler-24.03-LTS-SP10-x86_64-dvd.iso\n",
    EULER + "openEuler-24.03-LTS-SP9/ISO/x86_64/": _euler_iso("24.03-LTS-SP9"),
    EULER + "openEuler-26.09/ISO/x86_64/": _euler_iso("26.09", "openEuler-26.09-DevStation-x86_64-dvd.iso"),
    EULER + "openEuler-26.09/ISO/x86_64/openEuler-26.09-netinst-x86_64-dvd.iso.sha256sum":
        f"{SHA}  openEuler-26.09-netinst-x86_64-dvd.iso\n",
    EULER + "openEuler-25.09/ISO/x86_64/": _euler_iso("25.09"),
}


# --------------------------------------------------------------------- Cases

CASES = {
    "rocky": [
        Case(pages=ROCKY_PAGES, flavor="dvd", newest="10.10", filename="Rocky-10.10-x86_64-dvd1.iso",
             newest_urls=(ROCKY, ROCKY_10),
             extra={"sha256": SHA,
                    "newer": ({ROCKY_10: _links(*ROCKY_10_LINKS, "Rocky-10.11-x86_64-dvd1.iso"),
                               ROCKY_10 + "Rocky-10.11-x86_64-dvd1.iso.CHECKSUM": NONE}, "10.11")}),
    ],
    "proxmox": [
        Case(pages=PVE_PAGES, flavor="installer", newest="9.10-1", filename="proxmox-ve_9.10-1.iso",
             newest_urls=(PVE,),
             extra={"sha256": "02" * 32,
                    "newer": ({PVE: _links("./proxmox-ve_9.11-1.iso", *PVE_NAMES)}, "9.11-1")}),
        Case(pages=PVE_PAGES, flavor="mail-gateway", newest="9.1-1", filename="proxmox-mail-gateway_9.1-1.iso",
             newest_urls=(PVE,)),
    ],
    "qubes": [
        Case(pages={QUBES: QUBES_PAGE, QUBES + "Qubes-R4.10.0-x86_64.iso.DIGESTS": QUBES_DIGESTS},
             flavor="installer", newest="4.10.0", filename="Qubes-R4.10.0-x86_64.iso", newest_urls=(QUBES,),
             extra={"sha256": SHA,
                    "newer": ({QUBES: _links(*QUBES_NAMES, "Qubes-R4.10.1-x86_64.iso"),
                               QUBES + "Qubes-R4.10.1-x86_64.iso.DIGESTS": NONE}, "4.10.1"),
                    "pre_only": ({QUBES: _links("Qubes-R4.9.1-x86_64.iso", "Qubes-R4.10.0-rc1-x86_64.iso"),
                                  QUBES + "Qubes-R4.9.1-x86_64.iso.DIGESTS": NONE}, "4.9.1")}),
    ],
    "freebsd": [
        Case(pages=FB_PAGES, flavor="disc1", newest="15.1", filename="FreeBSD-15.1-RELEASE-amd64-disc1.iso",
             newest_urls=(FB, FB + "15.2/", FB + "15.1/"),
             extra={"sha256": SHA,
                    "newer": ({FB + "15.2/": _links("FreeBSD-15.2-RELEASE-amd64-disc1.iso"),
                               FB + "15.2/CHECKSUM.SHA256-FreeBSD-15.2-RELEASE-amd64": NONE}, "15.2")}),
    ],
    "ipfire": [
        Case(pages={IPFIRE: _links(*IPFIRE_LINKS)}, flavor="standard", newest="2.29 Core 203",
             filename="ipfire-2.29-core203-x86_64.iso", newest_urls=(IPFIRE,),
             extra={"newer": ({IPFIRE: _links(*IPFIRE_LINKS, f"{_IPF}/2.29-core204/ipfire-2.29-core204-x86_64.iso")},
                              "2.29 Core 204")}),
    ],
    "oracle": [
        Case(pages={ORACLE: _links(*ORACLE_LINKS)}, flavor="dvd", newest="10.10",
             filename="OracleLinux-R10-U10-x86_64-dvd.iso", newest_urls=(ORACLE,),
             extra={"newer": ({ORACLE: _links(*ORACLE_LINKS, f"{_OL}/OL11/u0/x86_64/OracleLinux-R11-U0-x86_64-dvd.iso")},
                              "11.0")}),
        Case(pages={ORACLE: _links(*ORACLE_LINKS)}, flavor="boot", newest="10.2",
             filename="OracleLinux-R10-U2-x86_64-boot.iso", newest_urls=(ORACLE,)),
    ],
    "talos": [
        Case(pages={TALOS: json.dumps(TALOS_RELEASES)}, flavor="metal", newest="1.14.2",
             filename="talos-1.14.2-metal-amd64.iso", newest_urls=(TALOS,),
             extra={"newer": ({TALOS: json.dumps([_talos("v1.14.3"), *TALOS_RELEASES])}, "1.14.3"),
                    "pre_only": ({TALOS: json.dumps([_talos("v1.14.2"), _talos("v1.15.0-rc.1", prerelease=True),
                                                     _talos("v1.15.0", prerelease=True)])}, "1.14.2")}),
    ],
    "centos": [
        Case(pages=CENTOS_PAGES, flavor="dvd", newest="10 (20260930.0)",
             filename="CentOS-Stream-10-20260930.0-x86_64-dvd1.iso", newest_urls=(CENTOS, CENTOS_10),
             extra={"sha256": SHA,
                    "newer": ({CENTOS_10: _links(*CENTOS_10_LINKS, "CentOS-Stream-10-20261006.0-x86_64-dvd1.iso"),
                               CENTOS_10 + "CentOS-Stream-10-20261006.0-x86_64-dvd1.iso.SHA256SUM": NONE},
                              "10 (20261006.0)")}),
    ],
    "xcpng": [
        Case(pages=XCP_PAGES, flavor="standard", newest="8.3.0 (20260806)", filename="xcp-ng-8.3.0-20260806.iso",
             newest_urls=(XCP, XCP + "9.0/", XCP + "8.3/"),
             extra={"sha256": SHA,
                    "newer": ({XCP + "9.0/": _links("xcp-ng-9.0.0-rc1.iso", "xcp-ng-9.0.0.iso"),
                               XCP + "9.0/SHA256SUMS": NONE}, "9.0.0")}),
        Case(pages=XCP_PAGES, flavor="netinstall", newest="8.3.0 (20260806)",
             filename="xcp-ng-8.3.0-20260806-netinstall.iso", newest_urls=(XCP, XCP + "9.0/", XCP + "8.3/")),
        Case(pages=XCP_LATER, flavor="standard", newest="10.0.0", filename="xcp-ng-10.0.0.iso",
             newest_urls=(XCP, XCP + "10.1/", XCP + "10.0/")),
    ],
    "openeuler": [
        Case(pages=EULER_PAGES, flavor="lts", newest="24.03-LTS-SP10",
             filename="openEuler-24.03-LTS-SP10-x86_64-dvd.iso",
             newest_urls=(EULER, EULER + "openEuler-26.03-LTS/ISO/x86_64/",
                          EULER + "openEuler-24.03-LTS-SP10/ISO/x86_64/"),
             extra={"sha256": SHA,
                    "newer": ({EULER + "openEuler-26.03-LTS/ISO/x86_64/": _euler_iso("26.03-LTS"),
                               EULER + "openEuler-26.03-LTS/ISO/x86_64/openEuler-26.03-LTS-x86_64-dvd.iso.sha256sum":
                                   NONE}, "26.03-LTS")}),
        Case(pages=EULER_PAGES, flavor="innovation-netinst", newest="26.09",
             filename="openEuler-26.09-netinst-x86_64-dvd.iso",
             newest_urls=(EULER, EULER + "openEuler-27.03/ISO/x86_64/", EULER + "openEuler-26.09/ISO/x86_64/"),
             extra={"sha256": SHA}),
    ],
}

EXEMPT = {}

RECIPES = {cls.key: cls for cls in (
    RockyLinuxRecipe, ProxmoxRecipe, QubesRecipe, FreeBSDRecipe, IPFireRecipe, OracleLinuxRecipe,
    TalosRecipe, CentOSStreamRecipe, XCPngRecipe, OpenEulerRecipe)}


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
def test_the_published_checksum_comes_with_the_image(monkeypatch, key, case):
    recipe, _ = use(monkeypatch, RECIPES[key](), case.pages)
    assert recipe.fetch_download_info(case.flavor).sha256 == case.extra["sha256"]


@pytest.mark.parametrize("key,case", [p for p in _cases() if p.values[1].filename])
def test_iso_identity_reads_the_filename_back(key, case):
    found = identify(case.filename)
    assert found is not None, case.filename
    assert (found.key, found.flavor_id, found.version) == (key, case.flavor, case.newest)


# ------------------------------------------------------------- refusals

@pytest.mark.parametrize("new_major", [NONE, _links("CHECKSUM", "Rocky-11-latest-x86_64-dvd.iso")],
                         ids=["404", "no-image"])
def test_rocky_does_not_fall_back_to_an_older_major(monkeypatch, new_major):
    pages = {**ROCKY_PAGES, ROCKY: _dirs("9", "10", "11"), f"{ROCKY}11/isos/x86_64/": new_major}
    recipe, _ = use(monkeypatch, RockyLinuxRecipe(), pages)
    with pytest.raises(ScrapeError) as err:
        recipe.fetch_download_info("dvd")
    assert "rockylinux" in err.value.reason or "Rocky Linux 11" in err.value.reason


def test_talos_refuses_a_newest_release_whose_image_is_not_up_yet(monkeypatch):
    """Its assets upload after the release is published; 1.14.1 is not current meanwhile."""
    recipe, _ = use(monkeypatch, TalosRecipe(), {TALOS: json.dumps([_talos("v1.14.2", iso=False), _talos("v1.14.1")])})
    with pytest.raises(ScrapeError):
        recipe.fetch_download_info("metal")


@pytest.mark.parametrize("flavor,listing", [
    ("standard", _links("xcp-ng-9.0.0-beta1.iso", "xcp-ng-9.0.0-x86_64.iso")),
    ("netinstall", _links("xcp-ng-9.0.0-rc1-netinstall.iso", "xcp-ng-9.0.0.iso")),
], ids=["renamed", "no-netinstall-yet"])
def test_xcpng_refuses_a_newer_series_it_cannot_read(monkeypatch, flavor, listing):
    """8.3 is not current because 9.0's release is named some other way."""
    recipe, _ = use(monkeypatch, XCPngRecipe(), {**XCP_PAGES, XCP + "9.0/": listing,
                                                 XCP + "9.0/SHA256SUMS": NONE})
    with pytest.raises(ScrapeError) as err:
        recipe.fetch_download_info(flavor)
    assert "9.0" in err.value.reason


def test_openeuler_refuses_a_newer_release_it_cannot_read(monkeypatch):
    """26.03-LTS has images, under a name this does not know; SP10 is not current."""
    pages = {**EULER_PAGES, EULER + "openEuler-26.03-LTS/ISO/x86_64/": _links(
        "openEuler-26.03-LTS-server-x86_64-dvd.iso", "openEuler-26.03-LTS-everything-x86_64-dvd.iso")}
    recipe, _ = use(monkeypatch, OpenEulerRecipe(), pages)
    with pytest.raises(ScrapeError) as err:
        recipe.fetch_download_info("lts")
    assert "26.03-LTS" in err.value.reason
