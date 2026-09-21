"""Recognise an ISO the catalog can keep up to date, from its filename alone.

VEIM used to take in every ISO it found and guess what it was from a word in
the name. "clonezilla-live-galaxybook-20260808.iso" - someone's customised
image - became the official Clonezilla with the version "Live", was offered an
update, and would have been overwritten by it. Anything unrecognised became a
row that could never be checked at all.

So this is strict on purpose. A name has to match, in full, the way the project
itself names that download, and it has to carry a version that compares equal
to the one the recipe reports. A renamed, remastered or otherwise unfamiliar
ISO matches nothing and is left alone - never adopted on a guess.

Downloads whose name never changes between releases (openSUSE Tumbleweed's
"-Current", Bazzite's "-stable", netboot.xyz.iso) are deliberately absent:
there is no telling which release such a file holds.
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
    _Rule("fedora", rf"Fedora-(?P<f>Workstation|KDE-Desktop|KDE|Cinnamon|Xfce|Budgie)-Live-(?P<v>\d+)-[\d.]+\.x86_64\.iso",
          {"workstation": "workstation", "kde-desktop": "kde", "kde": "kde",
           "cinnamon": "cinnamon", "xfce": "xfce", "budgie": "budgie"}),
    # Fedora put the architecture before the version until release 42.
    _Rule("fedora", rf"Fedora-(?P<f>Workstation|KDE|Cinnamon|Xfce|Budgie)-Live-x86_64-(?P<v>\d+)-[\d.]+\.iso",
          _same("workstation", "kde", "cinnamon", "xfce", "budgie")),
    _Rule("fedora", rf"Fedora-Server-dvd-x86_64-(?P<v>\d+)-[\d.]+\.iso", "server"),

    _Rule("ubuntu", rf"ubuntu-{V}-desktop-amd64\.iso", "desktop"),
    _Rule("ubuntu", rf"ubuntu-{V}-live-server-amd64\.iso", "server"),
    _Rule("ubuntu", rf"(?P<f>kubuntu|xubuntu|lubuntu)-{V}-desktop-amd64\.iso",
          _same("kubuntu", "xubuntu", "lubuntu")),
    _Rule("ubuntu", rf"ubuntu-(?P<f>mate|budgie)-{V}-desktop-amd64\.iso", _same("mate", "budgie")),

    _Rule("mint", rf"linuxmint-{V}-(?P<f>cinnamon|mate|xfce)-64bit\.iso",
          _same("cinnamon", "mate", "xfce")),

    _Rule("debian", rf"debian-{V}-amd64-netinst\.iso", "netinst"),
    _Rule("debian", rf"debian-live-{V}-amd64-(?P<f>gnome|kde|xfce|standard)\.iso",
          _same("gnome", "kde", "xfce", "standard")),

    _Rule("popos", rf"pop-os_{V}_amd64_(?P<f>intel|nvidia)_(?P<b>\d+)\.iso",
          _same("intel", "nvidia"), version="{v} (Build {b})"),
    # "-r3" is a respin of the same release.
    _Rule("zorin", rf"Zorin-OS-{V}-(?P<f>Core|Education)-64-bit(?:-r\d+)?\.iso",
          _same("core", "education")),
    _Rule("kde_neon", r"neon-user-desktop-(?P<v>\d{8}-\d{4})\.iso", "user"),
    _Rule("opensuse", rf"openSUSE-Leap-{V}-(?P<f>DVD|NET)-x86_64-Current\.iso",
          {"dvd": "leap-dvd", "net": "leap-net"}),
    _Rule("elementary", rf"elementaryos-{V}-stable-amd64\.\d+\.iso", "stable"),
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
    _Rule("endeavour", r"EndeavourOS_[A-Za-z-]+-(?P<v>\d{4}\.\d{2}\.\d{2})\.iso", "standard"),
    _Rule("artix", rf"artix-(?P<f>[a-z]+-(?:openrc|runit))-{DATE8}-x86_64\.iso",
          _same("plasma-openrc", "xfce-openrc", "base-openrc", "base-runit",
                "cinnamon-openrc", "mate-openrc")),
    _Rule("void", rf"void-live-x86_64-(?P<m>musl-)?{DATE8}-(?P<f>base|xfce)\.iso",
          lambda m: ("musl-" if m.group("m") else "") + m.group("f").lower()),
    _Rule("gentoo", rf"install-amd64-minimal-{DATE8}T\d{{6}}Z\.iso", "minimal"),
    _Rule("gentoo", rf"livegui-amd64-{DATE8}T\d{{6}}Z\.iso", "livegui"),
    _Rule("omarchy", rf"omarchy-{V}\.iso", "standard"),

    _Rule("garuda", r"garuda-(?P<f>dr460nized-gaming|dr460nized|gnome|kde-lite|xfce|cinnamon)"
                    r"-linux-[a-z]+-(?P<v>\d{6})\.iso",
          _same("dr460nized-gaming", "dr460nized", "gnome", "kde-lite", "xfce", "cinnamon")),
    _Rule("cachyos", r"cachyos-(?P<f>desktop|handheld)-linux-(?P<v>\d{6})\.iso",
          _same("desktop", "handheld")),
    _Rule("nobara", r"Nobara-(?P<v>\d+)-(?P<f>Official|KDE|GNOME|Steam-HTPC|Steam-Handheld)"
                    r"-(?P<d>\d{4}-\d{2}-\d{2})\.iso",
          _same("official", "kde", "gnome", "steam-htpc", "steam-handheld"),
          version="{v} ({d})"),
    _Rule("pikaos", rf"PikaOS-[A-Za-z]+-(?P<f>NVIDIA-KDE|NVIDIA-GNOME|KDE|GNOME|Hyprland)"
                    rf"-{V}-amd64-v3-(?P<d>[\d.]+)-\d+\.iso",
          _same("nvidia-kde", "nvidia-gnome", "kde", "gnome", "hyprland"),
          version="{v} ({d})"),

    _Rule("kali", r"kali-linux-(?P<v>\d{4}\.\d+[a-z]?)-installer-amd64\.iso", "installer"),
    _Rule("kali", r"kali-linux-(?P<v>\d{4}\.\d+[a-z]?)-installer-purple-amd64\.iso", "purple"),
    _Rule("parrot", rf"Parrot-(?P<f>security|home)-{V}_amd64\.iso", _same("security", "home")),
    _Rule("tails", rf"tails-amd64-{V}\.iso", "standard"),
    _Rule("hackeros", rf"HackerOS-V{V}(?:-(?P<f>LTS|Cybersecurity|Gaming|NVIDIA))?\.iso",
          lambda m: (m.group("f") or "official").lower()),
    _Rule("qubes", rf"Qubes-R{V}-x86_64\.iso", "installer"),

    # The two branches differ only in how they write a version.
    _Rule("clonezilla", r"clonezilla-live-(?P<v>\d{8}-[a-z]+)-amd64\.iso", "alternative"),
    _Rule("clonezilla", r"clonezilla-live-(?P<v>\d+\.\d+\.\d+-\d+)-amd64\.iso", "stable"),
    _Rule("systemrescue", rf"systemrescue-{V}-amd64\.iso", "standard"),
    _Rule("grml", r"grml-(?P<f>full|small)-(?P<v>\d{4}\.\d{2})-amd64\.iso", _same("full", "small")),
    _Rule("memtest", rf"memtest86plus-{V}-x86_64(?P<g>\.grub)?\.iso",
          lambda m: "grub" if m.group("g") else "x86_64"),
    _Rule("proxmox", r"proxmox-ve_(?P<v>\d+\.\d+-\d+)\.iso", "installer"),
    _Rule("gparted", r"gparted-live-(?P<v>\d+(?:\.\d+)*-\d+)-amd64\.iso", "standard"),
    _Rule("rescuezilla", rf"rescuezilla-{V}-64bit\.[a-z]+\.iso", "standard"),

    _Rule("puppy", rf"BookwormPup64_{V}\.iso", "bookworm"),
    _Rule("puppy", rf"fossapup64-{V}\.iso", "fossa"),
    _Rule("puppy", rf"Trixiepup64_Wayland-{V}\.iso", "trixie"),
    _Rule("tinycore", rf"(?P<f>CorePlus|TinyCore|CorePure64)-{V}\.iso",
          _same("coreplus", "tinycore", "corepure64")),
    _Rule("alpine", rf"alpine-(?P<f>standard|extended)-{V}-x86_64\.iso",
          _same("standard", "extended")),
    _Rule("sparky", rf"sparkylinux-{V}-x86_64-(?P<f>xfce|kde|lxqt|mate|minimalgui|minimalcli)\.iso",
          _same("xfce", "kde", "lxqt", "mate", "minimalgui", "minimalcli")),
    _Rule("antix", rf"antiX-{V}_x64-(?P<f>full|core)\.iso", _same("full", "core")),
    _Rule("q4os", rf"q4os-{V}-x64(?P<f>-tde|-instcd)?\.r\d+\.iso",
          lambda m: {"": "plasma", "-tde": "trinity", "-instcd": "instcd"}[(m.group("f") or "").lower()]),
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
