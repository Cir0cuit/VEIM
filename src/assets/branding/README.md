# Branding

## VEIM's own mark

`veim.svg` is the master. Everything else is generated from it by
`python tools/build_icons.py` and committed, because the installers need an
icon before any Python is available to render one:

| File | Used by |
|---|---|
| `veim-<size>.png` | The window and taskbar icon (`src/core/branding.py`), and the Linux hicolor icon theme. |
| `veim.ico` | Windows Start Menu and Desktop shortcuts. |
| `veim.icns` | The macOS `VEIM.app` bundle. |

## Bundled third-party logos

Logos here ship with the app because no mark-only file can be fetched from the
project. Everything else is downloaded at first run and kept out of git (see
`.gitignore`), so add to this folder only when there is no usable URL.

| File | Project | Why bundled |
|---|---|---|
| `tails.svg` | [Tails](https://tails.net/) | The published files are wordmarks with a baked white background, which reads as a pasted sticker inside a square icon chip. |

These are third-party trademarks, included to identify the projects they belong
to. If you fork and redistribute this app, check each project's trademark policy
first — Tails' is at <https://tails.net/contribute/how/promote/>.
