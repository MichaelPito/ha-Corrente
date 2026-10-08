"""Config flow and sensors for Switzerland, with ElCom and AIL's tariff file mocked."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.corrente.const import DOMAIN
from custom_components.corrente.core.elcom import LINDAS_ENDPOINT
from custom_components.corrente.core.switzerland import SWISS_TZ, SWISS_VAT

FIXTURES = Path(__file__).parent / "fixtures" / "ch"
AIL_URL = "https://api-ail.prod01.apimanagement.eu20.hana.ondemand.com/prd/tariffs_2027"
# The fixtures are AIL's 2027 tariffs: run these tests on a Wednesday in 2027.
WEDNESDAY_10AM = datetime(2027, 3, 10, 10, 0, tzinfo=SWISS_TZ)

AIL_DAY_NIGHT = {
    "country": "ch",
    "municipality": 5192,
    "municipality_name": "Lugano",
    "operator_id": "31",
    "operator_name": "Aziende Industriali di Lugano (AIL) SA",
    "tariff_url": AIL_URL,
    "electricity_tariff": "Casa & PMI giorno-notte-electricity",
    "grid_tariff": "Casa & PMI giorno-notte-grid7",
    "regional_tariff": "Casa & PMI giorno-notte-regional_fees",
    "canton": "TI",
}


@pytest.fixture
def mock_ch(aioclient_mock: AiohttpClientMocker) -> AiohttpClientMocker:
    aioclient_mock.post(
        LINDAS_ENDPOINT, text=(FIXTURES / "lindas-lugano-2027.json").read_text("utf-8")
    )
    aioclient_mock.get(AIL_URL, content=(FIXTURES / "ail-2027.json").read_bytes())
    return aioclient_mock


async def test_flow_lugano(
    hass: HomeAssistant, mock_ch: AiohttpClientMocker, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(WEDNESDAY_10AM)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"country": "ch"})
    assert result["step_id"] == "ch_search"

    # One municipality, one operator: straight to the tariff choice.
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"municipality": "Lugano"}
    )
    assert result["step_id"] == "ch_tariff"
    options = result["data_schema"].schema["electricity_tariff"].config["options"]
    names = [option["value"] for option in options]
    assert "Casa & PMI giorno-notte-electricity" in names

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"electricity_tariff": "Casa & PMI giorno-notte-electricity"}
    )
    assert result["step_id"] == "ch_grid"
    # The matching grid tariff and regional fees are suggested.
    defaults = {str(key): key.default() for key in result["data_schema"].schema}
    assert defaults["grid_tariff"] == "Casa & PMI giorno-notte-grid7"
    assert defaults["regional_tariff"] == "Casa & PMI giorno-notte-regional_fees"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "grid_tariff": "Casa & PMI giorno-notte-grid7",
            "regional_tariff": "Casa & PMI giorno-notte-regional_fees",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Corrente Lugano"
    assert result["data"] == AIL_DAY_NIGHT


async def test_flow_unknown_municipality(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.post(LINDAS_ENDPOINT, json={"results": {"bindings": []}})
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"country": "ch"})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"municipality": "Atlantide"}
    )
    assert result["step_id"] == "ch_search"
    assert result["errors"] == {"municipality": "no_match"}


async def test_flow_asks_for_link_when_file_is_unreadable(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(WEDNESDAY_10AM)
    aioclient_mock.post(
        LINDAS_ENDPOINT, text=(FIXTURES / "lindas-lugano-2027.json").read_text("utf-8")
    )
    aioclient_mock.get(AIL_URL, status=404)
    good_url = "https://example.ch/ail.json"
    aioclient_mock.get(good_url, content=(FIXTURES / "ail-2027.json").read_bytes())
    aioclient_mock.get("https://example.ch/page", text="<html></html>")

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"country": "ch"})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"municipality": "Lugano"}
    )
    assert result["step_id"] == "ch_url"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"tariff_url": "https://example.ch/page"}
    )
    assert result["errors"] == {"tariff_url": "invalid_file"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"tariff_url": good_url}
    )
    assert result["step_id"] == "ch_tariff"


async def test_swiss_sensors(
    hass: HomeAssistant, mock_ch: AiohttpClientMocker, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(WEDNESDAY_10AM)
    entry = MockConfigEntry(domain=DOMAIN, title="Corrente — AIL", data=AIL_DAY_NIGHT)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    registry = er.async_get(hass)

    def state(key: str):
        entity_id = registry.async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_{key}")
        return hass.states.get(entity_id)

    high = (0.0975 + 0.068 + 0.0102 + 0.012 + 0.0285) * (1 + SWISS_VAT)
    low = (0.086 + 0.061 + 0.0102 + 0.012 + 0.0285) * (1 + SWISS_VAT)
    assert float(state("price").state) == pytest.approx(high, abs=1e-5)
    assert state("price").attributes["grid_tariff"] == "Casa & PMI giorno-notte-grid7"
    assert state("price").attributes["federal_charges_checked_with_elcom"] is True
    assert state("price").attributes["unit_of_measurement"] == "CHF/kWh"
    assert state("period").state == "high"
    assert float(state("next_price").state) == pytest.approx(low, abs=1e-5)
    next_change = datetime.fromisoformat(state("next_price_change").state)
    assert next_change == datetime(2027, 3, 10, 22, 0, tzinfo=SWISS_TZ)
    assert float(state("monthly_fixed").state) == pytest.approx(8.55 * (1 + SWISS_VAT), abs=0.01)

    best = state("best_start")
    assert datetime.fromisoformat(best.state) == datetime(2027, 3, 10, 22, 0, tzinfo=SWISS_TZ)
    assert best.attributes["average_price"] == pytest.approx(low, abs=1e-5)
    schedule = state("price").attributes["schedule"]
    assert schedule[0]["price"] == pytest.approx(high, abs=1e-5)
    assert schedule[1]["price"] == pytest.approx(low, abs=1e-5)

    # At 22:00 the sensors switch to the low tariff on their own.
    freezer.move_to(datetime(2027, 3, 10, 22, 0, tzinfo=SWISS_TZ))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert state("period").state == "low"
    assert float(state("price").state) == pytest.approx(low, abs=1e-5)

    freezer.tick(timedelta(minutes=1))
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_swiss_setup_retries_when_file_is_down(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(WEDNESDAY_10AM)
    aioclient_mock.get(AIL_URL, status=500)
    entry = MockConfigEntry(domain=DOMAIN, data=AIL_DAY_NIGHT)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_swiss_options_change_tariff(
    hass: HomeAssistant, mock_ch: AiohttpClientMocker, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(WEDNESDAY_10AM)
    entry = MockConfigEntry(domain=DOMAIN, data=AIL_DAY_NIGHT)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "contract"}
    )
    assert result["step_id"] == "ch_tariff"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"electricity_tariff": "Casa & PMI 24h-electricity"}
    )
    assert result["step_id"] == "ch_grid"
    defaults = {str(key): key.default() for key in result["data_schema"].schema}
    assert defaults["grid_tariff"] == "Casa & PMI 24h-grid7"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "grid_tariff": "Casa & PMI 24h-grid7",
            "regional_tariff": "Casa & PMI 24h-regional_fees",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    # The entry reloads with the flat tariff: no more high/low periods.
    entity_id = er.async_get(hass).async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_period")
    assert hass.states.get(entity_id).state == "single"


async def test_new_year_follows_the_new_file(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, freezer: FrozenDateTimeFactory
) -> None:
    """On 1 January the stored 2027 file has no valid tariff: ElCom gives the 2028 link."""
    freezer.move_to(datetime(2028, 1, 5, 10, 0, tzinfo=SWISS_TZ))
    url_2028 = "https://example.ch/tariffs_2028"
    document_2028 = (
        (FIXTURES / "ail-2027.json")
        .read_text("utf-8")
        .replace("2027-01-01", "2028-01-01")
        .replace("2027-12-31", "2028-12-31")
    )
    lindas_2028 = (
        (FIXTURES / "lindas-lugano-2027.json").read_text("utf-8").replace(AIL_URL, url_2028)
    )
    aioclient_mock.get(AIL_URL, content=(FIXTURES / "ail-2027.json").read_bytes())
    aioclient_mock.post(LINDAS_ENDPOINT, text=lindas_2028)
    aioclient_mock.get(url_2028, text=document_2028)

    entry = MockConfigEntry(domain=DOMAIN, data=AIL_DAY_NIGHT)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.switzerland.data.source_url == url_2028
