"""Corrente: electricity prices and tariffs for Italy and Switzerland."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_CONTRACT_TYPE, CONF_PRICE_F1, CONF_PRICE_F2, CONF_PRICE_F3
from .core.contract import ItalyContractType, ItalyFixedContract

PLATFORMS: list[Platform] = [Platform.SENSOR]

type CorrenteConfigEntry = ConfigEntry[ItalyFixedContract]


def contract_from_options(options: dict) -> ItalyFixedContract:
    """Build the contract described by a config entry's options."""
    return ItalyFixedContract(
        contract_type=ItalyContractType(options[CONF_CONTRACT_TYPE]),
        price_f1=options[CONF_PRICE_F1],
        price_f2=options.get(CONF_PRICE_F2),
        price_f3=options.get(CONF_PRICE_F3),
    )


async def async_setup_entry(hass: HomeAssistant, entry: CorrenteConfigEntry) -> bool:
    """Set up Corrente from a config entry."""
    entry.runtime_data = contract_from_options({**entry.data, **entry.options})
    entry.async_on_unload(entry.add_update_listener(_async_reload_on_update))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: CorrenteConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload_on_update(hass: HomeAssistant, entry: CorrenteConfigEntry) -> None:
    """Reload when the user changes the contract in the options."""
    await hass.config_entries.async_reload(entry.entry_id)
