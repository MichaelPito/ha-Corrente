"""Constants for Corrente."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "corrente"

CONF_COUNTRY: Final = "country"
COUNTRY_ITALY: Final = "it"
COUNTRY_SWITZERLAND: Final = "ch"

# Italy
CONF_CONTRACT_TYPE: Final = "contract_type"
CONF_PRICE_F1: Final = "price_f1"
CONF_PRICE_F2: Final = "price_f2"
CONF_PRICE_F3: Final = "price_f3"

# Switzerland
CONF_MUNICIPALITY: Final = "municipality"
CONF_MUNICIPALITY_NAME: Final = "municipality_name"
CONF_OPERATOR_ID: Final = "operator_id"
CONF_OPERATOR_NAME: Final = "operator_name"
CONF_TARIFF_URL: Final = "tariff_url"
CONF_ELECTRICITY_TARIFF: Final = "electricity_tariff"
CONF_GRID_TARIFF: Final = "grid_tariff"
CONF_REGIONAL_TARIFF: Final = "regional_tariff"
CONF_CANTON: Final = "canton"

ISSUES_URL: Final = "https://github.com/MichaelPito/ha-corrente/issues/new/choose"
DONATE_URL: Final = "https://buymeacoffee.com/michaelpito"

ATTRIBUTION_ELCOM: Final = "Tariffs: grid operator files via ElCom open data"
