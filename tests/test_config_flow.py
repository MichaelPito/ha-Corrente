"""Tests for the config and options flows."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.corrente.config_flow import _standard_electricity, _tariff_choice
from custom_components.corrente.const import DOMAIN, ISSUES_URL
from custom_components.corrente.core.switzerland import parse_tariffs


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
    # The menu carries the "Suggest a change" link.
    assert result["description_placeholders"]["issues_url"] == ISSUES_URL
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


def test_fees_with_one_name_for_every_municipality_are_stored_once() -> None:
    """BKW names every municipality's fees the same: the entry keeps the name once."""
    document = (Path(__file__).parent / "fixtures" / "ch" / "bkw-2026.json").read_text("utf-8")
    tariffs = parse_tariffs(json.loads(document))
    name = "Konzessionsabgabe/Redevance de concession"
    choice = _tariff_choice(
        tariffs,
        "Energy Blue",
        {"grid_tariff": "Einheitstarif // Tarif unique", "regional_tariff": [name, name]},
        date(2026, 10, 14),
        362,
    )
    assert choice["regional_tariff"] == [name]
    assert choice["canton"] == "BE"


def test_operators_standard_energy_tariff_is_preselected() -> None:
    """ewz flags "ewz.natur" as its standard tariff; AIL flags none."""
    fixtures = Path(__file__).parent / "fixtures" / "ch"
    ewz = parse_tariffs(json.loads((fixtures / "ewz-2026.json").read_text("utf-8")))
    ail = parse_tariffs(json.loads((fixtures / "ail-2027.json").read_text("utf-8")))
    assert _standard_electricity(ewz, date(2026, 10, 15)) == "ewz.natur"
    assert _standard_electricity(ail, date(2027, 3, 10)) is None
