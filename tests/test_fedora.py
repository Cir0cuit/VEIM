"""Fedora resolution against a captured shape of releases.json.

Runs offline. The index identifies desktop spins by `subvariant` under a single
generic "Spins" variant; matching on `variant` alone silently made Cinnamon,
Xfce and Budgie unresolvable while Workstation kept working, so the gap only
showed up in a full-flavor sweep.
"""
import json

import pytest

from src.core.recipe_base import ScrapeError
from src.recipes.fedora import RELEASES_INDEX, FedoraRecipe, FedoraSpinsRecipe
from tests.test_stale_recipes import _with


SAMPLE = [
    {"version": "44", "arch": "x86_64", "variant": "Workstation", "subvariant": "Workstation",
     "link": "https://example.invalid/44/Workstation/x86_64/iso/Fedora-Workstation-Live-44-1.7.x86_64.iso",
     "sha256": "a" * 64, "size": "2851612672"},
    {"version": "43", "arch": "x86_64", "variant": "Workstation", "subvariant": "Workstation",
     "link": "https://example.invalid/43/Workstation/x86_64/iso/Fedora-Workstation-Live-43-1.2.x86_64.iso",
     "sha256": "b" * 64, "size": "2700000000"},
    {"version": "44", "arch": "x86_64", "variant": "Spins", "subvariant": "Cinnamon",
     "link": "https://example.invalid/44/Spins/x86_64/iso/Fedora-Cinnamon-Live-44-1.7.x86_64.iso",
     "sha256": "c" * 64, "size": "3084500992"},
    {"version": "44", "arch": "x86_64", "variant": "Spins", "subvariant": "Xfce",
     "link": "https://example.invalid/44/Spins/x86_64/iso/Fedora-Xfce-Live-44-1.7.x86_64.iso",
     "sha256": "d" * 64, "size": "2500000000"},
    {"version": "44", "arch": "aarch64", "variant": "Workstation", "subvariant": "Workstation",
     "link": "https://example.invalid/44/Workstation/aarch64/iso/Fedora-Workstation-44.aarch64.iso",
     "sha256": "e" * 64, "size": "1"},
    {"version": "Rawhide", "arch": "x86_64", "variant": "Workstation", "subvariant": "Workstation",
     "link": "https://example.invalid/rawhide/Fedora-Workstation-Rawhide.iso",
     "sha256": "f" * 64, "size": "1"},
]


@pytest.fixture
def recipe(monkeypatch):
    return _with(monkeypatch, FedoraRecipe(), {RELEASES_INDEX: json.dumps(SAMPLE)})[0]


def test_resolves_workstation_to_newest_version(recipe):
    info = recipe.fetch_download_info("workstation")
    assert info.version == "44"
    assert "Workstation-Live-44" in info.filename


def test_resolves_spins_by_subvariant(monkeypatch):
    """Regression: these were unresolvable when only `variant` was matched."""
    spins = _with(monkeypatch, FedoraSpinsRecipe(), {RELEASES_INDEX: json.dumps(SAMPLE)})[0]
    for flavor in ("cinnamon", "xfce"):
        info = spins.fetch_download_info(flavor)
        assert flavor in info.filename.lower(), f"{flavor} resolved to {info.filename}"
        assert info.version == "44"


def test_carries_checksum(recipe):
    info = recipe.fetch_download_info("workstation")
    assert info.sha256 == "a" * 64, "checksum must flow through so downloads get verified"


def test_ignores_other_architectures_and_rawhide(recipe):
    info = recipe.fetch_download_info("workstation")
    assert "aarch64" not in info.url
    assert "Rawhide" not in info.url


def test_unknown_flavor_fails_loudly(recipe):
    with pytest.raises(ScrapeError) as excinfo:
        recipe.fetch_download_info("no-such-spin")
    assert "no-such-spin" in str(excinfo.value)


def test_every_declared_flavor_is_resolvable_in_principle(recipe):
    """Each declared flavor must be a real id, not a label with no backing."""
    ids = [f.id for f in recipe.get_flavors()]
    assert "workstation" in ids and "kde" in ids
    # The desktop spins are an entry of their own, as on fedoraproject.org.
    assert "cinnamon" not in ids
    assert "cinnamon" in [f.id for f in FedoraSpinsRecipe().get_flavors()]
