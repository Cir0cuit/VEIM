import re
from src.core.recipe_base import (
    DistroRecipe, FlavorInfo, DownloadInfo, ScrapeError, hrefs, published_sha256, version_key)
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
            r.raise_for_status()
            # Release folders only: "26.1.0-rc4" and "26.1.0-pre" sit beside them.
            versions = [href.strip("/").split("/")[-1] for href in hrefs(r.text)
                        if f"/projects/manjarolinux/files/{sf_key}/" in href and "stats" not in href]
            versions = [v for v in versions if re.fullmatch(r'\d+(\.\d+)*', v)]
            if not versions:
                raise ScrapeError(self.name, f"no {sf_key} release folder listed on the Manjaro mirror")
            latest_ver = max(versions, key=version_key)

            sub_url = f"{url}{latest_ver}/"
            r_sub = session.get(sub_url, headers=sf_headers, timeout=10)
            r_sub.raise_for_status()
        except ScrapeError:
            raise
        except Exception as e:
            log.warning(f"[Manjaro] Scraping error: {e}")
            raise ScrapeError(self.name, f"could not read the Manjaro mirror ({e})")

        # The folder is the edition's, not everything in it is: kde/26.1.2/
        # also holds GNOME's minimal image. Only this edition's full image,
        # named for this release, will do.
        full_image = re.compile(rf"manjaro-{sf_key}-{re.escape(latest_ver)}-\d+-linux\d+\.iso")
        for href in hrefs(r_sub.text):
            # Links look like .../26.1.2/manjaro-kde-26.1.2-260910-linux71.iso/download
            fname = href.removesuffix("/download").rsplit("/", 1)[-1]
            if full_image.fullmatch(fname):
                dl_link = f"https://downloads.sourceforge.net/project/manjarolinux/{sf_key}/{latest_ver}/{fname}"
                return DownloadInfo(version=latest_ver, url=dl_link, filename=fname,
                                    sha256=published_sha256(session, dl_link + ".sha256", fname, self.name,
                                                            headers=sf_headers))

        raise ScrapeError(self.name, f"no {sf_key} {latest_ver} image in its folder on the Manjaro mirror")


# How EndeavourOS has dated its images: "Titan-Nova-2026.08.15" now,
# "Cassini_Nova-03-2023" (respun as "_R1", "_R2") and "Apollo_22_1" before.
_EOS_DATES = (
    (r'(\d{4})[._-](\d{2})[._-](\d{2})', lambda m: (int(m[1]), int(m[2]), int(m[3]))),
    (r'-(\d{2})-(\d{4})(?:_R\d+)?\.iso$', lambda m: (int(m[2]), int(m[1]), 0)),
    (r'[-_](\d{2})_(\d{1,2})\.iso$', lambda m: (2000 + int(m[1]), int(m[2]), 0)),
)


def _eos_age(name: str) -> tuple:
    """(year, month, day, respin) of an EndeavourOS image, from its name."""
    respin = re.search(r'_R(\d+)\.iso$', name)
    for pattern, date in _EOS_DATES:
        m = re.search(pattern, name)
        if m:
            return date(m) + (int(respin[1]) if respin else 0,)
    # Ranked as oldest, a release under a new naming scheme would leave the
    # previous one reported as current.
    raise ScrapeError(EndeavourRecipe.name, f"cannot tell how new {name} is")


class EndeavourRecipe(DistroRecipe):
    key = "endeavour"
    name = "EndeavourOS"
    description = "Terminal-centric Arch derivative with a vibrant, welcoming community."

    FLAVORS = [
        FlavorInfo("standard", "Standard")
    ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        session = self.get_session()
        mirror = "https://mirror.alpix.eu/endeavouros/iso/"

        try:
            r = session.get(mirror, timeout=10)
            r.raise_for_status()
        except Exception as e:
            log.warning(f"[Endeavour] Mirror scrape error: {e}")
            raise ScrapeError(self.name, f"could not read the EndeavourOS mirror ({e})")

        isos = [href for href in hrefs(r.text) if href.endswith(".iso") and "endeavouros" in href.lower()]
        if not isos:
            raise ScrapeError(self.name, "no ISO listed on the EndeavourOS mirror")
        best = max(isos, key=_eos_age)
        m = re.search(r'-(\d{4}\.\d{2}\.\d{2})(?:_R(\d+))?\.iso$', best)
        if not m:
            raise ScrapeError(self.name, f"the newest image, {best}, carries no YYYY.MM.DD version")
        # A respin keeps the release's date; without its number it would
        # never be told apart from the image it replaces.
        ver = f"{m[1]} R{m[2]}" if m[2] else m[1]
        return DownloadInfo(version=ver, url=mirror + best, filename=best)


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
        except Exception as e:
            log.warning(f"[Omarchy] Scrape error: {e}")
            raise ScrapeError(self.name, f"could not read omarchy.org ({e})")

        found = re.findall(r'(https://[^\s"\'<>]*/omarchy-(\d+(?:\.\d+)*)\.iso)', page.text)
        if not found:
            raise ScrapeError(self.name, "no current release listed on omarchy.org")
        url, ver = max(found, key=lambda pair: version_key(pair[1]))
        return DownloadInfo(version=ver, url=url, filename=url.split("/")[-1],
                            sha256=published_sha256(session, url + ".sha256", url.split("/")[-1], self.name))
