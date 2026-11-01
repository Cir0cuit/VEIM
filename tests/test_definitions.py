"""The definitions: checked for at every start, downloaded when newer, loaded
newest-first with the bundled copy always to fall back on."""
import hashlib
import io
import json
import os
import shutil
import zipfile

import pytest
import requests

from src import __version__
from src.core import definitions, paths

SUBMODULE = os.path.join(paths.resource_dir(), "definitions")
PACKAGE_DIR = os.path.join(SUBMODULE, definitions.PACKAGE)

BUNDLED = "2026.01.01.000000"
NEWER = "2026.06.01.120000"
NEWEST = "2026.09.01.120000"


def _package_files():
    for dirpath, dirnames, filenames in os.walk(PACKAGE_DIR):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for name in filenames:
            if name.endswith((".py", ".png")):
                full = os.path.join(dirpath, name)
                yield full, os.path.relpath(full, SUBMODULE).replace(os.sep, "/")


def build_archive(extra=None, drop=(), patch=None) -> bytes:
    """definitions.zip as the definitions CI publishes it, from the submodule."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as bundle:
        for full, arcname in _package_files():
            if arcname in drop:
                continue
            with open(full, "rb") as handle:
                data = handle.read()
            if patch and arcname in patch:
                data = patch[arcname](data)
            bundle.writestr(arcname, data)
        for arcname, data in (extra or {}).items():
            bundle.writestr(arcname, data)
    return buf.getvalue()


def manifest(version, archive, **overrides) -> bytes:
    data = {"api": definitions.API, "version": version,
            "sha256": hashlib.sha256(archive).hexdigest(), "min_app": "1.3.0"}
    data.update(overrides)
    return json.dumps(data).encode()


class FakeResponse:
    def __init__(self, body: bytes, status=200):
        self.body, self.status_code = body, status

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def iter_content(self, size):
        for i in range(0, len(self.body), size):
            yield self.body[i:i + size]


class FakeGitHub:
    """The definitions repository's releases, as requests.get sees them."""

    def __init__(self):
        self.files = {}
        self.requested = []

    def publish(self, version, archive, **overrides):
        self.files[definitions.MANIFEST_URL] = manifest(version, archive, **overrides)
        self.files[definitions.ARCHIVE_URL.format(version=version)] = archive

    def get(self, url, **kwargs):
        self.requested.append(url)
        if url not in self.files:
            return FakeResponse(b"Not Found", 404)
        return FakeResponse(self.files[url])


@pytest.fixture
def env(tmp_path, monkeypatch):
    """An installed VEIM: a bundled copy of the definitions inside it, a user
    data directory, and GitHub. The real definitions are restored after."""
    bundled = tmp_path / "bundle" / "definitions"
    shutil.copytree(PACKAGE_DIR, bundled / definitions.PACKAGE,
                    ignore=shutil.ignore_patterns("__pycache__"))
    (bundled / definitions.VERSION_FILE).write_text(BUNDLED)
    user = tmp_path / "user"
    user.mkdir()
    github = FakeGitHub()

    monkeypatch.setattr(definitions, "bundled_root", lambda: str(bundled))
    monkeypatch.setattr(paths, "user_data_dir", lambda: str(user))
    monkeypatch.setattr(paths, "state_path", lambda name: str(user / name))
    monkeypatch.setattr(paths, "is_frozen", lambda: True)
    monkeypatch.setattr(definitions.requests, "get", github.get)
    monkeypatch.setattr(definitions, "_loaded", None)
    monkeypatch.setattr(definitions, "_thread", None)
    yield github
    definitions._forget()


def _state():
    with open(paths.state_path(definitions.STATE_FILE), encoding="utf-8") as handle:
        return json.load(handle)


# ---------------------------------------------------------------- the check

def test_newer_published_definitions_are_downloaded_and_used(env):
    env.publish(NEWER, build_archive())

    assert definitions.sync() == NEWER
    loaded = definitions.get()

    assert (loaded.version, loaded.source) == (NEWER, definitions.DOWNLOADED)
    assert loaded.registry.get_recipe("ubuntu") is not None
    assert loaded.identify("ubuntu-24.04.2-desktop-amd64.iso").key == "ubuntu"
    assert os.path.isfile(os.path.join(definitions.cache_root(), NEWER, "VERSION"))


def test_definitions_already_held_are_not_downloaded_again(env):
    env.publish(NEWER, build_archive())
    definitions.sync()
    env.requested.clear()

    assert definitions.sync() is None
    assert env.requested == [definitions.MANIFEST_URL], "only the manifest is asked for"


def test_published_definitions_no_newer_than_the_bundled_copy_are_not_fetched(env):
    env.publish(BUNDLED, build_archive())

    assert definitions.sync() is None
    assert env.requested == [definitions.MANIFEST_URL]
    assert definitions.get().source == definitions.BUNDLED


@pytest.mark.parametrize("failure", ["offline", "missing", "captive-portal", "garbled"])
def test_no_answer_leaves_the_bundled_copy_in_use(env, monkeypatch, failure):
    if failure == "offline":
        def offline(url, **kwargs):
            raise requests.ConnectionError("no route to host")
        monkeypatch.setattr(definitions.requests, "get", offline)
    elif failure == "captive-portal":
        env.files[definitions.MANIFEST_URL] = b"<html>Sign in to the hotel Wi-Fi</html>"
    elif failure == "garbled":
        env.files[definitions.MANIFEST_URL] = b'{"api": 1, "version": "2026.6.1"'

    assert definitions.sync() is None
    assert definitions.get().source == definitions.BUNDLED


def test_an_archive_that_does_not_match_its_checksum_is_not_installed(env):
    env.publish(NEWER, build_archive())
    env.files[definitions.ARCHIVE_URL.format(version=NEWER)] = build_archive(
        extra={"veim_definitions/evil.py": b"raise SystemExit"})

    assert definitions.sync() is None
    assert not definitions._cached()
    assert definitions.get().source == definitions.BUNDLED


def test_definitions_for_a_newer_veim_are_left_alone(env):
    env.publish(NEWER, build_archive(), min_app="99.0.0")

    assert definitions.sync() is None
    assert env.requested == [definitions.MANIFEST_URL]


def test_a_check_cannot_run_past_its_deadline(env, monkeypatch):
    env.publish(NEWER, build_archive())
    monkeypatch.setattr(definitions, "SYNC_DEADLINE", -1)

    assert definitions.sync() is None
    assert not definitions._cached()


@pytest.mark.parametrize("field, value", [
    ("api", 2), ("api", True), ("api", "1"),
    ("version", "2026.6.1"), ("version", "../../evil"), ("version", "2026.06.01.120000/x"),
    ("sha256", "ABC"), ("sha256", "g" * 64),
    ("min_app", "1.3"), ("min_app", None),
])
def test_a_malformed_manifest_is_refused_whole(field, value):
    archive = build_archive()
    raw = json.loads(manifest(NEWER, archive))
    raw[field] = value
    with pytest.raises(ValueError):
        definitions.parse_manifest(json.dumps(raw).encode())


@pytest.mark.parametrize("name", [
    "../evil.py", "veim_definitions/../../evil.py", "/etc/evil.py", "evil.py",
    "veim_definitions/C:evil.py", "veim_definitions/native.pyd", "veim_definitions/lib.so",
    "veim_definitions/recipes/run.sh",
])
def test_an_archive_with_anything_but_source_and_logos_is_refused(tmp_path, name):
    with pytest.raises(ValueError):
        definitions.unpack(build_archive(extra={name: b"x"}), NEWER, str(tmp_path))
    assert not os.path.exists(tmp_path / "evil.py")


def test_an_archive_missing_part_of_the_package_is_refused(tmp_path):
    with pytest.raises(ValueError, match="missing"):
        definitions.unpack(build_archive(drop={"veim_definitions/registry.py"}), NEWER,
                           str(tmp_path))


def test_an_archive_that_unpacks_to_too_much_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(definitions, "MAX_UNPACKED_BYTES", 1024)
    with pytest.raises(ValueError, match="unpacks to more"):
        definitions.unpack(build_archive(), NEWER, str(tmp_path))
    assert os.listdir(tmp_path) == []


# ---------------------------------------------------------------- loading

def test_definitions_that_fail_to_import_are_not_used_or_tried_again(env):
    broken = build_archive(patch={"veim_definitions/registry.py": lambda b: b + b"\n)\n"})
    env.publish(NEWER, broken)
    assert definitions.sync() == NEWER

    loaded = definitions.get()

    assert loaded.source == definitions.BUNDLED
    assert _state()["bad"] == {NEWER: __version__}
    assert not os.path.exists(os.path.join(definitions.cache_root(), NEWER)), "pruned"
    env.requested.clear()
    assert definitions.sync() is None
    assert env.requested == [definitions.MANIFEST_URL], "not downloaded again"


def test_definitions_for_another_api_are_not_used(env):
    env.publish(NEWER, build_archive(
        patch={"veim_definitions/__init__.py": lambda b: b.replace(b"API = 1", b"API = 2")}))
    definitions.sync()

    assert definitions.get().source == definitions.BUNDLED


def test_a_veim_update_with_newer_bundled_definitions_uses_them(env, monkeypatch, tmp_path):
    env.publish(NEWER, build_archive())
    definitions.sync()
    bundled = tmp_path / "bundle" / "definitions"
    (bundled / definitions.VERSION_FILE).write_text(NEWEST)

    loaded = definitions.get()

    assert (loaded.version, loaded.source) == (NEWEST, definitions.BUNDLED)
    assert not os.path.exists(os.path.join(definitions.cache_root(), NEWER)), \
        "an older download is pruned"


def test_a_withdrawn_release_is_no_longer_used(env):
    """Deleting a bad release rolls clients back: the manifest names an older
    version than one already downloaded, and that download is set aside."""
    env.publish(NEWEST, build_archive())
    definitions.sync()
    env.publish(NEWER, build_archive())

    assert definitions.sync() == NEWER
    loaded = definitions.get()

    assert loaded.version == NEWER
    assert not os.path.exists(os.path.join(definitions.cache_root(), NEWEST))


def test_a_leftover_partial_directory_is_never_loaded(env):
    os.makedirs(os.path.join(definitions.cache_root(), NEWEST, definitions.PACKAGE))
    os.makedirs(os.path.join(definitions.cache_root(), ".incoming-abc", definitions.PACKAGE))

    assert definitions.get().source == definitions.BUNDLED


def test_a_checkout_uses_its_own_submodule_and_downloads_nothing(monkeypatch):
    monkeypatch.setattr(definitions, "_thread", None)
    monkeypatch.setattr(definitions.requests, "get", lambda *a, **k: pytest.fail("network"))

    definitions.start()

    assert definitions._thread is None
    assert not definitions.downloads_enabled()
    assert definitions.get().root == SUBMODULE


def test_a_checkout_without_its_submodule_downloads(env, monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "is_frozen", lambda: False)
    monkeypatch.setattr(definitions, "bundled_root", lambda: str(tmp_path / "empty"))
    env.publish(NEWER, build_archive())

    assert definitions.downloads_enabled()
    definitions.sync()
    assert definitions.get().source == definitions.DOWNLOADED


def test_no_definitions_at_all_says_what_to_do(env, monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "is_frozen", lambda: False)
    monkeypatch.setattr(definitions, "bundled_root", lambda: str(tmp_path / "empty"))

    with pytest.raises(RuntimeError, match="git submodule update --init"):
        definitions.get()


def test_the_check_runs_on_a_thread_and_loading_waits_for_it(env):
    env.publish(NEWER, build_archive())

    definitions.start()

    assert definitions.get().version == NEWER


def test_the_app_never_imports_the_definitions_by_name():
    """A static import would put them inside the frozen app's archive, where
    the copy shipped would shadow every download."""
    root = paths.resource_dir()
    for folder in ("src", "tools"):
        for dirpath, _, filenames in os.walk(os.path.join(root, folder)):
            for name in filenames:
                if name.endswith(".py"):
                    with open(os.path.join(dirpath, name), encoding="utf-8") as handle:
                        text = handle.read()
                    assert "import veim_definitions" not in text, name
                    assert "from veim_definitions" not in text, name


def test_a_state_file_in_an_unexpected_shape_is_not_fatal(env):
    env.publish(NEWER, build_archive())
    definitions.sync()
    with open(paths.state_path(definitions.STATE_FILE), "w", encoding="utf-8") as handle:
        json.dump({"bad": ["x"], "published": 5}, handle)

    assert definitions.get().version == NEWER


def test_pruning_spares_a_newer_download_a_late_check_has_just_installed(env):
    """Loading gives a check a few seconds; one that finishes later installs
    beside what was loaded, and that must survive until the next start."""
    env.publish(NEWER, build_archive())
    definitions.sync()
    definitions._prune(definitions.bundled_root())

    assert [v for v, _ in definitions._cached()] == [NEWER]
