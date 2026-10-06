"""Server, virtualisation and high-security platforms.

These are installers for machines rather than desktops to try out, but they are
exactly the images people keep on a Ventoy stick for provisioning work.
"""
import re
from typing import List

from src.core.recipe_base import (
    DistroRecipe, FlavorInfo, DownloadInfo, ScrapeError, hrefs, published_sha256, version_key)
from src.core.logger import log


def _hrefs(session, url: str, timeout: int = 20) -> List[str]:
    """Every href on a page. Raises when the page cannot be read."""
    r = session.get(url, timeout=timeout)
    r.raise_for_status()
    return hrefs(r.text)


class RockyLinuxRecipe(DistroRecipe):
    key = "rocky"
    name = "Rocky Linux"
    description = "Community enterprise OS, binary compatible with Red Hat Enterprise Linux."

    ROOT = "https://download.rockylinux.org/pub/rocky/"

    FLAVORS = [
        FlavorInfo("dvd", "DVD"),
        FlavorInfo("minimal", "Minimal"),
        FlavorInfo("boot", "Boot"),
    ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        if flavor_id not in ("dvd", "minimal", "boot"):
            raise ScrapeError(self.name, f"unknown Rocky image {flavor_id!r}")

        session = self.get_session()
        try:
            index = session.get(self.ROOT, timeout=20)
            index.raise_for_status()
            # The tree carries bare majors ("10") next to point releases
            # ("10.2"); the bare major tracks the newest point release, so
            # prefer it. A string sort would also rank "9.8" above "10".
            majors = {int(m) for m in re.findall(r'href="(\d+)/"', index.text)}
            if not majors:
                raise ScrapeError(self.name, "download.rockylinux.org listed no release series")
            # Only the newest major: when its images cannot be listed, an
            # older major's point release is not the current one.
            major = max(majors)
            iso_dir = f"{self.ROOT}{major}/isos/x86_64/"
            listing = session.get(iso_dir, timeout=20)
            listing.raise_for_status()
            # The point release by name ("Rocky-10.2-..."), never the
            # "Rocky-10-latest-..." alias beside it: that name and the bare
            # "10" stay the same through 10.3 and 10.4, so an image
            # downloaded at 10.2 would read as up to date for good. The
            # DVD alone is numbered ("dvd1").
            found = re.findall(
                rf'(Rocky-({major}\.\d+)-x86_64-{flavor_id}\d?\.iso)', listing.text)
            if not found:
                raise ScrapeError(self.name, f"no Rocky Linux {major} {flavor_id} image listed")
            fname, ver = max(found, key=lambda pair: version_key(pair[1]))
            sha256 = published_sha256(session, f"{iso_dir}{fname}.CHECKSUM", fname, self.name)
        except ScrapeError:
            raise
        except Exception as e:
            log.warning(f"[Rocky Linux] Scrape error: {e}")
            raise ScrapeError(self.name, f"could not read download.rockylinux.org ({e})")
        return DownloadInfo(version=ver, url=iso_dir + fname, filename=fname, sha256=sha256)


class ProxmoxRecipe(DistroRecipe):
    key = "proxmox"
    name = "Proxmox"
    description = ("Virtual Environment, Backup Server, Mail Gateway and Datacenter Manager, "
                   "each a bare-metal appliance managed from a browser.")

    # flavor -> the product's name in its image file. "installer" is VE, and
    # keeps the id it had when VE was the only product listed.
    PRODUCTS = {
        "installer": "proxmox-ve",
        "backup-server": "proxmox-backup-server",
        "mail-gateway": "proxmox-mail-gateway",
        "datacenter-manager": "proxmox-datacenter-manager",
    }

    FLAVORS = [
        FlavorInfo("installer", "Virtual Environment"),
        FlavorInfo("backup-server", "Backup Server"),
        FlavorInfo("mail-gateway", "Mail Gateway"),
        FlavorInfo("datacenter-manager", "Datacenter Manager"),
    ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        product = self.PRODUCTS.get(flavor_id)
        if product is None:
            raise ScrapeError(self.name, f"unknown Proxmox product {flavor_id!r}")

        session = self.get_session()
        base = "https://enterprise.proxmox.com/iso/"
        try:
            listing = session.get(base, timeout=20)
            listing.raise_for_status()
            found = re.findall(rf'({re.escape(product)}_(\d+\.\d+-\d+)\.iso)', listing.text)
            if found:
                fname, ver = max(found, key=lambda pair: version_key(pair[1]))
                return DownloadInfo(version=ver, url=base + fname, filename=fname,
                                    sha256=published_sha256(session, base + "SHA256SUMS", fname, self.name))
        except Exception as e:
            log.warning(f"[Proxmox] Scrape error: {e}")

        raise ScrapeError(self.name, f"no current {product} installer listed on enterprise.proxmox.com")


class QubesRecipe(DistroRecipe):
    key = "qubes"
    name = "Qubes OS"
    description = "Security through compartmentalisation: each task runs in its own isolated VM."

    FLAVORS = [
        FlavorInfo("installer", "Installer"),
    ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        session = self.get_session()
        base = "https://ftp.qubes-os.org/iso/"
        try:
            listing = session.get(base, timeout=25)
            listing.raise_for_status()
            # Release candidates sit in the same directory as finals and must
            # never be served as the current release.
            finals = re.findall(r'(Qubes-R(\d+(?:\.\d+)*)-x86_64\.iso)', listing.text)
            if finals:
                fname, ver = max(finals, key=lambda pair: version_key(pair[1]))
                return DownloadInfo(version=ver, url=base + fname, filename=fname,
                                    sha256=published_sha256(session, f"{base}{fname}.DIGESTS", fname, self.name))
        except Exception as e:
            log.warning(f"[Qubes OS] Scrape error: {e}")

        raise ScrapeError(self.name, "no current stable release listed on ftp.qubes-os.org")


class FreeBSDRecipe(DistroRecipe):
    key = "freebsd"
    name = "FreeBSD"
    description = "The BSD behind a great deal of networking and storage gear: one coherent base system."

    ROOT = "https://download.freebsd.org/releases/amd64/amd64/ISO-IMAGES/"

    FLAVORS = [
        FlavorInfo("disc1", "Installer (disc1)"),
        FlavorInfo("dvd1", "Installer with packages (dvd1)"),
        FlavorInfo("bootonly", "Net Install (bootonly)"),
    ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        if flavor_id not in ("disc1", "dvd1", "bootonly"):
            raise ScrapeError(self.name, f"unknown FreeBSD image {flavor_id!r}")
        session = self.get_session()
        try:
            releases = sorted({h.strip("/") for h in _hrefs(session, self.ROOT)
                               if re.fullmatch(r'\d+\.\d+/', h)}, key=version_key, reverse=True)
            for release in releases:
                # A directory appears for a release while it is still BETA or
                # RC; only "-RELEASE-" images count.
                fname = f"FreeBSD-{release}-RELEASE-amd64-{flavor_id}.iso"
                if fname not in _hrefs(session, f"{self.ROOT}{release}/"):
                    continue
                sha256 = published_sha256(
                    session, f"{self.ROOT}{release}/CHECKSUM.SHA256-FreeBSD-{release}-RELEASE-amd64",
                    fname, self.name)
                return DownloadInfo(version=release, url=f"{self.ROOT}{release}/{fname}",
                                    filename=fname, sha256=sha256)
        except Exception as e:
            log.warning(f"[FreeBSD] Scrape error: {e}")
            raise ScrapeError(self.name, f"could not read download.freebsd.org ({e})")

        raise ScrapeError(self.name, f"no released {flavor_id} image listed on download.freebsd.org")


class IPFireRecipe(DistroRecipe):
    key = "ipfire"
    name = "IPFire"
    description = "Hardened firewall and router distribution, configured from a browser."

    FLAVORS = [FlavorInfo("standard", "Installer x86_64")]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        session = self.get_session()
        try:
            r = session.get("https://www.ipfire.org/downloads", timeout=20)
            r.raise_for_status()
            found = re.findall(
                r'(https://downloads\.ipfire\.org/[^"\s]+/(ipfire-(\d+\.\d+)-core(\d+)-x86_64\.iso))', r.text)
        except Exception as e:
            log.warning(f"[IPFire] Scrape error: {e}")
            raise ScrapeError(self.name, f"could not read ipfire.org ({e})")
        if not found:
            raise ScrapeError(self.name, "ipfire.org listed no x86_64 installer")

        url, fname, series, core = max(found, key=lambda f: (version_key(f[2]), int(f[3])))
        return DownloadInfo(version=f"{series} Core {core}", url=url, filename=fname)


class OracleLinuxRecipe(DistroRecipe):
    key = "oracle"
    name = "Oracle Linux"
    description = "Oracle's free, RHEL-compatible enterprise distribution."

    FLAVORS = [
        FlavorInfo("dvd", "Full DVD"),
        FlavorInfo("boot", "Boot"),
    ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        if flavor_id not in ("dvd", "boot"):
            raise ScrapeError(self.name, f"unknown Oracle Linux image {flavor_id!r}")
        session = self.get_session()
        try:
            r = session.get("https://yum.oracle.com/oracle-linux-isos.html", timeout=20)
            r.raise_for_status()
            found = re.findall(
                rf'(https://yum\.oracle\.com/[^"\s]+/(OracleLinux-R(\d+)-U(\d+)-x86_64-{flavor_id}\.iso))', r.text)
        except Exception as e:
            log.warning(f"[Oracle Linux] Scrape error: {e}")
            raise ScrapeError(self.name, f"could not read yum.oracle.com ({e})")
        if not found:
            raise ScrapeError(self.name, f"yum.oracle.com listed no x86_64 {flavor_id} image")

        url, fname, release, update = max(found, key=lambda f: (int(f[2]), int(f[3])))
        return DownloadInfo(version=f"{release}.{update}", url=url, filename=fname)


class TalosRecipe(DistroRecipe):
    key = "talos"
    name = "Talos Linux"
    description = "Minimal, immutable Linux that exists to run Kubernetes, managed entirely by API."

    FLAVORS = [FlavorInfo("metal", "Bare metal (amd64)")]

    # Not /releases/latest: Talos patches two or three branches at once, and
    # GitHub flags the most recently published release as latest unless told
    # otherwise - one backport published without that would make 1.13.11 the
    # current release over 1.14.2. Twenty releases reach well past the newest
    # final, since every branch is patched every few weeks.
    # ponytail: newest of the last 20; page further if a gap that long appears.
    RELEASES = "https://api.github.com/repos/siderolabs/talos/releases?per_page=20"

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        try:
            r = self.get_session().get(self.RELEASES, timeout=20)
            r.raise_for_status()
            releases = r.json()
        except Exception as e:
            log.warning(f"[Talos Linux] GitHub API error: {e}")
            raise ScrapeError(self.name, f"could not read the Talos release feed ({e})")
        finals = [rel for rel in releases if not rel.get("draft") and not rel.get("prerelease")
                  and re.fullmatch(r'v\d+(\.\d+)+', str(rel.get("tag_name", "")))]
        if not finals:
            raise ScrapeError(self.name, "the Talos release feed listed no final release")
        newest = max(finals, key=lambda rel: version_key(rel["tag_name"]))
        tag = newest["tag_name"]
        for asset in newest.get("assets", []):
            if asset.get("name") == "metal-amd64.iso":
                # Upstream calls every release's image "metal-amd64.iso". Saved
                # under that name, nothing on the drive would say which it is.
                return DownloadInfo(version=tag, url=asset.get("browser_download_url"),
                                    filename=f"talos-{tag.lstrip('v')}-metal-amd64.iso")
        # Not the release before it: its assets may still be uploading.
        raise ScrapeError(self.name, f"Talos {tag} carries no metal-amd64.iso")


class CentOSStreamRecipe(DistroRecipe):
    key = "centos"
    name = "CentOS Stream"
    description = "The continuously delivered distribution that the next RHEL minor release is built from."

    ROOT = "https://mirror.stream.centos.org/"

    FLAVORS = [
        FlavorInfo("dvd", "DVD"),
        FlavorInfo("boot", "Boot"),
    ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        if flavor_id not in ("dvd", "boot"):
            raise ScrapeError(self.name, f"unknown CentOS Stream image {flavor_id!r}")
        kind = "dvd1" if flavor_id == "dvd" else "boot"
        session = self.get_session()
        try:
            streams = [int(m) for m in re.findall(r'href="(\d+)-stream/"', session.get(self.ROOT, timeout=20).text)]
            if not streams:
                raise ScrapeError(self.name, "the mirror index listed no stream")
            stream = max(streams)
            iso_dir = f"{self.ROOT}{stream}-stream/BaseOS/x86_64/iso/"
            listing = session.get(iso_dir, timeout=20)
            listing.raise_for_status()
            # The dated composes, never the "-latest-" alias beside them.
            found = re.findall(rf'(CentOS-Stream-{stream}-(\d{{8}}\.\d+)-x86_64-{kind}\.iso)"', listing.text)
        except ScrapeError:
            raise
        except Exception as e:
            log.warning(f"[CentOS Stream] Scrape error: {e}")
            raise ScrapeError(self.name, f"could not read mirror.stream.centos.org ({e})")
        if not found:
            raise ScrapeError(self.name, f"no dated {kind} image listed for CentOS Stream {stream}")

        fname, compose = max(found, key=lambda f: version_key(f[1]))
        return DownloadInfo(version=f"{stream} ({compose})", url=iso_dir + fname, filename=fname,
                            sha256=published_sha256(session, f"{iso_dir}{fname}.SHA256SUM", fname, self.name))


class XCPngRecipe(DistroRecipe):
    key = "xcpng"
    name = "XCP-ng"
    description = "Open-source Xen hypervisor platform, the community successor to XenServer."

    ROOT = "https://mirrors.xcp-ng.org/isos/"

    FLAVORS = [
        FlavorInfo("standard", "Installer"),
        FlavorInfo("netinstall", "Net Install"),
    ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        if flavor_id not in ("standard", "netinstall"):
            raise ScrapeError(self.name, f"unknown XCP-ng image {flavor_id!r}")
        suffix = "-netinstall" if flavor_id == "netinstall" else ""
        session = self.get_session()
        try:
            series = sorted({h.strip("/") for h in _hrefs(session, self.ROOT) if re.fullmatch(r'\d+\.\d+/', h)},
                            key=version_key, reverse=True)
            for release in series:
                folder = f"{self.ROOT}{release}/"
                isos = [h for h in _hrefs(session, folder) if h.startswith("xcp-ng-") and h.endswith(".iso")]
                # A series' first installer carries no build ("xcp-ng-8.2.1.iso")
                # or a respin number ("8.1.0-2"); refreshed ones are told apart
                # by date, with a ".2" for a second build on the same day. No
                # build ranks below any, so a refresh beats the GA image.
                found = []
                for h in isos:
                    m = re.fullmatch(rf'xcp-ng-(\d+\.\d+\.\d+)(?:-(\d+(?:\.\d+)?))?{suffix}\.iso', h)
                    if m:
                        found.append((h, m.group(1), m.group(2) or ""))
                if found:
                    fname, ver, build = max(found, key=lambda f: (version_key(f[1]), version_key(f[2])))
                    sha256 = published_sha256(session, folder + "SHA256SUMS", fname, self.name)
                    return DownloadInfo(version=f"{ver} ({build})" if build else ver, url=folder + fname,
                                        filename=fname, sha256=sha256)
                # A series opens with its betas and RCs - 8.3 sat in beta for
                # over a year while 8.2 was the release - so only then is the
                # series below it current. Anything else here is a release
                # under a name this does not know, and the one below is not it.
                if any(not re.search(r'-(?:alpha|beta|rc)\d', h) for h in isos):
                    raise ScrapeError(self.name, f"XCP-ng {release} lists no {flavor_id} installer by a known name")
        except ScrapeError:
            raise
        except Exception as e:
            log.warning(f"[XCP-ng] Scrape error: {e}")
            raise ScrapeError(self.name, f"could not read mirrors.xcp-ng.org ({e})")

        raise ScrapeError(self.name, f"no {flavor_id} installer listed on mirrors.xcp-ng.org")


class OpenEulerRecipe(DistroRecipe):
    key = "openeuler"
    name = "openEuler"
    description = ("Enterprise server distribution from the OpenAtom Foundation, with LTS and "
                   "six-monthly innovation releases.")

    ROOT = "https://repo.openeuler.org/"

    FLAVORS = [
        FlavorInfo("lts", "LTS (DVD)"),
        FlavorInfo("lts-netinst", "LTS (Net Install)"),
        FlavorInfo("innovation", "Innovation (DVD)"),
        FlavorInfo("innovation-netinst", "Innovation (Net Install)"),
    ]

    @staticmethod
    def _rank(release: str) -> tuple:
        """24.03-LTS < 24.03-LTS-SP1 < 24.09."""
        numbers = version_key(release.split("-LTS")[0])
        sp = re.search(r'SP(\d+)', release)
        return numbers + (int(sp.group(1)) if sp else 0,)

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        if flavor_id not in ("lts", "lts-netinst", "innovation", "innovation-netinst"):
            raise ScrapeError(self.name, f"unknown openEuler image {flavor_id!r}")
        want_lts = flavor_id.startswith("lts")
        part = "-netinst" if flavor_id.endswith("netinst") else ""
        session = self.get_session()
        try:
            releases = {h.strip("/") for h in _hrefs(session, self.ROOT)
                        if re.fullmatch(r'openEuler-\d\d\.\d\d(?:-LTS(?:-SP\d+)?)?/', h)}
            wanted = sorted((r for r in releases if ("-LTS" in r) == want_lts),
                            key=lambda r: self._rank(r[len("openEuler-"):]), reverse=True)
            for release in wanted:
                fname = f"{release}{part}-x86_64-dvd.iso"
                iso_dir = f"{self.ROOT}{release}/ISO/x86_64/"
                listing = session.get(iso_dir, timeout=20)
                if listing.status_code not in (200, 404):
                    # Not an answer; trying an older release here would serve
                    # it as the current one.
                    raise ScrapeError(self.name, f"{iso_dir} answered HTTP {listing.status_code}")
                # openEuler opens a release's folder when it is announced and
                # fills ISO/ later, so a missing or empty ISO folder means the
                # release before it is still the current one. ISOs under other
                # names do not: the layout changed, and the older release is
                # not current just because its name is the expected one.
                isos = [h for h in hrefs(listing.text) if h.endswith(".iso")] if listing.status_code == 200 else []
                if fname not in isos:
                    if isos:
                        raise ScrapeError(self.name, f"{release} lists no {fname}")
                    continue
                return DownloadInfo(version=release[len("openEuler-"):], url=iso_dir + fname, filename=fname,
                                    sha256=published_sha256(session, f"{iso_dir}{fname}.sha256sum", fname, self.name))
        except ScrapeError:
            raise
        except Exception as e:
            log.warning(f"[openEuler] Scrape error: {e}")
            raise ScrapeError(self.name, f"could not read repo.openeuler.org ({e})")

        raise ScrapeError(self.name, f"no {'LTS' if want_lts else 'innovation'} release with images on repo.openeuler.org")
