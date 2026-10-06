"""Offline proof that a recipe reports the newest release, whatever the page order.

The live sweep cannot tell a current release from an old one that still
answers - old images stay on mirrors for years - and a fixture written newest
first passes a recipe that takes the first link. So every recipe gets a Case:
captured shapes of what the project publishes, and the version it must report.
assert_newest then reads every page in several orders, and assert_no_fallback
makes the newest release unreachable and expects a refusal.

What a Case's pages must hold, or the test proves nothing:

- an older final release whose pages and images all answer. If they 404, a
  recipe that walks releases oldest first still lands on the newest one;
- the newest final release neither first nor last in page order;
- a pre-release (beta, rc, -testing) numbered above the newest final;
- a label alias ("-latest", "-current", "-Current.iso") where the project
  publishes one;
- a pair where text order and number order disagree: 9 vs 10, 8.8 vs 8.10,
  s4 vs s10, 178.9 vs 178.27;
- for a recipe that picks a series or major first, all of the above at the
  series level too.

Every URL a recipe asks for must be in the pages. StrictSession raises for one
that is not, rather than answering 404, because several recipes read a 404 as
"not released yet" and move on to the previous release - a typo in a fixture
then tests the fallback path while appearing to test the newest.
"""
import json
import random
import re
from dataclasses import dataclass, field
from typing import Optional

import requests

from src.core.recipe_base import ScrapeError, _refuse_server_errors


class Resp:
    """A response as recipes read one: text, status, final URL, headers, JSON."""

    def __init__(self, text="", status_code=200, url="", headers=None):
        self.text, self.status_code, self.url = text, status_code, url
        self.headers = headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}", response=self)

    def json(self):
        return json.loads(self.text)


class StrictSession:
    """Serves `pages` by exact URL, query string included.

    A str is a 200, a Resp is returned as it is (with the requested URL when it
    names none), and an Exception is raised. A 5xx Resp is refused the way
    get_session refuses one, so a recipe sees the HTTPError it would see live.
    An unmapped URL raises AssertionError and is recorded in `missing`: a
    recipe that swallows every exception would otherwise turn a missing
    fixture into a silent "not there". There is no lookup without the query:
    "?jsontable" and the plain listing are different documents.
    """

    def __init__(self, pages):
        self.pages = dict(pages)
        self.headers = {}
        self.asked, self.missing = [], []

    def get(self, url, **kw):
        self.asked.append(url)
        if url not in self.pages:
            self.missing.append(url)
            raise AssertionError(f"fixture missing {url}")
        page = self.pages[url]
        if isinstance(page, Exception):
            raise page
        if isinstance(page, Resp):
            resp = Resp(page.text, page.status_code, page.url or url, page.headers)
        else:
            resp = Resp(page, url=url)
        return _refuse_server_errors(resp)

    head = get


def use(monkeypatch, recipe, pages):
    """Point `recipe` at `pages`. github_latest and sourceforge_rss both read
    through get_session, so they need no patch of their own."""
    session = StrictSession(pages)
    monkeypatch.setattr(recipe, "get_session", lambda: session)
    return recipe, session


@dataclass
class Case:
    pages: dict
    flavor: str
    newest: str                     # the version the recipe must report
    filename: Optional[str] = None
    newest_urls: tuple = ()         # making any one of these fail must raise ScrapeError
    # "keep_order": URLs whose item order carries meaning and is not permuted
    # (say why beside it). Anything else a group's own tests need.
    extra: dict = field(default_factory=dict)


# ------------------------------------------------------------ permutations

_ITEM = re.compile(r"<item\b.*?</item>", re.I | re.S)
_ROW = re.compile(r"<tr\b.*?</tr>", re.I | re.S)
_LINK = re.compile(r"<a\b[^>]*>.*?</a>", re.I | re.S)
_ORDERS = ("reversed", 1, 2, 3)


def _order(mode, n, rng):
    return list(range(n))[::-1] if mode == "reversed" else rng.sample(range(n), n)


def _respan(text, spans, order):
    """`text` with the span at position i replaced by span order[i]; the markup
    between items stays where it was."""
    out, last = [], 0
    for (start, end), i in zip(spans, order):
        out += [text[last:start], text[spans[i][0]:spans[i][1]]]
        last = end
    return "".join(out) + text[last:]


def _json_items(data):
    """The list a JSON page is a listing of: the page itself, or the one list
    in a top-level object ({"data": [...]}, a release's "assets")."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        lists = [v for v in data.values() if isinstance(v, list)]
        if len(lists) == 1:
            return lists[0]
    return None


def _reorder_json(data, mode, rng):
    items = _json_items(data)
    items[:] = [items[i] for i in _order(mode, len(items), rng)]
    for item in items:
        if isinstance(item, dict) and isinstance(item.get("assets"), list):
            item["assets"] = [item["assets"][i] for i in _order(mode, len(item["assets"]), rng)]
    return data


def _variants(text):
    """[(label, page)] for each distinct reordering of `text`'s items."""
    try:
        data = json.loads(text) if text.lstrip()[:1] in ("[", "{") else None
    except ValueError:
        data = None

    if data is not None and _json_items(data):
        def build(mode, rng):
            # Re-dumped with json.dumps defaults, as fixtures write it.
            return json.dumps(_reorder_json(json.loads(text), mode, rng))
    else:
        # RSS items; else table rows, which carry a version cell with its
        # links (linuxmint.com); else links; else the lines of a text file.
        for pattern in (_ITEM, _ROW, _LINK):
            spans = [m.span() for m in pattern.finditer(text)]
            if len(spans) > 1:
                break
        else:
            spans = None
        if spans:
            def build(mode, rng):
                return _respan(text, spans, _order(mode, len(spans), rng))
        elif re.search(r"<[A-Za-z!?/]", text):
            return []                   # markup with one item or none: nothing to reorder
        else:
            lines = text.splitlines()
            tail = "\n" if text.endswith("\n") else ""

            def build(mode, rng):
                return "\n".join(lines[i] for i in _order(mode, len(lines), rng)) + tail

    seen, out = {text}, []
    for mode in _ORDERS:
        page = build(mode, random.Random(mode if mode != "reversed" else 0))
        if page not in seen:
            seen.add(page)
            out.append(("reversed" if mode == "reversed" else f"shuffle {mode}", page))
    return out


def permutations(text):
    """`text` with its items reordered: reversed, then three seeded shuffles,
    duplicates dropped. A page with nothing to reorder comes back once, as it is."""
    return [page for _, page in _variants(text)] or [text]


# --------------------------------------------------------------- assertions

def _resolve(monkeypatch, recipe_cls, case, pages, where):
    recipe, session = use(monkeypatch, recipe_cls(), pages)
    try:
        info = recipe.fetch_download_info(case.flavor)
    except Exception as e:
        raise AssertionError(f"{where}: raised {e!r}; fixture missing {session.missing}") from e
    assert not session.missing, f"{where}: fixture missing {session.missing}"
    assert info.version == case.newest, f"{where}: reported {info.version}, newest is {case.newest}"
    if case.filename is not None:
        assert info.filename == case.filename, f"{where}: filename {info.filename}"
    return info


def assert_newest(monkeypatch, recipe_cls, case):
    """The newest release, from the pages as written and with each page's items
    reordered in turn - so taking the first link, the last, or a text sort
    fails whichever order the fixture's author happened to use."""
    _resolve(monkeypatch, recipe_cls, case, case.pages, "pages as written")
    keep = set(case.extra.get("keep_order", ()))
    for url, page in case.pages.items():
        if url in keep:
            continue
        if isinstance(page, Resp) and page.status_code == 200:
            text = page.text
        elif isinstance(page, str):
            text = page
        else:
            continue
        for label, variant in _variants(text):
            if isinstance(page, Resp):
                variant = Resp(variant, page.status_code, page.url, page.headers)
            _resolve(monkeypatch, recipe_cls, case, {**case.pages, url: variant}, f"{url} {label}")


def assert_no_fallback(monkeypatch, recipe_cls, case):
    """With any newest-release URL timing out or answering 503, ScrapeError -
    never the previous release, which a reachable older page offers as if it
    were current."""
    assert case.newest_urls, "a Case names the URLs its newest release is read from"
    for url in case.newest_urls:
        assert url in case.pages, f"{url} is not among the pages"
        for failure in (TimeoutError(f"timed out: {url}"), Resp("", 503)):
            recipe, session = use(monkeypatch, recipe_cls(), {**case.pages, url: failure})
            where = f"{url} -> {failure!r}"
            try:
                info = recipe.fetch_download_info(case.flavor)
            except ScrapeError:
                info = None
            assert url in session.asked, f"{where}: never asked for, so failing it tests nothing"
            # A recipe that moved on to a page the fixture lacks may have
            # refused for that reason alone; map it so the fallback is tested.
            assert not session.missing, f"{where}: fixture missing {session.missing}"
            assert info is None, f"{where}: reported {info.version} instead of raising ScrapeError"
