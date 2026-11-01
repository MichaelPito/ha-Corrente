"""PUN-indexed contract: config flow, sensors and download schedule, with GME mocked."""

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
from custom_components.corrente.core.gme import GME_URL
from custom_components.corrente.core.italy import ITALY_TZ

FIXTURES = Path(__file__).parent / "fixtures" / "it"
ZIP = (FIXTURES / "gme-20261007-20261008.zip").read_bytes()
PUN_ENTRY = {
    "country": "it",
    "contract_type": "pun",
    "spread": 0.02,
    "losses": 10.0,
    "zone": "pun",
}


def rome(*args: int) -> datetime:
    return datetime(*args, tzinfo=ITALY_TZ)


async def _setup(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, title="Corrente", data=PUN_ENTRY)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _state(hass: HomeAssistant, entry: MockConfigEntry, key: str):
    entity_id = er.async_get(hass).async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_{key}")
    return hass.states.get(entity_id)


async def test_flow_pun_contract(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"country": "it"})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"contract_type": "pun"}
    )
    assert result["step_id"] == "prices_pun"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"spread": 0.02, "losses": 10.0, "zone": "pun"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {**PUN_ENTRY, "other_per_kwh": 0.0, "monthly_fixed": 0.0}


async def test_pun_sensors(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(rome(2026, 10, 7, 0, 5))
    aioclient_mock.get(GME_URL, content=ZIP)
    entry = await _setup(hass)
    assert entry.state is ConfigEntryState.LOADED

    # First quarter hour of 7 October: PUN 209,705070 €/MWh.
    wholesale = 0.20970507
    assert float(_state(hass, entry, "wholesale").state) == pytest.approx(wholesale, abs=1e-6)
    expected = wholesale * 1.10 + 0.02
    price = _state(hass, entry, "price")
    assert float(price.state) == pytest.approx(expected, abs=1e-5)
    assert price.attributes["attribution"].startswith("Fonte: Gestore dei Mercati Energetici")
    assert len(price.attributes["schedule"]) > 10
    assert _state(hass, entry, "band").state == "f3"

    best = _state(hass, entry, "best_start")
    assert best.state not in ("unknown", "unavailable")
    next_change = datetime.fromisoformat(_state(hass, entry, "next_price_change").state)
    assert next_change > rome(2026, 10, 7, 0, 5)

    # Only one download: today and tomorrow were in the same file.
    calls = aioclient_mock.call_count
    freezer.tick(timedelta(hours=3))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert aioclient_mock.call_count == calls


async def test_pun_setup_retries_when_gme_is_down(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(rome(2026, 10, 7, 9, 0))
    aioclient_mock.get(GME_URL, status=401)
    entry = await _setup(hass)
    assert entry.state is ConfigEntryState.SETUP_RETRY


def _only_today_zip() -> bytes:
    import io
    import zipfile

    source = zipfile.ZipFile(io.BytesIO(ZIP))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as target:
        for name in source.namelist():
            if name.startswith("20261007"):
                target.writestr(name, source.read(name))
    return out.getvalue()


async def test_tomorrow_is_fetched_after_publication_only(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(rome(2026, 10, 7, 9, 0))
    aioclient_mock.get(GME_URL, content=_only_today_zip())
    entry = await _setup(hass)
    assert aioclient_mock.call_count == 1

    # Morning: tomorrow is not due yet, nothing is downloaded.
    freezer.move_to(rome(2026, 10, 7, 12, 0))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert aioclient_mock.call_count == 1

    # After 13:30 + this installation's minute (at most 14:29): tomorrow is fetched.
    aioclient_mock.clear_requests()
    aioclient_mock.get(GME_URL, content=ZIP)
    freezer.move_to(rome(2026, 10, 7, 14, 45))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert aioclient_mock.call_count == 1
    schedule = _state(hass, entry, "price").attributes["schedule"]
    assert datetime.fromisoformat(schedule[-1]["end"]) > rome(2026, 10, 8, 12, 0)

    # Once tomorrow is known, no more downloads that day.
    freezer.move_to(rome(2026, 10, 7, 18, 0))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert aioclient_mock.call_count == 1


async def test_restart_while_gme_is_down(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
    hass_storage: dict,
) -> None:
    """The prices downloaded before a restart are kept on disk and used while GME is down."""
    freezer.move_to(rome(2026, 10, 7, 0, 5))
    aioclient_mock.get(GME_URL, content=ZIP)
    entry = await _setup(hass)
    key = f"corrente.gme.{entry.entry_id}"
    saved = hass_storage[key]
    assert saved["data"]

    # Restart three hours later with GME not answering.
    await hass.config_entries.async_unload(entry.entry_id)
    aioclient_mock.clear_requests()
    aioclient_mock.get(GME_URL, status=500)
    freezer.tick(timedelta(hours=3))
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert _state(hass, entry, "price").state not in ("unknown", "unavailable")

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert key not in hass_storage
