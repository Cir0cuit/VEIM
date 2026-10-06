import re
from typing import List
from src.core.recipe_base import (
    DistroRecipe, FlavorInfo, DownloadInfo, ScrapeError, SOURCEFORGE_PATHS, hrefs,
    published_sha256, sourceforge_rss, version_key)
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

    BASE = "https://distro.ibiblio.org/puppylinux/"

    # flavor -> (folder, the image's whole name). BookwormPup64's folder holds
    # one subfolder per release. The release folder itself is looked up:
    # naming it here pinned BookwormPup64 to the version that was current the
    # day this was written. Only ibiblio is read - a second mirror was tried
    # when it failed, and a mirror that has not synced yet reports the
    # previous release as current.
    # The last part is what the image's checksum file adds to its name.
    _RELEASE_DIRS = {
        "bookworm": ("puppy-bookwormpup/BookwormPup64/", r"BookwormPup64_(\d+(?:\.\d+)+)\.iso", "-checksum.txt"),
        "fossa": ("puppy-fossa/", r"fossapup64-(\d+(?:\.\d+)+)\.iso", ".sha256.txt"),
    }

    def _trixie(self, session) -> DownloadInfo:
        """TrixiePup64's official builds, which are on SourceForge only.

        The numbered folders on ibiblio (11.4) are a maintainer's test builds,
        its README says; the "2606 version" folders beside them hold nothing
        but a redirect here. Reading ibiblio kept this at April's 11.4 while
        three official builds went out.
        """
        feed = sourceforge_rss(session, "pb-gh-releases", "path=/TrixiePup64Wayland_release")
        found = {}
        for path in re.findall(SOURCEFORGE_PATHS, feed):
            # Series and build date: 2606-261003.
            m = re.fullmatch(r'/TrixiePup64Wayland_release/(TrixiePup64-Wayland-(\d{4}-\d{6})\.iso)', path)
            if m:
                found[m.group(2)] = m.group(1)
        if not found:
            raise ScrapeError(self.name, "no TrixiePup64 Wayland image listed on SourceForge")
        ver = max(found, key=version_key)
        return DownloadInfo(version=ver, filename=found[ver], url=(
            "https://downloads.sourceforge.net/project/pb-gh-releases/"
            f"TrixiePup64Wayland_release/{found[ver]}"))

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        session = self.get_session()
        target = flavor_id.lower()
        try:
            if target == "trixie":
                return self._trixie(session)
            if target not in self._RELEASE_DIRS:
                raise ScrapeError(self.name, f"unknown Puppy edition {flavor_id!r}")
            parent, image, sums = self._RELEASE_DIRS[target]
            full_dir = self.BASE + parent
            if target == "bookworm":
                releases = [h for h in _links(session, full_dir) if re.fullmatch(r'\d+(?:\.\d+)+/', h)]
                if not releases:
                    raise ScrapeError(self.name, f"no release folders listed in {full_dir}")
                full_dir += max(releases, key=version_key)

            # The edition's own name: devx_ and other images share the folder.
            found = {}
            for href in _links(session, full_dir):
                m = re.fullmatch(image, href)
                if m:
                    found[m.group(1)] = href
            if found:
                ver = max(found, key=version_key)
                url = full_dir + found[ver]
                return DownloadInfo(version=ver, url=url, filename=found[ver],
                                    sha256=published_sha256(session, url + sums, found[ver], self.name))
        except ScrapeError:
            raise
        except Exception as e:
            log.warning(f"[Puppy] Scrape error: {e}")

        raise ScrapeError(self.name, f"no current {target} build listed on the Puppy mirror")

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
            r.raise_for_status()
            # Every release the page links, by number: the first link was
            # taken once, and a release candidate's version did not parse and
            # was reported as the label "Latest".
            found = {}
            for href in hrefs(r.text):
                m = re.fullmatch(rf'.*/({target}-(\d+(?:\.\d+)+)-x86_64\.iso)', href)
                if m:
                    found[m.group(2)] = (href, m.group(1))
            if found:
                ver = max(found, key=version_key)
                url, fname = found[ver]
                return DownloadInfo(version=ver, url=url, filename=fname,
                                    sha256=published_sha256(session, url + ".sha256", fname, self.name))
        except Exception as e:
            log.warning(f"[Alpine] Error scraping alpine downloads: {e}")

        raise ScrapeError(self.name, f"no current {target} image listed on dl-cdn.alpinelinux.org")
