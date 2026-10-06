"""The freshness harness catches what it exists to catch.

Toy recipes stand in for the three ways a real one went stale: the first link
on the page, a text sort, and a timeout answered with the previous release.
"""
import json
import re

import pytest
import requests

from src.core.recipe_base import DistroRecipe, DownloadInfo, FlavorInfo, ScrapeError, hrefs, version_key
from tests.freshness import Case, Resp, StrictSession, assert_newest, assert_no_fallback, permutations, use


def _listing(*names):
    return "<html><body><h1>Index</h1>" + "".join(f'<a href="{n}">{n}</a>\n' for n in names) + "</body></html>"


# ------------------------------------------------------------ permutations

def test_html_links_are_reordered_and_the_markup_around_them_kept():
    page = _listing("a.iso", "b.iso", "c.iso", "d.iso")
    variants = permutations(page)
    assert variants[0] == _listing("d.iso", "c.iso", "b.iso", "a.iso")
    assert 2 <= len(variants) <= 4 and page not in variants
    for v in variants:
        assert sorted(hrefs(v)) == ["a.iso", "b.iso", "c.iso", "d.iso"]
        assert v.startswith("<html><body><h1>Index</h1>") and v.endswith("</body></html>")


def test_table_rows_move_with_the_cells_in_them():
    page = "<table><tr><td>22.1</td><td><a href=x>X</a></td></tr><tr><td>22.3</td><td><a href=y>Y</a></td></tr></table>"
    assert permutations(page) == [
        "<table><tr><td>22.3</td><td><a href=y>Y</a></td></tr><tr><td>22.1</td><td><a href=x>X</a></td></tr></table>"]


def test_rss_items_are_reordered():
    feed = "<rss><channel><title>t</title>" + "".join(
        f"<item><title>/v{n}.iso</title></item>" for n in (1, 2, 3)) + "</channel></rss>"
    variants = permutations(feed)
    assert variants[0].index("/v3.iso") < variants[0].index("/v1.iso")
    assert all(v.startswith("<rss><channel><title>t</title><item>") for v in variants)


def test_json_lists_are_reordered_and_each_release_assets_with_them():
    releases = json.dumps([{"tag_name": t, "assets": [{"name": f"{t}-{i}"} for i in range(3)]} for t in ("1", "2", "3")])
    first = json.loads(permutations(releases)[0])
    assert [r["tag_name"] for r in first] == ["3", "2", "1"]
    assert [a["name"] for a in first[0]["assets"]] == ["3-2", "3-1", "3-0"]

    table = json.dumps({"data": [{"name": n} for n in "abcd"]})
    assert [d["name"] for d in json.loads(permutations(table)[0])["data"]] == list("dcba")


def test_text_lines_are_reordered():
    assert permutations("one\ntwo\nthree\n")[0] == "three\ntwo\none\n"


@pytest.mark.parametrize("page", ['{"version": "1.0"}', "<p>one link: <a href=x>x</a></p>", "26.05\n", ""])
def test_a_page_with_nothing_to_reorder_comes_back_once(page):
    assert permutations(page) == [page]


# ------------------------------------------------------------ the session

def test_an_unmapped_url_is_a_failure_not_a_404():
    session = StrictSession({"https://x.invalid/a": "page"})
    assert session.get("https://x.invalid/a").text == "page"
    with pytest.raises(AssertionError, match="fixture missing https://x.invalid/a/"):
        session.get("https://x.invalid/a/")
    with pytest.raises(AssertionError):
        session.head("https://x.invalid/a?jsontable")
    assert session.missing == ["https://x.invalid/a/", "https://x.invalid/a?jsontable"]


def test_a_404_is_an_answer_and_a_5xx_is_refused_as_live():
    session = StrictSession({"https://x.invalid/404": Resp("", 404),
                             "https://x.invalid/503": Resp("", 503),
                             "https://x.invalid/t": TimeoutError("slow")})
    gone = session.get("https://x.invalid/404")
    assert gone.status_code == 404 and gone.url == "https://x.invalid/404"
    with pytest.raises(requests.HTTPError):
        gone.raise_for_status()
    with pytest.raises(requests.HTTPError, match="x.invalid answered HTTP 503"):
        session.get("https://x.invalid/503")
    with pytest.raises(TimeoutError):
        session.get("https://x.invalid/t")


def test_github_latest_reads_through_the_patched_session(monkeypatch):
    recipe, session = use(monkeypatch, _FirstLink(), {
        "https://api.github.com/repos/o/r/releases/latest": json.dumps({"tag_name": "v2", "assets": []})})
    assert recipe.github_latest("o/r") == ("v2", [])
    assert session.asked == ["https://api.github.com/repos/o/r/releases/latest"]


# ------------------------------------------------------------ toy recipes

ROOT = "https://toy.invalid/releases/"


class _Toy(DistroRecipe):
    key, name, description = "toy", "Toy", "A recipe for testing the harness."
    FLAVORS = [FlavorInfo("std", "Standard")]

    def releases(self, session):
        r = session.get(ROOT, timeout=10)
        r.raise_for_status()
        return [m.group(1) for m in map(re.compile(r"(\d+(?:\.\d+)*)/$").match, hrefs(r.text)) if m]

    def info(self, session, version):
        r = session.get(f"{ROOT}{version}/", timeout=10)
        r.raise_for_status()
        fname = next(h for h in hrefs(r.text) if h.endswith(".iso"))
        return DownloadInfo(version=version, url=f"{ROOT}{version}/{fname}", filename=fname)


class _FirstLink(_Toy):
    def fetch_download_info(self, flavor_id):
        try:
            return self.info(session := self.get_session(), self.releases(session)[0])
        except Exception as e:
            raise ScrapeError(self.name, str(e))


class _NumericMax(_Toy):
    def fetch_download_info(self, flavor_id):
        try:
            session = self.get_session()
            return self.info(session, max(self.releases(session), key=version_key))
        except Exception as e:
            raise ScrapeError(self.name, str(e))


class _FallsBack(_Toy):
    def fetch_download_info(self, flavor_id):
        session = self.get_session()
        for version in sorted(self.releases(session), key=version_key, reverse=True):
            try:
                return self.info(session, version)
            except Exception:
                continue
        raise ScrapeError(self.name, "nothing")


CASE = Case(
    pages={
        ROOT: _listing("9/", "10/", "8/"),
        ROOT + "8/": _listing("toy-8.iso"),
        ROOT + "9/": _listing("toy-9.iso"),
        ROOT + "10/": _listing("toy-10.iso"),
    },
    flavor="std", newest="10", filename="toy-10.iso",
    newest_urls=(ROOT + "10/",),
)


def test_assert_newest_catches_a_recipe_that_takes_the_first_link(monkeypatch):
    # The page as written puts the newest second, so only a reordering exposes it.
    with pytest.raises(AssertionError, match="pages as written: reported 9, newest is 10"):
        assert_newest(monkeypatch, _FirstLink, CASE)
    lucky = Case({**CASE.pages, ROOT: _listing("10/", "9/", "8/")}, "std", "10")
    with pytest.raises(AssertionError, match=r"releases/ reversed: reported 8"):
        assert_newest(monkeypatch, _FirstLink, lucky)


def test_assert_newest_passes_a_recipe_that_takes_the_numeric_max(monkeypatch):
    assert_newest(monkeypatch, _NumericMax, CASE)


def test_assert_newest_fails_when_the_recipe_asks_for_a_page_the_fixture_lacks(monkeypatch):
    pages = dict(CASE.pages)
    del pages[ROOT + "10/"]
    with pytest.raises(AssertionError, match=r"fixture missing \['https://toy.invalid/releases/10/'\]"):
        assert_newest(monkeypatch, _NumericMax, Case(pages, "std", "10"))


def test_assert_no_fallback_catches_a_recipe_that_serves_the_previous_release(monkeypatch):
    with pytest.raises(AssertionError, match="TimeoutError.*reported 9 instead of raising ScrapeError"):
        assert_no_fallback(monkeypatch, _FallsBack, CASE)


def test_assert_no_fallback_passes_a_recipe_that_refuses(monkeypatch):
    assert_no_fallback(monkeypatch, _NumericMax, CASE)


def test_assert_no_fallback_refuses_a_url_the_recipe_never_reads(monkeypatch):
    case = Case(CASE.pages, "std", "10", newest_urls=(ROOT + "8/",))
    with pytest.raises(AssertionError, match="never asked for"):
        assert_no_fallback(monkeypatch, _NumericMax, case)
