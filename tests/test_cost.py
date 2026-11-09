"""Tests for the cost sensors (Italian three-band contract)."""

from __future__ import annotations

from datetime import datetime

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant, State
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    mock_restore_cache,
)

from custom_components.corrente.const import DOMAIN
from custom_components.corrente.core.italy import ITALY_TZ

METER = "sensor.grid_import"
CONTRACT = {
    "country": "it",
    "contract_type": "three_bands",
    "price_f1": 0.30,
    "price_f2": 0.25,
    "price_f3": 0.20,
}


def rome(*args: int) -> datetime:
    return datetime(*args, tzinfo=ITALY_TZ)


async def _setup(hass: HomeAssistant, options: dict | None = None) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Corrente",
        data=CONTRACT,
        options={"energy_sensor": METER} if options is None else options,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _cost(hass: HomeAssistant, entry: MockConfigEntry, period: str) -> State | None:
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_cost_{period}"
    )
    return None if entity_id is None else hass.states.get(entity_id)


async def _meter(hass: HomeAssistant, value: float, unit: str = "kWh") -> None:
    hass.states.async_set(METER, str(value), {"unit_of_measurement": unit})
    await hass.async_block_till_done()


async def test_each_kwh_is_priced_when_used(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(rome(2026, 10, 7, 18, 0))  # F1
    entry = await _setup(hass)
    await _meter(hass, 1000.0)  # first reading: only a reference
    assert float(_cost(hass, entry, "day").state) == 0

    await _meter(hass, 1002.0)  # 2 kWh in F1 at 0.30
    freezer.move_to(rome(2026, 10, 7, 20, 0))  # F2
    await _meter(hass, 1003000.0, unit="Wh")  # 1 kWh more, reported in Wh, at 0.25

    day = _cost(hass, entry, "day")
    assert float(day.state) == pytest.approx(0.85)
    assert day.attributes["energy_kwh"] == pytest.approx(3.0)
    assert day.attributes["unit_of_measurement"] == "EUR"
    assert float(_cost(hass, entry, "month").state) == pytest.approx(0.85)


async def test_day_resets_at_midnight_month_keeps_going(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(rome(2026, 10, 7, 22, 0))  # F2
    entry = await _setup(hass)
    await _meter(hass, 10.0)
    await _meter(hass, 12.0)  # 2 kWh at 0.25

    freezer.move_to(rome(2026, 10, 8, 0, 0))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert float(_cost(hass, entry, "day").state) == 0
    assert float(_cost(hass, entry, "month").state) == pytest.approx(0.50)

    await _meter(hass, 13.0)  # 1 kWh in F3 at 0.20
    assert float(_cost(hass, entry, "day").state) == pytest.approx(0.20)
    assert float(_cost(hass, entry, "month").state) == pytest.approx(0.70)


async def test_meter_glitches_are_ignored(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(rome(2026, 10, 7, 12, 0))
    entry = await _setup(hass)
    await _meter(hass, 500.0)
    hass.states.async_set(METER, "unavailable")
    await hass.async_block_till_done()
    await _meter(hass, 0.0)  # meter reset or replaced
    await _meter(hass, 900.0)  # absurd jump
    await _meter(hass, 901.0)  # 1 kWh at 0.30
    assert float(_cost(hass, entry, "day").state) == pytest.approx(0.30)


async def test_restored_after_restart(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    freezer.move_to(rome(2026, 10, 7, 12, 0))
    mock_restore_cache(
        hass,
        [
            State(
                "sensor.corrente_cost_today",
                "1.5",
                {"period": "2026-10-07", "energy_kwh": 5.0, "last_reading_kwh": 100.0},
            ),
            State(
                "sensor.corrente_cost_this_month",
                "9.0",
                {"period": "2026-09", "energy_kwh": 30.0, "last_reading_kwh": 100.0},
            ),
        ],
    )
    entry = await _setup(hass)
    assert float(_cost(hass, entry, "day").state) == pytest.approx(1.5)
    # Last month's total is not carried into October.
    assert float(_cost(hass, entry, "month").state) == 0

    await _meter(hass, 101.0)  # continues from the restored reading: 1 kWh at 0.30
    assert float(_cost(hass, entry, "day").state) == pytest.approx(1.8)


async def test_no_meter_no_cost_sensors(hass: HomeAssistant) -> None:
    entry = await _setup(hass, options={})
    assert _cost(hass, entry, "day") is None


async def test_meter_is_chosen_from_the_options(hass: HomeAssistant) -> None:
    entry = await _setup(hass, options={})
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "meter"}
    )
    assert result["step_id"] == "meter"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"energy_sensor": METER}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options["energy_sensor"] == METER
    assert _cost(hass, entry, "day") is not None


PLUG = "sensor.plug_dishwasher_energy"


async def test_cost_per_appliance(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """A smart plug gets its own cost sensors, named after the plug; removing it removes them."""
    freezer.move_to(rome(2026, 10, 7, 20, 0))  # F2, 0.25 €/kWh
    plug_entry = MockConfigEntry(domain="shelly")
    plug_entry.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=plug_entry.entry_id, identifiers={("shelly", "plug1")}, name="Lavastoviglie"
    )
    er.async_get(hass).async_get_or_create(
        "sensor",
        "shelly",
        "plug1-energy",
        suggested_object_id="plug_dishwasher_energy",
        device_id=device.id,
    )
    entry = await _setup(hass, options={})

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "appliances"}
    )
    assert result["step_id"] == "appliances"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"appliance_sensors": [PLUG]}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    day_id = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_appliance_day_{PLUG}"
    )
    month_id = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_appliance_month_{PLUG}"
    )
    assert day_id and month_id
    assert hass.states.get(day_id).name == "Corrente Cost today — Lavastoviglie"
    assert _cost(hass, entry, "day") is None  # no home meter configured: no home cost

    hass.states.async_set(PLUG, "10.0", {"unit_of_measurement": "kWh"})
    await hass.async_block_till_done()
    hass.states.async_set(PLUG, "11.2", {"unit_of_measurement": "kWh"})  # 1.2 kWh at 0.25
    await hass.async_block_till_done()
    assert float(hass.states.get(day_id).state) == pytest.approx(0.30)
    assert float(hass.states.get(month_id).state) == pytest.approx(0.30)
    assert hass.states.get(day_id).attributes["meter"] == PLUG

    # Taken out of the options: its sensors go away.
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "appliances"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"appliance_sensors": []}
    )
    await hass.async_block_till_done()
    assert (
        registry.async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_appliance_day_{PLUG}")
        is None
    )
