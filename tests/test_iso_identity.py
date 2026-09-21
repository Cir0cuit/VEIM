"""Recognising official downloads by name.

Adoption rests on this being strict: a name that is merely similar must come
back as nothing, because the alternative is offering to overwrite somebody's
customised image with the stock one.
"""
import pytest

from src.core.iso_identity import identify, known_flavors
from src.recipes.registry import registry

# (filename, key, flavor, version) exactly as the recipes reported them on
# 2026-09-21. tests/test_recipes_live.py holds the same promise against the
# live mirrors; this keeps it without a network.
OFFICIAL = [
    ("Fedora-KDE-Desktop-Live-44-1.7.x86_64.iso", "fedora", "kde", "44"),
    ("Fedora-Server-dvd-x86_64-44-1.7.iso", "fedora", "server", "44"),
    ("ubuntu-26.04.1-desktop-amd64.iso", "ubuntu", "desktop", "26.04.1"),
    ("ubuntu-26.04.1-live-server-amd64.iso", "ubuntu", "server", "26.04.1"),
    ("kubuntu-26.04.1-desktop-amd64.iso", "ubuntu", "kubuntu", "26.04.1"),
    ("ubuntu-mate-25.10-desktop-amd64.iso", "ubuntu", "mate", "25.10"),
    ("linuxmint-22.3-cinnamon-64bit.iso", "mint", "cinnamon", "22.3"),
    ("debian-13.7.0-amd64-netinst.iso", "debian", "netinst", "13.7.0"),
    ("debian-live-13.7.0-amd64-kde.iso", "debian", "kde", "13.7.0"),
    ("pop-os_22.04_amd64_nvidia_58.iso", "popos", "nvidia", "22.04 (Build 58)"),
    ("Zorin-OS-18.1-Core-64-bit.iso", "zorin", "core", "18.1"),
    ("Zorin-OS-18-Core-64-bit-r3.iso", "zorin", "core", "18"),
    ("neon-user-desktop-20260903-0454.iso", "kde_neon", "user", "20260903-0454"),
    ("openSUSE-Leap-15.6-DVD-x86_64-Current.iso", "opensuse", "leap-dvd", "15.6"),
    ("elementaryos-8.1-stable-amd64.20260219.iso", "elementary", "stable", "8.1"),
    ("TUXEDO-OS-202609161651.iso", "tuxedo", "standard", "202609161651"),
    ("Mageia-10-x86_64.iso", "mageia", "classic-dvd", "10"),
    ("Mageia-10-Live-Plasma-x86_64.iso", "mageia", "live-plasma", "10"),
    ("MX-25.3_Xfce_x64.iso", "mxlinux", "xfce", "25.3"),
    ("MX-25.3_Xfce_ahs_x64.iso", "mxlinux", "xfce-ahs", "25.3"),
    ("devuan_excalibur_6.1.1_amd64_netinstall.iso", "devuan", "netinstall", "6.1.1"),
    ("slackware64-15.0-install-dvd.iso", "slackware", "install-dvd", "15.0"),
    ("archlinux-2026.09.01-x86_64.iso", "arch", "standard", "2026.09.01"),
    ("manjaro-kde-26.1.2-260910-linux71.iso", "manjaro", "plasma", "26.1.2"),
    ("EndeavourOS_Titan-Nova-2026.08.15.iso", "endeavour", "standard", "2026.08.15"),
    ("artix-base-runit-20260813-x86_64.iso", "artix", "base-runit", "20260813"),
    ("void-live-x86_64-20250202-xfce.iso", "void", "xfce", "20250202"),
    ("void-live-x86_64-musl-20250202-base.iso", "void", "musl-base", "20250202"),
    ("install-amd64-minimal-20260913T163055Z.iso", "gentoo", "minimal", "20260913"),
    ("livegui-amd64-20260913T163055Z.iso", "gentoo", "livegui", "20260913"),
    ("omarchy-4.0.4.iso", "omarchy", "standard", "4.0.4"),
    ("garuda-dr460nized-gaming-linux-garuda-260819.iso", "garuda", "dr460nized-gaming", "260819"),
    ("garuda-xfce-linux-lts-260819.iso", "garuda", "xfce", "260819"),
    ("cachyos-handheld-linux-260628.iso", "cachyos", "handheld", "260628"),
    ("Nobara-44-Steam-HTPC-2026-09-02.iso", "nobara", "steam-htpc", "44 (2026-09-02)"),
    ("PikaOS-Nest-NVIDIA-KDE-4.0-amd64-v3-26.08.20-4.iso", "pikaos", "nvidia-kde", "4.0 (26.08.20)"),
    ("kali-linux-2026.2-installer-amd64.iso", "kali", "installer", "2026.2"),
    ("kali-linux-2026.2-installer-purple-amd64.iso", "kali", "purple", "2026.2"),
    ("Parrot-security-7.3_amd64.iso", "parrot", "security", "7.3"),
    ("tails-amd64-7.13.iso", "tails", "standard", "7.13"),
    ("HackerOS-V5.0.iso", "hackeros", "official", "5.0"),
    ("HackerOS-V4.9-Cybersecurity.iso", "hackeros", "cybersecurity", "4.9"),
    ("Qubes-R4.3.1-x86_64.iso", "qubes", "installer", "4.3.1"),
    ("clonezilla-live-20260913-resolute-amd64.iso", "clonezilla", "alternative", "20260913-resolute"),
    ("clonezilla-live-3.3.3-37-amd64.iso", "clonezilla", "stable", "3.3.3-37"),
    ("systemrescue-13.02-amd64.iso", "systemrescue", "standard", "13.02"),
    ("grml-small-2026.09-amd64.iso", "grml", "small", "2026.09"),
    ("memtest86plus-8.10-x86_64.grub.iso", "memtest", "grub", "8.10"),
    ("proxmox-ve_9.2-1.iso", "proxmox", "installer", "9.2-1"),
    ("gparted-live-1.8.1-6-amd64.iso", "gparted", "standard", "1.8.1-6"),
    ("rescuezilla-2.6.2-64bit.noble.iso", "rescuezilla", "standard", "2.6.2"),
    ("BookwormPup64_10.0.12.iso", "puppy", "bookworm", "10.0.12"),
    ("Trixiepup64_Wayland-11.4.iso", "puppy", "trixie", "11.4"),
    ("CorePure64-15.0.iso", "tinycore", "corepure64", "15.0"),
    ("alpine-extended-3.24.2-x86_64.iso", "alpine", "extended", "3.24.2"),
    ("sparkylinux-8.4-x86_64-minimalcli.iso", "sparky", "minimalcli", "8.4"),
    ("antiX-26_x64-core.iso", "antix", "core", "26"),
    ("q4os-6.9-x64.r1.iso", "q4os", "plasma", "6.9"),
    ("q4os-6.9-x64-tde.r1.iso", "q4os", "trinity", "6.9"),
]

# Not adoptable, each for its own reason.
LEFT_ALONE = [
    "clonezilla-live-galaxybook-20260808.iso",      # customised: no official version in it
    "clonezilla-live-3.3.3-37-amd64-custom.iso",    # official name with something added
    "my-archlinux-2026.09.01-x86_64.iso",
    "ubuntu-26.04.1-desktop-amd64 (1).iso",
    "kali-linux-2026.2-live-amd64.iso",             # real, but no recipe flavor serves it
    "TinyCorePure64-16.2.iso",
    "Win11_25H2_English_x64.iso",
    "HBCD_PE_x64.iso",
    "memtest.iso",
    # Official, but the name is the same for every release.
    "netboot.xyz.iso",
    "bazzite-stable-amd64.iso",
    "openSUSE-Tumbleweed-DVD-x86_64-Current.iso",
    "latest-nixos-minimal-x86_64-linux.iso",
]


@pytest.mark.parametrize("filename,key,flavor,version", OFFICIAL)
def test_official_download_is_recognised(filename, key, flavor, version):
    found = identify(filename)
    assert found is not None, f"{filename} was not recognised"
    assert (found.key, found.flavor_id, found.version) == (key, flavor, version)


@pytest.mark.parametrize("filename", LEFT_ALONE)
def test_anything_else_is_left_alone(filename):
    assert identify(filename) is None


def test_case_of_the_name_does_not_matter():
    """FAT and exFAT keep the case a file was copied with, whatever that was."""
    assert identify("ARCHLINUX-2026.09.01-X86_64.ISO").key == "arch"


def test_every_rule_names_a_flavor_the_catalog_offers():
    """A rule pointing at a flavor that does not exist would adopt an ISO
    that every check then fails on."""
    for key, flavors in known_flavors().items():
        recipe = registry.get_recipe(key)
        assert recipe is not None, f"rule for unknown recipe {key!r}"
        offered = {f.id for f in recipe.get_flavors()}
        assert flavors <= offered, f"{key}: rules name {flavors - offered}, recipe offers {offered}"
