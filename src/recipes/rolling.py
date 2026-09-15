import re
from typing import List
from bs4 import BeautifulSoup
from src.core.recipe_base import DistroRecipe, FlavorInfo, DownloadInfo, ScrapeError
from src.core.logger import log

class ManjaroRecipe(DistroRecipe):
    def __init__(self):
        super().__init__(
            key="manjaro",
            name="Manjaro",
            category="Rolling Release",
            description="User-friendly, accessible desktop Linux based on Arch."
        )

    def get_flavors(self) -> List[FlavorInfo]:
        return [
            FlavorInfo("plasma", "KDE Plasma", "Flagship modern, powerful desktop experience."),
            FlavorInfo("gnome", "GNOME", "Clean, gesture-oriented GNOME desktop."),
            FlavorInfo("xfce", "Xfce", "Lightweight, reliable desktop edition.")
        ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        session = self.get_session()
        target = flavor_id.lower()
        sf_key = "kde" if target == "plasma" else target
        
        url = f"https://sourceforge.net/projects/manjarolinux/files/{sf_key}/"
        sf_headers = {"User-Agent": "curl/8.4.0", "Accept": "*/*"}
        try:
            r = session.get(url, headers=sf_headers, timeout=10)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")
                versions = []
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    if f"/projects/manjarolinux/files/{sf_key}/" in href and "stats" not in href:
                        parts = href.strip("/").split("/")
                        if parts:
                            ver_str = parts[-1]
                            if re.match(r'^\d+(\.\d+)*$', ver_str):
                                versions.append(ver_str)
                
                if versions:
                    versions.sort(key=lambda s: [int(u) for u in s.split(".") if u.isdigit()], reverse=True)
                    latest_ver = versions[0]
                    
                    sub_url = f"{url}{latest_ver}/"
                    r_sub = session.get(sub_url, headers=sf_headers, timeout=10)
                    if r_sub.status_code == 200:
                        soup_sub = BeautifulSoup(r_sub.text, "html.parser")
                        for a2 in soup_sub.find_all("a", href=True):
                            name_span = a2.find("span", class_="name")
                            fname = name_span.text if name_span else a2.text.strip()
                            if fname.endswith(".iso") and "minimal" not in fname.lower():
                                dl_link = f"https://downloads.sourceforge.net/project/manjarolinux/{sf_key}/{latest_ver}/{fname}"
                                return DownloadInfo(version=latest_ver, url=dl_link, filename=fname)

        except Exception as e:
            log.warning(f"[Manjaro] Scraping error: {e}")

        raise ScrapeError(self.name, f"no current {sf_key} ISO listed on the Manjaro mirror")

class EndeavourRecipe(DistroRecipe):
    def __init__(self):
        super().__init__(
            key="endeavour",
            name="EndeavourOS",
            category="Rolling Release",
            description="Terminal-centric Arch derivative with a vibrant, welcoming community."
        )

    def get_flavors(self) -> List[FlavorInfo]:
        return [
            FlavorInfo("standard", "Galileo Neo", "Standard live installer ISO with Calamares.")
        ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        session = self.get_session()
        mirror = "https://mirror.alpix.eu/endeavouros/iso/"

        try:
            r = session.get(mirror, timeout=10)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")
                isos = []
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    if href.endswith(".iso") and "endeavouros" in href.lower():
                        isos.append(href)
                if isos:
                    def _extract_date(name):
                        m = re.search(r'(\d{4})[\._-](\d{2})[\._-](\d{2})', name)
                        if m:
                            return (int(m.group(1)), int(m.group(2)), int(m.group(3)))
                        return (0, 0, 0)
                    isos.sort(key=_extract_date, reverse=True)
                    best = isos[0]
                    m = re.search(r'(\d{4}\.\d{2}\.\d{2})', best)
                    ver = m.group(1) if m else "Latest"
                    return DownloadInfo(version=ver, url=mirror + best, filename=best)
        except Exception as e:
            log.warning(f"[Endeavour] Mirror scrape error: {e}")


        raise ScrapeError(self.name, "no ISO listed on the EndeavourOS mirror")


class OmarchyRecipe(DistroRecipe):
    def __init__(self):
        super().__init__(
            key="omarchy",
            name="Omarchy",
            category="Rolling Release",
            description="Opinionated Arch and Hyprland setup, shipped as a ready-to-boot image.",
        )

    def get_flavors(self) -> List[FlavorInfo]:
        return [
            FlavorInfo("standard", "Standard", "Arch with the Omarchy Hyprland desktop preconfigured."),
        ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        session = self.get_session()
        try:
            page = session.get("https://omarchy.org/", timeout=25)
            page.raise_for_status()
            found = re.findall(r'(https://[^\s"\'<>]*/omarchy-(\d+(?:\.\d+)*)\.iso)', page.text)
            if found:
                url, ver = max(
                    found, key=lambda pair: tuple(int(p) for p in pair[1].split(".")))
                return DownloadInfo(version=ver, url=url, filename=url.split("/")[-1])
        except Exception as e:
            log.warning(f"[Omarchy] Scrape error: {e}")

        raise ScrapeError(self.name, "no current release listed on omarchy.org")
