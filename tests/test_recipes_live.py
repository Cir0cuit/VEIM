"""Live mirror sweep.

Excluded by default (see pyproject's addopts) because it depends on 30+ third-party
mirrors: a project having a bad day should not fail someone's build. Run it
deliberately when you suspect scraper rot:

    pytest -m network -v

It is the fastest way to find out which recipes have broken, and it fails with
the specific distro named rather than a generic timeout.
"""
import concurrent.futures as futures
import time

import pytest
import requests

from src.core.recipe_base import ScrapeError
from src.recipes.registry import registry

pytestmark = pytest.mark.network

TIMEOUT = 30
HEADERS = {"User-Agent": "curl/8.4.0"}
ALL = registry.get_all_recipes()


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
    ok, detail = _reachable(info.url)
    return None if ok else f"{recipe.key}/{flavor.id}: {detail} for {info.url}"


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
