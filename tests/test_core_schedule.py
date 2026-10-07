"""Tests for price schedules and the cheapest window."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from custom_components.corrente.core.contract import ItalyContractType, ItalyFixedContract
from custom_components.corrente.core.italy import ITALY_TZ, next_band_change
from custom_components.corrente.core.schedule import (
    Segment,
    build_schedule,
    cheapest_window,
)

THREE_BANDS = ItalyFixedContract(ItalyContractType.THREE_BANDS, 0.30, 0.25, 0.20)


def rome(*args: int) -> datetime:
    return datetime(*args, tzinfo=ITALY_TZ)


def italy_schedule(start: datetime, hours: int = 36) -> list[Segment]:
    return build_schedule(
        THREE_BANDS.price_at,
        lambda moment: next_band_change(moment)[0],
        start,
        timedelta(hours=hours),
    )


def test_italian_schedule_on_a_weekday() -> None:
    segments = italy_schedule(rome(2026, 10, 7, 10, 30), hours=24)
    assert [(s.start.hour, s.price) for s in segments] == [
        (10, 0.30),  # F1 until 19
        (19, 0.25),  # F2 until 23
        (23, 0.20),  # F3 until 7
        (7, 0.25),  # F2 until 8
        (8, 0.30),  # F1 again
    ]
    assert segments[0].start == rome(2026, 10, 7, 10, 30)
    assert segments[-1].end == rome(2026, 10, 8, 10, 30)


def test_adjacent_equal_prices_are_merged() -> None:
    two_bands = ItalyFixedContract(ItalyContractType.TWO_BANDS, 0.30, 0.22)
    segments = build_schedule(
        two_bands.price_at,
        lambda moment: next_band_change(moment)[0],
        rome(2026, 10, 7, 20, 0),
        timedelta(hours=12),
    )
    # F2 and F3 both cost 0.22 in a two-band contract: one segment from 20:00 until
    # F1 starts at 08:00, which is also where the 12-hour horizon ends.
    assert [(s.start.hour, s.end.hour, s.price) for s in segments] == [(20, 8, 0.22)]


def test_cheapest_window_waits_for_the_night() -> None:
    segments = italy_schedule(rome(2026, 10, 7, 10, 30))
    window = cheapest_window(segments, timedelta(hours=2))
    assert window.start == rome(2026, 10, 7, 23, 0)
    assert window.end == rome(2026, 10, 8, 1, 0)
    assert window.average_price == pytest.approx(0.20)


def test_cheapest_window_now_when_already_cheapest() -> None:
    segments = italy_schedule(rome(2026, 10, 7, 23, 30))
    window = cheapest_window(segments, timedelta(hours=2))
    assert window.start == rome(2026, 10, 7, 23, 30)


def test_cheapest_window_can_straddle_a_change() -> None:
    # 3 hours starting at 22:00 on Saturday: 1 h of F2 then F3 until Monday.
    # Starting at 23:00 is fully F3, so it beats 22:00.
    segments = italy_schedule(rome(2026, 10, 10, 21, 0), hours=6)
    window = cheapest_window(segments, timedelta(hours=3))
    assert window.start == rome(2026, 10, 10, 23, 0)


def test_cheapest_window_longer_than_schedule() -> None:
    segments = italy_schedule(rome(2026, 10, 7, 10, 0), hours=2)
    assert cheapest_window(segments, timedelta(hours=3)) is None
    assert cheapest_window([], timedelta(hours=1)) is None


def test_constant_price_schedule() -> None:
    start = rome(2026, 10, 7, 10, 0)
    segments = build_schedule(lambda m: 0.27, lambda m: None, start, timedelta(hours=24))
    assert segments == [Segment(start, start + timedelta(hours=24), 0.27)]
    assert cheapest_window(segments, timedelta(hours=2)).start == start


def test_naive_start_is_rejected() -> None:
    with pytest.raises(ValueError):
        build_schedule(lambda m: 0.1, lambda m: None, datetime(2026, 1, 1), timedelta(hours=1))
