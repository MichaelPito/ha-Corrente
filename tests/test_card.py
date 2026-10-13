"""Tests for serving the dashboard card."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from custom_components.corrente import CARD_URL
from custom_components.corrente.const import DOMAIN


def _italy_entry(title: str) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title=title,
        data={"country": "it", "contract_type": "single", "price_f1": 0.25},
    )


async def test_card_with_several_entries_at_startup(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """At startup every entry is set up at the same time; the card is registered once."""
    entries = [_italy_entry(f"Corrente {n}") for n in range(3)]
    for entry in entries:
        entry.add_to_hass(hass)
    assert await async_setup_component(hass, "http", {})

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    assert [entry.state for entry in entries] == [ConfigEntryState.LOADED] * 3
    client = await hass_client()
    response = await client.get(CARD_URL)
    assert response.status == 200
    assert "corrente-card" in await response.text()
