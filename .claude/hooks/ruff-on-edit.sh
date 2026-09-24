#!/usr/bin/env bash
# Pyflakes checks on the .py file Claude just edited. Unused imports (F401, F541)
# are left out: an import written one edit before its use is not a mistake.
f=$(python -c "import json, sys; print(json.load(sys.stdin).get('tool_input', {}).get('file_path', ''))")
case "$f" in *.py) ;; *) exit 0 ;; esac
command -v uvx >/dev/null || exit 0
uvx ruff check --no-cache --quiet --select F,E9 --ignore F401,F541 "$f" >&2 || exit 2
