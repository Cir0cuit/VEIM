#!/usr/bin/env bash
# Runs the offline suite when Claude ends a turn with code changes in the tree.
# Exit 2 hands the failure back to Claude instead of letting it stop.
input=$(cat)
# Already continuing because of this hook: stop rather than loop.
echo "$input" | grep -Eq '"stop_hook_active" *: *true' && exit 0
cd "$CLAUDE_PROJECT_DIR" || exit 0
[ -z "$(git status --porcelain -- src tests tools main.py)" ] && exit 0
out=$(QT_QPA_PLATFORM=offscreen python -m pytest -q -x 2>&1) && exit 0
echo "$out" | tail -30 >&2
exit 2
