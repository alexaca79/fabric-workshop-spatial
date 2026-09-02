"""Render the diagrams embedded in the docs.

These are drawn, not captured. Screenshotting the Fabric portal needs an
interactive sign-in with MFA, which cannot be automated here, and a stale
screenshot of a UI that changes every few months is worse than a clear diagram
of the thing that does not change. Each image is labelled as a diagram so nobody
mistakes it for a capture.

Run from the repository root::

    python scripts/build_doc_images.py

Output lands in docs/images/.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "docs" / "images"
sys.path.insert(0, str(REPO_ROOT / "decks"))

SCALE = 2  # draw at 2x and downsample, which is what keeps the text crisp

BG = (13, 23, 20)
CARD = (21, 38, 33)
EDGE = (31, 53, 46)
WHITE = (241, 245, 243)
MUTED = (156, 175, 168)
DIM = (100, 124, 116)
GREEN = (63, 193, 126)
BLUE = (56, 159, 247)
AMBER = (245, 158, 11)
RED = (239, 68, 68)
BRONZE = (192, 132, 74)
SILVER = (182, 194, 201)
GOLD = (227, 179, 65)


def font(size: int, bold: bool = False, mono: bool = False):
    """Segoe UI where available, with a graceful fall back to the default face."""
    names = (
        ["consola.ttf", "consolab.ttf"] if mono
        else (["segoeuib.ttf", "seguisb.ttf"] if bold else ["segoeui.ttf"])
    )
    for name in names:
        try:
            return ImageFont.truetype(name, size * SCALE)
        except OSError:
            continue
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf", size * SCALE)
    except OSError:
        return ImageFont.load_default()


def canvas(width: int, height: int):
    image = Image.new("RGB", (width * SCALE, height * SCALE), BG)
    return image, ImageDraw.Draw(image)


def box(draw, x, y, w, h, fill=CARD, edge=EDGE, width=1, radius=8):
    draw.rounded_rectangle(
        [x * SCALE, y * SCALE, (x + w) * SCALE, (y + h) * SCALE],
        radius=radius * SCALE, fill=fill, outline=edge, width=width * SCALE,
    )


def text(draw, x, y, value, size=13, colour=WHITE, bold=False, mono=False, anchor="la"):
    draw.text((x * SCALE, y * SCALE), value, font=font(size, bold, mono), fill=colour, anchor=anchor)


def arrow(draw, x1, y1, x2, y2, colour=GREEN, width=2, head=7):
    draw.line([x1 * SCALE, y1 * SCALE, x2 * SCALE, y2 * SCALE], fill=colour, width=width * SCALE)
    if x2 != x1:
        direction = 1 if x2 > x1 else -1
        draw.polygon(
            [
                (x2 * SCALE, y2 * SCALE),
                ((x2 - direction * head) * SCALE, (y2 - head * 0.55) * SCALE),
                ((x2 - direction * head) * SCALE, (y2 + head * 0.55) * SCALE),
            ],
            fill=colour,
        )
    else:
        direction = 1 if y2 > y1 else -1
        draw.polygon(
            [
                (x2 * SCALE, y2 * SCALE),
                ((x2 - head * 0.55) * SCALE, (y2 - direction * head) * SCALE),
                ((x2 + head * 0.55) * SCALE, (y2 - direction * head) * SCALE),
            ],
            fill=colour,
        )


def footer(draw, width, height, label):
    text(draw, 20, height - 22, label, 10, DIM)


def save(image, name):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / name
    image.resize((image.width // SCALE, image.height // SCALE), Image.LANCZOS).save(path, "PNG")
    print(f"  {name}  ({path.stat().st_size // 1024} KB)")
    return path


# ---------------------------------------------------------------------------
# 1. Three workspace layout
# ---------------------------------------------------------------------------

def three_workspace_layout():
    W, H = 900, 392
    image, draw = canvas(W, H)

    text(draw, 24, 22, "Three workspaces, one per medallion layer", 19, WHITE, bold=True)
    text(draw, 24, 50, "Cross-layer reads travel over OneLake shortcuts. Nothing is copied.",
         12, MUTED)

    layers = [
        ("BRONZE", "jdi-mock-training-bronze", "lh_bronze", BRONZE,
         ["bronze_stand_register", "bronze_scene_catalog", "Files/bronze/scenes/"]),
        ("SILVER", "jdi-mock-training-silver", "lh_silver", SILVER,
         ["silver_stand_observations", "shortcut: bronze_stand_register",
          "shortcut: bronze_scene_catalog"]),
        ("GOLD", "jdi-mock-training-gold", "lh_gold", GOLD,
         ["gold_stand_facts + dims", "shortcut: silver_stand_observations",
          "shortcut: bronze_stand_register"]),
    ]

    x, y, w, h, gap = 24, 90, 276, 196, 24
    for index, (name, workspace, lakehouse, colour, items) in enumerate(layers):
        left = x + index * (w + gap)
        box(draw, left, y, w, h, edge=colour, width=2)
        draw.rectangle(
            [left * SCALE, y * SCALE, (left + w) * SCALE, (y + 34) * SCALE],
            fill=colour,
        )
        text(draw, left + 14, y + 9, name, 14, BG, bold=True)
        text(draw, left + 14, y + 46, workspace, 11.5, WHITE, bold=True)
        text(draw, left + 14, y + 66, f"Lakehouse  {lakehouse}", 11, MUTED)
        draw.line(
            [(left + 14) * SCALE, (y + 90) * SCALE, (left + w - 14) * SCALE, (y + 90) * SCALE],
            fill=EDGE, width=1 * SCALE,
        )
        for row, item in enumerate(items):
            is_shortcut = item.startswith("shortcut:")
            text(draw, left + 14, y + 104 + row * 26, item, 10.5,
                 BLUE if is_shortcut else MUTED, mono=True)

        if index < len(layers) - 1:
            arrow(draw, left + w + 3, y + h / 2, left + w + gap - 3, y + h / 2, GREEN, 2, 8)

    # Gold also reaches back past silver to bronze, which is the edge people miss.
    bronze_left, gold_left = 24, 24 + 2 * (w + gap)
    depth = y + h + 34
    draw.line([(bronze_left + w / 2) * SCALE, (y + h) * SCALE,
               (bronze_left + w / 2) * SCALE, depth * SCALE], fill=AMBER, width=2 * SCALE)
    draw.line([(bronze_left + w / 2) * SCALE, depth * SCALE,
               (gold_left + w / 2) * SCALE, depth * SCALE], fill=AMBER, width=2 * SCALE)
    arrow(draw, gold_left + w / 2, depth, gold_left + w / 2, y + h + 3, AMBER, 2, 8)
    text(draw, (bronze_left + w / 2) + 14, depth + 6,
         "notebook 05 reads bronze_stand_register directly, skipping silver", 10.5, AMBER)

    footer(draw, W, H, "Diagram, not a screenshot  ·  docs/13-three-workspace-layout.md")
    return save(image, "three-workspace-layout.png")


# ---------------------------------------------------------------------------
# 2. Notebook binding: environment + default lakehouse
# ---------------------------------------------------------------------------

def notebook_binding():
    W, H = 900, 400
    image, draw = canvas(W, H)

    text(draw, 24, 22, "What a notebook must be bound to before it will run", 19, WHITE, bold=True)
    text(draw, 24, 50, "Both selections live in the notebook ribbon. Both are per notebook.", 12, MUTED)

    # Mock ribbon
    box(draw, 24, 86, 852, 56, fill=(16, 31, 27), edge=EDGE)
    text(draw, 40, 96, "01_bronze_stac_ingest", 12.5, WHITE, bold=True)
    text(draw, 40, 116, "Home   Edit   Run   View", 10.5, DIM)

    box(draw, 470, 96, 180, 36, fill=CARD, edge=GREEN, width=2)
    text(draw, 484, 106, "Environment", 9, DIM)
    text(draw, 484, 117, "env_forestops", 11, GREEN, bold=True)

    box(draw, 664, 96, 196, 36, fill=CARD, edge=BRONZE, width=2)
    text(draw, 678, 106, "Default lakehouse", 9, DIM)
    text(draw, 678, 117, "lh_bronze", 11, BRONZE, bold=True)

    panels = [
        (24, GREEN, "Environment  ·  env_forestops",
         ["Carries the pinned library set:", "geopandas, rasterio, odc-stac,",
          "planetary-computer, zarr, affine<3", "",
          "Without it: ModuleNotFoundError", "on the first import cell."]),
        (462, BRONZE, "Default lakehouse  ·  lh_bronze",
         ["Resolves every unqualified", "spark.table(\"...\") call.", "",
          "Wrong lakehouse attached:", "TABLE_OR_VIEW_NOT_FOUND,", "or worse, the wrong layer's data."]),
    ]
    for left, colour, head, lines in panels:
        box(draw, left, 168, 414, 190, edge=colour, width=2)
        text(draw, left + 18, 184, head, 13, colour, bold=True)
        for row, line in enumerate(lines):
            text(draw, left + 18, 214 + row * 22, line, 11, MUTED,
                 mono=line.startswith(("geopandas", "planetary", "spark.table", "TABLE_")))

    footer(draw, W, H, "Diagram, not a screenshot  ·  docs/12-spark-environment.md")
    return save(image, "notebook-binding.png")


# ---------------------------------------------------------------------------
# 3. Pipeline activity graph
# ---------------------------------------------------------------------------

def pipeline_graph():
    W, H = 900, 380
    image, draw = canvas(W, H)

    text(draw, 24, 22, "The scheduled pipeline", 19, WHITE, bold=True)
    text(draw, 24, 50, "One gate, placed after silver: late enough to measure real quality, "
                       "early enough that a bad month never reaches a planner.", 12, MUTED)

    steps = [
        ("Bronze\ningest", BRONZE), ("Silver\nderive", SILVER), ("Quality\ngate", RED),
        ("Gold\nclassify", GOLD), ("AI\nenrichment", GOLD), ("Publish\nstar schema", BLUE),
    ]
    x, y, w, h, gap = 24, 104, 122, 96, 22
    for index, (label, colour) in enumerate(steps):
        left = x + index * (w + gap)
        box(draw, left, y, w, h, edge=colour, width=2)
        for row, line in enumerate(label.split("\n")):
            text(draw, left + w / 2, y + 32 + row * 20, line, 12.5, colour, bold=True, anchor="ma")
        if index < len(steps) - 1:
            arrow(draw, left + w + 2, y + h / 2, left + w + gap - 2, y + h / 2, EDGE, 2, 7)

    gate_left = x + 2 * (w + gap)
    box(draw, gate_left - 40, y + h + 34, 200, 92, edge=RED, width=2)
    text(draw, gate_left - 26, y + h + 48, "If the gate fails", 12, RED, bold=True)
    for row, line in enumerate(["Gold is not touched.",
                                "Last month's tables stay live.",
                                "A named person is emailed."]):
        text(draw, gate_left - 26, y + h + 72 + row * 18, line, 10.5, MUTED)
    arrow(draw, gate_left + w / 2, y + h + 2, gate_left + w / 2, y + h + 30, RED, 2, 7)

    box(draw, 500, y + h + 34, 376, 92, edge=EDGE)
    text(draw, 518, y + h + 48, "Parameters", 12, GREEN, bold=True)
    for row, line in enumerate(["aoi_name, aoi_bbox, date_start, date_end",
                                "max_cloud_cover, min_scene_count",
                                "One pipeline serves every licence block."]):
        text(draw, 518, y + h + 72 + row * 18, line, 10.5, MUTED, mono=row < 2)

    footer(draw, W, H, "Diagram, not a screenshot  ·  pipelines/forest_classification_pipeline.json")
    return save(image, "pipeline-graph.png")


# ---------------------------------------------------------------------------
# 4. Star schema
# ---------------------------------------------------------------------------

def star_schema():
    W, H = 900, 490
    image, draw = canvas(W, H)

    text(draw, 24, 22, "The Direct Lake star schema", 19, WHITE, bold=True)
    text(draw, 24, 50, "Single-direction relationships, no calculated columns. "
                       "Both are Direct Lake fallback triggers.", 12, MUTED)

    fact_x, fact_y, fact_w, fact_h = 356, 196, 190, 116
    dim_w, dim_h = 200, 106

    # Draw the relationships first so the boxes sit on top of the line ends,
    # which keeps an arrow from appearing to pierce a table.
    links = [
        ((60 + dim_w, 76 + dim_h / 2), (fact_x, fact_y + 22), "many to one"),
        ((640, 76 + dim_h / 2), (fact_x + fact_w, fact_y + 22), "many to one"),
        ((60 + dim_w, 326 + dim_h / 2), (fact_x, fact_y + fact_h - 22), "many to one"),
    ]
    for (sx, sy), (ex, ey), label in links:
        draw.line([sx * SCALE, sy * SCALE, ex * SCALE, ey * SCALE], fill=EDGE, width=2 * SCALE)
        text(draw, (sx + ex) / 2, (sy + ey) / 2 - 16, label, 9.5, DIM, anchor="ma")

    box(draw, fact_x, fact_y, fact_w, fact_h, edge=GREEN, width=2)
    text(draw, fact_x + fact_w / 2, fact_y + 14, "gold_stand_facts", 12.5, GREEN,
         bold=True, anchor="ma")
    for row, line in enumerate(["102 rows", "stand_id", "date_key", "forest_class"]):
        text(draw, fact_x + fact_w / 2, fact_y + 40 + row * 19, line, 10.5,
             MUTED if row == 0 else WHITE, mono=row > 0, anchor="ma")

    dims = [
        (60, 76, "gold_dim_stand", ["120 rows", "stand_id", "lat / lon", "licence_block"], BRONZE),
        (640, 76, "gold_dim_date", ["365 rows", "date_key", "date", "year / month"], BLUE),
        (60, 326, "gold_dim_forest_class", ["7 rows", "forest_class", "colour_hex",
                                            "display_order"], GOLD),
    ]
    for dx, dy, name, lines, colour in dims:
        box(draw, dx, dy, dim_w, dim_h, edge=colour, width=2)
        text(draw, dx + dim_w / 2, dy + 11, name, 12, colour, bold=True, anchor="ma")
        for row, line in enumerate(lines):
            text(draw, dx + dim_w / 2, dy + 34 + row * 18, line, 10,
                 MUTED if row == 0 else WHITE, mono=row > 0, anchor="ma")

    box(draw, 600, 326, 276, 106, edge=AMBER, width=2)
    text(draw, 616, 340, "Mark the date table on `date`", 12, AMBER, bold=True)
    for row, line in enumerate(["not on `date_key`.", "Time intelligence against an integer",
                                "returns blank rather than erroring."]):
        text(draw, 616, 366 + row * 19, line, 10.5, MUTED)

    footer(draw, W, H, "Diagram, not a screenshot  ·  powerbi/semantic-model-guide.md")
    return save(image, "star-schema.png")


# ---------------------------------------------------------------------------
# 5. Debugging flow
# ---------------------------------------------------------------------------

def debugging_flow():
    W, H = 900, 350
    image, draw = canvas(W, H)

    text(draw, 24, 22, "Getting a real traceback out of a failed notebook job", 19, WHITE, bold=True)

    box(draw, 24, 62, 852, 52, fill=(30, 16, 16), edge=RED, width=2)
    text(draw, 42, 74, "System_Cancelled_Session_Statements_Failed", 12.5, RED, bold=True, mono=True)
    text(draw, 42, 94, "No cell. No line. No exception type. Any uncaught raise produces exactly this.",
         10.5, MUTED)

    steps = [
        ("1", "Trace it", "fabric_trace_notebook.py\nruns each cell in a\ncatching harness", GREEN),
        ("2", "Read the cell", "Per-cell status plus the\nfull traceback, written\nto OneLake", BLUE),
        ("3", "Probe the theory", "fabric_probe.py checks\nversions and reproduces\nthe fault in isolation", AMBER),
        ("4", "Verify the fix", "Confirm in a live session\nbefore editing any\nworkshop material", GOLD),
    ]
    x, y, w, h, gap = 24, 140, 200, 132, 17
    for index, (number, head, body, colour) in enumerate(steps):
        left = x + index * (w + gap)
        box(draw, left, y, w, h, edge=colour, width=2)
        draw.ellipse(
            [(left + 16) * SCALE, (y + 16) * SCALE, (left + 42) * SCALE, (y + 42) * SCALE],
            fill=colour,
        )
        text(draw, left + 29, y + 22, number, 12, BG, bold=True, anchor="ma")
        text(draw, left + 52, y + 22, head, 13, colour, bold=True)
        for row, line in enumerate(body.split("\n")):
            text(draw, left + 18, y + 58 + row * 19, line, 10,
                 MUTED, mono=line.startswith("fabric_"))
        if index < len(steps) - 1:
            arrow(draw, left + w + 1, y + h / 2, left + w + gap - 1, y + h / 2, EDGE, 2, 6)

    text(draw, 24, 296, "Never let an exception escape in a Fabric notebook job. The session "
                        "cancellation is what destroys the diagnostic information.", 11.5, AMBER)
    footer(draw, W, H, "Diagram, not a screenshot  ·  docs/14-debugging-notebook-failures.md")
    return save(image, "debugging-flow.png")


def main() -> int:
    print("rendering doc images...")
    for builder in (three_workspace_layout, notebook_binding, pipeline_graph,
                    star_schema, debugging_flow):
        builder()
    print(f"\ndone -> {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
