---
name: release
description: Cut a VEIM release - bump the version, regenerate the README screenshots, test, commit, then tag after confirmation
argument-hint: <X.Y.Z>
disable-model-invocation: true
---
Release VEIM $0.

1. Be on `dev` with a clean tree, level with `origin/dev`; stop otherwise.
2. Set `__version__` in `src/__init__.py` and `version` in `pyproject.toml` to `$0`.
3. `python tools/capture_docs_screenshots.py` (needs a real display, not `offscreen`).
4. `python -m pytest -q`. Stop on any failure.
5. Commit the two version files and `docs/images/` as `Release $0`.
6. Show `git log --oneline origin/main..dev` and wait for my go-ahead. Then:
   - `git fetch . dev:main` (fast-forwards the local main)
   - `git push origin dev main`
   - `git tag v$0` and `git push origin v$0`

   The tag starts `.github/workflows/release.yml`, which builds and publishes the installers.
