"""Tests for Swiss operator tariffs, against real files published by Ticino operators."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import date, datetime, time
from pathlib import Path

import pytest

from custom_components.corrente.coordinator import ElcomCheck, select_contract
from custom_components.corrente.core.switzerland import (
    SWISS_TZ,
    SWISS_VAT,
    PriceWindow,
    SwissContract,
    Tariff,
    UnsupportedTariffError,
    _is_federal_charge,
    _is_large_consumer,
    _names_place,
    canton_of,
    federal_addition,
    metering_per_month,
    missing_fees,
    national_charges,
    parse_tariffs,
    price_of_windows,
    suggest_grid,
    suggest_matching,
    suggest_regional_fees,
    tariffs_on,
    yearly_fee_as_monthly,
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


def test_ekz_seasonal_prices_are_supported() -> None:
    """EKZ "Erneuerbar" 2026, the standard household tariff: 13.3 Rp in winter, 9 in summer,
    each as a whole-day price. It was rejected as "time windows missing" up to 0.2.1."""
    ekz = load("ekz-2026.json")
    contract = SwissContract(
        electricity=by_name(ekz, "EKZ Energie Erneuerbar"),
        grid=next(t for t in ekz if t.name.startswith("EKZ Netz 400ST")),
        federal_per_kwh=0.0,
    )
    winter, _ = contract.price_at(zurich(2026, 10, 13, 12, 0))
    summer, _ = contract.price_at(zurich(2026, 7, 14, 12, 0))
    assert winter - summer == pytest.approx((0.133 - 0.09) * (1 + SWISS_VAT), abs=1e-6)
    assert contract.period_at(zurich(2026, 10, 13, 12, 0)) == "single"


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
    assert [fee.name for fee in fees] == [expected]


def test_single_rate_price_inside_a_day_night_tariff_is_not_added() -> None:
    """St. Gallen "Netztarif K" 2026: day 13.73, night 11.83 and, in the same tariff, the
    single-rate 13.13 as an all-day price. Added up, the grid would cost twice as much."""
    sgsw = load("sgsw-2026.json")
    contract = SwissContract(
        electricity=by_name(sgsw, "St.Galler Strom Basis <50 MWh/a"),
        grid=next(t for t in sgsw if t.tariff_type == "grid" and t.name == "Netztarif K"),
        federal_per_kwh=0.0,
    )
    price, _ = contract.price_at(zurich(2026, 10, 13, 10, 0))  # Tuesday, day
    assert price == pytest.approx((0.15 + 0.1373) * (1 + SWISS_VAT), abs=1e-5)


def test_grid_suggestion_checked_with_elcom() -> None:
    """St. Gallen: energy and grid describe their customers differently, and reactive
    energy prices are grid tariffs too. ElCom's household grid figure (11.25 Rp. + 2.3)
    points to the household tariff."""
    sgsw = load("sgsw-2026.json")
    day = EWZ_DAY
    electricity = by_name(sgsw, "St.Galler Strom Basis <50 MWh/a")
    grids = tariffs_on(sgsw, "grid", day)
    grid = suggest_grid(electricity, grids, 3203, "St. Gallen", (11.25, 2.3, 2026))
    assert grid.name == "Netztarif K"
    fees = suggest_regional_fees(
        electricity, tariffs_on(sgsw, "regional_fees", day), 3203, 1.76, 2026, grid
    )
    assert [fee.name for fee in fees] == ["Netztarif K"]


def test_geneva_grid_is_not_the_separate_reserve() -> None:
    """SIG publishes the "réserve d'électricité" (0.46 Rp.) as a grid tariff of its own."""
    sig = load("sig-2026.json")
    electricity = next(t for t in sig if t.tariff_type == "electricity")
    grid = suggest_grid(
        electricity, tariffs_on(sig, "grid", EWZ_DAY), 6621, "Genève", (9.877, 2.3, 2026)
    )
    assert grid.name == "Utilisation du réseau - Profil Simple"


def test_lausanne_fees_add_up() -> None:
    """Lausanne publishes each fee on its own; ElCom's household fees are 4.924 Rp."""
    sil = load("sil-2026.json")
    electricity = by_name(sil, "nativa - Energie - SIMPLE - 2026")
    regionals = tariffs_on(sil, "regional_fees", EWZ_DAY)
    fees = suggest_regional_fees(electricity, regionals, 5586, 4.924, 2026)
    assert len(fees) == len(regionals) == 6
    contract = SwissContract(
        electricity=electricity,
        grid=by_name(sil, "nativa - Utilisation du réseau - SIMPLE - 2026"),
        regional_fees=fees,
        canton="VD",
        municipality=5586,
        federal_per_kwh=0.0,
    )
    alone = SwissContract(
        electricity=electricity,
        grid=by_name(sil, "nativa - Utilisation du réseau - SIMPLE - 2026"),
        federal_per_kwh=0.0,
    )
    moment = zurich(2026, 10, 13, 12, 0)
    fees_rp = 100 * (contract.price_at(moment)[0] - alone.price_at(moment)[0]) / (1 + SWISS_VAT)
    assert fees_rp == pytest.approx(4.924, abs=0.1)


def test_one_set_of_fees_per_product_is_not_added_up() -> None:
    """AIL publishes one set of fees per product: ElCom's 2.22 Rp. means one of them."""
    ail = load("ail-2027.json")
    electricity = by_name(ail, "Casa & PMI 24h-electricity")
    fees = suggest_regional_fees(
        electricity, tariffs_on(ail, "regional_fees", DAY_2027), 5192, 2.22, 2027
    )
    assert [fee.name for fee in fees] == ["Casa & PMI 24h-regional_fees"]


def _fees_rp(fees, canton: str | None, municipality: int, name: str | None = None) -> float:
    windows = [w for fee in fees for w in fee.windows_for(canton, municipality, name)]
    return 100 * sum(w.price for w in windows if w.every_day)


def test_bkw_fees_by_municipality_name() -> None:
    """BKW numbers municipalities its own way ("15040 Ittigen"; federal number 362) and
    gives every municipality's fees the same name. ElCom: 1.5 Rp. for Ittigen."""
    bkw = load("bkw-2026.json")
    electricity = by_name(bkw, "Energy Blue")
    regionals = tariffs_on(bkw, "regional_fees", EWZ_DAY)
    fees = suggest_regional_fees(electricity, regionals, 362, 1.5, 2026, None, "Ittigen")
    assert _fees_rp(fees, "BE", 362, "Ittigen") == pytest.approx(1.5)


def test_bkw_fee_in_the_price() -> None:
    """The fee found by the municipality's name is in the price (1.5 Rp. in Ittigen)."""
    bkw = load("bkw-2026.json")
    fee = next(
        t
        for t in tariffs_on(bkw, "regional_fees", EWZ_DAY)
        if t.municipality_key(362, "Ittigen", "BE") is not None
    )

    def price(regional_fees) -> float:
        contract = SwissContract(
            electricity=by_name(bkw, "Energy Blue"),
            grid=next(t for t in bkw if t.tariff_type == "grid"),
            regional_fees=regional_fees,
            canton="BE",
            municipality=362,
            municipality_name="Ittigen",
            federal_per_kwh=0.0,
        )
        return contract.price_at(zurich(2026, 10, 14, 10, 0))[0]

    assert 100 * (price(fee) - price(None)) / (1 + SWISS_VAT) == pytest.approx(1.5)


def test_federal_charges_listed_as_fees_are_left_out() -> None:
    """Energie Thun lists the federal charges (Netzzuschlag...) as cantonal fees; Corrente
    adds them itself, so only the city's 2.8 Rp. remain (ElCom: 2.8)."""
    thun = load("energie-thun-2026.json")
    fee = tariffs_on(thun, "regional_fees", EWZ_DAY)[0]
    assert fee.canton_energy == {}
    assert _fees_rp([fee], "BE", 942) == pytest.approx(2.8)


def test_fee_written_in_chf_instead_of_rp() -> None:
    """Yverdon gives its 2 Rp. fee as 2 CHF/kWh (and its postal code as the number)."""
    yverdon = load("yverdon-2026.json")
    fee = tariffs_on(yverdon, "regional_fees", EWZ_DAY)[0]
    assert _fees_rp([fee], "VD", 5938, "Yverdon-les-Bains") == pytest.approx(2.624)


def test_large_consumer_fee_tier_is_left_out() -> None:
    """Winterthur: 0.9 Rp. up to 100'000 kWh and 0.6 Rp. above, as two entries (ElCom 0.9)."""
    fee = tariffs_on(load("winterthur-2026.json"), "regional_fees", EWZ_DAY)[0]
    assert _fees_rp([fee], "ZH", 230) == pytest.approx(0.9)


@pytest.mark.parametrize(
    ("comment", "large"),
    [
        ("ab 101'000 kWh", True),  # Winterthur's second tier
        ("bis 100'000 kWh", False),
        # AIM: one entry describing both tiers of the household's fee.
        ("FER FINO A 500 MWh/anno : 1.20 cts/kWh ; eccedenza oltre 500 MWh/anno : 0.00", False),
        ("Abgaben und Leistungen an die Stadt Thun", False),
    ],
)
def test_large_consumer_comments(comment: str, large: bool) -> None:
    assert _is_large_consumer(comment) is large


def test_fees_for_the_whole_canton() -> None:
    """EWO lists its fees under "6 Obwalden", the canton. ElCom for Sarnen: 1.4 Rp."""
    ewo = load("ewo-2026.json")
    electricity = by_name(ewo, "EWO NaturStrom Basis")
    grid = by_name(ewo, "EWO Basis Netz")
    fees = suggest_regional_fees(
        electricity, tariffs_on(ewo, "regional_fees", EWZ_DAY), 1407, 1.4, 2026, grid, "Sarnen"
    )
    assert _fees_rp(fees, "OW", 1407, "Sarnen") == pytest.approx(1.4)
    # A municipality called like a canton is not that canton: Zürich city is not ZH.
    assert fees[0].municipality_key(261, "Zürich", "ZH") is None


def test_federal_addition_from_the_users_day_night_tariff() -> None:
    """ebs (Schwyz): the household grid "N-Casa" is day/night; the only flat one is for
    building sites and pointed to "charges included". N-Casa + 3.03 fits ElCom's 13.03."""
    ebs = load("ebs-2026.json")
    grids = tariffs_on(ebs, "grid", EWZ_DAY)
    chosen = by_name(grids, "N-Casa")
    assert federal_addition(grids, 10.729, 2.3, 2026, chosen=chosen) == pytest.approx(0.0303)


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


# Found by the code review of 0.2.2 (16 October 2026).


def _fee(
    name: str, windows, *, canton=None, municipality=None, municipality_names=None, energy=()
) -> Tariff:
    return Tariff(
        name=name,
        tariff_type="regional_fees",
        form="constant",
        start_date=date(2026, 1, 1),
        end_date=date(2027, 12, 31),
        customer_type="",
        energy=tuple(energy),
        monthly_base=0.0,
        canton_energy={canton: tuple(windows)} if canton else {},
        municipality_energy={municipality: tuple(windows)} if municipality else {},
        municipality_names=municipality_names or {},
    )


def _day_night(day: float, night: float) -> tuple[PriceWindow, ...]:
    return (
        PriceWindow(price=day, start=time(6, 0), end=time(22, 0)),
        PriceWindow(price=night, start=time(22, 0), end=time(6, 0)),
    )


def test_several_day_night_fees_add_up() -> None:
    """Two fees, each with day and night windows, are priced separately and added up
    (merged into one tariff, their windows overlapped and the price failed)."""
    ail = load("ail-2027.json")
    fees = (
        _fee("A", _day_night(0.02, 0.01), municipality=5192),
        _fee("B", _day_night(0.004, 0.002), municipality=5192),
    )

    def price(regional_fees) -> float:
        return SwissContract(
            electricity=by_name(ail, "Casa & PMI 24h-electricity"),
            grid=by_name(ail, "Casa & PMI 24h-grid7"),
            regional_fees=regional_fees,
            municipality=5192,
            federal_per_kwh=0.0,
        ).price_at(zurich(2027, 3, 10, 12, 0))[0]

    assert price(fees) - price(None) == pytest.approx(0.024 * (1 + SWISS_VAT), abs=1e-6)


def test_seasonal_flat_price_is_not_a_single_rate_alternative() -> None:
    """A summer all-day price between the winter day and night prices is a season of its
    own, not St. Gallen's single-rate alternative."""
    document = {
        "tariffs": [
            {
                "tariffName": "Saison",
                "tariffType": "electricity",
                "tariffForm": "multilevel",
                "startDate": "2026-01-01",
                "endDate": "2026-12-31",
                "prices": {
                    "energy": [
                        {"months": ["Jan", "Feb", "Mar", "Oct", "Nov", "Dec"], "from": "06:00",
                         "to": "22:00", "price": 0.12, "priceUnit": "CHF/kWh"},
                        {"months": ["Jan", "Feb", "Mar", "Oct", "Nov", "Dec"], "from": "22:00",
                         "to": "06:00", "price": 0.08, "priceUnit": "CHF/kWh"},
                        {"months": ["Apr", "May", "Jun", "Jul", "Aug", "Sep"], "from": "00:00",
                         "to": "00:00", "price": 0.10, "priceUnit": "CHF/kWh"},
                    ]
                },
            }
        ]
    }  # fmt: skip
    tariff = parse_tariffs(document)[0]
    assert [w.price for w in tariff.energy] == [0.12, 0.08, 0.10]


def test_fees_with_one_name_follow_the_place_not_the_file_order() -> None:
    """EKZ: same-named fees for the canton and for one municipality elsewhere."""
    ail = load("ail-2027.json")
    elsewhere = _fee("Abgaben", [PriceWindow(price=0.05)], municipality=1701)
    canton = _fee("Abgaben", [PriceWindow(price=0.0016)], canton="ZH")
    options = {
        "electricity_tariff": "Casa & PMI 24h-electricity",
        "grid_tariff": "Casa & PMI 24h-grid7",
        "regional_tariff": ["Abgaben"],
        "municipality": 243,
        "canton": "ZH",
    }
    contract = select_contract([*ail, elsewhere, canton], options, DAY_2027)
    assert contract.regional_fees == (canton,)


def test_municipality_name_without_the_canton() -> None:
    """ElCom writes "Kirchdorf (BE)", BKW's file "Kirchdorf"."""
    fee = _fee("K", [PriceWindow(price=0.015)], municipality=15050,
               municipality_names={"kirchdorf": 15050})  # fmt: skip
    assert fee.municipality_key(434, "Kirchdorf (BE)", "BE") == 15050


def test_fees_for_everywhere_count_with_the_local_ones() -> None:
    ail = load("ail-2027.json")
    electricity = by_name(ail, "Casa & PMI 24h-electricity")
    local = _fee("Comune", [PriceWindow(price=0.01)], municipality=5192)
    everywhere = _fee("Tutti", [], energy=[PriceWindow(price=0.005)])
    fees = suggest_regional_fees(electricity, [local, everywhere], 5192, 1.5, 2027)
    assert {fee.name for fee in fees} == {"Comune", "Tutti"}


@pytest.mark.parametrize(
    ("name", "canton", "expected"),
    [
        ("NNA_GR", "GR", True),
        ("NNE-H_ZH", "ZH", True),
        ("Netz EWA AG Haushalt", "AG", False),  # Aktiengesellschaft
        ("Netznutzung NE7", "NE", False),  # network level 7
    ],
)
def test_canton_codes_in_tariff_names(name: str, canton: str, expected: bool) -> None:
    grid = _fee(name, [])
    assert _names_place(grid, "", canton) is expected


@pytest.mark.parametrize(
    ("comment", "federal"),
    [
        ("Netzzuschlag", True),
        ("Systemdienstleistungen", True),
        ("Abgabe an die Gemeinde (ohne Netzzuschlag)", False),
        ("Taxe communale, hors supplément réseau", False),
        ("Abgaben und Leistungen an die Stadt Thun", False),
    ],
)
def test_federal_charge_comments(comment: str, federal: bool) -> None:
    assert _is_federal_charge(comment) is federal


def test_ewz_low_weekend_across_the_autumn_clock_change() -> None:
    """25 October 2026 (clocks go back, a Sunday): Saturday 22:00 summer time to Monday
    06:00 winter time is one low segment of 33 real hours."""
    contract = _ewz_zurich()
    saturday_night = zurich(2026, 10, 24, 23, 0)
    change, _ = contract.next_change(saturday_night)
    assert change == zurich(2026, 10, 26, 6, 0)
    low = contract.schedule(zurich(2026, 10, 24, 12, 0), zurich(2026, 10, 27))[1]
    assert low.start == zurich(2026, 10, 24, 22, 0)
    assert low.end.timestamp() - low.start.timestamp() == 33 * 3600


def test_night_across_the_spring_clock_change() -> None:
    """28 March 2027 (clocks go forward at 02:00): the night 22:00-06:00 lasts 7 real hours
    and the day price starts at 06:00 summer time."""
    ail = load("ail-2027.json")
    contract = SwissContract(
        electricity=by_name(ail, "Casa & PMI 24h-electricity"),
        grid=by_name(ail, "Casa & PMI 24h-grid7"),
        regional_fees=_fee("A", _day_night(0.02, 0.01), municipality=5192),
        municipality=5192,
        federal_per_kwh=0.0,
    )
    night = contract.schedule(zurich(2027, 3, 27, 12, 0), zurich(2027, 3, 28, 12, 0))[1]
    assert night.start == zurich(2027, 3, 27, 22, 0)
    assert night.end == zurich(2027, 3, 28, 6, 0)
    assert night.end.timestamp() - night.start.timestamp() == 7 * 3600
    assert contract.period_at(zurich(2027, 3, 28, 3, 30)) == "low"


def test_grid_price_in_rp_written_as_chf() -> None:
    """Romande Energie 2027, grid "Double": the weekday price up to 17:00 is written as
    10.62 CHF/kWh. Read as 10.62 Rp., like the night and weekend price of the same tariff."""
    tariffs = load("romande-energie-2027-double.json")
    grid = by_name(tariffs, "Double")
    assert max(window.price for window in grid.energy) == pytest.approx(0.1644)
    contract = SwissContract(
        electricity=by_name(tariffs, "Double Energie Suisse"),
        grid=grid,
        federal_per_kwh=0.0,
    )
    low = (0.1199 + 0.1062) * (1 + SWISS_VAT)
    high = (0.1693 + 0.1644) * (1 + SWISS_VAT)
    assert contract.price_at(zurich(2027, 3, 10, 10, 0))[0] == pytest.approx(low, abs=1e-5)
    assert contract.price_at(zurich(2027, 3, 10, 18, 0))[0] == pytest.approx(high, abs=1e-5)
    assert contract.price_at(zurich(2027, 3, 13, 10, 0))[0] == pytest.approx(low, abs=1e-5)


def test_federal_charges_from_own_day_night_tariff_before_building_sites() -> None:
    """ebs (Schwyz) 2027: the household grid "N-Casa" is seasonal day/night and leaves the
    federal charges out (ElCom: 10.45 + 2.3 Rp.). The only flat grid tariff is for building
    sites, 90 CHF a month: compared with it, the charges looked included (3.5 Rp. too low)."""
    grids = tariffs_on(load("ebs-2027.json"), "grid", DAY_2027)
    chosen = by_name(grids, "N-Casa")
    assert federal_addition(grids, 10.45, 2.3, 2027, chosen=chosen) == national_charges(2027)


def test_monthly_part_of_a_municipal_fee_counts_in_fixed_charges() -> None:
    """OIKEN 2027: the municipal fee in Sion is 0.732 Rp./kWh plus 0.84 CHF a month."""
    oiken = load("oiken-2027.json")
    fee = by_name(tariffs_on(oiken, "regional_fees", DAY_2027), "Tarif Simple")
    contract = SwissContract(
        electricity=by_name(tariffs_on(oiken, "electricity", DAY_2027), "Tarif Simple"),
        grid=by_name(tariffs_on(oiken, "grid", DAY_2027), "Tarif Simple"),
        regional_fees=fee,
        municipality=6266,
        municipality_name="Sion",
    )
    assert contract.monthly_fixed == pytest.approx((3 + 7 + 0.84) * (1 + SWISS_VAT), abs=0.01)
    assert fee.base_for("VS", 9999) == 0.0  # not one of OIKEN's municipalities


# Found comparing every operator with ElCom for 2027 (20 October 2026).

_WORKDAYS = ["Mo", "Tu", "We", "Th", "Fr"]
_EVERY_DAY = [*_WORKDAYS, "Sa", "Su"]


def _one_tariff(energy: list[dict], form: str = "multilevel") -> Tariff:
    """A tariff from its "energy" price list, as written in an operator's file."""
    document = {
        "tariffs": [
            {
                "tariffName": "T",
                "tariffType": "grid",
                "tariffForm": form,
                "startDate": "2027-01-01",
                "endDate": "2027-12-31",
                "prices": {
                    "base": {"price": 0, "priceUnit": "CHF/M"},
                    "energy": [{"priceUnit": "CHF/kWh", **window} for window in energy],
                },
            }
        ]
    }
    return parse_tariffs(document)[0]


def test_single_rate_written_twice_is_one_price() -> None:
    """Gsteig, Egerkingen, Bürglen 2027: a single rate as a high/low tariff with the same
    whole-day price twice. It was rejected ("time windows missing")."""
    whole_day = {"weekdays": _EVERY_DAY, "from": "00:00", "to": "00:00", "price": 0.1585}
    tariff = _one_tariff([whole_day, whole_day])
    tariff.check_supported()
    assert price_of_windows(tariff.energy, zurich(2027, 3, 10, 12, 0)) == (0.1585, False)


def test_repeated_surcharge_next_to_other_prices_still_adds_up() -> None:
    """Herzogenbuchsee 2027 grid: winter and summer prices, plus three small charges for
    the whole year, two of them at 0.19 Rp. Both count."""
    year = {"weekdays": _EVERY_DAY, "from": "00:00", "to": "23:59"}
    winter = ["Jan", "Feb", "Mar", "Oct", "Nov", "Dec"]
    summer = ["Apr", "May", "Jun", "Jul", "Aug", "Sep"]
    tariff = _one_tariff(
        [
            {**year, "months": winter, "price": 0.0965},
            {**year, "months": summer, "price": 0.0725},
            {**year, "price": 0.0019},
            {**year, "price": 0.0017},
            {**year, "price": 0.0019},
        ]
    )
    tariff.check_supported()
    price, _ = price_of_windows(tariff.energy, zurich(2027, 1, 13, 12, 0))
    assert price == pytest.approx(0.0965 + 0.0055)
    price, _ = price_of_windows(tariff.energy, zurich(2027, 7, 14, 12, 0))
    assert price == pytest.approx(0.0725 + 0.0055)


def test_part_of_a_day_inside_the_whole_day_wins() -> None:
    """Dietlikon 2027 grid: Saturday 07:00-13:00 at 7.22 Rp. and the whole of Saturday at
    5.48 Rp. (meaning the rest of it). Diessenhofen: the same, at one price."""
    tariff = _one_tariff(
        [
            {"weekdays": _WORKDAYS, "from": "07:00", "to": "20:00", "price": 0.0722},
            {"weekdays": _WORKDAYS, "from": "20:00", "to": "07:00", "price": 0.0548},
            {"weekdays": ["Sa"], "from": "07:00", "to": "13:00", "price": 0.0722},
            {"weekdays": ["Sa"], "from": "00:00", "to": "00:00", "price": 0.0548},
            {"weekdays": ["Su"], "from": "00:00", "to": "00:00", "price": 0.0548},
        ]
    )
    tariff.check_supported()
    saturday = 13
    assert price_of_windows(tariff.energy, zurich(2027, 3, saturday, 9, 0))[0] == 0.0722
    assert price_of_windows(tariff.energy, zurich(2027, 3, saturday, 15, 0))[0] == 0.0548


def test_overlapping_prices_without_months_are_unsupported() -> None:
    """Merenschwand 2027 left out the months of its winter and summer prices: the same
    hours have two prices. The tariff is not offered rather than failing later."""
    tariff = _one_tariff(
        [
            {"weekdays": _EVERY_DAY, "from": "18:00", "to": "09:00", "price": 0.0935},
            {"weekdays": _EVERY_DAY, "from": "09:00", "to": "18:00", "price": 0.0935},
            {"weekdays": _EVERY_DAY, "from": "09:00", "to": "18:00", "price": 0.0655},
            {"weekdays": _EVERY_DAY, "from": "18:00", "to": "09:00", "price": 0.0795},
        ]
    )
    with pytest.raises(UnsupportedTariffError, match="overlapping"):
        tariff.check_supported()


def test_federal_charges_checked_without_the_monthly_fee() -> None:
    """Spreitenbach 2027 writes its yearly grid fee (66 CHF, ElCom) as 66 CHF a month.
    With the fee in, the charges looked included; ElCom's grid price per kWh without
    fees (5.43 Rp.) shows they are not (2.85 Rp. were missing)."""
    grids = tariffs_on(load("spreitenbach-2027.json"), "grid", DAY_2027)
    chosen = by_name(grids, "Strom KN Netznutzung")
    assert federal_addition(grids, 7.443, 2.3, 2027, chosen=chosen) == 0.0  # the old answer
    addition = federal_addition(grids, 7.443, 2.3, 2027, chosen=chosen, elcom_working_rp=5.426)
    assert addition == national_charges(2027)


def test_yearly_grid_fee_written_as_monthly() -> None:
    """Spreitenbach 2027 writes 66 CHF a month; ElCom's household fixed costs are
    66 CHF a year. Other grids of the file, and a fee unlike ElCom's, stay as they are."""
    tariffs = load("spreitenbach-2027.json")
    kn = by_name(tariffs, "Strom KN Netznutzung")
    assert yearly_fee_as_monthly(kn, 66.0) == 5.5
    assert yearly_fee_as_monthly(kn, 66.4) == 5.5333  # rounding in ElCom's figure
    assert yearly_fee_as_monthly(kn, 120.0) is None
    assert yearly_fee_as_monthly(kn, None) is None
    assert yearly_fee_as_monthly(by_name(tariffs, "Strom KN Energie"), 66.0) is None
    options = {
        "electricity_tariff": "Strom KN Energie",
        "grid_tariff": "Strom KN Netznutzung",
        "municipality": 4040,
        "canton": "AG",
    }
    check = ElcomCheck(federal_per_kwh=None, grid_monthly_base=5.5)
    assert select_contract(tariffs, options, DAY_2027, check).grid.monthly_base == 5.5
    assert select_contract(tariffs, options, DAY_2027).grid.monthly_base == 66.0


def test_metering_comes_from_elcom_when_the_file_lists_it_apart() -> None:
    """AIL lists metering (5.30 CHF a month) as a tariff of its own; ElCom's 1.413 Rp.
    at 4500 kWh is the same fee. Where the file's fees match ElCom's grid fixed
    costs and metering together, nothing is added."""
    assert metering_per_month(8.55, 0.0, 1.413) == pytest.approx(5.30, abs=0.01)
    assert metering_per_month(4.0, 48.0, 1.6) == 6.0  # the grid's fee only: add
    assert metering_per_month(10.0, 48.0, 1.6) == 0.0  # 120 CHF = 48 + 72: in already
    assert metering_per_month(6.2, 0.0, 1.653) == 0.0  # all of the fee is metering
    assert metering_per_month(0.0, None, 1.6) == 6.0  # no fixed costs from ElCom
    assert metering_per_month(4.0, 48.0, None) == 0.0
    assert metering_per_month(4.0, 48.0, 0.0) == 0.0


def test_metering_counts_in_the_fixed_charges() -> None:
    tariffs = load("ail-2027.json")
    contract = SwissContract(
        electricity=by_name(tariffs, "Casa & PMI 24h-electricity"),
        grid=by_name(tariffs, "Casa & PMI 24h-grid7"),
        canton="TI",
        municipality=5192,
    )
    with_metering = replace(contract, metering_monthly=5.3)
    assert with_metering.monthly_fixed == pytest.approx(
        contract.monthly_fixed + 5.3 * (1 + SWISS_VAT), abs=0.01
    )


def test_grid_suggestion_skips_tariffs_far_from_elcom() -> None:
    """Gränichen 2027: with a flat energy tariff, the only flat grid tariff is for
    building sites, 20 Rp. away from ElCom's household figure."""
    tariffs = load("graenichen-2027.json")
    electricity = by_name(tariffs, "energie.natur+")
    grids = tariffs_on(tariffs, "grid", DAY_2027)
    grid = suggest_grid(electricity, grids, 4006, "Gränichen", (10.867, 2.3, 2027, 9.25))
    # netz.kompakt.flex, or street lighting at the same price: the closest to ElCom.
    assert grid.name in {"netz.kompakt.flex", "netz.öB"}
    assert suggest_grid(electricity, grids, 4006, "Gränichen").name == "netz.temporär"


def test_federal_charges_clear_when_the_next_hypothesis_is_far() -> None:
    """ebs 2026 compared per kWh (ElCom: 10.32 Rp. without fees): the household day/night
    average is 0.72 Rp. off with all charges added, 1.45 with the surcharge only. Over
    0.6 Rp., the check used to fall back to the building-site tariff, which said none."""
    grids = tariffs_on(load("ebs-2026.json"), "grid", date(2026, 10, 13))
    chosen = by_name(grids, "N-Casa")
    addition = federal_addition(grids, 10.729, 2.3, 2026, chosen=chosen, elcom_working_rp=10.319)
    assert addition == national_charges(2026)


def test_missing_fees_from_elcom() -> None:
    """Fees ElCom counts and the file lacks; monthly fees count at 4500 kWh a year."""
    oiken = load("oiken-2027.json")
    fee = by_name(tariffs_on(oiken, "regional_fees", DAY_2027), "Tarif Simple")
    # No fee in the file, ElCom 2 Rp.: all of it is missing.
    assert missing_fees([], "VS", 6266, "Sion", 2.0, 2027) == pytest.approx(0.02)
    # Sion: 0.732 Rp. plus 0.84 CHF a month (0.224 Rp.), ElCom 1.17: close enough.
    assert missing_fees([fee], "VS", 6266, "Sion", 1.17, 2027) == 0.0
    # Most of ElCom's fees not in the file (Basel 2027: 0.65 Rp. in IWB's file, 7.79 at ElCom).
    assert missing_fees([fee], "VS", 6266, "Sion", 7.79, 2027) == pytest.approx(
        (7.79 - 0.732 - 0.224) / 100, abs=1e-5
    )


def test_fees_that_hold_the_federal_charges() -> None:
    """Lachen 2027: 2.68 Rp. of fees in the file, 0.38 at ElCom: the grid surcharge
    (2.3 Rp.) is in the fee, and Corrente adds it on its own. Fällanden: 2.85 Rp.,
    all the federal charges, against none at ElCom. Rothrist (8 against 0.8) is no
    known pattern: left as it is."""
    lachen = _fee("Abgaben", (PriceWindow(price=0.0268),), canton="SZ")
    assert missing_fees([lachen], "SZ", 1344, "Lachen", 0.38, 2027) == pytest.approx(-0.023)
    faellanden = _fee("Abgaben", (PriceWindow(price=0.0285),), canton="ZH")
    assert missing_fees([faellanden], "ZH", 193, "Fällanden", 0.0, 2027) == pytest.approx(
        -national_charges(2027)
    )
    rothrist = _fee("Konzession", (PriceWindow(price=0.08),), municipality=4282)
    assert missing_fees([rothrist], "AG", 4282, "Rothrist", 0.8, 2027) == 0.0


def test_fee_suggestion_counts_monthly_fees() -> None:
    """Blumenstein 2027: 0.1 Rp. per kWh for households, and for businesses 25 CHF a
    month and nothing per kWh. ElCom: 0.1 Rp. Only the households' fee fits."""
    name = "Leistungen Gemeinde Blumenstein"
    households = _fee(f"{name} (kWh)", (PriceWindow(price=0.001),), municipality=922)
    businesses = replace(
        _fee(name, (PriceWindow(price=0.0),), municipality=922), municipality_base={922: 25.0}
    )
    electricity = _fee("Naturstrom H", (PriceWindow(price=0.1),))
    grid = _fee("Einfach Haushalt", (PriceWindow(price=0.1),))
    fees = suggest_regional_fees(
        electricity, [households, businesses], 922, 0.1, 2027, grid, "Blumenstein"
    )
    assert fees == [households]
