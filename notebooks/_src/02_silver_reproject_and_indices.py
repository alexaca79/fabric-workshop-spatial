# %% [markdown]
# # Lab 02 - Analyse masking, reprojection and spectral indices
#
# **Session 2, Step 2.** This is the block where Copilot writes most of the code
# and you find what it assumed. By the end you have one row per stand per scene
# date, in the New Brunswick projection, with the pixel accounting needed to know
# which rows to trust.
#
# ## What silver promises
#
# Comparability. Two scenes from different dates, possibly different UTM zones,
# must produce numbers that sit in the same column and can be compared without a
# footnote.
#
# ```
# raw scenes (native UTM, integer reflectance, cloud included)
#      |  mask cloud and shadow from SCL
#      |  scale integers to reflectance
#      |  reproject once to EPSG:2953
#      |  compute NDVI, NDMI, NBR, EVI
#      |  zonal statistics per stand
#      v
# silver_stand_observations   grain: stand_id x scene_date
# ```
#
# ## How to work with Copilot in this notebook
#
# Prompt with intent and constraints, not syntax. Then read the answer with one
# question in mind: **what did it assume that I did not tell it?**
#
# Three assumptions worth catching today:
#
# | Assumption | What breaks | Why you will not notice |
# |---|---|---|
# | Reflectance is already scaled | NDMI and EVI thresholds | NDVI is a ratio, so the scale cancels and it looks fine |
# | Zero means nodata | Valid dark pixels deleted | Shadowed forest quietly disappears, biasing every index up |
# | An approximate SCL class list | Thin cirrus survives | Cirrus depresses NDMI, which reads as drought stress |

# %% [markdown]
# ## Step 0 · Confirm the Environment and shared lakehouse
#
# Attach `env_forestops` and the `lh_woodlands` lakehouse from the ribbon.
#
# This notebook reads the Bronze tables and saved imagery written by Labs 00 and
# 01 in your own default lakehouse. Both input routes use this same handoff.
# It never searches or downloads replacement imagery.

# %%
def require_environment(packages):
    """Fail immediately, and legibly, if the Environment is not attached."""
    import importlib

    missing = []
    for name in packages:
        try:
            importlib.import_module(name)
        except ImportError:
            missing.append(name)

    if missing:
        raise RuntimeError(
            f"Missing packages: {', '.join(missing)}. Attach the 'env_forestops' "
            "Environment from the notebook ribbon, then restart the session."
        )
    print(f"environment OK ({len(packages)} packages available)")

require_environment([
    "geopandas", "rioxarray", "rasterio", "xarray", "zarr",
])

# %% [markdown]
# ## Step 1 · Configuration and inputs

# %%
import json
import os

import geopandas as gpd
import numpy as np
import pandas as pd
import xarray as xr
from pyspark.sql import SparkSession

spark = SparkSession.builder.getOrCreate()

AOI_NAME = "central-nb-block-a"
AOI_BBOX = (-66.90, 46.10, -66.40, 46.40)

CRS_WGS84 = 4326
CRS_ANALYSIS = 2953

BANDS = ("B04", "B08", "B11", "B12", "SCL")
REFLECTANCE_SCALE = 10_000.0

# Scene classification values to remove. From the Sentinel-2 L2A product
# definition. Getting one of these wrong leaves cloud in the data.
SCL_INVALID = (
    0,   # no data
    1,   # saturated or defective
    2,   # dark area pixels
    3,   # cloud shadow
    8,   # cloud, medium probability
    9,   # cloud, high probability
    10,  # thin cirrus
    11,  # snow or ice
)

MIN_VALID_PIXEL_FRACTION = 0.60

# --- Medallion layer --------------------------------------------------------
# Writes Silver tables while reading Bronze by plain table name from the shared
# lab lakehouse.
LAYER = "silver"
WORKSPACE = "jdi-training"
LAKEHOUSE = "lh_woodlands"

TABLE_STAND_REGISTER = "bronze_stand_register"
TABLE_SCENE_CATALOG = "bronze_scene_catalog"
TABLE_OBSERVATIONS = "silver_stand_observations"    # written here

BRONZE_SCENE_ROOT = f"/lakehouse/default/Files/bronze/scenes/{AOI_NAME}"

def report(name, ok, detail=""):
    print(f"[{'PASS' if ok else 'FAIL'}] {name:<42} {detail}")

# %% [markdown]
# ## Step 2 · Load the stand register
#
# Reverse of the write in notebook 00. WKB back to geometry, srid back to CRS.

# %%
from shapely import wkb

def load_stand_register(table):
    pdf = spark.table(table).toPandas()
    srids = pdf["srid"].dropna().unique()
    if len(srids) > 1:
        raise ValueError(f"register mixes CRS values {sorted(srids)}")
    geometry = [wkb.loads(bytes(v)) if v is not None else None for v in pdf["geometry_wkb"]]
    return gpd.GeoDataFrame(pdf.drop(columns=["geometry_wkb"]), geometry=geometry, crs=int(srids[0]))

stands = load_stand_register(TABLE_STAND_REGISTER)
print(f"{len(stands)} stands, CRS EPSG:{stands.crs.to_epsg()}")
report("register loaded", len(stands) > 0)
report("register is in the analysis CRS", stands.crs.to_epsg() == CRS_ANALYSIS)

# %% [markdown]
# ## Step 3 · Load the imagery
#
# Load the persisted dataset from Lab 01, including its input route and scene IDs.
# A recycled Spark session does not remove lakehouse files. If the dataset is
# missing or incomplete, finish Lab 01 in this same lakehouse first.

# %%
def restore_crs(ds):
    """Put back the CRS that the Zarr round trip quietly dropped.

    xarray writes `spatial_ref` as a plain data variable rather than a
    coordinate, and rioxarray only looks in `.coords`, so a reloaded cube
    reports no CRS even though every projection attribute is still sitting
    there intact. Promote it back, and fall back to the EPSG that notebook 01
    recorded on the dataset if anything else went missing.
    """
    if "spatial_ref" in ds.data_vars:
        ds = ds.set_coords("spatial_ref")
    if ds.rio.crs is None and "crs_epsg" in ds.attrs:
        ds = ds.rio.write_crs(f"EPSG:{ds.attrs['crs_epsg']}")
    return ds

try:
    raw = restore_crs(xr.open_zarr(f"{BRONZE_SCENE_ROOT}/_session_cache.zarr"))
    if raw.rio.crs is None:
        raise ValueError("session cache has no recoverable CRS")
    if raw.attrs.get("input_mode") not in {"manual", "stac"} or not raw.attrs.get("scene_ids"):
        raise ValueError("saved imagery has no verified source provenance")
    if raw.attrs.get("aoi_bbox") != list(AOI_BBOX) or not set(BANDS).issubset(raw.data_vars):
        raise ValueError("saved imagery does not match this area's five required bands")
    print(f"Loaded session cache: {raw.sizes.get('time')} dates, CRS {raw.rio.crs}")
except (OSError, ValueError, KeyError) as exc:
    raise RuntimeError("Bronze imagery is missing or invalid. Complete Lab 01 in this default lakehouse; no online fallback was attempted.") from exc

print(f"Input route: {raw.attrs['input_mode']}; source scenes: {raw.attrs['scene_ids']}")
print(f"native CRS: {raw.rio.crs}")
print(f"dates: {[str(t)[:10] for t in raw.time.values]}")

# %% [markdown]
# ## Step 4 · Mask cloud, shadow and snow
#
# The scene classification layer is a per-pixel class raster shipped with every
# Level 2A scene. Masked pixels become `NaN`, not zero.
#
# **Why not zero.** Zero is a legitimate reflectance value in deep shadow. Using
# it as a sentinel deletes valid dark pixels and biases every index upward, and
# nothing downstream can tell the difference between "dark forest" and "removed".

# %%
def mask_invalid(ds, scl_band="SCL", invalid=SCL_INVALID):
    """Mask cloud, shadow, snow and defective pixels using the SCL band."""
    #@todo Raise a KeyError if the SCL band is missing, rather than skipping masking silently
    #@todo Build a boolean keep mask: pixels whose SCL value is NOT in invalid
    #@todo Drop the SCL variable and apply the mask with .where(keep)
    #@todo Attach the keep mask back as a valid_mask variable so pixel accounting is possible later
    #@todo Return the masked dataset
    #@hint ds["SCL"].isin(list(invalid)) gives you the invalid pixels; you want the inverse
    #@hint .where(keep) sets everything else to NaN, which is what you want
    #@stub return ds
#@solution
    if scl_band not in ds:
        raise KeyError(f"{scl_band} not present; cloud masking cannot be skipped silently")

    scl = ds[scl_band]
    keep = ~scl.isin(list(invalid))

    masked = ds.drop_vars(scl_band).where(keep)
    masked = masked.assign_attrs(ds.attrs)
    masked["valid_mask"] = keep
    return masked
#@end

masked = mask_invalid(raw)
kept = float(masked["valid_mask"].mean().compute())
print(f"{kept:.1%} of pixels survived masking")
report("SCL removed from data variables", "SCL" not in masked.data_vars)
report("valid_mask retained", "valid_mask" in masked)
report("some pixels survived", kept > 0.05, f"{kept:.1%} kept")
if kept < 0.30:
    print("      Fewer than 30% of pixels usable. Widen the date range or accept")
    print("      that this period cannot be reported on. That is a real answer.")

# %% [markdown]
# ## Step 5 · The scale factor
#
# Sentinel-2 Level 2A stores surface reflectance as integers. Divide by 10000.
#
# This is the assumption Copilot most often omits, and the failure is subtle
# enough to survive a code review. Run the cell below before fixing it, and look
# at the numbers.

# %%
print("Before scaling:")
print(f"  B08 range: {float(raw['B08'].min().compute()):.0f} to {float(raw['B08'].max().compute()):.0f}")
print("  Surface reflectance is physically bounded between 0 and 1.")
print("  Those are integers, not reflectance.\n")

def scale_reflectance(ds, scale=REFLECTANCE_SCALE):
    """Convert integer surface reflectance to the 0 to 1 range."""
    #@todo Copy the dataset
    #@todo For every data variable except valid_mask, cast to float32 and divide by scale
    #@todo Return the scaled dataset
    #@hint Do not scale valid_mask. It is a boolean, and dividing it by 10000 is not helpful.
    #@stub return ds
#@solution
    out = ds.copy()
    for band in [v for v in ds.data_vars if v != "valid_mask"]:
        out[band] = ds[band].astype("float32") / scale
    return out
#@end

scaled = scale_reflectance(masked)
peak = float(scaled["B08"].max().compute())
print(f"After scaling:\n  B08 peak: {peak:.3f}")
report("reflectance is in the 0 to 1 range", peak <= 1.5, f"peak {peak:.3f}")

# %% [markdown]
# ### Why NDVI hides this bug
#
# NDVI is `(NIR - Red) / (NIR + Red)`. Scale both bands by the same factor and it
# cancels exactly. NDMI has the same form, so it also cancels. The damage is done
# by the **thresholds**: an NDMI cut-off of 0.18 means one thing on scaled data
# and nothing at all on unscaled data.
#
# Anywhere you compare an index against an absolute number, the scale matters.

# %%
unscaled_ndvi = (raw["B08"] - raw["B04"]) / (raw["B08"] + raw["B04"])
scaled_ndvi = (scaled["B08"] - scaled["B04"]) / (scaled["B08"] + scaled["B04"])
difference = float(np.abs(unscaled_ndvi - scaled_ndvi).max().compute())
print(f"Maximum NDVI difference between scaled and unscaled inputs: {difference:.2e}")
print("Effectively zero. The bug is invisible in NDVI and fatal in every threshold.")

# %% [markdown]
# ## Step 6 · Reproject, once
#
# Everything downstream works in EPSG:2953. Reprojecting once, here, is what
# stops two reports disagreeing because they resampled differently.
#
# Continuous reflectance uses bilinear resampling. A categorical raster would
# need nearest, because the average of class 4 and class 8 is not class 6.

# %%
from rasterio.enums import Resampling

def reproject(ds, target_epsg=CRS_ANALYSIS):
    """Reproject a raster dataset to the analysis CRS."""
    #@todo Raise a ValueError if the dataset has no CRS
    #@todo Return the dataset unchanged if it is already in the target CRS
    #@todo Otherwise reproject with rio.reproject and bilinear resampling
    #@hint ds.rio.reproject(f"EPSG:{target_epsg}", resampling=Resampling.bilinear)
    #@stub return ds
#@solution
    if ds.rio.crs is None:
        raise ValueError("raster has no CRS; a missing CRS here means spatial metadata was lost upstream")
    if ds.rio.crs.to_epsg() == target_epsg:
        return ds
    return ds.rio.reproject(f"EPSG:{target_epsg}", resampling=Resampling.bilinear)
#@end

projected = reproject(scaled.drop_vars("valid_mask"))
print(f"before: {scaled.rio.crs}")
print(f"after:  {projected.rio.crs}")
report("raster is in the analysis CRS", projected.rio.crs.to_epsg() == CRS_ANALYSIS)
report("raster and stands now agree", projected.rio.crs.to_epsg() == stands.crs.to_epsg())

# %% [markdown]
# ## Step 7 · Composite the time stack
#
# Several dates collapse to one value per pixel. Use the **median**, not the
# mean.
#
# Residual cloud that survived masking is bright and one-sided. It drags a mean
# upward while barely moving a median. This one word is the cheapest defence
# against an imperfect cloud mask that exists.

# %%
#@todo Collapse the time dimension with a median, skipping NaN and keeping attributes
#@hint projected.median(dim="time", skipna=True, keep_attrs=True)
#@stub composite = projected.isel(time=0)
#@solution
composite = projected.median(dim="time", skipna=True, keep_attrs=True)
#@end

composite = composite.rio.write_crs(CRS_ANALYSIS)
print(f"composited {projected.sizes.get('time', 1)} dates to a single grid")
report("time dimension collapsed", "time" not in composite.dims)
report("CRS retained through compositing", composite.rio.crs.to_epsg() == CRS_ANALYSIS)

# %% [markdown]
# ## Step 8 · Spectral indices
#
# This is the cell to hand to Copilot. Prompt it with the intent, then read the
# answer against the table at the top of this notebook.
#
# | Index | Formula | Measures | Fails when |
# |---|---|---|---|
# | NDVI | `(B08 - B04) / (B08 + B04)` | Greenness | Saturates in closed canopy |
# | NDMI | `(B08 - B11) / (B08 + B11)` | Canopy moisture | Unscaled input moves every threshold |
# | NBR | `(B08 - B12) / (B08 + B12)` | Canopy removal | Cannot separate harvest from windthrow |
# | EVI | `2.5(B08 - B04) / (B08 + 2.4·B04 + 1)` | Greenness, less saturating | Needs scaled reflectance to mean anything |

# %%
def normalised_difference(a, b):
    """Guarded normalised difference. Division by zero becomes NaN, not infinity."""
    denominator = a + b
    return xr.where(denominator == 0, np.nan, (a - b) / denominator)

def all_indices(ds):
    """Compute NDVI, NDMI, NBR and EVI from scaled reflectance."""
    #@todo Guard against unscaled input: raise if B08 peaks above 10
    #@todo Compute ndvi from B08 and B04 using normalised_difference
    #@todo Compute ndmi from B08 and B11
    #@todo Compute nbr from B08 and B12
    #@todo Compute the two-band evi: 2.5 * (nir - red) / (nir + 2.4 * red + 1)
    #@todo Return them as a single xr.Dataset with keys ndvi, ndmi, nbr, evi
    #@hint The guard is what turns a silent wrong answer into a loud one
    #@stub return xr.Dataset()
#@solution
    peak = float(ds["B08"].max().compute())
    if peak > 10.0:
        raise ValueError(
            f"B08 peaks at {peak:.0f}. Reflectance was not scaled; divide by 10000 first. "
            "NDVI would look fine and every NDMI threshold would be wrong."
        )

    nir, red, swir1, swir2 = ds["B08"], ds["B04"], ds["B11"], ds["B12"]
    return xr.Dataset({
        "ndvi": normalised_difference(nir, red),
        "ndmi": normalised_difference(nir, swir1),
        "nbr": normalised_difference(nir, swir2),
        "evi": 2.5 * (nir - red) / (nir + 2.4 * red + 1),
    })
#@end

indices = all_indices(composite).rio.write_crs(CRS_ANALYSIS)
for name in ("ndvi", "ndmi", "nbr", "evi"):
    values = indices[name].values
    finite = values[np.isfinite(values)]
    print(f"  {name:<5} {finite.min():6.3f} to {finite.max():6.3f}   median {np.median(finite):6.3f}")

report("all four indices computed", set(indices.data_vars) == {"ndvi", "ndmi", "nbr", "evi"})
in_range = all(
    np.nanmin(indices[n].values) >= -1.001 and np.nanmax(indices[n].values) <= 1.001
    for n in ("ndvi", "ndmi", "nbr")
)
report("normalised indices within -1 to 1", in_range)

# %% [markdown]
# ### Look at them

# %%
import matplotlib.pyplot as plt

fig, axes = plt.subplots(1, 3, figsize=(17, 5))
for ax, (name, cmap, limits) in zip(
    axes,
    [("ndvi", "RdYlGn", (0, 1)), ("ndmi", "BrBG", (-0.3, 0.6)), ("nbr", "RdYlGn", (-0.2, 0.8))],
):
    indices[name].plot(ax=ax, cmap=cmap, vmin=limits[0], vmax=limits[1])
    ax.set_title(name.upper())
    ax.set_xlabel("")
    ax.set_ylabel("")
plt.suptitle(f"{AOI_NAME} · composite indices · EPSG:{CRS_ANALYSIS}")
plt.tight_layout()
plt.show()

# %% [markdown]
# Read the NDMI panel next to the NDVI panel. NDVI is close to uniform across
# mature forest because it saturates. NDMI shows structure that NDVI cannot,
# which is exactly why the classifier uses NDMI to separate species groups.

# %% [markdown]
# ## Step 9 · Zonal statistics
#
# The step that turns raster into rows. From here on, the data is joinable to
# everything else Woodlands holds.
#
# Two things to get right. Align the CRS before clipping, or every stand returns
# `NaN` with no error. And carry the pixel accounting, or you will publish a
# confident NDVI computed from the four pixels that were not cloud.

# %%
def zonal_stats(index_ds, stand_frame, percentiles=(10, 90)):
    """Summarise every index within every stand boundary."""
    #@todo Raise a ValueError if the raster and the stands are in different CRS values
    #@hint Mismatched CRS gives NaN for every stand and no error. Fail loudly instead.
    #@stub pass
#@solution
    if stand_frame.crs is None or index_ds.rio.crs is None:
        raise ValueError("both the raster and the stands must declare a CRS before zonal statistics")
    if index_ds.rio.crs.to_epsg() != stand_frame.crs.to_epsg():
        raise ValueError(
            f"raster is EPSG:{index_ds.rio.crs.to_epsg()} and stands are EPSG:{stand_frame.crs.to_epsg()}; "
            "align them first, or every stand returns NaN with no error"
        )
#@end

    index_names = list(index_ds.data_vars)
    records = []

    for _, stand in stand_frame.iterrows():
        #@todo Clip index_ds to this stand's geometry, catching the case where it falls outside the raster
        #@todo For each index, ravel the values, keep only the finite ones
        #@todo Record <index>_mean and <index>_p10 / <index>_p90 for each index
        #@todo Record pixel_count, valid_pixel_count and valid_pixel_fraction
        #@hint index_ds.rio.clip([stand.geometry], crs=stand_frame.crs, drop=True, all_touched=False)
        #@hint A stand outside the window is a real outcome. Record it with zero pixels rather than skipping it.
        #@stub records.append({"stand_id": stand["stand_id"]})
#@solution
        record = {"stand_id": stand["stand_id"]}
        try:
            clipped = index_ds.rio.clip([stand.geometry], crs=stand_frame.crs, drop=True, all_touched=False)
        except Exception:
            for name in index_names:
                record[f"{name}_mean"] = np.nan
                for p in percentiles:
                    record[f"{name}_p{p}"] = np.nan
            record.update(pixel_count=0, valid_pixel_count=0, valid_pixel_fraction=0.0)
            records.append(record)
            continue

        total = valid = 0
        for name in index_names:
            values = clipped[name].values.ravel()
            finite = values[np.isfinite(values)]
            total = max(total, values.size)
            valid = max(valid, finite.size)
            if finite.size == 0:
                record[f"{name}_mean"] = np.nan
                for p in percentiles:
                    record[f"{name}_p{p}"] = np.nan
                continue
            record[f"{name}_mean"] = float(np.mean(finite))
            for p in percentiles:
                record[f"{name}_p{p}"] = float(np.percentile(finite, p))

        record["pixel_count"] = int(total)
        record["valid_pixel_count"] = int(valid)
        record["valid_pixel_fraction"] = float(valid / total) if total else 0.0
        records.append(record)
#@end

    return pd.DataFrame.from_records(records)

stats = zonal_stats(indices, stands)
print(f"{len(stats)} stand rows produced")
stats.head()

# %% [markdown]
# ### Why the 90th percentile, not just the mean
#
# A stand with a shadowed north edge has pixels that say nothing about the
# canopy. They drag the mean down by an amount that varies with the sun angle,
# which varies with the date. The 90th percentile is far more stable across
# dates, which is what makes a change detection between two months meaningful.

# %%
comparison = stats[["stand_id", "ndvi_mean", "ndvi_p90", "valid_pixel_fraction"]].copy()
comparison["gap"] = comparison["ndvi_p90"] - comparison["ndvi_mean"]
print(f"Median gap between NDVI p90 and NDVI mean: {comparison['gap'].median():.3f}")
print("That gap is shadow, edge pixels and gaps in the canopy. It is not noise,")
print("and it moves with the season, which is why the classifier uses p90.")
comparison.nlargest(5, "gap")

# %% [markdown]
# ## Step 10 · Attach stand attributes and write silver

# %%
scene_date = pd.to_datetime(str(raw.time.values[0])[:10]).date()
scene_ids = ",".join(raw.attrs["scene_ids"])

attributes = stands[["stand_id", "licence_block", "species_group", "planted_year", "management_regime"]].copy()
attributes["area_ha"] = stands.geometry.area.to_numpy() / 10_000.0

#@todo Merge stats with attributes on stand_id, validating one_to_one
#@todo Add scene_date, a scene_ids column, and srid = CRS_ANALYSIS
#@hint validate="one_to_one" turns a silent fan-out into an immediate error
#@stub observations = stats
#@solution
observations = stats.merge(attributes, on="stand_id", how="left", validate="one_to_one")
observations["scene_date"] = scene_date
observations["scene_ids"] = scene_ids
observations["srid"] = CRS_ANALYSIS
#@end

print(f"{len(observations)} rows, {len(observations.columns)} columns")
observations.head(3)

# %%
#@todo Write observations to TABLE_OBSERVATIONS as Delta, overwriting with overwriteSchema
#@hint spark.createDataFrame(observations) then the usual Delta write
#@stub pass
#@solution
(
    spark.createDataFrame(observations).write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(TABLE_OBSERVATIONS)
)
#@end

print(f"{TABLE_OBSERVATIONS}: {spark.table(TABLE_OBSERVATIONS).count()} rows")

# %% [markdown]
# ## Step 11 · The quality gate
#
# This is what stops a bad month reaching a report that someone acts on. Run it
# before you go anywhere near gold.

# %%
def quality_gate(df, expected_stands, min_trusted_fraction=0.70):
    results = []

    results.append(("observations present", not df.empty, f"{len(df)} rows"))

    duplicates = int(df.duplicated(subset=["stand_id", "scene_date"]).sum())
    results.append(("grain is unique", duplicates == 0, f"{duplicates} duplicates"))

    trusted = df[df["valid_pixel_fraction"] >= MIN_VALID_PIXEL_FRACTION]["stand_id"].nunique()
    fraction = trusted / expected_stands if expected_stands else 0
    results.append((
        "trusted stand coverage",
        fraction >= min_trusted_fraction,
        f"{trusted}/{expected_stands} ({fraction:.0%}), floor {min_trusted_fraction:.0%}",
    ))

    offenders = []
    for col in [c for c in df.columns if c.startswith(("ndvi", "ndmi", "nbr"))]:
        series = df[col].dropna()
        if not series.empty and (series.min() < -1.001 or series.max() > 1.001):
            offenders.append(f"{col} [{series.min():.2f}, {series.max():.2f}]")
    results.append(("index values in range", not offenders, "; ".join(offenders) or "all within -1 to 1"))

    areas = df["area_ha"].dropna()
    bad_area = int(((areas < 0.5) | (areas > 5000)).sum())
    results.append((
        "stand areas plausible",
        bad_area == 0,
        f"{bad_area} outside 0.5 to 5000 ha, range {areas.min():.1f} to {areas.max():.1f}",
    ))

    return results

gate = quality_gate(observations, expected_stands=len(stands))
for name, ok, detail in gate:
    report(name, ok, detail)

gate_open = all(ok for _, ok, _ in gate)
print()
print("Gate open, silver is publishable." if gate_open
      else "GATE CLOSED. Do not build gold on this. Fix the failures above first.")

# %% [markdown]
# ## Checkpoint
#
# You are done when `silver_stand_observations` exists at the stand and
# scene-date grain, and the quality gate is open.
#
# ## The three Copilot assumptions, revisited
#
# Go back and check which of these your generated code got right first time:
#
# 1. Did it apply the reflectance scale factor?
# 2. Did it treat zero as nodata?
# 3. Did it use the correct SCL class list, including 10 for thin cirrus?
#
# The lesson is not that Copilot is unreliable. It is that it answers the
# question you asked, and geospatial work is full of questions people ask
# imprecisely. State the CRS, state the scale, state the nodata convention, and
# the same prompt gets it right.
#
# **Next:** `03_gold_forest_classification` turns these numbers into classes.
