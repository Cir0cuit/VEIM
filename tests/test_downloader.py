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


@pytest.mark.parametrize("reinstall", [False, True], ids=["new", "over-read-only"])
def test_archive_download_promotes_the_extracted_iso(tmp_path, reinstall):
    """End to end: the archive is fetched, unpacked, and the .zip discarded.

    A reinstall replaces the old image even when it is read-only (a FAT
    read-only attribute reads as mode 0444 on Linux), as a raw ISO's does.
    """
    if reinstall and os.name != "posix":
        pytest.skip("Windows cannot replace a read-only file either way")
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
    if reinstall:
        dest.write_bytes(b"OLD-ISO")
        dest.chmod(0o444)
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


# --------------------------------------------------------------- free space

def _held_session(payload: bytes, gate):
    """A server that sends the first chunk, then waits for `gate`."""
    class FakeResponse:
        status_code = 200
        headers = {"Content-Length": str(len(payload))}
        def raise_for_status(self): pass
        def close(self): pass
        def iter_content(self, chunk_size=1):
            yield payload[:10]
            gate.wait(30)
            yield payload[10:]

    class FakeSession:
        def get(self, *a, **kw): return FakeResponse()

    return FakeSession()


def _start(task):
    import threading
    done = threading.Event()
    outcome = {}
    task.start_async(completion_callback=lambda ok, msg: (outcome.update(ok=ok, msg=msg),
                                                          done.set()))
    return done, outcome


def test_free_space_counts_the_downloads_already_running(tmp_path, monkeypatch):
    """Regression: six transfers started at once onto a drive with room for two.
    Each one checked the disk on its own and, on its own, fitted."""
    import threading
    import time
    from src.core import downloader

    payload = os.urandom(1024)
    # Room for one and a half of these, never for two.
    monkeypatch.setattr(downloader.shutil, "disk_usage",
                        lambda path: (10 ** 9, 10 ** 9 - 1536, 1536))

    gate = threading.Event()
    first = DownloadTask("https://example.invalid/a.iso", str(tmp_path / "a.iso"),
                         session=_held_session(payload, gate))
    first_done, first_outcome = _start(first)
    deadline = time.monotonic() + 5
    while downloader.reserved_bytes() == 0 and time.monotonic() < deadline:
        time.sleep(0.01)
    assert downloader.reserved_bytes() == len(payload) - 10 or downloader.reserved_bytes() == len(payload)

    second = DownloadTask("https://example.invalid/b.iso", str(tmp_path / "b.iso"),
                          session=_held_session(payload, threading.Event()))
    second_done, second_outcome = _start(second)
    assert second_done.wait(10)
    assert not second_outcome["ok"]
    assert "spoken for by downloads already running" in second_outcome["msg"]
    assert not (tmp_path / "b.iso").exists()

    gate.set()
    assert first_done.wait(10)
    assert first_outcome["ok"]
    assert downloader.reserved_bytes() == 0, "a finished transfer must give its space back"

    # With the first one done, the same request fits.
    third_gate = threading.Event()
    third_gate.set()
    third = DownloadTask("https://example.invalid/c.iso", str(tmp_path / "c.iso"),
                         session=_held_session(payload, third_gate))
    third_done, third_outcome = _start(third)
    assert third_done.wait(10)
    assert third_outcome["ok"], third_outcome


def test_a_failed_transfer_gives_its_space_back(tmp_path, quick_retries):
    from src.core import downloader

    class Boom:
        def get(self, *a, **kw): raise OSError("no route to host")

    task = DownloadTask("https://example.invalid/x.iso", str(tmp_path / "x.iso"), session=Boom())
    done, outcome = _start(task)
    assert done.wait(10)
    assert not outcome["ok"]
    assert downloader.reserved_bytes() == 0


# ------------------------------------------------------------------ retries

class _FlakyServer:
    """Serves `payload` in pieces, dropping the connection after each piece
    for the first `drops` requests. Honours Range, like a real mirror."""

    def __init__(self, payload: bytes, piece: int, drops: int):
        self.payload, self.piece, self.drops = payload, piece, drops
        self.requests = 0

    def get(self, url, headers=None, **kw):
        self.requests += 1
        start = int((headers or {}).get("Range", "bytes=0-")[6:-1] or 0)
        drop = self.requests <= self.drops
        server, body = self, self.payload[start:]

        class Resp:
            status_code = 206 if start else 200
            headers = {"Content-Length": str(len(body))}
            def raise_for_status(self): pass
            def close(self): pass
            def iter_content(self, chunk_size=1):
                yield body[:server.piece]
                if drop:
                    import requests
                    raise requests.exceptions.ConnectionError("link dropped")
                yield body[server.piece:]
        return Resp()


@pytest.fixture
def quick_retries(monkeypatch):
    from src.core import downloader
    monkeypatch.setattr(downloader, "RETRY_DELAYS_SECONDS", (0.01, 0.01, 0.01, 0.01))


def test_an_interrupted_transfer_that_keeps_advancing_is_never_given_up_on(tmp_path, quick_retries):
    """Regression: four attempts, each resuming further along, and the
    fourth drop failed the download 'permanently' with 3.8 GB on disk."""
    payload = os.urandom(20_000)
    server = _FlakyServer(payload, piece=1_000, drops=15)     # far more than the retry budget
    task = DownloadTask("https://example.invalid/u.iso", str(tmp_path / "u.iso"), session=server)
    done, outcome = _start(task)
    assert done.wait(30)
    assert outcome["ok"], outcome
    assert (tmp_path / "u.iso").read_bytes() == payload
    assert server.requests == 16


def test_a_transfer_getting_nowhere_is_retried_then_fails(tmp_path, quick_retries):
    class Dead:
        def __init__(self): self.requests = 0
        def get(self, *a, **kw):
            self.requests += 1
            import requests
            raise requests.exceptions.ConnectionError("no route to host")

    dead = Dead()
    task = DownloadTask("https://example.invalid/u.iso", str(tmp_path / "u.iso"), session=dead)
    done, outcome = _start(task)
    assert done.wait(30)
    assert not outcome["ok"]
    assert dead.requests == 5, "one attempt plus the four retries"


def test_the_row_is_told_about_each_retry(tmp_path, monkeypatch):
    from src.core import downloader
    monkeypatch.setattr(downloader, "RETRY_DELAYS_SECONDS", (0.6, 0.01, 0.01, 0.01))
    payload = os.urandom(3_000)
    server = _FlakyServer(payload, piece=1_000, drops=1)
    notes = []
    task = DownloadTask("https://example.invalid/u.iso", str(tmp_path / "u.iso"), session=server)
    import threading
    done = threading.Event()
    task.start_async(progress_callback=lambda t: notes.append(t.note),
                     completion_callback=lambda ok, msg: done.set())
    assert done.wait(30)
    assert any(n.startswith("Connection lost, retrying in 1 s (1 of 4)") for n in notes), notes
    assert any(n.startswith("Reconnecting (1 of 4)") for n in notes), notes
    assert notes[-1] == "", "the note must clear once the transfer is moving again"
    assert task.note == ""


def test_cancel_during_the_retry_pause_stops_at_once(tmp_path, monkeypatch):
    import time
    from src.core import downloader
    monkeypatch.setattr(downloader, "RETRY_DELAYS_SECONDS", (30, 30, 30, 30))
    server = _FlakyServer(os.urandom(3_000), piece=1_000, drops=1)
    task = DownloadTask("https://example.invalid/u.iso", str(tmp_path / "u.iso"), session=server)
    done, outcome = _start(task)

    deadline = time.monotonic() + 5
    while not task.note and time.monotonic() < deadline:
        time.sleep(0.01)
    assert task.note.startswith("Connection lost")
    started = time.monotonic()
    task.cancel()
    assert done.wait(5), "cancel did not end the wait"
    assert time.monotonic() - started < 2
    assert not outcome["ok"]
    assert not (tmp_path / "u.iso.part").exists(), "a cancelled transfer keeps no partial file"
    assert server.requests == 1, "cancel was answered by another attempt"
