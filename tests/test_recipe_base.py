"""Version normalisation, page parsing and the fail-loud contract."""
import pytest

from src.core.recipe_base import DownloadInfo, ScrapeError, clean_version, hrefs, table_rows


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


def test_hrefs_are_every_link_target_decoded():
    page = '<a href="../">..</a><a name="top"></a><A HREF="a&amp;b.iso"/><link href="x.css">'
    assert hrefs(page) == ["../", "a&b.iso"]


def test_table_rows_are_the_text_of_each_cell():
    """The shape of linuxmint.com's release table: the version is a row's first cell."""
    page = ('<table><tr><th>Version</th></tr>'
            '<tr><td rowspan="3">22.3</td><td><a href="edition.php?id=326">Cinnamon </a></td></tr>'
            '<tr><td><a href="edition.php?id=328">MATE </a></td></tr></table><p>22.2</p>')
    assert table_rows(page) == [[], ["22.3", "Cinnamon"], ["MATE"]]
