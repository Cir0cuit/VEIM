"""The contract between VEIM and its definitions.

The recipes that find each distribution's current release live in a separate
repository (Cir0cuit/VEIM-definitions) and are updated without a VEIM release;
see src/core/definitions.py. What they hand back, and what they raise, is
defined here, because the app reads it: these names are API version
definitions.API, and changing one is a change to that version.
"""
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List


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


@dataclass
class FlavorInfo:
    id: str
    name: str



@dataclass(frozen=True)
class IsoIdentity:
    """What a filename says an image is: the definitions' iso_identity rules
    produce these, and the inventory matches them against recipes."""
    key: str            # recipe key
    flavor_id: str
    version: str        # in the form the recipe's DownloadInfo reports it


class DistroRecipe(ABC):
    """
    Abstract base recipe for Linux distributions and bootable utilities.

    A recipe declares its key, name, description and FLAVORS; the registry
    gives it its category. Recipes themselves live in the definitions
    (veim_definitions.common adds the page-reading helpers on top of this).
    """
    key: str
    name: str
    description: str
    FLAVORS: List[FlavorInfo] = []
    category = ""

    def get_flavors(self) -> List[FlavorInfo]:
        """Return list of supported flavors/variants for this distro."""
        return list(self.FLAVORS)

    @abstractmethod
    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        """Fetch latest version and download URL for the given flavor."""
        pass

    def __repr__(self):
        return f"<DistroRecipe {self.name} [{self.key}]>"
