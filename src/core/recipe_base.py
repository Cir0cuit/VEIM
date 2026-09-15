from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List, Dict
import re
import requests
import random
from src.core.logger import log


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
    size_bytes: int = 0
    release_date: str = ""
    notes: str = ""
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


@dataclass
class FlavorInfo:
    id: str
    name: str
    description: str = ""
    arch: str = "x86_64"

class DistroRecipe(ABC):
    """
    Abstract base recipe for Linux distributions and bootable utilities.
    """
    def __init__(self, key: str, name: str, category: str, description: str = ""):
        self.key = key
        self.name = name
        self.category = category  # e.g. "Popular", "Rolling", "Security", "Rescue", "Lightweight"
        self.description = description
        
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:130.0) Gecko/20100101 Firefox/130.0",
            "Mozilla/5.0 (X11; Linux x86_64; rv:130.0) Gecko/20100101 Firefox/130.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.7; rv:130.0) Gecko/20100101 Firefox/130.0",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        ]

    def get_session(self) -> requests.Session:
        session = requests.Session()
        ua = random.choice(self.user_agents)
        session.headers.update({
            "User-Agent": ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.7",
            "DNT": "1",
            "Upgrade-Insecure-Requests": "1"
        })
        return session

    @abstractmethod
    def get_flavors(self) -> List[FlavorInfo]:
        """Return list of supported flavors/variants for this distro."""
        pass

    @abstractmethod
    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        """Fetch latest version and download URL for the given flavor."""
        pass

    def __repr__(self):
        return f"<DistroRecipe {self.name} [{self.key}]>"
