"""Italian ARERA time bands (fasce orarie F1, F2, F3).

Pure Python, no Home Assistant imports, so it can be unit-tested in isolation.

Bands (ARERA, Delibera 181/06 and later updates):
- F1: Monday-Friday 08:00-19:00, national holidays excluded.
- F2: Monday-Friday 07:00-08:00 and 19:00-23:00; Saturday 07:00-23:00;
  national holidays excluded.
- F3: Monday-Saturday 00:00-07:00 and 23:00-24:00; Sundays and national
  holidays all day.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from enum import StrEnum
from zoneinfo import ZoneInfo

ITALY_TZ = ZoneInfo("Europe/Rome")


class Band(StrEnum):
    """Italian time band."""

    F1 = "F1"
    F2 = "F2"
    F3 = "F3"


# Holidays that count as F3, as listed by ARERA (TIV, Allegato A to delibera
# 362/2023/R/eel, Tabella 6; originally delibera 181/06). The list is closed:
# national holidays added later by law (for example San Francesco on 4 October
# from 2026) are NOT F3 unless ARERA amends the table. Easter Monday is computed.
_FIXED_HOLIDAYS: tuple[tuple[int, int], ...] = (
    (1, 1),  # Capodanno
    (1, 6),  # Epifania
    (4, 25),  # Festa della Liberazione
    (5, 1),  # Festa del Lavoro
    (6, 2),  # Festa della Repubblica
    (8, 15),  # Ferragosto
    (11, 1),  # Ognissanti
    (12, 8),  # Immacolata Concezione
    (12, 25),  # Natale
    (12, 26),  # Santo Stefano
)


def easter_sunday(year: int) -> date:
    """Return Easter Sunday for a Gregorian year (anonymous Gregorian algorithm)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7  # noqa: E741 - name from the algorithm
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return date(year, month, day + 1)


def national_holidays(year: int) -> frozenset[date]:
    """Return the holidays that count as F3 in a given year (ARERA list)."""
    days = {date(year, month, day) for month, day in _FIXED_HOLIDAYS}
    days.add(easter_sunday(year) + timedelta(days=1))  # Lunedì dell'Angelo
    return frozenset(days)


def band_at(moment: datetime) -> Band:
    """Return the band in force at a timezone-aware moment."""
    if moment.tzinfo is None:
        raise ValueError("moment must be timezone-aware")
    local = moment.astimezone(ITALY_TZ)
    day = local.date()
    hour = local.hour

    if day.weekday() == 6 or day in national_holidays(day.year):
        return Band.F3
    if hour < 7 or hour >= 23:
        return Band.F3
    if day.weekday() == 5:
        return Band.F2
    if 8 <= hour < 19:
        return Band.F1
    return Band.F2


def next_band_change(moment: datetime) -> tuple[datetime, Band]:
    """Return when the band next changes after ``moment`` and the new band.

    Bands only change on the hour. Italian UTC offsets are whole hours, so
    stepping one UTC hour at a time visits every local hour boundary, DST
    transitions included. At most one week ahead is ever needed.
    """
    if moment.tzinfo is None:
        raise ValueError("moment must be timezone-aware")
    current = band_at(moment)
    candidate = moment.astimezone(UTC).replace(minute=0, second=0, microsecond=0)
    for _ in range(24 * 8):
        candidate += timedelta(hours=1)
        band = band_at(candidate)
        if band != current:
            return candidate.astimezone(ITALY_TZ), band
    raise RuntimeError("no band change found within eight days")  # pragma: no cover
