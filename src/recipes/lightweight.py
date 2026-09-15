import re
from typing import List
from bs4 import BeautifulSoup
from src.core.recipe_base import DistroRecipe, FlavorInfo, DownloadInfo, ScrapeError
from src.core.logger import log

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

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        session = self.get_session()
        target = flavor_id.lower()

        mirrors = [
            "https://distro.ibiblio.org/puppylinux/",
            "https://ftp.nluug.nl/os/Linux/distr/puppylinux/"
        ]

        if target == "bookworm":
            sub_path = "puppy-bookwormpup/BookwormPup64/10.0.12/"
        elif target == "fossa":
            sub_path = "puppy-fossa/"
        else:
            sub_path = "puppy-trixie/TrixiePup64/11.4/wayland/"

        for base in mirrors:
            try:
                full_dir = base + sub_path
                r = session.get(full_dir, timeout=10)
                if r.status_code == 200:
                    soup = BeautifulSoup(r.text, "html.parser")
                    isos = []
                    for a in soup.find_all("a", href=True):
                        href = a["href"]
                        if href.endswith(".iso") and "devx" not in href.lower():
                            isos.append(href)
                    if isos:
                        isos.sort(reverse=True)
                        best = isos[0]
                        m = re.search(r'[\-_]([\d\.]+)(?:[\-_]|\.iso)', best)
                        ver = m.group(1) if m else "Latest"
                        return DownloadInfo(version=ver, url=full_dir + best, filename=best)
            except Exception as e:
                log.warning(f"[Puppy] Error checking mirror {base}: {e}")

        raise ScrapeError(self.name, f"no current {target} build listed on the Puppy mirrors")

class TinyCoreRecipe(DistroRecipe):
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
            FlavorInfo("corepure64", "CorePure64 (x86_64)", "Pure 64-bit Core Linux system.")
        ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        session = self.get_session()
        target = flavor_id.lower()

        if target == "corepure64":
            base_url = "http://tinycorelinux.net/15.x/x86_64/release/"
            target_match = "CorePure64"
        elif target == "tinycore":
            base_url = "http://tinycorelinux.net/15.x/x86/release/"
            target_match = "TinyCore"
        else:
            base_url = "http://tinycorelinux.net/15.x/x86/release/"
            target_match = "CorePlus"

        try:
            r = session.get(base_url, timeout=10)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    if href.endswith(".iso") and target_match.lower() in href.lower():
                        m = re.search(rf'{target_match}-([\d\.]+)\.iso', href, re.IGNORECASE)
                        ver = m.group(1) if m else "15.0"
                        full_url = base_url + href if not href.startswith("http") else href
                        return DownloadInfo(version=ver, url=full_url, filename=href)
        except Exception as e:
            log.warning(f"[TinyCore] Error scraping {base_url}: {e}")

        raise ScrapeError(self.name, f"no current {target_match} image listed in the Tiny Core archive")

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
            FlavorInfo("extended", "Extended x86_64", "Includes additional packages for offline installs.")
        ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        session = self.get_session()
        target = "alpine-extended" if flavor_id.lower() == "extended" else "alpine-standard"

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
