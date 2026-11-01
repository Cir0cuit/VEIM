"""Version normalisation and the fail-loud contract."""
import pytest

from src.core.recipe_base import DownloadInfo, ScrapeError, clean_version, is_older, version_key


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


@pytest.mark.parametrize("newer,older", [
    ("10", "9"),
    ("10.0.12", "10.0.9"),
    ("16.0 (Build 178.27)", "16.0 (Build 178.9)"),
    ("2.06s10", "2.06s4"),
    ("8.10", "8.8"),
])
def test_version_key_ranks_by_number_where_text_order_disagrees(newer, older):
    """Every one of these pairs sorts the other way as text."""
    assert newer < older
    assert version_key(newer) > version_key(older)
    assert is_older(older, newer) and not is_older(newer, older)


def test_a_package_revision_is_not_older_than_its_release():
    assert version_key("9.2-1") >= version_key("9.2")
    assert not is_older("9.2-1", "9.2")


@pytest.mark.parametrize("candidate,installed", [
    ("Tumbleweed", "x"), ("Stable", "26.05"), ("26.05", "Stable"), ("10", "10")])
def test_is_older_says_no_when_the_numbers_settle_nothing(candidate, installed):
    assert not is_older(candidate, installed)


ISO = "distro-1.2-x86_64.iso"
H = "ab" * 32
