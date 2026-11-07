#!/usr/bin/env python3
"""Generate the application icons (PNG + Windows .ico) from vector maths.

Run once from the repository root:

    python tools/make_icons.py

Only Pillow is needed, and only at build time — the running app renders its
icons with Qt from the SVG set in `src/fcc/icons.py`.
"""

from __future__ import annotations

import argparse
import math
import os
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError:  # pragma: no cover
    print("Pillow is required:  pip install pillow", file=sys.stderr)
    raise SystemExit(2)

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"

CORAL = (217, 119, 87, 255)
CORAL_DARK = (224, 138, 109, 255)
CREAM = (250, 249, 245, 255)
INK = (31, 30, 27, 255)
TRANSPARENT = (0, 0, 0, 0)


def rounded_square(size: int, radius_ratio: float, color) -> Image.Image:
    scale = 4
    big = size * scale
    image = Image.new("RGBA", (big, big), TRANSPARENT)
    draw = ImageDraw.Draw(image)
    radius = int(big * radius_ratio)
    draw.rounded_rectangle((0, 0, big - 1, big - 1), radius=radius, fill=color)
    return image.resize((size, size), Image.LANCZOS)


def spark(size: int, color=CORAL, rays: int = 12, outer: float = 0.40,
          inner: float = 0.095, width: float = 0.105) -> Image.Image:
    """Draw the sunburst mark used by Claude, supersampled then downscaled."""
    scale = 4
    big = size * scale
    image = Image.new("RGBA", (big, big), TRANSPARENT)
    draw = ImageDraw.Draw(image)
    centre = big / 2.0
    outer_px = big * outer
    inner_px = big * inner
    half_width = big * width / 2.0

    for index in range(rays):
        angle = math.radians(index * (360.0 / rays) - 90.0)
        cos_a, sin_a = math.cos(angle), math.sin(angle)
        perp_cos, perp_sin = math.cos(angle + math.pi / 2), math.sin(angle + math.pi / 2)
        tip_x = centre + outer_px * cos_a
        tip_y = centre + outer_px * sin_a
        base_x = centre + inner_px * cos_a
        base_y = centre + inner_px * sin_a
        narrow = half_width * 0.52
        polygon = [
            (base_x + perp_cos * narrow, base_y + perp_sin * narrow),
            (tip_x + perp_cos * half_width, tip_y + perp_sin * half_width),
            (tip_x - perp_cos * half_width, tip_y - perp_sin * half_width),
            (base_x - perp_cos * narrow, base_y - perp_sin * narrow),
        ]
        draw.polygon(polygon, fill=color)
        cap = half_width
        draw.ellipse((tip_x - cap, tip_y - cap, tip_x + cap, tip_y + cap), fill=color)
        small = narrow
        draw.ellipse((base_x - small, base_y - small, base_x + small, base_y + small), fill=color)

    hub = big * 0.075
    draw.ellipse((centre - hub, centre - hub, centre + hub, centre + hub), fill=color)
    return image.resize((size, size), Image.LANCZOS)


def compose(size: int, background=CREAM, mark_color=CORAL, radius_ratio: float = 0.26,
            transparent_background: bool = False) -> Image.Image:
    if transparent_background:
        base = Image.new("RGBA", (size, size), TRANSPARENT)
    else:
        base = rounded_square(size, radius_ratio, background)
    mark = spark(size, mark_color)
    base.alpha_composite(mark)
    return base


def write(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)
    print(f"  wrote {path.relative_to(ROOT)}  ({path.stat().st_size // 1024} KB)")


def build(output: Path) -> None:
    print("Generating icons…")
    output.mkdir(parents=True, exist_ok=True)

    write(compose(1024), output / "logo.png")
    write(compose(1024, background=INK, mark_color=CORAL_DARK), output / "logo-dark.png")
    write(compose(512), output / "icon-512.png")
    write(compose(256), output / "icon-256.png")
    write(compose(128), output / "icon-128.png")
    write(compose(64), output / "icon-64.png")
    write(compose(32), output / "icon-32.png")
    write(spark(256, CORAL, ), output / "spark-256.png")
    write(spark(256, CREAM), output / "spark-cream-256.png")
    write(compose(1024, background=CORAL, mark_color=CREAM), output / "installer.png")

    ico_sizes = [(16, 16), (20, 20), (24, 24), (32, 32), (40, 40), (48, 48),
                 (64, 64), (128, 128), (256, 256)]
    frames = [compose(size[0]) for size in ico_sizes]
    frames[-1].save(output / "icon.ico", format="ICO", sizes=ico_sizes,
                    append_images=frames[:-1])
    print(f"  wrote {(output / 'icon.ico').relative_to(ROOT)}")

    installer_frames = [compose(size[0], background=CORAL, mark_color=CREAM) for size in ico_sizes]
    installer_frames[-1].save(output / "installer.ico", format="ICO", sizes=ico_sizes,
                              append_images=installer_frames[:-1])
    print(f"  wrote {(output / 'installer.ico').relative_to(ROOT)}")

    tray_sizes = [(16, 16), (24, 24), (32, 32), (48, 48)]
    tray = [compose(size[0]) for size in tray_sizes]
    tray[-1].save(output / "tray.ico", format="ICO", sizes=tray_sizes,
                  append_images=tray[:-1])
    print(f"  wrote {(output / 'tray.ico').relative_to(ROOT)}")

    if os.environ.get("FCC_MACOS_ICONSET") == "1":
        mac = output / "ClaudeCodeStudio.iconset"
        mac.mkdir(parents=True, exist_ok=True)
        for size in (16, 32, 64, 128, 256, 512):
            write(compose(size), mac / f"icon_{size}x{size}.png")
            write(compose(size * 2), mac / f"icon_{size}x{size}@2x.png")
        print("  wrote macOS iconset (run `iconutil -c icns` afterwards)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(ASSETS), help="where to write the icons")
    args = parser.parse_args()
    build(Path(args.output).expanduser().resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
