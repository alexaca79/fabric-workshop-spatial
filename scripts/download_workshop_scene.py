"""Download the documented public Sentinel-2 scene for maintainer verification.

Learners use the Planetary Computer browser download links in the handout.
This helper performs the equivalent original-file download for release testing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
from pathlib import Path
from urllib.parse import urlsplit

import planetary_computer
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from forestops.manual_imagery import MANUAL_BANDS, read_manual_items, validate_scene_selection

SCENE_ID = "S2C_MSIL2A_20260629T152621_R068_T19TFM_20260629T201011"
ITEM_URL = f"https://planetarycomputer.microsoft.com/api/stac/v1/collections/sentinel-2-l2a/items/{SCENE_ID}"
LOGGER = logging.getLogger(__name__)


def download_scene(output: Path) -> dict:
    """Download exact original files, validate headers, and write a hash receipt."""
    output.mkdir(parents=True, exist_ok=True)
    response = requests.get(ITEM_URL, timeout=60)
    response.raise_for_status()
    payload = response.json()
    if payload.get("id") != SCENE_ID:
        raise ValueError("The catalogue returned an unexpected scene")
    records = []
    for band in MANUAL_BANDS:
        source = payload["assets"][band]["href"].split("?", 1)[0]
        path = output / Path(urlsplit(source).path).name
        signed = planetary_computer.sign(source)
        with requests.get(signed, stream=True, timeout=(30, 120)) as response:
            if response.status_code != 200:
                raise RuntimeError(f"{band} download returned HTTP {response.status_code}")
            expected = int(response.headers.get("Content-Length", 0))
            if path.exists() and expected and path.stat().st_size == expected:
                LOGGER.info("Verified existing size for %s", band)
            else:
                temporary = path.with_suffix(".partial")
                with temporary.open("wb") as stream:
                    for chunk in response.iter_content(1024 * 1024):
                        stream.write(chunk)
                if expected and temporary.stat().st_size != expected:
                    raise ValueError(f"{band} download is incomplete")
                temporary.replace(path)
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        records.append({"band": band, "filename": path.name, "bytes": path.stat().st_size,
                        "sha256": digest, "source_href": source})
        LOGGER.info("%s: %.1f MB downloaded", band, path.stat().st_size / 1e6)
    for asset in payload["assets"].values():
        if (urlsplit(asset["href"]).hostname or "").endswith(".blob.core.windows.net"):
            asset["href"] = asset["href"].split("?", 1)[0]
    (output / "item.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    items = read_manual_items(output)
    validate_scene_selection(items, (-66.9, 46.1, -66.4, 46.4), "2026-06-01", "2026-08-31", 20, 6)
    result = {"scene_id": SCENE_ID, "item_url": ITEM_URL, "validation": "PASS",
              "files": records, "download_bytes": sum(item["bytes"] for item in records)}
    (output / "download-receipt.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def create_parser() -> argparse.ArgumentParser:
    """Create the maintainer download command parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    return parser


def main() -> int:
    """Download without displaying signed URLs or credentials."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        receipt = download_scene(create_parser().parse_args().output)
    except (OSError, ValueError, RuntimeError, requests.RequestException) as error:
        LOGGER.error("Download failed (%s); check connectivity and retry. Signed URLs are not logged.", type(error).__name__)
        return 1
    LOGGER.info("Scene %s: %s, %.1f MB total", receipt["scene_id"], receipt["validation"], receipt["download_bytes"] / 1e6)
    return 0


if __name__ == "__main__":
    sys.exit(main())
