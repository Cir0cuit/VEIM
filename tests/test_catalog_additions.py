"""The entries and editions added on 2026-09-21, against captured listings.

Runs offline. Each case is one of the ways a recipe ends up offering the wrong
thing: a pre-release that sits in the same folder as the release, versions
compared as text, an edition mistaken for one with a similar name, or an older
release served because the newest could not be read.
"""
import json

import pytest

from src.core.recipe_base import ScrapeError
from src.recipes.enterprise import (
    CentOSStreamRecipe, FreeBSDRecipe, IPFireRecipe, OpenEulerRecipe, OracleLinuxRecipe,
    ProxmoxRecipe, TalosRecipe, XCPngRecipe)
from src.recipes.modern_desktop import LinuxLiteRecipe
from src.recipes.rescue import HrmpfRecipe, SuperGrub2Recipe
from src.recipes.security import CaineRecipe, KaliRecipe
from src.recipes.ubuntu import UbuntuRecipe
from tests.test_stale_recipes import _Resp, _listing, _with


def _rss(*paths):
    return "<rss>" + "".join(f"<item><title><![CDATA[{p}]]></title></item>" for p in paths) + "</rss>"


# ------------------------------------------------------------------ FreeBSD

FREEBSD = FreeBSDRecipe.ROOT


def test_freebsd_skips_a_release_that_is_still_in_beta(monkeypatch):
    recipe, _ = _with(monkeypatch, FreeBSDRecipe(), {
        FREEBSD: _listing("../", "14.5/", "15.1/", "15.2/"),
        FREEBSD + "15.2/": _listing("FreeBSD-15.2-BETA1-amd64-disc1.iso"),
        FREEBSD + "15.1/": _listing("FreeBSD-15.1-RELEASE-amd64-disc1.iso", "FreeBSD-15.1-RELEASE-amd64-dvd1.iso"),
        FREEBSD + "15.1/CHECKSUM.SHA256-FreeBSD-15.1-RELEASE-amd64":
            "SHA256 (FreeBSD-15.1-RELEASE-amd64-disc1.iso) = " + "b" * 64 + "\n",
    })
    info = recipe.fetch_download_info("disc1")

    assert (info.version, info.filename) == ("15.1", "FreeBSD-15.1-RELEASE-amd64-disc1.iso")
    assert info.sha256 == "b" * 64


def test_freebsd_does_not_fall_back_when_the_mirror_fails(monkeypatch):
    recipe, _ = _with(monkeypatch, FreeBSDRecipe(), {
        FREEBSD: _listing("14.5/", "15.1/"),
        FREEBSD + "15.1/": TimeoutError("timed out"),
        FREEBSD + "14.5/": _listing("FreeBSD-14.5-RELEASE-amd64-disc1.iso"),
    })
    with pytest.raises(ScrapeError):
        recipe.fetch_download_info("disc1")


# --------------------------------------------------- IPFire, Oracle, Proxmox

def test_ipfire_takes_the_highest_core_update(monkeypatch):
    base = "https://downloads.ipfire.org/releases/ipfire-2.x/"
    recipe, _ = _with(monkeypatch, IPFireRecipe(), {
        "https://www.ipfire.org/downloads": _listing(
            base + "2.29-core99/ipfire-2.29-core99-x86_64.iso",
            base + "2.29-core203/ipfire-2.29-core203-x86_64.iso"),
    })
    info = recipe.fetch_download_info("standard")

    assert info.version == "2.29 Core 203", "core99 sorts above core203 as text"
    assert info.filename == "ipfire-2.29-core203-x86_64.iso"


def test_oracle_ranks_releases_as_numbers(monkeypatch):
    root = "https://yum.oracle.com/ISOS/OracleLinux/"
    recipe, _ = _with(monkeypatch, OracleLinuxRecipe(), {
        "https://yum.oracle.com/oracle-linux-isos.html": _listing(
            root + "OL9/u8/x86_64/OracleLinux-R9-U8-x86_64-dvd.iso",
            root + "OL10/u2/x86_64/OracleLinux-R10-U2-x86_64-dvd.iso",
            root + "OL10/u2/x86_64/OracleLinux-R10-U2-x86_64-boot.iso"),
    })
    dvd = recipe.fetch_download_info("dvd")

    assert (dvd.version, dvd.filename) == ("10.2", "OracleLinux-R10-U2-x86_64-dvd.iso")
    assert recipe.fetch_download_info("boot").filename.endswith("-boot.iso")


def test_proxmox_products_are_not_taken_for_each_other(monkeypatch):
    recipe, _ = _with(monkeypatch, ProxmoxRecipe(), {
        "https://enterprise.proxmox.com/iso/": _listing(
            "proxmox-ve_8.4-1.iso", "proxmox-ve_9.2-1.iso", "proxmox-backup-server_4.2-1.iso",
            "proxmox-mail-gateway_9.1-1.iso", "proxmox-datacenter-manager_1.1-1.iso"),
    })
    assert recipe.fetch_download_info("installer").filename == "proxmox-ve_9.2-1.iso"
    assert recipe.fetch_download_info("backup-server").version == "4.2-1"
    assert recipe.fetch_download_info("mail-gateway").version == "9.1-1"
    assert recipe.fetch_download_info("datacenter-manager").version == "1.1-1"


# -------------------------------------------------------------------- Talos

def test_talos_is_saved_under_a_name_that_says_which_release_it_is(monkeypatch):
    release = {"tag_name": "v1.14.1", "assets": [
        {"name": "metal-arm64.iso", "browser_download_url": "https://example.invalid/metal-arm64.iso"},
        {"name": "metal-amd64.iso", "browser_download_url": "https://example.invalid/metal-amd64.iso"}]}
    recipe, _ = _with(monkeypatch, TalosRecipe(), {
        "https://api.github.com/repos/siderolabs/talos/releases/latest": json.dumps(release)})
    info = recipe.fetch_download_info("metal")

    assert info.version == "1.14.1"
    assert info.filename == "talos-1.14.1-metal-amd64.iso"
    assert info.url.endswith("/metal-amd64.iso")


# ------------------------------------------------------------ CentOS Stream

def test_centos_stream_names_the_compose_of_the_newest_stream(monkeypatch):
    root = CentOSStreamRecipe.ROOT
    iso_dir = root + "10-stream/BaseOS/x86_64/iso/"
    recipe, _ = _with(monkeypatch, CentOSStreamRecipe(), {
        root: _listing("9-stream/", "10-stream/"),
        iso_dir: _listing("CentOS-Stream-10-20260831.0-x86_64-dvd1.iso",
                          "CentOS-Stream-10-20260914.0-x86_64-dvd1.iso",
                          "CentOS-Stream-10-latest-x86_64-dvd1.iso",
                          "CentOS-Stream-10-20260914.0-x86_64-boot.iso"),
        iso_dir + "CentOS-Stream-10-20260914.0-x86_64-dvd1.iso.SHA256SUM":
            "SHA256 (CentOS-Stream-10-20260914.0-x86_64-dvd1.iso) = " + "c" * 64,
    })
    info = recipe.fetch_download_info("dvd")

    assert info.version == "10 (20260914.0)"
    assert "latest" not in info.filename
    assert info.sha256 == "c" * 64


# ------------------------------------------------------------------- XCP-ng

def test_xcpng_takes_the_newest_refresh_of_the_installer(monkeypatch):
    root = XCPngRecipe.ROOT
    recipe, _ = _with(monkeypatch, XCPngRecipe(), {
        root: _listing("../", "8.2/", "8.3/"),
        root + "8.3/": _listing("old/", "xcp-ng-8.3.0-20250606.iso", "xcp-ng-8.3.0-20250606.2.iso",
                                "xcp-ng-8.3.0-20260806.iso", "xcp-ng-8.3.0-20260806-netinstall.iso"),
    })
    full = recipe.fetch_download_info("standard")
    net = recipe.fetch_download_info("netinstall")

    assert (full.version, full.filename) == ("8.3.0 (20260806)", "xcp-ng-8.3.0-20260806.iso")
    assert net.filename == "xcp-ng-8.3.0-20260806-netinstall.iso"


# ---------------------------------------------------------------- openEuler

EULER = OpenEulerRecipe.ROOT


def _euler_pages():
    return {
        EULER: _listing("openEuler-24.03-LTS/", "openEuler-24.03-LTS-SP3/", "openEuler-24.03-LTS-SP4/",
                        "openEuler-25.03/", "openEuler-25.09/", "openEuler-26.03/"),
        EULER + "openEuler-24.03-LTS-SP4/ISO/x86_64/": _listing(
            "openEuler-24.03-LTS-SP4-x86_64-dvd.iso", "openEuler-24.03-LTS-SP4-netinst-x86_64-dvd.iso"),
        EULER + "openEuler-24.03-LTS-SP4/ISO/x86_64/openEuler-24.03-LTS-SP4-x86_64-dvd.iso.sha256sum":
            "d" * 64 + "  openEuler-24.03-LTS-SP4-x86_64-dvd.iso",
        EULER + "openEuler-25.09/ISO/x86_64/": _listing("openEuler-25.09-x86_64-dvd.iso"),
        # 26.03 is announced - its folder exists - but has no images yet.
    }


def test_openeuler_tells_lts_service_packs_from_innovation_releases(monkeypatch):
    recipe, _ = _with(monkeypatch, OpenEulerRecipe(), _euler_pages())

    lts = recipe.fetch_download_info("lts")
    assert (lts.version, lts.sha256) == ("24.03-LTS-SP4", "d" * 64)
    assert recipe.fetch_download_info("lts-netinst").filename == "openEuler-24.03-LTS-SP4-netinst-x86_64-dvd.iso"
    assert recipe.fetch_download_info("innovation").version == "25.09", "26.03 has no images yet"


def test_openeuler_does_not_fall_back_when_the_mirror_fails(monkeypatch):
    pages = _euler_pages()
    pages[EULER + "openEuler-26.03/ISO/x86_64/"] = _Resp("", 503)
    recipe, _ = _with(monkeypatch, OpenEulerRecipe(), pages)

    with pytest.raises(ScrapeError):
        recipe.fetch_download_info("innovation")


# ------------------------------------------------- SourceForge and GitHub

def test_linux_lite_ignores_release_candidates(monkeypatch):
    recipe, _ = _with(monkeypatch, LinuxLiteRecipe(), {
        "https://sourceforge.net/projects/linux-lite/rss?limit=100": _rss(
            "/8.2/rc1/linux-lite-8.2-rc1-64bit.iso", "/8.0/linux-lite-8.0-64bit.iso",
            "/7.8/linux-lite-7.8-64bit.iso")})
    info = recipe.fetch_download_info("standard")

    assert info.version == "8.0"
    assert info.url == "https://downloads.sourceforge.net/project/linux-lite/8.0/linux-lite-8.0-64bit.iso"


def test_super_grub2_ignores_betas_and_picks_the_platform_asked_for(monkeypatch):
    folder = "/2.06s4/super_grub2_disk_2.06s4/"
    recipe, _ = _with(monkeypatch, SuperGrub2Recipe(), {
        "https://sourceforge.net/projects/supergrub2/rss?limit=100": _rss(
            "/2.06s5-beta1/supergrub2-classic-2.06s5-beta1-multiarch-CD.iso",
            folder + "supergrub2-classic-2.06s4-multiarch-CD.iso",
            folder + "supergrub2-classic-2.06s4-x86_64_efi-CD.iso")})

    assert recipe.fetch_download_info("multiarch").version == "2.06s4"
    assert recipe.fetch_download_info("x86_64-efi").filename == "supergrub2-classic-2.06s4-x86_64_efi-CD.iso"
    with pytest.raises(ScrapeError):
        recipe.fetch_download_info("i386-pc")


def test_hrmpf_takes_the_x86_64_image(monkeypatch):
    release = {"tag_name": "hrmpf-20251231", "assets": [
        {"name": "hrmpf-aarch64-20251231.iso", "browser_download_url": "https://example.invalid/a.iso"},
        {"name": "hrmpf-x86_64-20251231.iso", "browser_download_url": "https://example.invalid/x.iso"}]}
    recipe, _ = _with(monkeypatch, HrmpfRecipe(), {
        "https://api.github.com/repos/leahneukirchen/hrmpf/releases/latest": json.dumps(release)})
    info = recipe.fetch_download_info("standard")

    assert (info.version, info.filename) == ("20251231", "hrmpf-x86_64-20251231.iso")


def test_caine_takes_the_newest_release_from_its_own_host(monkeypatch):
    recipe, _ = _with(monkeypatch, CaineRecipe(), {
        CaineRecipe.PAGE: _listing(
            "https://www.caine-live.net/Downloads/caine9.0.iso",
            "https://cfitaly.net/caine/caine14.0.iso",
            "https://www.caine-live.net/Downloads/caine14.0.iso",
            "https://www.caine-live.net/Downloads/caine13.0.iso")})
    info = recipe.fetch_download_info("standard")

    assert info.version == "14.0", "9.0 sorts above 14.0 as text"
    assert info.url == "https://www.caine-live.net/Downloads/caine14.0.iso"


# ------------------------------------------------------------ Kali, Ubuntu

KALI = "https://cdimage.kali.org/current/"


def test_kali_editions_are_matched_by_their_whole_name(monkeypatch):
    """Regression: matching on a word served the installer for "live", and the
    first link containing "installer" for the installer itself."""
    recipe, _ = _with(monkeypatch, KaliRecipe(), {KALI: _listing(
        "kali-linux-2026.2-installer-netinst-amd64.iso", "kali-linux-2026.2-installer-purple-amd64.iso",
        "kali-linux-2026.2-installer-amd64.iso", "kali-linux-2026.2-live-amd64.iso.torrent")})

    assert recipe.fetch_download_info("installer").filename == "kali-linux-2026.2-installer-amd64.iso"
    assert recipe.fetch_download_info("netinst").filename == "kali-linux-2026.2-installer-netinst-amd64.iso"
    assert recipe.fetch_download_info("purple").filename == "kali-linux-2026.2-installer-purple-amd64.iso"
    # Published by BitTorrent only, so not an edition VEIM can offer.
    assert "live" not in [f.id for f in recipe.get_flavors()]
    with pytest.raises(ScrapeError):
        recipe.fetch_download_info("live")


def test_ubuntu_does_not_serve_the_previous_release_because_of_a_timeout(monkeypatch):
    base = "https://cdimage.ubuntu.com/ubuntucinnamon/releases/"
    recipe, _ = _with(monkeypatch, UbuntuRecipe(), {
        base: _listing("25.10/", "26.04.1/"),
        base + "26.04.1/": TimeoutError("timed out"),
        base + "25.10/release/": _listing("ubuntucinnamon-25.10-desktop-amd64.iso"),
    })
    with pytest.raises(ScrapeError):
        recipe.fetch_download_info("cinnamon")


def test_ubuntu_flavours_are_found_by_their_own_prefix(monkeypatch):
    base = "https://cdimage.ubuntu.com/ubuntu-unity/releases/"
    recipe, _ = _with(monkeypatch, UbuntuRecipe(), {
        base: _listing("24.04.5/", "26.04/"),
        base + "26.04/release/": _listing("ubuntu-unity-26.04-desktop-amd64.iso"),
    })
    info = recipe.fetch_download_info("unity")

    assert (info.version, info.filename) == ("26.04", "ubuntu-unity-26.04-desktop-amd64.iso")
