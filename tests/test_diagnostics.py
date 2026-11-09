"""Diagnostics to attach to a request: what Corrente read and computed."""

from __future__ import annotations

import json

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.json import JSONEncoder
from homeassistant.setup import async_setup_component
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import (
    get_diagnostics_for_config_entry,
)
from pytest_homeassistant.typing import ClientSessionGenerator

from custom_components.corrente.const import DOMAIN
from custom_components.corrente.core.version import VERSION
from custom_components.corrente.diagnostics import async_get_config_entry_diagnostics

from .test_switzerland_ha import AIL_DAY_NIGHT, WEDNESDAY_10AM, mock_ch  # noqa: F401


async def test_switzerland(
    hass: HomeAssistant,
    mock_ch,  # noqa: F811
    freezer: FrozenDateTimeFactory,
) -> None:
    # Called directly: with the clock in 2027, the web API's test login has expired.
    freezer.move_to(WEDNESDAY_10AM)
    entry = MockConfigEntry(domain=DOMAIN, data=AIL_DAY_NIGHT)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    assert diagnostics["version"] == VERSION
    swiss = diagnostics["switzerland"]
    assert swiss["municipality"] == 5192
    assert swiss["period_now"] == "high"
    assert [t["name"] for t in swiss["tariffs"]][:2] == [
        "Casa & PMI giorno-notte-electricity",
        "Casa & PMI giorno-notte-grid7",
    ]
    assert swiss["tariffs"][0]["windows_chf_per_kwh"]
    assert swiss["next_24_hours"][0]["price"] == swiss["price_now_with_vat"]
    json.dumps(diagnostics, cls=JSONEncoder)  # what the download does


async def test_italy(hass: HomeAssistant, hass_client: ClientSessionGenerator) -> None:
    assert await async_setup_component(hass, "diagnostics", {})
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"country": "it", "contract_type": "two_bands", "price_f1": 0.25, "price_f2": 0.2},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    diagnostics = await get_diagnostics_for_config_entry(hass, hass_client, entry)
    assert diagnostics["italy"]["price_f1"] == 0.25
    assert diagnostics["italy"]["contract_type"] == "two_bands"
