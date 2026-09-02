"""Bronze layer: search the Planetary Computer STAC API and land raw scenes.

Bronze promises fidelity. Nothing here reprojects, masks or renames. The only
columns added describe how and when the data arrived.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Iterable

import planetary_computer as pc
import pystac_client

from .config import BANDS, AreaOfInterest

STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
COLLECTION = "sentinel-2-l2a"


def open_catalog(url: str = STAC_URL) -> pystac_client.Client:
    """Open the STAC catalogue with the Planetary Computer signing hook.

    ``modifier=pc.sign_inplace`` signs assets as items are read. Signing at read
    time is deliberate: a signed href is a short-lived credential, so it must
    never be persisted to a table.
    """
    return pystac_client.Client.open(url, modifier=pc.sign_inplace)


def search_scenes(
    aoi: AreaOfInterest,
    date_start: str,
    date_end: str,
    max_cloud_cover: float = 20.0,
    max_scenes: int = 6,
    collection: str = COLLECTION,
    catalog: pystac_client.Client | None = None,
) -> list[Any]:
    """Find the least cloudy scenes covering the area of interest.

    Scene-level cloud cover is a blunt filter: a scene can be 40 percent cloudy
    overall and perfectly clear over a small area of interest. Sorting by cloud
    cover and taking the best handful is more useful than a hard threshold, so
    the threshold here is generous and the ranking does the work.
    """
    client = catalog or open_catalog()
    search = client.search(
        collections=[collection],
        bbox=list(aoi.bbox),
        datetime=f"{date_start}/{date_end}",
        query={"eo:cloud_cover": {"lt": max_cloud_cover}},
    )
    items = list(search.items())
    items.sort(key=lambda it: it.properties.get("eo:cloud_cover", 100.0))
    return items[:max_scenes]


def scene_catalog_rows(
    items: Iterable[Any],
    aoi: AreaOfInterest,
    pipeline_run_id: str,
    bands: tuple[str, ...] = BANDS,
) -> list[dict[str, Any]]:
    """Flatten STAC items into bronze catalogue rows.

    Asset hrefs are stored unsigned. Persisting a signed href creates a
    credential in a table and a support ticket three days later when it expires.
    """
    ingested_at = datetime.now(timezone.utc)
    rows: list[dict[str, Any]] = []
    for item in items:
        props = item.properties
        unsigned = {
            band: _strip_signature(item.assets[band].href)
            for band in bands
            if band in item.assets
        }
        rows.append(
            {
                "scene_id": item.id,
                "collection": item.collection_id,
                "datetime_utc": _parse_dt(props.get("datetime")),
                "cloud_cover_pct": float(props.get("eo:cloud_cover", float("nan"))),
                "epsg": int(props.get("proj:epsg") or props.get("proj:code", "0").split(":")[-1] or 0),
                "platform": props.get("platform", ""),
                "aoi_name": aoi.name,
                "bbox_wgs84": json.dumps(list(aoi.bbox)),
                "assets_json": json.dumps(unsigned),
                "ingested_at_utc": ingested_at,
                "pipeline_run_id": pipeline_run_id,
            }
        )
    return rows


def _strip_signature(href: str) -> str:
    """Remove the SAS query string so only the durable URL is stored."""
    return href.split("?", 1)[0]


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def load_bands(
    items: Iterable[Any],
    aoi: AreaOfInterest,
    bands: tuple[str, ...] = BANDS,
    resolution_m: int = 20,
    target_epsg: int | None = None,
):
    """Windowed read of the requested bands into an xarray Dataset.

    Passing the bounding box into the loader is what turns a multi-gigabyte
    scene into a few megabytes: the Cloud Optimized GeoTIFF layout lets the
    client fetch only the blocks that intersect the window.

    ``target_epsg`` is left as None in bronze on purpose. Reprojection belongs in
    silver, once, not scattered across ingestion.
    """
    import odc.stac

    return odc.stac.load(
        list(items),
        bands=list(bands),
        bbox=list(aoi.bbox),
        resolution=resolution_m,
        crs=f"EPSG:{target_epsg}" if target_epsg else None,
        chunks={},
        groupby="solar_day",
    )


def write_scene_raster(dataset, scene_dir: str, band: str) -> str:
    """Write one band of one scene to the Lakehouse as a GeoTIFF.

    Bronze rasters exist so that a silver result can be re-derived without going
    back to the network, which matters when someone asks in November why the
    August number looked the way it did.
    """
    import os

    os.makedirs(scene_dir, exist_ok=True)
    out_path = f"{scene_dir}/{band}.tif"
    dataset[band].rio.to_raster(out_path, driver="COG", compress="DEFLATE")
    return out_path
