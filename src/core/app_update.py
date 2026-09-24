"""Whether a newer VEIM has been released.

Checks the GitHub Releases API, not a branch: what people install comes from a
release, so that is what a version comparison has to be against.

Two entry points. check() is the automatic one, and it answers None whether
there is nothing new or GitHub never answered, because the prompt has nothing
to say in either case. check_now() is for someone who pressed a button, and it
distinguishes those two outcomes - telling a user with no connection that they
are up to date would be a lie.

Both ask every time they are called. VEIM is opened, used and closed rather
than left running, so a check is one request per start, and a cached answer
from the last run is precisely how a release published since then goes
unmentioned. What is stored is a fallback rather than a shortcut: it stands in
when GitHub cannot be reached, so a release already known about is still
offered on a train.

An answer of "no thanks" is remembered: skip_version() retires one release for
good and snooze() stops the asking for a week. Both are read by is_muted(),
which only the automatic check consults - somebody who presses the button is
asking, and gets an answer whatever they refused before.
"""
import json
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

SNOOZE_DURATION = 7 * 24 * 3600
STATE_FILE = "update_check.json"

# What a check found.
UPDATE_AVAILABLE = "update"
UP_TO_DATE = "current"
UNREACHABLE = "unreachable"


@dataclass(frozen=True)
class Release:
    version: str
    url: str
    notes: str


@dataclass(frozen=True)
class CheckResult:
    """One check's outcome, including the case a bare Release cannot express:
    the answer never arrived. `release` is set only when what GitHub published
    is newer than the running build."""
    state: str
    latest: str = ""
    release: Optional[Release] = None
    error: str = ""

    @property
    def update_available(self) -> bool:
        return self.release is not None


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


def _fetch(installed: str) -> CheckResult:
    """Ask GitHub what the latest release is and record the answer."""
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
        return CheckResult(UNREACHABLE, error=str(e))

    tag = str(payload.get("tag_name", "")).lstrip("vV")
    url = payload.get("html_url") or RELEASES_PAGE
    notes = (payload.get("body") or "").strip()

    state = _read_state()
    state["last_check"] = time.time()
    state["pending"] = {"version": tag, "url": url, "notes": notes[:2000]}
    _write_state(state)

    if not _newer(tag, installed):
        return CheckResult(UP_TO_DATE, latest=tag)

    log.info(f"VEIM {tag} is available (running {installed})")
    return CheckResult(UPDATE_AVAILABLE, latest=tag,
                       release=Release(tag, url, notes))


def _pending_release(state: dict, installed: str) -> Optional[Release]:
    """What the last check that did reach GitHub found, if it is still newer.

    Every field is read defensively: this file outlives the version that wrote
    it, and a missing key here would kill the checking thread.
    """
    pending = state.get("pending") or {}
    if not _newer(pending.get("version", ""), installed):
        return None
    return Release(pending["version"],
                   pending.get("url") or RELEASES_PAGE,
                   pending.get("notes", ""))


def check(installed: str = __version__) -> Optional[Release]:
    """The published release when it is newer than this build, else None.

    Asks every time, which is once per start. Never raises: a check that could
    not reach GitHub falls back to what the last one found, and otherwise
    leaves the app working exactly as it was, which is the whole point of it
    being optional.
    """
    result = _fetch(installed)
    if result.state == UNREACHABLE:
        return _pending_release(_read_state(), installed)
    return result.release


def check_now(installed: str = __version__) -> CheckResult:
    """A check somebody asked for, so it always goes to the network.

    Answering a button press with yesterday's cached result would make the
    button look broken the one time it matters.
    """
    return _fetch(installed)


def skip_version(version: str) -> None:
    """Never raise this release again. A later one still gets through."""
    state = _read_state()
    state["skipped_version"] = version
    _write_state(state)
    log.info(f"VEIM {version} skipped; a newer release will still be offered")


def snooze(duration: float = SNOOZE_DURATION) -> None:
    """Stop asking for a while, whatever gets published in the meantime."""
    state = _read_state()
    state["snoozed_until"] = time.time() + duration
    _write_state(state)


def is_snoozed() -> bool:
    """Whether the asking is off for a while.

    Version-independent, unlike a skip, so the automatic check can consult it
    before the request rather than after: a week of quiet is also a week of not
    troubling GitHub.
    """
    return time.time() < _read_state().get("snoozed_until", 0)


def is_muted(version: str) -> bool:
    """Whether the user has already refused to hear about this release.

    Only the automatic check asks. A prompt that cannot be turned off is worse
    than no prompt, and a button that ignores the user is worse still - so
    check_now() never consults this.
    """
    skipped = _read_state().get("skipped_version", "")
    if skipped and not _newer(version, skipped):
        # This release, or one it has already overtaken, was refused.
        return True
    return is_snoozed()
