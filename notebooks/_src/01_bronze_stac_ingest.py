# %% [markdown]
# # Lab 01 - Import Planetary Computer imagery
#
# Choose one route in Step 1. Both produce the same Bronze catalogue, native-CRS
# imagery and saved dataset for Lab 02.
#
# - `manual` (default): download one Sentinel-2 L2A scene's original `B04`, `B08`,
#   `B11`, `B12` and `SCL` TIFFs plus its STAC Item JSON, then upload them to Files.
# - `stac`: search and read Planetary Computer directly from this notebook.
#
# A JPG, PNG, thumbnail or rendered RGB GeoTIFF cannot replace the five analysis
# bands. Keep the original TIFF filenames and save the metadata as `item.json`.
# See the imagery-download handout before using manual mode.
#
# Bronze preserves integer pixels and source provenance. It aligns bands to a
# 20 m grid in their native CRS; masking, scaling and EPSG:2953 reprojection belong
# in Lab 02. Signed download URLs are never written to the catalogue.

# %% [markdown]
# ## Step 0 · Confirm the Environment is attached
#
# Attach the published `env_forestops` Environment and set your own lakehouse as
# default before running. The required packages are shared by both input routes.

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
    "pystac_client", "planetary_computer", "odc.stac",
    "rioxarray", "rasterio", "geopandas",
])

# %% [markdown]
# ## Step 1 · Configuration
#
# Same area of interest as notebook 00. If you changed it for the homework,
# change it here too.

# %%
import json
from datetime import datetime, timezone

AOI_NAME = "central-nb-block-a"
AOI_BBOX = (-66.90, 46.10, -66.40, 46.40)

DATE_START = "2026-06-01"
DATE_END = "2026-08-31"
MAX_CLOUD_COVER = 20.0
MAX_SCENES = 6
RESOLUTION_M = 20

COLLECTION = "sentinel-2-l2a"
BANDS = ("B04", "B08", "B11", "B12", "SCL")
INPUT_MODE = "manual"
MANUAL_SCENE_ROOT = f"/lakehouse/default/Files/bronze/manual/{AOI_NAME}"

if INPUT_MODE not in {"manual", "stac"}:
    raise ValueError('INPUT_MODE must be "manual" or "stac".')

# --- Medallion layer --------------------------------------------------------
# Writes Bronze tables and files to the shared lab lakehouse.
LAYER = "bronze"
WORKSPACE = "fabric-training"
LAKEHOUSE = "lh_woodlands"

TABLE_SCENE_CATALOG = "bronze_scene_catalog"
BRONZE_SCENE_ROOT = f"/lakehouse/default/Files/bronze/scenes/{AOI_NAME}"

PIPELINE_RUN_ID = f"run-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
print(f"pipeline_run_id = {PIPELINE_RUN_ID}")

# %% [markdown]
# ### Which bands and why
#
# | Asset | Wavelength | Resolution | Used for |
# |---|---|---|---|
# | `B04` | Red, 665 nm | 10 m | NDVI and EVI |
# | `B08` | Near infrared, 842 nm | 10 m | Every index. Vegetation structure. |
# | `B11` | Shortwave infrared, 1610 nm | 20 m | NDMI. Canopy moisture. |
# | `B12` | Shortwave infrared, 2190 nm | 20 m | NBR. Harvest and burn. |
# | `SCL` | Scene classification | 20 m | Cloud, shadow and snow masking |
#
# Loading at 20 m rather than 10 m costs nothing at stand scale and cuts the
# bytes by four. A 12 hectare stand is roughly 300 pixels at 20 m, which is more
# than enough for a stable median.

# %% [markdown]
# ## Step 2 - Prepare the selected route
#
# In manual mode, each scene folder contains `item.json` and its five TIFFs.
# This validation code is provided. Run the whole cell without changing it.
# The catalogue-opening TODO applies only to `stac` mode.

# %%
#@include manual_imagery.py
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from forestops.manual_imagery import read_manual_items, validate_scene_selection

STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"

if INPUT_MODE == "stac":
    import planetary_computer as pc
    import pystac_client

    #@todo Open STAC_URL with modifier=pc.sign_inplace and timeout=60
    #@hint Only the automatic route opens the remote catalogue.
    #@stub catalog = None
    #@solution
    catalog = pystac_client.Client.open(STAC_URL, modifier=pc.sign_inplace, timeout=60)
    #@end
    if catalog is None:
        raise RuntimeError("Complete the catalogue TODO for stac mode.")
else:
    print(f"Manual mode: reading uploaded files from {MANUAL_SCENE_ROOT}")

# %% [markdown]
# ## Step 3 - Select and validate scenes
#
# Manual mode validates the uploaded files without contacting Planetary Computer.
# The search-function TODO is needed only for `stac` mode. Both routes check area,
# dates, cloud cover and a common native CRS before any table is written.

# %%
def search_scenes(bbox, date_start, date_end, max_cloud, max_scenes):
    """Return the least cloudy scenes covering the area of interest."""
    #@todo Call catalog.search() with collections, bbox, datetime and an eo:cloud_cover query
    #@todo Materialise the results into a list
    #@todo Sort by the eo:cloud_cover property, ascending, defaulting missing values to 100
    #@todo Return the first max_scenes items
    #@hint datetime takes a single string, "2026-06-01/2026-08-31"
    #@hint query={"eo:cloud_cover": {"lt": max_cloud}}
    #@stub return []
#@solution
    search = catalog.search(
        collections=[COLLECTION],
        bbox=list(bbox),
        datetime=f"{date_start}/{date_end}",
        query={"eo:cloud_cover": {"lt": max_cloud}},
    )
    items = list(search.items())
    items.sort(key=lambda it: it.properties.get("eo:cloud_cover", 100.0))
    return items[:max_scenes]
#@end

if INPUT_MODE == "manual":
    items = read_manual_items(MANUAL_SCENE_ROOT)
else:
    items = search_scenes(AOI_BBOX, DATE_START, DATE_END, MAX_CLOUD_COVER, MAX_SCENES)
validate_scene_selection(items, AOI_BBOX, DATE_START, DATE_END, MAX_CLOUD_COVER, MAX_SCENES)
print(f"{len(items)} scenes selected\n")
for item in items:
    print(f"  {item.id}")
    print(f"    date  {item.properties['datetime'][:10]}   cloud {item.properties.get('eo:cloud_cover', 0):5.1f}%"
          f"   epsg {item.properties.get('proj:epsg', item.properties.get('proj:code', 'n/a'))}")

# %% [markdown]
# ### Validation
#
# Zero scenes is the most common outcome on the first attempt, and it is almost
# never a code problem. Work the list in order: bounding box order, longitude
# sign, date range, then cloud threshold.

# %%
def report(name, ok, detail=""):
    print(f"[{'PASS' if ok else 'FAIL'}] {name:<40} {detail}")

report("search returned scenes", len(items) > 0, f"{len(items)} items")
if not items:
    print("\n  Troubleshooting, in order:")
    print("   1. bbox order is west, south, east, north")
    print("   2. New Brunswick longitudes are negative, around -66")
    print("   3. widen DATE_START and DATE_END before touching the cloud filter")
    print("   4. raise MAX_CLOUD_COVER to 60 and rely on the ranking instead")
else:
    report("all scenes below the cloud threshold",
           all(i.properties.get("eo:cloud_cover", 100) < MAX_CLOUD_COVER for i in items))
    report("scenes are sorted by cloud cover",
           [i.properties.get("eo:cloud_cover", 100) for i in items]
           == sorted(i.properties.get("eo:cloud_cover", 100) for i in items))
    epsgs = {i.properties.get("proj:epsg", i.properties.get("proj:code")) for i in items}
    report("scene projections noted", True, f"native EPSG values: {epsgs}")
    if len(epsgs) > 1:
        print("      Scenes span more than one UTM zone. They must be reprojected")
        print("      before mosaicking, which silver handles. Note it now.")

# %% [markdown]
# ## Step 4 · Inspect one item
#
# Before loading anything, read what the catalogue is telling you. Every number
# you eventually publish traces back through this metadata.

# %%
sample = items[0]
print(f"id          {sample.id}")
print(f"collection  {sample.collection_id}")
print(f"datetime    {sample.properties['datetime']}")
print(f"platform    {sample.properties.get('platform')}")
print(f"cloud       {sample.properties.get('eo:cloud_cover')}%")
print(f"native crs  {sample.properties.get('proj:code', sample.properties.get('proj:epsg'))}")
print(f"\nassets available: {len(sample.assets)}")
for band in BANDS:
    asset = sample.assets[band]
    print(f"  {band:<5} {asset.media_type}")
    print(f"        {asset.href.split('?')[0]}")

# %% [markdown]
# ## Step 5 · Windowed read
#
# The same loader reads uploaded TIFFs in manual mode or signed remote assets in
# stac mode. Only the area of interest is loaded into the working dataset.
# A manual download still transfers the full original TIFFs to your computer.
#
# Note what is deliberately absent: no `crs` argument. Bronze does not
# reproject. That happens once, in silver.

# %%
import odc.stac

#@todo Load the selected items with odc.stac.load()
#@todo Pass bands=list(BANDS), bbox=list(AOI_BBOX), resolution=RESOLUTION_M
#@todo Use chunks={} for lazy loading and groupby="solar_day" to merge same-day tiles
#@hint Do not pass a crs argument. Reprojecting here would break the bronze contract.
#@stub raw = None
#@solution
raw = odc.stac.load(
    items,
    bands=list(BANDS),
    bbox=list(AOI_BBOX),
    resolution=RESOLUTION_M,
    chunks={},
    groupby="solar_day",
)
#@end

print(raw)

# %% [markdown]
# ### Validation

# %%
report("dataset loaded", raw is not None)
if raw is None:
    raise RuntimeError("Complete the windowed-load TODO before continuing.")
report("all requested bands present", set(BANDS).issubset(set(raw.data_vars)),
       f"{sorted(raw.data_vars)}")
report("dataset has a CRS", raw.rio.crs is not None, f"{raw.rio.crs}")
report("dataset has a time dimension", "time" in raw.dims, f"{raw.sizes.get('time', 0)} dates")
approx_mb = (raw.sizes.get("x", 0) * raw.sizes.get("y", 0) * raw.sizes.get("time", 1) * len(BANDS) * 2) / 1e6
report("window is a sensible size", approx_mb < 2000, f"about {approx_mb:.0f} MB uncompressed")
if approx_mb >= 2000:
    raise ValueError("Reduce the area or number of scenes before computing this dataset.")
raw.attrs.update({"input_mode": INPUT_MODE, "pipeline_run_id": PIPELINE_RUN_ID,
                  "scene_ids": [item.id for item in items], "aoi_bbox": list(AOI_BBOX)})

# %% [markdown]
# ## Step 6 · Look at it
#
# Always look at the imagery before trusting a number derived from it. Cloud,
# haze and a scene that only clips the corner of your block are all obvious to
# an eye and invisible in a summary statistic.

# %%
import matplotlib.pyplot as plt

first_date = raw.isel(time=0)
fig, axes = plt.subplots(1, 3, figsize=(16, 5))

first_date["B04"].plot(ax=axes[0], cmap="Reds", robust=True, add_colorbar=False)
axes[0].set_title("B04 red")

first_date["B08"].plot(ax=axes[1], cmap="Greens", robust=True, add_colorbar=False)
axes[1].set_title("B08 near infrared")

first_date["SCL"].plot(ax=axes[2], cmap="tab20", add_colorbar=True)
axes[2].set_title("SCL scene classification")

for ax in axes:
    ax.set_xlabel("")
    ax.set_ylabel("")
plt.suptitle(f"{AOI_NAME} · {str(raw.time.values[0])[:10]}")
plt.tight_layout()
plt.show()

# %% [markdown]
# The scene classification panel is the one to read carefully. Large blocks of a
# single colour over your stands mean cloud, and cloud is what silver has to
# remove before any index is worth computing.

# %% [markdown]
# ## Step 7 · Write the bronze scene catalogue
#
# One row per scene. This table is how you answer "where did this number come
# from" six months from now.
#
# Asset hrefs are stored **unsigned**. Strip the query string.

# %%
def scene_epsg(props):
    """Read the native EPSG code, whichever spelling the catalogue uses.

    The STAC projection extension moved from `proj:epsg`, an integer, to
    `proj:code`, a string like "EPSG:32619". Planetary Computer now emits the
    newer form, so reading only `proj:epsg` records a zero for every scene and
    quietly loses the one piece of provenance silver depends on.
    """
    epsg = props.get("proj:epsg")
    if epsg:
        return int(epsg)
    code = props.get("proj:code") or ""
    if code.upper().startswith("EPSG:"):
        return int(code.split(":", 1)[1])
    return 0

def scene_catalog_rows(stac_items, aoi_name, aoi_bbox, run_id):
    """Flatten STAC items into bronze catalogue rows."""
    ingested_at = datetime.now(timezone.utc)
    rows = []
    for item in stac_items:
        props = item.properties
        #@todo Store each asset's source_href when present, otherwise its href, without a query string
        #@hint The part after ? is the SAS token. Storing it creates a credential in a table.
        #@stub unsigned = {}
#@solution
        unsigned = {
            band: item.assets[band].extra_fields.get("source_href", item.assets[band].href).split("?", 1)[0]
            for band in BANDS if band in item.assets
        }
#@end

        #@todo Append a row with scene_id, collection, datetime_utc, cloud_cover_pct, epsg,
        #@todo platform, aoi_name, bbox_wgs84 as JSON, assets_json, ingested_at_utc, pipeline_run_id
        #@hint datetime.fromisoformat(value.replace("Z", "+00:00")) parses the STAC timestamp
        #@stub rows.append({"scene_id": item.id})
#@solution
        rows.append({
            "scene_id": item.id,
            "collection": item.collection_id,
            "datetime_utc": datetime.fromisoformat(props["datetime"].replace("Z", "+00:00")),
            "cloud_cover_pct": float(props.get("eo:cloud_cover", float("nan"))),
            "epsg": scene_epsg(props),
            "platform": props.get("platform", ""),
            "aoi_name": aoi_name,
            "bbox_wgs84": json.dumps(list(aoi_bbox)),
            "assets_json": json.dumps(unsigned),
            "input_mode": INPUT_MODE,
            "ingested_at_utc": ingested_at,
            "pipeline_run_id": run_id,
        })
#@end
    return rows

rows = scene_catalog_rows(items, AOI_NAME, AOI_BBOX, PIPELINE_RUN_ID)
print(f"{len(rows)} catalogue rows prepared")
print(json.dumps({k: str(v)[:70] for k, v in rows[0].items()}, indent=2))

# %% [markdown]
# ### Bronze is append-only
#
# Every run appends with a new `pipeline_run_id`. Overwriting bronze destroys
# the ability to explain a number published last month, which is the entire
# reason the layer exists.

# %%
import pandas as pd
from pyspark.sql import SparkSession

spark = SparkSession.builder.getOrCreate()

#@todo Create a Spark DataFrame from the rows via pandas
#@todo Append it to TABLE_SCENE_CATALOG as Delta with mergeSchema enabled
#@hint .write.format("delta").mode("append").option("mergeSchema", "true").saveAsTable(...)
#@stub pass
#@solution
catalog_sdf = spark.createDataFrame(pd.DataFrame(rows))
(
    catalog_sdf.write
    .format("delta")
    .mode("append")
    .option("mergeSchema", "true")
    .saveAsTable(TABLE_SCENE_CATALOG)
)
#@end

total = spark.table(TABLE_SCENE_CATALOG).count()
this_run = spark.table(TABLE_SCENE_CATALOG).filter(f"pipeline_run_id = '{PIPELINE_RUN_ID}'").count()
print(f"{TABLE_SCENE_CATALOG}: {this_run} rows this run, {total} rows total")

# %% [markdown]
# ### Validation

# %%
catalogue = spark.table(TABLE_SCENE_CATALOG).toPandas()
report("catalogue populated", len(catalogue) > 0, f"{len(catalogue)} rows")
report("this run wrote rows", this_run == len(items), f"{this_run} of {len(items)}")
report("no signed hrefs stored",
       not catalogue["assets_json"].str.contains(r"\?", regex=True).any(),
       "asset URLs carry no SAS token")
report("run id present on every row", catalogue["pipeline_run_id"].notna().all())
report("cloud cover recorded", catalogue["cloud_cover_pct"].notna().all())
# A zero here means the projection extension changed spelling again and the
# catalogue has silently stopped recording the native CRS. Silver needs it.
this_run_rows = catalogue[catalogue["pipeline_run_id"] == PIPELINE_RUN_ID]
report("native projection recorded", (this_run_rows["epsg"] > 0).all(),
       f"EPSG values this run: {sorted(this_run_rows['epsg'].unique())}")

# %% [markdown]
# ## Step 8 · Persist the raw window to Files
#
# Bronze rasters let silver be re-derived without going back to the network,
# which matters when the question arrives months later and the token that
# fetched the original is long expired.

# %%
import os

os.makedirs(BRONZE_SCENE_ROOT, exist_ok=True)

#@todo For the first time slice, write each band in BANDS to BRONZE_SCENE_ROOT as a COG
#@todo Name each file "<scene_date>_<band>.tif"
#@hint slice_ds[band].rio.to_raster(path, driver="COG", compress="DEFLATE")
#@hint Call .compute() on the lazy array first, or the write will be slow and chatty
written = []
#@solution
slice_ds = raw.isel(time=0).compute()
scene_date = str(raw.time.values[0])[:10]
for band in BANDS:
    path = f"{BRONZE_SCENE_ROOT}/{scene_date}_{band}.tif"
    slice_ds[band].rio.to_raster(path, driver="COG", compress="DEFLATE")
    written.append(path)
#@end

for path in written:
    size_mb = os.path.getsize(path) / 1e6
    print(f"  {os.path.basename(path):<28} {size_mb:6.1f} MB")

report("raster files written", len(written) == len(BANDS), f"{len(written)} files")
report("files are non-empty", all(os.path.getsize(p) > 0 for p in written))

# %% [markdown]
# ## Step 9 · Hand off to silver
#
# The next notebook needs the loaded dataset. Keep it in memory if you are
# running straight through, or reload it from the bronze catalogue if the
# session recycled.

# %%
# Zarr does not round-trip a non-dimension coordinate as a coordinate. On read,
# `spatial_ref` comes back as an ordinary data variable, and rioxarray only looks
# for the CRS in `.coords`, so the reloaded cube reports no CRS at all. The
# attributes on spatial_ref do survive, so notebook 02 can promote it back, but
# record the EPSG on the dataset as well: it is one integer, it survives
# everything, and it turns a silent loss of spatial metadata into a fact.
raw.attrs["crs_epsg"] = raw.rio.crs.to_epsg()

raw.to_zarr(f"{BRONZE_SCENE_ROOT}/_session_cache.zarr", mode="w", consolidated=True, zarr_version=2)
print(f"Session cache written in EPSG:{raw.attrs['crs_epsg']}. Reload in notebook 02 with:")
print(f'  raw = xarray.open_zarr("{BRONZE_SCENE_ROOT}/_session_cache.zarr")')
print('  raw = raw.set_coords("spatial_ref")   # or the CRS is silently gone')

# %% [markdown]
# ## Checkpoint
#
# You are done when:
#
# - `bronze_scene_catalog` holds one to six scenes for this run, without signed URLs
# - The raster files exist under `Files/bronze/scenes/<AOI_NAME>/`
# - The Zarr dataset records the input route, source scene IDs, date and native CRS
# - You looked at the imagery and know how cloudy it is
#
# ## What bronze deliberately does not do
#
# No cloud masking, reflectance scaling, index calculation or reprojection into
# the analysis CRS. Those decisions remain in Silver.
#
# **Next:** `02_silver_reproject_and_indices` masks the cloud, fixes the
# projection and turns pixels into one row per stand.
