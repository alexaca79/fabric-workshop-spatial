"""Vector-style icon renderer for the workshop decks.

Icons are drawn with Pillow at 4x the target size and downsampled, which gives
clean anti-aliased edges without shipping a font dependency or a folder of
third-party SVGs. Everything here is drawn from primitives, so the deck has no
licensing question attached to it and the palette can change in one place.

Usage::

    from icons import icon_path
    slide.shapes.add_picture(icon_path("satellite", BLUE), Inches(1), Inches(2),
                             height=Inches(0.5))

Rendered files are cached under ``decks/assets/icons`` and are regenerated only
when missing, so a deck rebuild is fast after the first run.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Callable

from PIL import Image, ImageDraw

ASSET_DIR = Path(__file__).resolve().parent / "assets" / "icons"
SUPERSAMPLE = 4
TARGET_PX = 256
CANVAS = TARGET_PX * SUPERSAMPLE
STROKE = int(CANVAS * 0.055)

_REGISTRY: dict[str, Callable[[ImageDraw.ImageDraw, int, int, tuple[int, int, int, int]], None]] = {}


def icon(name: str):
    """Register an icon drawing function under a name."""

    def wrapper(fn):
        _REGISTRY[name] = fn
        return fn

    return wrapper


# ---------------------------------------------------------------------------
# Drawing helpers. All coordinates are fractions of the canvas, 0 to 1.
# ---------------------------------------------------------------------------


def _p(canvas: int, x: float, y: float) -> tuple[float, float]:
    return x * canvas, y * canvas


def _line(d, c, w, colour, *points, close: bool = False):
    pts = [_p(c, x, y) for x, y in points]
    if close:
        pts.append(pts[0])
    d.line(pts, fill=colour, width=w, joint="curve")
    # Pillow does not round line caps, so a small dot at each vertex keeps
    # corners from looking chipped at small sizes.
    r = w / 2
    for x, y in pts:
        d.ellipse([x - r, y - r, x + r, y + r], fill=colour)


def _rect(d, c, w, colour, x0, y0, x1, y1, radius: float = 0.0, fill=None):
    box = [*_p(c, x0, y0), *_p(c, x1, y1)]
    if radius:
        d.rounded_rectangle(box, radius=radius * c, outline=colour, width=w, fill=fill)
    else:
        d.rectangle(box, outline=colour, width=w, fill=fill)


def _circle(d, c, w, colour, cx, cy, r, fill=None):
    box = [(cx - r) * c, (cy - r) * c, (cx + r) * c, (cy + r) * c]
    d.ellipse(box, outline=colour, width=w, fill=fill)


def _arc(d, c, w, colour, cx, cy, r, start, end):
    box = [(cx - r) * c, (cy - r) * c, (cx + r) * c, (cy + r) * c]
    d.arc(box, start=start, end=end, fill=colour, width=w)


def _dot(d, c, colour, cx, cy, r):
    box = [(cx - r) * c, (cy - r) * c, (cx + r) * c, (cy + r) * c]
    d.ellipse(box, fill=colour)


def _ellipse_ring(d, c, w, colour, cx, cy, rx, ry):
    d.ellipse([(cx - rx) * c, (cy - ry) * c, (cx + rx) * c, (cy + ry) * c], outline=colour, width=w)


# ---------------------------------------------------------------------------
# Platform and tooling
# ---------------------------------------------------------------------------


@icon("satellite")
def _satellite(d, c, w, col):
    _rect(d, c, w, col, 0.42, 0.42, 0.58, 0.58, radius=0.02)
    _line(d, c, w, col, (0.42, 0.46), (0.20, 0.30), (0.30, 0.16), (0.52, 0.32))
    _line(d, c, w, col, (0.58, 0.54), (0.80, 0.70), (0.70, 0.84), (0.48, 0.68))
    _line(d, c, w, col, (0.58, 0.44), (0.72, 0.32))
    _arc(d, c, w, col, 0.74, 0.28, 0.14, 200, 330)
    _arc(d, c, w, col, 0.74, 0.28, 0.22, 210, 320)


@icon("lakehouse")
def _lakehouse(d, c, w, col):
    _ellipse_ring(d, c, w, col, 0.5, 0.26, 0.30, 0.11)
    _line(d, c, w, col, (0.20, 0.26), (0.20, 0.72))
    _line(d, c, w, col, (0.80, 0.26), (0.80, 0.72))
    _arc(d, c, w, col, 0.5, 0.61, 0.30, 0, 180)
    _arc(d, c, w, col, 0.5, 0.44, 0.30, 20, 160)


@icon("layers")
def _layers(d, c, w, col):
    _line(d, c, w, col, (0.50, 0.16), (0.84, 0.34), (0.50, 0.52), (0.16, 0.34), close=True)
    _line(d, c, w, col, (0.16, 0.50), (0.50, 0.68), (0.84, 0.50))
    _line(d, c, w, col, (0.16, 0.66), (0.50, 0.84), (0.84, 0.66))


@icon("notebook")
def _notebook(d, c, w, col):
    _rect(d, c, w, col, 0.26, 0.14, 0.80, 0.86, radius=0.04)
    _line(d, c, w, col, (0.38, 0.14), (0.38, 0.86))
    _line(d, c, w, col, (0.20, 0.28), (0.32, 0.28))
    _line(d, c, w, col, (0.20, 0.50), (0.32, 0.50))
    _line(d, c, w, col, (0.20, 0.72), (0.32, 0.72))
    _line(d, c, w, col, (0.50, 0.36), (0.70, 0.36))
    _line(d, c, w, col, (0.50, 0.52), (0.70, 0.52))


@icon("code")
def _code(d, c, w, col):
    _line(d, c, w, col, (0.36, 0.30), (0.16, 0.50), (0.36, 0.70))
    _line(d, c, w, col, (0.64, 0.30), (0.84, 0.50), (0.64, 0.70))
    _line(d, c, w, col, (0.56, 0.20), (0.44, 0.80))


@icon("copilot")
def _copilot(d, c, w, col):
    def spark(cx, cy, r):
        _line(d, c, w, col, (cx, cy - r), (cx + r * 0.3, cy - r * 0.3), (cx + r, cy),
              (cx + r * 0.3, cy + r * 0.3), (cx, cy + r), (cx - r * 0.3, cy + r * 0.3),
              (cx - r, cy), (cx - r * 0.3, cy - r * 0.3), close=True)

    spark(0.42, 0.44, 0.28)
    spark(0.74, 0.72, 0.15)


@icon("brain")
def _brain(d, c, w, col):
    # Drawn as a processor rather than an anatomical brain: at 40 pixels on a
    # slide, lobes turn to mush and a chip still reads as "model".
    _rect(d, c, w, col, 0.28, 0.28, 0.72, 0.72, radius=0.04)
    _rect(d, c, w, col, 0.42, 0.42, 0.58, 0.58, radius=0.02)
    for offset in (0.38, 0.50, 0.62):
        _line(d, c, w, col, (offset, 0.14), (offset, 0.28))
        _line(d, c, w, col, (offset, 0.72), (offset, 0.86))
        _line(d, c, w, col, (0.14, offset), (0.28, offset))
        _line(d, c, w, col, (0.72, offset), (0.86, offset))


@icon("chart")
def _chart(d, c, w, col):
    _line(d, c, w, col, (0.18, 0.16), (0.18, 0.82), (0.84, 0.82))
    _rect(d, c, w, col, 0.28, 0.56, 0.40, 0.82)
    _rect(d, c, w, col, 0.46, 0.38, 0.58, 0.82)
    _rect(d, c, w, col, 0.64, 0.24, 0.76, 0.82)


@icon("map")
def _map(d, c, w, col):
    _line(d, c, w, col, (0.14, 0.26), (0.38, 0.16), (0.62, 0.30), (0.86, 0.20),
          (0.86, 0.74), (0.62, 0.84), (0.38, 0.70), (0.14, 0.80), close=True)
    _line(d, c, w, col, (0.38, 0.16), (0.38, 0.70))
    _line(d, c, w, col, (0.62, 0.30), (0.62, 0.84))


@icon("globe")
def _globe(d, c, w, col):
    _circle(d, c, w, col, 0.5, 0.5, 0.34)
    _line(d, c, w, col, (0.16, 0.50), (0.84, 0.50))
    _ellipse_ring(d, c, w, col, 0.5, 0.5, 0.16, 0.34)
    _arc(d, c, w, col, 0.5, 0.30, 0.34, 30, 150)
    _arc(d, c, w, col, 0.5, 0.70, 0.34, 210, 330)


@icon("pipeline")
def _pipeline(d, c, w, col):
    _rect(d, c, w, col, 0.06, 0.34, 0.30, 0.66, radius=0.04)
    _rect(d, c, w, col, 0.38, 0.34, 0.62, 0.66, radius=0.04)
    _rect(d, c, w, col, 0.70, 0.34, 0.94, 0.66, radius=0.04)
    _line(d, c, w, col, (0.30, 0.50), (0.38, 0.50))
    _line(d, c, w, col, (0.62, 0.50), (0.70, 0.50))
    _dot(d, c, col, 0.18, 0.50, 0.045)
    _dot(d, c, col, 0.50, 0.50, 0.045)
    _dot(d, c, col, 0.82, 0.50, 0.045)


@icon("table")
def _table(d, c, w, col):
    _rect(d, c, w, col, 0.14, 0.20, 0.86, 0.80, radius=0.03)
    _line(d, c, w, col, (0.14, 0.38), (0.86, 0.38))
    _line(d, c, w, col, (0.14, 0.59), (0.86, 0.59))
    _line(d, c, w, col, (0.38, 0.20), (0.38, 0.80))
    _line(d, c, w, col, (0.62, 0.20), (0.62, 0.80))


@icon("shortcut")
def _shortcut(d, c, w, col):
    # An external-link glyph rather than a chain: a shortcut points at data that
    # lives somewhere else, which is exactly what this shape says.
    _line(d, c, w, col, (0.56, 0.20), (0.18, 0.20), (0.18, 0.82), (0.80, 0.82), (0.80, 0.44))
    _line(d, c, w, col, (0.48, 0.52), (0.86, 0.14))
    _line(d, c, w, col, (0.60, 0.14), (0.86, 0.14), (0.86, 0.40))


@icon("delta")
def _delta(d, c, w, col):
    _line(d, c, w, col, (0.50, 0.16), (0.86, 0.80), (0.14, 0.80), close=True)
    _line(d, c, w, col, (0.30, 0.62), (0.70, 0.62))


# ---------------------------------------------------------------------------
# Process, quality and governance
# ---------------------------------------------------------------------------


@icon("shield")
def _shield(d, c, w, col):
    _line(d, c, w, col, (0.50, 0.12), (0.82, 0.26), (0.82, 0.52))
    _line(d, c, w, col, (0.82, 0.52), (0.50, 0.88), (0.18, 0.52))
    _line(d, c, w, col, (0.18, 0.52), (0.18, 0.26), (0.50, 0.12))
    _line(d, c, w, col, (0.36, 0.48), (0.46, 0.60), (0.66, 0.38))


@icon("check")
def _check(d, c, w, col):
    _circle(d, c, w, col, 0.5, 0.5, 0.34)
    _line(d, c, w, col, (0.32, 0.51), (0.45, 0.65), (0.70, 0.36))


@icon("warning")
def _warning(d, c, w, col):
    _line(d, c, w, col, (0.50, 0.14), (0.88, 0.80), (0.12, 0.80), close=True)
    _line(d, c, w, col, (0.50, 0.40), (0.50, 0.58))
    _dot(d, c, col, 0.50, 0.69, 0.035)


@icon("checklist")
def _checklist(d, c, w, col):
    _rect(d, c, w, col, 0.20, 0.14, 0.80, 0.86, radius=0.04)
    _line(d, c, w, col, (0.31, 0.33), (0.36, 0.39), (0.46, 0.28))
    _line(d, c, w, col, (0.31, 0.53), (0.36, 0.59), (0.46, 0.48))
    _line(d, c, w, col, (0.54, 0.33), (0.70, 0.33))
    _line(d, c, w, col, (0.54, 0.53), (0.70, 0.53))
    _line(d, c, w, col, (0.31, 0.72), (0.70, 0.72))


@icon("filter")
def _filter(d, c, w, col):
    _line(d, c, w, col, (0.16, 0.20), (0.84, 0.20), (0.58, 0.50), (0.58, 0.82),
          (0.42, 0.72), (0.42, 0.50), close=True)


@icon("gate")
def _gate(d, c, w, col):
    # A checkpoint barrier: post, boom arm, and the stripe pattern that says stop.
    _line(d, c, w, col, (0.22, 0.24), (0.22, 0.86))
    _line(d, c, w, col, (0.12, 0.86), (0.32, 0.86))
    _line(d, c, w, col, (0.22, 0.34), (0.88, 0.34))
    _line(d, c, w, col, (0.40, 0.34), (0.40, 0.48))
    _line(d, c, w, col, (0.60, 0.34), (0.60, 0.48))
    _line(d, c, w, col, (0.80, 0.34), (0.80, 0.48))


@icon("clock")
def _clock(d, c, w, col):
    _circle(d, c, w, col, 0.5, 0.5, 0.34)
    _line(d, c, w, col, (0.50, 0.30), (0.50, 0.52), (0.66, 0.60))


@icon("refresh")
def _refresh(d, c, w, col):
    _arc(d, c, w, col, 0.5, 0.5, 0.32, 40, 320)
    _line(d, c, w, col, (0.66, 0.20), (0.76, 0.30), (0.64, 0.38))


@icon("search")
def _search(d, c, w, col):
    _circle(d, c, w, col, 0.44, 0.42, 0.26)
    _line(d, c, w, col, (0.63, 0.62), (0.84, 0.84))


@icon("target")
def _target(d, c, w, col):
    _circle(d, c, w, col, 0.5, 0.5, 0.34)
    _circle(d, c, w, col, 0.5, 0.5, 0.19)
    _dot(d, c, col, 0.5, 0.5, 0.055)


@icon("flag")
def _flag(d, c, w, col):
    _line(d, c, w, col, (0.26, 0.14), (0.26, 0.88))
    _line(d, c, w, col, (0.26, 0.20), (0.78, 0.20), (0.64, 0.38), (0.78, 0.56), (0.26, 0.56))


@icon("key")
def _key(d, c, w, col):
    _circle(d, c, w, col, 0.34, 0.38, 0.20)
    _line(d, c, w, col, (0.46, 0.52), (0.82, 0.86))
    _line(d, c, w, col, (0.62, 0.68), (0.72, 0.58))
    _line(d, c, w, col, (0.72, 0.78), (0.82, 0.68))


@icon("gear")
def _gear(d, c, w, col):
    _circle(d, c, w, col, 0.5, 0.5, 0.16)
    for k in range(8):
        angle = math.radians(k * 45)
        x0, y0 = 0.5 + 0.26 * math.cos(angle), 0.5 + 0.26 * math.sin(angle)
        x1, y1 = 0.5 + 0.38 * math.cos(angle), 0.5 + 0.38 * math.sin(angle)
        _line(d, c, w, col, (x0, y0), (x1, y1))
    _circle(d, c, w, col, 0.5, 0.5, 0.30)


# ---------------------------------------------------------------------------
# Domain
# ---------------------------------------------------------------------------


@icon("tree")
def _tree(d, c, w, col):
    _line(d, c, w, col, (0.50, 0.12), (0.70, 0.40), (0.30, 0.40), close=True)
    _line(d, c, w, col, (0.50, 0.30), (0.76, 0.62), (0.24, 0.62), close=True)
    _line(d, c, w, col, (0.50, 0.62), (0.50, 0.88))
    _line(d, c, w, col, (0.34, 0.88), (0.66, 0.88))


@icon("forest")
def _forest(d, c, w, col):
    _line(d, c, w, col, (0.30, 0.20), (0.46, 0.54), (0.14, 0.54), close=True)
    _line(d, c, w, col, (0.30, 0.54), (0.30, 0.76))
    _line(d, c, w, col, (0.66, 0.30), (0.86, 0.66), (0.46, 0.66), close=True)
    _line(d, c, w, col, (0.66, 0.66), (0.66, 0.84))
    _line(d, c, w, col, (0.10, 0.84), (0.90, 0.84))


@icon("cloud")
def _cloud(d, c, w, col):
    _arc(d, c, w, col, 0.38, 0.48, 0.20, 150, 360)
    _arc(d, c, w, col, 0.62, 0.54, 0.16, 250, 60)
    _line(d, c, w, col, (0.21, 0.62), (0.76, 0.62))
    _arc(d, c, w, col, 0.21, 0.56, 0.07, 90, 270)
    _arc(d, c, w, col, 0.76, 0.56, 0.07, 270, 90)


@icon("calendar")
def _calendar(d, c, w, col):
    _rect(d, c, w, col, 0.16, 0.22, 0.84, 0.84, radius=0.04)
    _line(d, c, w, col, (0.16, 0.40), (0.84, 0.40))
    _line(d, c, w, col, (0.32, 0.14), (0.32, 0.28))
    _line(d, c, w, col, (0.68, 0.14), (0.68, 0.28))
    for col_x in (0.31, 0.50, 0.69):
        for row_y in (0.55, 0.71):
            _dot(d, c, col, col_x, row_y, 0.035)


@icon("people")
def _people(d, c, w, col):
    _circle(d, c, w, col, 0.38, 0.34, 0.15)
    _arc(d, c, w, col, 0.38, 0.78, 0.26, 180, 360)
    _arc(d, c, w, col, 0.68, 0.34, 0.14, 250, 110)
    _arc(d, c, w, col, 0.70, 0.78, 0.22, 250, 350)


@icon("compass")
def _compass(d, c, w, col):
    _circle(d, c, w, col, 0.5, 0.5, 0.34)
    _line(d, c, w, col, (0.36, 0.64), (0.58, 0.58), (0.64, 0.36), (0.42, 0.42), close=True)
    _dot(d, c, col, 0.5, 0.5, 0.04)


@icon("download")
def _download(d, c, w, col):
    _line(d, c, w, col, (0.50, 0.14), (0.50, 0.62))
    _line(d, c, w, col, (0.32, 0.44), (0.50, 0.62), (0.68, 0.44))
    _line(d, c, w, col, (0.18, 0.74), (0.18, 0.86), (0.82, 0.86), (0.82, 0.74))


@icon("book")
def _book(d, c, w, col):
    _line(d, c, w, col, (0.50, 0.26), (0.50, 0.84))
    _arc(d, c, w, col, 0.30, 0.34, 0.22, 100, 260)
    _line(d, c, w, col, (0.14, 0.26), (0.14, 0.76))
    _line(d, c, w, col, (0.14, 0.76), (0.50, 0.84))
    _arc(d, c, w, col, 0.70, 0.34, 0.22, 280, 80)
    _line(d, c, w, col, (0.86, 0.26), (0.86, 0.76))
    _line(d, c, w, col, (0.86, 0.76), (0.50, 0.84))


@icon("rocket")
def _rocket(d, c, w, col):
    _line(d, c, w, col, (0.50, 0.12), (0.66, 0.40), (0.66, 0.68), (0.34, 0.68), (0.34, 0.40), close=True)
    _circle(d, c, w, col, 0.50, 0.38, 0.09)
    _line(d, c, w, col, (0.34, 0.50), (0.20, 0.66), (0.34, 0.68))
    _line(d, c, w, col, (0.66, 0.50), (0.80, 0.66), (0.66, 0.68))
    _line(d, c, w, col, (0.42, 0.74), (0.50, 0.90), (0.58, 0.74))


@icon("lightbulb")
def _lightbulb(d, c, w, col):
    _arc(d, c, w, col, 0.50, 0.42, 0.26, 160, 20)
    _line(d, c, w, col, (0.26, 0.46), (0.38, 0.68))
    _line(d, c, w, col, (0.74, 0.46), (0.62, 0.68))
    _line(d, c, w, col, (0.38, 0.68), (0.62, 0.68))
    _line(d, c, w, col, (0.40, 0.78), (0.60, 0.78))
    _line(d, c, w, col, (0.44, 0.87), (0.56, 0.87))


@icon("handoff")
def _handoff(d, c, w, col):
    _line(d, c, w, col, (0.12, 0.36), (0.62, 0.36))
    _line(d, c, w, col, (0.50, 0.24), (0.62, 0.36), (0.50, 0.48))
    _line(d, c, w, col, (0.88, 0.66), (0.38, 0.66))
    _line(d, c, w, col, (0.50, 0.54), (0.38, 0.66), (0.50, 0.78))


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def available() -> list[str]:
    return sorted(_REGISTRY)


def render(name: str, colour: tuple[int, int, int], out_path: Path | None = None) -> Path:
    """Draw an icon and return the path to the cached PNG."""
    if name not in _REGISTRY:
        raise KeyError(f"unknown icon '{name}'. Available: {', '.join(available())}")

    hex_colour = "%02x%02x%02x" % colour
    path = out_path or ASSET_DIR / f"{name}_{hex_colour}.png"
    if path.exists():
        return path

    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    _REGISTRY[name](draw, CANVAS, STROKE, (*colour, 255))

    image = image.resize((TARGET_PX, TARGET_PX), Image.LANCZOS)
    image.save(path, "PNG")
    return path


def icon_path(name: str, colour: tuple[int, int, int]) -> str:
    return str(render(name, colour))


def render_all(colours: dict[str, tuple[int, int, int]]) -> int:
    """Pre-render every icon in every supplied colour. Returns the file count."""
    count = 0
    for name in available():
        for colour in colours.values():
            render(name, colour)
            count += 1
    return count


def contact_sheet(colour: tuple[int, int, int], out_path: Path | None = None) -> Path:
    """Render every icon into one grid image, for reviewing the set at a glance."""
    names = available()
    columns = 8
    rows = math.ceil(len(names) / columns)
    tile = TARGET_PX
    sheet = Image.new("RGBA", (columns * tile, rows * tile), (15, 23, 42, 255))

    for index, name in enumerate(names):
        glyph = Image.open(render(name, colour)).convert("RGBA")
        x = (index % columns) * tile
        y = (index // columns) * tile
        sheet.alpha_composite(glyph, (x, y))

    path = out_path or ASSET_DIR / "_contact_sheet.png"
    sheet.save(path, "PNG")
    return path


if __name__ == "__main__":
    from theme import BLUE, WHITE

    rendered = render_all({"blue": BLUE, "white": WHITE})
    sheet = contact_sheet(BLUE)
    print(f"{len(available())} icons available")
    print(f"{rendered} files rendered into {ASSET_DIR}")
    print(f"contact sheet: {sheet}")
