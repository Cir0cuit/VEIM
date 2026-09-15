"""Version normalisation and the fail-loud contract."""
import pytest

from src.core.recipe_base import DownloadInfo, ScrapeError, clean_version


@pytest.mark.parametrize("raw,expected", [
    ("v2025.11_31_x86-64_0.42", "2025.11_31_x86-64_0.42"),  # ShredOS double-v
    ("8.1-", "8.1"),                                        # elementary trailing dash
    ("23.0-SP1-", "23.0-SP1"),                              # FydeOS trailing dash
    ("v2.6.2", "2.6.2"),
    ("  22.04  ", "22.04"),
    ("Tumbleweed", "Tumbleweed"),                           # word left alone
    ("virt", "virt"),                                       # leading v kept (not a tag)
    ("Vera", "Vera"),
    ("", "Unknown"),
    (None, "Unknown"),
])
def test_clean_version(raw, expected):
    assert clean_version(raw) == expected


def test_download_info_normalises_version_on_construction():
    info = DownloadInfo(version="v2025.11_31", url="https://example.invalid/a.iso")
    assert info.version == "2025.11_31"


def test_scrape_error_carries_distro_and_reason():
    err = ScrapeError("Zorin OS", "release feed returned no current build")
    assert err.distro == "Zorin OS"
    assert "release feed" in err.reason
    assert "Zorin OS" in str(err)
