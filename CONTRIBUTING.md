# Contributing

```bash
git clone --recurse-submodules https://github.com/Cir0cuit/VEIM
cd VEIM
pip install -e ".[dev]"

pytest                  # the app: 550-odd tests, no network and no display needed
```

The offline suite runs headless on Qt's `offscreen` platform, and is what CI
runs on Linux, Windows and macOS across Python 3.10 and 3.12.

Work happens on `dev`. `main` is what gets tagged and released.

## Definitions

The recipes - how VEIM finds each distribution's current release - the
catalog and the filename rules are not in this repository. They are
[VEIM-definitions](https://github.com/Cir0cuit/VEIM-definitions), checked out
here as the `definitions/` submodule, and published from there as releases of
their own: VEIM checks for a newer one at every start and downloads it
(`src/core/definitions.py`). Fixing or adding a recipe is work in
`definitions/`, pushed to that repository, and needs no VEIM release. Its
[CONTRIBUTING.md](https://github.com/Cir0cuit/VEIM-definitions/blob/main/CONTRIBUTING.md)
has the rules and its own suite, including the live sweep against every
mirror, which its Mirrors workflow runs every Monday:

```bash
cd definitions
pytest                  # every recipe against fixture pages
pytest -m network       # every edition against its live mirror
```

What the two share is the contract in `src/core/recipe_base.py`:
`DistroRecipe`, `DownloadInfo`, `FlavorInfo`, `ScrapeError`, `IsoIdentity` and
the version helpers. Definitions declare the contract version they are written
for (`API`, matched by `definitions.API` here) and the oldest VEIM they run in
(`MIN_APP`); their CI tests every change against that VEIM and `main`. Adding
to the contract means a VEIM release first and a raised `MIN_APP` after;
changing it means a new `API` in both. The definitions may import only the
standard library modules they list in `STDLIB`, which the frozen build bundles
(`packaging/veim.spec`): an installed VEIM holds nothing else.

A source checkout runs its own `definitions/` and downloads nothing, so an edit
there is what runs. Run `python tools/readme_catalog.py --write` after moving
the submodule forward: the README's catalog is generated from it.

## Layout

```
main.py                    entry point
src/
├── core/
│   ├── paths.py           where the app may read from and write to
│   ├── branding.py        VEIM's own icon and typeface, and the Windows taskbar identity
│   ├── drive.py           cross-platform removable and Ventoy drive detection
│   ├── downloader.py      resumable transfers, SHA-256, archives, rate metering
│   ├── inventory.py       what is on the drive, reconciled against the filesystem;
│   │                      adoption candidates and exclusions
│   ├── ventoy_config.py   ventoy.json aliases and the search root
│   ├── recipe_base.py     the contract with the definitions: DistroRecipe,
│   │                      DownloadInfo, FlavorInfo, ScrapeError, IsoIdentity,
│   │                      version_key, is_older
│   ├── definitions.py     the check for newer definitions, and loading them
│   ├── icons.py           logo sources, and High-DPI caching of the shipped logos
│   ├── app_update.py      whether a newer VEIM has been released
│   ├── browser.py         opening a link without the bundle's environment
│   └── logger.py
├── assets/
│   ├── branding/          VEIM's own mark
│   ├── fonts/             Atkinson Hyperlegible Next, and its licence
│   └── icons/             one rendered logo per catalog entry, shipped
└── ui/
    ├── theme.py           palettes and the entire stylesheet
    ├── components.py      shared widgets: rows, chips, drive map, flow layout, combo box
    ├── sidebar.py         navigation and drive summary
    ├── drive_picker.py    startup drive chooser
    ├── dashboard.py       installed library and download orchestration
    ├── distro_card.py     one installed row: check, update in place, remove
    ├── unmanaged_row.py   one image VEIM leaves alone: adopt, menu name, delete
    ├── downloading_card.py  a fresh install that has no row yet
    ├── adopt_dialog.py    choosing which loose ISOs to take in
    ├── catalog_view.py    browsable catalog
    ├── update_prompt.py   the automatic check, and the dialog it raises
    ├── update_button.py   the drive picker's "Check for VEIM Updates"
    ├── workspace.py       sidebar plus pages
    └── app.py             root window
definitions/               the VEIM-definitions submodule: recipes, catalog,
                           filename rules
packaging/                 PyInstaller spec and the per-OS installer recipes
tests/                     pytest suite
tools/                     development scripts
docs/images/               screenshots the README embeds
```

Views never call `setStyleSheet` themselves. Every widget carries an
`objectName` that the one generated stylesheet targets, so a new theme is a
`ThemeColors` entry rather than a sweep through the UI.

## Adding a distribution

In `definitions/`: see its
[CONTRIBUTING.md](https://github.com/Cir0cuit/VEIM-definitions/blob/main/CONTRIBUTING.md).
What it needs from here is the logo: add an entry to `ICON_URLS` in
`src/core/icons.py`, run `python tools/fetch_icons.py` and commit the PNG it
writes to `src/assets/icons/`, so the next VEIM ships it. The suite fails if a
catalog entry has none.

## Adding a theme

Add a `ThemeColors` entry to `THEMES` in `src/ui/theme.py`. The theme menu and
the stylesheet are both generated from it. The suite checks every palette for
text contrast, for a readable button label, and for surfaces that would make a
row invisible against its background.

## Releasing

Move the `definitions` submodule to the latest commit on its `main`
(`git submodule update --remote definitions`): that is the copy a new install
falls back on. Bump `__version__` in `src/__init__.py` and `version` in
`pyproject.toml`, then:

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
Both are a plain X.Y.Z, which the workflow also enforces: the check compares
the numbers alone, so a `1.0.8rc1` would never be offered `1.0.8`.

Publishing the release from the GitHub UI works too: that creates the tag, which
starts the same workflow, and the installers are uploaded to the release you
already wrote. Whichever way the tag arrives, the release ends up with four
installers and `SHA256SUMS.txt` attached.

Everything starts from PyInstaller: `pyinstaller packaging/veim.spec` produces
`dist/VEIM` (`dist/VEIM.app` on macOS), and the per-platform scripts under
`packaging/` wrap that. Building
locally needs [Inno Setup](https://jrsoftware.org/isdl.php) on Windows and
`appimagetool` on Linux; macOS needs only what ships with the system.

A frozen build runs from a read-only bundle, so nothing may write beside the
executable. `src/core/paths.py` is the only place that decides where runtime
files go, and a test fails if the spec stops bundling an asset the app reads.

## Scripts

The icon scripts need Pillow, which is a development dependency only, so
install with `pip install -e ".[dev]"` first.

| Script | Purpose |
|---|---|
| `tools/fetch_icons.py` | Fetches and renders the distribution logos in `ICON_URLS` into `src/assets/icons/`, which is committed and shipped; only missing ones, or all of them with `--force`. Checks each result: Qt renders a subset of SVG and fails silently on the rest, writing a blank image rather than none. |
| `tools/build_icons.py` | Renders `src/assets/branding/veim.svg` into the PNG, `.ico` and `.icns` files the app and the installers use. Run it after editing the SVG. |
| `tools/capture_docs_screenshots.py` | Regenerates the images the README embeds, from a scripted drive that puts a row in every state, plus the adoption dialog. Refuses to save if the sidebar shows a real path instead of `K:\`. Needs a display. |
| `tools/readme_catalog.py` | Prints the README's catalog section from the registry; `--write` puts it in place. |
| `tools/capture_ui_screenshots.py` | Renders the UI to `screenshots/` for local inspection. Not for documentation — the captures show a real path. |
| `tools/audit_icons.py` | Compares each Wikimedia logo against Wikimedia's own rendering of the same file. Run it after adding an SVG: Qt renders a subset of SVG and fails silently on the rest, producing a wrong image rather than none. |
