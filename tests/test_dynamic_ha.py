"""Swiss dynamic tariffs in Home Assistant: EKZ in Dietikon, APIs and ElCom mocked."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.corrente.const import DOMAIN
from custom_components.corrente.core.dynamic import (
    DynamicTariffError,
    async_fetch_prices,
    parse_prices,
)
from custom_components.corrente.core.elcom import LINDAS_ENDPOINT
from custom_components.corrente.core.switzerland import SWISS_TZ, SWISS_VAT

FIXTURES = Path(__file__).parent / "fixtures" / "ch"
EKZ_FILE = "https://www.ekz.ch/dam/ekz/privatkunden/strom/tarife-und-agb/tarife_ekz.json"
# The link ElCom registered for 2026 (a 404 in reality, see FONTI-DATI.md).
EKZ_FILE_2026 = (
    "https://www.ekz.ch/dam/ekz/privatkunden/strom/tarife-und-agb/Tarifbersicht_EKZ_2026.json"
)
ENERGY_API = "https://api.tariffs.ekz.ch/v1/tariffs?tariff_name=electricity_dynamic"
GRID_API = "https://api.tariffs.ekz.ch/v1/tariffs?tariff_name=grid_400D_inclFees"
ENERGY = "EKZ Energie Dynamisch"
GRID = "EKZ Netz 400D + SDL, Stromreserve, Solidarisierte Kosten, Bundesabgaben"
NOON = datetime(2026, 10, 8, 12, 5, tzinfo=SWISS_TZ)

EKZ_DYNAMIC = {
    "country": "ch",
    "municipality": 243,
    "municipality_name": "Dietikon",
    "operator_id": "486",
    "operator_name": "Elektrizitätswerke des Kantons Zürich (EKZ)",
    "tariff_url": EKZ_FILE,
    "electricity_tariff": ENERGY,
    "grid_tariff": GRID,
    "regional_tariff": None,
    "canton": None,
}


def mock_ekz(aioclient_mock: AiohttpClientMocker, *, api_status: int = 200) -> None:
    aioclient_mock.post(
        LINDAS_ENDPOINT, text=(FIXTURES / "lindas-dietikon-2026.json").read_text("utf-8")
    )
    for url in (EKZ_FILE, EKZ_FILE_2026):
        aioclient_mock.get(url, content=(FIXTURES / "ekz-2026.json").read_bytes())
    if api_status != 200:
        aioclient_mock.get(ENERGY_API, status=api_status)
        aioclient_mock.get(GRID_API, status=api_status)
        return
    aioclient_mock.get(
        ENERGY_API, text=(FIXTURES / "ekz-electricity-dynamic-20261008.json").read_text("utf-8")
    )
    aioclient_mock.get(GRID_API, text=(FIXTURES / "ekz-grid-400d-20261008.json").read_text("utf-8"))


def api_calls(aioclient_mock: AiohttpClientMocker) -> int:
    return sum(1 for _method, url, *_ in aioclient_mock.mock_calls if url.host.startswith("api."))


async def test_dynamic_sensors(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(NOON)
    mock_ekz(aioclient_mock)
    entry = MockConfigEntry(domain=DOMAIN, title="Corrente — EKZ", data=EKZ_DYNAMIC)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert api_calls(aioclient_mock) == 2  # energy and grid

    registry = er.async_get(hass)

    def state(key: str):
        entity_id = registry.async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_{key}")
        return hass.states.get(entity_id)

    # 12:00-12:15 from the two fixtures; EKZ's grid prices include the federal
    # charges, which the ElCom check finds (nothing added).
    price = state("price")
    assert price.attributes["federal_charges_checked_with_elcom"] is True

    def price_at_noon(fixture: str, kind: str) -> float:
        segments = parse_prices(json.loads((FIXTURES / fixture).read_text("utf-8")), kind)
        return next(seg.price for seg in segments if seg.start == NOON.replace(minute=0))

    energy = price_at_noon("ekz-electricity-dynamic-20261008.json", "electricity")
    grid = price_at_noon("ekz-grid-400d-20261008.json", "grid")
    assert float(price.state) == pytest.approx((energy + grid) * (1 + SWISS_VAT), abs=1e-5)
    assert price.attributes["energy_tariff"] == ENERGY
    assert price.attributes["dynamic_prices_until"] == "2026-10-08T22:00:00+00:00"
    schedule = price.attributes["schedule"]
    assert datetime.fromisoformat(schedule[-1]["end"]) == datetime(
        2026, 10, 9, 0, 0, tzinfo=SWISS_TZ
    )
    assert state("period").state in ("high", "low")
    assert state("best_start").state not in ("unknown", "unavailable")
    assert float(state("monthly_fixed").state) == pytest.approx(3.0 * (1 + SWISS_VAT), abs=0.01)

    # In the afternoon tomorrow's prices are due: Corrente asks again, about
    # every half hour, until they come (the fixtures never have them).
    freezer.move_to(datetime(2026, 10, 8, 13, 30, tzinfo=SWISS_TZ))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert api_calls(aioclient_mock) == 4
    freezer.move_to(datetime(2026, 10, 8, 13, 40, tzinfo=SWISS_TZ))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert api_calls(aioclient_mock) == 4

    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_dynamic_setup_retries_when_api_is_down(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(NOON)
    mock_ekz(aioclient_mock, api_status=503)
    entry = MockConfigEntry(domain=DOMAIN, data=EKZ_DYNAMIC)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def _flow_to_grid_step(hass: HomeAssistant) -> dict:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"country": "ch"})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"municipality": "Dietikon"}
    )
    assert result["step_id"] == "ch_tariff"
    names = [
        o["value"] for o in result["data_schema"].schema["electricity_tariff"].config["options"]
    ]
    assert ENERGY in names  # dynamic tariffs are offered now
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"electricity_tariff": ENERGY}
    )
    assert result["step_id"] == "ch_grid"
    grids = result["data_schema"].schema["grid_tariff"].config["options"]
    assert GRID in grids
    return result


async def test_flow_with_dynamic_tariffs(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(NOON)
    mock_ekz(aioclient_mock)
    result = await _flow_to_grid_step(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"grid_tariff": GRID, "regional_tariff": []}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["electricity_tariff"] == ENERGY
    assert result["data"]["grid_tariff"] == GRID


async def test_flow_reports_unreachable_dynamic_prices(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(NOON)
    mock_ekz(aioclient_mock, api_status=500)
    result = await _flow_to_grid_step(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"grid_tariff": GRID, "regional_tariff": []}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "dynamic_unavailable"}


async def test_flow_explains_a_web_page_instead_of_prices(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, freezer: FrozenDateTimeFactory
) -> None:
    """AIL links its dynamic tariff to a web page: say so, instead of "try later"."""
    freezer.move_to(NOON)
    aioclient_mock.post(
        LINDAS_ENDPOINT, text=(FIXTURES / "lindas-dietikon-2026.json").read_text("utf-8")
    )
    for url in (EKZ_FILE, EKZ_FILE_2026):
        aioclient_mock.get(url, content=(FIXTURES / "ekz-2026.json").read_bytes())
    for url in (ENERGY_API, GRID_API):
        aioclient_mock.get(url, text="<!doctype html><html><body>Tariffa dinamica</body></html>")
    result = await _flow_to_grid_step(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"grid_tariff": GRID, "regional_tariff": []}
    )
    assert result["errors"] == {"base": "dynamic_not_api"}
    assert "issues_url" in result["description_placeholders"]


async def test_energy_prices_from_the_grid_answer(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Primeo (2027) refuses tariff_type=electricity and sends the energy prices with
    the grid ones: Corrente asks for the grid and reads the energy from the answer."""
    api = "https://tarife.primeo-energie.ch/api/v1/tariffs"
    answer = (FIXTURES / "primeo-grid-20261023.json").read_text("utf-8")
    aioclient_mock.get(api, params={"tariff_type": "electricity"}, status=422)
    aioclient_mock.get(api, params={"tariff_type": "grid"}, text=answer)
    session = async_get_clientsession(hass)
    start = datetime(2026, 10, 23, tzinfo=SWISS_TZ)
    end = start + timedelta(days=1)
    energy = await async_fetch_prices(session, api, "electricity", start, end)
    grid = await async_fetch_prices(session, api, "grid", start, end)
    assert len(energy) == len(grid) == 96
    assert {s.price for s in energy} == {0.13, 0.144}
    assert min(s.price for s in grid) == 0.0303
    assert energy[0].start == start


async def test_grid_refused_is_an_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    api = "https://tarife.example.ch/api/v1/tariffs"
    aioclient_mock.get(api, status=422)
    start = datetime(2026, 10, 23, tzinfo=SWISS_TZ)
    with pytest.raises(DynamicTariffError):
        await async_fetch_prices(
            async_get_clientsession(hass), api, "grid", start, start + timedelta(days=1)
        )
