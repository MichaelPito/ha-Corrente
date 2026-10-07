"""Price schedules and the cheapest time to run an appliance.

Both Italian band contracts and Swiss operator tariffs are piecewise constant:
the price only changes at known moments. A schedule is the list of those
pieces for the next hours. Pure Python, no Home Assistant imports.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

PriceAt = Callable[[datetime], float]
NextChange = Callable[[datetime], datetime | None]


@dataclass(frozen=True, slots=True)
class Segment:
    """A stretch of time with one price per kWh."""

    start: datetime
    end: datetime
    price: float


@dataclass(frozen=True, slots=True)
class Window:
    """The cheapest stretch of a given length."""

    start: datetime
    end: datetime
    average_price: float


def build_schedule(
    price_at: PriceAt, next_change: NextChange, start: datetime, horizon: timedelta
) -> list[Segment]:
    """Cut ``[start, start + horizon)`` into segments of constant price.

    Everything is computed in UTC: Python subtracts and adds datetimes of the
    same zone on the wall clock, which would be an hour off on the nights the
    clocks change.
    """
    if start.tzinfo is None:
        raise ValueError("start must be timezone-aware")
    start = start.astimezone(UTC)
    end = start + horizon
    segments: list[Segment] = []
    cursor = start
    while cursor < end:
        price = price_at(cursor)
        change = next_change(cursor)
        if change is not None:
            change = change.astimezone(UTC)
        stop = end if change is None or change > end else change
        if stop <= cursor:  # defensive: never loop on a non-advancing change
            stop = end
        if segments and segments[-1].price == price:
            segments[-1] = Segment(segments[-1].start, stop, price)
        else:
            segments.append(Segment(cursor, stop, price))
        cursor = stop
    return segments


def _average(segments: Sequence[Segment], start: datetime, end: datetime) -> float:
    total = 0.0
    for segment in segments:
        overlap_start = max(segment.start, start)
        overlap_end = min(segment.end, end)
        if overlap_end > overlap_start:
            total += segment.price * (overlap_end - overlap_start).total_seconds()
    return total / (end - start).total_seconds()


def cheapest_window(segments: Sequence[Segment], duration: timedelta) -> Window | None:
    """Return the start of the cheapest ``duration`` within the schedule.

    With piecewise-constant prices the best window starts at a segment start
    or ends at a segment end, so only those candidates are checked. Ties go to
    the earliest start, so "now" wins when nothing is cheaper.
    """
    if not segments or duration <= timedelta(0):
        return None
    segments = [Segment(s.start.astimezone(UTC), s.end.astimezone(UTC), s.price) for s in segments]
    first, last = segments[0].start, segments[-1].end
    if last - first < duration:
        return None
    candidates = {s.start for s in segments} | {s.end - duration for s in segments}
    starts = sorted(c for c in candidates if first <= c <= last - duration)
    best: Window | None = None
    for start in starts:
        average = _average(segments, start, start + duration)
        if best is None or average < best.average_price - 1e-12:
            best = Window(start, start + duration, round(average, 6))
    return best
