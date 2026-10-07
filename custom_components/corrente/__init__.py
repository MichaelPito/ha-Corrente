"""Corrente: electricity prices and tariffs for Italy and Switzerland."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import (
    CONF_CONTRACT_TYPE,
    CONF_COUNTRY,
    CONF_LOSSES,
    CONF_PRICE_F1,
    CONF_PRICE_F2,
    CONF_PRICE_F3,
    CONF_SPREAD,
    CONF_ZONE,
    COUNTRY_SWITZERLAND,
    DOMAIN,
)
from .coordinator import SwissTariffCoordinator
from .coordinator_gme import GmePriceCoordinator
from .core.contract import ItalyContractType, ItalyFixedContract, ItalyIndexedContract

PLATFORMS: list[Platform] = [Platform.SENSOR]

CARD_URL = "/corrente/corrente-card.js"
_CARD_PATH = Path(__file__).parent / "frontend" / "corrente-card.js"
_CARD_REGISTERED = f"{DOMAIN}_card_registered"


async def _async_register_card(hass: HomeAssistant) -> None:
    """Serve the dashboard card and load it in the frontend, once per Home Assistant run."""
    if hass.data.get(_CARD_REGISTERED) or hass.http is None:
        return
    from homeassistant.components.frontend import add_extra_js_url
    from homeassistant.components.http import StaticPathConfig

    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(_CARD_PATH), cache_headers=False)]
    )
    if "frontend" in hass.config.components:
        manifest = await hass.async_add_executor_job(
            (Path(__file__).parent / "manifest.json").read_text
        )
        add_extra_js_url(hass, f"{CARD_URL}?v={json.loads(manifest)['version']}")
    hass.data[_CARD_REGISTERED] = True


@dataclass(slots=True)
class CorrenteData:
    """What a config entry needs at runtime: an Italian contract or a Swiss coordinator."""

    italy: ItalyFixedContract | None = None
    switzerland: SwissTariffCoordinator | None = None
    italy_indexed: ItalyIndexedContract | None = None
    gme: GmePriceCoordinator | None = None


type CorrenteConfigEntry = ConfigEntry[CorrenteData]


def contract_from_options(options: dict) -> ItalyFixedContract:
    """Build the Italian contract described by a config entry's options."""
    return ItalyFixedContract(
        contract_type=ItalyContractType(options[CONF_CONTRACT_TYPE]),
        price_f1=options[CONF_PRICE_F1],
        price_f2=options.get(CONF_PRICE_F2),
        price_f3=options.get(CONF_PRICE_F3),
    )


async def async_setup_entry(hass: HomeAssistant, entry: CorrenteConfigEntry) -> bool:
    """Set up Corrente from a config entry."""
    await _async_register_card(hass)
    if entry.data.get(CONF_COUNTRY) == COUNTRY_SWITZERLAND:
        coordinator = SwissTariffCoordinator(hass, entry)
        await coordinator.async_config_entry_first_refresh()
        entry.runtime_data = CorrenteData(switzerland=coordinator)
    elif {**entry.data, **entry.options}[CONF_CONTRACT_TYPE] == ItalyContractType.INDEXED:
        options = {**entry.data, **entry.options}
        indexed = ItalyIndexedContract(
            spread=options[CONF_SPREAD],
            losses=options.get(CONF_LOSSES, 0.0) / 100,
            zone=options.get(CONF_ZONE, "pun").upper(),
        )
        gme = GmePriceCoordinator(hass, entry, indexed.zone)
        await gme.async_config_entry_first_refresh()
        entry.runtime_data = CorrenteData(italy_indexed=indexed, gme=gme)
    else:
        entry.runtime_data = CorrenteData(
            italy=contract_from_options({**entry.data, **entry.options})
        )
    entry.async_on_unload(entry.add_update_listener(_async_reload_on_update))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: CorrenteConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload_on_update(hass: HomeAssistant, entry: CorrenteConfigEntry) -> None:
    """Reload when the user changes the contract in the options."""
    await hass.config_entries.async_reload(entry.entry_id)
