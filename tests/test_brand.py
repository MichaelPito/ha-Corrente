"""The integration's own brand images (Home Assistant 2026.3+ reads them from brand/)."""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

BRAND = Path(__file__).parent.parent / "custom_components" / "corrente" / "brand"


def png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()[:24]
    assert data[:8] == b"\x89PNG\r\n\x1a\n", f"{path.name} is not a PNG"
    return struct.unpack(">II", data[16:24])


@pytest.mark.parametrize(("name", "size"), [("icon.png", 256), ("icon@2x.png", 512)])
def test_icons_are_square_and_sized(name: str, size: int) -> None:
    assert png_size(BRAND / name) == (size, size)


@pytest.mark.parametrize(
    ("name", "low", "high"),
    [
        ("logo.png", 128, 256),
        ("logo@2x.png", 256, 512),
        ("dark_logo.png", 128, 256),
        ("dark_logo@2x.png", 256, 512),
    ],
)
def test_logos_follow_the_brands_rules(name: str, low: int, high: int) -> None:
    width, height = png_size(BRAND / name)
    assert width > height  # landscape
    assert low <= min(width, height) <= high
