"""The automation blueprint must be valid for Home Assistant."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components.automation.config import AUTOMATION_BLUEPRINT_SCHEMA
from homeassistant.components.blueprint import models
from homeassistant.util.yaml import load_yaml

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
