"""Corrente: electricity prices and tariffs for Italy and Switzerland."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import (
    CONF_CONTRACT_TYPE,
    CONF_COUNTRY,
    CONF_LOSSES,
    CONF_MONTHLY_FIXED,
    CONF_OTHER_PER_KWH,
    CONF_PRICE_F1,
    CONF_PRICE_F2,
    CONF_PRICE_F3,
    CONF_SPREAD,
    CONF_ZONE,
    COUNTRY_SWITZERLAND,
    DOMAIN,
)
from .coordinator import SwissTariffCoordinator, no_tariffs_issue_id, tariff_file_store
from .coordinator_gme import GmePriceCoordinator
from .core.contract import ItalyContractType, ItalyFixedContract, ItalyIndexedContract
from .guide import async_dismiss_notification, async_setup_guide

PLATFORMS: list[Platform] = [Platform.SENSOR]

CARD_URL = "/corrente/corrente-card.js"
_CARD_PATH = Path(__file__).parent / "frontend" / "corrente-card.js"
_CARD_REGISTERED = f"{DOMAIN}_card_registered"


async def _async_register_card(hass: HomeAssistant) -> None:
    """Serve the dashboard card and load it in the frontend, once per Home Assistant run."""
    if hass.data.get(_CARD_REGISTERED) or hass.http is None:
        return
    # Claimed before the first await: at startup every entry is set up at the same time,
    # and a second registration of the same path fails the entry.
    hass.data[_CARD_REGISTERED] = True
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
        other_per_kwh=options.get(CONF_OTHER_PER_KWH) or 0.0,
        monthly_fixed=options.get(CONF_MONTHLY_FIXED) or 0.0,
    )


async def async_setup_entry(hass: HomeAssistant, entry: CorrenteConfigEntry) -> bool:
    """Set up Corrente from a config entry."""
    await _async_register_card(hass)
    await async_setup_guide(hass)
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
            other_per_kwh=options.get(CONF_OTHER_PER_KWH) or 0.0,
            monthly_fixed=options.get(CONF_MONTHLY_FIXED) or 0.0,
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


async def async_remove_entry(hass: HomeAssistant, entry: CorrenteConfigEntry) -> None:
    """Remove what the entry left in Repairs, and the guide's notice with the last entry."""
    ir.async_delete_issue(hass, DOMAIN, no_tariffs_issue_id(entry.entry_id))
    await tariff_file_store(hass, entry.entry_id).async_remove()
    if not any(e.entry_id != entry.entry_id for e in hass.config_entries.async_entries(DOMAIN)):
        async_dismiss_notification(hass)


async def _async_reload_on_update(hass: HomeAssistant, entry: CorrenteConfigEntry) -> None:
    """Reload when the user changes the contract in the options."""
    await hass.config_entries.async_reload(entry.entry_id)
