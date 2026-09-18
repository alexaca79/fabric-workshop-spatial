"""Add numbered callouts to real portal captures, keeping raw images unchanged.

Usage:
    python scripts/annotate_manual_screenshots.py [--only 08-lakehouse-create.png]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from PIL.PngImagePlugin import PngInfo

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PLAN = ROOT / "scripts/verification/screenshots/manual/annotations.json"
INK = "#17352E"
ACCENT = "#CB3A24"
WHITE = "#FFFFFF"
LOGGER = logging.getLogger(__name__)


def font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Use the same readable caption font as the existing workshop images."""
    for name in ("segoeuib.ttf" if bold else "segoeui.ttf",
                 "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def wrapped_lines(draw: ImageDraw.ImageDraw, text: str, width: int,
                  text_font: ImageFont.FreeTypeFont | ImageFont.ImageFont) -> list[str]:
    """Wrap caption words without shrinking the original screenshot."""
    lines: list[str] = []
    current = ""
    for word in text.split():
        if draw.textlength(word, font=text_font) > width:
            raise ValueError(f"Caption word is too wide: {word}")
        candidate = f"{current} {word}".strip()
        if current and draw.textlength(candidate, font=text_font) > width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def annotate(raw: Path, output: Path, capture: dict) -> dict:
    """Render bounded callouts and return a source-hash receipt.

    Raises:
        ValueError: A callout is outside the image or would overwrite its source.
    """
    if raw.resolve() == output.resolve():
        raise ValueError("Annotated output must not overwrite the raw capture")
    source_hash = hashlib.sha256(raw.read_bytes()).hexdigest()
    with Image.open(raw) as original:
        source = original.convert("RGB")
    image_width, image_height = source.size
    probe = ImageDraw.Draw(source)
    caption_font = font(16)
    title_font = font(19, bold=True)
    caption_lines = wrapped_lines(probe, capture["title"], image_width - 40, title_font)
    callouts = capture["focus"]
    if not 1 <= len(callouts) <= 4:
        raise ValueError("Use one to four focused callouts per screenshot")
    for number, callout in enumerate(callouts, 1):
        caption_lines.extend(wrapped_lines(
            probe, f"{number}. {callout['text']}", image_width - 40, caption_font,
        ))
    footer_height = 34 + 25 * len(caption_lines)
    annotated = Image.new("RGB", (image_width, image_height + footer_height), WHITE)
    annotated.paste(source, (0, 0))
    draw = ImageDraw.Draw(annotated)
    for number, callout in enumerate(callouts, 1):
        left, top, width, height = callout["box"]
        badge_x, badge_y = callout["badge"]
        if not (width > 0 and height > 0 and 0 <= left < left + width <= image_width
                and 0 <= top < top + height <= image_height):
            raise ValueError(f"Callout {number} is outside {raw.name}")
        if not (18 <= badge_x <= image_width - 18 and 18 <= badge_y <= image_height - 18):
            raise ValueError(f"Badge {number} is outside {raw.name}")
        center_x, center_y = left + width / 2, top + height / 2
        radius_x, radius_y = width / 2 + 5, height / 2 + 5
        delta_x, delta_y = badge_x - center_x, badge_y - center_y
        ellipse_distance = math.hypot(delta_x / radius_x, delta_y / radius_y)
        if ellipse_distance <= 1:
            raise ValueError(f"Badge {number} must be outside its target")
        target_x = center_x + delta_x / ellipse_distance
        target_y = center_y + delta_y / ellipse_distance
        distance = math.hypot(target_x - badge_x, target_y - badge_y)
        unit_x, unit_y = (target_x - badge_x) / distance, (target_y - badge_y) / distance
        start = (badge_x + 17 * unit_x, badge_y + 17 * unit_y)
        end = (target_x, target_y)
        ellipse = (center_x - radius_x, center_y - radius_y,
                   center_x + radius_x, center_y + radius_y)
        draw.ellipse(ellipse, outline=WHITE, width=7)
        draw.ellipse(ellipse, outline=ACCENT, width=3)
        draw.line((start, end), fill=WHITE, width=8)
        draw.line((start, end), fill=ACCENT, width=4)
        draw.polygon((end,
                      (target_x - 12 * unit_x + 6 * unit_y,
                       target_y - 12 * unit_y - 6 * unit_x),
                      (target_x - 12 * unit_x - 6 * unit_y,
                       target_y - 12 * unit_y + 6 * unit_x)), fill=ACCENT)
        draw.ellipse((badge_x - 16, badge_y - 16, badge_x + 16, badge_y + 16),
                     fill=ACCENT, outline=WHITE, width=3)
        draw.text((badge_x, badge_y - 1), str(number), fill=WHITE,
                  font=font(16, bold=True), anchor="mm")
    draw.line((0, image_height, image_width, image_height), fill="#C4D3CF", width=2)
    for index, line in enumerate(caption_lines):
        draw.text((20, image_height + 14 + index * 25), line, fill=INK,
                  font=title_font if index == 0 else caption_font)
    metadata = PngInfo()
    metadata.add_text("Source SHA256", source_hash)
    metadata.add_text("Source", f"raw/{raw.name}")
    metadata.add_text("Treatment", "Original portal pixels with numbered circle and arrow overlays")
    output.parent.mkdir(parents=True, exist_ok=True)
    annotated.save(output, pnginfo=metadata)
    if hashlib.sha256(raw.read_bytes()).hexdigest() != source_hash:
        raise RuntimeError(f"Raw screenshot changed during annotation: {raw.name}")
    return {"file": output.name, "raw_sha256": source_hash,
            "annotated_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            "raw_size": list(source.size), "annotated_size": list(annotated.size),
            "callouts": len(callouts)}


def create_parser() -> argparse.ArgumentParser:
    """Create the screenshot annotation command parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--only", help="Render a single filename from the annotation plan")
    return parser


def main() -> int:
    """Render the selected captures and a provenance receipt beside the images."""
    arguments = create_parser().parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        captures = json.loads(arguments.plan.read_text(encoding="utf-8"))["captures"]
        selected = [capture for capture in captures
                    if arguments.only is None or capture["file"] == arguments.only]
        if not selected:
            raise ValueError("No captures match --only")
        receipts = []
        for capture in selected:
            filename = capture["file"]
            if Path(filename).name != filename or Path(filename).suffix != ".png":
                raise ValueError(f"Expected a PNG filename without directories: {filename}")
            output = ROOT / "docs/images/training" / arguments.plan.parent.name / filename
            receipts.append(annotate(arguments.plan.parent / "raw" / filename, output, capture))
            LOGGER.info("Annotated %s", filename)
        receipt_name = "annotation-receipts.json" if not arguments.only else "annotation-preview.json"
        (arguments.plan.parent / receipt_name).write_text(
            json.dumps(receipts, indent=2) + "\n", encoding="utf-8",
        )
        return 0
    except (OSError, ValueError, KeyError, RuntimeError) as error:
        LOGGER.error("Annotation failed: %s", error)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
