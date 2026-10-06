"""Freshness Cases for Fedora's four entries, Arch, and the Arch-based rolling
releases (Manjaro, EndeavourOS, Omarchy).

Fedora's index keeps every release until it is end of life, so an image the
current release dropped would still be found one release down. Arch's index
summarises itself in a field that can lag its own list. Manjaro files other
editions' images in an edition's folder. EndeavourOS has named its images
four different ways. Each Case below carries the shape that would mislead.
"""
import json

import pytest

from src.core.iso_identity import identify
from src.core.recipe_base import ScrapeError
from src.recipes.arch import ArchRecipe
from src.recipes.fedora import (RELEASES_INDEX, FedoraAtomicRecipe, FedoraLabsRecipe,
                                FedoraRecipe, FedoraSpinsRecipe)
from src.recipes.rolling import EndeavourRecipe, ManjaroRecipe, OmarchyRecipe
from tests.freshness import Case, Resp, assert_newest, assert_no_fallback, use


# ------------------------------------------------------------------ Fedora

def _fe(version, subvariant, fname, arch="x86_64"):
    return {"version": version, "arch": arch, "variant": subvariant, "subvariant": subvariant,
            "link": f"https://download.fedoraproject.org/pub/fedora/linux/releases/{version}/{fname}",
            "sha256": f"{version}{subvariant}".ljust(64, "0")[:64]}


def _fedora_images(version, tag):
    """One release's worth of the images the Cases ask for; `tag` is how its
    filenames spell the release ("44-1.7", "45_Beta-1.3")."""
    return [
        _fe(version, "Server", f"Fedora-Server-dvd-x86_64-{tag}.iso"),
        _fe(version, "Server", f"Fedora-Server-netinst-x86_64-{tag}.iso"),
        _fe(version, "Silverblue", f"Fedora-Silverblue-ostree-x86_64-{tag}.iso"),
        _fe(version, "Mate", f"Fedora-MATE_Compiz-Live-{tag}.x86_64.iso"),
        _fe(version, "Python_Classroom", f"Fedora-Python-Classroom-Live-{tag}.x86_64.iso"),
    ]


FEDORA_ENTRIES = (
    _fedora_images("43", "43-1.6")
    + [_fe("43", "IoT", "Fedora-IoT-ostree-43-20251021.0.x86_64.iso")]
    + _fedora_images("44", "44-1.7")
    + [_fe("44", "IoT", "Fedora-IoT-ostree-44-20260427.0.x86_64.iso"),
       _fe("44", "IoT_Simplified_Provisioner", "Fedora-IoT-provisioner-44-20260427.0.x86_64.iso"),
       _fe("44", "Server", "Fedora-Server-dvd-aarch64-44-1.7.iso", arch="aarch64")]
    # A release text order puts above 44.
    + _fedora_images("9", "9-1.1")
    # Pre-releases above it: the index lists the branched Beta and Rawhide.
    + _fedora_images("45 Beta", "45_Beta-1.3")
    + _fedora_images("Rawhide", "Rawhide-20261006.n.0")
)
FEDORA_INDEX = json.dumps(FEDORA_ENTRIES)


def _fedora_case(flavor, newest, filename):
    return Case(pages={RELEASES_INDEX: FEDORA_INDEX}, flavor=flavor, newest=newest,
                filename=filename, newest_urls=(RELEASES_INDEX,))


# ------------------------------------------------------------------ Arch

ARCH_INDEX = "https://archlinux.org/releng/releases/json/"


def _arch_release(version, available=True):
    return {"version": version, "available": available,
            "iso_url": f"/iso/{version}/archlinux-{version}-x86_64.iso",
            "sha256_sum": version.replace(".", "").ljust(64, "a")}


def _arch_index(*releases, latest="2026.10.01"):
    data = {"version": 1, "releases": list(releases)}
    if latest is not None:
        data["latest_version"] = latest
    return json.dumps(data)


# Arch versions are zero-padded dates, so text and number order agree, and it
# publishes no pre-release images: neither trap applies.
ARCH_RELEASES = (_arch_release("2026.08.01"), _arch_release("2026.10.01"),
                 _arch_release("2026.09.01"), _arch_release("2026.07.01", available=False))


# ------------------------------------------------------------------ Manjaro

SF = "https://sourceforge.net/projects/manjarolinux/files/kde/"


def _sf_folders(*names):
    return "<table>" + "".join(
        f'<tr><th><a href="/projects/manjarolinux/files/kde/{n}/">{n}</a></th>'
        f'<td><a href="/projects/manjarolinux/files/kde/{n}/stats/timeline">stats</a></td></tr>'
        for n in names) + "</table>"


def _sf_files(folder, *names):
    return "<table>" + "".join(
        f'<tr><th><a href="https://sourceforge.net/projects/manjarolinux/files/kde/{folder}/{n}/download">'
        f'{n}</a></th></tr>' for n in names) + "</table>"


def _manjaro_folder(version, built):
    full = f"manjaro-kde-{version}-{built}-linux71.iso"
    return _sf_files(version, full + ".sig", full + ".sha256", full,
                     f"manjaro-kde-{version}-minimal-{built}-linux618.iso",
                     # Filed under kde, but GNOME's.
                     f"manjaro-gnome-{version}-{built}-linux71.iso",
                     full + ".pkgs")


MANJARO_SUM = ("https://downloads.sourceforge.net/project/manjarolinux/kde/26.1.10/"
               "manjaro-kde-26.1.10-261020-linux71.iso.sha256")
MANJARO_PAGES = {
    # 26.1.10 against 26.1.9 is the text-order trap; 26.2.0-rc1 and -pre are
    # the pre-releases above it.
    SF: _sf_folders("26.1.9", "26.2.0-rc1", "26.1.10", "26.2.0-pre", "26.1.2", "25.0.10"),
    SF + "26.1.10/": _manjaro_folder("26.1.10", "261020"),
    SF + "26.1.9/": _manjaro_folder("26.1.9", "260930"),
    MANJARO_SUM: "e" * 64 + "  manjaro-kde-26.1.10-261020-linux71.iso\n",
}


# ------------------------------------------------------------------ EndeavourOS

EOS = "https://mirror.alpix.eu/endeavouros/iso/"


def _autoindex(*names):
    return "<html><body><pre>" + "".join(
        f'<a href="{n}">{n}</a>    01-Jan-2026 00:00    1\n' for n in names) + "</pre></body></html>"


# The names as the mirror has them, in its (alphabetical) order, which puts
# the lower-case 2021 image last and the newest in the middle. EndeavourOS
# publishes no pre-releases or aliases there.
EOS_NAMES = (
    "EndeavourOS_Apollo_22_1.iso", "EndeavourOS_Cassini_Nova-03-2023.iso",
    "EndeavourOS_Cassini_Nova-03-2023_R1.iso", "EndeavourOS_Galileo-Neo-2024.01.25.iso",
    "EndeavourOS_Titan-2026.03.06.iso", "EndeavourOS_Titan-Nova-2026.08.15.iso",
    "EndeavourOS_Titan-Nova-2026.08.15.iso.sha512sum", "EndeavourOS_Titan-Nova-2026.08.15.iso.sig",
    "Endeavouros-Galileo-11-2023.iso", "Endeavouros_Cassini_Nova-03-2023_R3.iso",
    "endeavouros-2021.08.27-x86_64.iso",
)


# ------------------------------------------------------------------ Omarchy

OMARCHY = "https://omarchy.org/"
OMARCHY_SUM = "https://iso.omarchy.org/omarchy-4.0.10.iso.sha256"
OMARCHY_PAGE = "<html><body>" + "".join(
    f'<a href="https://iso.omarchy.org/{n}">{n}</a>'
    # 4.0.10 against 4.0.9 is the text-order trap; the rc is not a release.
    for n in ("omarchy-4.0.9.iso", "omarchy-4.0.10.iso", "omarchy-4.0.10.iso.sha256",
              "omarchy-4.1.0-rc1.iso", "omarchy-3.2.0.iso")) + "</body></html>"


CASES = {
    "fedora": [
        _fedora_case("server-netinst", "44", "Fedora-Server-netinst-x86_64-44-1.7.iso"),
        _fedora_case("iot", "44 (20260427.0)", "Fedora-IoT-ostree-44-20260427.0.x86_64.iso"),
    ],
    "fedora_atomic": _fedora_case("silverblue", "44", "Fedora-Silverblue-ostree-x86_64-44-1.7.iso"),
    "fedora_spins": _fedora_case("mate", "44", "Fedora-MATE_Compiz-Live-44-1.7.x86_64.iso"),
    "fedora_labs": _fedora_case("python-classroom", "44", "Fedora-Python-Classroom-Live-44-1.7.x86_64.iso"),
    "arch": Case(pages={ARCH_INDEX: _arch_index(*ARCH_RELEASES)}, flavor="standard",
                 newest="2026.10.01", filename="archlinux-2026.10.01-x86_64.iso",
                 newest_urls=(ARCH_INDEX,)),
    "manjaro": Case(pages=MANJARO_PAGES, flavor="plasma", newest="26.1.10",
                    filename="manjaro-kde-26.1.10-261020-linux71.iso",
                    newest_urls=(SF, SF + "26.1.10/")),
    "endeavour": Case(pages={EOS: _autoindex(*EOS_NAMES)}, flavor="standard", newest="2026.08.15",
                      filename="EndeavourOS_Titan-Nova-2026.08.15.iso", newest_urls=(EOS,)),
    "omarchy": Case(pages={OMARCHY: OMARCHY_PAGE, OMARCHY_SUM: "d" * 64 + "  omarchy-4.0.10.iso\n"},
                    flavor="standard", newest="4.0.10", filename="omarchy-4.0.10.iso",
                    newest_urls=(OMARCHY,)),
}
EXEMPT = {}

RECIPES = {cls.key: cls for cls in (FedoraRecipe, FedoraAtomicRecipe, FedoraSpinsRecipe,
                                    FedoraLabsRecipe, ArchRecipe, ManjaroRecipe,
                                    EndeavourRecipe, OmarchyRecipe)}


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
    assert found is not None, f"{case.filename} is not recognised"
    assert (found.key, found.flavor_id, found.version) == (key, case.flavor, case.newest)


def _fetch(monkeypatch, cls, pages, flavor):
    return use(monkeypatch, cls(), pages)[0].fetch_download_info(flavor)


# ------------------------------------------------------------------ Fedora

FEDORA_45 = {"server-netinst": (FedoraRecipe, "45"), "iot": (FedoraRecipe, "45 (20261021.0)"),
             "silverblue": (FedoraAtomicRecipe, "45"), "mate": (FedoraSpinsRecipe, "45"),
             "python-classroom": (FedoraLabsRecipe, "45")}


@pytest.mark.parametrize("flavor", FEDORA_45)
def test_fedora_newer_release_appears(monkeypatch, flavor):
    cls, newest = FEDORA_45[flavor]
    index = FEDORA_ENTRIES + _fedora_images("45", "45-1.5") + [
        _fe("45", "IoT", "Fedora-IoT-ostree-45-20261021.0.x86_64.iso")]
    assert _fetch(monkeypatch, cls, {RELEASES_INDEX: json.dumps(index)}, flavor).version == newest


def test_fedora_beta_alone_above_is_not_a_release(monkeypatch):
    index = _fedora_images("44", "44-1.7") + _fedora_images("45 Beta", "45_Beta-1.3")
    assert _fetch(monkeypatch, FedoraRecipe, {RELEASES_INDEX: json.dumps(index)}, "server").version == "44"


def test_fedora_image_the_newest_release_has_not_rebuilt_stays_current(monkeypatch):
    """Sway Atomic was left out of 45 Beta while Fedora still ships it: its 44
    image is its current one, and a 45 build is offered as an update when it
    lands. One retired for good goes when 44 leaves the index at end of life."""
    index = json.dumps([
        _fe("44", "Sericea", "Fedora-Sericea-ostree-x86_64-44-1.7.iso"),
        _fe("44", "Silverblue", "Fedora-Silverblue-ostree-x86_64-44-1.7.iso"),
        _fe("45", "Silverblue", "Fedora-Silverblue-Installer-45-1.5.x86_64.iso"),
    ])
    pages = {RELEASES_INDEX: index}
    assert _fetch(monkeypatch, FedoraAtomicRecipe, pages, "silverblue").version == "45"
    assert _fetch(monkeypatch, FedoraAtomicRecipe, pages, "sway-atomic").version == "44"


# ------------------------------------------------------------------ Arch

def test_arch_newer_release_appears(monkeypatch):
    pages = {ARCH_INDEX: _arch_index(*ARCH_RELEASES, _arch_release("2026.11.01"), latest="2026.11.01")}
    info = _fetch(monkeypatch, ArchRecipe, pages, "standard")
    assert (info.version, info.filename) == ("2026.11.01", "archlinux-2026.11.01-x86_64.iso")
    assert info.sha256 == "20261101".ljust(64, "a")


@pytest.mark.parametrize("latest", [None, "2026.09.01"], ids=["missing", "lagging"])
def test_arch_reads_the_list_not_its_summary(monkeypatch, latest):
    """Without latest_version the old code reported the schema "version": 1."""
    pages = {ARCH_INDEX: _arch_index(*ARCH_RELEASES, latest=latest)}
    assert _fetch(monkeypatch, ArchRecipe, pages, "standard").version == "2026.10.01"


def test_arch_withdrawn_release_is_not_offered(monkeypatch):
    pages = {ARCH_INDEX: _arch_index(*ARCH_RELEASES, _arch_release("2026.11.01", available=False))}
    assert _fetch(monkeypatch, ArchRecipe, pages, "standard").version == "2026.10.01"


# ------------------------------------------------------------------ Manjaro

def test_manjaro_newer_release_appears(monkeypatch):
    pages = {**MANJARO_PAGES,
             SF: _sf_folders("26.1.9", "26.1.11", "26.1.10"),
             SF + "26.1.11/": _manjaro_folder("26.1.11", "261101"),
             MANJARO_SUM.replace("26.1.10-261020", "26.1.11-261101").replace("/26.1.10/", "/26.1.11/"): ""}
    assert _fetch(monkeypatch, ManjaroRecipe, pages, "plasma").version == "26.1.11"


def test_manjaro_prerelease_alone_above_is_not_a_release(monkeypatch):
    pages = {**MANJARO_PAGES, SF: _sf_folders("26.2.0-rc1", "26.1.10", "26.2.0-pre")}
    assert _fetch(monkeypatch, ManjaroRecipe, pages, "plasma").version == "26.1.10"


def test_manjaro_carries_the_published_checksum(monkeypatch):
    assert _fetch(monkeypatch, ManjaroRecipe, MANJARO_PAGES, "plasma").sha256 == "e" * 64


def test_manjaro_refuses_another_editions_image_filed_in_its_folder(monkeypatch):
    pages = {**MANJARO_PAGES, SF + "26.1.10/": _sf_files(
        "26.1.10", "manjaro-gnome-26.1.10-261020-linux71.iso",
        "manjaro-kde-26.1.10-minimal-261020-linux618.iso")}
    with pytest.raises(ScrapeError):
        _fetch(monkeypatch, ManjaroRecipe, pages, "plasma")


# ------------------------------------------------------------------ EndeavourOS

def test_endeavour_newer_release_appears(monkeypatch):
    pages = {EOS: _autoindex(*EOS_NAMES, "EndeavourOS_Vega-2026.11.02.iso")}
    assert _fetch(monkeypatch, EndeavourRecipe, pages, "standard").version == "2026.11.02"


def test_endeavour_respin_is_newer_than_the_image_it_replaces(monkeypatch):
    pages = {EOS: _autoindex("EndeavourOS_Titan-Nova-2026.08.15_R1.iso", *EOS_NAMES)}
    info = _fetch(monkeypatch, EndeavourRecipe, pages, "standard")
    assert (info.version, info.filename) == ("2026.08.15 R1", "EndeavourOS_Titan-Nova-2026.08.15_R1.iso")


@pytest.mark.parametrize("name", ["EndeavourOS_Vega-11-2026.iso", "EndeavourOS_Vega-2026-11-02.iso",
                                  "EndeavourOS_Vega.iso"])
def test_endeavour_refuses_a_newest_image_it_cannot_version(monkeypatch, name):
    """A release under another naming scheme is refused, not ranked below
    2026.08.15 or reported as "Latest"."""
    with pytest.raises(ScrapeError):
        _fetch(monkeypatch, EndeavourRecipe, {EOS: _autoindex(*EOS_NAMES, name)}, "standard")


# ------------------------------------------------------------------ Omarchy

def test_omarchy_newer_release_appears(monkeypatch):
    sum_url = "https://iso.omarchy.org/omarchy-4.1.0.iso.sha256"
    pages = {OMARCHY: OMARCHY_PAGE.replace("omarchy-3.2.0.iso", "omarchy-4.1.0.iso"), sum_url: ""}
    assert _fetch(monkeypatch, OmarchyRecipe, pages, "standard").version == "4.1.0"


def test_omarchy_carries_the_published_checksum(monkeypatch):
    assert _fetch(monkeypatch, OmarchyRecipe, CASES["omarchy"].pages, "standard").sha256 == "d" * 64
