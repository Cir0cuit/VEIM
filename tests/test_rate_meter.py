"""Transfer-rate metering.

The speed and ETA readouts used to be computed from a single 0.4s sample, so
they swung with every burst of TCP jitter and the ETA looked like a different
random number on each refresh. These tests pin the behaviour that replaced it.
"""
import pytest

from src.core.downloader import RateMeter


class FakeClock:
    """A monotonic clock we can step deterministically."""

    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t

    def advance(self, seconds):
        self.t += seconds


@pytest.fixture
def clock(monkeypatch):
    c = FakeClock()
    monkeypatch.setattr("src.core.downloader.time.monotonic", c)
    return c


MB = 1024 * 1024


def test_speed_averages_over_the_window(clock):
    """A steady 10 MB/s transfer reports 10 MB/s."""
    meter = RateMeter(window=6.0)
    meter.reset(0)

    total = 0
    for _ in range(20):
        clock.advance(0.5)
        total += 5 * MB          # 5 MB every 0.5s == 10 MB/s
        meter.update(total)

    assert meter.speed_mbps == pytest.approx(10.0, rel=0.05)


def test_a_single_stalled_sample_does_not_crater_the_speed(clock):
    """One empty half-second is jitter, not a collapse in throughput.

    Under the old instantaneous calculation this sample alone reported ~0 MB/s
    and sent the ETA to infinity.
    """
    meter = RateMeter(window=6.0)
    meter.reset(0)

    total = 0
    for _ in range(10):
        clock.advance(0.5)
        total += 5 * MB
        meter.update(total)

    before = meter.speed_mbps
    clock.advance(0.5)
    meter.update(total)          # nothing arrived in this slice
    after = meter.speed_mbps

    assert after > before * 0.7, "one idle sample should barely move the average"


def test_a_single_burst_does_not_spike_the_speed(clock):
    """The mirror flushing a large buffer is not a tenfold speedup."""
    meter = RateMeter(window=6.0)
    meter.reset(0)

    total = 0
    for _ in range(10):
        clock.advance(0.5)
        total += 5 * MB
        meter.update(total)

    before = meter.speed_mbps
    clock.advance(0.5)
    total += 50 * MB             # a ten-chunk burst lands at once
    meter.update(total)

    assert meter.speed_mbps < before * 2.5


def test_eta_is_damped_towards_a_new_estimate(clock):
    """A change in speed moves the ETA gradually rather than snapping to it."""
    meter = RateMeter(window=6.0, smoothing=0.2)
    meter.reset(0)

    total = 0
    for _ in range(20):
        clock.advance(0.5)
        total += 10 * MB         # 20 MB/s
        meter.update(total)

    remaining = 2000 * MB
    settled = meter.eta_seconds(remaining)
    assert settled == pytest.approx(100, rel=0.1)   # 2000 MB at 20 MB/s

    # Halve the rate. The true ETA doubles; the reported one must not jump there.
    for _ in range(4):
        clock.advance(0.5)
        total += 5 * MB
        meter.update(total)
    stepped = meter.eta_seconds(remaining)

    assert stepped > settled, "estimate should be rising"
    assert stepped < settled * 1.6, "but not snap straight to the new value"


def test_eta_holds_last_estimate_through_a_stall(clock):
    """A stalled connection keeps the last figure instead of flashing '--'."""
    meter = RateMeter(window=2.0)
    meter.reset(0)

    total = 0
    for _ in range(8):
        clock.advance(0.5)
        total += 5 * MB
        meter.update(total)
    established = meter.eta_seconds(500 * MB)
    assert established > 0

    # Long enough with no bytes that the window contains no progress at all.
    for _ in range(10):
        clock.advance(0.5)
        meter.update(total)

    assert meter.speed_mbps == pytest.approx(0.0, abs=0.01)
    assert meter.eta_seconds(500 * MB) == established


def test_eta_is_zero_when_nothing_remains(clock):
    meter = RateMeter()
    meter.reset(0)
    clock.advance(1.0)
    meter.update(10 * MB)
    assert meter.eta_seconds(0) == 0


def test_reset_discards_the_previous_connection(clock):
    """After a retry, samples from the dead connection must not count."""
    meter = RateMeter(window=10.0)
    meter.reset(0)

    total = 0
    for _ in range(10):
        clock.advance(0.5)
        total += 20 * MB         # 40 MB/s
        meter.update(total)
    assert meter.speed_mbps > 30

    clock.advance(30.0)          # the connection died and we backed off
    meter.reset(total)
    assert meter.speed_mbps == 0.0

    for _ in range(4):
        clock.advance(0.5)
        total += 1 * MB          # resumed at 2 MB/s
        meter.update(total)

    assert meter.speed_mbps == pytest.approx(2.0, rel=0.2)
