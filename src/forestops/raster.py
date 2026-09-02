"""Silver layer raster work: masking, scaling and reprojection.

Silver promises comparability. Two scenes from different dates and different
UTM zones must produce numbers that can sit in the same column and be compared
without a footnote.
"""

from __future__ import annotations

import numpy as np
import xarray as xr

from .config import CRS_ANALYSIS, REFLECTANCE_SCALE, SCL_INVALID


def mask_invalid(ds: xr.Dataset, scl_band: str = "SCL", invalid: tuple[int, ...] = SCL_INVALID) -> xr.Dataset:
    """Mask cloud, shadow, snow and defective pixels using the scene classification layer.

    Masked pixels become NaN rather than zero. Zero is a legitimate reflectance
    value in deep shadow, so using it as a sentinel quietly deletes valid dark
    pixels and biases every index upward.
    """
    if scl_band not in ds:
        raise KeyError(f"{scl_band} not present; cloud masking cannot be skipped silently")

    scl = ds[scl_band]
    keep = ~scl.isin(list(invalid))

    masked = ds.drop_vars(scl_band).where(keep)
    masked = masked.assign_attrs(ds.attrs)
    masked["valid_mask"] = keep
    return masked


def scale_reflectance(ds: xr.Dataset, scale: float = REFLECTANCE_SCALE, bands: tuple[str, ...] | None = None) -> xr.Dataset:
    """Convert integer surface reflectance to the 0 to 1 range.

    This is the step most often skipped, and the failure is subtle: normalised
    ratios such as NDVI are unaffected because the scale cancels, so the data
    looks correct while every absolute threshold has silently moved by a factor
    of ten thousand.
    """
    target = bands or tuple(v for v in ds.data_vars if v != "valid_mask")
    out = ds.copy()
    for band in target:
        out[band] = ds[band].astype("float32") / scale
    return out


def reproject(ds: xr.Dataset, target_epsg: int = CRS_ANALYSIS, resampling: str = "bilinear") -> xr.Dataset:
    """Reproject a raster dataset to the analysis CRS.

    Done once, in silver. Reprojecting per query is slow and, worse, lets two
    reports disagree because they resampled differently.

    Continuous reflectance uses bilinear resampling. A categorical raster such as
    the scene classification layer must use nearest, because the average of
    class 4 and class 8 is not class 6.
    """
    if ds.rio.crs is None:
        raise ValueError(
            "raster has no CRS. odc.stac sets one on load; a missing CRS here usually means the "
            "dataset was rebuilt from arrays and lost its spatial metadata."
        )
    if ds.rio.crs.to_epsg() == target_epsg:
        return ds
    return ds.rio.reproject(f"EPSG:{target_epsg}", resampling=_resampling_enum(resampling))


def _resampling_enum(name: str):
    from rasterio.enums import Resampling

    try:
        return getattr(Resampling, name)
    except AttributeError as exc:  # pragma: no cover - configuration error
        raise ValueError(f"unknown resampling method '{name}'") from exc


def composite_median(ds: xr.Dataset, time_dim: str = "time") -> xr.Dataset:
    """Collapse a time stack to a per-pixel median.

    Median rather than mean because residual cloud that survived masking is
    bright and one-sided, so it drags a mean upward while barely moving a
    median. This is the cheapest defence against imperfect cloud masks.
    """
    if time_dim not in ds.dims:
        return ds
    return ds.median(dim=time_dim, skipna=True, keep_attrs=True)


def valid_fraction(ds: xr.Dataset, band: str) -> float:
    """Fraction of pixels in ``band`` that survived masking."""
    arr = ds[band].values
    total = arr.size
    if total == 0:
        return 0.0
    return float(np.count_nonzero(~np.isnan(arr)) / total)


def clip_to(ds: xr.Dataset, geometries, crs) -> xr.Dataset:
    """Clip a raster to the supplied geometries, aligning CRS first."""
    if ds.rio.crs is None:
        raise ValueError("raster has no CRS; clipping would silently produce an empty result")
    return ds.rio.clip(geometries, crs=crs, drop=True, all_touched=False)
