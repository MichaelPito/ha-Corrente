"""Tests for the GME price files, against real downloads."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from custom_components.corrente.core.gme import GmeError, parse_gme_zip
from custom_components.corrente.core.italy import ITALY_TZ

FIXTURES = Path(__file__).parent / "fixtures" / "it"


def load(name: str, zone: str = "PUN"):
    return parse_gme_zip((FIXTURES / name).read_bytes(), zone)


def rome(*args: int) -> datetime:
    return datetime(*args, tzinfo=ITALY_TZ)


def test_two_normal_days_in_quarter_hours() -> None:
    segments = load("gme-20261007-20261008.zip")
    assert len(segments) == 2 * 96
    first, last = segments[0], segments[-1]
    assert first.start == rome(2026, 10, 7, 0, 0)
    assert first.end - first.start == timedelta(minutes=15)
    assert first.price == pytest.approx(0.20970507)  # 209,705070 €/MWh
    assert last.end == rome(2026, 10, 9, 0, 0)
    # Contiguous, no gaps.
    assert all(a.end == b.start for a, b in zip(segments, segments[1:], strict=False))


def test_zone_prices() -> None:
    pun = load("gme-20261007-20261008.zip", "PUN")
    sicily = load("gme-20261007-20261008.zip", "SICI")
    assert len(sicily) == len(pun)
    assert {s.start for s in sicily} == {s.start for s in pun}


def test_end_of_summer_time_has_100_quarters() -> None:
    segments = load("gme-20251026.zip")
    assert len(segments) == 100
    assert segments[0].start == rome(2025, 10, 26, 0, 0)
    assert segments[-1].end == rome(2025, 10, 27, 0, 0)
    # Real elapsed time (in UTC: same-zone subtraction would ignore the clock change).
    assert segments[-1].end.astimezone(UTC) - segments[0].start.astimezone(UTC) == timedelta(
        hours=25
    )


def test_start_of_summer_time_has_92_quarters() -> None:
    segments = load("gme-20260329.zip")
    assert len(segments) == 92
    assert segments[-1].end == rome(2026, 3, 30, 0, 0)
    assert segments[-1].end.astimezone(UTC) - segments[0].start.astimezone(UTC) == timedelta(
        hours=23
    )


def test_not_a_zip() -> None:
    with pytest.raises(GmeError):
        parse_gme_zip(b"<html>error</html>")


def test_unknown_zone() -> None:
    with pytest.raises(ValueError):
        load("gme-20261007-20261008.zip", "MARS")
