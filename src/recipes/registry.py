from typing import List, Dict, Optional
from src.core.recipe_base import DistroRecipe
from src.recipes.fedora import FedoraRecipe
from src.recipes.ubuntu import UbuntuRecipe
from src.recipes.mint import MintRecipe
from src.recipes.debian import DebianRecipe
from src.recipes.arch import ArchRecipe
from src.recipes.rolling import ManjaroRecipe, EndeavourRecipe, OmarchyRecipe
from src.recipes.security import KaliRecipe, ParrotRecipe
from src.recipes.modern_desktop import PopOSRecipe, KDENeonRecipe, ZorinRecipe
from src.recipes.rescue import (
    ClonezillaRecipe, GPartedRecipe, RescuezillaRecipe, ShredOSRecipe,
    NetbootRecipe, SystemRescueRecipe, MemtestRecipe)
from src.recipes.lightweight import PuppyRecipe, TinyCoreRecipe, AlpineRecipe
from src.recipes.gaming import BazziteRecipe, GarudaRecipe, CachyOSRecipe, NobaraRecipe, PikaOSRecipe
from src.recipes.community_desktop import OpenSUSERecipe, NixOSRecipe, ElementaryRecipe, TuxedoRecipe, MageiaRecipe
from src.recipes.specialized import ArtixRecipe, SparkyRecipe, TailsRecipe, FydeOSRecipe, HackerOSRecipe, AlmaLinuxRecipe
from src.recipes.debian_family import (
    MXLinuxRecipe, AntiXRecipe, DevuanRecipe, Q4OSRecipe, GrmlRecipe)
from src.recipes.independent import VoidRecipe, GentooRecipe, SlackwareRecipe
from src.recipes.enterprise import RockyLinuxRecipe, ProxmoxRecipe, QubesRecipe

# Order is the order the filter chips appear in.
CATEGORY_ORDER = [
    "Beginner Friendly",
    "General Purpose",
    "Rolling Release",
    "Enthusiast",
    "Gaming & Performance",
    "Security & Privacy",
    "Server & Enterprise",
    "Rescue & Diagnostics",
    "Lightweight",
]

CATEGORY_BY_KEY = {
    "ubuntu": "Beginner Friendly",
    "mint": "Beginner Friendly",
    "zorin": "Beginner Friendly",
    "popos": "Beginner Friendly",
    "elementary": "Beginner Friendly",
    "tuxedo": "Beginner Friendly",
    "fydeos": "Beginner Friendly",

    "fedora": "General Purpose",
    "debian": "General Purpose",
    "opensuse": "General Purpose",
    "kde_neon": "General Purpose",
    "mageia": "General Purpose",
    "mxlinux": "General Purpose",

    "arch": "Rolling Release",
    "manjaro": "Rolling Release",
    "endeavour": "Rolling Release",
    "artix": "Rolling Release",
    "omarchy": "Rolling Release",

    "gentoo": "Enthusiast",
    "slackware": "Enthusiast",
    "nixos": "Enthusiast",
    "devuan": "Enthusiast",
    "void": "Enthusiast",

    "bazzite": "Gaming & Performance",
    "cachyos": "Gaming & Performance",
    "garuda": "Gaming & Performance",
    "nobara": "Gaming & Performance",
    "pikaos": "Gaming & Performance",

    "kali": "Security & Privacy",
    "parrot": "Security & Privacy",
    "tails": "Security & Privacy",
    "qubes": "Security & Privacy",
    "hackeros": "Security & Privacy",

    "almalinux": "Server & Enterprise",
    "rocky": "Server & Enterprise",
    "proxmox": "Server & Enterprise",

    "systemrescue": "Rescue & Diagnostics",
    "clonezilla": "Rescue & Diagnostics",
    "gparted": "Rescue & Diagnostics",
    "rescuezilla": "Rescue & Diagnostics",
    "grml": "Rescue & Diagnostics",
    "memtest": "Rescue & Diagnostics",
    "shredos": "Rescue & Diagnostics",
    "netboot": "Rescue & Diagnostics",

    "antix": "Lightweight",
    "puppy": "Lightweight",
    "tinycore": "Lightweight",
    "alpine": "Lightweight",
    "sparky": "Lightweight",
    "q4os": "Lightweight",
}


class RecipeRegistry:
    def __init__(self):
        self._recipes: Dict[str, DistroRecipe] = {}
        self._register_defaults()

    def _register(self, recipe: DistroRecipe):
        if recipe.key not in CATEGORY_BY_KEY:
            raise KeyError(
                f"{recipe.key!r} has no entry in CATEGORY_BY_KEY - add one so it "
                "appears under a filter chip"
            )
        recipe.category = CATEGORY_BY_KEY[recipe.key]
        self._recipes[recipe.key] = recipe

    def _register_defaults(self):
        self._register(FedoraRecipe())
        self._register(UbuntuRecipe())
        self._register(MintRecipe())
        self._register(DebianRecipe())
        self._register(PopOSRecipe())
        self._register(ZorinRecipe())
        self._register(KDENeonRecipe())
        self._register(OpenSUSERecipe())
        self._register(ElementaryRecipe())
        self._register(TuxedoRecipe())
        self._register(MageiaRecipe())
        self._register(AlmaLinuxRecipe())
        self._register(FydeOSRecipe())
        self._register(MXLinuxRecipe())
        self._register(DevuanRecipe())
        self._register(RockyLinuxRecipe())
        self._register(SlackwareRecipe())

        self._register(ArchRecipe())
        self._register(ManjaroRecipe())
        self._register(EndeavourRecipe())
        self._register(ArtixRecipe())
        self._register(NixOSRecipe())
        self._register(VoidRecipe())
        self._register(GentooRecipe())
        self._register(OmarchyRecipe())

        self._register(BazziteRecipe())
        self._register(GarudaRecipe())
        self._register(CachyOSRecipe())
        self._register(NobaraRecipe())
        self._register(PikaOSRecipe())

        self._register(KaliRecipe())
        self._register(ParrotRecipe())
        self._register(TailsRecipe())
        self._register(HackerOSRecipe())
        self._register(QubesRecipe())

        self._register(ClonezillaRecipe())
        self._register(SystemRescueRecipe())
        self._register(GrmlRecipe())
        self._register(MemtestRecipe())
        self._register(ProxmoxRecipe())
        self._register(GPartedRecipe())
        self._register(RescuezillaRecipe())
        self._register(ShredOSRecipe())
        self._register(NetbootRecipe())

        self._register(PuppyRecipe())
        self._register(TinyCoreRecipe())
        self._register(AlpineRecipe())
        self._register(SparkyRecipe())
        self._register(AntiXRecipe())
        self._register(Q4OSRecipe())

    def get_recipe(self, key: str) -> Optional[DistroRecipe]:
        return self._recipes.get(key)

    def get_all_recipes(self) -> List[DistroRecipe]:
        return list(self._recipes.values())

    def get_categories(self) -> List[str]:
        """"All" plus every category that currently has at least one entry."""
        present = {r.category for r in self._recipes.values()}
        return ["All"] + [c for c in CATEGORY_ORDER if c in present]

    def get_by_category(self, category: str) -> List[DistroRecipe]:
        if not category or category == "All":
            return self.get_all_recipes()
        return [r for r in self._recipes.values() if r.category == category]

registry = RecipeRegistry()
