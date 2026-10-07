"""Tests for the config and options flows."""

from __future__ import annotations

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.corrente.const import DOMAIN


async def test_three_band_flow_creates_entry(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"country": "it"})
    assert result["step_id"] == "italy"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"contract_type": "three_bands"}
    )
    assert result["step_id"] == "prices_three_bands"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"price_f1": 0.30, "price_f2": 0.25, "price_f3": 0.20}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "country": "it",
        "contract_type": "three_bands",
        "price_f1": 0.30,
        "price_f2": 0.25,
        "price_f3": 0.20,
    }


async def test_single_price_flow_asks_one_price(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"country": "it"})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"contract_type": "single"}
    )
    assert result["step_id"] == "prices_single"
    assert list(result["data_schema"].schema) == ["price_f1"]


async def test_options_flow_changes_contract(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"country": "it"})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"contract_type": "single"}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"price_f1": 0.27})
    entry = result["result"]
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.MENU
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "contract"}
    )
    assert result["step_id"] == "contract"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"contract_type": "two_bands"}
    )
    assert result["step_id"] == "prices_two_bands"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"price_f1": 0.31, "price_f2": 0.21}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options == {"contract_type": "two_bands", "price_f1": 0.31, "price_f2": 0.21}
