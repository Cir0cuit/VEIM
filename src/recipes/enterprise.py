"""Server, virtualisation and high-security platforms.

These are installers for machines rather than desktops to try out, but they are
exactly the images people keep on a Ventoy stick for provisioning work.
"""
import re
from typing import List

from src.core.recipe_base import DistroRecipe, FlavorInfo, DownloadInfo, ScrapeError
from src.core.logger import log


def _version_key(version: str):
    return tuple(int(p) for p in re.findall(r'\d+', version))


class RockyLinuxRecipe(DistroRecipe):
    def __init__(self):
        super().__init__(
            key="rocky",
            name="Rocky Linux",
            category="Popular & Desktop",
            description="Community enterprise OS, binary compatible with Red Hat Enterprise Linux.",
        )

    def get_flavors(self) -> List[FlavorInfo]:
        return [
            FlavorInfo("dvd", "DVD", "Full installation medium with a package set included."),
            FlavorInfo("minimal", "Minimal", "Smallest bootable installer."),
            FlavorInfo("boot", "Boot", "Network installer; fetches everything during setup."),
        ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        if flavor_id not in ("dvd", "minimal", "boot"):
            raise ScrapeError(self.name, f"unknown Rocky image {flavor_id!r}")

        session = self.get_session()
        root = "https://download.rockylinux.org/pub/rocky/"
        try:
            index = session.get(root, timeout=20)
            index.raise_for_status()
            # The tree carries bare majors ("10") next to point releases
            # ("10.2"); the bare major tracks the newest point release, so
            # prefer it. A string sort would also rank "9.8" above "10".
            majors = sorted({m for m in re.findall(r'href="(\d+)/"', index.text)},
                            key=_version_key)
            for major in reversed(majors):
                listing = session.get(f"{root}{major}/isos/x86_64/", timeout=20)
                if listing.status_code != 200:
                    continue
                # The point release by name ("Rocky-10.2-..."), never the
                # "Rocky-10-latest-..." alias beside it: that name and the bare
                # "10" stay the same through 10.3 and 10.4, so an image
                # downloaded at 10.2 would read as up to date for good. The
                # DVD alone is numbered ("dvd1").
                found = re.findall(
                    rf'(Rocky-({major}\.\d+)-x86_64-{flavor_id}\d?\.iso)', listing.text)
                if found:
                    fname, ver = max(found, key=lambda pair: _version_key(pair[1]))
                    return DownloadInfo(
                        version=ver,
                        url=f"{root}{major}/isos/x86_64/{fname}",
                        filename=fname,
                    )
        except Exception as e:
            log.warning(f"[Rocky Linux] Scrape error: {e}")

        raise ScrapeError(self.name, f"no current {flavor_id} image listed on download.rockylinux.org")


class ProxmoxRecipe(DistroRecipe):
    def __init__(self):
        super().__init__(
            key="proxmox",
            name="Proxmox",
            category="Rescue & Diagnostics",
            description="Virtual Environment, Backup Server, Mail Gateway and Datacenter Manager, "
                        "each a bare-metal appliance managed from a browser.",
        )

    # flavor -> the product's name in its image file. "installer" is VE, and
    # keeps the id it had when VE was the only product listed.
    PRODUCTS = {
        "installer": "proxmox-ve",
        "backup-server": "proxmox-backup-server",
        "mail-gateway": "proxmox-mail-gateway",
        "datacenter-manager": "proxmox-datacenter-manager",
    }

    def get_flavors(self) -> List[FlavorInfo]:
        return [
            FlavorInfo("installer", "Virtual Environment", "KVM and LXC virtualisation platform."),
            FlavorInfo("backup-server", "Backup Server", "Deduplicating backup target for VMs, containers and hosts."),
            FlavorInfo("mail-gateway", "Mail Gateway", "Spam and virus filtering in front of a mail server."),
            FlavorInfo("datacenter-manager", "Datacenter Manager", "One view over several Proxmox clusters."),
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
                fname, ver = max(found, key=lambda pair: _version_key(pair[1]))
                return DownloadInfo(version=ver, url=base + fname, filename=fname)
        except Exception as e:
            log.warning(f"[Proxmox] Scrape error: {e}")

        raise ScrapeError(self.name, f"no current {product} installer listed on enterprise.proxmox.com")


class QubesRecipe(DistroRecipe):
    def __init__(self):
        super().__init__(
            key="qubes",
            name="Qubes OS",
            category="Security & Pentest",
            description="Security through compartmentalisation: each task runs in its own isolated VM.",
        )

    def get_flavors(self) -> List[FlavorInfo]:
        return [
            FlavorInfo("installer", "Installer", "Full installation image, around 6 GB."),
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
                fname, ver = max(finals, key=lambda pair: _version_key(pair[1]))
                return DownloadInfo(version=ver, url=base + fname, filename=fname)
        except Exception as e:
            log.warning(f"[Qubes OS] Scrape error: {e}")

        raise ScrapeError(self.name, "no current stable release listed on ftp.qubes-os.org")


def _hrefs(session, url: str, timeout: int = 20) -> List[str]:
    """Every href on a page. Raises when the page cannot be read."""
    r = session.get(url, timeout=timeout)
    r.raise_for_status()
    return re.findall(r'href="([^"]+)"', r.text)


class FreeBSDRecipe(DistroRecipe):
    ROOT = "https://download.freebsd.org/releases/amd64/amd64/ISO-IMAGES/"

    def __init__(self):
        super().__init__(
            key="freebsd",
            name="FreeBSD",
            category="Server & Enterprise",
            description="The BSD behind a great deal of networking and storage gear: one coherent base system.",
        )

    def get_flavors(self) -> List[FlavorInfo]:
        return [
            FlavorInfo("disc1", "Installer (disc1)", "Standard installer with the base system."),
            FlavorInfo("dvd1", "Installer with packages (dvd1)", "Installer plus a set of packages for offline setup."),
            FlavorInfo("bootonly", "Network installer (bootonly)", "Smallest image; fetches everything during setup."),
        ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        if flavor_id not in ("disc1", "dvd1", "bootonly"):
            raise ScrapeError(self.name, f"unknown FreeBSD image {flavor_id!r}")
        session = self.get_session()
        try:
            releases = sorted({h.strip("/") for h in _hrefs(session, self.ROOT)
                               if re.fullmatch(r'\d+\.\d+/', h)}, key=_version_key, reverse=True)
            for release in releases:
                # A directory appears for a release while it is still BETA or
                # RC; only "-RELEASE-" images count.
                fname = f"FreeBSD-{release}-RELEASE-amd64-{flavor_id}.iso"
                if fname not in _hrefs(session, f"{self.ROOT}{release}/"):
                    continue
                sha256 = ""
                sums = session.get(f"{self.ROOT}{release}/CHECKSUM.SHA256-FreeBSD-{release}-RELEASE-amd64", timeout=20)
                if sums.status_code == 200:
                    m = re.search(rf'SHA256 \({re.escape(fname)}\) = ([0-9a-f]{{64}})', sums.text)
                    sha256 = m.group(1) if m else ""
                return DownloadInfo(version=release, url=f"{self.ROOT}{release}/{fname}",
                                    filename=fname, sha256=sha256)
        except Exception as e:
            log.warning(f"[FreeBSD] Scrape error: {e}")
            raise ScrapeError(self.name, f"could not read download.freebsd.org ({e})")

        raise ScrapeError(self.name, f"no released {flavor_id} image listed on download.freebsd.org")


class IPFireRecipe(DistroRecipe):
    def __init__(self):
        super().__init__(
            key="ipfire",
            name="IPFire",
            category="Server & Enterprise",
            description="Hardened firewall and router distribution, configured from a browser.",
        )

    def get_flavors(self) -> List[FlavorInfo]:
        return [FlavorInfo("standard", "Installer x86_64", "Firewall installer for 64-bit PCs.")]

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

        url, fname, series, core = max(found, key=lambda f: (_version_key(f[2]), int(f[3])))
        return DownloadInfo(version=f"{series} Core {core}", url=url, filename=fname)


class OracleLinuxRecipe(DistroRecipe):
    def __init__(self):
        super().__init__(
            key="oracle",
            name="Oracle Linux",
            category="Server & Enterprise",
            description="Oracle's free, RHEL-compatible enterprise distribution.",
        )

    def get_flavors(self) -> List[FlavorInfo]:
        return [
            FlavorInfo("dvd", "Full ISO (DVD)", "Complete offline installation medium."),
            FlavorInfo("boot", "Boot ISO", "Network installer; fetches packages during setup."),
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
    def __init__(self):
        super().__init__(
            key="talos",
            name="Talos Linux",
            category="Server & Enterprise",
            description="Minimal, immutable Linux that exists to run Kubernetes, managed entirely by API.",
        )

    def get_flavors(self) -> List[FlavorInfo]:
        return [FlavorInfo("metal", "Bare metal (amd64)", "Boot image for installing Talos on physical machines.")]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        session = self.get_session()
        try:
            r = session.get("https://api.github.com/repos/siderolabs/talos/releases/latest", timeout=15)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            log.warning(f"[Talos] GitHub API error: {e}")
            raise ScrapeError(self.name, f"could not read the Talos release feed ({e})")

        tag = str(data.get("tag_name", ""))
        for asset in data.get("assets", []):
            if asset.get("name") == "metal-amd64.iso" and re.fullmatch(r'v\d+(\.\d+)+', tag):
                # Upstream calls every release's image "metal-amd64.iso". Saved
                # under that name, nothing on the drive would say which it is.
                return DownloadInfo(version=tag, url=asset.get("browser_download_url"),
                                    filename=f"talos-{tag.lstrip('v')}-metal-amd64.iso")
        raise ScrapeError(self.name, "the latest Talos release carries no metal-amd64.iso")


class CentOSStreamRecipe(DistroRecipe):
    ROOT = "https://mirror.stream.centos.org/"

    def __init__(self):
        super().__init__(
            key="centos",
            name="CentOS Stream",
            category="Server & Enterprise",
            description="The continuously delivered distribution that the next RHEL minor release is built from.",
        )

    def get_flavors(self) -> List[FlavorInfo]:
        return [
            FlavorInfo("dvd", "DVD", "Full installation medium."),
            FlavorInfo("boot", "Boot", "Network installer; fetches everything during setup."),
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

        fname, compose = max(found, key=lambda f: _version_key(f[1]))
        sha256 = ""
        try:
            sums = session.get(f"{iso_dir}{fname}.SHA256SUM", timeout=20)
            m = re.search(r'=\s*([0-9a-f]{64})', sums.text) if sums.status_code == 200 else None
            sha256 = m.group(1) if m else ""
        except Exception as e:
            log.warning(f"[CentOS Stream] No checksum for {fname}: {e}")
        return DownloadInfo(version=f"{stream} ({compose})", url=iso_dir + fname, filename=fname, sha256=sha256)


class XCPngRecipe(DistroRecipe):
    ROOT = "https://mirrors.xcp-ng.org/isos/"

    def __init__(self):
        super().__init__(
            key="xcpng",
            name="XCP-ng",
            category="Server & Enterprise",
            description="Open-source Xen hypervisor platform, the community successor to XenServer.",
        )

    def get_flavors(self) -> List[FlavorInfo]:
        return [
            FlavorInfo("standard", "Installer", "Full offline installer."),
            FlavorInfo("netinstall", "Network installer", "Small installer that fetches packages during setup."),
        ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        if flavor_id not in ("standard", "netinstall"):
            raise ScrapeError(self.name, f"unknown XCP-ng image {flavor_id!r}")
        suffix = "-netinstall" if flavor_id == "netinstall" else ""
        session = self.get_session()
        try:
            series = sorted({h.strip("/") for h in _hrefs(session, self.ROOT) if re.fullmatch(r'\d+\.\d+/', h)},
                            key=_version_key, reverse=True)
            for release in series:
                # Refreshed installers of one release are told apart by date,
                # with a ".2" for a second build on the same day.
                found = []
                for h in _hrefs(session, f"{self.ROOT}{release}/"):
                    m = re.fullmatch(rf'xcp-ng-(\d+\.\d+\.\d+)-(\d{{8}}(?:\.\d+)?){suffix}\.iso', h)
                    if m:
                        found.append((h, m.group(1), m.group(2)))
                if found:
                    fname, ver, build = max(found, key=lambda f: (_version_key(f[1]), _version_key(f[2])))
                    return DownloadInfo(version=f"{ver} ({build})", url=f"{self.ROOT}{release}/{fname}", filename=fname)
        except Exception as e:
            log.warning(f"[XCP-ng] Scrape error: {e}")
            raise ScrapeError(self.name, f"could not read mirrors.xcp-ng.org ({e})")

        raise ScrapeError(self.name, f"no {flavor_id} installer listed on mirrors.xcp-ng.org")


class OpenEulerRecipe(DistroRecipe):
    ROOT = "https://repo.openeuler.org/"

    def __init__(self):
        super().__init__(
            key="openeuler",
            name="openEuler",
            category="Server & Enterprise",
            description="Enterprise server distribution from the OpenAtom Foundation, with LTS and "
                        "six-monthly innovation releases.",
        )

    def get_flavors(self) -> List[FlavorInfo]:
        return [
            FlavorInfo("lts", "LTS (DVD)", "Newest long-term support release, with its latest service pack."),
            FlavorInfo("lts-netinst", "LTS (Network Install)", "Small LTS installer that fetches packages during setup."),
            FlavorInfo("innovation", "Innovation release (DVD)", "Newest six-monthly release."),
            FlavorInfo("innovation-netinst", "Innovation release (Network Install)", "Small installer for the newest release."),
        ]

    @staticmethod
    def _rank(release: str) -> tuple:
        """24.03-LTS < 24.03-LTS-SP1 < 24.09."""
        numbers = _version_key(release.split("-LTS")[0])
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
                if listing.status_code == 404 or f'"{fname}"' not in listing.text:
                    continue                  # announced, images not published yet
                sha256 = ""
                sums = session.get(f"{iso_dir}{fname}.sha256sum", timeout=20)
                if sums.status_code == 200:
                    m = re.match(r'([0-9a-f]{64})', sums.text.strip())
                    sha256 = m.group(1) if m else ""
                return DownloadInfo(version=release[len("openEuler-"):], url=iso_dir + fname,
                                    filename=fname, sha256=sha256)
        except Exception as e:
            log.warning(f"[openEuler] Scrape error: {e}")
            raise ScrapeError(self.name, f"could not read repo.openeuler.org ({e})")

        raise ScrapeError(self.name, f"no {'LTS' if want_lts else 'innovation'} release with images on repo.openeuler.org")
