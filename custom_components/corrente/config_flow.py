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
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.util import dt as dt_util

from .const import (
    CONF_CANTON,
    CONF_CONTRACT_TYPE,
    CONF_COUNTRY,
    CONF_ELECTRICITY_TARIFF,
    CONF_GRID_TARIFF,
    CONF_MUNICIPALITY,
    CONF_MUNICIPALITY_NAME,
    CONF_OPERATOR_ID,
    CONF_OPERATOR_NAME,
    CONF_PRICE_F1,
    CONF_PRICE_F2,
    CONF_PRICE_F3,
    CONF_REGIONAL_TARIFF,
    CONF_TARIFF_URL,
    COUNTRY_ITALY,
    COUNTRY_SWITZERLAND,
    DOMAIN,
    DONATE_URL,
    ISSUES_URL,
)
from .core.contract import ItalyContractType
from .core.elcom import (
    ElcomError,
    OperatorInMunicipality,
    TariffFileError,
    async_fetch_tariff_document,
    async_search_municipalities,
)
from .core.switzerland import (
    SWISS_TZ,
    Tariff,
    UnsupportedTariffError,
    parse_tariffs,
    suggest_matching,
    tariffs_on,
)

_PLACEHOLDERS = {"issues_url": ISSUES_URL, "donate_url": DONATE_URL}
_NO_REGIONAL = "none"

_PRICE_SELECTOR = NumberSelector(
    NumberSelectorConfig(
        min=0,
        max=5,
        step="any",
        mode=NumberSelectorMode.BOX,
        unit_of_measurement="€/kWh",
    )
)

_COUNTRY_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_COUNTRY): SelectSelector(
            SelectSelectorConfig(
                options=[COUNTRY_ITALY, COUNTRY_SWITZERLAND],
                mode=SelectSelectorMode.LIST,
                translation_key=CONF_COUNTRY,
            )
        )
    }
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

_SEARCH_SCHEMA = vol.Schema({vol.Required(CONF_MUNICIPALITY): TextSelector()})
_URL_SCHEMA = vol.Schema(
    {vol.Required(CONF_TARIFF_URL): TextSelector(TextSelectorConfig(type=TextSelectorType.URL))}
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


def _select(options: list[str], *, key: str, default: str | None = None) -> vol.Schema:
    selector = SelectSelector(
        SelectSelectorConfig(
            options=[SelectOptionDict(value=o, label=o) for o in options],
            mode=SelectSelectorMode.DROPDOWN,
        )
    )
    marker = vol.Required(key, default=default) if default else vol.Required(key)
    return vol.Schema({marker: selector})


def _supported(tariff: Tariff) -> bool:
    try:
        tariff.check_supported()
    except UnsupportedTariffError:
        return False
    return bool(tariff.energy)


class CorrenteConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up Corrente from the UI."""

    VERSION = 1

    def __init__(self) -> None:
        self._contract_type: ItalyContractType | None = None
        self._matches: list[OperatorInMunicipality] = []
        self._operator: OperatorInMunicipality | None = None
        self._tariff_url: str | None = None
        self._tariffs: list[Tariff] = []
        self._electricity: str | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Choose the country."""
        if user_input is not None:
            if user_input[CONF_COUNTRY] == COUNTRY_SWITZERLAND:
                return await self.async_step_ch_search()
            return await self.async_step_italy()
        return self.async_show_form(
            step_id="user", data_schema=_COUNTRY_SCHEMA, description_placeholders=_PLACEHOLDERS
        )

    # Italy ---------------------------------------------------------------

    async def async_step_italy(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Choose the shape of the Italian contract."""
        if user_input is not None:
            self._contract_type = ItalyContractType(user_input[CONF_CONTRACT_TYPE])
            return await self._async_step_prices()
        return self.async_show_form(
            step_id="italy", data_schema=_CONTRACT_SCHEMA, description_placeholders=_PLACEHOLDERS
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

    # Switzerland ---------------------------------------------------------

    async def async_step_ch_search(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Find the municipality and its grid operator(s) in ElCom open data."""
        errors: dict[str, str] = {}
        if user_input is not None:
            year = dt_util.now(SWISS_TZ).year
            try:
                self._matches = await async_search_municipalities(
                    async_get_clientsession(self.hass), user_input[CONF_MUNICIPALITY], year
                )
            except ElcomError:
                errors["base"] = "cannot_connect"
            else:
                if not self._matches:
                    errors[CONF_MUNICIPALITY] = "no_match"
                elif len(self._matches) == 1:
                    return await self._async_use_operator(self._matches[0])
                else:
                    return await self.async_step_ch_operator()
        return self.async_show_form(
            step_id="ch_search",
            data_schema=_SEARCH_SCHEMA,
            errors=errors,
            description_placeholders=_PLACEHOLDERS,
        )

    async def async_step_ch_operator(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose among several municipalities or operators."""
        labels = {f"{m.municipality_name} — {m.operator_name}": m for m in self._matches}
        if user_input is not None:
            return await self._async_use_operator(labels[user_input[CONF_OPERATOR_NAME]])
        return self.async_show_form(
            step_id="ch_operator", data_schema=_select(list(labels), key=CONF_OPERATOR_NAME)
        )

    async def _async_use_operator(self, operator: OperatorInMunicipality) -> ConfigFlowResult:
        self._operator = operator
        if operator.tariff_url and await self._async_load_tariffs(operator.tariff_url):
            return await self.async_step_ch_tariff()
        return await self.async_step_ch_url()

    async def _async_load_tariffs(self, url: str) -> bool:
        try:
            document = await async_fetch_tariff_document(async_get_clientsession(self.hass), url)
        except TariffFileError:
            return False
        today = dt_util.now(SWISS_TZ).date()
        tariffs = parse_tariffs(document)
        if not any(_supported(t) for t in tariffs_on(tariffs, "electricity", today)):
            return False
        self._tariff_url = url
        self._tariffs = tariffs
        return True

    async def async_step_ch_url(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """The operator publishes no readable file: ask for the link."""
        assert self._operator is not None
        errors: dict[str, str] = {}
        if user_input is not None:
            if await self._async_load_tariffs(user_input[CONF_TARIFF_URL].strip()):
                return await self.async_step_ch_tariff()
            errors[CONF_TARIFF_URL] = "invalid_file"
        return self.async_show_form(
            step_id="ch_url",
            data_schema=_URL_SCHEMA,
            errors=errors,
            description_placeholders={
                **_PLACEHOLDERS,
                "operator": self._operator.operator_name,
                "elcom_url": self._operator.tariff_url or "—",
            },
        )

    async def async_step_ch_tariff(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose the energy tariff."""
        today = dt_util.now(SWISS_TZ).date()
        names = sorted(
            {t.name for t in tariffs_on(self._tariffs, "electricity", today) if _supported(t)}
        )
        if user_input is not None:
            self._electricity = user_input[CONF_ELECTRICITY_TARIFF]
            return await self.async_step_ch_grid()
        return self.async_show_form(
            step_id="ch_tariff",
            data_schema=_select(names, key=CONF_ELECTRICITY_TARIFF),
            description_placeholders={"operator": self._operator.operator_name},
        )

    async def async_step_ch_grid(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the grid tariff and the regional fees that go with the energy tariff."""
        assert self._operator is not None and self._electricity is not None
        today = dt_util.now(SWISS_TZ).date()
        grids = [t for t in tariffs_on(self._tariffs, "grid", today) if _supported(t)]
        regionals = tariffs_on(self._tariffs, "regional_fees", today)
        if user_input is not None:
            regional_name = user_input[CONF_REGIONAL_TARIFF]
            regional = next((t for t in regionals if t.name == regional_name), None)
            cantons = sorted(regional.canton_energy) if regional else []
            return self.async_create_entry(
                title=f"Corrente — {self._operator.operator_name}",
                data={
                    CONF_COUNTRY: COUNTRY_SWITZERLAND,
                    CONF_MUNICIPALITY: self._operator.municipality,
                    CONF_MUNICIPALITY_NAME: self._operator.municipality_name,
                    CONF_OPERATOR_ID: self._operator.operator_id,
                    CONF_OPERATOR_NAME: self._operator.operator_name,
                    CONF_TARIFF_URL: self._tariff_url,
                    CONF_ELECTRICITY_TARIFF: self._electricity,
                    CONF_GRID_TARIFF: user_input[CONF_GRID_TARIFF],
                    CONF_REGIONAL_TARIFF: None if regional is None else regional.name,
                    CONF_CANTON: cantons[0] if cantons else None,
                },
            )
        grid_names = sorted({t.name for t in grids})
        regional_names = sorted({t.name for t in regionals})
        suggested_grid = suggest_matching(self._electricity, grids)
        suggested_regional = suggest_matching(self._electricity, regionals)
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_GRID_TARIFF,
                    default=suggested_grid.name if suggested_grid else vol.UNDEFINED,
                ): SelectSelector(
                    SelectSelectorConfig(options=grid_names, mode=SelectSelectorMode.DROPDOWN)
                ),
                vol.Required(
                    CONF_REGIONAL_TARIFF,
                    default=suggested_regional.name if suggested_regional else _NO_REGIONAL,
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=[*regional_names, _NO_REGIONAL], mode=SelectSelectorMode.DROPDOWN
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id="ch_grid",
            data_schema=schema,
            description_placeholders={"electricity": self._electricity},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> CorrenteOptionsFlow:
        """Return the options flow."""
        return CorrenteOptionsFlow()


class CorrenteOptionsFlow(OptionsFlow):
    """Change the Italian contract after setup."""

    def __init__(self) -> None:
        self._contract_type: ItalyContractType | None = None

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Choose the shape of the contract."""
        if self.config_entry.data.get(CONF_COUNTRY) == COUNTRY_SWITZERLAND:
            # Swiss tariffs follow the operator's file; to change them, add the entry again.
            return self.async_abort(reason="switzerland_readd")
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
