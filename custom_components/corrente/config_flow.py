"""Config and options flow for Corrente."""

from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Any

import voluptuous as vol
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
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
    CONF_APPLIANCE_SENSORS,
    CONF_BEST_HOURS,
    CONF_CANTON,
    CONF_CONTRACT_TYPE,
    CONF_COUNTRY,
    CONF_ELECTRICITY_TARIFF,
    CONF_ENERGY_SENSOR,
    CONF_GRID_TARIFF,
    CONF_LOSSES,
    CONF_MUNICIPALITY,
    CONF_MUNICIPALITY_NAME,
    CONF_OPERATOR_ID,
    CONF_OPERATOR_NAME,
    CONF_PRICE_F1,
    CONF_PRICE_F2,
    CONF_PRICE_F3,
    CONF_REGIONAL_TARIFF,
    CONF_SPREAD,
    CONF_TARIFF_URL,
    CONF_ZONE,
    COUNTRY_ITALY,
    COUNTRY_SWITZERLAND,
    DOMAIN,
    DONATE_URL,
    ISSUES_URL,
)
from .core.contract import ItalyContractType
from .core.dynamic import DynamicTariffError, NotAnApiError, async_fetch_prices
from .core.elcom import (
    ElcomError,
    OperatorInMunicipality,
    TariffFileError,
    async_fetch_tariff_document,
    async_operators_for,
    async_search_municipalities,
    async_tariff_url_candidates,
)
from .core.gme import ZONES
from .core.switzerland import (
    SWISS_TZ,
    Tariff,
    UnsupportedTariffError,
    canton_of,
    parse_tariffs,
    regional_names,
    suggest_grid,
    suggest_regional_fees,
    tariffs_on,
)

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


def _pun_schema(defaults: dict[str, Any]) -> vol.Schema:
    """Spread, grid losses and zone of a PUN-indexed contract."""
    return vol.Schema(
        {
            vol.Required(
                CONF_SPREAD, default=defaults.get(CONF_SPREAD, vol.UNDEFINED)
            ): NumberSelector(
                NumberSelectorConfig(
                    min=-0.5,
                    max=1,
                    step="any",
                    mode=NumberSelectorMode.BOX,
                    unit_of_measurement="€/kWh",
                )
            ),
            vol.Required(CONF_LOSSES, default=defaults.get(CONF_LOSSES, 0.0)): NumberSelector(
                NumberSelectorConfig(
                    min=0, max=20, step=0.1, mode=NumberSelectorMode.BOX, unit_of_measurement="%"
                )
            ),
            vol.Required(CONF_ZONE, default=defaults.get(CONF_ZONE, "pun")): SelectSelector(
                SelectSelectorConfig(
                    options=[zone.lower() for zone in ZONES],
                    mode=SelectSelectorMode.DROPDOWN,
                    translation_key=CONF_ZONE,
                )
            ),
        }
    )


def _prices_schema(contract_type: ItalyContractType, defaults: dict[str, Any]) -> vol.Schema:
    """Return the price fields needed by a contract type."""
    if contract_type is ItalyContractType.INDEXED:
        return _pun_schema(defaults)
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
    return bool(tariff.energy) or tariff.is_dynamic


async def _dynamic_prices_error(
    hass: HomeAssistant, tariffs: list[Tariff], choice: dict[str, Any], today
) -> str | None:
    """Try the operator's API once for each dynamic tariff the user picked.

    Returns the error key to show, or None when every dynamic price could be read.
    """
    picked = [
        t
        for kind, key in (("electricity", CONF_ELECTRICITY_TARIFF), ("grid", CONF_GRID_TARIFF))
        for t in tariffs_on(tariffs, kind, today)
        if t.name == choice[key] and t.is_dynamic and t.dynamic_url
    ]
    start = datetime.combine(today, time(0, 0), SWISS_TZ)
    for tariff in picked:
        try:
            prices = await async_fetch_prices(
                async_get_clientsession(hass),
                tariff.dynamic_url,
                tariff.tariff_type,
                start,
                start + timedelta(days=1),
            )
        except NotAnApiError:
            return "dynamic_not_api"
        except DynamicTariffError:
            return "dynamic_unavailable"
        if not prices:
            return "dynamic_unavailable"
    return None


def _electricity_names(tariffs: list[Tariff], today) -> list[str]:
    """Energy tariffs in force today that Corrente can price."""
    return sorted({t.name for t in tariffs_on(tariffs, "electricity", today) if _supported(t)})


def _grid_schema(
    tariffs: list[Tariff], electricity: str, today, place: OperatorInMunicipality | None
) -> vol.Schema:
    """Grid tariff and regional fees, with the ones for this energy tariff and place suggested.

    With ElCom's household figures for the place, the suggestions are checked
    against them (see suggest_grid and suggest_regional_fees).
    """
    grids = [t for t in tariffs_on(tariffs, "grid", today) if _supported(t)]
    regionals = tariffs_on(tariffs, "regional_fees", today)
    energy = next(
        (t for t in tariffs_on(tariffs, "electricity", today) if t.name == electricity), None
    )
    municipality = place.municipality if place else None
    elcom = None
    if place and place.grid_h4_rp is not None and place.aidfee_rp is not None:
        elcom = (place.grid_h4_rp, place.aidfee_rp, today.year)
    suggested_grid, suggested_fees = None, []
    if energy is not None:
        suggested_grid = suggest_grid(
            energy, grids, municipality, place.municipality_name if place else None, elcom
        )
        suggested_fees = suggest_regional_fees(
            energy,
            regionals,
            municipality,
            place.charge_rp if place else None,
            today.year,
            suggested_grid,
        )
    return vol.Schema(
        {
            vol.Required(
                CONF_GRID_TARIFF,
                default=suggested_grid.name if suggested_grid else vol.UNDEFINED,
            ): SelectSelector(
                SelectSelectorConfig(
                    options=sorted({t.name for t in grids}), mode=SelectSelectorMode.DROPDOWN
                )
            ),
            # Several: some operators publish each fee on its own (Lausanne).
            vol.Optional(
                CONF_REGIONAL_TARIFF, default=[t.name for t in suggested_fees]
            ): SelectSelector(
                SelectSelectorConfig(
                    options=sorted({t.name for t in regionals}),
                    multiple=True,
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
        }
    )


def _tariff_choice(
    tariffs: list[Tariff],
    electricity: str,
    user_input: dict[str, Any],
    today,
    municipality: int | None,
) -> dict[str, Any]:
    """The tariff part of a Swiss entry, from the grid step's answers."""
    names = regional_names(user_input.get(CONF_REGIONAL_TARIFF))
    fees = [t for t in tariffs_on(tariffs, "regional_fees", today) if t.name in names]
    cantons = sorted({canton for fee in fees for canton in fee.canton_energy})
    canton = canton_of(municipality)
    return {
        CONF_ELECTRICITY_TARIFF: electricity,
        CONF_GRID_TARIFF: user_input[CONF_GRID_TARIFF],
        CONF_REGIONAL_TARIFF: [fee.name for fee in fees],
        CONF_CANTON: canton if canton in cantons else (cantons[0] if cantons else None),
    }


async def _elcom_place(
    hass: HomeAssistant, municipality: int, operator_id: str, year: int
) -> OperatorInMunicipality | None:
    """ElCom's figures for an operator in a municipality, None if ElCom does not answer."""
    try:
        operators = await async_operators_for(async_get_clientsession(hass), municipality, year)
    except ElcomError:
        return None
    return next((o for o in operators if o.operator_id == operator_id), None)


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

    async def async_step_prices_pun(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Enter spread, losses and zone of a PUN-indexed contract."""
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
        candidates = await async_tariff_url_candidates(
            async_get_clientsession(self.hass),
            operator.municipality,
            operator.operator_id,
            dt_util.now(SWISS_TZ).year,
            operator.tariff_url,
        )
        for url in candidates:
            if await self._async_load_tariffs(url):
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
        if user_input is not None:
            self._electricity = user_input[CONF_ELECTRICITY_TARIFF]
            return await self.async_step_ch_grid()
        today = dt_util.now(SWISS_TZ).date()
        return self.async_show_form(
            step_id="ch_tariff",
            data_schema=_select(
                _electricity_names(self._tariffs, today), key=CONF_ELECTRICITY_TARIFF
            ),
            description_placeholders={"operator": self._operator.operator_name},
        )

    async def async_step_ch_grid(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the grid tariff and the regional fees that go with the energy tariff."""
        assert self._operator is not None and self._electricity is not None
        today = dt_util.now(SWISS_TZ).date()
        errors: dict[str, str] = {}
        if user_input is not None:
            choice = _tariff_choice(
                self._tariffs, self._electricity, user_input, today, self._operator.municipality
            )
            if not (error := await _dynamic_prices_error(self.hass, self._tariffs, choice, today)):
                return self.async_create_entry(
                    # Short, so entity ids stay readable: "sensor.corrente_lugano_price_now".
                    title=f"Corrente {self._operator.municipality_name}",
                    data={
                        CONF_COUNTRY: COUNTRY_SWITZERLAND,
                        CONF_MUNICIPALITY: self._operator.municipality,
                        CONF_MUNICIPALITY_NAME: self._operator.municipality_name,
                        CONF_OPERATOR_ID: self._operator.operator_id,
                        CONF_OPERATOR_NAME: self._operator.operator_name,
                        CONF_TARIFF_URL: self._tariff_url,
                        **choice,
                    },
                )
            errors["base"] = error
        return self.async_show_form(
            step_id="ch_grid",
            data_schema=_grid_schema(self._tariffs, self._electricity, today, self._operator),
            description_placeholders={**_PLACEHOLDERS, "electricity": self._electricity},
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> CorrenteOptionsFlow:
        """Return the options flow."""
        return CorrenteOptionsFlow()


class CorrenteOptionsFlow(OptionsFlow):
    """Change the contract (Italy) or the tariffs (Switzerland) after setup."""

    def __init__(self) -> None:
        self._contract_type: ItalyContractType | None = None
        self._electricity: str | None = None

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Change the contract or tariff, or the energy meter used for costs."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["contract", "meter", "appliances", "appliance"],
            description_placeholders=_PLACEHOLDERS,
        )

    def _save(self, changes: dict[str, Any]) -> ConfigFlowResult:
        """Keep the options that this step does not change."""
        return self.async_create_entry(data={**self.config_entry.options, **changes})

    async def async_step_meter(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Choose the energy meter whose kWh are priced into today's and this month's cost."""
        if user_input is not None:
            return self._save({CONF_ENERGY_SENSOR: user_input.get(CONF_ENERGY_SENSOR)})
        schema = vol.Schema(
            {
                vol.Optional(CONF_ENERGY_SENSOR): EntitySelector(
                    EntitySelectorConfig(domain="sensor", device_class=SensorDeviceClass.ENERGY)
                )
            }
        )
        current = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(
            step_id="meter", data_schema=self.add_suggested_values_to_schema(schema, current)
        )

    async def async_step_appliances(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Appliances with their own meter (smart plugs): each gets its own cost sensors."""
        if user_input is not None:
            return self._save({CONF_APPLIANCE_SENSORS: user_input.get(CONF_APPLIANCE_SENSORS, [])})
        schema = vol.Schema(
            {
                vol.Optional(CONF_APPLIANCE_SENSORS): EntitySelector(
                    EntitySelectorConfig(
                        domain="sensor", device_class=SensorDeviceClass.ENERGY, multiple=True
                    )
                )
            }
        )
        current = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(
            step_id="appliances",
            data_schema=self.add_suggested_values_to_schema(schema, current),
        )

    async def async_step_appliance(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """How long the appliance runs, for the best time to start."""
        if user_input is not None:
            return self._save({CONF_BEST_HOURS: float(user_input[CONF_BEST_HOURS])})
        current = {**self.config_entry.data, **self.config_entry.options}
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_BEST_HOURS, default=float(current.get(CONF_BEST_HOURS, 2.0))
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=0.5,
                        max=8,
                        step=0.5,
                        mode=NumberSelectorMode.SLIDER,
                        unit_of_measurement="h",
                    )
                )
            }
        )
        return self.async_show_form(step_id="appliance", data_schema=schema)

    async def async_step_contract(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose the shape of the contract, or the Swiss energy tariff."""
        if self.config_entry.data.get(CONF_COUNTRY) == COUNTRY_SWITZERLAND:
            return await self.async_step_ch_tariff()
        current = {**self.config_entry.data, **self.config_entry.options}
        if user_input is not None:
            self._contract_type = ItalyContractType(user_input[CONF_CONTRACT_TYPE])
            return await self._async_step_prices()
        return self.async_show_form(
            step_id="contract",
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

    async def async_step_prices_pun(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change spread, losses and zone of a PUN-indexed contract."""
        return await self._async_step_prices(user_input)

    async def _async_step_prices(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        assert self._contract_type is not None
        if user_input is not None:
            return self._save({CONF_CONTRACT_TYPE: self._contract_type.value, **user_input})
        current = {**self.config_entry.data, **self.config_entry.options}
        defaults = {
            key: value
            for key, value in current.items()
            if key
            in (CONF_PRICE_F1, CONF_PRICE_F2, CONF_PRICE_F3, CONF_SPREAD, CONF_LOSSES, CONF_ZONE)
            and value is not None
        }
        return self.async_show_form(
            step_id=_step_id_for(self._contract_type),
            data_schema=_prices_schema(self._contract_type, defaults),
            description_placeholders=_PLACEHOLDERS,
        )

    # Switzerland ---------------------------------------------------------

    def _swiss_tariffs(self) -> list[Tariff]:
        coordinator = self.config_entry.runtime_data.switzerland
        return coordinator.data.tariffs if coordinator and coordinator.data else []

    async def async_step_ch_tariff(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose another energy tariff of the same operator."""
        tariffs = self._swiss_tariffs()
        if not tariffs:
            return self.async_abort(reason="tariffs_unavailable")
        if user_input is not None:
            self._electricity = user_input[CONF_ELECTRICITY_TARIFF]
            return await self.async_step_ch_grid()
        today = dt_util.now(SWISS_TZ).date()
        current = {**self.config_entry.data, **self.config_entry.options}
        names = _electricity_names(tariffs, today)
        default = current.get(CONF_ELECTRICITY_TARIFF)
        return self.async_show_form(
            step_id="ch_tariff",
            data_schema=_select(
                names, key=CONF_ELECTRICITY_TARIFF, default=default if default in names else None
            ),
            description_placeholders={"operator": self.config_entry.data[CONF_OPERATOR_NAME]},
        )

    async def async_step_ch_grid(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the grid tariff and regional fees."""
        assert self._electricity is not None
        tariffs = self._swiss_tariffs()
        today = dt_util.now(SWISS_TZ).date()
        municipality = self.config_entry.data[CONF_MUNICIPALITY]
        errors: dict[str, str] = {}
        if user_input is not None:
            choice = _tariff_choice(tariffs, self._electricity, user_input, today, municipality)
            if not (error := await _dynamic_prices_error(self.hass, tariffs, choice, today)):
                return self._save(choice)
            errors["base"] = error
        return self.async_show_form(
            step_id="ch_grid",
            data_schema=_grid_schema(
                tariffs,
                self._electricity,
                today,
                await _elcom_place(
                    self.hass, municipality, self.config_entry.data[CONF_OPERATOR_ID], today.year
                ),
            ),
            description_placeholders={**_PLACEHOLDERS, "electricity": self._electricity},
            errors=errors,
        )
