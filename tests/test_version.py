"""The version is written in a few places; they must agree."""

from __future__ import annotations

import json
from pathlib import Path

from custom_components.corrente.core.version import USER_AGENT, VERSION

ROOT = Path(__file__).parent.parent


def test_manifest_and_code_agree() -> None:
    manifest = json.loads((ROOT / "custom_components" / "corrente" / "manifest.json").read_text())
    assert manifest["version"] == VERSION
    assert f"Corrente/{VERSION}" in USER_AGENT


def test_changelog_has_the_version() -> None:
    assert f"## [{VERSION}]" in (ROOT / "CHANGELOG.md").read_text("utf-8")
