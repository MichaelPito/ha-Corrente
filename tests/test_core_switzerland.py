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
    canton_of,
    federal_addition,
    national_charges,
    parse_tariffs,
    price_of_windows,
    suggest_grid,
    suggest_matching,
    suggest_regional_fees,
    tariffs_on,
)

FIXTURES = Path(__file__).parent / "fixtures" / "ch"
DAY_2027 = date(2027, 3, 10)  # a Wednesday
EWZ_DAY = date(2026, 10, 13)


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


@pytest.mark.parametrize(
    ("fixture", "day", "municipality", "place", "electricity_name", "expected_grid"),
    [
        # Unchanged from the name-only suggestion.
        ("ail-2027.json", DAY_2027, 5192, "Lugano", "Casa & PMI giorno-notte-electricity",
         "Casa & PMI giorno-notte-grid7"),
        ("ail-2027.json", DAY_2027, 5192, "Lugano", "Casa & PMI 24h tìacqua-electricity",
         "Casa & PMI 24h tìacqua-grid7"),
        ("amb-2027.json", DAY_2027, 5002, "Bellinzona", "Casa", "Casa"),
        ("groupe-e-2026.json", date(2026, 10, 13), 2196, "Fribourg",
         "Tarif double BASIC énergie / Doppeltarif BASIC Energie",
         "Tarif double réseau / Doppeltarif Netz"),
        # EKZ: the standard household grid, and the dynamic grid for the dynamic energy.
        ("ekz-2026.json", date(2026, 10, 13), 243, "Dietikon", "EKZ Energie Erneuerbar",
         "EKZ Netz 400ST + SDL, Stromreserve, Solidarisierte Kosten, Bundesabgaben"),
        ("ekz-2026.json", date(2026, 10, 13), 243, "Dietikon", "EKZ Energie Dynamisch",
         "EKZ Netz 400D + SDL, Stromreserve, Solidarisierte Kosten, Bundesabgaben"),
        # ewz: the city of Zürich or Graubünden, from where the user lives.
        ("ewz-2026.json", date(2026, 10, 13), 261, "Zürich", "ewz.natur", "NNA_ZH"),
        ("ewz-2026.json", date(2026, 10, 13), 3661, "Cazis", "ewz.natur", "NNA_GR"),
    ],
)  # fmt: skip
def test_suggest_grid(
    fixture: str,
    day: date,
    municipality: int,
    place: str,
    electricity_name: str,
    expected_grid: str,
) -> None:
    tariffs = load(fixture)
    electricity = by_name(tariffs_on(tariffs, "electricity", day), electricity_name)
    grid = suggest_grid(electricity, tariffs_on(tariffs, "grid", day), municipality, place)
    assert grid.name == expected_grid


@pytest.mark.parametrize(
    ("municipality", "expected"), [(261, "A&L Stadt Zürich"), (3661, "A&L Cazis")]
)
def test_suggest_regional_fees_for_the_municipality(municipality: int, expected: str) -> None:
    tariffs = load("ewz-2026.json")
    day = date(2026, 10, 13)
    electricity = by_name(tariffs, "ewz.natur")
    fees = suggest_regional_fees(
        electricity, tariffs_on(tariffs, "regional_fees", day), municipality
    )
    assert fees.name == expected


def test_place_is_a_whole_word() -> None:
    # A municipality called "Au" is not named in "Haushalt": the standard grid stays first.
    tariffs = load("ewz-2026.json")
    day = date(2026, 10, 13)
    electricity = by_name(tariffs, "ewz.natur")
    grid = suggest_grid(electricity, tariffs_on(tariffs, "grid", day), None, "Au")
    assert grid.name == "NNA_ZH"


@pytest.mark.parametrize(
    ("municipality", "canton"),
    [(1, "ZH"), (261, "ZH"), (351, "BE"), (2196, "FR"), (3661, "GR"), (5192, "TI"),
     (6621, "GE"), (6831, "JU"), (9051, None), (0, None), (None, None)],
)  # fmt: skip
def test_canton_of(municipality: int | None, canton: str | None) -> None:
    assert canton_of(municipality) == canton


def test_naive_datetimes_are_rejected() -> None:
    ail = load("ail-2027.json")
    contract = SwissContract(
        electricity=by_name(ail, "Casa & PMI 24h-electricity"),
        grid=by_name(ail, "Casa & PMI 24h-grid7"),
    )
    with pytest.raises(ValueError):
        contract.price_at(datetime(2027, 3, 10, 12, 0))


def _flat_grid(price: float, monthly_base: float = 0.0):
    """A flat grid tariff, as operators publish them."""
    return parse_tariffs(
        {
            "tariffs": [
                {
                    "tariffName": "grid",
                    "tariffType": "grid",
                    "tariffForm": "constant",
                    "startDate": "2027-01-01",
                    "endDate": "2027-12-31",
                    "prices": {
                        "base": {"price": monthly_base, "priceUnit": "CHF/M"},
                        "energy": [
                            {"from": "00:00", "to": "00:00", "price": price, "priceUnit": "CHF/kWh"}
                        ],
                    },
                }
            ]
        }
    )


def test_federal_addition_ail_leaves_charges_out() -> None:
    """AIL 2027: grid 6.8 Rp + 8.55 CHF/month vs ElCom 9.628 + 2.3: all charges must be added."""
    grids = tariffs_on(load("ail-2027.json"), "grid", DAY_2027)
    assert federal_addition(grids, 9.628, 2.3, 2027) == pytest.approx(national_charges(2027))


def test_federal_addition_ekz_includes_charges() -> None:
    """EKZ 2027 "Netz 400F + SDL, Stromreserve, Solidarisierte Kosten": 10.2 Rp vs ElCom 7.9."""
    assert federal_addition(_flat_grid(0.102), 7.9, 2.3, 2027) == 0.0


def test_federal_addition_prefers_the_chosen_tariff() -> None:
    """EKZ 2026: "400F" (households) includes the surcharge, "400LS" (businesses) matches
    ElCom without it. The user's own tariff decides."""
    household = _flat_grid(0.1053)[0]
    business = _flat_grid(0.0823)[0]
    grids = [household, business]
    assert federal_addition(grids, 8.23, 2.3, 2026, chosen=household) == 0.0
    assert federal_addition(grids, 8.23, 2.3, 2026, chosen=business) == pytest.approx(0.023)


def test_federal_addition_surcharge_only() -> None:
    assert federal_addition(_flat_grid(0.079), 7.9, 2.3, 2027) == pytest.approx(0.023)


def test_federal_addition_without_flat_grid() -> None:
    assert federal_addition([], 7.9, 2.3, 2027) is None


def test_federal_addition_with_day_night_grids_only() -> None:
    """ewz 2026, city of Zürich: all grid tariffs are day/night. "NNA_ZH" (14.95 / 9 Rp)
    averages about 12.4 Rp against ElCom's 10.735 + 2.3: the charges are included."""
    grids = tariffs_on(load("ewz-2026.json"), "grid", EWZ_DAY)
    chosen = by_name(grids, "NNA_ZH")
    assert federal_addition(grids, 10.735, 2.3, 2026, chosen=chosen) == 0.0


def _ewz_zurich() -> SwissContract:
    ewz = load("ewz-2026.json")
    return SwissContract(
        electricity=by_name(ewz, "ewz.natur"),
        grid=by_name(ewz, "NNA_ZH"),
        regional_fees=by_name(ewz, "A&L Stadt Zürich"),
        municipality=261,
        federal_per_kwh=0.0,
    )


def test_ewz_day_night_and_sunday() -> None:
    """Monday to Saturday 06:00-22:00 is high; nights and the whole of Sunday are low.

    ewz writes the windows as "06:00"-"21:59" and gives Sunday as a whole day on its
    own: Sunday's price must not be added on top of the night price.
    """
    contract = _ewz_zurich()
    high = (0.093 + 0.1495 + 0.02) * (1 + SWISS_VAT)
    low = (0.049 + 0.09 + 0.02) * (1 + SWISS_VAT)
    tuesday = zurich(2026, 10, 13, 16, 20)
    assert contract.price_at(tuesday) == (pytest.approx(high, abs=1e-5), False)
    assert contract.price_at(zurich(2026, 10, 13, 21, 59, 30)) == (
        pytest.approx(high, abs=1e-5),
        False,
    )
    assert contract.price_at(zurich(2026, 10, 18, 12, 0)) == (pytest.approx(low, abs=1e-5), False)
    assert contract.period_at(tuesday) == "high"
    assert contract.period_at(zurich(2026, 10, 13, 23, 0)) == "low"
    change, price = contract.next_change(tuesday)
    assert change == zurich(2026, 10, 13, 22, 0)
    assert price == pytest.approx(low, abs=1e-5)


def test_contract_uses_the_checked_federal_addition() -> None:
    ail = load("ail-2027.json")
    contract = SwissContract(
        electricity=by_name(ail, "Casa & PMI 24h-electricity"),
        grid=by_name(ail, "Casa & PMI 24h-grid7"),
        federal_per_kwh=0.0,
    )
    price, _ = contract.price_at(zurich(2027, 3, 10, 12, 0))
    assert price == pytest.approx((0.0975 + 0.068) * (1 + SWISS_VAT), abs=1e-5)
