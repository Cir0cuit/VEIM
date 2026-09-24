---
name: fix-recipe
description: Diagnose and fix a VEIM distribution recipe that fails, reports a stale release, or reports a label instead of a version. Use when a live mirror test fails, a row shows "No current release", or a recipe offers an old version.
argument-hint: <recipe-key>
---
Fix the recipe with key `$0`. The rules are in CONTRIBUTING.md, "Adding a distribution".

1. Reproduce: `python -m pytest -m network tests/test_recipes_live.py -k $0 -v`. Note which flavor fails and why.
2. Fetch the pages the recipe's `fetch_download_info()` reads and compare them with what the code expects.
3. Fix it:
   - newest release by numeric sort over the whole listing, never the first link or a pinned folder;
   - never a label ("latest", "current", "stable") as the version;
   - on a network error raise `ScrapeError(self.name, reason)`; no fallback to an older release or a hardcoded URL;
   - supply `sha256` when the project publishes one.
4. If the image's filename changed, update its `_Rule` in `src/core/iso_identity.py` (exact, whole-name pattern).
5. Add an offline regression to `tests/test_stale_recipes.py`: capture the shape of the page that broke the recipe and serve it with `_with(monkeypatch, Recipe(), pages)`; `_listing`, `_jsontable` and `_Resp` build the pages.
6. Verify: `python -m pytest -q`, then the command from step 1.
