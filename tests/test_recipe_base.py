"""Version normalisation, page parsing and the fail-loud contract."""
import pytest

import requests

from src.core.recipe_base import (
    DownloadInfo, ScrapeError, clean_version, hrefs, is_older, published_sha256, sha256_in, table_rows,
    version_key)
from tests.freshness import Resp, StrictSession


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


@pytest.mark.parametrize("sums", [
    f"{H}  {ISO}\n",                                      # GNU
    f"{H} *{ISO}\n",                                      # GNU, binary mode
    f"{H}  ./{ISO}\n",                                    # find . | sha256sum
    f"{H}  v1.2/{ISO}\n",                                 # summed from the folder above
    f"SHA256 ({ISO}) = {H}\n",                            # BSD
    f"# {ISO}: 123 bytes\nSHA256 ({ISO}) = {H}\n",        # Rocky's .CHECKSUM
    f"{'cd' * 32}  other.iso\n{H}  {ISO}\n",              # a list of several
    f"{H.upper()}  {ISO}\r\n",                            # upper case, CRLF
    f"{H}\n",                                             # a bare .sha256
])
def test_sha256_in_reads_the_common_layouts(sums):
    assert sha256_in(sums, ISO) == H


@pytest.mark.parametrize("sums", [
    f"{H}  other.iso\n",                                  # names another file
    f"{H}  {ISO}.zip\n",                                  # names a longer one
    f"{H}  x{ISO}\n",                                     # or one that ends the same
    f"{'ab' * 64}  {ISO}\n",                              # a SHA-512
    f"SHA512 ({ISO}) = {'ab' * 64}\n",
    "",
])
def test_sha256_in_takes_only_a_sha256_of_exactly_that_file(sums):
    assert sha256_in(sums, ISO) == ""


def test_published_sha256_fetches_the_list():
    session = StrictSession({"https://x/SHA256SUMS": f"{H}  {ISO}\n"})
    assert published_sha256(session, "https://x/SHA256SUMS", ISO, "Distro") == H


@pytest.mark.parametrize("answer", [
    Resp("", 404), Resp("", 503), Resp(f"{H}  {ISO}\n", 403), requests.ConnectionError("down"),
    f"{H}  other.iso\n"])
def test_published_sha256_is_empty_rather_than_a_failure(answer, caplog):
    """A checksum is a bonus: without it the download goes ahead unverified."""
    session = StrictSession({"https://x/SHA256SUMS": answer})
    assert published_sha256(session, "https://x/SHA256SUMS", ISO, "Distro") == ""
    assert "[Distro]" in caplog.text
