"""Tests for Swiss dynamic tariffs, against real answers of the operators' APIs."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from custom_components.corrente.core.dynamic import (
    DynamicTariffError,
    is_api_url,
    parse_prices,
    request_url,
)
from custom_components.corrente.core.switzerland import (
    SWISS_TZ,
    SWISS_VAT,
    PriceNotPublishedError,
    SwissContract,
    UnsupportedTariffError,
    federal_addition,
    national_charges,
    parse_tariffs,
    suggest_grid,
    tariffs_on,
)

FIXTURES = Path(__file__).parent / "fixtures" / "ch"
DAY = datetime(2026, 10, 8, tzinfo=SWISS_TZ).date()


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text("utf-8"))


def zurich(*args: int) -> datetime:
    return datetime(*args, tzinfo=SWISS_TZ)


def ekz_tariff(tariff_type: str, name: str):
    tariffs = parse_tariffs(load("ekz-2026.json"))
    return next(t for t in tariffs_on(tariffs, tariff_type, DAY) if t.name == name)


ENERGY_DYNAMIC = "EKZ Energie Dynamisch"
GRID_DYNAMIC = "EKZ Netz 400D + SDL, Stromreserve, Solidarisierte Kosten, Bundesabgaben"
GRID_FLAT = "EKZ Netz 400F + SDL, Stromreserve, Solidarisierte Kosten, Bundesabgaben"


# The API answers ------------------------------------------------------------


def test_ekz_2026_format() -> None:
    segments = parse_prices(load("ekz-electricity-dynamic-20261008.json"), "electricity")
    # EKZ also returns the next interval, without a per-kWh price (not published yet).
    assert len(load("ekz-electricity-dynamic-20261008.json")["prices"]) == 97
    assert len(segments) == 96
    first = segments[0]
    assert first.start == zurich(2026, 10, 8, 0, 0)
    assert first.start.tzinfo is UTC
    assert first.end - first.start == timedelta(minutes=15)
    assert first.price == pytest.approx(0.11514)  # CHF_m 3.0 (monthly fee) is not per kWh


def test_groupe_e_grid() -> None:
    segments = parse_prices(load("groupe-e-grid-20261008.json"), "grid")
    assert len(segments) == 96
    assert segments[0].price == pytest.approx(0.07)
    assert parse_prices(load("groupe-e-grid-20261008.json"), "electricity") == []


def test_ckw_timestamps_without_seconds() -> None:
    segments = parse_prices(load("ckw-integrated-20261008-09.json"), "integrated")
    assert len(segments) == 192
    assert segments[0].start == zurich(2026, 10, 8, 0, 0)
    assert segments[-1].end == zurich(2026, 10, 10, 0, 0)


def test_2027_format() -> None:
    document = {
        "publication_timestamp": "2026-12-31T18:00:00+01:00",
        "prices": [
            {
                "start_timestamp": "2027-01-01T00:00:00+01:00",
                "end_timestamp": "2027-01-01T00:15:00+01:00",
                "grid": {
                    "tariff_name": "grid_dynamic",
                    "base": {"unit": "CHF/m", "value": 3.0},
                    "energy": {"unit": "CHF/kWh", "value": 0.0612},
                    "power": {"unit": "CHF/kW/m", "value": 1.2},
                },
            }
        ],
    }
    (segment,) = parse_prices(document, "grid")
    assert segment.price == pytest.approx(0.0612)
    assert segment.start == zurich(2027, 1, 1, 0, 0)


def test_unreadable_answers() -> None:
    with pytest.raises(DynamicTariffError):
        parse_prices({"error": "nope"}, "grid")
    with pytest.raises(DynamicTariffError):
        parse_prices(
            {
                "prices": [
                    {
                        "start_timestamp": "yesterday",
                        "end_timestamp": "today",
                        "grid": [{"unit": "CHF_kWh", "value": 0.1}],
                    }
                ]
            },
            "grid",
        )
    assert parse_prices({"publication_timestamp": None, "prices": []}, "grid") == []


def test_api_links() -> None:
    assert is_api_url("https://api.tariffs.ekz.ch/v1/tariffs?tariff_name=electricity_dynamic")
    assert not is_api_url("www.aew.ch/dynamic")  # AEW 2027: a web page, not an API
    assert not is_api_url(None)
    url = request_url(
        "https://api.tariffs.ekz.ch/v1/tariffs?tariff_name=grid_400D_inclFees",
        "grid",
        zurich(2026, 10, 8, 0, 0),
        zurich(2026, 10, 10, 0, 0),
    )
    assert url.query["tariff_name"] == "grid_400D_inclFees"  # the operator's choice is kept
    assert url.query["tariff_type"] == "grid"
    assert url.query["start_timestamp"] == "2026-10-08T00:00:00+02:00"
    assert url.query["end_timestamp"] == "2026-10-10T00:00:00+02:00"


# Tariff files ---------------------------------------------------------------


def test_ekz_file_lists_dynamic_tariffs() -> None:
    energy = ekz_tariff("electricity", ENERGY_DYNAMIC)
    assert energy.is_dynamic
    assert energy.dynamic_url.endswith("tariff_name=electricity_dynamic")
    assert energy.monthly_base == 3.0
    energy.check_supported()  # an API is named: Corrente can price it


def test_dynamic_tariff_without_api_is_unsupported() -> None:
    document = load("ekz-2026.json")
    raw = next(t for t in document["tariffs"] if t["tariffName"] == ENERGY_DYNAMIC)
    raw["prices"]["dynamic"]["url"] = "www.aew.ch/dynamic"
    (tariff,) = [t for t in parse_tariffs({"tariffs": [raw]})]
    with pytest.raises(UnsupportedTariffError):
        tariff.check_supported()


def test_bkw_file_quirks() -> None:
    """BKW writes dates with a time and has "#N/A" municipalities; one bad entry is skipped."""
    good = {
        "tariffName": "Strom Basis",
        "tariffType": "electricity",
        "startDate": "2027-01-01T00:00:00",
        "endDate": "2027-12-31T00:00:00",
        "prices": {
            "energy": [{"price": 0.15, "priceUnit": "CHF/kWh", "from": "00:00", "to": "00:00"}],
            "municipalityTaxes": [
                {
                    "municipalityNumber": "#N/A",
                    "municipalityEnergy": [
                        {"price": 0.01, "priceUnit": "CHF/kWh", "from": "00:00", "to": "00:00"}
                    ],
                }
            ],
        },
    }
    broken = {"tariffName": "Broken", "tariffType": "grid"}  # no dates
    (tariff,) = parse_tariffs({"tariffs": [good, broken]})
    assert tariff.start_date.isoformat() == "2027-01-01"
    assert tariff.end_date.isoformat() == "2027-12-31"
    assert tariff.municipality_energy == {}


# Contracts with dynamic prices ---------------------------------------------


def ekz_contract(grid: str = GRID_DYNAMIC) -> SwissContract:
    contract = SwissContract(
        electricity=ekz_tariff("electricity", ENERGY_DYNAMIC),
        grid=ekz_tariff("grid", grid),
        federal_per_kwh=0.0,  # EKZ's grid prices include the federal charges
    )
    prices = {
        "electricity": parse_prices(load("ekz-electricity-dynamic-20261008.json"), "electricity")
    }
    if contract.grid.is_dynamic:
        prices["grid"] = parse_prices(load("ekz-grid-400d-20261008.json"), "grid")
    return contract.with_dynamic_prices(prices)


def test_price_is_energy_plus_grid_plus_vat() -> None:
    contract = ekz_contract()
    price, gap = contract.price_at(zurich(2026, 10, 8, 0, 0))
    assert price == pytest.approx((0.11514 + 0.08529) * (1 + SWISS_VAT), abs=1e-6)
    assert gap is False
    assert contract.is_time_dependent()
    assert contract.monthly_fixed == pytest.approx(3.0 * (1 + SWISS_VAT), abs=0.01)


def test_dynamic_energy_with_flat_grid() -> None:
    contract = ekz_contract(GRID_FLAT)
    price, _ = contract.price_at(zurich(2026, 10, 8, 0, 0))
    assert price == pytest.approx((0.11514 + 0.1053) * (1 + SWISS_VAT), abs=1e-6)
    assert [t.tariff_type for t in contract.dynamic_tariffs] == ["electricity"]


def test_prices_end_where_publication_ends() -> None:
    contract = ekz_contract()
    assert contract.known_until == zurich(2026, 10, 9, 0, 0)
    with pytest.raises(PriceNotPublishedError):
        contract.price_at(zurich(2026, 10, 9, 0, 0))
    assert contract.price_or_none(zurich(2026, 10, 9, 6, 0)) is None

    schedule = contract.schedule(zurich(2026, 10, 8, 20, 0), zurich(2026, 10, 9, 8, 0))
    assert schedule[0].start == zurich(2026, 10, 8, 20, 0)
    assert schedule[-1].end == zurich(2026, 10, 9, 0, 0)
    assert all(a.end == b.start for a, b in zip(schedule, schedule[1:], strict=False))
    assert all(a.price != b.price for a, b in zip(schedule, schedule[1:], strict=False))


def test_next_change_and_period() -> None:
    contract = ekz_contract()
    now = zurich(2026, 10, 8, 12, 5)
    when, price = contract.next_change(now)
    assert when > now
    assert when.minute % 15 == 0
    assert price != contract.price_at(now)[0]

    day = contract.schedule(zurich(2026, 10, 8, 0, 0), zurich(2026, 10, 9, 0, 0))
    cheapest = min(day, key=lambda s: s.price)
    dearest = max(day, key=lambda s: s.price)
    assert contract.period_at(cheapest.start) == "low"
    assert contract.period_at(dearest.start) == "high"
    assert contract.period_at(zurich(2026, 10, 9, 6, 0)) is None
    # Nothing after the last published price.
    assert contract.next_change(zurich(2026, 10, 8, 23, 50)) is None


def test_no_prices_downloaded_yet() -> None:
    contract = SwissContract(
        electricity=ekz_tariff("electricity", ENERGY_DYNAMIC),
        grid=ekz_tariff("grid", GRID_FLAT),
    )
    assert contract.price_or_none(zurich(2026, 10, 8, 12, 0)) is None
    assert contract.schedule(zurich(2026, 10, 8, 12, 0), zurich(2026, 10, 9, 12, 0)) == []
    assert contract.next_change(zurich(2026, 10, 8, 12, 0)) is None


# Federal charges with a dynamic grid tariff --------------------------------

# ElCom 2026, Bulle (Groupe E), profile H4: grid usage 8.777 Rp + grid surcharge 2.3 Rp.
BULLE_GRID_RP, BULLE_AIDFEE_RP = 8.777, 2.3


@pytest.mark.parametrize(
    "chosen",
    [
        "Tarif Vario réseau / Tarif Vario Netz",
        "Tarif double réseau / Doppeltarif Netz",
        "Tarif unitaire réseau / Einheitstarif Netz",
    ],
)
def test_groupe_e_federal_charges_are_included(chosen: str) -> None:
    """Compared with household tariffs, Groupe E's grid prices already include the charges.

    Before, a dynamic or day/night choice was compared with all flat tariffs,
    and a business tariff ("BT DUO") made Corrente add the 2.3 Rp surcharge again.
    """
    grids = tariffs_on(parse_tariffs(load("groupe-e-2026.json")), "grid", DAY)
    tariff = next(t for t in grids if t.name == chosen)
    addition = federal_addition(grids, BULLE_GRID_RP, BULLE_AIDFEE_RP, 2026, chosen=tariff)
    assert addition == 0.0


def test_ekz_federal_charges_with_dynamic_grid() -> None:
    grids = tariffs_on(parse_tariffs(load("ekz-2026.json")), "grid", DAY)
    tariff = next(t for t in grids if t.name == GRID_DYNAMIC)
    # ElCom 2026, Dietikon: grid usage 8.23 Rp + grid surcharge 2.3 Rp.
    assert federal_addition(grids, 8.23, 2.3, 2026, chosen=tariff) == 0.0


def test_file_price_of_a_dynamic_tariff_is_not_added() -> None:
    """AIL writes an indicative 8.35 Rp on its dynamic tariff: only the API price counts."""
    document = load("ekz-2026.json")
    raw = next(t for t in document["tariffs"] if t["tariffName"] == ENERGY_DYNAMIC)
    raw["prices"]["energy"] = [
        {"price": 0.0835, "priceUnit": "CHF/kWh", "from": "00:00", "to": "00:00"}
    ]
    (energy,) = parse_tariffs({"tariffs": [raw]})
    contract = SwissContract(
        electricity=energy, grid=ekz_tariff("grid", GRID_FLAT), federal_per_kwh=0.0
    ).with_dynamic_prices(
        {"electricity": parse_prices(load("ekz-electricity-dynamic-20261008.json"), "electricity")}
    )
    price, _ = contract.price_at(zurich(2026, 10, 8, 0, 0))
    assert price == pytest.approx((0.11514 + 0.1053) * (1 + SWISS_VAT), abs=1e-6)


PRIMEO_API = "https://tarife.primeo-energie.ch/api/v1/tariffs"


def test_primeo_2026_dynamic_grid_gets_its_api() -> None:
    """Primeo's 2026 file writes "URL wird auf der Webseite … bekannt gegeben"
    instead of the link: Corrente knows the API. Another operator selling the same
    product name with its own prices (Elektra Gretzenbach) keeps its file as it is."""
    document = load("primeo-2026.json")
    grids = tariffs_on(parse_tariffs(document), "grid", DAY)
    dynamic = next(t for t in grids if t.is_dynamic)
    assert dynamic.dynamic_url == PRIMEO_API
    dynamic.check_supported()
    other = parse_tariffs({**document, "dsoName": "Elektra Gretzenbach AG"})
    with pytest.raises(UnsupportedTariffError):
        next(t for t in other if t.is_dynamic and t.tariff_type == "grid").check_supported()


def test_primeo_dynamic_grid_holds_the_federal_charges() -> None:
    """Every Primeo dynamic grid price is a whole number of Rp. plus 3.03, the federal
    charges; its standard grid leaves them out (ElCom 2026, Aesch BL: 11.927 Rp.)."""
    grids = tariffs_on(parse_tariffs(load("primeo-2026.json")), "grid", DAY)
    dynamic = next(t for t in grids if t.is_dynamic)
    standard = next(t for t in grids if not t.is_dynamic)
    federal = national_charges(2026)
    assert federal_addition(grids, 14.6, 2.3, 2026, chosen=standard, elcom_working_rp=11.927) == (
        federal
    )
    assert federal_addition(grids, 14.6, 2.3, 2026, chosen=dynamic, elcom_working_rp=11.927) == 0
    prices = parse_prices(load("primeo-grid-20261023.json"), "grid")
    assert {round(100 * s.price - 100 * federal, 6) % 1 for s in prices} == {0.0}

    tariffs = parse_tariffs(load("primeo-2026.json"))
    energy = next(
        t for t in tariffs if t.name == "Primeo NetzDynamisch" and t.tariff_type == "electricity"
    )
    fees = next(
        t for t in tariffs if t.name == "Primeo NetzDynamisch" and t.tariff_type == "regional_fees"
    )
    contract = SwissContract(
        electricity=energy, grid=dynamic, regional_fees=fees, canton="BL", municipality=2761
    ).with_dynamic_prices({"grid": prices})
    midnight = datetime(2026, 10, 23, 0, 0, tzinfo=SWISS_TZ)  # Friday, night energy price
    expected = (0.13 + 0.0703 + 0.00025) * (1 + SWISS_VAT)  # federal charges not added again
    assert contract.price_at(midnight)[0] == pytest.approx(expected, abs=1e-6)


def test_grid_named_like_the_energy_tariff_is_suggested() -> None:
    """Primeo NetzDynamisch: energy by the clock, grid dynamic. Same name, same product."""
    tariffs = parse_tariffs(load("primeo-2026.json"))
    energy = next(
        t for t in tariffs if t.name == "Primeo NetzDynamisch" and t.tariff_type == "electricity"
    )
    grids = tariffs_on(tariffs, "grid", DAY)
    assert suggest_grid(energy, grids, 2761, "Aesch (BL)").name == "Primeo NetzDynamisch"
    standard = next(
        t for t in tariffs if t.name == "Primeo Standard" and t.tariff_type == "electricity"
    )
    assert suggest_grid(standard, grids, 2761, "Aesch (BL)").name == "Primeo Standard"
