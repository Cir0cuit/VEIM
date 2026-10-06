"""Live mirror sweep.

Excluded by default (see pyproject's addopts) because it depends on 30+ third-party
mirrors: a project having a bad day should not fail someone's build. Run it
deliberately when you suspect scraper rot:

    pytest -m network -v

It is the fastest way to find out which recipes have broken, and it fails with
the specific distro named rather than a generic timeout.
"""
import concurrent.futures as futures
import datetime
import functools
import re
import time
import warnings

import pytest
import requests

from src.core.iso_identity import identify
from src.core.recipe_base import ScrapeError, version_key
from src.recipes.registry import registry

pytestmark = pytest.mark.network

TIMEOUT = 30
HEADERS = {"User-Agent": "curl/8.4.0"}
ALL = registry.get_all_recipes()


def _misidentified(recipe, flavor_id, info) -> str:
    """Why adoption would get this download wrong, or "" if it would not.

    A name the rules do not know is fine - that ISO is simply never offered.
    A name they read as a different flavor or version is not: the adopted row
    would report an update forever, or fetch the wrong edition.
    """
    # A version with no number in it ("Stable", "Tumbleweed", "Latest") never
    # changes, so whatever was downloaded under it reads as up to date for good.
    # Digits do not rescue a label: "Latest 2" or "stable-6" names a channel,
    # and the number in it is not the release a later check will compare.
    if (not any(ch.isdigit() for ch in info.version)
            or re.search(r"latest|current|stable|rolling", info.version, re.I)):
        return f"version {info.version!r} is a label, not a release"

    found = identify(info.filename or "")
    expected = (recipe.key, flavor_id, info.version)
    if found is None or (found.key, found.flavor_id, found.version) == expected:
        return ""
    return f"{info.filename} is read as {found}, but the recipe says {expected}"


def _reachable(url: str) -> tuple:
    """(ok, detail) for a URL, preferring HEAD and falling back to a ranged GET."""
    try:
        resp = requests.head(url, allow_redirects=True, timeout=TIMEOUT, headers=HEADERS)
        code = resp.status_code
        # Some mirrors reject HEAD outright; retry with a tiny ranged GET.
        if code in (403, 405, 501):
            with requests.get(url, stream=True, allow_redirects=True, timeout=TIMEOUT,
                              headers={**HEADERS, "Range": "bytes=0-1023"}) as g:
                code = g.status_code
        return code < 400, f"HTTP {code}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


@pytest.mark.parametrize("recipe", ALL, ids=lambda r: r.key)
def test_first_flavor_resolves_to_a_live_url(recipe):
    flavors = recipe.get_flavors()
    assert flavors, f"{recipe.key} declares no flavors"

    try:
        info = recipe.fetch_download_info(flavors[0].id)
    except ScrapeError as e:
        pytest.fail(f"{recipe.key} could not resolve a current release: {e.reason}")

    assert info.url, f"{recipe.key} returned no URL"
    assert info.version and info.version != "Unknown", f"{recipe.key} returned no version"

    assert not _misidentified(recipe, flavors[0].id, info)

    ok, detail = _reachable(info.url)
    assert ok, f"{recipe.key} -> {info.url} unreachable ({detail})"


def _check(job):
    """(failure_message or None) for one (recipe, flavor) pair."""
    recipe, flavor = job
    try:
        info = recipe.fetch_download_info(flavor.id)
    except ScrapeError as e:
        return f"{recipe.key}/{flavor.id}: {e.reason}"
    except Exception as e:
        return f"{recipe.key}/{flavor.id}: {type(e).__name__}: {e}"
    wrong = _misidentified(recipe, flavor.id, info)
    if wrong:
        return f"{recipe.key}/{flavor.id}: {wrong}"
    ok, detail = _reachable(info.url)
    if not ok:
        return f"{recipe.key}/{flavor.id}: {detail} for {info.url}"
    return _stale(recipe, flavor.id, info) or None


# endoflife.date tracks the current release of a few dozen of these projects
# and is not scraped the way the recipes are, so it can tell when a recipe is
# reading a listing that stopped moving - which nothing else here notices: an
# old release still downloads, still identifies and is still reachable.
# Every id was checked against https://endoflife.date/api/all.json; editions
# not listed have no product there.
EOL_PRODUCTS = {
    "ubuntu": "ubuntu",
    # The site follows Ubuntu itself, and not every flavor ships what it does:
    # Ubuntu MATE skipped 26.04 and Unity publishes no point releases.
    ("ubuntu", "mate"): None,
    ("ubuntu", "unity"): None,
    "debian": "debian",
    "fedora": "fedora",
    "fedora_atomic": "fedora",
    "fedora_spins": "fedora",
    "fedora_labs": "fedora",
    "almalinux": "almalinux",
    "rocky": "rocky-linux",
    "oracle": "oracle-linux",
    "alpine": "alpine-linux",
    "tails": "tails",
    "mxlinux": "mxlinux",
    "slackware": "slackware",
    "xcpng": "xcp-ng",
    "devuan": "devuan",
    "antix": "antix",
    "mint": "linuxmint",
    "centos": "centos-stream",
    "freebsd": "freebsd",
    "nixos": "nixos",
    "popos": "pop-os",
    "mageia": "mageia",
    # Only Leap has cycles; Tumbleweed is not on the site.
    ("opensuse", "leap-dvd"): "opensuse",
    ("opensuse", "leap-net"): "opensuse",
    ("proxmox", "installer"): "proxmox-ve",
    ("proxmox", "backup-server"): "proxmox-backup-server",
    ("proxmox", "mail-gateway"): "proxmox-mail-gateway",
    ("proxmox", "datacenter-manager"): "proxmox-datacenter-manager",
}

# A mirror can trail a release by a day or two, and the site is edited by hand,
# sometimes ahead of the images. A release younger than this is not yet held
# against a recipe.
EOL_GRACE = datetime.timedelta(days=7)


def _eol_product(key: str, flavor_id: str):
    return EOL_PRODUCTS.get((key, flavor_id), EOL_PRODUCTS.get(key))


@functools.lru_cache(maxsize=None)
def _eol_cycles(product: str):
    """The product's cycles, or None when the site cannot be read. Its outage
    is not a recipe's fault, so it is cached as such and never fails a test."""
    try:
        resp = requests.get(f"https://endoflife.date/api/{product}.json",
                            timeout=TIMEOUT, headers=HEADERS)
        resp.raise_for_status()
        cycles = resp.json()
        if not isinstance(cycles, list):
            raise ValueError(f"expected a list, got {type(cycles).__name__}")
        return cycles
    except Exception as e:
        warnings.warn(f"endoflife.date {product} unavailable, not checked: {e}")
        return None


def _settled(date, today) -> bool:
    try:
        return today - datetime.date.fromisoformat(str(date)) >= EOL_GRACE
    except ValueError:
        return False


def _eol_current(product: str, cycles, today=None):
    """(version, released) that endoflife.date calls current, or None.

    Cycles like "lmde7" are other products under one id and are dropped. The
    newest cycle is the newest by release date, not by number: openSUSE still
    lists Leap 42.3, which outnumbers 16.0. FreeBSD is the exception - its two
    branches interleave (14.5 ships after 15.1), so there the highest wins.
    """
    today = today or datetime.date.today()
    numeric = [c for c in cycles
               if re.fullmatch(r"\d+(\.\d+)*", str(c.get("cycle", "")))
               and _settled(c.get("releaseDate"), today)]
    if not numeric:
        return None
    if product == "freebsd":
        cycle = max(numeric, key=lambda c: version_key(c["cycle"]))
    else:
        cycle = max(numeric, key=lambda c: str(c["releaseDate"]))
    # A point release in its first week is not expected of the mirror yet;
    # the cycle it belongs to is.
    if cycle.get("latest") and _settled(cycle.get("latestReleaseDate"), today):
        return str(cycle["latest"]), cycle["latestReleaseDate"]
    return str(cycle["cycle"]), cycle["releaseDate"]


def _stale(recipe, flavor_id, info) -> str:
    """Why endoflife.date says this edition is behind, or "" if it does not.

    Only a recipe that is older fails. The site lags too (it listed Oracle
    10.1 with 10.2 out), so a recipe ahead of it is believed. Comparing the
    oracle's numbers as a prefix lets "13.7.0", "9.2-1" and "10 (20260930.0)"
    stand for 13.7, 9.2 and 10.
    """
    product = _eol_product(recipe.key, flavor_id)
    cycles = _eol_cycles(product) if product else None
    current = _eol_current(product, cycles) if cycles else None
    if not current:
        return ""
    want, released = current
    have, need = version_key(info.version), version_key(want)
    if have[:len(need)] >= need:
        return ""
    return (f"{recipe.key}/{flavor_id}: recipe {info.version} < endoflife.date "
            f"{product} {want} (released {released})")


@pytest.mark.slow
def test_every_flavor_of_every_recipe():
    """Sweep all flavors at once and report every failure together."""
    jobs = [(r, f) for r in ALL for f in r.get_flavors()]

    # Deliberately gentle: at higher concurrency cdimage.debian.org rate-limits
    # us and the sweep reports failures that are our own fault, not upstream's.
    with futures.ThreadPoolExecutor(max_workers=4) as pool:
        first_pass = [(job, msg) for job, msg in zip(jobs, pool.map(_check, jobs)) if msg]

    # Anything that failed gets one more try on its own. Debian in particular
    # throttles a parallel sweep and then serves a listing with no images in
    # it, which the recipe correctly refuses - but that is our fault, not a
    # broken flavor, and reporting it as one sends you hunting the wrong bug.
    failures = []
    for job, _ in first_pass:
        time.sleep(1.0)
        retry = _check(job)
        if retry:
            failures.append(retry)

    assert not failures, "broken flavors:\n  " + "\n  ".join(failures)


ORACLE_JOBS = [(r, f) for r in ALL for f in r.get_flavors() if _eol_product(r.key, f.id)]


@pytest.mark.parametrize("recipe,flavor", ORACLE_JOBS,
                         ids=[f"{r.key}/{f.id}" for r, f in ORACLE_JOBS])
def test_oracle_agrees_the_edition_is_current(recipe, flavor):
    """Just the editions endoflife.date covers, so freshness can be checked on
    its own in a minute: pytest -m network tests/test_recipes_live.py -k oracle"""
    product = _eol_product(recipe.key, flavor.id)
    if not _eol_cycles(product):
        pytest.skip(f"endoflife.date {product} unavailable")
    try:
        info = recipe.fetch_download_info(flavor.id)
    except ScrapeError as e:
        pytest.fail(f"{recipe.key}/{flavor.id} could not resolve a current release: {e.reason}")
    stale = _stale(recipe, flavor.id, info)
    assert not stale, stale


def test_oracle_maps_every_catalog_entry_it_covers():
    """A distribution added later that endoflife.date already tracks is
    checked against it, rather than left out because nobody thought to look."""
    try:
        products = set(requests.get("https://endoflife.date/api/all.json",
                                    timeout=TIMEOUT, headers=HEADERS).json())
    except Exception as e:
        pytest.skip(f"endoflife.date unavailable: {e}")

    mapped = {k if isinstance(k, str) else k[0] for k in EOL_PRODUCTS}
    unmapped = []
    for r in ALL:
        names = {r.key, r.key.replace("_", "-"),
                 re.sub(r"[^a-z0-9]+", "-", r.name.lower()).strip("-")}
        if r.key not in mapped and names & products:
            unmapped.append(f"{r.key} ({', '.join(sorted(names & products))})")
    assert not unmapped, "add to EOL_PRODUCTS:\n  " + "\n  ".join(unmapped)
