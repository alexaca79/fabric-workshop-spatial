"""Spectral indices used to describe forest condition.

Each function documents what the index actually measures and where it fails,
because an index applied outside its useful range is the most confident kind of
wrong number.
"""

from __future__ import annotations

import xarray as xr


def _normalised_difference(a: xr.DataArray, b: xr.DataArray) -> xr.DataArray:
    denominator = a + b
    return xr.where(denominator == 0, float("nan"), (a - b) / denominator)


def ndvi(ds: xr.Dataset, red: str = "B04", nir: str = "B08") -> xr.DataArray:
    """Normalised difference vegetation index: greenness.

    Well understood and robust. Saturates in closed canopy, so it separates
    forest from non-forest reliably and separates one mature stand from another
    poorly. Use it as a gate, not as a discriminator.
    """
    out = _normalised_difference(ds[nir], ds[red])
    out.name = "ndvi"
    return out


def ndmi(ds: xr.Dataset, nir: str = "B08", swir1: str = "B11") -> xr.DataArray:
    """Normalised difference moisture index: canopy water content.

    Drops under drought stress and after canopy removal. This is the index that
    most needs the reflectance scale factor applied, because the thresholds are
    absolute rather than relative.
    """
    out = _normalised_difference(ds[nir], ds[swir1])
    out.name = "ndmi"
    return out


def nbr(ds: xr.Dataset, nir: str = "B08", swir2: str = "B12") -> xr.DataArray:
    """Normalised burn ratio: sensitive to fire and to harvest.

    Both remove canopy and expose soil and slash, so a large drop between two
    dates is the primary harvest signal in this pipeline. It cannot tell you
    which of the two happened; that is what the change type and the review queue
    are for.
    """
    out = _normalised_difference(ds[nir], ds[swir2])
    out.name = "nbr"
    return out


def evi(ds: xr.Dataset, red: str = "B04", nir: str = "B08", blue: str | None = None) -> xr.DataArray:
    """Enhanced vegetation index, two-band form when blue is unavailable.

    Saturates later than NDVI in dense canopy, which is where most of the
    interesting variation in a managed forest sits. The two-band form drops the
    aerosol correction, which is acceptable on Level 2A data that has already
    been atmospherically corrected.
    """
    nir_band = ds[nir]
    red_band = ds[red]
    if blue and blue in ds:
        out = 2.5 * (nir_band - red_band) / (nir_band + 6 * red_band - 7.5 * ds[blue] + 1)
    else:
        out = 2.5 * (nir_band - red_band) / (nir_band + 2.4 * red_band + 1)
    out.name = "evi"
    return out


def all_indices(ds: xr.Dataset) -> xr.Dataset:
    """Compute every index used by the classifier as one dataset.

    Expects scaled reflectance. Passing raw integers produces an NDVI that looks
    entirely reasonable and an NDMI that is quietly meaningless, which is the
    exact failure the Session 2 Copilot exercise is built around.
    """
    _assert_scaled(ds)
    return xr.Dataset(
        {
            "ndvi": ndvi(ds),
            "ndmi": ndmi(ds),
            "nbr": nbr(ds),
            "evi": evi(ds),
        }
    )


def _assert_scaled(ds: xr.Dataset, band: str = "B08") -> None:
    """Fail loudly when reflectance has not been scaled.

    Surface reflectance lives between roughly 0 and 1. Values in the thousands
    mean the scale factor was skipped.
    """
    if band not in ds:
        return
    try:
        peak = float(ds[band].max().values)
    except Exception:  # pragma: no cover - lazy arrays without a computed max
        return
    if peak > 10.0:
        raise ValueError(
            f"{band} peaks at {peak:.0f}, which means reflectance was not scaled. "
            "Divide by 10000 before computing indices, or NDMI and EVI thresholds will be wrong "
            "while NDVI looks perfectly fine."
        )
