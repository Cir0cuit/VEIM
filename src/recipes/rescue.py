import re
from src.core.recipe_base import (
    DistroRecipe, FlavorInfo, DownloadInfo, ScrapeError, SOURCEFORGE_PATHS, published_sha256, sha256_in,
    sourceforge_rss, version_key)
from src.core.logger import log


# SourceForge answers a browser's user agent with a 403 page, so checksums
# are asked for as curl, as sourceforge_rss does.
_CURL = {"User-Agent": "curl/8.4.0"}


def _github_sha256(asset: dict) -> str:
    """The SHA-256 GitHub records for a release asset; "" for one uploaded
    before GitHub kept a digest."""
    digest = asset.get("digest") or ""
    return digest[len("sha256:"):] if digest.startswith("sha256:") else ""


def _checksums_release(session, distro: str, url: str, pattern: str, filename: str):
    """(version, filename, sha256) of the newest image a CHECKSUMS.TXT names.

    Clonezilla and GParted Live publish one per branch, naming the branch's
    current build under MD5SUMS, SHA1SUMS, SHA256SUMS, SHA512SUMS, B2SUMS and
    B3SUMS headings. It names one build today; every match is still compared
    by number, so a file that lists two gives the newer rather than the first.
    """
    try:
        resp = session.get(url, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        log.warning(f"[{distro}] Scrape error: {e}")
        raise ScrapeError(distro, f"could not read {url} ({e})")
    versions = set(re.findall(pattern, resp.text))
    if not versions:
        raise ScrapeError(distro, f"{url} names no image")
    ver = max(versions, key=version_key)
    fname = filename.format(ver)
    # A BLAKE3 sum is 64 hex digits as well, so only the SHA256SUMS block will do.
    block = resp.text.partition("### SHA256SUMS:")[2].partition("###")[0]
    return ver, fname, sha256_in(block, fname)


class ClonezillaRecipe(DistroRecipe):
    key = "clonezilla"
    name = "Clonezilla"
    description = "Bare-metal partition and disk imaging / cloning tool."

    FLAVORS = [
        FlavorInfo("alternative", "Alternative Stable (Ubuntu Base)"),
        FlavorInfo("stable", "Standard Stable (Debian Base)")
    ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        if flavor_id not in ("alternative", "stable"):
            raise ScrapeError(self.name, f"unknown Clonezilla image {flavor_id!r}")
        # The branch's own CHECKSUMS.TXT is what clonezilla.org links as that
        # branch's current build; the testing branches have their own.
        ver, fname, sha256 = _checksums_release(
            self.get_session(), self.name,
            f"https://clonezilla.org/downloads/{flavor_id}/data/CHECKSUMS.TXT",
            r'clonezilla-live-(\S+?)-amd64\.iso', "clonezilla-live-{}-amd64.iso")
        return DownloadInfo(
            version=ver, filename=fname, sha256=sha256,
            url=f"https://downloads.sourceforge.net/project/clonezilla/clonezilla_live_{flavor_id}/{ver}/{fname}")


class GPartedRecipe(DistroRecipe):
    key = "gparted"
    name = "GParted Live"
    description = "Complete partition manager for resizing, copying, and creating partitions."

    FLAVORS = [
        FlavorInfo("standard", "Live AMD64")
    ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        # The CHECKSUMS.TXT gparted.org/download.php links for the stable
        # branch, rather than the first ISO named anywhere on that page.
        ver, fname, sha256 = _checksums_release(
            self.get_session(), self.name, "https://gparted.org/gparted-live/stable/CHECKSUMS.TXT",
            r'gparted-live-(\d+(?:\.\d+)*-\d+)-amd64\.iso', "gparted-live-{}-amd64.iso")
        return DownloadInfo(
            version=ver, filename=fname, sha256=sha256,
            url=f"https://downloads.sourceforge.net/project/gparted/gparted-live-stable/{ver}/{fname}")


class RescuezillaRecipe(DistroRecipe):
    key = "rescuezilla"
    name = "Rescuezilla"
    description = "The Swiss Army knife of system recovery with a friendly point-and-click GUI."

    FLAVORS = [
        FlavorInfo("standard", "Standard 64-bit")
    ]

    API = "https://api.github.com/repos/rescuezilla/rescuezilla/releases/latest"

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        # Each release is built on several Ubuntu bases, one ISO apiece
        # (rescuezilla-2.6.2-64bit.noble.iso ... .resolute.iso), and GitHub
        # lists them alphabetically: the first 64-bit ISO is whichever codename
        # sorts first - noble for 2.6.2, focal for 2.6.1 - not the newest base
        # nor the one upstream recommends. The release notes open by naming
        # that one, which github_latest does not return, hence the API here.
        try:
            r = self.get_session().get(self.API, timeout=15)
            r.raise_for_status()
            release = r.json()
        except Exception as e:
            log.warning(f"[Rescuezilla] GitHub API error: {e}")
            raise ScrapeError(self.name, f"could not read the Rescuezilla release feed ({e})")
        tag = str(release.get("tag_name", ""))
        m = re.search(rf'rescuezilla-{re.escape(tag)}-64bit\.[a-z]+\.iso', release.get("body") or "")
        assets = {a.get("name"): a for a in release.get("assets", [])}
        if not tag or not m or m.group(0) not in assets:
            raise ScrapeError(self.name, f"the Rescuezilla {tag} release notes name no 64-bit ISO it carries")
        asset = assets[m.group(0)]
        return DownloadInfo(version=tag, url=asset.get("browser_download_url"),
                            filename=m.group(0), sha256=_github_sha256(asset))


class ShredOSRecipe(DistroRecipe):
    key = "shredos"
    name = "ShredOS"
    description = "Fast, autonomous disk wiping utility supporting DoD 5220.22-M, Gutmann, and Blancco."

    FLAVORS = [
        FlavorInfo("standard", "Standard x86-64")
    ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        tag, assets = self.github_latest("PartialVolume/shredos.x86_64")
        # A release carries i686 and x86-64 builds, each as .img and .iso, in
        # full, _lite and _plus-partition editions. The whole name pins the
        # full x86-64 .img, which a substring test only found because GitHub
        # happens to list it first. 0.37 and 0.38 had no "v" before their
        # number, and 0.37 a Buildroot point release (2024.02.2_26.0).
        for asset in assets:
            aname = asset.get("name", "")
            if re.fullmatch(r'shredos-\d{4}\.\d+(?:\.\d+)?_\d+(?:\.\d+)?_x86-64_v?\d+(?:\.\d+)*_\d{8}\.img', aname):
                return DownloadInfo(version=tag, url=asset.get("browser_download_url"), filename=aname,
                                    sha256=_github_sha256(asset))
        raise ScrapeError(self.name, "the ShredOS release feed listed no x86-64 image")


class NetbootRecipe(DistroRecipe):
    key = "netboot"
    name = "netboot.xyz"
    description = ("Boot almost any operating system directly over the network via iPXE; "
                   "the .efi editions start in UEFI mode only.")

    FLAVORS = [
        FlavorInfo("standard", "Standard ISO"),
        FlavorInfo("sb", "Secure Boot ISO"),
        FlavorInfo("efi", "UEFI (.efi)"),
        FlavorInfo("snp", "UEFI SNP (.efi)"),
        FlavorInfo("arm64", "ARM64 UEFI (.efi)"),
    ]

    # flavor -> the part of upstream's name between "netboot.xyz" and the extension
    _ASSET = {"standard": ("", ".iso"), "sb": ("-sb", ".iso"), "efi": ("", ".efi"),
              "snp": ("-snp", ".efi"), "arm64": ("-arm64", ".efi")}

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        if flavor_id not in self._ASSET:
            raise ScrapeError(self.name, f"unknown netboot.xyz image {flavor_id!r}")
        edition, ext = self._ASSET[flavor_id]
        aname = f"netboot.xyz{edition}{ext}"
        tag, assets = self.github_latest("netbootxyz/netboot.xyz")
        if not re.fullmatch(r'v?\d+(\.\d+)+', tag):
            raise ScrapeError(self.name, f"the latest netboot.xyz release is tagged {tag!r}, not a version")
        urls = {a.get("name"): a.get("browser_download_url") for a in assets}
        if aname not in urls:
            raise ScrapeError(self.name, f"the latest netboot.xyz release carries no {aname}")

        # A checksum the release does not list is a download left unverified,
        # not a release refused - as for Bazzite.
        sums_url = urls.get("netboot.xyz-sha256-checksums.txt")
        sha256 = published_sha256(self.get_session(), sums_url, aname, self.name) if sums_url else ""

        # Upstream's names are the same for every release; saved as they are,
        # nothing on the drive would say which one it holds.
        version = tag.lstrip("v")
        return DownloadInfo(version=version, url=urls[aname], sha256=sha256,
                            filename=f"netboot.xyz{edition}-{version}{ext}")


class SystemRescueRecipe(DistroRecipe):
    key = "systemrescue"
    name = "SystemRescue"
    description = "Arch-based rescue toolkit for repairing and administering a broken system."

    FLAVORS = [
        FlavorInfo("standard", "Live AMD64"),
    ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        session = self.get_session()
        try:
            paths = re.findall(SOURCEFORGE_PATHS,
                               sourceforge_rss(session, "systemrescuecd", "path=/sysresccd-x86"))
        except Exception as e:
            log.warning(f"[SystemRescue] Scrape error: {e}")
            raise ScrapeError(self.name, f"could not read the SourceForge file list ({e})")

        # The newest release folder first, then its image. The newest image
        # under today's name is the newest release only while the name holds:
        # a next release named differently would leave the two dozen older
        # ones still in the feed offering the previous one. A folder that is
        # not a plain version would be a pre-release.
        folders = {m.group(1) for path in paths
                   if (m := re.fullmatch(r'/sysresccd-x86/(\d+(?:\.\d+)+)/[^/]+', path))}
        if not folders:
            raise ScrapeError(self.name, "no release listed on SourceForge")
        ver = max(folders, key=version_key)
        fname = f"systemrescue-{ver}-amd64.iso"
        if f"/sysresccd-x86/{ver}/{fname}" not in paths:
            raise ScrapeError(self.name, f"SystemRescue {ver} lists no {fname} on SourceForge")
        url = f"https://downloads.sourceforge.net/project/systemrescuecd/sysresccd-x86/{ver}/{fname}"
        return DownloadInfo(version=ver, url=url, filename=fname,
                            sha256=published_sha256(session, url + ".sha256", fname, self.name, headers=_CURL))


class MemtestRecipe(DistroRecipe):
    key = "memtest"
    name = "Memtest86+"
    description = "Stand-alone memory tester that boots before any operating system."

    FLAVORS = [
        FlavorInfo("x86_64", "64-bit"),
        FlavorInfo("grub", "64-bit (GRUB)"),
    ]

    _SUFFIX = {"x86_64": "x86_64", "grub": "x86_64.grub"}

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        suffix = self._SUFFIX.get(flavor_id)
        if not suffix:
            raise ScrapeError(self.name, f"unknown Memtest86+ image {flavor_id!r}")

        session = self.get_session()
        try:
            page = session.get("https://www.memtest.org/", timeout=25)
            page.raise_for_status()
            versions = set(re.findall(rf'mt86plus_(\d+(?:\.\d+)*)_{re.escape(suffix)}\.iso\.zip',
                                      page.text))
        except Exception as e:
            log.warning(f"[Memtest86+] Scrape error: {e}")
            raise ScrapeError(self.name, f"could not read memtest.org ({e})")
        if not versions:
            raise ScrapeError(self.name, "no current release listed on memtest.org")

        ver = max(versions, key=version_key)
        zip_name = f"mt86plus_{ver}_{suffix}.iso.zip"
        # Upstream publishes no plain .iso, and Ventoy cannot boot a .zip, so
        # the downloader unpacks this one - after checking the .zip, which is
        # what upstream's sum is of.
        return DownloadInfo(
            version=ver,
            url=f"https://www.memtest.org/download/v{ver}/{zip_name}",
            filename=f"memtest86plus-{ver}-{suffix}.iso",
            archive="zip",
            sha256=published_sha256(session, f"https://www.memtest.org/download/v{ver}/sha256sum.txt", zip_name,
                                    self.name, headers=_CURL),
        )


class SuperGrub2Recipe(DistroRecipe):
    key = "supergrub2"
    name = "Super GRUB2 Disk"
    description = "Boots an installed system whose own bootloader is broken or missing."

    # flavor -> the platform named in the image file
    PLATFORMS = {
        "multiarch": "multiarch",
        "x86_64-efi": "x86_64_efi",
        "i386-pc": "i386_pc",
        "i386-efi": "i386_efi",
    }

    FLAVORS = [
        FlavorInfo("multiarch", "Hybrid (BIOS and UEFI)"),
        FlavorInfo("x86_64-efi", "64-bit UEFI"),
        FlavorInfo("i386-pc", "Legacy BIOS"),
        FlavorInfo("i386-efi", "32-bit UEFI"),
    ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        platform = self.PLATFORMS.get(flavor_id)
        if platform is None:
            raise ScrapeError(self.name, f"unknown Super GRUB2 Disk image {flavor_id!r}")
        session = self.get_session()
        try:
            paths = re.findall(SOURCEFORGE_PATHS, sourceforge_rss(session, "supergrub2", "limit=100"))
        except Exception as e:
            log.warning(f"[Super GRUB2 Disk] Scrape error: {e}")
            raise ScrapeError(self.name, f"could not read the SourceForge file list ({e})")

        # The newest release folder first, then its image for the platform.
        # The newest image under today's name is the newest release only
        # while the name holds: a next release named differently would leave
        # this one's files, still in the feed, offering this one.
        # Finals only: betas are published as "2.06s5-beta1" in the same tree.
        finals = {m.group(1) for path in paths if (m := re.fullmatch(r'/(\d+\.\d+s\d+)/.+', path))}
        if not finals:
            raise ScrapeError(self.name, "no released Super GRUB2 Disk listed on SourceForge")
        ver = max(finals, key=version_key)
        fname = f"supergrub2-classic-{ver}-{platform}-CD.iso"
        path = next((p for p in paths if p.startswith(f"/{ver}/") and p.endswith("/" + fname)), None)
        if path is None:
            raise ScrapeError(self.name, f"Super GRUB2 Disk {ver} lists no {fname} on SourceForge")
        return DownloadInfo(
            version=ver, filename=fname,
            url=f"https://downloads.sourceforge.net/project/supergrub2{path}",
            sha256=published_sha256(
                session, f"https://downloads.sourceforge.net/project/supergrub2/{ver}/SHA256SUMS", fname,
                self.name, headers=_CURL))


class HrmpfRecipe(DistroRecipe):
    key = "hrmpf"
    name = "hrmpf"
    description = "Void Linux-based rescue system: a console packed with repair and recovery tools."

    FLAVORS = [FlavorInfo("standard", "x86_64")]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        _, assets = self.github_latest("leahneukirchen/hrmpf")
        for asset in assets:
            m = re.fullmatch(r'hrmpf-x86_64-(\d{8})\.iso', asset.get("name", ""))
            if m:
                return DownloadInfo(version=m.group(1), url=asset.get("browser_download_url"),
                                    filename=asset["name"], sha256=_github_sha256(asset))
        raise ScrapeError(self.name, "the latest hrmpf release carries no x86_64 ISO")
