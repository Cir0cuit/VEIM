---
name: add-distro
description: Add a distribution or tool to the VEIM catalog with every step CONTRIBUTING.md requires. Use when asked to add a distro, recipe, edition or catalog entry.
argument-hint: <distribution name>
---
Add $ARGUMENTS to the catalog. The rules are in CONTRIBUTING.md, "Adding a distribution".

1. Recipe: subclass `DistroRecipe` in the fitting `src/recipes/` module, set `key`, `name`, `description` and `FLAVORS` (a list of `FlavorInfo(id, name)`), and implement `fetch_download_info()`:
   - newest release by numeric sort, never a label, `ScrapeError(self.name, reason)` on any network error, no hardcoded fallback;
   - `sha256` when the project publishes one;
   - read pages and feeds with the helpers in `src/core/recipe_base.py` (`hrefs`, `table_rows`, `version_key`, `github_latest`, `sourceforge_rss`) rather than a local copy;
   - if the image's filename lacks the version, rename it on the way down so it carries one.
2. Add the class to `CATALOG` in `src/recipes/registry.py` with its category (one of `CATEGORY_ORDER`).
3. Add a `_Rule` to `src/core/iso_identity.py` that reads the downloaded filename back to the same key, flavor id and version (exact, whole-name pattern). Skip it only for names that never change between releases.
4. Add the logo to `ICON_URLS` in `src/core/icons.py`, run `python tools/fetch_icons.py` and check the PNG it writes to `src/assets/icons/` is not blank. For a Wikimedia SVG also run `python tools/audit_icons.py`.
5. `python tools/readme_catalog.py --write`.
6. Verify: `python -m pytest -m network tests/test_recipes_live.py -k <key> -v`, then `python -m pytest -q`.
