@CONTRIBUTING.md

- Run tests with `python -m pytest`; set `QT_QPA_PLATFORM=offscreen` to run them without a display.
- Check one recipe against its live mirror: `python -m pytest -m network tests/test_recipes_live.py -k <key>`.
