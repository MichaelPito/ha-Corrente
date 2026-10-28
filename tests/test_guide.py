"""The guide inside Home Assistant (docs/ONBOARDING.md).

The content checks are the rule that keeps the guide up to date: a release fails if
its news are missing, a text lacks a language, or a feature is not in any topic.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.components import persistent_notification
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.corrente.const import DOMAIN
from custom_components.corrente.core.version import VERSION
from custom_components.corrente.guide import (
    GUIDE_JS_URL,
    GUIDE_PATH,
    NOTIFICATION_ID,
    load_content,
    topic_status,
)

ROOT = Path(__file__).parent.parent
INTEGRATION = ROOT / "custom_components" / "corrente"
LANGUAGES = {"en", "it", "de", "fr"}
CONTENT = load_content()


def _texts(node: Any, path: str = "") -> list[tuple[str, dict]]:
    """Every translated text in the guide, with where it is."""
    if isinstance(node, dict):
        if {"en", "it", "de", "fr"} & set(node):
            return [(path, node)]
        return [t for key, value in node.items() for t in _texts(value, f"{path}.{key}")]
    if isinstance(node, list):
        return [t for i, value in enumerate(node) for t in _texts(value, f"{path}[{i}]")]
    return []


def test_news_of_this_version() -> None:
    """Every release says what is new, in the guide too."""
    assert CONTENT["version"] == VERSION
    assert CONTENT["whats_new"][0]["version"] == VERSION
    for language in LANGUAGES:
        assert CONTENT["whats_new"][0]["items"][language]


def test_every_text_in_four_languages() -> None:
    texts = _texts(CONTENT)
    assert len(texts) > 100
    for path, text in texts:
        assert set(text) == LANGUAGES, path
        values = [text[language] for language in sorted(LANGUAGES)]
        assert all(values), path
        if isinstance(values[0], list):
            assert len({len(v) for v in values}) == 1, path  # as many news items in each


def _features() -> set[str]:
    strings = json.loads((INTEGRATION / "strings.json").read_text("utf-8"))
    blueprints = (ROOT / "blueprints" / "automation" / "corrente").glob("*.yaml")
    return (
        {f"sensor:{key}" for key in strings["entity"]["sensor"]}
        | {f"config:{key}" for key in strings["config"]["step"]}
        | {f"options:{key}" for key in strings["options"]["step"]["init"]["menu_options"]}
        | {f"blueprint:{path.stem}" for path in blueprints}
        | {"card", "diagnostics"}
    )


def test_every_feature_has_a_topic() -> None:
    """A new sensor, setup step, option or blueprint needs its place in the guide."""
    covered = {key for topic in CONTENT["topics"] for key in topic["covers"]}
    assert _features() - covered == set()
    assert covered - _features() == set()  # no topic points to something gone


def test_tour_and_topics() -> None:
    ids = [topic["id"] for topic in CONTENT["topics"]]
    assert len(ids) == len(set(ids))
    assert CONTENT["tour"] == ids  # the full guide goes through every topic
    statuses = {"setup_italy", "setup_switzerland", "setup_pun", "dynamic", "bill_costs",
                "meter", "appliances"}  # fmt: skip
    for topic in CONTENT["topics"]:
        assert topic["steps"], topic["id"]
        assert topic["status"] in statuses | {None}, topic["id"]
        assert set(topic["countries"]) <= {"it", "ch"}
        assert topic["icon"].startswith("mdi:")
        for step in topic["steps"]:
            if "action" in step:
                assert step["action"]["path"].startswith(("/", "https://")), topic["id"]


def test_notices_carry_their_links() -> None:
    ui = CONTENT["ui"]
    for language in LANGUAGES:
        assert "/corrente-guide?tour=1" in ui["welcome_notification"][language]
        assert "{items}" in ui["update_notification"][language]
        assert "{n}" in ui["step_of"][language] and "{total}" in ui["step_of"][language]


ITALY = {"country": "it", "contract_type": "single", "price_f1": 0.25}
PUN = {"country": "it", "contract_type": "indexed", "spread": 0.02}
SWISS = {"country": "ch", "municipality": 5192}


@pytest.mark.parametrize(
    ("entries", "expected"),
    [
        ([], {"setup_italy": "todo", "setup_switzerland": "todo"}),
        (
            [ITALY],
            {"setup_italy": "done", "setup_switzerland": "na", "dynamic": "na",
             "bill_costs": "todo", "meter": "todo"},
        ),
        (
            [{**PUN, "other_per_kwh": 0.05, "energy_sensor": "sensor.grid"}],
            {"setup_italy": "done", "setup_pun": "done", "bill_costs": "done", "meter": "done"},
        ),
        (
            [{**SWISS, "dynamic": True, "appliance_sensors": ["sensor.plug"]}],
            {"setup_switzerland": "done", "setup_italy": "na", "setup_pun": "na",
             "bill_costs": "na", "dynamic": "done", "appliances": "done", "meter": "todo"},
        ),
    ],
)  # fmt: skip
def test_status_follows_the_setup(entries: list[dict], expected: dict[str, str]) -> None:
    status = topic_status(entries)
    for key, value in expected.items():
        assert status.get(key) == value, key


async def _setup(hass: HomeAssistant, **data: Any) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, data={**ITALY, **data})
    entry.add_to_hass(hass)
    assert await async_setup_component(hass, "http", {})
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    return entry


async def test_websocket_gives_content_and_status(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    await _setup(hass, energy_sensor="sensor.grid")
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": "corrente/guide"})
    answer = await client.receive_json()
    assert answer["success"]
    result = answer["result"]
    assert result["version"] == VERSION
    assert result["countries"] == ["it"]
    assert result["status"]["meter"] == "done"
    assert result["status"]["setup_switzerland"] == "na"
    assert result["content"]["tour"] == CONTENT["tour"]


async def test_panel_in_the_sidebar(hass: HomeAssistant) -> None:
    hass.config.components.add("frontend")
    with (
        patch(
            "homeassistant.components.panel_custom.async_register_panel", new=AsyncMock()
        ) as register,
        patch("homeassistant.components.frontend.add_extra_js_url"),  # the card's
    ):
        await _setup(hass)
    register.assert_awaited_once()
    kwargs = register.await_args.kwargs
    assert kwargs["frontend_url_path"] == GUIDE_PATH
    assert kwargs["webcomponent_name"] == "corrente-guide-panel"
    assert kwargs["sidebar_title"] == "Corrente"
    assert kwargs["module_url"] == f"{GUIDE_JS_URL}?v={VERSION}"
    assert not kwargs["require_admin"]


def _notification(hass: HomeAssistant) -> dict | None:
    return persistent_notification._async_get_or_create_notifications(hass).get(NOTIFICATION_ID)


async def test_welcome_notice_after_the_install(hass: HomeAssistant) -> None:
    hass.config.language = "it"
    await _setup(hass)
    notice = _notification(hass)
    assert notice is not None
    assert "/corrente-guide?tour=1" in notice["message"]
    assert "guida completa" in notice["message"]


async def test_news_notice_after_an_update(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    hass_storage["corrente.guide"] = {"version": 1, "key": "corrente.guide",
                                      "data": {"version": "0.3.4"}}  # fmt: skip
    await _setup(hass)
    notice = _notification(hass)
    assert notice is not None
    assert "/corrente-guide?topic=whats_new" in notice["message"]
    assert VERSION in notice["title"]
    news = CONTENT["whats_new"][0]["items"]["en"][0]
    assert news in notice["message"]


async def test_no_notice_when_nothing_changed(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    hass_storage["corrente.guide"] = {"version": 1, "key": "corrente.guide",
                                      "data": {"version": VERSION}}  # fmt: skip
    await _setup(hass)
    assert _notification(hass) is None


async def test_notice_goes_with_the_last_entry(hass: HomeAssistant) -> None:
    entry = await _setup(hass)
    assert _notification(hass) is not None
    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert _notification(hass) is None


async def test_guide_script_is_served(hass: HomeAssistant, hass_client) -> None:
    await _setup(hass)
    client = await hass_client()
    response = await client.get(GUIDE_JS_URL)
    assert response.status == 200
    assert "corrente-guide-panel" in await response.text()
