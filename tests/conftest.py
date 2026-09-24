"""Shared test fixtures."""
import os

import pytest

# Qt needs an offscreen platform in headless CI.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def state_file(tmp_path, monkeypatch):
    """Every update-check answer is written here; the next check reads it back."""
    from src.core import app_update
    path = tmp_path / "update_check.json"
    monkeypatch.setattr(app_update.paths, "state_path", lambda _name: str(path))
    return path


@pytest.fixture
def drive_root(tmp_path):
    """An empty throwaway directory standing in for a mounted Ventoy drive."""
    return str(tmp_path)


@pytest.fixture
def managed_dir(drive_root):
    """The Managed_ISOs directory inside the fake drive."""
    path = os.path.join(drive_root, "Managed_ISOs")
    os.makedirs(path, exist_ok=True)
    return path


@pytest.fixture
def make_iso(managed_dir):
    """Create a fake ISO of a given size and return its filename."""

    def _make(filename: str, size_bytes: int = 1024):
        full = os.path.join(managed_dir, filename)
        with open(full, "wb") as fh:
            fh.write(b"\0" * size_bytes)
        return filename

    return _make
