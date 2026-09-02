"""Zonal statistics: the step that turns imagery into one row per stand.

This is where raster becomes tabular, and where the pipeline stops being a
remote sensing exercise and starts being something a planner can join to
everything else Woodlands holds.
"""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd
import xarray as xr

from .config import CRS_ANALYSIS


def zonal_stats(
    index_ds: xr.Dataset,
    stands: gpd.GeoDataFrame,
    stand_id_col: str = "stand_id",
    percentiles: tuple[int, ...] = (10, 90),
) -> pd.DataFrame:
    """Summarise every index within every stand boundary.

    Returns one row per stand with mean and selected percentiles per index, plus
    the pixel accounting needed to decide whether the row can be trusted.

    The percentiles matter more than they look. A mean NDVI over a stand with a
    shadowed north edge is dragged down by pixels that say nothing about the
    canopy; the 90th percentile is far more stable across dates.
    """
    _assert_aligned(index_ds, stands)

    records: list[dict[str, float | str | int]] = []
    index_names = list(index_ds.data_vars)

    for _, stand in stands.iterrows():
        try:
            clipped = index_ds.rio.clip([stand.geometry], crs=stands.crs, drop=True, all_touched=False)
        except Exception:
            # A stand entirely outside the raster window is a legitimate outcome,
            # not an error. It is recorded with zero pixels so the gap is visible
            # rather than silently absent from the output.
            records.append(_empty_record(stand[stand_id_col], index_names))
            continue

        record: dict[str, float | str | int] = {stand_id_col: stand[stand_id_col]}
        total_pixels = 0
        valid_pixels = 0

        for name in index_names:
            values = clipped[name].values.ravel()
            finite = values[np.isfinite(values)]
            total_pixels = max(total_pixels, values.size)
            valid_pixels = max(valid_pixels, finite.size)

            if finite.size == 0:
                record[f"{name}_mean"] = float("nan")
                for p in percentiles:
                    record[f"{name}_p{p}"] = float("nan")
                continue

            record[f"{name}_mean"] = float(np.mean(finite))
            for p in percentiles:
                record[f"{name}_p{p}"] = float(np.percentile(finite, p))

        record["pixel_count"] = int(total_pixels)
        record["valid_pixel_count"] = int(valid_pixels)
        record["valid_pixel_fraction"] = float(valid_pixels / total_pixels) if total_pixels else 0.0
        records.append(record)

    return pd.DataFrame.from_records(records)


def _empty_record(stand_id: str, index_names: list[str]) -> dict[str, float | str | int]:
    record: dict[str, float | str | int] = {"stand_id": stand_id}
    for name in index_names:
        record[f"{name}_mean"] = float("nan")
        record[f"{name}_p10"] = float("nan")
        record[f"{name}_p90"] = float("nan")
    record["pixel_count"] = 0
    record["valid_pixel_count"] = 0
    record["valid_pixel_fraction"] = 0.0
    return record


def _assert_aligned(index_ds: xr.Dataset, stands: gpd.GeoDataFrame) -> None:
    """Refuse to compute statistics across mismatched coordinate systems.

    Silently returning NaN for every stand is the usual behaviour when the
    raster and the vectors disagree, and it costs an afternoon to diagnose.
    """
    if stands.crs is None:
        raise ValueError("stand geometry has no CRS; declare it with .set_crs() before zonal statistics")
    if index_ds.rio.crs is None:
        raise ValueError("index raster has no CRS; reprojection must run before zonal statistics")

    raster_epsg = index_ds.rio.crs.to_epsg()
    vector_epsg = stands.crs.to_epsg()
    if raster_epsg != vector_epsg:
        raise ValueError(
            f"raster is EPSG:{raster_epsg} and stands are EPSG:{vector_epsg}. Align them first; "
            "mismatched CRS produces NaN for every stand and no error message."
        )


def attach_stand_attributes(
    stats: pd.DataFrame,
    stands: gpd.GeoDataFrame,
    scene_id: str,
    scene_date,
    keep: tuple[str, ...] = ("licence_block", "species_group", "planted_year", "management_regime"),
) -> pd.DataFrame:
    """Join register attributes and scene identity onto the statistics."""
    projected = stands.to_crs(CRS_ANALYSIS) if stands.crs.to_epsg() != CRS_ANALYSIS else stands
    attrs = projected[["stand_id", *[c for c in keep if c in projected.columns]]].copy()
    attrs["area_ha"] = projected.geometry.area.to_numpy() / 10_000.0

    out = stats.merge(attrs, on="stand_id", how="left", validate="one_to_one")
    out.insert(1, "scene_id", scene_id)
    out.insert(2, "scene_date", pd.to_datetime(scene_date).date())
    out["srid"] = CRS_ANALYSIS
    return out
