"""Freshness Cases for the gaming and security recipes.

Bazzite and Garuda read one pointer each that the project itself keeps
current, so there is no listing to reorder; they are exempt from the Case
table and tested by hand at the bottom, including the refusal.
"""
from dataclasses import replace

import pytest

from src.core.iso_identity import identify
from src.core.recipe_base import ScrapeError
from src.recipes.gaming import BazziteRecipe, CachyOSRecipe, GarudaRecipe, NobaraRecipe, PikaOSRecipe
from src.recipes.security import CaineRecipe, KaliRecipe, ParrotRecipe
from tests.freshness import Case, Resp, assert_newest, assert_no_fallback, use

HASH = "0123456789abcdef" * 4


def _listing(*names):
    return "<html><body><h1>Index</h1>" + "".join(f'<a href="{n}">{n}</a>\n' for n in names) + "</body></html>"


def _sums(*names):
    return "".join(f"{HASH}  {n}\n" for n in names)


# -------------------------------------------------------------------- Kali

KALI = KaliRecipe.CURRENT
KALI_SUMS = KALI + "SHA256SUMS"
# Kali numbers its releases by quarter, so .9 and .10 never meet; they stand
# for any pair that text order and number order rank differently.
_KALI = _listing(
    "../", "SHA256SUMS",
    "kali-linux-2026.9-installer-amd64.iso",
    "kali-linux-2026-W41-installer-amd64.iso",          # weekly build, not a release
    "kali-linux-2026.10-installer-amd64.iso",
    "kali-linux-2026.10-installer-everything-amd64.iso.torrent",
    "kali-linux-2026.10-live-amd64.iso.torrent",
    "kali-linux-2026.8-installer-amd64.iso",
)

# ------------------------------------------------------------------ Parrot

PARROT = ParrotRecipe.BASE
_PARROT = _listing(
    "../", "5.2/", "5.2-1/", "7.9/", "7.10-1/", "7.10/", "8.0-beta1/", "caine/", "latest/", "7.0/")


def _parrot_release(v):
    return _listing(
        "../", f"Parrot-core-{v}_rpi.img.xz", f"Parrot-security-tuned-{v}_amd64.iso",
        f"Parrot-security-{v}_arm64.iso", f"Parrot-security-{v}_amd64.iso",
        f"Parrot-security-{v}_amd64.iso.torrent", f"Parrot-home-{v}_amd64.iso",
        f"Parrot-home-tuned-{v}_amd64.iso", "signed-hashes.txt")


def _parrot_sums(v):
    # signed-hashes.txt: an MD5, SHA-256 and SHA-512 block, clearsigned.
    return (f"-----BEGIN PGP SIGNED MESSAGE-----\nHash: SHA512\n\nParrot OS {v}\n\nmd5\n"
            f"{HASH[:32]}  Parrot-security-{v}_amd64.iso\n\nsha256\n"
            f"{HASH}  Parrot-home-{v}_amd64.iso\n{HASH}  Parrot-security-{v}_amd64.iso\n\n"
            f"sha512\n{HASH * 2}  Parrot-security-{v}_amd64.iso\n")


_PARROT_PAGES = {
    PARROT: _PARROT,
    # A respin folder of torrents only, like the real 5.2-1/: its images are 7.10's.
    PARROT + "7.10-1/": _listing("../", "Parrot-security-7.10_amd64.iso.torrent",
                                 "Parrot-home-7.10_amd64.iso.torrent"),
    PARROT + "7.10/": _parrot_release("7.10"),
    PARROT + "7.10/signed-hashes.txt": _parrot_sums("7.10"),
    PARROT + "7.9/": _parrot_release("7.9"),
    PARROT + "8.0-beta1/": _parrot_release("8.0-beta1"),
}

# ------------------------------------------------------------------- CAINE

CAINE = CaineRecipe.PAGE
CAINE_SUMS = "https://www.caine-live.net/page5/caine14.0.iso.sha256.txt"
_CAINE_LINKS = (
    "https://www.caine-live.net/Downloads/caine9.0.iso",
    "https://cfitaly.net/caine/caine14.0.iso",
    "https://cfitaly.net/caine/caine15.0_beta01.iso",
    "https://www.caine-live.net/Downloads/caine14.0.iso",
    CAINE_SUMS,
    "../Downloads/caine11.iso.torrent",
    "https://caine.mirror.garr.it/caine/caine13.0.iso",
    "https://archive.org/download/caine8/caine8.iso",
)

# ------------------------------------------------------------------ Nobara

NOBARA = "https://nobaraproject.org/download-nobara/"
NOBARA_IMG = "https://nobara-images.nobaraproject.org/"
_NOBARA_LINKS = (
    NOBARA_IMG + "Nobara-43-KDE-2026-03-14.iso",
    NOBARA_IMG + "Nobara-9-KDE-2019-01-01.iso",           # "9" outranks "44" as text
    NOBARA_IMG + "Nobara-44-KDE-2026-09-02.iso",
    NOBARA_IMG + "Nobara-44-KDE-2026-09-02.iso.sha256sum",
    NOBARA_IMG + "Nobara-45-KDE-Beta-2026-10-01.iso",
    NOBARA_IMG + "Nobara-44-GNOME-2026-09-20.iso",
    NOBARA_IMG + "Nobara-44-KDE-2026-08-15.iso",
)


def _nobara_sums(fname):
    # Nobara writes the name with a "./" in front.
    return {f"{NOBARA_IMG}{fname}.sha256sum": f"{HASH}  ./{fname}\n"}

# ------------------------------------------------------------------ PikaOS

PIKA = "https://pika-os.com/"
PIKA_ISO = "https://iso.pika-os.com/"
_PIKA_KDE = (
    "PikaOS-Wren-KDE-3.0-amd64-v3-25.12.01-2.iso",        # "Wren" outranks "Nest" as text
    "PikaOS-Nest-KDE-4.0-amd64-v3-26.06.11-10.iso",
    "PikaOS-Nest-KDE-4.0-amd64-v3-26.08.20-4.iso",
    "PikaOS-Nest-NVIDIA-KDE-4.0-amd64-v3-26.09.01-1.iso",
    "PikaOS-Nest-KDE-4.1-amd64-v3-26.10.01-beta1.iso",
    "PikaOS-Nest-COSMIC-4.0-amd64-v3-26.08.20-4.iso",
)
_PIKA_GNOME = (
    "PikaOS-Nest-GNOME-9.0-amd64-v3-26.05.01-1.iso",
    "PikaOS-Lark-GNOME-10.0-amd64-v3-26.11.02-1.iso",     # "9.0" outranks "10.0" as text
    "PikaOS-Nest-GNOME-9.0-amd64-v3-26.08.20-4.iso",
)


def _pika_edition(ed):
    return (
        f"PikaOS-Nest-{ed}-9.0-amd64-v3-26.05.01-1.iso",
        f"PikaOS-Lark-{ed}-10.0-amd64-v3-26.10.02-2.iso",       # "9.0" outranks "10.0" as text
        f"PikaOS-Nest-NVIDIA-{ed}-10.0-amd64-v3-26.11.01-1.iso",
        f"PikaOS-Lark-{ed}-10.1-amd64-v3-26.12.01-beta1.iso",
        f"PikaOS-Nest-{ed}-9.0-amd64-v3-26.08.20-4.iso",
    )


def _pika(*names):
    return _listing(*(PIKA_ISO + n for n in names))

# ----------------------------------------------------------------- CachyOS

CACHY = CachyOSRecipe.PAGE
CACHY_CDN = "https://cdn77.cachyos.org/ISO/"
_CACHY_LINKS = (
    CACHY_CDN + "desktop/260426/cachyos-desktop-linux-260426.iso",
    CACHY_CDN + "handheld/260628/cachyos-handheld-linux-260628.iso",
    CACHY_CDN + "desktop/260809/cachyos-desktop-linux-260809.iso",
    "https://sourceforge.net/projects/cachyos-arch/files/gui-installer/desktop/260809/"
    "cachyos-desktop-linux-260809.iso/download",
    CACHY_CDN + "desktop/251130/cachyos-desktop-linux-251130.iso",
)


def _cachy_sums(path):
    return {f"{CACHY_CDN}{path}.sha256": f"{HASH}  {path.rsplit('/', 1)[-1]}\n"}


CASES = {
    "kali": [
        Case(
            pages={KALI: _KALI, KALI_SUMS: _sums("kali-linux-2026.10-installer-amd64.iso")},
            flavor="installer", newest="2026.10",
            filename="kali-linux-2026.10-installer-amd64.iso",
            newest_urls=(KALI,),
            extra={"newer": ({KALI: _KALI.replace("</body>", '<a href="kali-linux-2026.11-installer-amd64.iso">x</a></body>')},
                             "2026.11")},
        ),
        # A respin ranks above the release it replaces.
        Case(
            pages={KALI: _listing("kali-linux-2026.1-installer-purple-amd64.iso",
                                  "kali-linux-2026.2a-installer-purple-amd64.iso",
                                  "kali-linux-2026.2-installer-purple-amd64.iso",
                                  "kali-linux-2026.2a-installer-netinst-amd64.iso"),
                   KALI_SUMS: _sums("kali-linux-2026.2a-installer-purple-amd64.iso")},
            flavor="purple", newest="2026.2a",
            filename="kali-linux-2026.2a-installer-purple-amd64.iso",
            newest_urls=(KALI,),
        ),
    ],
    "parrot": Case(
        pages=_PARROT_PAGES,
        flavor="security", newest="7.10", filename="Parrot-security-7.10_amd64.iso",
        newest_urls=(PARROT, PARROT + "7.10-1/", PARROT + "7.10/"),
        extra={"newer": ({PARROT: _PARROT.replace("7.0/</a>", '7.0/</a><a href="7.11/">7.11/</a>'),
                          PARROT + "7.11/": _parrot_release("7.11"),
                          PARROT + "7.11/signed-hashes.txt": _parrot_sums("7.11")}, "7.11")},
    ),
    "caine": Case(
        pages={CAINE: _listing(*_CAINE_LINKS), CAINE_SUMS: f"{HASH}  caine14.0.iso\n"},
        flavor="standard", newest="14.0", filename="caine14.0.iso",
        newest_urls=(CAINE,),
        # Linked relatively, and with no minor version, as caine10 and 11 were.
        extra={"newer": ({CAINE: _listing(*_CAINE_LINKS, "../Downloads/caine15.iso")}, "15")},
    ),
    "nobara": Case(
        pages={NOBARA: _listing(*_NOBARA_LINKS), **_nobara_sums("Nobara-44-KDE-2026-09-02.iso")},
        flavor="kde", newest="44 (2026-09-02)", filename="Nobara-44-KDE-2026-09-02.iso",
        newest_urls=(NOBARA,),
        extra={"newer": ({NOBARA: _listing(*_NOBARA_LINKS, NOBARA_IMG + "Nobara-45-KDE-2026-10-20.iso"),
                          **_nobara_sums("Nobara-45-KDE-2026-10-20.iso")}, "45 (2026-10-20)")},
    ),
    "pikaos": [
        Case(
            pages={PIKA: _pika(*_PIKA_KDE)},
            flavor="kde", newest="4.0 (26.08.20)", filename="PikaOS-Nest-KDE-4.0-amd64-v3-26.08.20-4.iso",
            newest_urls=(PIKA,),
            extra={"newer": ({PIKA: _pika(*_PIKA_KDE, "PikaOS-Nest-KDE-4.1-amd64-v3-26.10.02-1.iso")},
                             "4.1 (26.10.02)")},
        ),
        Case(
            pages={PIKA: _pika(*_PIKA_GNOME)},
            flavor="gnome", newest="10.0 (26.11.02)", filename="PikaOS-Lark-GNOME-10.0-amd64-v3-26.11.02-1.iso",
            newest_urls=(PIKA,),
        ),
        *(Case(pages={PIKA: _pika(*_pika_edition(ed))}, flavor=ed.lower(), newest="10.0 (26.10.02)",
               filename=f"PikaOS-Lark-{ed}-10.0-amd64-v3-26.10.02-2.iso", newest_urls=(PIKA,))
          for ed in ("COSMIC", "Niri")),
    ],
    # The download page names one build per edition; the dates are all six
    # digits, so no pair of them sorts differently as text, and CachyOS
    # publishes no pre-releases there.
    "cachyos": Case(
        pages={CACHY: _listing(*_CACHY_LINKS), **_cachy_sums("desktop/260809/cachyos-desktop-linux-260809.iso")},
        flavor="desktop", newest="260809", filename="cachyos-desktop-linux-260809.iso",
        newest_urls=(CACHY,),
        extra={"newer": ({CACHY: _listing(*_CACHY_LINKS, CACHY_CDN + "desktop/261010/cachyos-desktop-linux-261010.iso"),
                          **_cachy_sums("desktop/261010/cachyos-desktop-linux-261010.iso")}, "261010")},
    ),
}

EXEMPT = {
    "bazzite": "one fixed file per edition whose Last-Modified is the version; nothing to order "
               "(tested by hand below)",
    "garuda": "reads the latest.iso redirect Garuda keeps pointed at its release; nothing to order "
              "(tested by hand below)",
}

RECIPES = {cls.key: cls for cls in (KaliRecipe, ParrotRecipe, CaineRecipe, NobaraRecipe, PikaOSRecipe,
                                    CachyOSRecipe)}


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


@pytest.mark.parametrize("key,case", [p for p in _cases() if "newer" in p.values[1].extra])
def test_a_newer_release_is_taken_when_it_appears(monkeypatch, key, case):
    pages, version = case.extra["newer"]
    assert_newest(monkeypatch, RECIPES[key], replace(case, pages={**case.pages, **pages}, newest=version,
                                                     filename=None, extra={}))


@pytest.mark.parametrize("key,case", [p for p in _cases() if p.values[1].filename])
def test_iso_identity_reads_the_filename_back(key, case):
    found = identify(case.filename)
    assert found is not None and (found.key, found.flavor_id, found.version) == (key, case.flavor, case.newest)


# ------------------------------------------------- pre-release only above

def test_parrot_takes_no_pre_release_folder(monkeypatch):
    pages = {**_PARROT_PAGES, PARROT: _listing("7.9/", "7.10/", "7.11-rc1/", "8.0-beta1/")}
    recipe, session = use(monkeypatch, ParrotRecipe(), pages)
    assert recipe.fetch_download_info("home").version == "7.10"
    assert PARROT + "8.0-beta1/" not in session.asked


def test_caine_takes_no_beta_above_the_release(monkeypatch):
    recipe, _ = use(monkeypatch, CaineRecipe(), {
        CAINE: _listing("https://cfitaly.net/caine/caine15.0_beta01.iso",
                        "https://www.caine-live.net/Downloads/caine14.0.iso"),
        CAINE_SUMS: ""})
    assert recipe.fetch_download_info("standard").version == "14.0"


def test_pikaos_takes_no_beta_above_the_release(monkeypatch):
    recipe, _ = use(monkeypatch, PikaOSRecipe(), {
        PIKA: _pika("PikaOS-Nest-KDE-4.1-amd64-v3-26.10.01-beta1.iso", "PikaOS-Nest-KDE-4.0-amd64-v3-26.08.20-4.iso")})
    assert recipe.fetch_download_info("kde").version == "4.0 (26.08.20)"


def test_parrot_refuses_an_older_folder_when_the_newest_lacks_the_edition(monkeypatch):
    pages = {**_PARROT_PAGES, PARROT + "7.10/": _listing("Parrot-home-7.10_amd64.iso")}
    recipe, session = use(monkeypatch, ParrotRecipe(), pages)
    with pytest.raises(ScrapeError):
        recipe.fetch_download_info("security")
    assert PARROT + "7.9/" not in session.asked


def test_parrot_refuses_a_release_folder_with_no_images_yet(monkeypatch):
    # A release mid-upload, the shape 6.3.2/ is in for good: torrents and
    # hashes, no image. Unlike a respin it is the newest release, so 7.10's
    # images below it are not current.
    pages = {**_PARROT_PAGES,
             PARROT: _listing("7.9/", "7.10/", "7.11/"),
             PARROT + "7.11/": _listing("../", "Parrot-security-7.11_amd64.iso.torrent", "signed-hashes.txt")}
    recipe, session = use(monkeypatch, ParrotRecipe(), pages)
    with pytest.raises(ScrapeError):
        recipe.fetch_download_info("security")
    assert PARROT + "7.10/" not in session.asked


def test_kali_reads_only_cdimage(monkeypatch):
    # A third-party mirror whose current/ still held the release before was
    # once read when cdimage failed; StrictSession fails on any URL but these.
    recipe, session = use(monkeypatch, KaliRecipe(), {KALI: Resp("", 503)})
    with pytest.raises(ScrapeError):
        recipe.fetch_download_info("installer")
    assert session.asked == [KALI]


def test_checksums_are_supplied_where_published(monkeypatch):
    for cls, key in ((KaliRecipe, "kali"), (CaineRecipe, "caine"), (NobaraRecipe, "nobara"),
                     (CachyOSRecipe, "cachyos"), (ParrotRecipe, "parrot")):
        case = CASES[key][0] if isinstance(CASES[key], list) else CASES[key]
        recipe, _ = use(monkeypatch, cls(), case.pages)
        assert recipe.fetch_download_info(case.flavor).sha256 == HASH, key


# ----------------------------------------------------------------- Bazzite

BAZZITE = "https://download.bazzite.gg/"
_BAZZITE = {
    BAZZITE + "bazzite-deck-stable-live-amd64.iso":
        Resp(headers={"Last-Modified": "Tue, 06 Oct 2026 06:57:57 GMT"}),
    BAZZITE + "bazzite-deck-stable-live-amd64.iso-CHECKSUM": f"{HASH}  bazzite-deck-stable-live-amd64.iso\n",
    # The name before upstream's rename: frozen, still answering, never to be read.
    BAZZITE + "bazzite-deck-stable-amd64.iso": Resp(headers={"Last-Modified": "Sat, 18 Oct 2025 22:45:38 GMT"}),
}
BAZZITE_CASE = Case(pages=_BAZZITE, flavor="deck-kde", newest="20261006",
                    filename="bazzite-deck-stable-live-20261006-amd64.iso",
                    newest_urls=(BAZZITE + "bazzite-deck-stable-live-amd64.iso",))


def test_bazzite_reads_the_live_installer_not_the_frozen_old_name(monkeypatch):
    recipe, session = use(monkeypatch, BazziteRecipe(), _BAZZITE)
    info = recipe.fetch_download_info("deck-kde")
    assert (info.version, info.filename, info.sha256) == ("20261006", BAZZITE_CASE.filename, HASH)
    assert BAZZITE + "bazzite-deck-stable-amd64.iso" not in session.asked
    found = identify(info.filename)
    assert (found.key, found.flavor_id, found.version) == ("bazzite", "deck-kde", "20261006")


@pytest.mark.parametrize("flavor,image", BazziteRecipe._IMAGES.items())
def test_bazzite_names_every_edition_so_it_reads_back(monkeypatch, flavor, image):
    upstream = BAZZITE + f"{image}-stable-live-amd64.iso"
    recipe, _ = use(monkeypatch, BazziteRecipe(), {
        upstream: Resp(headers={"Last-Modified": "Tue, 06 Oct 2026 07:02:03 GMT"}),
        upstream + "-CHECKSUM": f"{HASH}  {image}-stable-live-amd64.iso\n"})
    info = recipe.fetch_download_info(flavor)
    assert (info.filename, info.sha256) == (f"{image}-stable-live-20261006-amd64.iso", HASH)
    found = identify(info.filename)
    assert (found.key, found.flavor_id, found.version) == ("bazzite", flavor, "20261006")


def test_bazzite_refuses_rather_than_falling_back(monkeypatch):
    assert_no_fallback(monkeypatch, BazziteRecipe, BAZZITE_CASE)


def test_bazzite_refuses_an_unknown_edition(monkeypatch):
    recipe, _ = use(monkeypatch, BazziteRecipe(), {})
    with pytest.raises(ScrapeError):
        recipe.fetch_download_info("deck-nvidia")


# ------------------------------------------------------------------ Garuda

GARUDA_LATEST = GarudaRecipe.LATEST.format("mokka")
GARUDA_ISO = "https://iso.builds.garudalinux.org/iso/garuda/mokka/260819/garuda-mokka-linux-garuda-260819.iso"
_GARUDA = {
    GARUDA_LATEST: Resp("<html>302 Found</html>", 302, headers={"Location": GARUDA_ISO}),
    GARUDA_ISO + ".sha256": f"{HASH}  garuda-mokka-linux-garuda-260819.iso\n",
    # The build tree holds a later build that latest.iso does not name yet.
    "https://iso.builds.garudalinux.org/iso/garuda/mokka/": _listing("../", "260819/", "260822/"),
}
GARUDA_CASE = Case(pages=_GARUDA, flavor="mokka", newest="260819",
                   filename="garuda-mokka-linux-garuda-260819.iso", newest_urls=(GARUDA_LATEST,))


def test_garuda_takes_the_release_latest_iso_names_not_the_newest_build(monkeypatch):
    recipe, session = use(monkeypatch, GarudaRecipe(), _GARUDA)
    info = recipe.fetch_download_info("mokka")
    assert (info.version, info.url, info.filename, info.sha256) == ("260819", GARUDA_ISO, GARUDA_CASE.filename, HASH)
    assert session.asked == [GARUDA_LATEST, GARUDA_ISO + ".sha256"]
    found = identify(info.filename)
    assert (found.key, found.flavor_id, found.version) == ("garuda", "mokka", "260819")


def test_garuda_refuses_rather_than_falling_back(monkeypatch):
    assert_no_fallback(monkeypatch, GarudaRecipe, GARUDA_CASE)


def test_garuda_refuses_a_pointer_that_names_no_iso(monkeypatch):
    recipe, _ = use(monkeypatch, GarudaRecipe(), {GARUDA_LATEST: Resp("", 404)})
    with pytest.raises(ScrapeError):
        recipe.fetch_download_info("mokka")
