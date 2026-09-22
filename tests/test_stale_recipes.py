"""Recipes that reported a release, or a label, that had stopped being current.

Runs offline, against captured shapes of what each project publishes. Every
case here is a way a recipe kept working while telling the user something
stale, found on 2026-09-21 by comparing all fifty recipes with DistroWatch and
endoflife.date:

- Pop!_OS read System76's download page, whose markup still carried 22.04
  links after 24.04 shipped, and took the first one.
- openSUSE Leap knew only the 15.x file layout, took 16.0 for a release with
  no images, and went on serving 15.6.
- Tumbleweed, NixOS, AlmaLinux, Rocky and Bazzite reported a label that never
  changes ("Tumbleweed", "26.05", "10-latest", "10", "Stable"), so an image
  downloaded once read as up to date for good.
- Artix and TUXEDO took the first image in a directory listing.
"""
import json

import pytest

from src.core.recipe_base import ScrapeError
from src.recipes.community_desktop import NixOSRecipe, OpenSUSERecipe, TuxedoRecipe
from src.recipes.enterprise import RockyLinuxRecipe
from src.recipes.gaming import BazziteRecipe
from src.recipes.modern_desktop import PopOSRecipe
from src.recipes.specialized import AlmaLinuxRecipe, ArtixRecipe


def _listing(*names):
    return "<html><body>" + "".join(f'<a href="{n}">{n}</a>' for n in names) + "</body></html>"


def _jsontable(*names):
    return json.dumps({"data": [{"name": n} for n in names]})


class _Resp:
    def __init__(self, text="", status_code=200, url="", headers=None):
        self.text, self.status_code, self.url, self.headers = text, status_code, url, headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return json.loads(self.text)


class _Session:
    """Serves `pages` by URL; anything else is a 404. A page may be a ready
    _Resp, for the cases where headers or a redirect target matter."""
    headers = {}

    def __init__(self, pages):
        self.pages = dict(pages)
        self.asked = []

    def get(self, url, **kw):
        self.asked.append(url)
        page = self.pages.get(url)
        if isinstance(page, Exception):
            raise page
        if isinstance(page, _Resp):
            return page
        return _Resp(page, url=url) if page is not None else _Resp("", 404, url=url)

    head = get


def _with(monkeypatch, recipe, pages):
    session = _Session(pages)
    monkeypatch.setattr(recipe, "get_session", lambda: session)
    return recipe, session


# ------------------------------------------------------------------ Pop!_OS

def _pop_build(release, channel, build):
    url = f"https://iso.pop-os.org/{release}/amd64/{channel}/{build}/pop-os_{release}_amd64_{channel}_{build}.iso"
    return json.dumps({"version": release, "url": url, "build": str(build), "sha_sum": "a" * 64})


def test_popos_serves_the_newest_release_the_build_api_has(monkeypatch):
    api = "https://api.pop-os.org/builds/{}/intel"
    recipe, session = _with(monkeypatch, PopOSRecipe(), {
        api.format("22.04"): _pop_build("22.04", "intel", 58),
        api.format("24.04"): _pop_build("24.04", "intel", 20),
        api.format("26.04"): "",                      # how the API answers for a release not out yet
    })
    monkeypatch.setattr(PopOSRecipe, "_releases_to_try", staticmethod(lambda year: ["26.10", "26.04", "25.10", "25.04", "24.10", "24.04", "22.04"]))

    info = recipe.fetch_download_info("intel")

    assert info.version == "24.04 (Build 20)"
    assert info.filename == "pop-os_24.04_amd64_intel_20.iso"
    assert info.sha256 == "a" * 64
    assert not any("system76.com" in url for url in session.asked), "read the stale download page"


def test_popos_candidates_run_newest_first_down_to_22_04():
    releases = PopOSRecipe._releases_to_try(2026)
    assert releases[0] == "26.10" and releases[-1] == "22.04"
    assert releases.index("26.04") < releases.index("24.04") < releases.index("22.04")


def test_popos_refuses_when_the_api_is_silent(monkeypatch):
    recipe, _ = _with(monkeypatch, PopOSRecipe(), {})
    with pytest.raises(ScrapeError):
        recipe.fetch_download_info("nvidia")


# ----------------------------------------------------------------- openSUSE

SUSE = "https://download.opensuse.org/"
OPENSUSE = {
    # 16.0 is linked as current; 16.1 is mentioned once, as the beta it is.
    "https://get.opensuse.org/leap/": _listing("/leap/16.0/", "/leap/16.0/#download", "/leap/16.1/"),
    SUSE + "distribution/leap/16.0/offline/?jsontable": _jsontable(
        "Leap-16.0-offline-installer-x86_64-Build178.9.install.iso",
        "Leap-16.0-offline-installer-x86_64-Build178.27.install.iso",
        "Leap-16.0-offline-installer-x86_64.install.iso",
        "Leap-16.0-online-installer-x86_64-Build178.27.install.iso"),
    # Already on the mirror while still in beta.
    SUSE + "distribution/leap/16.1/offline/?jsontable": _jsontable(
        "Leap-16.1-offline-installer-x86_64-Build44.3.install.iso"),
    SUSE + "distribution/leap/15.6/iso/?jsontable": _jsontable("openSUSE-Leap-15.6-DVD-x86_64-Current.iso"),
    SUSE + "tumbleweed/iso/?jsontable": _jsontable(
        "openSUSE-Tumbleweed-DVD-x86_64-Current.iso",
        "openSUSE-Tumbleweed-DVD-x86_64-Snapshot20260912-Media.iso",
        "openSUSE-Tumbleweed-DVD-x86_64-Snapshot20260919-Media.iso",
        "openSUSE-MicroOS-DVD-x86_64-Snapshot20260920-Media.iso",
        "openSUSE-Tumbleweed-KDE-Live-x86_64-Snapshot20260919-Media.iso"),
}


def test_leap_is_the_release_opensuse_calls_current(monkeypatch):
    recipe, _ = _with(monkeypatch, OpenSUSERecipe(), OPENSUSE)

    dvd = recipe.fetch_download_info("leap-dvd")
    assert dvd.version == "16.0 (Build 178.27)", "178.9 sorts above 178.27 as text"
    assert dvd.filename == "Leap-16.0-offline-installer-x86_64-Build178.27.install.iso"
    assert dvd.url == SUSE + "distribution/leap/16.0/offline/" + dvd.filename

    assert recipe.fetch_download_info("leap-net").filename == \
        "Leap-16.0-online-installer-x86_64-Build178.27.install.iso"


def test_leap_does_not_fall_back_to_an_older_release(monkeypatch):
    pages = dict(OPENSUSE)
    pages[SUSE + "distribution/leap/16.0/offline/?jsontable"] = _jsontable("README")
    recipe, _ = _with(monkeypatch, OpenSUSERecipe(), pages)

    with pytest.raises(ScrapeError):
        recipe.fetch_download_info("leap-dvd")


def test_tumbleweed_reports_the_snapshot_not_a_label(monkeypatch):
    recipe, _ = _with(monkeypatch, OpenSUSERecipe(), OPENSUSE)
    info = recipe.fetch_download_info("tumbleweed-dvd")

    assert info.version == "20260919"
    assert info.filename == "openSUSE-Tumbleweed-DVD-x86_64-Snapshot20260919-Media.iso"


# -------------------------------------------------------------------- NixOS

def _nixos(monkeypatch, pages):
    recipe, session = _with(monkeypatch, NixOSRecipe(), pages)
    monkeypatch.setattr(NixOSRecipe, "_candidate_channels", staticmethod(lambda today=None: ["26.11", "26.05"]))
    return recipe, session


NIX_ALIAS = "https://channels.nixos.org/nixos-{}/latest-nixos-minimal-x86_64-linux.iso"
NIX_REAL = ("https://releases.nixos.org/nixos/26.05/nixos-26.05.10304.6d663c0533ff/"
            "nixos-minimal-26.05.10304.6d663c0533ff-x86_64-linux.iso")


def test_nixos_reports_the_build_the_alias_stands_for(monkeypatch):
    recipe, _ = _nixos(monkeypatch, {NIX_ALIAS.format("26.05"): _Resp(url=NIX_REAL)})
    info = recipe.fetch_download_info("minimal")

    assert info.version == "26.05.10304"
    assert info.filename == "nixos-minimal-26.05.10304.6d663c0533ff-x86_64-linux.iso"
    assert info.url == NIX_REAL


def test_nixos_does_not_serve_the_previous_release_because_of_a_timeout(monkeypatch):
    """A channel that does not exist answers 404, and the next one is tried.
    One that cannot be reached is not an answer at all."""
    recipe, _ = _nixos(monkeypatch, {
        NIX_ALIAS.format("26.11"): TimeoutError("timed out"),
        NIX_ALIAS.format("26.05"): _Resp(url=NIX_REAL),
    })
    with pytest.raises(ScrapeError):
        recipe.fetch_download_info("minimal")


# ------------------------------------------------------ Rocky and AlmaLinux

def test_rocky_names_the_point_release(monkeypatch):
    root = "https://download.rockylinux.org/pub/rocky/"
    recipe, _ = _with(monkeypatch, RockyLinuxRecipe(), {
        root: _listing("8/", "9/", "9.8/", "10/", "10.2/"),
        root + "10/isos/x86_64/": _listing(
            "Rocky-10-latest-x86_64-dvd.iso", "Rocky-10.1-x86_64-dvd1.iso", "Rocky-10.2-x86_64-dvd1.iso",
            "Rocky-10-latest-x86_64-boot.iso", "Rocky-10.2-x86_64-boot.iso"),
    })

    dvd = recipe.fetch_download_info("dvd")
    assert (dvd.version, dvd.filename) == ("10.2", "Rocky-10.2-x86_64-dvd1.iso")
    assert recipe.fetch_download_info("boot").filename == "Rocky-10.2-x86_64-boot.iso"


def test_almalinux_names_the_point_release(monkeypatch):
    root = AlmaLinuxRecipe.REPO_ROOT
    recipe, _ = _with(monkeypatch, AlmaLinuxRecipe(), {
        root: _listing("8/", "9/", "10/", "10.2/"),
        f"{root}10/isos/x86_64/": _listing(
            "AlmaLinux-10-latest-x86_64-minimal.iso", "AlmaLinux-10.1-x86_64-minimal.iso",
            "AlmaLinux-10.2-x86_64-minimal.iso"),
    })
    info = recipe.fetch_download_info("minimal")

    assert (info.version, info.filename) == ("10.2", "AlmaLinux-10.2-x86_64-minimal.iso")


# ------------------------------------------------------------------ Bazzite

def test_bazzite_is_versioned_by_the_date_its_image_was_built(monkeypatch):
    url = "https://download.bazzite.gg/bazzite-stable-amd64.iso"
    recipe, _ = _with(monkeypatch, BazziteRecipe(), {
        url: _Resp(url=url, headers={"Last-Modified": "Sat, 18 Oct 2025 22:47:58 GMT"}),
        url + "-CHECKSUM": "9c8d06cd8e57f2274678edeb14b4b13a79b8117c70571a65199919a66305b5c7  bazzite-stable-amd64.iso\n",
    })
    info = recipe.fetch_download_info("desktop-kde")

    assert info.version == "20251018"
    assert info.sha256.startswith("9c8d06cd")


def test_bazzite_refuses_rather_than_report_a_label(monkeypatch):
    recipe, _ = _with(monkeypatch, BazziteRecipe(), {})
    with pytest.raises(ScrapeError):
        recipe.fetch_download_info("desktop-kde")


# --------------------------------------------------------- Artix and TUXEDO

def test_artix_takes_the_newest_stable_image_not_the_first_or_a_weekly(monkeypatch):
    recipe, _ = _with(monkeypatch, ArtixRecipe(), {
        "https://download.artixlinux.org/iso/": _listing(
            "https://download.artixlinux.org/iso/artix-base-runit-20260407-x86_64.iso",
            "https://download.artixlinux.org/iso/artix-base-runit-20260813-x86_64.iso",
            "https://download.artixlinux.org/weekly-iso/artix-base-runit-20260920-x86_64.iso",
            "https://download.artixlinux.org/iso/artix-base-openrc-20260901-x86_64.iso"),
    })
    info = recipe.fetch_download_info("base-runit")

    assert info.version == "20260813"
    assert "weekly" not in info.url


def test_tuxedo_takes_the_newest_image_not_the_first(monkeypatch):
    recipe, _ = _with(monkeypatch, TuxedoRecipe(), {
        "https://os.tuxedocomputers.com/": _listing(
            "TUXEDO-OS-202512181030.iso", "TUXEDO-OS-202609161651.iso", "TUXEDO-OS-current.iso"),
    })
    assert recipe.fetch_download_info("standard").version == "202609161651"


# ------------------------------------------------------------------ Debian

def _debian_pages(cd_status=200, get_status=200):
    from src.recipes.debian import TREES, NETINST_DIR, LIVE_DIR
    cd, get = TREES
    listing = _listing("debian-13.6.0-amd64-netinst.iso", "debian-13.7.0-amd64-netinst.iso",
                       "debian-13.7.0-amd64-netinst.iso.torrent", "SHA256SUMS")
    live = _listing("debian-live-13.7.0-amd64-kde.iso", "debian-live-13.7.0-amd64-kde-lite.iso",
                    "debian-live-13.7.0-amd64-gnome.iso")
    sums = ("abc123  debian-13.6.0-amd64-netinst.iso\n"
            "def456  debian-13.7.0-amd64-netinst.iso\n")
    return {
        cd + NETINST_DIR: _Resp(listing, cd_status, url=cd + NETINST_DIR),
        cd + NETINST_DIR + "SHA256SUMS": _Resp(sums, cd_status),
        cd + LIVE_DIR: _Resp(live, cd_status),
        get + NETINST_DIR: _Resp(listing, get_status, url=get + NETINST_DIR),
        get + NETINST_DIR + "SHA256SUMS": _Resp(sums, get_status),
        get + LIVE_DIR: _Resp(live, get_status),
    }


def test_debian_takes_the_newest_image_and_its_checksum(monkeypatch):
    from src.recipes.debian import DebianRecipe, TREES, NETINST_DIR
    recipe, session = _with(monkeypatch, DebianRecipe(), _debian_pages())
    info = recipe.fetch_download_info("netinst")
    assert info.version == "13.7.0"
    assert info.filename == "debian-13.7.0-amd64-netinst.iso"
    assert info.url == TREES[0] + NETINST_DIR + info.filename
    assert info.sha256 == "def456"


def test_debian_live_matches_the_whole_name(monkeypatch):
    """"kde" must not serve kde-lite, nor "standard" anything else."""
    from src.recipes.debian import DebianRecipe
    recipe, _ = _with(monkeypatch, DebianRecipe(), _debian_pages())
    assert recipe.fetch_download_info("kde").filename == "debian-live-13.7.0-amd64-kde.iso"
    with pytest.raises(ScrapeError):
        recipe.fetch_download_info("standard")


def test_debian_asks_get_debian_org_when_cdimage_answers_500(monkeypatch):
    """Regression: cdimage.debian.org answers HTTP 500 now and then, and the
    row read "No current release" for a release that was right there."""
    from src.recipes.debian import DebianRecipe, TREES, NETINST_DIR
    recipe, session = _with(monkeypatch, DebianRecipe(), _debian_pages(cd_status=500))
    info = recipe.fetch_download_info("netinst")
    assert info.version == "13.7.0"
    assert info.url == TREES[1] + NETINST_DIR + "debian-13.7.0-amd64-netinst.iso"
    assert info.sha256 == "def456"
    assert session.asked[0] == TREES[0] + NETINST_DIR


def test_debian_names_what_went_wrong_when_both_hosts_fail(monkeypatch):
    from src.recipes.debian import DebianRecipe
    recipe, _ = _with(monkeypatch, DebianRecipe(), _debian_pages(cd_status=500, get_status=503))
    with pytest.raises(ScrapeError) as err:
        recipe.fetch_download_info("netinst")
    assert "HTTP 500" in str(err.value) and "HTTP 503" in str(err.value)
    assert "no netinst image" not in str(err.value), "a server error is not an empty listing"
