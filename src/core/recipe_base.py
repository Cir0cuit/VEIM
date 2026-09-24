from abc import ABC, abstractmethod
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import List
import re
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.core.logger import log

# A server error is a hiccup, not an answer. Two more tries, a second or two
# apart, cover the kind cdimage.debian.org has; then it is refused.
SERVER_ERROR_STATUSES = (500, 502, 503, 504)
SERVER_ERROR_RETRIES = 2
SERVER_ERROR_BACKOFF = 1.0

BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:130.0) Gecko/20100101 Firefox/130.0"

# The path of each file a SourceForge RSS feed lists, newest first.
SOURCEFORGE_PATHS = r'<title><!\[CDATA\[(/[^\]]+)\]\]></title>'


def _refuse_server_errors(response, *args, **kwargs):
    """Session hook: a 5xx that survived the retries is raised, never parsed.

    The body of an error page holds no download links, and a recipe that
    searched it reported "no current release" for a release that was there.
    """
    if response.status_code >= 500:
        raise requests.HTTPError(
            f"{response.url.split('//', 1)[-1].split('/', 1)[0]} answered "
            f"HTTP {response.status_code}", response=response)
    return response


class ScrapeError(Exception):
    """A recipe could not determine a current, trustworthy download.

    Raised instead of silently returning a stale hardcoded URL. Serving an
    outdated ISO that looks current is worse than reporting a failure: the user
    burns a USB stick with an old release and has no way to tell.
    """

    def __init__(self, distro: str, reason: str):
        self.distro = distro
        self.reason = reason
        super().__init__(f"{distro}: {reason}")


@dataclass
class DownloadInfo:
    version: str
    url: str
    sha256: str = ""
    filename: str = ""
    # "zip" when upstream publishes the ISO only inside an archive, which
    # the downloader unpacks - Ventoy cannot boot a .zip.
    archive: str = ""

    def __post_init__(self):
        self.version = clean_version(self.version)

def clean_version(version: str) -> str:
    """Normalise a scraped version string for display.

    Scrapers pull versions out of filenames and release tags, which arrive with
    stray prefixes and separators: "v2025.11_31" keeps its tag "v" and then gets
    another one at render time ("vv2025..."), and truncated captures leave a
    trailing "-" ("8.1-", "23.0-SP1-").
    """
    if not version:
        return "Unknown"
    v = str(version).strip()
    # Strip a leading release-tag "v" ("v2.6.2" -> "2.6.2") but keep words that
    # merely start with v, like "virt" or "Vera".
    v = re.sub(r'^v(?=\d)', '', v)
    # Drop separator debris left by partial regex captures.
    v = v.strip(" -_.")
    return v or "Unknown"


def version_key(version: str) -> tuple:
    """Sort key made of the numbers in a version, which ranks 10 above 9 - a
    string sort gets that backwards."""
    return tuple(int(n) for n in re.findall(r'\d+', str(version)))


def is_older(candidate: str, installed: str) -> bool:
    """True when `candidate` is recognisably an earlier release than `installed`.

    A check compares what a recipe reports with what is on the drive, and used
    to call any difference an update. A recipe that falls behind upstream then
    offers a downgrade as if it were news. Versions are compared by the numbers
    in them; when that settles nothing ("Tumbleweed", "Stable"), the answer is
    False and the caller is left with plain inequality.
    """
    ours, theirs = version_key(installed), version_key(candidate)
    return bool(ours) and bool(theirs) and theirs < ours


class _Page(HTMLParser):
    """The href of every link on a page, and the text in each table row's cells."""

    def __init__(self):
        super().__init__()
        self.hrefs, self.rows, self._in_cell = [], [], False

    def handle_starttag(self, tag, attrs):
        href = dict(attrs).get("href")
        if tag == "a" and href is not None:
            self.hrefs.append(href)
        elif tag == "tr":
            self.rows.append([])
            self._in_cell = False
        elif tag == "td" and self.rows:
            self.rows[-1].append("")
            self._in_cell = True

    def handle_endtag(self, tag):
        if tag in ("td", "tr"):
            self._in_cell = False

    def handle_data(self, data):
        if self._in_cell:
            self.rows[-1][-1] += data


def _parse(html: str) -> _Page:
    page = _Page()
    page.feed(html)
    page.close()
    return page


def hrefs(html: str) -> List[str]:
    """Every link's href, in page order, with entities decoded."""
    return _parse(html).hrefs


def table_rows(html: str) -> List[List[str]]:
    """The stripped text of each table row's cells."""
    return [[cell.strip() for cell in row] for row in _parse(html).rows]


def sourceforge_rss(session, project: str, query: str) -> str:
    """A SourceForge project's RSS feed of its newest files, newest first."""
    r = session.get(f"https://sourceforge.net/projects/{project}/rss?{query}",
                    timeout=25, headers={"User-Agent": "curl/8.4.0"})
    r.raise_for_status()
    return r.text


@dataclass
class FlavorInfo:
    id: str
    name: str

class DistroRecipe(ABC):
    """
    Abstract base recipe for Linux distributions and bootable utilities.

    A recipe declares its key, name, description and FLAVORS; the registry
    gives it its category.
    """
    key: str
    name: str
    description: str
    FLAVORS: List[FlavorInfo] = []
    category = ""

    def get_session(self) -> requests.Session:
        """A session for reading release pages.

        A server error is retried, then refused: cdimage.debian.org answers
        500 for a request or two at a time, and a recipe that parsed the
        error page as a listing reported "no current release" for a release
        that was there. A 4xx still comes back as a response - a 404 is an
        answer several recipes read ("that release has no images yet").
        """
        session = requests.Session()
        session.headers.update({
            "User-Agent": BROWSER_UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.7",
            "DNT": "1",
            "Upgrade-Insecure-Requests": "1"
        })
        adapter = HTTPAdapter(max_retries=Retry(
            total=SERVER_ERROR_RETRIES, status_forcelist=SERVER_ERROR_STATUSES,
            allowed_methods=("GET", "HEAD"), backoff_factor=SERVER_ERROR_BACKOFF,
            raise_on_status=False))
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        session.hooks["response"].append(_refuse_server_errors)
        return session

    def github_latest(self, repo: str):
        """(tag, assets) of a GitHub project's latest release."""
        try:
            r = self.get_session().get(f"https://api.github.com/repos/{repo}/releases/latest", timeout=15)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            log.warning(f"[{self.name}] GitHub API error: {e}")
            raise ScrapeError(self.name, f"could not read the {self.name} release feed ({e})")
        return str(data.get("tag_name", "")), data.get("assets", [])

    def get_flavors(self) -> List[FlavorInfo]:
        """Return list of supported flavors/variants for this distro."""
        return list(self.FLAVORS)

    @abstractmethod
    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        """Fetch latest version and download URL for the given flavor."""
        pass

    def __repr__(self):
        return f"<DistroRecipe {self.name} [{self.key}]>"
