"""The automation blueprint must be valid for Home Assistant."""

from __future__ import annotations

import shutil
from pathlib import Path

from homeassistant.components.automation.config import AUTOMATION_BLUEPRINT_SCHEMA
from homeassistant.components.blueprint import models
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util.yaml import load_yaml
from pytest_homeassistant_custom_component.common import async_capture_events

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
