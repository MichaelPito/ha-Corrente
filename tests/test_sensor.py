"""Tests for the sensors."""

from __future__ import annotations

from datetime import datetime, timedelta

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.corrente.const import DOMAIN
from custom_components.corrente.core.italy import ITALY_TZ


def _entity_id(hass: HomeAssistant, entry: MockConfigEntry, key: str) -> str:
    entity_id = er.async_get(hass).async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_{key}")
    assert entity_id is not None
    return entity_id


async def _setup(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Corrente",
        data={
            "country": "it",
            "contract_type": "three_bands",
            "price_f1": 0.30,
            "price_f2": 0.25,
            "price_f3": 0.20,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_sensors_follow_the_bands(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Wednesday 7 October 2026, 18:30 in Rome: F1, next change 19:00 to F2.
    freezer.move_to(datetime(2026, 10, 7, 18, 30, tzinfo=ITALY_TZ))
    entry = await _setup(hass)

    assert hass.states.get(_entity_id(hass, entry, "price")).state == "0.3"
    assert hass.states.get(_entity_id(hass, entry, "band")).state == "F1"
    assert hass.states.get(_entity_id(hass, entry, "next_band")).state == "F2"
    assert hass.states.get(_entity_id(hass, entry, "next_price")).state == "0.25"
    next_change = hass.states.get(_entity_id(hass, entry, "next_band_change")).state
    assert datetime.fromisoformat(next_change) == datetime(2026, 10, 7, 19, 0, tzinfo=ITALY_TZ)

    # At 19:00 the sensors refresh on their own.
    freezer.tick(timedelta(minutes=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(_entity_id(hass, entry, "band")).state == "F2"
    assert hass.states.get(_entity_id(hass, entry, "price")).state == "0.25"
    assert hass.states.get(_entity_id(hass, entry, "next_band")).state == "F3"


async def test_unload(hass: HomeAssistant) -> None:
    entry = await _setup(hass)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
