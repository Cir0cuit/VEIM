import re
from typing import List
from src.core.recipe_base import DistroRecipe, FlavorInfo, DownloadInfo, ScrapeError, hrefs, version_key
from src.core.logger import log


def _links(session, url: str) -> List[str]:
    """The hrefs on a directory listing, or [] if it could not be read."""
    r = session.get(url, timeout=10)
    if r.status_code != 200:
        return []
    return hrefs(r.text)


class PuppyRecipe(DistroRecipe):
    key = "puppy"
    name = "Puppy Linux"
    description = "Extraordinarily fast, portable Linux designed to run entirely in RAM."

    FLAVORS = [
        FlavorInfo("bookworm", "BookwormPup64"),
        FlavorInfo("fossa", "FossaPup64"),
        FlavorInfo("trixie", "TrixiePup64")
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
        return max(releases, key=version_key) + "/" if releases else ""

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
                        found.append((version_key(m.group(1)), m.group(1), href))
                if found:
                    _, ver, best = max(found)
                    return DownloadInfo(version=ver, url=full_dir + best, filename=best)
            except Exception as e:
                log.warning(f"[Puppy] Error checking mirror {base}: {e}")

        raise ScrapeError(self.name, f"no current {target} build listed on the Puppy mirrors")

class TinyCoreRecipe(DistroRecipe):
    key = "tinycore"
    name = "Tiny Core Linux"
    description = "Ultra-minimalist modular desktop system starting at just 16 MB."

    SITE = "http://tinycorelinux.net/"

    FLAVORS = [
        FlavorInfo("coreplus", "CorePlus (x86)"),
        FlavorInfo("tinycore", "TinyCore (x86)"),
        FlavorInfo("corepure64", "CorePure64 (x86_64)"),
        FlavorInfo("tinycorepure64", "TinyCorePure64 (x86_64)"),
        FlavorInfo("core", "Core (x86)"),
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
                ver = max(versions, key=version_key)
                return DownloadInfo(version=ver, url=base_url + versions[ver], filename=versions[ver])
        except ScrapeError:
            raise
        except Exception as e:
            log.warning(f"[TinyCore] Scrape error: {e}")

        raise ScrapeError(self.name, f"no current {image} image listed in the Tiny Core archive")

class AlpineRecipe(DistroRecipe):
    key = "alpine"
    name = "Alpine Linux"
    description = "Security-oriented, ultra-lightweight Linux distribution based on musl and BusyBox."

    FLAVORS = [
        FlavorInfo("standard", "Standard x86_64"),
        FlavorInfo("extended", "Extended x86_64"),
        FlavorInfo("virt", "Virtual x86_64"),
        FlavorInfo("xen", "Xen x86_64"),
    ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        session = self.get_session()
        if flavor_id.lower() not in ("standard", "extended", "virt", "xen"):
            raise ScrapeError(self.name, f"unknown Alpine image {flavor_id!r}")
        target = f"alpine-{flavor_id.lower()}"

        try:
            r = session.get("https://alpinelinux.org/downloads/", timeout=10)
            if r.status_code == 200:
                for href in hrefs(r.text):
                    if target in href and href.endswith("x86_64.iso"):
                        m = re.search(rf'{target}-([\d\.]+)-x86_64\.iso', href)
                        ver = m.group(1) if m else "Latest"
                        return DownloadInfo(version=ver, url=href, filename=href.split("/")[-1])
        except Exception as e:
            log.warning(f"[Alpine] Error scraping alpine downloads: {e}")

        raise ScrapeError(self.name, f"no current {target} image listed on dl-cdn.alpinelinux.org")
