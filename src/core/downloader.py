import os
import time
import hashlib
import threading
import zipfile
import requests
import shutil
from collections import deque
from typing import Callable, Optional
from urllib.parse import urlparse
from src.core.logger import log

# Speed is averaged over this window; a single chunk-to-chunk sample measures
# TCP jitter, not throughput.
SPEED_WINDOW_SECONDS = 6.0

# How often the UI is told about progress.
PROGRESS_INTERVAL_SECONDS = 0.5

# Weight of a new ETA estimate against the running one.
ETA_SMOOTHING = 0.2

# Bytes each running transfer still has to write, by task. A free-space check
# that looked only at the disk let six downloads start at once onto a drive
# with room for two: each one, on its own, fitted.
_reservations: dict = {}
_reservations_lock = threading.Lock()


def reserved_bytes(except_task=None) -> int:
    """What the transfers in flight are still going to write."""
    with _reservations_lock:
        return sum(n for t, n in _reservations.items() if t is not except_task)


def _reserve(task, remaining: int) -> None:
    with _reservations_lock:
        _reservations[task] = max(remaining, 0)


def _release(task) -> None:
    with _reservations_lock:
        _reservations.pop(task, None)


def _headers_for(url: str) -> dict:
    ua = ("curl/8.4.0" if ("sourceforge" in url or "ibiblio" in url)
          else "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    return {"User-Agent": ua, "Accept": "*/*"}


def probe_size(url: str, session: Optional[requests.Session] = None) -> int:
    """How many bytes a download is, or 0 when the server will not say.

    Asked before a transfer starts, so that one which will not fit can be
    refused - or the room made for it - before anything is written. A HEAD
    first; a mirror that refuses those gets a GET that is closed unread.
    """
    session = session or requests.Session()
    headers = _headers_for(url)
    try:
        resp = session.head(url, headers=headers, timeout=(20, 30), allow_redirects=True)
        length = resp.headers.get("Content-Length") if resp.ok else None
        resp.close()
        if not length:
            resp = session.get(url, headers=headers, stream=True, timeout=(20, 30),
                               allow_redirects=True)
            length = resp.headers.get("Content-Length") if resp.ok else None
            resp.close()
        return int(length) if length else 0
    except (requests.exceptions.RequestException, ValueError) as e:
        log.warning(f"Could not learn the size of {url}: {e}")
        return 0


def free_for_download(dest_dir: str) -> int:
    """Free space on the drive, less what running transfers still need."""
    total, used, free = shutil.disk_usage(dest_dir)
    return free - reserved_bytes()


class DownloadError(Exception):
    pass

class InsufficientSpaceError(DownloadError):
    pass

class ChecksumError(DownloadError):
    """The finished file did not match the checksum upstream published."""


class ArchiveError(DownloadError):
    """The download was an archive we could not turn into a bootable ISO."""


def describe_failure(exc: Exception, url: str = "") -> str:
    """A sentence a person can act on, instead of a requests traceback.

    The UI shows whatever comes back from a failed transfer, and the raw
    exception is a 300-character urllib3 dump naming a pool class and a C
    source line. The detail still reaches the log; this is what reaches the
    user.
    """
    if isinstance(exc, DownloadError):
        return str(exc)

    host = ""
    request = getattr(exc, "request", None)
    for candidate in (getattr(request, "url", "") or "", url):
        if candidate:
            try:
                host = urlparse(candidate).netloc or ""
            except ValueError:
                host = ""
            if host:
                break
    where = f" ({host})" if host else ""

    if isinstance(exc, requests.exceptions.SSLError):
        return (f"The mirror's security certificate is not valid{where}. "
                f"That is a fault on the mirror, not on your machine — "
                f"try again later.")
    if isinstance(exc, (requests.exceptions.ConnectTimeout,
                        requests.exceptions.ReadTimeout)):
        return f"The mirror{where} stopped responding."
    if isinstance(exc, requests.exceptions.TooManyRedirects):
        return f"The mirror{where} redirected in a loop."
    if isinstance(exc, requests.exceptions.HTTPError):
        status = getattr(getattr(exc, "response", None), "status_code", None)
        if status == 404:
            return f"The mirror{where} no longer has this file."
        if status in (401, 403):
            return f"The mirror{where} refused the download."
        if status and 500 <= status < 600:
            return f"The mirror{where} is having trouble (HTTP {status})."
        return f"The mirror{where} returned HTTP {status}." if status else \
            f"The mirror{where} rejected the download."
    if isinstance(exc, requests.exceptions.ConnectionError):
        return f"Could not reach the mirror{where}. Check your connection."
    if isinstance(exc, OSError):
        reason = getattr(exc, "strerror", None) or str(exc)
        return f"Could not write to the drive: {reason}"

    text = str(exc).strip() or exc.__class__.__name__
    return text if len(text) <= 200 else text[:197] + "..."


def extract_iso_from_zip(zip_path: str, dest_path: str) -> None:
    """Unpack the single ISO inside `zip_path` to `dest_path`.

    Some projects publish only a zipped image - Memtest86+ ships
    mt86plus_<ver>_x86_64.iso.zip and no plain .iso at all. Ventoy boots ISO
    files, so writing the archive to the drive would leave the user with
    something that silently never appears in the boot menu.
    """
    with zipfile.ZipFile(zip_path) as archive:
        members = [m for m in archive.infolist()
                   if not m.is_dir() and m.filename.lower().endswith(".iso")]
        if len(members) != 1:
            raise ArchiveError(
                f"expected exactly one .iso inside the archive, found {len(members)}"
            )
        member = members[0]
        with archive.open(member) as src, open(dest_path, "wb") as out:
            shutil.copyfileobj(src, out, 1024 * 1024)


def sha256_of(path: str, chunk_size: int = 1024 * 1024) -> str:
    """Stream a file through SHA-256.

    ISOs run to several GB, so this reads in chunks rather than loading the
    file into memory.
    """
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(chunk_size), b""):
            digest.update(block)
    return digest.hexdigest()

class RateMeter:
    """Sliding-window transfer rate, with a damped ETA.

    Measuring speed as `bytes_since_last / elapsed_since_last` makes the
    readout a sample of instantaneous jitter rather than of throughput: at a
    0.4s sample interval the figure swung between a fraction of and several
    times the real rate, and dividing the remaining bytes by that number
    produced an ETA that looked random on every refresh.

    Averaging over a window of several seconds gives a speed that tracks real
    changes but ignores chunk-to-chunk noise, and easing the ETA toward each
    new estimate stops it snapping around when the speed does shift.
    """

    def __init__(self, window: float = SPEED_WINDOW_SECONDS,
                 smoothing: float = ETA_SMOOTHING):
        self.window = window
        self.smoothing = smoothing
        self._samples: deque = deque()   # (timestamp, cumulative_bytes)
        self._eta: Optional[float] = None

    def reset(self, downloaded_bytes: int = 0):
        """Start a fresh window - after a retry, the old samples are meaningless."""
        self._samples.clear()
        self._samples.append((time.monotonic(), downloaded_bytes))
        self._eta = None

    def update(self, downloaded_bytes: int) -> None:
        now = time.monotonic()
        self._samples.append((now, downloaded_bytes))
        # Keep one sample older than the window, so a full span stays available.
        while len(self._samples) > 2 and now - self._samples[1][0] >= self.window:
            self._samples.popleft()

    @property
    def speed_mbps(self) -> float:
        if len(self._samples) < 2:
            return 0.0
        (t0, b0), (t1, b1) = self._samples[0], self._samples[-1]
        span = t1 - t0
        if span <= 0:
            return 0.0
        return ((b1 - b0) / span) / (1024 * 1024)

    def eta_seconds(self, remaining_bytes: int) -> int:
        """Damped seconds-remaining estimate, or 0 when it cannot be known."""
        speed = self.speed_mbps
        if remaining_bytes <= 0:
            return 0
        if speed <= 0:
            # Keep the last estimate rather than flashing "--" during a stall.
            return int(self._eta) if self._eta else 0

        estimate = remaining_bytes / (speed * 1024 * 1024)
        if self._eta is None:
            self._eta = estimate
        else:
            self._eta += (estimate - self._eta) * self.smoothing
        return max(0, int(self._eta))


class DownloadTask:
    def __init__(self, url: str, dest_path: str, expected_size: int = 0,
                 session: Optional[requests.Session] = None, sha256: str = "",
                 archive: str = ""):
        self.url = url
        self.dest_path = dest_path
        self.part_path = dest_path + ".part"
        self.expected_size = expected_size
        # Published checksum, verified before .part is promoted to .iso.
        self.sha256 = (sha256 or "").strip().lower()
        # "zip" when the fetched file is an archive to unpack, "" for a raw ISO.
        self.archive = (archive or "").strip().lower()
        self.session = session or requests.Session()
        
        self.is_cancelled = False
        self.is_completed = False
        self.downloaded_bytes = 0
        self.total_bytes = 0
        self.speed_mbps = 0.0
        self.eta_seconds = 0
        self._meter = RateMeter()
        self._thread: Optional[threading.Thread] = None

    def cancel(self):
        self.is_cancelled = True
        log.info(f"Download cancellation requested for {self.dest_path}")

    def start_async(self, progress_callback: Optional[Callable[['DownloadTask'], None]] = None,
                    completion_callback: Optional[Callable[[bool, str], None]] = None):
        self._thread = threading.Thread(
            target=self._run,
            args=(progress_callback, completion_callback),
            daemon=True
        )
        self._thread.start()

    def _run(self, progress_cb, completion_cb):
        try:
            self._transfer(progress_cb, completion_cb)
        finally:
            _release(self)

    def _check_space(self, dest_dir: str) -> None:
        """Raise unless this transfer fits beside the ones already running.

        Their .part files have taken their bytes off the disk already; what
        they have still to write has not, so it is counted here.
        """
        total, used, free = shutil.disk_usage(dest_dir)
        remaining = ((self.total_bytes - self.downloaded_bytes)
                     if self.total_bytes > 0 else 1024 ** 3)
        others = reserved_bytes(except_task=self)
        if free - others < remaining:
            gb = lambda n: round(n / (1024 ** 3), 2)
            detail = (f"{gb(free)} GB, of which {gb(others)} GB is spoken for by "
                      f"downloads already running" if others else f"{gb(free)} GB")
            raise InsufficientSpaceError(
                f"Not enough space on drive! Required: {gb(remaining)} GB, "
                f"Available: {detail}")
        _reserve(self, remaining)

    def _transfer(self, progress_cb, completion_cb):
        dest_dir = os.path.dirname(self.dest_path)
        os.makedirs(dest_dir, exist_ok=True)

        max_retries = 3
        retry_count = 0
        mode = "wb"

        if os.path.exists(self.part_path) and os.path.getsize(self.part_path) > 0:
            self.downloaded_bytes = os.path.getsize(self.part_path)
            mode = "ab"
        else:
            self.downloaded_bytes = 0

        while retry_count <= max_retries and not self.is_cancelled:
            try:
                log.info(f"Download attempt {retry_count + 1}/{max_retries + 1}: {self.url} (offset {self.downloaded_bytes})")

                headers = _headers_for(self.url)
                ua = headers["User-Agent"]
                if self.downloaded_bytes > 0:
                    headers["Range"] = f"bytes={self.downloaded_bytes}-"

                resp = self.session.get(self.url, headers=headers, stream=True, timeout=(20, 90), allow_redirects=True)
                
                # Cloudflare curl fallback
                if resp.status_code == 403 and "curl" not in ua:
                    resp.close()
                    headers["User-Agent"] = "curl/8.4.0"
                    resp = self.session.get(self.url, headers=headers, stream=True, timeout=(20, 90), allow_redirects=True)

                if resp.status_code == 416:
                    # Range not satisfiable -> server already finished or doesn't support range
                    log.info("Range not satisfiable (416), restarting from beginning.")
                    self.downloaded_bytes = 0
                    mode = "wb"
                    if "Range" in headers:
                        del headers["Range"]
                    resp = self.session.get(self.url, headers=headers, stream=True, timeout=(20, 90), allow_redirects=True)

                if resp.status_code == 200 and self.downloaded_bytes > 0:
                    # Server didn't honor range request, restart from 0
                    self.downloaded_bytes = 0
                    mode = "wb"

                resp.raise_for_status()

                content_len = resp.headers.get("Content-Length")
                if content_len:
                    if resp.status_code == 206:
                        self.total_bytes = self.downloaded_bytes + int(content_len)
                    else:
                        self.total_bytes = int(content_len)
                elif not self.total_bytes:
                    self.total_bytes = self.expected_size

                self._check_space(dest_dir)

                chunk_size = 128 * 1024  # 128 KB chunks
                # Samples from before a stall describe a connection that is gone.
                self._meter.reset(self.downloaded_bytes)
                last_emit = time.monotonic()

                with open(self.part_path, mode) as f:
                    for chunk in resp.iter_content(chunk_size=chunk_size):
                        if self.is_cancelled:
                            f.close()
                            if os.path.exists(self.part_path):
                                try:
                                    os.remove(self.part_path)
                                except Exception:
                                    pass
                            if completion_cb:
                                completion_cb(False, "Cancelled by user")
                            return

                        if chunk:
                            f.write(chunk)
                            self.downloaded_bytes += len(chunk)
                            self._meter.update(self.downloaded_bytes)

                            now = time.monotonic()
                            if now - last_emit >= PROGRESS_INTERVAL_SECONDS:
                                last_emit = now
                                if self.total_bytes > 0:
                                    _reserve(self, self.total_bytes - self.downloaded_bytes)
                                self.speed_mbps = self._meter.speed_mbps
                                if self.total_bytes > 0:
                                    self.eta_seconds = self._meter.eta_seconds(
                                        self.total_bytes - self.downloaded_bytes
                                    )

                                if progress_cb:
                                    progress_cb(self)

                if self.total_bytes > 0 and self.downloaded_bytes < self.total_bytes:
                    raise DownloadError(f"Incomplete download: {self.downloaded_bytes}/{self.total_bytes} bytes")

                # A corrupt ISO can still reach the expected byte count.
                if self.sha256:
                    log.info(f"Verifying SHA-256 for {os.path.basename(self.dest_path)}...")
                    actual = sha256_of(self.part_path)
                    if actual != self.sha256:
                        try:
                            os.remove(self.part_path)
                        except Exception:
                            pass
                        raise ChecksumError(
                            "Downloaded file failed its SHA-256 check "
                            f"(expected {self.sha256[:16]}..., got {actual[:16]}...). "
                            "The file was discarded."
                        )
                    log.info("SHA-256 verified.")

                if os.path.exists(self.dest_path):
                    try:
                        os.remove(self.dest_path)
                    except Exception:
                        pass

                if self.archive == "zip":
                    log.info(f"Extracting ISO from archive for {os.path.basename(self.dest_path)}...")
                    extract_iso_from_zip(self.part_path, self.dest_path)
                    os.remove(self.part_path)
                else:
                    os.replace(self.part_path, self.dest_path)
                self.is_completed = True
                log.info(f"Download successfully finished: {self.dest_path}")

                if progress_cb:
                    progress_cb(self)
                if completion_cb:
                    completion_cb(True, "Success")
                return

            except (ChecksumError, ArchiveError, InsufficientSpaceError) as e:
                # Retrying fixes none of these.
                log.error(f"Download could not be finalised for {self.url}: {e}")
                if completion_cb:
                    completion_cb(False, describe_failure(e, self.url))
                return
            except (requests.exceptions.RequestException, DownloadError, IOError) as e:
                retry_count += 1
                log.warning(f"Download transient error (attempt {retry_count}): {e}")
                if retry_count > max_retries or self.is_cancelled:
                    log.exception(f"Download failed permanently for {self.url}: {e}")
                    if self.is_cancelled and os.path.exists(self.part_path):
                        try:
                            os.remove(self.part_path)
                        except Exception:
                            pass
                    if completion_cb:
                        completion_cb(False, describe_failure(e, self.url))
                    return
                # Wait briefly and resume with "ab"
                mode = "ab"
                time.sleep(1.5)
            except Exception as e:
                log.exception(f"Fatal error during download: {e}")
                if completion_cb:
                    completion_cb(False, describe_failure(e, self.url))
                return

