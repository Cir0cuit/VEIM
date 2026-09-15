"""Download integrity.

DownloadInfo has always carried an sha256 field, but nothing ever verified it,
so a corrupted ISO that still reached the expected byte count was written to
the drive and only failed at boot.
"""
import os

import pytest

from src.core.downloader import DownloadTask, ChecksumError, sha256_of


def test_sha256_of_matches_hashlib(tmp_path):
    import hashlib
    payload = b"veim" * 5000
    f = tmp_path / "blob.bin"
    f.write_bytes(payload)
    assert sha256_of(str(f)) == hashlib.sha256(payload).hexdigest()


def test_sha256_of_streams_large_files(tmp_path):
    """Chunked reads must produce the same digest as a single read."""
    import hashlib
    payload = os.urandom(3 * 1024 * 1024 + 17)
    f = tmp_path / "big.bin"
    f.write_bytes(payload)
    assert sha256_of(str(f), chunk_size=64 * 1024) == hashlib.sha256(payload).hexdigest()


def test_task_normalises_supplied_checksum():
    task = DownloadTask("https://example.invalid/a.iso", "a.iso", sha256="  ABCDEF  ")
    assert task.sha256 == "abcdef"


def test_task_without_checksum_is_unverified():
    task = DownloadTask("https://example.invalid/a.iso", "a.iso")
    assert task.sha256 == ""


def test_checksum_error_is_a_download_error():
    from src.core.downloader import DownloadError
    assert issubclass(ChecksumError, DownloadError)


# --------------------------------------------------- end-to-end verification

def _serve(directory):
    """Start a throwaway HTTP server for the given directory."""
    import http.server, socketserver, threading

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(directory), **kw)

        def log_message(self, *a):
            pass

    httpd = socketserver.TCPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}"


def _download(url, dest, sha256="", timeout=30):
    import threading
    result = {}
    done = threading.Event()
    task = DownloadTask(url, dest, sha256=sha256)
    task.start_async(completion_callback=lambda ok, msg: (result.update(ok=ok, msg=msg), done.set()))
    assert done.wait(timeout), "download did not finish in time"
    return result


@pytest.fixture
def served(tmp_path):
    import hashlib
    payload = os.urandom(128 * 1024)
    (tmp_path / "served").mkdir()
    (tmp_path / "served" / "test.iso").write_bytes(payload)
    httpd, base = _serve(tmp_path / "served")
    try:
        yield base + "/test.iso", hashlib.sha256(payload).hexdigest()
    finally:
        httpd.shutdown()


def test_valid_checksum_keeps_file(served, tmp_path):
    url, digest = served
    dest = str(tmp_path / "out.iso")
    result = _download(url, dest, sha256=digest)

    assert result["ok"] is True
    assert os.path.exists(dest)


def test_bad_checksum_discards_file(served, tmp_path):
    """A mismatch must not leave a corrupt ISO on the Ventoy drive."""
    url, _ = served
    dest = str(tmp_path / "out.iso")
    result = _download(url, dest, sha256="0" * 64)

    assert result["ok"] is False
    assert "SHA-256" in result["msg"]
    assert not os.path.exists(dest), "corrupt download was left on disk"
    assert not os.path.exists(dest + ".part"), "partial file was not cleaned up"


def test_missing_checksum_still_downloads(served, tmp_path):
    url, _ = served
    dest = str(tmp_path / "out.iso")
    result = _download(url, dest)

    assert result["ok"] is True
    assert os.path.exists(dest)


# --------------------------------------------------------------- archives

def _iso_bytes(size: int = 40000) -> bytes:
    """A blob shaped enough like an ISO9660 image to be recognisable."""
    data = bytearray(b"\0" * size)
    data[32769:32774] = b"CD001"
    return bytes(data)


def test_extract_iso_from_zip_writes_the_inner_image(tmp_path):
    """Memtest86+ publishes no plain .iso, only mt86plus_<ver>_x86_64.iso.zip."""
    import zipfile
    from src.core.downloader import extract_iso_from_zip

    payload = _iso_bytes()
    archive = tmp_path / "mt86plus_8.10_x86_64.iso.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("memtest.iso", payload)

    dest = tmp_path / "memtest86plus-8.10-x86_64.iso"
    extract_iso_from_zip(str(archive), str(dest))

    assert dest.read_bytes() == payload
    assert dest.read_bytes()[32769:32774] == b"CD001"


def test_extract_refuses_an_archive_without_exactly_one_iso(tmp_path):
    """Ventoy cannot boot a .zip, so a surprising archive must fail loudly."""
    import zipfile
    from src.core.downloader import extract_iso_from_zip, ArchiveError

    empty = tmp_path / "none.zip"
    with zipfile.ZipFile(empty, "w") as z:
        z.writestr("readme.txt", "no image here")
    with pytest.raises(ArchiveError):
        extract_iso_from_zip(str(empty), str(tmp_path / "out.iso"))

    two = tmp_path / "two.zip"
    with zipfile.ZipFile(two, "w") as z:
        z.writestr("a.iso", _iso_bytes(1000))
        z.writestr("b.iso", _iso_bytes(1000))
    with pytest.raises(ArchiveError):
        extract_iso_from_zip(str(two), str(tmp_path / "out.iso"))


def test_archive_download_promotes_the_extracted_iso(tmp_path, monkeypatch):
    """End to end: the archive is fetched, unpacked, and the .zip discarded."""
    import io
    import zipfile
    import threading
    from src.core.downloader import DownloadTask

    payload = _iso_bytes()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("memtest.iso", payload)
    archive_bytes = buf.getvalue()

    class FakeResponse:
        status_code = 200
        headers = {"Content-Length": str(len(archive_bytes))}
        def raise_for_status(self): pass
        def close(self): pass
        def iter_content(self, chunk_size=1):
            yield archive_bytes

    class FakeSession:
        def get(self, *a, **kw): return FakeResponse()

    dest = tmp_path / "memtest86plus-8.10-x86_64.iso"
    done = threading.Event()
    outcome = {}

    task = DownloadTask(url="https://example.invalid/mt.iso.zip", dest_path=str(dest),
                        session=FakeSession(), archive="zip")
    task.start_async(completion_callback=lambda ok, msg: (outcome.update(ok=ok, msg=msg),
                                                          done.set()))
    assert done.wait(30), "download did not finish"

    assert outcome["ok"], outcome
    assert dest.read_bytes() == payload
    assert not (tmp_path / "memtest86plus-8.10-x86_64.iso.part").exists(), \
        "the downloaded archive was left on the drive"


def test_plain_iso_download_is_unaffected_by_the_archive_path(tmp_path):
    """A normal ISO must still be promoted byte-for-byte, not run through unzip."""
    import threading
    from src.core.downloader import DownloadTask

    payload = _iso_bytes(5000)

    class FakeResponse:
        status_code = 200
        headers = {"Content-Length": str(len(payload))}
        def raise_for_status(self): pass
        def close(self): pass
        def iter_content(self, chunk_size=1):
            yield payload

    class FakeSession:
        def get(self, *a, **kw): return FakeResponse()

    dest = tmp_path / "plain.iso"
    done = threading.Event()
    outcome = {}
    task = DownloadTask(url="https://example.invalid/plain.iso", dest_path=str(dest),
                        session=FakeSession())
    task.start_async(completion_callback=lambda ok, msg: (outcome.update(ok=ok),
                                                          done.set()))
    assert done.wait(30)
    assert outcome["ok"]
    assert dest.read_bytes() == payload
