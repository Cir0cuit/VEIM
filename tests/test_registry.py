"""Registry-wide invariants.

These run offline. The live-mirror sweep lives in test_recipes_live.py behind
the `network` marker.
"""
import inspect

import pytest

from src.recipes.registry import registry
from src.core.recipe_base import DistroRecipe, FlavorInfo


ALL = registry.get_all_recipes()


def test_registry_is_not_empty():
    assert len(ALL) >= 30


def test_keys_are_unique():
    # Read the keys off CATALOG itself: the registry is a dict by key, so a
    # duplicate would already have replaced the other entry there.
    from src.recipes.registry import CATALOG
    keys = [cls.key for cls in CATALOG]
    assert len(keys) == len(set(keys)), "duplicate recipe key would shadow an entry"


@pytest.mark.parametrize("recipe", ALL, ids=lambda r: r.key)
def test_recipe_declares_usable_metadata(recipe: DistroRecipe):
    assert recipe.key and recipe.key.strip()
    assert recipe.name and recipe.name.strip()
    assert recipe.category and recipe.category.strip()
    assert recipe.description, f"{recipe.key} has no catalog description"


@pytest.mark.parametrize("recipe", ALL, ids=lambda r: r.key)
def test_flavors_are_well_formed(recipe: DistroRecipe):
    flavors = recipe.get_flavors()
    assert flavors, f"{recipe.key} declares no flavors"
    assert all(isinstance(f, FlavorInfo) for f in flavors)

    ids = [f.id for f in flavors]
    assert len(ids) == len(set(ids)), f"{recipe.key} has duplicate flavor ids"
    assert all(i and i.strip() for i in ids)
    assert all(f.name and f.name.strip() for f in flavors)


@pytest.mark.parametrize("recipe", ALL, ids=lambda r: r.key)
def test_no_silent_stale_fallbacks(recipe: DistroRecipe):
    """Recipes must raise ScrapeError rather than return a pinned URL.

    A hardcoded fallback hands the user an outdated ISO that looks current, so
    every resolution path has to end in a raise rather than a DownloadInfo
    built from a baked-in version string.
    """
    # The recipe's own class and any shared base it resolves through: the four
    # Fedora entries are a table each, over one base that does the fetching.
    source = "\n".join(inspect.getsource(cls) for cls in type(recipe).__mro__
                       if cls.__module__.startswith("src.recipes"))
    lowered = source.lower()

    assert "# fallback" not in lowered, (
        f"{recipe.key} still has a fallback block; it should raise ScrapeError instead"
    )

    assert "ScrapeError" in source, (
        f"{recipe.key} never raises ScrapeError - it cannot fail loudly."
    )


def test_categories_cover_every_recipe():
    cats = registry.get_categories()
    assert cats[0] == "All"
    covered = {r.key for r in ALL if r.category in cats[1:]}
    assert covered == {r.key for r in ALL}


def test_categories_have_no_near_duplicates():
    """Guard against typo'd category names splitting one group into two.

    "Lightweight" vs "Lightweight & Fast" and "Rolling Release" vs "Rolling
    Releases" each rendered as two separate filter chips for what is really one
    category.
    """
    cats = [c for c in registry.get_categories() if c != "All"]
    normalised = {}
    for c in cats:
        key = c.lower().replace("&", "and").replace(" ", "").rstrip("s")
        normalised.setdefault(key, []).append(c)
    dupes = {k: v for k, v in normalised.items() if len(v) > 1}
    assert not dupes, f"near-duplicate categories: {list(dupes.values())}"


def test_every_category_is_a_filter_chip():
    """The catalog table in registry.py is the single source of truth."""
    from src.recipes.registry import CATALOG, CATEGORY_ORDER
    unknown = sorted(set(CATALOG.values()) - set(CATEGORY_ORDER))
    assert not unknown, f"categories missing from CATEGORY_ORDER: {unknown}"


def test_no_category_swallows_the_catalog():
    """A filter holding a third of the entries is not filtering anything.

    'Popular & Desktop' had grown to 18 of 50, which is what prompted the
    rebalance; this keeps any single bucket from drifting back there.
    """
    from collections import Counter
    counts = Counter(r.category for r in registry.get_all_recipes())
    total = sum(counts.values())
    worst, size = counts.most_common(1)[0]
    assert size <= total * 0.25, (
        f"{worst!r} holds {size} of {total} entries - split it up"
    )


def test_categories_are_listed_in_the_declared_order():
    from src.recipes.registry import CATEGORY_ORDER
    listed = registry.get_categories()
    assert listed[0] == "All"
    assert listed[1:] == [c for c in CATEGORY_ORDER if c in listed]
