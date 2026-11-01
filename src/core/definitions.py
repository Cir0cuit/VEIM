"""Where the catalog comes from.

The recipes that find each distribution's current release, the catalog they
make up and the rules that recognise their images by filename are not part of
VEIM. They live in Cir0cuit/VEIM-definitions, which publishes them as a
release of their own whenever a change passes its tests. A scraper a mirror
has broken is fixed there, and reaches users without a VEIM release.

At every start, start() asks for the latest release's manifest - a few hundred
bytes. Only when it names definitions newer than any VEIM already has is the
archive fetched, checked against the manifest's SHA-256 and unpacked into the
user's data directory. That runs on a thread from the first line of main();
the catalog is first needed after a drive has been picked, by which time the
check has normally long finished. A check still running then is given a moment
and otherwise left to finish for the next start.

get() loads the newest definitions that import cleanly: downloaded ones, or
the copy that ships inside VEIM, which is always there to fall back on. A
download that fails to load is recorded and not tried again by this VEIM.
The manifest is the authority on what is current: downloaded definitions newer
than the published ones were withdrawn, and are not used.

A source checkout uses its own definitions/ submodule and downloads nothing,
so an edit there is what runs. Without the submodule it downloads like an
installed build.

What a download is trusted on: it comes over verified HTTPS from this one
repository's releases, and must match the SHA-256 its manifest gives. Nothing
signs it separately, so whoever can publish there can run code in every VEIM;
that repository's main branch and release rights are guarded accordingly.
"""
import hashlib
import importlib
import importlib.util
import io
import json
import os
import re
import shutil
import sys
import tempfile
import threading
import time
import zipfile
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

import requests

from src import __version__
from src.core import paths
from src.core.logger import log
from src.core.recipe_base import IsoIdentity, is_older, version_key

# The contract version: src/core/recipe_base.py as it stands. Definitions
# declare the one they are written against, and a release's manifest is named
# for it, so a VEIM only ever reads the manifest for the API it speaks.
API = 1

REPO = "Cir0cuit/VEIM-definitions"
MANIFEST_URL = f"https://github.com/{REPO}/releases/latest/download/manifest-v{API}.json"
# Composed here from a version the manifest gives, never taken from it.
ARCHIVE_URL = "https://github.com/" + REPO + "/releases/download/{version}/definitions.zip"

PACKAGE = "veim_definitions"
VERSION_FILE = "VERSION"
# Publish time, UTC: 2026.11.01.183005. The same string names the release,
# its tag and its directory in the cache.
VERSION_PATTERN = re.compile(r"\d{4}\.\d{2}\.\d{2}\.\d{6}")
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
APP_VERSION_PATTERN = re.compile(r"\d+\.\d+\.\d+")
REQUIRED_MODULES = ("__init__.py", "registry.py", "iso_identity.py")

# Everything in an archive is source or a logo; nothing else is unpacked.
MEMBER_PATTERN = re.compile(PACKAGE + r"/(?:[a-z0-9_]+/)*[A-Za-z0-9_][A-Za-z0-9_.-]*\.(?:py|png)")
MAX_MEMBERS = 500
MAX_MANIFEST_BYTES = 64 * 1024
MAX_ARCHIVE_BYTES = 5 * 1024 * 1024
MAX_UNPACKED_BYTES = 20 * 1024 * 1024

TIMEOUT = (5, 10)          # connect, and each read
SYNC_DEADLINE = 30.0       # the whole check, tested between reads
SYNC_WAIT = 3.0            # what get() gives a check still running
STATE_FILE = "definitions.json"
STAGING_PREFIX = ".incoming-"

DOWNLOADED = "downloaded"
BUNDLED = "bundled"


@dataclass(frozen=True)
class Definitions:
    version: str
    source: str                   # DOWNLOADED or BUNDLED
    root: str                     # the directory holding veim_definitions/
    registry: object              # veim_definitions.registry.RecipeRegistry
    category_order: List[str]
    identify: Callable[[str], Optional[IsoIdentity]]
    known_flavors: Callable[[], Dict[str, set]]
    moved_flavors: Dict[Tuple[str, str], str] = field(default_factory=dict)

    @property
    def icon_dir(self) -> str:
        return os.path.join(self.root, PACKAGE, "icons")


class UnusableDefinitions(Exception):
    """Definitions that cannot be used, for a reason of their own making."""


# --- where definitions are -------------------------------------------------

def bundled_root() -> str:
    """The copy VEIM ships: the definitions/ submodule, or its frozen copy."""
    return os.path.join(paths.resource_dir(), "definitions")


def cache_root() -> str:
    return os.path.join(paths.user_data_dir(), "definitions")


def _complete(root: str) -> bool:
    return all(os.path.isfile(os.path.join(root, PACKAGE, name)) for name in REQUIRED_MODULES)


def downloads_enabled() -> bool:
    """An installed build downloads; a checkout with its submodule does not."""
    return paths.is_frozen() or not _complete(bundled_root())


def read_version(root: str) -> str:
    """The version a copy of the definitions carries, or "0" for none (a checkout)."""
    try:
        with open(os.path.join(root, VERSION_FILE), encoding="utf-8") as handle:
            version = handle.read().strip()
    except OSError:
        return "0"
    return version if VERSION_PATTERN.fullmatch(version) else "0"


def _newer(a: str, b: str) -> bool:
    return version_key(a) > version_key(b)


def _cached() -> List[Tuple[str, str]]:
    """(version, root) of each complete download, newest first."""
    try:
        names = os.listdir(cache_root())
    except OSError:
        return []
    found = [(name, os.path.join(cache_root(), name)) for name in names
             if VERSION_PATTERN.fullmatch(name)]
    found = [(v, root) for v, root in found if _complete(root) and read_version(root) == v]
    return sorted(found, key=lambda c: version_key(c[0]), reverse=True)


# --- what has been learnt --------------------------------------------------

def _read_state() -> dict:
    try:
        with open(paths.state_path(STATE_FILE), encoding="utf-8") as handle:
            state = json.load(handle)
        return state if isinstance(state, dict) else {}
    except Exception:
        return {}


# The check's thread and the loading one both update the state file.
_state_lock = threading.Lock()


def _write_state(state: dict) -> None:
    path = paths.state_path(STATE_FILE)
    try:
        # Swapped in whole: a reader never sees half a file.
        with open(path + ".tmp", "w", encoding="utf-8") as handle:
            json.dump(state, handle)
        os.replace(path + ".tmp", path)
    except OSError as e:
        log.debug(f"Could not record the definitions state: {e}")


def _update_state(key: str, update: Callable[[object], object]) -> None:
    with _state_lock:
        state = _read_state()
        state[key] = update(state.get(key))
        _write_state(state)


def _is_bad(version: str, state: dict) -> bool:
    """Failed to load in this VEIM. Another VEIM may manage, so it is asked again."""
    bad = state.get("bad")
    return isinstance(bad, dict) and bad.get(version) == __version__


def _mark_bad(version: str) -> None:
    def add(bad):
        bad = bad if isinstance(bad, dict) else {}
        bad[version] = __version__
        return bad
    _update_state("bad", add)


def _published(state: dict) -> str:
    published = state.get("published", "")
    return published if isinstance(published, str) and VERSION_PATTERN.fullmatch(published) else ""


def _set_aside(version: str, state: dict) -> bool:
    """Failed to load here, or withdrawn: newer than what is now published."""
    published = _published(state)
    return _is_bad(version, state) or bool(published and _newer(version, published))


def _usable_downloads(state: dict) -> List[Tuple[str, str]]:
    """Downloads this VEIM may load."""
    return [(v, root) for v, root in _cached() if not _set_aside(v, state)]


# --- the check -------------------------------------------------------------

class _Deadline:
    def __init__(self, seconds: float):
        self.end = time.monotonic() + seconds

    def check(self):
        if time.monotonic() > self.end:
            raise TimeoutError(f"took longer than {SYNC_DEADLINE:.0f} s")


def _fetch(url: str, limit: int, deadline: _Deadline) -> bytes:
    headers = {"User-Agent": f"veim/{__version__}"}
    with requests.get(url, headers=headers, timeout=TIMEOUT, stream=True) as response:
        response.raise_for_status()
        body = bytearray()
        # Small reads, so the deadline is looked at often on a slow link.
        for chunk in response.iter_content(4096):
            body += chunk
            if len(body) > limit:
                raise ValueError(f"{url} is larger than {limit} bytes")
            deadline.check()
    return bytes(body)


def parse_manifest(raw: bytes) -> dict:
    """The manifest's fields, checked: anything off and the whole thing is refused."""
    manifest = json.loads(raw.decode("utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("the manifest is not an object")
    api, version = manifest.get("api"), manifest.get("version")
    sha256, min_app = manifest.get("sha256"), manifest.get("min_app")
    if type(api) is not int or api != API:
        raise ValueError(f"the manifest is for API {api!r}, VEIM speaks {API}")
    if not isinstance(version, str) or not VERSION_PATTERN.fullmatch(version):
        raise ValueError(f"the manifest's version {version!r} is malformed")
    if not isinstance(sha256, str) or not SHA256_PATTERN.fullmatch(sha256):
        raise ValueError("the manifest's sha256 is malformed")
    if not isinstance(min_app, str) or not APP_VERSION_PATTERN.fullmatch(min_app):
        raise ValueError(f"the manifest's min_app {min_app!r} is malformed")
    return {"version": version, "sha256": sha256, "min_app": min_app}


def unpack(archive: bytes, version: str, destination: str) -> None:
    """Unpack an archive into `destination`, refusing it whole if any part is
    not what definitions are made of."""
    with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
        members = [m for m in bundle.infolist() if not m.is_dir()]
        if len(members) > MAX_MEMBERS:
            raise ValueError(f"the archive holds {len(members)} files")
        if sum(m.file_size for m in members) > MAX_UNPACKED_BYTES:
            raise ValueError("the archive unpacks to more than "
                             f"{MAX_UNPACKED_BYTES // (1024 * 1024)} MB")
        for member in members:
            if not MEMBER_PATTERN.fullmatch(member.filename):
                raise ValueError(f"the archive holds {member.filename!r}")
        for member in members:
            target = os.path.join(destination, *member.filename.split("/"))
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with bundle.open(member) as source, open(target, "xb") as out:
                shutil.copyfileobj(source, out)
    if not _complete(destination):
        raise ValueError("the archive is missing part of the package")
    with open(os.path.join(destination, VERSION_FILE), "w", encoding="utf-8") as handle:
        handle.write(version)


def _install(archive: bytes, version: str) -> None:
    os.makedirs(cache_root(), exist_ok=True)
    final = os.path.join(cache_root(), version)
    staging = tempfile.mkdtemp(prefix=STAGING_PREFIX, dir=cache_root())
    try:
        unpack(archive, version, staging)
        for attempt in range(5):
            if _complete(final) and read_version(final) == version:
                return                      # another VEIM got there first
            try:
                if os.path.isdir(final):
                    shutil.rmtree(final)    # a remnant, never a loaded copy
                os.replace(staging, final)
                return
            except PermissionError:
                # A virus scanner holding the files it has just been shown.
                time.sleep(0.2 * (attempt + 1))
        raise PermissionError(f"could not move the definitions into {final}")
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def sync() -> Optional[str]:
    """Install the published definitions if they are newer than what VEIM has.

    The version installed, or None. Never raises: no connection, a captive
    portal or a malformed release all leave VEIM with what it had.
    """
    try:
        return _sync(_Deadline(SYNC_DEADLINE))
    except Exception as e:
        log.info(f"Definitions not updated: {e}")
        return None


def _sync(deadline: _Deadline) -> Optional[str]:
    manifest = parse_manifest(_fetch(MANIFEST_URL, MAX_MANIFEST_BYTES, deadline))
    version = manifest["version"]
    _update_state("published", lambda _: version)
    state = _read_state()
    if is_older(__version__, manifest["min_app"]):
        log.info(f"Definitions {version} need VEIM {manifest['min_app']} or newer; "
                 f"this is {__version__}")
        return None
    have = max([read_version(bundled_root())] + [v for v, _ in _usable_downloads(state)],
               key=version_key)
    if not _newer(version, have) or _is_bad(version, state):
        log.debug(f"Definitions {have} are current (published: {version})")
        return None
    archive = _fetch(ARCHIVE_URL.format(version=version), MAX_ARCHIVE_BYTES, deadline)
    if hashlib.sha256(archive).hexdigest() != manifest["sha256"]:
        raise ValueError(f"definitions {version} do not match their published checksum")
    _install(archive, version)
    log.info(f"Definitions {version} downloaded")
    return version


# --- loading ---------------------------------------------------------------

def _forget() -> None:
    for name in [n for n in sys.modules if n == PACKAGE or n.startswith(PACKAGE + ".")]:
        del sys.modules[name]


def import_definitions(root: str, version: str, source: str) -> Definitions:
    """Import the package under `root` and take from it what VEIM uses.

    Imported by location rather than through sys.path, so that the copy
    chosen is the copy that runs.
    """
    _forget()
    importlib.invalidate_caches()
    package_dir = os.path.join(root, PACKAGE)
    spec = importlib.util.spec_from_file_location(
        PACKAGE, os.path.join(package_dir, "__init__.py"),
        submodule_search_locations=[package_dir])
    module = importlib.util.module_from_spec(spec)
    sys.modules[PACKAGE] = module
    try:
        spec.loader.exec_module(module)
        if getattr(module, "API", None) != API:
            raise UnusableDefinitions(f"written for API {getattr(module, 'API', None)!r}, "
                                      f"VEIM speaks {API}")
        min_app = getattr(module, "MIN_APP", "0.0.0")
        if is_older(__version__, min_app):
            raise UnusableDefinitions(f"need VEIM {min_app} or newer")
        registry_module = importlib.import_module(f"{PACKAGE}.registry")
        identity_module = importlib.import_module(f"{PACKAGE}.iso_identity")
        registry = registry_module.registry
        if not registry.get_all_recipes():
            raise UnusableDefinitions("the catalog is empty")
        return Definitions(
            version=version, source=source, root=root, registry=registry,
            category_order=list(registry_module.CATEGORY_ORDER),
            identify=identity_module.identify,
            known_flavors=identity_module.known_flavors,
            moved_flavors=dict(registry_module.MOVED_FLAVORS))
    except Exception:
        _forget()
        raise


def _prune(keep: str) -> None:
    """Remove downloads that will not be loaded again: everything older than
    the one in use, anything withdrawn or failed, and abandoned unpacking.
    Never the one in use, nor anything newer that may yet be used: a check
    still running may have just put it there."""
    state = _read_state()
    keep_version = read_version(keep)
    try:
        names = os.listdir(cache_root())
    except OSError:
        return
    for name in names:
        root = os.path.join(cache_root(), name)
        if root == keep:
            continue
        if name.startswith(STAGING_PREFIX):
            try:
                stale = time.time() - os.path.getmtime(root) > 3600
            except OSError:
                stale = False
            if stale:
                shutil.rmtree(root, ignore_errors=True)
        elif not VERSION_PATTERN.fullmatch(name):
            continue
        elif not _newer(name, keep_version) or _set_aside(name, state):
            # Its VERSION first: a half-deleted copy is then never a candidate.
            try:
                os.remove(os.path.join(root, VERSION_FILE))
            except OSError:
                pass
            shutil.rmtree(root, ignore_errors=True)


def _load() -> Definitions:
    candidates = []
    if downloads_enabled():
        candidates += [(v, root, DOWNLOADED) for v, root in _usable_downloads(_read_state())]
    if _complete(bundled_root()):
        candidates.append((read_version(bundled_root()), bundled_root(), BUNDLED))
    # Newest first; the bundled copy wins a tie, needing nothing from disk.
    candidates.sort(key=lambda c: (version_key(c[0]), c[2] == BUNDLED), reverse=True)
    for version, root, source in candidates:
        try:
            loaded = import_definitions(root, version, source)
        except OSError as e:
            # The files, not the code: gone or locked. Not held against it.
            log.error(f"Definitions {version} ({source}) could not be read: {e}")
            continue
        except Exception as e:
            log.exception(f"Definitions {version} ({source}) failed to load: {e}")
            if source == DOWNLOADED:
                _mark_bad(version)
            continue
        log.info(f"Definitions {version} ({source}), "
                 f"{len(loaded.registry.get_all_recipes())} catalog entries")
        if downloads_enabled():
            _prune(root)
        return loaded
    if not paths.is_frozen() and not _complete(bundled_root()):
        raise RuntimeError("No definitions: run `git submodule update --init` in the VEIM "
                           "checkout, or connect to the internet to download them")
    raise RuntimeError("No usable definitions; reinstall VEIM")


_lock = threading.Lock()
_thread: Optional[threading.Thread] = None
_loaded: Optional[Definitions] = None


def start() -> None:
    """Begin the check for newer definitions, unless this is a checkout."""
    global _thread
    if _thread is None and downloads_enabled():
        _thread = threading.Thread(target=sync, name="definitions-check", daemon=True)
        _thread.start()


def get() -> Definitions:
    """The definitions in use, loaded on first call."""
    global _loaded
    with _lock:
        if _loaded is None:
            if _thread is not None:
                _thread.join(SYNC_WAIT)
            _loaded = _load()
        return _loaded


def loaded() -> Optional[Definitions]:
    """The definitions in use if already loaded, without loading them."""
    return _loaded


def registry():
    """The catalog: veim_definitions.registry.RecipeRegistry."""
    return get().registry


def identify(filename: str) -> Optional[IsoIdentity]:
    """Which official download `filename` is, by the definitions' rules."""
    return get().identify(filename)
