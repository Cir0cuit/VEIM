@CONTRIBUTING.md

- Run tests with `python -m pytest`; set `QT_QPA_PLATFORM=offscreen` to run them without a display.
- Recipes live in the `definitions/` submodule (its own repository and suite): `cd definitions && python -m pytest`.
- Check one recipe against its live mirror: `cd definitions && python -m pytest -m network tests/test_recipes_live.py -k <key>`.
- A push to the definitions repository's `main` reaches every VEIM user at their next start; no VEIM release needed.
