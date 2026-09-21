import re
from typing import List
from bs4 import BeautifulSoup
from src.core.recipe_base import DistroRecipe, FlavorInfo, DownloadInfo, ScrapeError
from src.core.logger import log

def _numeric(version: str) -> tuple:
    """Sort key for dotted versions. As strings, "10.0.9" outranks "10.0.12"."""
    return tuple(int(part) for part in version.split("."))


def _links(session, url: str) -> List[str]:
    """The hrefs on a directory listing, or [] if it could not be read."""
    r = session.get(url, timeout=10)
    if r.status_code != 200:
        return []
    return [a["href"] for a in BeautifulSoup(r.text, "html.parser").find_all("a", href=True)]


class PuppyRecipe(DistroRecipe):
    def __init__(self):
        super().__init__(
            key="puppy",
            name="Puppy Linux",
            category="Lightweight",
            description="Extraordinarily fast, portable Linux designed to run entirely in RAM."
        )

    def get_flavors(self) -> List[FlavorInfo]:
        return [
            FlavorInfo("bookworm", "BookwormPup64", "Built using Debian 12 Bookworm binary packages."),
            FlavorInfo("fossa", "FossaPup64", "Built using Ubuntu 20.04 Focal Fossa binary packages."),
            FlavorInfo("trixie", "TrixiePup64", "Modern release built using Debian 13 Trixie.")
        ]

    # flavor -> (folder holding one subfolder per release, path inside a release).
    # The release folder itself is looked up: naming it here pinned these two
    # to the version that was current the day this was written.
    _RELEASE_DIRS = {
        "bookworm": ("puppy-bookwormpup/BookwormPup64/", ""),
        "trixie": ("puppy-trixie/TrixiePup64/", "wayland/"),
    }

    def _newest_release_dir(self, session, parent_url: str) -> str:
        releases = [h.rstrip("/") for h in _links(session, parent_url)
                    if re.fullmatch(r'\d+(?:\.\d+)+/', h)]
        return max(releases, key=_numeric) + "/" if releases else ""

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        session = self.get_session()
        target = flavor_id.lower()

        mirrors = [
            "https://distro.ibiblio.org/puppylinux/",
            "https://ftp.nluug.nl/os/Linux/distr/puppylinux/"
        ]

        for base in mirrors:
            try:
                if target in self._RELEASE_DIRS:
                    parent, inner = self._RELEASE_DIRS[target]
                    release = self._newest_release_dir(session, base + parent)
                    if not release:
                        continue
                    full_dir = base + parent + release + inner
                else:
                    full_dir = base + "puppy-fossa/"

                found = []
                for href in _links(session, full_dir):
                    m = re.search(r'[\-_](\d+(?:\.\d+)+)\.iso$', href)
                    if m and "devx" not in href.lower():
                        found.append((_numeric(m.group(1)), m.group(1), href))
                if found:
                    _, ver, best = max(found)
                    return DownloadInfo(version=ver, url=full_dir + best, filename=best)
            except Exception as e:
                log.warning(f"[Puppy] Error checking mirror {base}: {e}")

        raise ScrapeError(self.name, f"no current {target} build listed on the Puppy mirrors")

class TinyCoreRecipe(DistroRecipe):
    SITE = "http://tinycorelinux.net/"

    def __init__(self):
        super().__init__(
            key="tinycore",
            name="Tiny Core Linux",
            category="Lightweight",
            description="Ultra-minimalist modular desktop system starting at just 16 MB."
        )

    def get_flavors(self) -> List[FlavorInfo]:
        return [
            FlavorInfo("coreplus", "CorePlus (x86)", "Complete installation image with wireless tools and window managers."),
            FlavorInfo("tinycore", "TinyCore (x86)", "Minimalist GUI desktop experience (16 MB)."),
            FlavorInfo("corepure64", "CorePure64 (x86_64)", "Pure 64-bit Core Linux system."),
            FlavorInfo("tinycorepure64", "TinyCorePure64 (x86_64)", "64-bit Core with the minimalist GUI desktop."),
            FlavorInfo("core", "Core (x86)", "Command line only: the 17 MB base everything else builds on."),
        ]

    # flavor -> (architecture folder, image name)
    _IMAGES = {
        "coreplus": ("x86", "CorePlus"),
        "tinycore": ("x86", "TinyCore"),
        "corepure64": ("x86_64", "CorePure64"),
        "tinycorepure64": ("x86_64", "TinyCorePure64"),
        "core": ("x86", "Core"),
    }

    def _current_series(self, session) -> int:
        """The release series the project's own download page points at.

        This used to be written into the URLs as "15.x". Tiny Core went on to
        16 and 17, and the recipe kept reporting 15.0 as the latest - so a
        drive holding 16.2 was offered an "update" that was a downgrade.
        """
        r = session.get(self.SITE + "downloads.html", timeout=10)
        r.raise_for_status()
        series = [int(n) for n in re.findall(r'(\d+)\.x/x86(?:_64)?/release', r.text)]
        if not series:
            raise ScrapeError(self.name, "the Tiny Core download page names no release series")
        return max(series)

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        if flavor_id.lower() not in self._IMAGES:
            raise ScrapeError(self.name, f"unknown Tiny Core image {flavor_id!r}")
        arch, image = self._IMAGES[flavor_id.lower()]
        session = self.get_session()

        try:
            base_url = f"{self.SITE}{self._current_series(session)}.x/{arch}/release/"
            versions = {}
            for href in _links(session, base_url):
                # The whole name: "CorePure64-" is also the tail of "TinyCorePure64-".
                m = re.fullmatch(rf'{image}-(\d+(?:\.\d+)+)\.iso', href)
                if m:
                    versions[m.group(1)] = href
            if versions:
                ver = max(versions, key=_numeric)
                return DownloadInfo(version=ver, url=base_url + versions[ver], filename=versions[ver])
        except ScrapeError:
            raise
        except Exception as e:
            log.warning(f"[TinyCore] Scrape error: {e}")

        raise ScrapeError(self.name, f"no current {image} image listed in the Tiny Core archive")

class AlpineRecipe(DistroRecipe):
    def __init__(self):
        super().__init__(
            key="alpine",
            name="Alpine Linux",
            category="Lightweight",
            description="Security-oriented, ultra-lightweight Linux distribution based on musl and BusyBox."
        )

    def get_flavors(self) -> List[FlavorInfo]:
        return [
            FlavorInfo("standard", "Standard x86_64", "General purpose live and installation media."),
            FlavorInfo("extended", "Extended x86_64", "Includes additional packages for offline installs."),
            FlavorInfo("virt", "Virtual x86_64", "Slimmed-down kernel, for virtual machines."),
            FlavorInfo("xen", "Xen x86_64", "With Xen hypervisor support, for a dom0."),
        ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        session = self.get_session()
        if flavor_id.lower() not in ("standard", "extended", "virt", "xen"):
            raise ScrapeError(self.name, f"unknown Alpine image {flavor_id!r}")
        target = f"alpine-{flavor_id.lower()}"

        try:
            r = session.get("https://alpinelinux.org/downloads/", timeout=10)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    if target in href and href.endswith("x86_64.iso"):
                        m = re.search(rf'{target}-([\d\.]+)-x86_64\.iso', href)
                        ver = m.group(1) if m else "Latest"
                        return DownloadInfo(version=ver, url=href, filename=href.split("/")[-1])
        except Exception as e:
            log.warning(f"[Alpine] Error scraping alpine downloads: {e}")

        raise ScrapeError(self.name, f"no current {target} image listed on dl-cdn.alpinelinux.org")
