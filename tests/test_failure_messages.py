"""What the user is told when a download fails.

The UI prints whatever the transfer hands back. Before describe_failure() that
was the raw requests exception: three hundred characters naming a urllib3 pool
class and a line in _ssl.c.
"""
import requests

from src.core.downloader import (ArchiveError, ChecksumError,
                                 InsufficientSpaceError, describe_failure)

URL = "https://cdimage.debian.org/debian-cd/current-live/amd64/x.iso"


def with_request(exc, url=URL):
    exc.request = requests.Request(method="GET", url=url).prepare()
    return exc


def test_expired_certificate_reads_as_a_sentence():
    """The real failure this was written for: a Debian mirror whose
    certificate had expired."""
    raw = ("HTTPSConnectionPool(host='chuangtzu.ftp.acc.umu.se', port=443): "
           "Max retries exceeded with url: /debian-cd/current-live/amd64/"
           "iso-hybrid/debian-live-13.7.0-amd64-gnome.iso (Caused by "
           "SSLError(SSLCertVerificationError(1, '[SSL: CERTIFICATE_VERIFY_FAILED] "
           "certificate verify failed: certificate has expired (_ssl.c:1082)')))")
    message = describe_failure(
        with_request(requests.exceptions.SSLError(raw),
                     "https://chuangtzu.ftp.acc.umu.se/debian-cd/x.iso"),
        URL)

    assert "certificate is not valid" in message
    assert "chuangtzu.ftp.acc.umu.se" in message
    assert "HTTPSConnectionPool" not in message
    assert "_ssl.c" not in message
    assert len(message) < 200


def test_host_falls_back_to_the_requested_url():
    message = describe_failure(requests.exceptions.SSLError("boom"), URL)
    assert "cdimage.debian.org" in message


def test_missing_file():
    response = requests.Response()
    response.status_code = 404
    exc = with_request(requests.exceptions.HTTPError("404"))
    exc.response = response
    assert "no longer has this file" in describe_failure(exc, URL)


def test_server_trouble():
    response = requests.Response()
    response.status_code = 503
    exc = with_request(requests.exceptions.HTTPError("503"))
    exc.response = response
    assert "HTTP 503" in describe_failure(exc, URL)


def test_unreachable_mirror():
    message = describe_failure(requests.exceptions.ConnectionError("no route"), URL)
    assert "Could not reach the mirror" in message
    assert "cdimage.debian.org" in message


def test_timeout():
    assert "stopped responding" in describe_failure(
        requests.exceptions.ReadTimeout("slow"), URL)


def test_disk_error_names_the_drive_not_the_network():
    message = describe_failure(OSError(28, "No space left on device"), URL)
    assert "Could not write to the drive" in message
    assert "No space left on device" in message


def test_the_app_s_own_errors_pass_through_unchanged():
    """These already read well and say something describe_failure cannot."""
    for exc in (InsufficientSpaceError("Not enough space on drive! Required: 4.2 GB"),
                ChecksumError("checksum mismatch, the file was deleted"),
                ArchiveError("expected exactly one .iso inside the archive")):
        assert describe_failure(exc, URL) == str(exc)


def test_an_unexpected_error_is_still_trimmed():
    message = describe_failure(ValueError("x" * 500), URL)
    assert len(message) <= 200
    assert message.endswith("...")
