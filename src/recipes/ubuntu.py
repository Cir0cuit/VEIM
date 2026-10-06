import re
from src.core.recipe_base import (
    DistroRecipe, FlavorInfo, DownloadInfo, ScrapeError, hrefs, published_sha256, version_key)
from src.core.logger import log

PRERELEASE = re.compile(r"[-_.](?:alpha|beta|rc|snapshot|daily)", re.IGNORECASE)
META_RELEASE = "https://changelogs.ubuntu.com/meta-release"


def _end_of_life(text):
    """The X.Y of each series meta-release marks "Supported: 0": past end of life.

    A flavour keeps the directory of a series it built after Canonical stops
    supporting it (Ubuntu MATE's newest is 25.10, past end of life), so the
    newest directory is not the current release by itself. A series missing
    from the file is not passed over: one is added on its release day, and
    until then it is the newest there is.
    """
    eol, stanzas = set(), 0
    for stanza in re.split(r"\n\s*\n", text):
        version = re.search(r"(?m)^Version: (\d+\.\d+)", stanza)
        supported = re.search(r"(?m)^Supported: ([01])\s*$", stanza)
        if version and supported:
            stanzas += 1
            if supported.group(1) == "0":
                eol.add(version.group(1))
    return eol if stanzas else None


class UbuntuRecipe(DistroRecipe):
    key = "ubuntu"
    name = "Ubuntu"
    description = "The world's most widely used desktop Linux distribution."

    FLAVORS = [
        FlavorInfo("desktop", "Ubuntu Desktop"),
        FlavorInfo("server", "Ubuntu Server"),
        FlavorInfo("kubuntu", "Kubuntu"),
        FlavorInfo("xubuntu", "Xubuntu"),
        FlavorInfo("lubuntu", "Lubuntu"),
        FlavorInfo("mate", "Ubuntu MATE"),
        FlavorInfo("budgie", "Ubuntu Budgie"),
        FlavorInfo("cinnamon", "Ubuntu Cinnamon"),
        FlavorInfo("unity", "Ubuntu Unity"),
        FlavorInfo("studio", "Ubuntu Studio"),
        FlavorInfo("edubuntu", "Edubuntu"),
        FlavorInfo("kylin", "Ubuntu Kylin"),
    ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        session = self.get_session()
        target = flavor_id.lower()

        if target in ("desktop", "server"):
            base_url = "https://releases.ubuntu.com/"
        else:
            slug_map = {
                "kubuntu": "kubuntu",
                "xubuntu": "xubuntu",
                "lubuntu": "lubuntu",
                "mate": "ubuntu-mate",
                "budgie": "ubuntu-budgie",
                "cinnamon": "ubuntucinnamon",
                "unity": "ubuntu-unity",
                "studio": "ubuntustudio",
                "edubuntu": "edubuntu",
                "kylin": "ubuntukylin",
            }
            slug = slug_map.get(target, "ubuntu")
            base_url = f"https://cdimage.ubuntu.com/{slug}/releases/"

        prefix = "ubuntu" if target in ("desktop", "server") else slug
        kind = "live-server" if target == "server" else "desktop"
        # The exact name, so a series directory that carries the .0 image beside
        # its point release (26.04.1/ holds both) yields the newer of the two.
        image = re.compile(rf"{re.escape(prefix)}-(\d+(?:\.\d+)*)-{kind}-amd64\.iso")

        try:
            meta = session.get(META_RELEASE, timeout=10)
            meta.raise_for_status()
        except Exception as e:
            raise ScrapeError(self.name, f"could not read {META_RELEASE} ({e})")
        eol = _end_of_life(meta.text)
        if eol is None:
            # Without it a series past end of life would be served as current.
            raise ScrapeError(self.name, f"{META_RELEASE} lists no series with its support status")

        try:
            r = session.get(base_url, timeout=10)
            r.raise_for_status()
        except Exception as e:
            log.warning(f"[Ubuntu] Error scraping {base_url}: {e}")
            raise ScrapeError(self.name, f"could not read the {target} release index ({e})")

        # Four-part directories are respins: 24.04.5.1/.
        # A series past end of life is passed over by its X.Y, respins too.
        versions = [v for v in (h.strip("/") for h in hrefs(r.text) if re.fullmatch(r"\d+(?:\.\d+)+/?", h))
                    if ".".join(v.split(".")[:2]) not in eol]
        versions.sort(key=version_key, reverse=True)

        for ver in versions[:8]:
            for p in (f"{base_url}{ver}/", f"{base_url}{ver}/release/"):
                try:
                    r2 = session.get(p, timeout=6)
                except Exception as e:
                    # Not an answer. Moving on to the next-older release
                    # here would serve it as current because of one timeout.
                    raise ScrapeError(self.name, f"could not read {p} ({e})")
                # releases.ubuntu.com has no release/ below a version, and a
                # flavour may skip a series; anything else is a refusal, and
                # the next-older release is not the answer to it.
                if r2.status_code == 404:
                    continue
                if r2.status_code != 200:
                    raise ScrapeError(self.name, f"{p} answered HTTP {r2.status_code}")

                isos = [h for h in hrefs(r2.text) if h.endswith(".iso")]
                found = [(version_key(m.group(1)), m.group(1), h)
                         for h in isos for m in [image.fullmatch(h)] if m]
                if found:
                    _, version, filename = max(found)
                    return DownloadInfo(version=version, url=p + filename, filename=filename,
                                        sha256=published_sha256(session, p + "SHA256SUMS", filename, self.name))
                # A series that so far has only betas and snapshots is not out
                # yet. One with a final amd64 image under a name this does not
                # know has been released, and the previous one is not current.
                finals = [h for h in isos if "amd64" in h.lower() and not PRERELEASE.search(h)]
                if finals:
                    raise ScrapeError(self.name, f"{p} holds {finals[0]}, not an image named "
                                                 f"{prefix}-<version>-{kind}-amd64.iso")

        raise ScrapeError(self.name, f"no current amd64 {target} ISO found under {base_url}")
