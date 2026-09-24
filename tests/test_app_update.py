"""Deciding whether a newer VEIM has been released."""
import json
import time

from src.core import app_update


class _Response:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def _offline(*_a, **_k):
    raise app_update.requests.exceptions.ConnectionError("offline")


def serve(monkeypatch, payload):
    monkeypatch.setattr(app_update.requests, "get",
                        lambda *a, **k: _Response(payload))


def test_a_newer_tag_is_reported(state_file, monkeypatch):
    serve(monkeypatch, {"tag_name": "v2.0.0",
                        "html_url": "https://example.invalid/v2.0.0",
                        "body": "notes"})
    release = app_update.check(installed="1.0.1")
    assert release and release.version == "2.0.0"
    assert release.url == "https://example.invalid/v2.0.0"


def test_the_running_version_is_not_an_update(state_file, monkeypatch):
    serve(monkeypatch, {"tag_name": "v1.0.1", "html_url": "https://example.invalid"})
    assert app_update.check(installed="1.0.1") is None


def test_an_older_tag_is_not_an_update(state_file, monkeypatch):
    serve(monkeypatch, {"tag_name": "v0.9.0", "html_url": "https://example.invalid"})
    assert app_update.check(installed="1.0.1") is None


def test_a_tag_that_is_not_a_version_is_ignored(state_file, monkeypatch):
    serve(monkeypatch, {"tag_name": "nightly", "html_url": "https://example.invalid"})
    assert app_update.check(installed="1.0.1") is None


def test_a_failed_request_is_not_fatal(state_file, monkeypatch):
    def boom(*_a, **_k):
        raise app_update.requests.exceptions.ConnectionError("offline")

    monkeypatch.setattr(app_update.requests, "get", boom)
    assert app_update.check(installed="1.0.1") is None


def test_every_start_asks(state_file, monkeypatch):
    """VEIM is opened and closed rather than left running, so a stored answer
    is how a release published since the last run goes unmentioned."""
    calls = []

    def counted(*a, **k):
        calls.append(1)
        return _Response({"tag_name": "v2.0.0", "html_url": "https://example.invalid"})

    monkeypatch.setattr(app_update.requests, "get", counted)
    app_update.check(installed="1.0.1")
    app_update.check(installed="1.0.1")

    assert len(calls) == 2, "a start must not answer from the last start"


def test_a_check_that_cannot_reach_github_offers_what_was_known(state_file, monkeypatch):
    """Found yesterday, still worth offering on a train today."""
    state_file.write_text(json.dumps(
        {"pending": {"version": "2.0.0", "url": "https://example.invalid/v2"}}),
        encoding="utf-8")
    monkeypatch.setattr(app_update.requests, "get", _offline)

    release = app_update.check(installed="1.0.1")

    assert release and release.version == "2.0.0"


def test_a_state_file_missing_fields_does_not_raise(state_file, monkeypatch):
    """This file outlives the version that wrote it."""
    state_file.write_text(json.dumps({"pending": {"version": "9.9.9"}}),
                          encoding="utf-8")
    monkeypatch.setattr(app_update.requests, "get", _offline)

    release = app_update.check(installed="1.0.1")
    assert release and release.url == app_update.RELEASES_PAGE


def test_unreadable_state_is_treated_as_absent(state_file, monkeypatch):
    state_file.write_text("{ not json", encoding="utf-8")
    serve(monkeypatch, {"tag_name": "v2.0.0", "html_url": "https://example.invalid"})
    assert app_update.check(installed="1.0.1").version == "2.0.0"


def test_it_asks_about_releases_not_commits():
    """A branch head would flag every commit as a new version."""
    assert app_update.LATEST_API.endswith("/releases/latest")


# ------------------------------------------------------- the check a user asks for

def test_a_manual_check_reports_an_update(state_file, monkeypatch):
    serve(monkeypatch, {"tag_name": "v2.0.0",
                        "html_url": "https://example.invalid/v2.0.0"})
    result = app_update.check_now(installed="1.0.1")

    assert result.state == app_update.UPDATE_AVAILABLE
    assert result.update_available
    assert result.latest == "2.0.0"
    assert result.release.url == "https://example.invalid/v2.0.0"


def test_a_manual_check_reports_nothing_newer(state_file, monkeypatch):
    serve(monkeypatch, {"tag_name": "v1.0.1", "html_url": "https://example.invalid"})
    result = app_update.check_now(installed="1.0.1")

    assert result.state == app_update.UP_TO_DATE
    assert not result.update_available


def test_an_unreachable_github_is_not_up_to_date(state_file, monkeypatch):
    """check() answers None to both, which is all a banner needs. A button
    that said "no updates found" to a machine with no connection would lie."""
    def boom(*_a, **_k):
        raise app_update.requests.exceptions.ConnectionError("offline")

    monkeypatch.setattr(app_update.requests, "get", boom)
    result = app_update.check_now(installed="1.0.1")

    assert result.state == app_update.UNREACHABLE
    assert result.state != app_update.UP_TO_DATE
    assert "offline" in result.error


def test_a_manual_check_ignores_the_daily_throttle(state_file, monkeypatch):
    calls = []

    def counted(*a, **k):
        calls.append(1)
        return _Response({"tag_name": "v2.0.0", "html_url": "https://example.invalid"})

    monkeypatch.setattr(app_update.requests, "get", counted)
    app_update.check_now(installed="1.0.1")
    app_update.check_now(installed="1.0.1")

    assert len(calls) == 2, "pressing the button must ask, not recite"


def test_a_manual_check_records_what_it_found(state_file, monkeypatch):
    """Both write the same state, and that is what a later start with no
    connection falls back to."""
    serve(monkeypatch, {"tag_name": "v2.0.0", "html_url": "https://example.invalid"})
    app_update.check_now(installed="1.0.1")

    monkeypatch.setattr(app_update.requests, "get", _offline)

    assert app_update.check(installed="1.0.1").version == "2.0.0"


# ------------------------------------------------------- answers that stick

def test_a_skipped_version_is_muted(state_file):
    app_update.skip_version("2.0.0")

    assert app_update.is_muted("2.0.0")
    assert not app_update.is_muted("2.0.1"), "a newer release is a new question"


def test_skipping_also_covers_what_that_release_overtook(state_file):
    """A release can be withdrawn; being offered its predecessor after
    refusing it is not a new question."""
    app_update.skip_version("2.0.0")

    assert app_update.is_muted("1.5.0")


def test_snoozing_mutes_everything_for_a_week(state_file, monkeypatch):
    app_update.snooze()
    assert app_update.is_muted("9.9.9")
    assert app_update.is_snoozed(), "and the check can skip asking at all"

    later = time.time() + app_update.SNOOZE_DURATION + 1
    monkeypatch.setattr(app_update.time, "time", lambda: later)
    assert not app_update.is_muted("9.9.9")


def test_nothing_is_muted_to_begin_with(state_file):
    assert not app_update.is_muted("2.0.0")


def test_an_answer_survives_the_next_check(state_file, monkeypatch):
    """The check writes the same file; it must not wipe the reply."""
    app_update.skip_version("2.0.0")
    serve(monkeypatch, {"tag_name": "v2.0.0", "html_url": "https://example.invalid"})

    app_update.check_now(installed="1.0.1")

    assert app_update.is_muted("2.0.0")
