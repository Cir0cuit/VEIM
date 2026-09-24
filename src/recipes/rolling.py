import re
from src.core.recipe_base import DistroRecipe, FlavorInfo, DownloadInfo, ScrapeError, hrefs
from src.core.logger import log

class ManjaroRecipe(DistroRecipe):
    key = "manjaro"
    name = "Manjaro"
    description = "User-friendly, accessible desktop Linux based on Arch."

    FLAVORS = [
        FlavorInfo("plasma", "KDE Plasma"),
        FlavorInfo("gnome", "GNOME"),
        FlavorInfo("xfce", "Xfce")
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
                versions = []
                for href in hrefs(r.text):
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
                        for href in hrefs(r_sub.text):
                            # Links look like .../26.1.2/manjaro-kde-26.1.2-260910-linux71.iso/download
                            fname = href.removesuffix("/download").rsplit("/", 1)[-1]
                            if fname.endswith(".iso") and "minimal" not in fname.lower():
                                dl_link = f"https://downloads.sourceforge.net/project/manjarolinux/{sf_key}/{latest_ver}/{fname}"
                                return DownloadInfo(version=latest_ver, url=dl_link, filename=fname)

        except Exception as e:
            log.warning(f"[Manjaro] Scraping error: {e}")

        raise ScrapeError(self.name, f"no current {sf_key} ISO listed on the Manjaro mirror")

class EndeavourRecipe(DistroRecipe):
    key = "endeavour"
    name = "EndeavourOS"
    description = "Terminal-centric Arch derivative with a vibrant, welcoming community."

    FLAVORS = [
        FlavorInfo("standard", "Galileo Neo")
    ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        session = self.get_session()
        mirror = "https://mirror.alpix.eu/endeavouros/iso/"

        try:
            r = session.get(mirror, timeout=10)
            if r.status_code == 200:
                isos = []
                for href in hrefs(r.text):
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
    key = "omarchy"
    name = "Omarchy"
    description = "Opinionated Arch and Hyprland setup, shipped as a ready-to-boot image."

    FLAVORS = [
        FlavorInfo("standard", "Standard"),
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
