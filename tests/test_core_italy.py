"""Tests for the Italian time bands and fixed-price contracts (pure Python)."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from custom_components.corrente.core.contract import (
    ItalyContractType,
    ItalyFixedContract,
)
from custom_components.corrente.core.italy import (
    ITALY_TZ,
    Band,
    band_at,
    easter_sunday,
    national_holidays,
    next_band_change,
)


def rome(*args: int) -> datetime:
    return datetime(*args, tzinfo=ITALY_TZ)


@pytest.mark.parametrize(
    ("year", "expected"),
    [
        (2024, date(2024, 3, 31)),
        (2025, date(2025, 4, 20)),
        (2026, date(2026, 4, 5)),
        (2027, date(2027, 3, 28)),
    ],
)
def test_easter_sunday(year: int, expected: date) -> None:
    assert easter_sunday(year) == expected


def test_national_holidays() -> None:
    holidays_2026 = national_holidays(2026)
    assert date(2026, 4, 6) in holidays_2026  # Lunedì dell'Angelo
    assert date(2026, 12, 26) in holidays_2026
    assert len(holidays_2026) == 11
    # San Francesco is a national holiday again from 2026, but not in ARERA's list.
    assert date(2027, 10, 4) not in national_holidays(2027)


@pytest.mark.parametrize(
    ("moment", "expected"),
    [
        (rome(2026, 10, 7, 10, 0), Band.F1),  # Wednesday morning
        (rome(2026, 10, 7, 8, 0), Band.F1),
        (rome(2026, 10, 7, 18, 59), Band.F1),
        (rome(2026, 10, 7, 7, 30), Band.F2),
        (rome(2026, 10, 7, 19, 0), Band.F2),
        (rome(2026, 10, 7, 22, 59), Band.F2),
        (rome(2026, 10, 7, 23, 0), Band.F3),
        (rome(2026, 10, 7, 6, 59), Band.F3),
        (rome(2026, 10, 10, 10, 0), Band.F2),  # Saturday daytime
        (rome(2026, 10, 10, 23, 30), Band.F3),  # Saturday night
        (rome(2026, 10, 11, 12, 0), Band.F3),  # Sunday
        (rome(2026, 12, 25, 12, 0), Band.F3),  # Christmas, a Friday
        (rome(2026, 4, 6, 12, 0), Band.F3),  # Easter Monday
        (rome(2027, 10, 4, 12, 0), Band.F1),  # San Francesco 2027, a Monday: still F1
    ],
)
def test_band_at(moment: datetime, expected: Band) -> None:
    assert band_at(moment) is expected


def test_band_at_converts_to_italian_time() -> None:
    # 06:00 UTC is 08:00 in Rome during summer time.
    assert band_at(datetime(2026, 10, 7, 6, 0, tzinfo=UTC)) is Band.F1


def test_band_at_rejects_naive_datetimes() -> None:
    with pytest.raises(ValueError):
        band_at(datetime(2026, 10, 7, 10, 0))


@pytest.mark.parametrize(
    ("moment", "expected_at", "expected_band"),
    [
        (rome(2026, 10, 7, 10, 15), rome(2026, 10, 7, 19, 0), Band.F2),
        (rome(2026, 10, 9, 22, 30), rome(2026, 10, 9, 23, 0), Band.F3),
        (rome(2026, 10, 10, 22, 0), rome(2026, 10, 10, 23, 0), Band.F3),
        # Saturday night runs through Sunday to Monday 07:00.
        (rome(2026, 10, 10, 23, 30), rome(2026, 10, 12, 7, 0), Band.F2),
        # Same across the end of summer time (25 October 2026).
        (rome(2026, 10, 24, 23, 30), rome(2026, 10, 26, 7, 0), Band.F2),
    ],
)
def test_next_band_change(moment: datetime, expected_at: datetime, expected_band: Band) -> None:
    changes_at, band = next_band_change(moment)
    assert changes_at == expected_at
    assert changes_at.astimezone(ITALY_TZ).hour == expected_at.hour
    assert band is expected_band


def test_three_band_contract() -> None:
    contract = ItalyFixedContract(ItalyContractType.THREE_BANDS, 0.30, 0.25, 0.20)
    assert contract.price_at(rome(2026, 10, 7, 10, 0)) == 0.30
    assert contract.price_at(rome(2026, 10, 7, 20, 0)) == 0.25
    assert contract.price_at(rome(2026, 10, 11, 10, 0)) == 0.20


def test_two_band_contract_uses_f23_for_f2_and_f3() -> None:
    contract = ItalyFixedContract(ItalyContractType.TWO_BANDS, 0.30, 0.22)
    assert contract.price_for_band(Band.F1) == 0.30
    assert contract.price_for_band(Band.F2) == 0.22
    assert contract.price_for_band(Band.F3) == 0.22


def test_single_price_contract() -> None:
    contract = ItalyFixedContract(ItalyContractType.SINGLE, 0.27)
    assert {contract.price_for_band(band) for band in Band} == {0.27}


@pytest.mark.parametrize(
    "kwargs",
    [
        {"contract_type": ItalyContractType.TWO_BANDS, "price_f1": 0.3},
        {"contract_type": ItalyContractType.THREE_BANDS, "price_f1": 0.3, "price_f2": 0.2},
        {"contract_type": ItalyContractType.SINGLE, "price_f1": -0.1},
    ],
)
def test_invalid_contracts(kwargs: dict) -> None:
    with pytest.raises(ValueError):
        ItalyFixedContract(**kwargs)
