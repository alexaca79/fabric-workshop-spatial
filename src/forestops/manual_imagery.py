"""Validate manually downloaded Sentinel-2 assets without network access."""

from __future__ import annotations

import json
import math
from datetime import date
from pathlib import Path
from urllib.parse import unquote, urlsplit, urlunsplit

import pystac
import rasterio
from shapely.geometry import box, shape

MANUAL_BANDS = ("B04", "B08", "B11", "B12", "SCL")


def read_manual_items(folder: str | Path) -> list[pystac.Item]:
    """Read one to six scene folders containing item.json and five original TIFFs.

    Args:
        folder: Uploaded scene folder, or parent of uploaded scene folders.

    Returns:
        STAC items restricted to verified local analysis bands. Each asset keeps
        its unsigned Planetary Computer URL in ``source_href`` for provenance.

    Raises:
        ValueError: Metadata, paths, raster headers, or scene identities disagree.
        FileNotFoundError: The metadata or a required band was not uploaded.
    """
    root = Path(folder).resolve()
    manifests = [root / "item.json"] if (root / "item.json").is_file() else sorted(root.glob("*/item.json"))
    if not manifests:
        raise FileNotFoundError("Upload item.json and all five original TIFF bands to the configured scene folder.")
    if len(manifests) > 6:
        raise ValueError("Use at most six Sentinel-2 scenes for this workshop.")
    items = []
    identities = set()
    native_crs = set()
    for manifest in manifests:
        if manifest.stat().st_size > 2_000_000:
            raise ValueError("item.json is too large; use a single STAC Item, not a catalogue export.")
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        if payload.get("type") != "Feature" or payload.get("collection") != "sentinel-2-l2a":
            raise ValueError("item.json must be a Sentinel-2 L2A STAC Item from Planetary Computer.")
        item = pystac.Item.from_dict(payload, preserve_dict=True)
        if not item.id or item.id in identities or item.datetime is None:
            raise ValueError("Every scene needs a unique STAC ID and acquisition datetime.")
        if item.datetime.tzinfo is None:
            raise ValueError("The STAC acquisition datetime must include a timezone.")
        cloud = item.properties.get("eo:cloud_cover")
        if not isinstance(cloud, (int, float)) or not math.isfinite(cloud) or not 0 <= cloud <= 100:
            raise ValueError("The STAC Item must record finite cloud cover between 0 and 100 percent.")
        identities.add(item.id)
        verified_assets = {}
        scene_crs = set()
        for band in MANUAL_BANDS:
            asset = item.assets.get(band)
            if asset is None:
                raise ValueError(f"STAC metadata is missing {band}; RGB previews cannot replace analysis bands.")
            address = urlsplit(asset.href)
            filename = unquote(address.path.rsplit("/", 1)[-1])
            if address.scheme != "https" or not address.hostname or not address.hostname.endswith(".blob.core.windows.net"):
                raise ValueError(f"{band} must reference a Planetary Computer Azure Blob asset.")
            if not filename or Path(filename).name != filename or "/" in filename or "\\" in filename:
                raise ValueError(f"{band} has an invalid asset filename.")
            path = (manifest.parent / filename).resolve()
            if not path.is_relative_to(manifest.parent.resolve()) or path.suffix.lower() not in {".tif", ".tiff"}:
                raise ValueError(f"{band} must be a TIFF in the same folder as item.json.")
            if not path.is_file():
                raise FileNotFoundError(f"Upload the original {band} TIFF named {filename} beside item.json.")
            projection = item.properties | asset.extra_fields
            expected_crs = projection.get("proj:code") or projection.get("proj:epsg")
            expected_shape = projection.get("proj:shape")
            expected_transform = projection.get("proj:transform")
            if expected_crs is None or expected_shape is None or expected_transform is None:
                raise ValueError(f"{band} metadata lacks projection, shape or transform; download the complete STAC Item.")
            with rasterio.open(path) as raster:
                if raster.driver != "GTiff" or raster.count != 1 or raster.crs is None or not raster.crs.is_projected:
                    raise ValueError(f"{band} must be a single-band projected GeoTIFF, not a preview image.")
                if raster.crs != rasterio.crs.CRS.from_user_input(expected_crs):
                    raise ValueError(f"{band} CRS does not match item.json.")
                if [raster.height, raster.width] != list(expected_shape):
                    raise ValueError(f"{band} dimensions do not match item.json; do not substitute a crop or another scene.")
                actual_transform = list(raster.transform)[:6]
                if len(expected_transform) < 6 or any(
                    not math.isclose(actual, expected, rel_tol=0, abs_tol=1e-6)
                    for actual, expected in zip(actual_transform, expected_transform[:6], strict=True)
                ):
                    raise ValueError(f"{band} grid does not match item.json.")
                accepted_dtypes = {"uint8", "uint16"} if band == "SCL" else {"uint16"}
                if (raster.dtypes[0] not in accepted_dtypes or raster.nodata not in (None, 0)
                        or raster.scales != (1.0,) or raster.offsets != (0.0,)):
                    raise ValueError(f"{band} must retain original Sentinel-2 integer values without scaling or altered nodata.")
                scene_crs.add(raster.crs.to_epsg())
            local_asset = asset.clone()
            local_asset.href = str(path)
            local_asset.extra_fields["source_href"] = urlunsplit((address.scheme, address.netloc, address.path, "", ""))
            verified_assets[band] = local_asset
        if len(scene_crs) != 1 or None in scene_crs:
            raise ValueError("All five bands for a scene must use the same native EPSG code.")
        native_crs.update(scene_crs)
        item.assets = {}
        for band, asset in verified_assets.items():
            item.add_asset(band, asset)
        item.links = []
        item.properties["input_mode"] = "manual"
        item.properties["proj:code"] = f"EPSG:{next(iter(scene_crs))}"
        items.append(item)
    if len(native_crs) != 1:
        raise ValueError("Choose scenes from one native UTM zone; Bronze must not silently reproject mixed zones.")
    return sorted(items, key=lambda item: (item.properties["eo:cloud_cover"], item.id))


def validate_scene_selection(
    items: list[pystac.Item], bbox: tuple[float, float, float, float],
    date_start: str, date_end: str, max_cloud: float, max_scenes: int,
) -> None:
    """Reject empty, out-of-area, out-of-period or mixed-projection inputs."""
    if not items or len(items) > max_scenes:
        raise ValueError(f"Select between one and {max_scenes} scenes before continuing.")
    start = date.fromisoformat(date_start)
    end = date.fromisoformat(date_end)
    if start > end:
        raise ValueError("DATE_START must not be after DATE_END.")
    area = box(*bbox)
    projections = set()
    identities = set()
    for item in items:
        if item.collection_id != "sentinel-2-l2a" or item.id in identities:
            raise ValueError("Use unique Sentinel-2 L2A scene IDs.")
        identities.add(item.id)
        if item.datetime is None or not start <= item.datetime.date() <= end:
            raise ValueError(f"Scene {item.id} is outside DATE_START/DATE_END.")
        footprint = shape(item.geometry) if item.geometry else None
        if footprint is None or not footprint.is_valid or footprint.intersection(area).area <= 0:
            raise ValueError(f"Scene {item.id} does not intersect AOI_BBOX.")
        cloud = item.properties.get("eo:cloud_cover")
        if not isinstance(cloud, (int, float)) or not math.isfinite(cloud) or not 0 <= cloud < max_cloud:
            raise ValueError(f"Scene {item.id} is not below MAX_CLOUD_COVER.")
        if not set(MANUAL_BANDS).issubset(item.assets):
            raise ValueError(f"Scene {item.id} is missing required analysis bands.")
        for band in MANUAL_BANDS:
            properties = item.properties | item.assets[band].extra_fields
            code = properties.get("proj:code") or properties.get("proj:epsg")
            if code is None:
                raise ValueError(f"Scene {item.id} has no native projection metadata.")
            projections.add(rasterio.crs.CRS.from_user_input(code).to_epsg())
    if len(projections) != 1 or None in projections:
        raise ValueError("Choose scenes from one native EPSG grid; reprojection belongs in Silver.")
