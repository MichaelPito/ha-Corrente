"""The automation blueprint must be valid for Home Assistant."""

from __future__ import annotations

import shutil
from datetime import timedelta
from pathlib import Path

from homeassistant.components.automation.config import AUTOMATION_BLUEPRINT_SCHEMA
from homeassistant.components.blueprint import models
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from homeassistant.util.yaml import load_yaml
from pytest_homeassistant.common import (
    async_capture_events,
    async_fire_time_changed,
    async_mock_service,
)

BLUEPRINT = (
    Path(__file__).parent.parent
    / "blueprints"
    / "automation"
    / "corrente"
    / "start_at_best_time.yaml"
)


def test_blueprint_is_valid() -> None:
    blueprint = models.Blueprint(
        load_yaml(BLUEPRINT), expected_domain="automation", schema=AUTOMATION_BLUEPRINT_SCHEMA
    )
    assert set(blueprint.inputs) == {"best_start", "ready", "appliance", "notify_device"}


PRICE_ALERT = BLUEPRINT.parent / "price_alert.yaml"


def test_price_alert_is_valid() -> None:
    blueprint = models.Blueprint(
        load_yaml(PRICE_ALERT), expected_domain="automation", schema=AUTOMATION_BLUEPRINT_SCHEMA
    )
    assert set(blueprint.inputs) == {"price_sensor", "direction", "threshold", "actions"}


async def _alert_automation(hass: HomeAssistant, direction: str, threshold: float) -> list:
    target = Path(hass.config.path("blueprints", "automation", "corrente"))
    target.mkdir(parents=True, exist_ok=True)
    shutil.copy(PRICE_ALERT, target / "price_alert.yaml")
    hass.states.async_set("sensor.corrente_price_now", "0.25", {"unit_of_measurement": "CHF/kWh"})
    events = async_capture_events(hass, "corrente_test_alert")
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "use_blueprint": {
                    "path": "corrente/price_alert.yaml",
                    "input": {
                        "price_sensor": "sensor.corrente_price_now",
                        "direction": direction,
                        "threshold": threshold,
                        "actions": [
                            {
                                "event": "corrente_test_alert",
                                "event_data": {"price": "{{ price }}", "unit": "{{ unit }}"},
                            }
                        ],
                    },
                }
            }
        },
    )
    await hass.async_block_till_done()
    return events


async def test_price_alert_fires_once_when_price_drops(hass: HomeAssistant) -> None:
    events = await _alert_automation(hass, "below", 0.20)
    attrs = {"unit_of_measurement": "CHF/kWh"}
    hass.states.async_set("sensor.corrente_price_now", "0.21", attrs)
    await hass.async_block_till_done()
    assert events == []
    hass.states.async_set("sensor.corrente_price_now", "0.19", attrs)
    await hass.async_block_till_done()
    hass.states.async_set("sensor.corrente_price_now", "0.18", attrs)  # still below: no repeat
    await hass.async_block_till_done()
    assert len(events) == 1
    assert events[0].data == {"price": 0.19, "unit": "CHF/kWh"}
    hass.states.async_set("sensor.corrente_price_now", "unavailable")  # not a crossing
    await hass.async_block_till_done()
    hass.states.async_set("sensor.corrente_price_now", "0.17", attrs)
    await hass.async_block_till_done()
    assert len(events) == 2


async def test_price_alert_above(hass: HomeAssistant) -> None:
    events = await _alert_automation(hass, "above", 0.30)
    hass.states.async_set("sensor.corrente_price_now", "0.31", {"unit_of_measurement": "EUR/kWh"})
    await hass.async_block_till_done()
    assert [e.data["price"] for e in events] == [0.31]


SOLAR = BLUEPRINT.parent / "solar_surplus.yaml"


def test_solar_surplus_is_valid() -> None:
    blueprint = models.Blueprint(
        load_yaml(SOLAR), expected_domain="automation", schema=AUTOMATION_BLUEPRINT_SCHEMA
    )
    assert set(blueprint.inputs) == {
        "grid_power",
        "exporting_is",
        "appliance",
        "appliance_power",
        "max_import",
        "delay",
        "price_sensor",
        "cheap_price",
    }


async def _solar(hass: HomeAssistant, **inputs) -> tuple[list, list]:
    target = Path(hass.config.path("blueprints", "automation", "corrente"))
    target.mkdir(parents=True, exist_ok=True)
    shutil.copy(SOLAR, target / "solar_surplus.yaml")
    hass.states.async_set("sensor.grid", "300", {"unit_of_measurement": "W"})
    hass.states.async_set("switch.boiler", "off")
    on = async_mock_service(hass, "switch", "turn_on")
    off = async_mock_service(hass, "switch", "turn_off")
    config = {
        "grid_power": "sensor.grid",
        "appliance": "switch.boiler",
        "appliance_power": 2000,
        "max_import": 200,
        "delay": 5,
        **inputs,
    }
    assert await async_setup_component(
        hass,
        "automation",
        {"automation": {"use_blueprint": {"path": "corrente/solar_surplus.yaml", "input": config}}},
    )
    await hass.async_block_till_done()
    return on, off


async def _wait(hass: HomeAssistant, minutes: float) -> None:
    """Let time pass. "for: N minutes" in triggers waits on the event loop's clock, which
    async_fire_time_changed advances by the offset from the real time: keep that offset."""
    await hass.async_block_till_done()
    offset = hass.data.setdefault("_test_offset", [timedelta(0)])
    offset[0] += timedelta(minutes=minutes)
    async_fire_time_changed(hass, dt_util.utcnow() + offset[0])
    await hass.async_block_till_done()


async def test_solar_surplus_switches_on_and_off(hass: HomeAssistant) -> None:
    on, off = await _solar(hass)
    w = {"unit_of_measurement": "W"}
    # Sun: exporting 2.5 kW (negative), but only for 3 minutes — a passing moment.
    hass.states.async_set("sensor.grid", "-2500", w)
    await _wait(hass, 3)
    hass.states.async_set("sensor.grid", "-800", w)
    await _wait(hass, 5)
    assert on == []
    # Steady surplus for 5 minutes: switch on.
    hass.states.async_set("sensor.grid", "-2400", w)
    await _wait(hass, 5.1)
    assert [c.data["entity_id"] for c in on] == [["switch.boiler"]]
    hass.states.async_set("switch.boiler", "on")
    # With the boiler on the home still exports a little: stays on.
    hass.states.async_set("sensor.grid", "-300", w)
    await _wait(hass, 10)
    assert off == []
    # A cloud: buying 1.5 kW for 5 minutes: switch off.
    hass.states.async_set("sensor.grid", "1500", w)
    await _wait(hass, 5.1)
    assert [c.data["entity_id"] for c in off] == [["switch.boiler"]]


async def test_solar_surplus_kw_positive_when_exporting(hass: HomeAssistant) -> None:
    on, _off = await _solar(hass, exporting_is="positive")
    hass.states.async_set("sensor.grid", "2.1", {"unit_of_measurement": "kW"})
    await _wait(hass, 5.1)
    assert len(on) == 1


async def test_cheap_price_runs_without_sun(hass: HomeAssistant) -> None:
    price = "sensor.corrente_price_now"
    hass.states.async_set(price, "0.25", {"unit_of_measurement": "CHF/kWh"})
    on, off = await _solar(hass, price_sensor=price, cheap_price=0.20)
    w = {"unit_of_measurement": "W"}
    # Night tariff starts: on, even while buying from the grid.
    hass.states.async_set(price, "0.18", {"unit_of_measurement": "CHF/kWh"})
    await hass.async_block_till_done()
    assert len(on) == 1
    hass.states.async_set("switch.boiler", "on")
    hass.states.async_set("sensor.grid", "2300", w)
    await _wait(hass, 10)
    assert off == []  # cheap: no switch-off for lack of sun
    # The cheap hours end while still buying: off.
    hass.states.async_set(price, "0.26", {"unit_of_measurement": "CHF/kWh"})
    await hass.async_block_till_done()
    assert len(off) == 1
