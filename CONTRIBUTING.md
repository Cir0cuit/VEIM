# Contributing

```bash
git clone https://github.com/Cir0cuit/VEIM
cd VEIM
pip install -e ".[dev]"

pytest                  # 720-odd tests, no network and no display needed
pytest -m network       # also resolve all 216 editions against live mirrors
```

The offline suite runs headless on Qt's `offscreen` platform, and is what CI
runs on Linux, Windows and macOS across Python 3.10 and 3.12. Network tests are
excluded by default — a mirror having a bad day should not fail your build. Run
them when you suspect scraper rot: they fail with the distribution named. The
live sweep also fails when a recipe reports a label ("latest", "current") in
place of a version, and when the filename a recipe would write is one that
`iso_identity` reads back as a different entry, edition or version.

Work happens on `dev`. `main` is what gets tagged and released.

## Layout

```
main.py                    entry point
src/
├── core/
│   ├── paths.py           where the app may read from and write to
│   ├── branding.py        VEIM's own icon, and the Windows taskbar identity
│   ├── drive.py           cross-platform removable and Ventoy drive detection
│   ├── downloader.py      resumable transfers, SHA-256, archives, rate metering
│   ├── inventory.py       what is on the drive, reconciled against the filesystem;
│   │                      adoption candidates and exclusions
│   ├── iso_identity.py    which official download a filename is, if any
│   ├── ventoy_config.py   ventoy.json aliases and the search root
│   ├── recipe_base.py     DistroRecipe contract, DownloadInfo, ScrapeError, is_older
│   ├── icons.py           logo sources, rasterising and High-DPI caching
│   ├── app_update.py      whether a newer VEIM has been released
│   ├── browser.py         opening a link without the bundle's environment
│   └── logger.py
├── recipes/               one module per distribution family
│   └── registry.py        registration and the catalog taxonomy
├── assets/
│   ├── branding/          VEIM's own mark
│   └── icons/             one rendered logo per catalog entry, shipped
└── ui/
    ├── theme.py           palettes and the entire stylesheet
    ├── components.py      shared widgets: rows, chips, flow layout, combo box
    ├── sidebar.py         navigation and drive summary
    ├── drive_picker.py    startup drive chooser
    ├── dashboard.py       installed library and download orchestration
    ├── distro_card.py     one installed row: check, update in place, remove
    ├── downloading_card.py  a fresh install that has no row yet
    ├── adopt_dialog.py    choosing which loose ISOs to take in
    ├── catalog_view.py    browsable catalog
    ├── update_prompt.py   the automatic check, and the dialog it raises
    ├── update_button.py   the drive picker's "Check for VEIM Updates"
    ├── workspace.py       sidebar plus pages
    └── app.py             root window
packaging/                 PyInstaller spec and the per-OS installer recipes
tests/                     pytest suite
tools/                     development scripts
docs/images/               screenshots the README embeds
```

Views never call `setStyleSheet` themselves. Every widget carries an
`objectName` that the one generated stylesheet targets, so a new theme is a
`ThemeColors` entry rather than a sweep through the UI.

## Adding a distribution

Subclass `DistroRecipe`, implement `get_flavors()` and `fetch_download_info()`,
then register it in `src/recipes/registry.py` and add it to `CATEGORY_BY_KEY`
there — registration fails loudly if the entry is missing.

`fetch_download_info()` must `raise ScrapeError(self.name, reason)` when it
cannot determine a current release. Never return a hardcoded URL as a fallback;
the suite checks for it. Supply `sha256` when the project publishes one.

The version it reports is the one the user sees on the row and the one a later
check is compared against, so it has to be the release itself, found fresh each
time:

- Read the release listing and take the newest by numeric sort — not the
  first link on the page, not a folder pinned in the source.
- Never report a label. "latest", "current" and "stable" are not versions,
  and a row carrying one can never be told it is out of date.
- On a network error, raise. Falling back to an older release that happened
  to be reachable reports a stale version as current, which is worse than
  no answer; "No current release" on the row is the honest outcome.
- If the image's filename does not carry the version (Bazzite, Talos), rename
  it on the way down so that it does.

Then add a rule to `src/core/iso_identity.py` that reads that filename back
into the same key, flavor id and version — exact pattern, whole name. That is
what lets an ISO a user copied onto the drive be recognised and adopted, and
`pytest -m network` fails when a recipe's filename and its rule disagree.
Names that never change between releases get no rule on purpose.

Add an entry to `ICON_URLS` in `src/core/icons.py`, then run
`python tools/fetch_icons.py` and commit the PNG it writes to
`src/assets/icons/`. The app ships its logos rather than fetching them, and the
suite fails if a distribution has none.

Finally `python tools/readme_catalog.py --write`: the README's counts, category
table and edition list are generated from the registry, and a test fails when
they lag behind it.

## Adding a theme

Add a `ThemeColors` entry to `THEMES` in `src/ui/theme.py`. The theme menu and
the stylesheet are both generated from it. The suite checks every palette for
text contrast, for a readable button label, and for surfaces that would make a
row invisible against its background.

## Releasing

Bump `__version__` in `src/__init__.py` and `version` in `pyproject.toml`, then:

```bash
git tag v1.0.0
git push origin v1.0.0
```

`.github/workflows/release.yml` builds on four runners and publishes the result
to GitHub Releases:

| Runner | Artifact |
|---|---|
| `windows-latest` | Inno Setup installer, plus a portable zip |
| `ubuntu-22.04` | AppImage |
| `macos-15` | Apple Silicon disk image |
| `macos-15-intel` | Intel disk image |

The tag has to match `__version__` or the workflow stops before building
anything — the in-app update check compares the running version against the
release tag, so a mismatch would either hide a release or advertise one forever.

Publishing the release from the GitHub UI works too: that creates the tag, which
starts the same workflow, and the installers are uploaded to the release you
already wrote. Whichever way the tag arrives, the release ends up with four
installers and `SHA256SUMS.txt` attached.

Everything starts from PyInstaller: `pyinstaller packaging/veim.spec` produces
`dist/VEIM` (`dist/VEIM.app` on macOS), and the per-platform scripts under
`packaging/` wrap that. Building locally needs
[Inno Setup](https://jrsoftware.org/isdl.php) on Windows and `appimagetool` on
Linux; macOS needs only what ships with the system.

A frozen build runs from a read-only bundle, so nothing may write beside the
executable. `src/core/paths.py` is the only place that decides where runtime
files go, and a test fails if the spec stops bundling an asset the app reads.

## Scripts

| Script | Purpose |
|---|---|
| `tools/fetch_icons.py` | Renders the distribution logos in `ICON_URLS` into `src/assets/icons/`, which is committed and shipped. Checks each result: Qt renders a subset of SVG and fails silently on the rest, writing a blank image rather than none. |
| `tools/build_icons.py` | Renders `src/assets/branding/veim.svg` into the PNG, `.ico` and `.icns` files the app and the installers use. Run it after editing the SVG. |
| `tools/capture_docs_screenshots.py` | Regenerates the images the README embeds, from a scripted drive that puts a row in every state, plus the adoption dialog. Refuses to save if the sidebar shows a real path instead of `K:\`. Needs a display. |
| `tools/readme_catalog.py` | Prints the README's catalog section from the registry; `--write` puts it in place. |
| `tools/capture_ui_screenshots.py` | Renders the UI to `screenshots/` for local inspection. Not for documentation — the captures show a real path. |
| `tools/audit_icons.py` | Compares each Wikimedia logo against Wikimedia's own rendering of the same file. Run it after adding an SVG: Qt renders a subset of SVG and fails silently on the rest, producing a wrong image rather than none. |
