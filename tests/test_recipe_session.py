"""The session every recipe reads release pages with.

Regression: cdimage.debian.org answers HTTP 500 for a request or two at a
time. The Debian recipe parsed the error page as a listing, found no image in
it, and the row read "No current release" - shipped that way in 1.0.6.
"""
import requests
import pytest

from src.core import recipe_base
from src.recipes.debian import DebianRecipe


def _response(status: int, url: str = "https://cdimage.debian.org/debian-cd/current/"):
    r = requests.Response()
    r.status_code = status
    r.url = url
    return r


def test_server_errors_are_retried_before_being_refused():
    session = DebianRecipe().get_session()
    for scheme in ("https://", "http://"):
        retry = session.get_adapter(scheme + "example.invalid/").max_retries
        assert retry.total == recipe_base.SERVER_ERROR_RETRIES
        assert set(retry.status_forcelist) == set(recipe_base.SERVER_ERROR_STATUSES)
        assert retry.backoff_factor == recipe_base.SERVER_ERROR_BACKOFF
        assert "GET" in retry.allowed_methods and "HEAD" in retry.allowed_methods
        assert not retry.raise_on_status, "the hook says what happened; urllib3's error does not"
    assert recipe_base._refuse_server_errors in session.hooks["response"]


@pytest.mark.parametrize("status", recipe_base.SERVER_ERROR_STATUSES)
def test_a_server_error_that_survives_the_retries_is_raised_not_parsed(status):
    with pytest.raises(requests.HTTPError) as err:
        recipe_base._refuse_server_errors(_response(status))
    assert str(err.value) == f"cdimage.debian.org answered HTTP {status}"


@pytest.mark.parametrize("status", (200, 206, 301, 403, 404, 429))
def test_anything_below_500_is_still_an_answer(status):
    """A 404 is read by several recipes: "that release has no images yet"."""
    assert recipe_base._refuse_server_errors(_response(status)).status_code == status
