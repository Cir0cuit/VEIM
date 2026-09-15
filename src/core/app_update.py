"""Whether a newer VEIM has been released.

Checks the GitHub Releases API, not a branch: what people install comes from a
release, so that is what a version comparison has to be against.
"""
import json
import os
import time
from dataclasses import dataclass
from typing import Optional

import requests
from packaging.version import InvalidVersion, Version

from src import __version__
from src.core import paths
from src.core.logger import log

REPO = "Cir0cuit/VEIM"
LATEST_API = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPO}/releases/latest"

CHECK_INTERVAL = 24 * 3600
STATE_FILE = "update_check.json"


@dataclass(frozen=True)
class Release:
    version: str
    url: str
    notes: str


def _read_state() -> dict:
    try:
        with open(paths.state_path(STATE_FILE), encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return {}


def _write_state(state: dict) -> None:
    try:
        with open(paths.state_path(STATE_FILE), "w", encoding="utf-8") as handle:
            json.dump(state, handle)
    except OSError as e:
        log.debug(f"Could not record the update check: {e}")


def _newer(candidate: str, installed: str) -> bool:
    try:
        return Version(candidate) > Version(installed)
    except InvalidVersion:
        # A tag that is not a version number is not something to compare.
        return False


def check(installed: str = __version__, force: bool = False) -> Optional[Release]:
    """The published release when it is newer than this build, else None.

    Throttled to one request a day. Never raises: a failed check leaves the app
    working exactly as it was, which is the whole point of it being optional.
    """
    state = _read_state()
    if not force and time.time() - state.get("last_check", 0) < CHECK_INTERVAL:
        pending = state.get("pending")
        if pending and _newer(pending.get("version", ""), installed):
            return Release(pending["version"], pending["url"], pending.get("notes", ""))
        return None

    try:
        response = requests.get(
            LATEST_API,
            headers={"Accept": "application/vnd.github+json",
                     "User-Agent": f"veim/{installed}"},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as e:
        log.debug(f"Update check could not reach GitHub: {e}")
        return None

    tag = str(payload.get("tag_name", "")).lstrip("vV")
    url = payload.get("html_url") or RELEASES_PAGE
    notes = (payload.get("body") or "").strip()

    state["last_check"] = time.time()
    state["pending"] = {"version": tag, "url": url, "notes": notes[:2000]}
    _write_state(state)

    if not _newer(tag, installed):
        return None

    log.info(f"VEIM {tag} is available (running {installed})")
    return Release(tag, url, notes)
