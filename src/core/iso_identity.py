"""Recognise an image the catalog can keep up to date, from its filename alone.

VEIM used to take in every ISO it found and guess what it was from a word in
the name. "clonezilla-live-galaxybook-20260808.iso" - someone's customised
image - became the official Clonezilla with the version "Live", was offered an
update, and would have been overwritten by it. Anything unrecognised became a
row that could never be checked at all.

So this is strict on purpose. A name has to match, in full, the way the project
itself names that download, and it has to carry a version that compares equal
to the one the recipe reports. A renamed, remastered or otherwise unfamiliar
ISO matches nothing and is left alone - never adopted on a guess.

Names that stay the same from one release to the next (the "-Current" and
"-latest-" aliases, Bazzite's "-stable", upstream's own netboot.xyz.iso) are
deliberately absent: there is no telling which release such a file holds.
Where VEIM renames such a download so that it does say (Bazzite, Talos,
netboot.xyz), the rule reads VEIM's name instead.

Not every image is an ISO - netboot.xyz also ships bare .efi files, which
Ventoy boots too - so each rule spells out its own extension.
"""
import re
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Union

from src.core.recipe_base import clean_version


@dataclass(frozen=True)
class IsoIdentity:
    key: str            # recipe key
    flavor_id: str
    version: str        # in the form the recipe's DownloadInfo reports it


Flavor = Union[str, Dict[str, str], Callable[[re.Match], str]]


class _Rule:
    def __init__(self, key: str, pattern: str, flavor: Flavor, version: str = "{v}"):
        self.key = key
        self.regex = re.compile(pattern, re.IGNORECASE)
        self.flavor = flavor
        self.version = version

    def match(self, filename: str) -> Optional[IsoIdentity]:
        m = self.regex.fullmatch(filename)
        if not m:
            return None
        if callable(self.flavor):
            flavor = self.flavor(m)
        elif isinstance(self.flavor, dict):
            flavor = self.flavor.get((m.group("f") or "").lower(), "")
        else:
            flavor = self.flavor
        if not flavor:
            return None
        version = clean_version(self.version.format(**m.groupdict()))
        return IsoIdentity(self.key, flavor, version)


def _same(*names: str) -> Dict[str, str]:
    """Flavor ids that are spelled the way the filename spells them."""
    return {n: n for n in names}


V = r"(?P<v>\d+(?:\.\d+)*)"          # 44, 22.3, 13.7.0
DATE8 = r"(?P<v>\d{8})"              # 20260813

_RULES: List[_Rule] = [
    # Fedora is four catalog entries (see recipes/fedora.py); the name says
    # which one an image belongs to.
    _Rule("fedora", r"Fedora-(?P<f>Workstation|KDE-Desktop|KDE)-Live-(?P<v>\d+)-[\d.]+\.x86_64\.iso",
          {"workstation": "workstation", "kde-desktop": "kde", "kde": "kde"}),
    # Fedora put the architecture before the version until release 42.
    _Rule("fedora", r"Fedora-(?P<f>Workstation|KDE)-Live-x86_64-(?P<v>\d+)-[\d.]+\.iso",
          _same("workstation", "kde")),
    _Rule("fedora", r"Fedora-Server-(?P<f>dvd|netinst)-x86_64-(?P<v>\d+)-[\d.]+\.iso",
          {"dvd": "server", "netinst": "server-netinst"}),
    _Rule("fedora", r"Fedora-Everything-netinst-x86_64-(?P<v>\d+)-[\d.]+\.iso", "everything"),
    _Rule("fedora", r"Fedora-IoT-ostree-(?P<v>\d+)-(?P<d>\d{8}\.\d+)\.x86_64\.iso", "iot",
          version="{v} ({d})"),
    _Rule("fedora_atomic", r"Fedora-(?P<f>Silverblue|Kinoite|Sericea|Onyx|COSMIC-Atomic)-ostree-x86_64"
                           r"-(?P<v>\d+)-[\d.]+\.iso",
          {"silverblue": "silverblue", "kinoite": "kinoite", "sericea": "sway-atomic",
           "onyx": "budgie-atomic", "cosmic-atomic": "cosmic-atomic"}),
    # From 45 (seen in its Beta): "Fedora-Silverblue-Installer-45-1.3.x86_64.iso".
    _Rule("fedora_atomic", r"Fedora-(?P<f>Silverblue|Kinoite|CosmicAtomic)-Installer"
                           r"-(?P<v>\d+)-[\d.]+\.x86_64\.iso",
          {"silverblue": "silverblue", "kinoite": "kinoite", "cosmicatomic": "cosmic-atomic"}),
    _Rule("fedora_spins", r"Fedora-(?P<f>Xfce|Cinnamon|Budgie|COSMIC|MATE_Compiz|LXQt|LXDE|i3|Sway"
                          r"|MiracleWM|KDE-Mobile|SoaS)-Live-(?P<v>\d+)-[\d.]+\.x86_64\.iso",
          {"xfce": "xfce", "cinnamon": "cinnamon", "budgie": "budgie", "cosmic": "cosmic",
           "mate_compiz": "mate", "lxqt": "lxqt", "lxde": "lxde", "i3": "i3", "sway": "sway",
           "miraclewm": "miraclewm", "kde-mobile": "kde-mobile", "soas": "soas"}),
    _Rule("fedora_spins", r"Fedora-(?P<f>Xfce|Cinnamon|Budgie|MATE_Compiz|LXQt|LXDE|i3|Sway|SoaS)"
                          r"-Live-x86_64-(?P<v>\d+)-[\d.]+\.iso",
          {"xfce": "xfce", "cinnamon": "cinnamon", "budgie": "budgie", "mate_compiz": "mate",
           "lxqt": "lxqt", "lxde": "lxde", "i3": "i3", "sway": "sway", "soas": "soas"}),
    _Rule("fedora_labs", r"Fedora-(?P<f>Astronomy_KDE|Design_suite|Games|Jam_KDE|Python-Classroom|Robotics"
                         r"|Scientific_KDE|Security)-Live-(?P<v>\d+)-[\d.]+\.x86_64\.iso",
          {"astronomy_kde": "astronomy", "design_suite": "design-suite", "games": "games",
           "jam_kde": "jam", "python-classroom": "python-classroom", "robotics": "robotics",
           "scientific_kde": "scientific", "security": "security"}),

    _Rule("ubuntu", rf"ubuntu-{V}-desktop-amd64\.iso", "desktop"),
    _Rule("ubuntu", rf"ubuntu-{V}-live-server-amd64\.iso", "server"),
    _Rule("ubuntu", rf"(?P<f>kubuntu|xubuntu|lubuntu)-{V}-desktop-amd64\.iso",
          _same("kubuntu", "xubuntu", "lubuntu")),
    _Rule("ubuntu", rf"ubuntu-(?P<f>mate|budgie|unity)-{V}-desktop-amd64\.iso",
          _same("mate", "budgie", "unity")),
    _Rule("ubuntu", rf"(?P<f>ubuntucinnamon|ubuntustudio|edubuntu|ubuntukylin)-{V}-desktop-amd64\.iso",
          {"ubuntucinnamon": "cinnamon", "ubuntustudio": "studio", "edubuntu": "edubuntu",
           "ubuntukylin": "kylin"}),

    _Rule("mint", rf"linuxmint-{V}-(?P<f>cinnamon|mate|xfce)-64bit\.iso",
          _same("cinnamon", "mate", "xfce")),

    _Rule("debian", rf"debian-{V}-amd64-netinst\.iso", "netinst"),
    _Rule("debian", rf"debian-live-{V}-amd64-(?P<f>gnome|kde|xfce|cinnamon|mate|lxqt|lxde|standard)\.iso",
          _same("gnome", "kde", "xfce", "cinnamon", "mate", "lxqt", "lxde", "standard")),

    # The Intel/AMD image's channel was "intel" until 24.04's release, "generic" since.
    _Rule("popos", rf"pop-os_{V}_amd64_(?P<f>intel|generic|nvidia)_(?P<b>\d+)\.iso",
          {"intel": "intel", "generic": "intel", "nvidia": "nvidia"}, version="{v} (Build {b})"),
    # "-r3" is a respin of the same release, and newer than it. A bare major
    # gains ".0" so that "18.0 r3" still sorts below "18.1".
    _Rule("zorin", r"Zorin-OS-(?P<v>\d+(?:\.\d+)+)-(?P<f>Core|Education)-64-bit-r(?P<r>\d+)\.iso",
          _same("core", "education"), version="{v} r{r}"),
    _Rule("zorin", r"Zorin-OS-(?P<v>\d+)-(?P<f>Core|Education)-64-bit-r(?P<r>\d+)\.iso",
          _same("core", "education"), version="{v}.0 r{r}"),
    _Rule("zorin", rf"Zorin-OS-{V}-(?P<f>Core|Education)-64-bit\.iso",
          _same("core", "education")),
    _Rule("kde_neon", r"neon-user-desktop-(?P<v>\d{8}-\d{4})\.iso", "user"),
    _Rule("opensuse", r"Leap-(?P<v>\d+\.\d+)-(?P<f>offline|online)-installer-x86_64"
                      r"-Build(?P<b>[\d.]+)\.install\.iso",
          {"offline": "leap-dvd", "online": "leap-net"}, version="{v} (Build {b})"),
    # Leap 15 and earlier. Still recognised, so that one left on a drive is
    # offered its update to the current release.
    _Rule("opensuse", rf"openSUSE-Leap-{V}-(?P<f>DVD|NET)-x86_64-Current\.iso",
          {"dvd": "leap-dvd", "net": "leap-net"}),
    _Rule("opensuse", r"openSUSE-Tumbleweed-(?P<f>DVD|KDE-Live|GNOME-Live|NET)-x86_64"
                      r"-Snapshot(?P<v>\d{8})-Media\.iso",
          {"dvd": "tumbleweed-dvd", "kde-live": "tumbleweed-kde",
           "gnome-live": "tumbleweed-gnome", "net": "tumbleweed-net"}),
    _Rule("nixos", r"nixos-(?P<f>graphical|minimal)-(?P<v>\d+\.\d+\.\d+)\.[0-9a-f]+-x86_64-linux\.iso",
          _same("graphical", "minimal")),
    # The DVD alone is numbered ("dvd1").
    _Rule("rocky", r"Rocky-(?P<v>\d+\.\d+)-x86_64-(?P<f>dvd|minimal|boot)\d?\.iso",
          _same("dvd", "minimal", "boot")),
    _Rule("almalinux", r"AlmaLinux-(?P<v>\d+\.\d+)-x86_64-(?P<f>dvd|minimal|boot)\.iso",
          _same("dvd", "minimal", "boot")),
    # The date is the build, and the only part a point release changes.
    _Rule("elementary", rf"elementaryos-{V}-stable-amd64\.(?P<d>\d+)\.iso", "stable",
          version="{v} ({d})"),
    _Rule("tuxedo", r"TUXEDO-OS-(?P<v>\d{12})\.iso", "standard"),
    _Rule("mageia", rf"Mageia-{V}-x86_64\.iso", "classic-dvd"),
    _Rule("mageia", rf"Mageia-{V}-Live-(?P<f>Plasma|GNOME|Xfce)-x86_64\.iso",
          {"plasma": "live-plasma", "gnome": "live-gnome", "xfce": "live-xfce"}),

    _Rule("mxlinux", rf"MX-{V}_(?P<f>Xfce_ahs|Xfce|KDE|fluxbox)_x64\.iso",
          {"xfce": "xfce", "xfce_ahs": "xfce-ahs", "kde": "kde", "fluxbox": "fluxbox"}),
    _Rule("devuan", rf"devuan_[a-z]+_{V}_amd64_(?P<f>desktop-live|netinstall|server)\.iso",
          _same("desktop-live", "netinstall", "server")),
    _Rule("slackware", rf"slackware64-{V}-install-dvd\.iso", "install-dvd"),

    _Rule("arch", r"archlinux-(?P<v>\d{4}\.\d{2}\.\d{2})-x86_64\.iso", "standard"),
    _Rule("manjaro", rf"manjaro-(?P<f>kde|gnome|xfce)-{V}-\d+-linux\d+\.iso",
          {"kde": "plasma", "gnome": "gnome", "xfce": "xfce"}),
    _Rule("endeavour", r"EndeavourOS_[A-Za-z_-]+-(?P<v>\d{4}\.\d{2}\.\d{2})\.iso", "standard"),
    _Rule("endeavour", r"EndeavourOS_[A-Za-z_-]+-(?P<v>\d{4}\.\d{2}\.\d{2})_R(?P<r>\d+)\.iso", "standard",
          version="{v} R{r}"),
    _Rule("artix", rf"artix-(?P<f>[a-z]+-(?:openrc|runit))-{DATE8}-x86_64\.iso",
          _same("plasma-openrc", "xfce-openrc", "base-openrc", "base-runit",
                "cinnamon-openrc", "mate-openrc")),
    _Rule("void", rf"void-live-x86_64-(?P<m>musl-)?{DATE8}-(?P<f>base|xfce)\.iso",
          lambda m: ("musl-" if m.group("m") else "") + m.group("f").lower()),
    _Rule("gentoo", rf"install-amd64-minimal-{DATE8}T\d{{6}}Z\.iso", "minimal"),
    _Rule("gentoo", rf"livegui-amd64-{DATE8}T\d{{6}}Z\.iso", "livegui"),
    _Rule("omarchy", rf"omarchy-{V}\.iso", "standard"),

    # VEIM's own name for it: upstream's is the same for every build.
    _Rule("bazzite", rf"(?P<f>bazzite(?:-deck)?(?:-gnome)?(?:-nvidia(?:-open)?)?)-stable-live-{DATE8}-amd64\.iso",
          {"bazzite": "desktop-kde", "bazzite-gnome": "desktop-gnome", "bazzite-deck": "deck-kde",
           "bazzite-deck-gnome": "deck-gnome", "bazzite-nvidia": "desktop-nvidia",
           "bazzite-nvidia-open": "desktop-nvidia-open", "bazzite-gnome-nvidia": "desktop-gnome-nvidia",
           "bazzite-gnome-nvidia-open": "desktop-gnome-nvidia-open"}),
    _Rule("garuda", r"garuda-(?P<f>dr460nized-gaming|dr460nized|gnome|kde-lite|xfce|cinnamon|mokka"
                    r"|hyprland|sway|i3)-linux-[a-z]+-(?P<v>\d{6})\.iso",
          _same("dr460nized-gaming", "dr460nized", "gnome", "kde-lite", "xfce", "cinnamon", "mokka",
                "hyprland", "sway", "i3")),
    _Rule("cachyos", r"cachyos-(?P<f>desktop|handheld)-linux-(?P<v>\d{6})\.iso",
          _same("desktop", "handheld")),
    _Rule("nobara", r"Nobara-(?P<v>\d+)-(?P<f>Official|KDE|GNOME|Steam-HTPC|Steam-Handheld)"
                    r"-(?P<d>\d{4}-\d{2}-\d{2})\.iso",
          _same("official", "kde", "gnome", "steam-htpc", "steam-handheld"),
          version="{v} ({d})"),
    _Rule("pikaos", rf"PikaOS-[A-Za-z]+-(?P<f>NVIDIA-KDE|NVIDIA-GNOME|KDE|GNOME|Hyprland|COSMIC|Niri)"
                    rf"-{V}-amd64-v3-(?P<d>[\d.]+)-\d+\.iso",
          _same("nvidia-kde", "nvidia-gnome", "kde", "gnome", "hyprland", "cosmic", "niri"),
          version="{v} ({d})"),

    _Rule("kali", r"kali-linux-(?P<v>\d{4}\.\d+[a-z]?)-installer-amd64\.iso", "installer"),
    _Rule("kali", r"kali-linux-(?P<v>\d{4}\.\d+[a-z]?)-installer-purple-amd64\.iso", "purple"),
    _Rule("kali", r"kali-linux-(?P<v>\d{4}\.\d+[a-z]?)-installer-netinst-amd64\.iso", "netinst"),
    _Rule("parrot", rf"Parrot-(?P<f>security|home)-{V}_amd64\.iso", _same("security", "home")),
    _Rule("tails", rf"tails-amd64-{V}\.iso", "standard"),
    _Rule("hackeros", rf"HackerOS-V{V}(?:-(?P<f>LTS|Cybersecurity|Gaming))?\.iso",
          lambda m: (m.group("f") or "official").lower()),
    _Rule("qubes", rf"Qubes-R{V}-x86_64\.iso", "installer"),

    # The two branches differ only in how they write a version.
    _Rule("clonezilla", r"clonezilla-live-(?P<v>\d{8}-[a-z]+)-amd64\.iso", "alternative"),
    _Rule("clonezilla", r"clonezilla-live-(?P<v>\d+\.\d+\.\d+-\d+)-amd64\.iso", "stable"),
    _Rule("systemrescue", rf"systemrescue-{V}-amd64\.iso", "standard"),
    _Rule("grml", r"grml-(?P<f>full|small)-(?P<v>\d{4}\.\d{2}(?:\.\d+)*)-amd64\.iso", _same("full", "small")),
    _Rule("memtest", rf"memtest86plus-{V}-x86_64(?P<g>\.grub)?\.iso",
          lambda m: "grub" if m.group("g") else "x86_64"),
    # VEIM's own names: upstream's are the same for every release.
    _Rule("netboot", rf"netboot\.xyz(?P<f>-sb)?-{V}\.iso", {"": "standard", "-sb": "sb"}),
    _Rule("netboot", rf"netboot\.xyz(?P<f>-snp|-arm64)?-{V}\.efi",
          {"": "efi", "-snp": "snp", "-arm64": "arm64"}),
    _Rule("proxmox", r"proxmox-(?P<f>ve|backup-server|mail-gateway|datacenter-manager)"
                     r"_(?P<v>\d+\.\d+-\d+)\.iso",
          {"ve": "installer", "backup-server": "backup-server", "mail-gateway": "mail-gateway",
           "datacenter-manager": "datacenter-manager"}),
    _Rule("gparted", r"gparted-live-(?P<v>\d+(?:\.\d+)*-\d+)-amd64\.iso", "standard"),
    _Rule("rescuezilla", rf"rescuezilla-{V}-64bit\.[a-z]+\.iso", "standard"),
    # The version is the release tag, v2025.11_31_x86-64_0.42, which the
    # name spells with the "v" moved (or dropped, as 0.37's was) and the
    # build date added. The Buildroot base can be a point release, 2024.02.2.
    _Rule("shredos", r"shredos-(?P<b>\d{4}\.\d+(?:\.\d+)?_\d+(?:\.\d+)?)_x86-64_v?(?P<n>\d+(?:\.\d+)*)_\d{8}\.img",
          "standard",
          version="{b}_x86-64_{n}"),

    _Rule("supergrub2", r"supergrub2-classic-(?P<v>\d+\.\d+s\d+)-(?P<f>multiarch|x86_64_efi|i386_pc|i386_efi)"
                        r"-CD\.iso",
          {"multiarch": "multiarch", "x86_64_efi": "x86_64-efi", "i386_pc": "i386-pc", "i386_efi": "i386-efi"}),
    _Rule("hrmpf", rf"hrmpf-x86_64-{DATE8}\.iso", "standard"),
    _Rule("caine", r"caine(?P<v>\d+(?:\.\d+)?)\.iso", "standard"),       # caine14.0.iso, caine11.iso

    _Rule("linuxlite", r"linux-lite-(?P<v>\d+\.\d+)-64bit\.iso", "standard"),
    _Rule("freebsd", r"FreeBSD-(?P<v>\d+\.\d+)-RELEASE-amd64-(?P<f>disc1|dvd1|bootonly)\.iso",
          _same("disc1", "dvd1", "bootonly")),
    _Rule("ipfire", r"ipfire-(?P<v>\d+\.\d+)-core(?P<c>\d+)-x86_64\.iso", "standard",
          version="{v} Core {c}"),
    _Rule("oracle", r"OracleLinux-R(?P<r>\d+)-U(?P<u>\d+)-x86_64-(?P<f>dvd|boot)\.iso",
          _same("dvd", "boot"), version="{r}.{u}"),
    # VEIM's own name for it: upstream calls every release "metal-amd64.iso".
    _Rule("talos", rf"talos-{V}-metal-amd64\.iso", "metal"),
    _Rule("centos", r"CentOS-Stream-(?P<s>\d+)-(?P<c>\d{8}\.\d+)-x86_64-(?P<f>dvd1|boot)\.iso",
          {"dvd1": "dvd", "boot": "boot"}, version="{s} ({c})"),
    # A dated refresh or a respin ("8.1.0-2"), and a series' first image, which has no build.
    _Rule("xcpng", r"xcp-ng-(?P<v>\d+\.\d+\.\d+)-(?P<b>\d+(?:\.\d+)?)(?P<n>-netinstall)?\.iso",
          lambda m: "netinstall" if m.group("n") else "standard", version="{v} ({b})"),
    _Rule("xcpng", r"xcp-ng-(?P<v>\d+\.\d+\.\d+)(?P<n>-netinstall)?\.iso",
          lambda m: "netinstall" if m.group("n") else "standard"),
    _Rule("openeuler", r"openEuler-(?P<v>\d\d\.\d\d(?:-LTS(?:-SP\d+)?)?)(?P<n>-netinst)?-x86_64-dvd\.iso",
          lambda m: ("lts" if "lts" in m.group("v").lower() else "innovation")
                    + ("-netinst" if m.group("n") else "")),

    _Rule("puppy", rf"BookwormPup64_{V}\.iso", "bookworm"),
    _Rule("puppy", rf"fossapup64-{V}\.iso", "fossa"),
    # The official builds are numbered by series and build date; the 11.x
    # test builds are still recognised, so one on a drive is offered them.
    _Rule("puppy", r"TrixiePup64-Wayland-(?P<v>\d{4}-\d{6})\.iso", "trixie"),
    _Rule("puppy", rf"Trixiepup64_Wayland-{V}\.iso", "trixie"),
    _Rule("tinycore", rf"(?P<f>CorePlus|TinyCorePure64|TinyCore|CorePure64|Core)-{V}\.iso",
          _same("coreplus", "tinycorepure64", "tinycore", "corepure64", "core")),
    _Rule("alpine", rf"alpine-(?P<f>standard|extended|virt|xen)-{V}-x86_64\.iso",
          _same("standard", "extended", "virt", "xen")),
    # The rolling line is numbered by year and month, the stable one like Debian.
    _Rule("sparky", r"sparkylinux-(?P<v>\d{4}\.\d{2})-x86_64-(?P<f>xfce|kde|lxqt|mate|minimalgui"
                    r"|minimalcli|gameover|multimedia|rescue)\.iso",
          lambda m: "rolling-" + m.group("f").lower()),
    _Rule("sparky", rf"sparkylinux-{V}-x86_64-(?P<f>xfce|kde|lxqt|mate|minimalgui|minimalcli)\.iso",
          _same("xfce", "kde", "lxqt", "mate", "minimalgui", "minimalcli")),
    _Rule("antix", rf"antiX-{V}_x64-(?P<f>full|core)\.iso", _same("full", "core")),
    # 6.x leaves Plasma unmarked and calls Trinity -tde; 7.0 spells both out.
    _Rule("q4os", rf"q4os-{V}-x64(?P<f>-plasma|-tde|-trinity|-instcd)?\.r\d+\.iso",
          lambda m: {"": "plasma", "-plasma": "plasma", "-tde": "trinity", "-trinity": "trinity",
                     "-instcd": "instcd"}[(m.group("f") or "").lower()]),
]


def identify(filename: str) -> Optional[IsoIdentity]:
    """What `filename` is, if it is named exactly like an official download."""
    for rule in _RULES:
        found = rule.match(filename)
        if found:
            return found
    return None


def known_flavors() -> Dict[str, set]:
    """Recipe key -> flavor ids these rules can produce. For the tests, which
    hold this table to the registry."""
    out: Dict[str, set] = {}
    for rule in _RULES:
        if isinstance(rule.flavor, str):
            flavors = {rule.flavor}
        elif isinstance(rule.flavor, dict):
            flavors = set(rule.flavor.values())
        else:
            flavors = set()
        out.setdefault(rule.key, set()).update(flavors)
    return out
