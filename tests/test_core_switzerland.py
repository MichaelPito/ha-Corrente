"""Tests for Swiss operator tariffs, against real files published by Ticino operators."""

from __future__ import annotations

import json
from datetime import date, datetime, time
from pathlib import Path

import pytest

from custom_components.corrente.core.switzerland import (
    SWISS_TZ,
    SWISS_VAT,
    PriceWindow,
    SwissContract,
    UnsupportedTariffError,
    national_charges,
    parse_tariffs,
    price_of_windows,
    suggest_matching,
    tariffs_on,
)

FIXTURES = Path(__file__).parent / "fixtures" / "ch"
DAY_2027 = date(2027, 3, 10)  # a Wednesday


def load(name: str):
    # utf-8-sig: some operators publish files with a byte order mark (AMB).
    return parse_tariffs(json.loads((FIXTURES / name).read_text(encoding="utf-8-sig")))


def by_name(tariffs, name: str):
    return next(t for t in tariffs if t.name == name)


def zurich(*args: int) -> datetime:
    return datetime(*args, tzinfo=SWISS_TZ)


def test_national_charges() -> None:
    assert national_charges(2026) == pytest.approx(0.0303)
    assert national_charges(2027) == pytest.approx(0.0285)
    assert national_charges(2031) == national_charges(2027)


def test_ail_flat_tariff_price() -> None:
    ail = load("ail-2027.json")
    contract = SwissContract(
        electricity=by_name(ail, "Casa & PMI 24h-electricity"),
        grid=by_name(ail, "Casa & PMI 24h-grid7"),
        regional_fees=by_name(ail, "Casa & PMI 24h-regional_fees"),
        canton="TI",
    )
    expected = (0.0975 + 0.068 + 0.0102 + 0.012 + 0.0285) * (1 + SWISS_VAT)
    price, gap = contract.price_at(zurich(2027, 3, 10, 12, 0))
    assert price == pytest.approx(expected, abs=1e-5)
    assert not gap
    assert not contract.is_time_dependent()
    assert contract.period_at(zurich(2027, 3, 10, 12, 0)) == "single"
    assert contract.next_change(zurich(2027, 3, 10, 12, 0)) is None
    assert contract.monthly_fixed == pytest.approx(8.55 * (1 + SWISS_VAT), abs=0.01)


def test_ail_matches_elcom_totals_2027() -> None:
    """Recompute ElCom's published H4 components (4500 kWh/year) for AIL 2027."""
    ail = load("ail-2027.json")
    energy = by_name(ail, "Casa & PMI 24h tìacqua-electricity")
    grid = by_name(ail, "Casa & PMI 24h tìacqua-grid7")
    fees = by_name(ail, "Casa & PMI 24h tìacqua-regional_fees")
    noon = zurich(2027, 3, 10, 12, 0)

    energy_rp = 100 * sum(w.price for w in energy.energy)
    grid_rp = 100 * (grid.energy[0].price + grid.monthly_base * 12 / 4500)
    # Federal charges other than the 2.3 Rp grid surcharge belong to ElCom's grid usage.
    grid_rp += 100 * (national_charges(2027) - 0.023)
    fees_rp = 100 * sum(w.price for w in fees.windows_for(canton="TI") if w.covers(noon))

    assert energy_rp == pytest.approx(10.35, abs=0.01)  # ElCom "energy"
    assert grid_rp == pytest.approx(9.628, abs=0.01)  # ElCom "gridusage"
    assert fees_rp == pytest.approx(2.22, abs=0.01)  # ElCom "charge"


def test_ail_day_night_tariff() -> None:
    ail = load("ail-2027.json")
    contract = SwissContract(
        electricity=by_name(ail, "Casa & PMI giorno-notte-electricity"),
        grid=by_name(ail, "Casa & PMI giorno-notte-grid7"),
    )
    day, _ = contract.price_at(zurich(2027, 3, 10, 10, 0))
    night, _ = contract.price_at(zurich(2027, 3, 10, 23, 0))
    early, _ = contract.price_at(zurich(2027, 3, 10, 5, 0))
    assert day == pytest.approx((0.0975 + 0.068 + 0.0285) * (1 + SWISS_VAT), abs=1e-5)
    assert night == pytest.approx((0.086 + 0.061 + 0.0285) * (1 + SWISS_VAT), abs=1e-5)
    assert early == night
    assert contract.is_time_dependent()
    assert contract.period_at(zurich(2027, 3, 10, 10, 0)) == "high"
    assert contract.period_at(zurich(2027, 3, 10, 23, 0)) == "low"

    changes_at, new_price = contract.next_change(zurich(2027, 3, 10, 10, 0))
    assert changes_at == zurich(2027, 3, 10, 22, 0)
    assert new_price == night
    changes_at, _ = contract.next_change(zurich(2027, 3, 10, 23, 0))
    assert changes_at == zurich(2027, 3, 11, 6, 0)


def test_aim_weekday_and_weekend_windows() -> None:
    tariffs = load("aim-2026-2027.json")
    grids = tariffs_on(tariffs, "grid", DAY_2027)
    energy = tariffs_on(tariffs, "electricity", DAY_2027)
    assert len(grids) == 1 and len(energy) == 1
    contract = SwissContract(electricity=energy[0], grid=grids[0])

    high = (0.1088 + 0.1032 + 0.0285) * (1 + SWISS_VAT)
    low = (0.1088 + 0.0896 + 0.0285) * (1 + SWISS_VAT)
    assert contract.price_at(zurich(2027, 3, 10, 10, 0)) == (pytest.approx(high, abs=1e-5), False)
    assert contract.price_at(zurich(2027, 3, 10, 3, 0)) == (pytest.approx(low, abs=1e-5), False)
    assert contract.price_at(zurich(2027, 3, 10, 21, 0)) == (pytest.approx(low, abs=1e-5), False)
    assert contract.price_at(zurich(2027, 3, 13, 10, 0)) == (pytest.approx(low, abs=1e-5), False)

    changes_at, _ = contract.next_change(zurich(2027, 3, 10, 3, 0))
    assert changes_at == zurich(2027, 3, 10, 8, 0)
    # Friday evening: low until Monday 08:00.
    changes_at, _ = contract.next_change(zurich(2027, 3, 12, 21, 0))
    assert changes_at == zurich(2027, 3, 15, 8, 0)


def test_gap_in_schedule_uses_cheapest_window() -> None:
    windows = [
        PriceWindow(price=0.10, start=time(8, 0), end=time(20, 0)),
        PriceWindow(price=0.07, start=time(20, 0)),
    ]
    assert price_of_windows(windows, zurich(2027, 3, 10, 3, 0)) == (0.07, True)
    assert price_of_windows(windows, zurich(2027, 3, 10, 9, 0)) == (0.10, False)


def test_aim_file_mixes_years() -> None:
    tariffs = load("aim-2026-2027.json")
    assert tariffs_on(tariffs, "grid", date(2026, 6, 1)) != tariffs_on(tariffs, "grid", DAY_2027)


def test_amb_bom_and_flat_tariff() -> None:
    amb = load("amb-2027.json")
    electricity = next(t for t in amb if t.tariff_type == "electricity" and t.name == "Casa")
    grid = next(t for t in amb if t.tariff_type == "grid" and t.name == "Casa")
    contract = SwissContract(electricity=electricity, grid=grid)
    price, _ = contract.price_at(zurich(2027, 3, 10, 12, 0))
    assert price == pytest.approx((0.098 + 0.068 + 0.0285) * (1 + SWISS_VAT), abs=1e-5)


def test_amb_dynamic_without_windows_is_unsupported() -> None:
    amb = load("amb-2027.json")
    electricity = next(t for t in amb if t.tariff_type == "electricity" and t.name == "Dinamica")
    grid = next(t for t in amb if t.tariff_type == "grid" and t.name == "Dinamica")
    with pytest.raises(UnsupportedTariffError):
        SwissContract(electricity=electricity, grid=grid)


@pytest.mark.parametrize(
    ("fixture", "electricity_name", "expected_grid"),
    [
        ("ail-2027.json", "Casa & PMI giorno-notte-electricity", "Casa & PMI giorno-notte-grid7"),
        ("ail-2027.json", "Casa & PMI 24h-electricity", "Casa & PMI 24h-grid7"),
        (
            "aim-2026-2027.json",
            "Tariffa PC Piccoli clienti - Energia 2027",
            "Tariffa PC Piccoli clienti - Rete 2027",
        ),
        ("amb-2027.json", "Casa", "Casa"),
    ],
)
def test_suggest_matching_grid(fixture: str, electricity_name: str, expected_grid: str) -> None:
    tariffs = load(fixture)
    grids = tariffs_on(tariffs, "grid", DAY_2027)
    assert suggest_matching(electricity_name, grids).name == expected_grid


def test_naive_datetimes_are_rejected() -> None:
    ail = load("ail-2027.json")
    contract = SwissContract(
        electricity=by_name(ail, "Casa & PMI 24h-electricity"),
        grid=by_name(ail, "Casa & PMI 24h-grid7"),
    )
    with pytest.raises(ValueError):
        contract.price_at(datetime(2027, 3, 10, 12, 0))
