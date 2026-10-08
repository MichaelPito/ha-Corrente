"""Render the brand images in custom_components/corrente/brand from the SVGs here.

Needs Playwright with Chromium and Pillow:
    python docs/brand/render.py [path to chromium]
Sizes follow https://github.com/home-assistant/brands#image-specification.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

HERE = Path(__file__).parent
OUT = HERE.parent.parent / "custom_components" / "corrente" / "brand"
SCALE = 4  # render larger, then trim and scale down


def render(browser, svg: str, height: int) -> Image.Image:
    _, _, vb_width, vb_height = (float(v) for v in re.search(r'viewBox="([^"]+)"', svg)[1].split())
    width, tall = round(height * SCALE * vb_width / vb_height), height * SCALE
    page = browser.new_page(viewport={"width": width, "height": tall})
    page.set_content(
        '<html><body style="margin:0;background:transparent">'
        + svg.replace("<svg ", f'<svg width="{width}" height="{tall}" ', 1)
        + "</body></html>"
    )
    path = OUT / "_render.png"
    page.screenshot(path=str(path), omit_background=True)
    page.close()
    image = Image.open(path)
    image.load()
    path.unlink()
    image = image.crop(image.getbbox())
    return image.resize((round(image.width * height / image.height), height), Image.LANCZOS)


def main() -> None:
    executable = sys.argv[1] if len(sys.argv) > 1 else None
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=executable)
        for name in ("icon", "logo", "dark_logo"):
            svg = (HERE / f"{name}.svg").read_text()
            for height, suffix in ((128, ""), (256, "@2x")):
                if name == "icon":
                    height *= 2  # icons are 256 and 512 pixels
                image = render(browser, svg, height)
                image.save(OUT / f"{name}{suffix}.png", optimize=True)
                print(f"{name}{suffix}.png", image.size)
        browser.close()


if __name__ == "__main__":
    main()
