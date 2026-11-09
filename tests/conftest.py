"""Shared fixtures."""

from __future__ import annotations

import importlib
import sys

import pytest

try:
    import pytest_homeassistant  # noqa: F401  # Home Assistant 2026.11 and later
except ImportError:
    # The oldest supported Home Assistant (2025.10) only has the community package
    # it replaced: let the tests import it under the new name. Remove this with 2025.10.
    for _name in (
        "",
        ".common",
        ".typing",
        ".test_util",
        ".test_util.aiohttp",
        ".components",
        ".components.diagnostics",
    ):
        sys.modules[f"pytest_homeassistant{_name}"] = importlib.import_module(
            f"pytest_homeassistant_custom_component{_name}"
        )


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Let Home Assistant load the integration from custom_components."""
