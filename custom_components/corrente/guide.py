"""The guide inside Home Assistant: a sidebar panel, contextual to how Corrente is set up.

The content lives in guide.json (topics, steps, the full tour, what's new, in four
languages); a test fails a release that does not update it. See docs/ONBOARDING.md.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import voluptuous as vol
from homeassistant.components import persistent_notification, websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store

from .const import (
    CONF_APPLIANCE_SENSORS,
    CONF_CONTRACT_TYPE,
    CONF_COUNTRY,
    CONF_ENERGY_SENSOR,
    CONF_MONTHLY_FIXED,
    CONF_OTHER_PER_KWH,
    COUNTRY_ITALY,
    COUNTRY_SWITZERLAND,
    DOMAIN,
)
from .core.version import VERSION

GUIDE_PATH = "corrente-guide"  # the panel's address: /corrente-guide?topic=costs, ?tour=1
GUIDE_JS_URL = "/corrente/corrente-guide.js"
_GUIDE_JS = Path(__file__).parent / "frontend" / "corrente-guide.js"
_GUIDE_JSON = Path(__file__).parent / "guide.json"
_REGISTERED = f"{DOMAIN}_guide_registered"
_CONTENT = f"{DOMAIN}_guide_content"
_STORE_VERSION = 1
NOTIFICATION_ID = f"{DOMAIN}_guide"

DONE, TODO, NOT_NEEDED = "done", "todo", "na"


def load_content() -> dict[str, Any]:
    """The guide's content, as in guide.json."""
    return json.loads(_GUIDE_JSON.read_text(encoding="utf-8"))


async def _async_content(hass: HomeAssistant) -> dict[str, Any]:
    if _CONTENT not in hass.data:
        hass.data[_CONTENT] = await hass.async_add_executor_job(load_content)
    return hass.data[_CONTENT]


def topic_status(entries: list[dict[str, Any]]) -> dict[str, str]:
    """Whether each guided task is done, still to do or not needed, from the entries.

    ``entries`` are the config entries' data and options merged, plus ``dynamic``:
    whether a Swiss entry runs a dynamic tariff. Topics without a status are
    information that is always useful (the price sensors, the card...).
    """
    italy = [e for e in entries if e.get(CONF_COUNTRY) != COUNTRY_SWITZERLAND]
    swiss = [e for e in entries if e.get(CONF_COUNTRY) == COUNTRY_SWITZERLAND]
    indexed = [e for e in italy if e.get(CONF_CONTRACT_TYPE) == "indexed"]

    def setup(mine: list, others: list) -> str:
        if mine:
            return DONE
        return NOT_NEEDED if others else TODO

    status = {
        "setup_italy": setup(italy, swiss),
        "setup_switzerland": setup(swiss, italy),
        "setup_pun": DONE if indexed else NOT_NEEDED if swiss and not italy else "",
        "dynamic": (
            NOT_NEEDED
            if italy and not swiss
            else DONE
            if any(e.get("dynamic") for e in swiss)
            else ""
        ),
        "bill_costs": (
            NOT_NEEDED
            if not italy and swiss
            else DONE
            if any(e.get(CONF_OTHER_PER_KWH) or e.get(CONF_MONTHLY_FIXED) for e in italy)
            else TODO
            if italy
            else ""
        ),
        "meter": (
            DONE if any(e.get(CONF_ENERGY_SENSOR) for e in entries) else TODO if entries else ""
        ),
        "appliances": DONE if any(e.get(CONF_APPLIANCE_SENSORS) for e in entries) else "",
    }
    return {key: value for key, value in status.items() if value}


def _entries(hass: HomeAssistant) -> list[dict[str, Any]]:
    result = []
    for entry in hass.config_entries.async_entries(DOMAIN):
        merged = {**entry.data, **entry.options}
        runtime = getattr(entry, "runtime_data", None)
        coordinator = getattr(runtime, "switzerland", None)
        data = getattr(coordinator, "data", None)
        merged["dynamic"] = bool(data and data.contract.dynamic_tariffs)
        result.append(merged)
    return result


def _price_entities(node: Any) -> tuple[list[str], bool]:
    """The price entities in the energy settings, and whether a grid source is set up.

    Searched through the whole settings: their layout changed between Home Assistant
    versions (2025.10: "flow_from" lists; later: one entry per source).
    """
    prices: list[str] = []
    grid = False
    if isinstance(node, dict):
        if node.get("type") == "grid":
            grid = True
        for key, value in node.items():
            if key == "entity_energy_price" and isinstance(value, str):
                prices.append(value)
            else:
                found, has_grid = _price_entities(value)
                prices += found
                grid = grid or has_grid
    elif isinstance(node, list):
        for value in node:
            found, has_grid = _price_entities(value)
            prices += found
            grid = grid or has_grid
    return prices, grid


async def _async_energy_status(hass: HomeAssistant) -> str:
    """Done when the energy dashboard prices the grid with Corrente; to do when it has a
    grid source priced otherwise; nothing to say without an energy dashboard."""
    if "energy" not in hass.config.components:
        return ""
    from homeassistant.components.energy.data import async_get_manager
    from homeassistant.helpers import entity_registry as er

    manager = await async_get_manager(hass)
    prices, grid = _price_entities(manager.data or {})
    registry = er.async_get(hass)
    if any((e := registry.async_get(p)) and e.platform == DOMAIN for p in prices):
        return DONE
    return TODO if grid else ""


@websocket_api.websocket_command({vol.Required("type"): "corrente/guide"})
@websocket_api.async_response
async def _ws_guide(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """The guide's content and where this home stands with each topic."""
    entries = _entries(hass)
    countries = sorted(
        {
            COUNTRY_SWITZERLAND if e.get(CONF_COUNTRY) == COUNTRY_SWITZERLAND else COUNTRY_ITALY
            for e in entries
        }
    )
    connection.send_result(
        msg["id"],
        {
            "version": VERSION,
            "content": await _async_content(hass),
            "countries": countries,
            "status": {**topic_status(entries), "energy": await _async_energy_status(hass)},
        },
    )


def _language(hass: HomeAssistant, texts: dict[str, Any]) -> Any:
    language = (hass.config.language or "en").split("-")[0]
    return texts.get(language, texts["en"])


async def _async_notify(hass: HomeAssistant) -> None:
    """A notice with a link to the guide: after the install, and after each update."""
    store: Store[dict[str, Any]] = Store(hass, _STORE_VERSION, f"{DOMAIN}.guide")
    seen = await store.async_load()
    if seen and seen.get("version") == VERSION:
        return
    content = await _async_content(hass)
    ui = content["ui"]
    if seen is None:
        message = _language(hass, ui["welcome_notification"])
    else:
        news = next((n for n in content["whats_new"] if n["version"] == VERSION), None)
        items = _language(hass, news["items"]) if news else []
        message = _language(hass, ui["update_notification"]).replace(
            "{items}", "\n".join(f"- {item}" for item in items)
        )
    persistent_notification.async_create(
        hass,
        message.replace("{version}", VERSION),
        title=f"Corrente {VERSION}",
        notification_id=NOTIFICATION_ID,
    )
    await store.async_save({"version": VERSION})


async def async_setup_guide(hass: HomeAssistant) -> None:
    """Register the guide's panel and websocket command, once per Home Assistant run."""
    if hass.data.get(_REGISTERED) or hass.http is None:
        return
    hass.data[_REGISTERED] = True  # claimed before the first await (see the card)
    from homeassistant.components.http import StaticPathConfig

    await hass.http.async_register_static_paths(
        [StaticPathConfig(GUIDE_JS_URL, str(_GUIDE_JS), cache_headers=False)]
    )
    websocket_api.async_register_command(hass, _ws_guide)
    if "frontend" in hass.config.components:
        from homeassistant.components import panel_custom

        await panel_custom.async_register_panel(
            hass,
            frontend_url_path=GUIDE_PATH,
            webcomponent_name="corrente-guide-panel",
            sidebar_title="Corrente",
            sidebar_icon="mdi:lightning-bolt",
            module_url=f"{GUIDE_JS_URL}?v={VERSION}",
            require_admin=False,
        )
    await _async_notify(hass)


@callback
def async_dismiss_notification(hass: HomeAssistant) -> None:
    """Remove the guide's notice (when the last entry is removed)."""
    persistent_notification.async_dismiss(hass, NOTIFICATION_ID)
