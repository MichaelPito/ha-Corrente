"""Corrente: electricity prices and tariffs for Italy and Switzerland."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import (
    CONF_CONTRACT_TYPE,
    CONF_COUNTRY,
    CONF_PRICE_F1,
    CONF_PRICE_F2,
    CONF_PRICE_F3,
    COUNTRY_SWITZERLAND,
)
from .coordinator import SwissTariffCoordinator
from .core.contract import ItalyContractType, ItalyFixedContract

PLATFORMS: list[Platform] = [Platform.SENSOR]


@dataclass(slots=True)
class CorrenteData:
    """What a config entry needs at runtime: an Italian contract or a Swiss coordinator."""

    italy: ItalyFixedContract | None = None
    switzerland: SwissTariffCoordinator | None = None


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
    if entry.data.get(CONF_COUNTRY) == COUNTRY_SWITZERLAND:
        coordinator = SwissTariffCoordinator(hass, entry)
        await coordinator.async_config_entry_first_refresh()
        entry.runtime_data = CorrenteData(switzerland=coordinator)
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
