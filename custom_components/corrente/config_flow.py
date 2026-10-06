"""Config and options flow for Corrente."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_CONTRACT_TYPE,
    CONF_COUNTRY,
    CONF_PRICE_F1,
    CONF_PRICE_F2,
    CONF_PRICE_F3,
    COUNTRY_ITALY,
    DOMAIN,
    DONATE_URL,
    ISSUES_URL,
)
from .core.contract import ItalyContractType

_PLACEHOLDERS = {"issues_url": ISSUES_URL, "donate_url": DONATE_URL}

_PRICE_SELECTOR = NumberSelector(
    NumberSelectorConfig(
        min=0,
        max=5,
        step="any",
        mode=NumberSelectorMode.BOX,
        unit_of_measurement="€/kWh",
    )
)

_CONTRACT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CONTRACT_TYPE): SelectSelector(
            SelectSelectorConfig(
                options=[contract.value for contract in ItalyContractType],
                mode=SelectSelectorMode.LIST,
                translation_key=CONF_CONTRACT_TYPE,
            )
        )
    }
)


def _prices_schema(contract_type: ItalyContractType, defaults: dict[str, Any]) -> vol.Schema:
    """Return the price fields needed by a contract type."""
    fields = [CONF_PRICE_F1]
    if contract_type is not ItalyContractType.SINGLE:
        fields.append(CONF_PRICE_F2)
    if contract_type is ItalyContractType.THREE_BANDS:
        fields.append(CONF_PRICE_F3)
    return vol.Schema(
        {
            vol.Required(field, default=defaults[field])
            if field in defaults
            else vol.Required(field): _PRICE_SELECTOR
            for field in fields
        }
    )


def _step_id_for(contract_type: ItalyContractType) -> str:
    return f"prices_{contract_type.value}"


class CorrenteConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up Corrente from the UI."""

    VERSION = 1

    def __init__(self) -> None:
        self._contract_type: ItalyContractType | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Choose the shape of the contract."""
        if user_input is not None:
            self._contract_type = ItalyContractType(user_input[CONF_CONTRACT_TYPE])
            return await self._async_step_prices()
        return self.async_show_form(
            step_id="user",
            data_schema=_CONTRACT_SCHEMA,
            description_placeholders=_PLACEHOLDERS,
        )

    async def async_step_prices_single(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Enter the price of a single-price contract."""
        return await self._async_step_prices(user_input)

    async def async_step_prices_two_bands(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Enter the prices of a two-band contract."""
        return await self._async_step_prices(user_input)

    async def async_step_prices_three_bands(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Enter the prices of a three-band contract."""
        return await self._async_step_prices(user_input)

    async def _async_step_prices(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        assert self._contract_type is not None
        if user_input is not None:
            return self.async_create_entry(
                title="Corrente",
                data={
                    CONF_COUNTRY: COUNTRY_ITALY,
                    CONF_CONTRACT_TYPE: self._contract_type.value,
                    **user_input,
                },
            )
        return self.async_show_form(
            step_id=_step_id_for(self._contract_type),
            data_schema=_prices_schema(self._contract_type, {}),
            description_placeholders=_PLACEHOLDERS,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> CorrenteOptionsFlow:
        """Return the options flow."""
        return CorrenteOptionsFlow()


class CorrenteOptionsFlow(OptionsFlow):
    """Change the contract after setup."""

    def __init__(self) -> None:
        self._contract_type: ItalyContractType | None = None

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Choose the shape of the contract."""
        current = {**self.config_entry.data, **self.config_entry.options}
        if user_input is not None:
            self._contract_type = ItalyContractType(user_input[CONF_CONTRACT_TYPE])
            return await self._async_step_prices()
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(_CONTRACT_SCHEMA, current),
            description_placeholders=_PLACEHOLDERS,
        )

    async def async_step_prices_single(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the price of a single-price contract."""
        return await self._async_step_prices(user_input)

    async def async_step_prices_two_bands(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the prices of a two-band contract."""
        return await self._async_step_prices(user_input)

    async def async_step_prices_three_bands(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the prices of a three-band contract."""
        return await self._async_step_prices(user_input)

    async def _async_step_prices(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        assert self._contract_type is not None
        if user_input is not None:
            return self.async_create_entry(
                data={CONF_CONTRACT_TYPE: self._contract_type.value, **user_input}
            )
        current = {**self.config_entry.data, **self.config_entry.options}
        defaults = {
            key: value
            for key, value in current.items()
            if key in (CONF_PRICE_F1, CONF_PRICE_F2, CONF_PRICE_F3) and value is not None
        }
        return self.async_show_form(
            step_id=_step_id_for(self._contract_type),
            data_schema=_prices_schema(self._contract_type, defaults),
            description_placeholders=_PLACEHOLDERS,
        )
