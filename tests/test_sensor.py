"""Tests for the sensors."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant.common import (
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
    assert hass.states.get(_entity_id(hass, entry, "band")).state == "f1"
    assert hass.states.get(_entity_id(hass, entry, "next_band")).state == "f2"
    assert hass.states.get(_entity_id(hass, entry, "next_price")).state == "0.25"
    next_change = hass.states.get(_entity_id(hass, entry, "next_band_change")).state
    assert datetime.fromisoformat(next_change) == datetime(2026, 10, 7, 19, 0, tzinfo=ITALY_TZ)

    # Cheapest 2 hours in the next 24: F3 from 23:00.
    best = hass.states.get(_entity_id(hass, entry, "best_start"))
    assert datetime.fromisoformat(best.state) == datetime(2026, 10, 7, 23, 0, tzinfo=ITALY_TZ)
    assert best.attributes["average_price"] == 0.20
    schedule = hass.states.get(_entity_id(hass, entry, "price")).attributes["schedule"]
    assert [(item["price"]) for item in schedule[:3]] == [0.30, 0.25, 0.20]

    # At 19:00 the sensors refresh on their own.
    freezer.tick(timedelta(minutes=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(_entity_id(hass, entry, "band")).state == "f2"
    assert hass.states.get(_entity_id(hass, entry, "price")).state == "0.25"
    assert hass.states.get(_entity_id(hass, entry, "next_band")).state == "f3"


async def test_unload(hass: HomeAssistant) -> None:
    entry = await _setup(hass)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_appliance_duration_from_options(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(datetime(2026, 10, 7, 18, 30, tzinfo=ITALY_TZ))
    entry = await _setup(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "appliance"}
    )
    assert result["step_id"] == "appliance"
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"best_hours": 4})
    await hass.async_block_till_done()
    assert entry.options["best_hours"] == 4.0

    best = hass.states.get(_entity_id(hass, entry, "best_start"))
    assert best.attributes["duration_hours"] == 4.0
    assert "4 h" in best.attributes["friendly_name"]
    # Four hours of F3 from 23:00 (Wednesday night).
    assert datetime.fromisoformat(best.state) == datetime(2026, 10, 7, 23, 0, tzinfo=ITALY_TZ)


async def test_other_costs_from_the_bill(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """With the bill's other costs entered, the price includes them and the fixed costs
    per month get a sensor of their own (not created when none are entered)."""
    freezer.move_to(datetime(2026, 10, 7, 18, 30, tzinfo=ITALY_TZ))
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "country": "it",
            "contract_type": "single",
            "price_f1": 0.12,
            "other_per_kwh": 0.07,
            "monthly_fixed": 9.5,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    price = hass.states.get(_entity_id(hass, entry, "price"))
    assert float(price.state) == pytest.approx(0.19)
    assert price.attributes["other_costs_per_kwh"] == 0.07
    assert hass.states.get(_entity_id(hass, entry, "monthly_fixed")).state == "9.5"


async def test_no_fixed_costs_sensor_without_them(hass: HomeAssistant) -> None:
    entry = await _setup(hass)
    registry = er.async_get(hass)
    assert registry.async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_monthly_fixed") is None
