"""Shared test fixtures.

Puts the repository root on sys.path so `src.*` imports resolve when pytest is
run from anywhere. Without this every test dies with ModuleNotFoundError.
"""
import os
import sys
import tempfile
import shutil

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# Qt needs an offscreen platform in headless CI.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def drive_root():
    """An empty throwaway directory standing in for a mounted Ventoy drive."""
    path = tempfile.mkdtemp(prefix="veim_test_")
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


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
