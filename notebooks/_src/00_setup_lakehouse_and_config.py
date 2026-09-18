# Notebook 00: Setup, configuration and the Woodlands stand register
# Session 1, hands-on block at 2:50. Budget 50 minutes.
#
# Authored in percent format. Run scripts/build_notebooks.py to produce the
# solution and student .ipynb files.

# %% [markdown]
# # 00 · Land a Woodlands dataset, reproject it, write a Delta table
#
# **Session 1, hands-on block.** By the end of this notebook you will have a
# Lakehouse containing a forest stand register, reprojected to the New Brunswick
# provincial coordinate system, stored as a Delta table that Spark, the SQL
# analytics endpoint and Power BI can all read.
#
# ## What you are building
#
# ```
# stand register (WGS84 degrees)
#         |
#         |  declare CRS, reproject to EPSG:2953, compute area in hectares
#         v
# bronze_stand_register  (Delta, geometry as WKB + srid)
# ```
#
# ## The three things that trip people up
#
# | Trap | What it looks like | Why it happens |
# |---|---|---|
# | Writing a `geometry` column to Delta | `AnalysisException: cannot resolve column 'geometry'` | Spark has no geometry type. Serialise to WKB. |
# | Calling `.to_crs()` on a frame with no CRS | `ValueError: Cannot transform naive geometries` | GeoPandas refuses to guess, which is correct behaviour. |
# | Computing area before reprojecting | Areas like `0.0004` | Square degrees. Plausible until someone checks a cruise sheet. |
#
# ## Before you start
#
# Two attachments, both from the notebook ribbon, both required.
#
# | Attach | Value | Why |
# |---|---|---|
# | Environment | `env_forestops` | Brings the geospatial stack, which the base runtime lacks |
# | Default lakehouse | `lh_bronze` in `jdi-mock-training-bronze` | Where this notebook writes |
#
# If either is missing, the next cell stops you rather than letting you find out
# forty minutes later.

# %% [markdown]
# ## Step 0 · Confirm the Environment is attached
#
# The geospatial libraries are not in the Fabric Spark base runtime. They arrive
# through the published `env_forestops` Environment.
#
# Do not reach for `%pip install` here. It reports success and then leaves a
# broken session: `planetary_computer` dies on a `typing_extensions` import, and
# pandas gets silently upgraded out from under the platform libraries. The full
# story is in docs/12-spark-environment.md.

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
            "Environment from the notebook ribbon, then restart the session. "
            "Do not %pip install them, see docs/12-spark-environment.md."
        )
    print(f"environment OK ({len(packages)} packages available)")


require_environment(["geopandas", "shapely", "pyproj"])

# %% [markdown]
# ## Step 1 · Configuration
#
# Every value the notebook needs lives in one place. When you move to your own
# operating area for the homework, this is the only cell you change.

# %%
import json
import math
from dataclasses import dataclass

# --- Area of interest -------------------------------------------------------
# Bounding box order is west, south, east, north. Getting this wrong is the most
# common cause of a STAC search that returns nothing in Session 2.
AOI_NAME = "central-nb-block-a"
AOI_BBOX = (-66.90, 46.10, -66.40, 46.40)

# --- Coordinate reference systems ------------------------------------------
CRS_WGS84 = 4326      # degrees. Search geometry and Power BI map points.
CRS_ANALYSIS = 2953   # NAD83(CSRS) New Brunswick Stereographic, in metres.

# --- Stand register ---------------------------------------------------------
# Synthetic stands keep the workshop runnable before anyone has access to
# production inventory. Flip this to False once you have the real register.
USE_SYNTHETIC_STANDS = True
SYNTHETIC_STAND_COUNT = 120
RANDOM_SEED = 20260902

# --- Medallion layer --------------------------------------------------------
# Bronze, silver and gold each get their own workspace, so a mistake in one
# layer cannot quietly overwrite another. This notebook writes to bronze.
LAYER = "bronze"
WORKSPACE = "jdi-mock-training-bronze"
LAKEHOUSE = "lh_bronze"
TABLE_STAND_REGISTER = "bronze_stand_register"

print(json.dumps({
    "aoi_name": AOI_NAME,
    "aoi_bbox": list(AOI_BBOX),
    "crs_analysis": CRS_ANALYSIS,
    "synthetic_stands": USE_SYNTHETIC_STANDS,
    "layer": LAYER,
    "workspace": WORKSPACE,
    "lakehouse": LAKEHOUSE,
}, indent=2))

# %% [markdown]
# ## Step 2 · Validate the bounding box before it costs you an hour
#
# A reversed bounding box does not raise an error anywhere in the stack. It
# quietly returns nothing, an hour later, in a different notebook.
#
# Write a check that fails immediately and says what is wrong.

# %%
def validate_bbox(bbox):
    """Raise a useful error if the bounding box is malformed."""
    #@todo Unpack the four values as west, south, east, north
    #@todo Raise a ValueError if west is not less than east, naming both values
    #@todo Raise a ValueError if south is not less than north, naming both values
    #@todo Raise a ValueError if longitudes fall outside -180 to 180
    #@todo Raise a ValueError if latitudes fall outside -90 to 90
    #@todo Return the bbox unchanged so the function can be used inline
    #@hint New Brunswick longitudes are around -66, not 66. A missing minus sign puts you in Mongolia.
    #@stub return bbox
    #@solution
    west, south, east, north = bbox
    if west >= east:
        raise ValueError(f"west {west} must be less than east {east}; the bbox order is W, S, E, N")
    if south >= north:
        raise ValueError(f"south {south} must be less than north {north}; the bbox order is W, S, E, N")
    if not (-180 <= west <= 180 and -180 <= east <= 180):
        raise ValueError(f"longitude out of range in {bbox}; New Brunswick is near -66, not 66")
    if not (-90 <= south <= 90 and -90 <= north <= 90):
        raise ValueError(f"latitude out of range in {bbox}")
    return bbox
    #@end


validate_bbox(AOI_BBOX)

# Approximate extent, so you know whether the area is a sensible size.
mid_lat = (AOI_BBOX[1] + AOI_BBOX[3]) / 2
width_km = (AOI_BBOX[2] - AOI_BBOX[0]) * 111.32 * abs(math.cos(math.radians(mid_lat)))
height_km = (AOI_BBOX[3] - AOI_BBOX[1]) * 110.57
print(f"Area of interest is roughly {width_km:.1f} km by {height_km:.1f} km")

# %% [markdown]
# ### Validation

# %%
checks = []
try:
    validate_bbox((-66.4, 46.1, -66.9, 46.4))  # east and west swapped
    checks.append(("rejects reversed longitude", False))
except ValueError:
    checks.append(("rejects reversed longitude", True))

try:
    validate_bbox((66.9, 46.1, 67.4, 46.4))  # positive longitude, wrong hemisphere
    checks.append(("accepts valid eastern hemisphere box", True))
except ValueError:
    checks.append(("accepts valid eastern hemisphere box", False))

try:
    validate_bbox((-66.9, 96.1, -66.4, 96.4))  # latitude out of range
    checks.append(("rejects impossible latitude", False))
except ValueError:
    checks.append(("rejects impossible latitude", True))

for name, ok in checks:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")

# %% [markdown]
# ## Step 3 · Build the stand register
#
# Real stands are irregular polygons that were surveyed, not drawn. The
# generator below builds a hexagonal tessellation and then jitters the vertices,
# which matters for one specific reason: a square grid stays square under a bad
# reprojection, so projection bugs become invisible.
#
# You are given the geometry generator. Your job is the attributes and the CRS.

# %%
import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Polygon, box


def hex_grid(bounds, spacing_m):
    """Hexagonal tessellation covering the bounds, in a projected CRS."""
    minx, miny, maxx, maxy = bounds
    r = spacing_m / math.sqrt(3)
    dx, dy = spacing_m, spacing_m * math.sqrt(3) / 2
    cells, row, y = [], 0, miny
    while y < maxy + dy:
        x = minx + (0.0 if row % 2 == 0 else dx / 2)
        while x < maxx + dx:
            cells.append(Polygon([
                (x + r * math.cos(math.radians(a)), y + r * math.sin(math.radians(a)))
                for a in range(0, 360, 60)
            ]))
            x += dx
        y += dy
        row += 1
    return cells


# %% [markdown]
# ### Your turn: build the register
#
# The area of interest is a box in degrees. The hexagon generator needs a
# projected coordinate system, because it works in metres. Getting from one to
# the other in the right order is the whole exercise.

# %%
def build_stand_register(aoi_bbox, n_stands=SYNTHETIC_STAND_COUNT, seed=RANDOM_SEED):
    rng = np.random.default_rng(seed)

    #@todo Create a single-row GeoDataFrame from the bbox using shapely's box(), with crs=CRS_WGS84
    #@todo Reproject that frame to CRS_ANALYSIS so the hexagon generator can work in metres
    #@hint gpd.GeoDataFrame(geometry=[box(*aoi_bbox)], crs=CRS_WGS84).to_crs(CRS_ANALYSIS)
    #@stub frame = None
    #@solution
    frame = gpd.GeoDataFrame(geometry=[box(*aoi_bbox)], crs=CRS_WGS84).to_crs(CRS_ANALYSIS)
    #@end

    minx, miny, maxx, maxy = frame.total_bounds
    area_m2 = (maxx - minx) * (maxy - miny)
    spacing = math.sqrt((area_m2 / max(n_stands * 1.6, 1)) * 2 / math.sqrt(3))

    #@todo Build the hexagon cells with hex_grid() and wrap them in a GeoDataFrame with crs=CRS_ANALYSIS
    #@todo Keep only the cells that intersect the area of interest polygon
    #@hint frame.geometry.iloc[0] is the area of interest polygon
    #@stub grid = None
    #@solution
    grid = gpd.GeoDataFrame(geometry=hex_grid((minx, miny, maxx, maxy), spacing), crs=CRS_ANALYSIS)
    grid = grid[grid.intersects(frame.geometry.iloc[0])].reset_index(drop=True)
    #@end

    # Jitter the vertices so the stands look surveyed rather than tessellated.
    jitter = spacing * 0.06
    grid["geometry"] = [
        Polygon([(x + rng.normal(0, jitter), y + rng.normal(0, jitter))
                 for x, y in geom.exterior.coords[:-1]])
        for geom in grid.geometry
    ]

    grid = grid[grid.geometry.is_valid & grid.within(frame.geometry.iloc[0])].reset_index(drop=True)
    if len(grid) < n_stands:
        raise ValueError(f"Only {len(grid)} valid interior cells are available for {n_stands} stands")
    keep = rng.choice(len(grid), size=n_stands, replace=False)
    grid = grid.iloc[sorted(keep)].reset_index(drop=True)

    n = len(grid)
    natural = rng.random(n) < 0.30

    #@todo Add a stable stand_id column, formatted like "CEN-00001"
    #@todo Add licence_block, drawn at random from LB-A through LB-F
    #@todo Add species_group, drawn from softwood, hardwood, mixedwood with probabilities 0.52, 0.28, 0.20
    #@todo Add planted_year as a nullable integer, null wherever natural is True
    #@todo Add management_regime: "natural" where natural is True, otherwise plantation or thinned
    #@hint pd.array(np.where(natural, None, years), dtype="Int64") gives you a nullable integer column
    #@stub grid["stand_id"] = [f"{AOI_NAME[:3].upper()}-{i:05d}" for i in range(1, n + 1)]
    #@solution
    grid["stand_id"] = [f"{AOI_NAME[:3].upper()}-{i:05d}" for i in range(1, n + 1)]
    grid["licence_block"] = rng.choice([f"LB-{c}" for c in "ABCDEF"], size=n)
    grid["species_group"] = rng.choice(["softwood", "hardwood", "mixedwood"], size=n, p=[0.52, 0.28, 0.20])
    planted = rng.integers(1968, 2023, size=n)
    grid["planted_year"] = pd.array(np.where(natural, None, planted), dtype="Int64")
    grid["management_regime"] = np.where(natural, "natural", rng.choice(["plantation", "thinned"], size=n))
    #@end

    #@todo Add area_ha, computed from the geometry
    #@hint The frame is already in EPSG:2953, so .area is in square metres. One hectare is 10,000 of them.
    #@stub grid["area_ha"] = None
    #@solution
    grid["area_ha"] = grid.geometry.area / 10_000.0
    #@end

    grid["source"] = "synthetic"
    return grid


stands = build_stand_register(AOI_BBOX)
print(f"{len(stands)} stands, CRS {stands.crs}")
stands.head()

# %% [markdown]
# ### Validation
#
# The area check is the one that matters. Stands between 5 and 500 hectares are
# plausible for managed forest. Numbers near zero mean you computed area in
# degrees; numbers in the tens of thousands mean you reprojected twice.

# %%
def report(name, ok, detail=""):
    print(f"[{'PASS' if ok else 'FAIL'}] {name:<38} {detail}")


report("register is not empty", len(stands) > 0, f"{len(stands)} stands")
report("CRS is the analysis projection", stands.crs is not None and stands.crs.to_epsg() == CRS_ANALYSIS,
       f"EPSG:{stands.crs.to_epsg() if stands.crs else None}")
report("stand_id is unique", stands["stand_id"].is_unique)
report("all expected columns present",
       {"stand_id", "licence_block", "species_group", "planted_year", "management_regime", "area_ha"}
       .issubset(stands.columns))
report("areas are plausible",
       bool(stands["area_ha"].between(5, 500).all()),
       f"{stands['area_ha'].min():.1f} to {stands['area_ha'].max():.1f} ha")
report("natural stands have no planting year",
       bool(stands.loc[stands.management_regime == "natural", "planted_year"].isna().all()))

# %% [markdown]
# ## Step 4 · The reprojection trap, demonstrated
#
# Run this cell and read the output before continuing. It is the fastest way to
# understand why the pipeline reprojects once, in silver, and stores the result.

# %%
in_degrees = stands.to_crs(CRS_WGS84)
first = in_degrees.iloc[[0]]

print("Same stand, two coordinate systems:\n")
print(f"  EPSG:4326  area = {first.geometry.area.iloc[0]:.10f}  (square degrees, meaningless)")
print(f"  EPSG:2953  area = {stands.iloc[[0]].geometry.area.iloc[0] / 10_000:.2f} hectares\n")

# The dangerous version: relabelling instead of transforming.
mislabelled = stands.copy()
mislabelled = mislabelled.set_crs(CRS_WGS84, allow_override=True)
print("set_crs() on already-projected data relabels without moving anything:")
print(f"  bounds now claim to be degrees: {[round(v, 1) for v in mislabelled.total_bounds]}")
print("  Those are metres wearing a degrees label. No error is raised. This is how")
print("  geometry ends up in the Gulf of Guinea.")

# %% [markdown]
# ## Step 5 · Write bronze as Delta
#
# Spark has no geometry type. Geometry travels as well-known binary, with the
# spatial reference identifier in its own column so that a consumer never has to
# guess what the numbers mean.

# %%
from pyspark.sql import SparkSession

spark = SparkSession.builder.getOrCreate()


def geodataframe_to_spark(gdf, spark_session):
    """Convert a GeoDataFrame to a Spark DataFrame with WKB geometry."""
    #@todo Raise a ValueError if gdf.crs is None, rather than writing geometry nobody can interpret
    #@todo Copy the frame and add a geometry_wkb column holding each geometry's .wkb
    #@todo Add an srid column holding gdf.crs.to_epsg()
    #@todo Drop the geometry column and convert to a plain pandas DataFrame
    #@todo Convert any Int64 nullable columns to object with None, so Arrow can serialise them
    #@todo Return spark_session.createDataFrame(frame)
    #@hint Pandas Int64 columns fail the Arrow conversion. planted_year is one of them.
    #@stub return None
    #@solution
    if gdf.crs is None:
        raise ValueError("GeoDataFrame has no CRS; declare it before writing to Delta")

    frame = gdf.copy()
    frame["geometry_wkb"] = frame.geometry.apply(lambda g: g.wkb if g is not None else None)
    frame["srid"] = gdf.crs.to_epsg()
    frame = pd.DataFrame(frame.drop(columns=["geometry"]))

    for column in frame.columns:
        if str(frame[column].dtype) == "Int64":
            frame[column] = frame[column].astype("object").where(frame[column].notna(), None)

    return spark_session.createDataFrame(frame)
    #@end


sdf = geodataframe_to_spark(stands, spark)
sdf.printSchema()

# %%
#@todo Write sdf to TABLE_STAND_REGISTER as Delta, overwriting, with overwriteSchema enabled
#@hint sdf.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(...)
#@stub pass
#@solution
(
    sdf.write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(TABLE_STAND_REGISTER)
)
#@end

print(f"Wrote {spark.table(TABLE_STAND_REGISTER).count()} rows to {TABLE_STAND_REGISTER}")

# %% [markdown]
# ## Step 6 · Read it back and prove the round trip
#
# A write that cannot be read back into the same geometry is not a write worth
# having. This is also the pattern every later notebook uses to load the
# register.

# %%
from shapely import wkb


def spark_to_geodataframe(sdf_in, wkb_col="geometry_wkb", srid_col="srid"):
    """Rebuild a GeoDataFrame from a Delta table, restoring the CRS."""
    #@todo Convert the Spark DataFrame to pandas
    #@todo Read the distinct srid values and raise if there is more than one
    #@todo Rebuild the geometry column with wkb.loads(bytes(value))
    #@todo Return a GeoDataFrame with the wkb column dropped and crs set from the srid
    #@hint A table mixing two CRS values puts geometry in two different places with no error.
    #@stub return None
    #@solution
    pdf = sdf_in.toPandas()
    srids = pdf[srid_col].dropna().unique()
    if len(srids) > 1:
        raise ValueError(f"table mixes spatial reference systems {sorted(srids)}; reproject before reading")
    geometry = [wkb.loads(bytes(v)) if v is not None else None for v in pdf[wkb_col]]
    return gpd.GeoDataFrame(pdf.drop(columns=[wkb_col]), geometry=geometry, crs=int(srids[0]))
    #@end


round_trip = spark_to_geodataframe(spark.table(TABLE_STAND_REGISTER))
print(f"{len(round_trip)} stands read back, CRS {round_trip.crs}")

# %% [markdown]
# ### Validation

# %%
report("row count survives the round trip", len(round_trip) == len(stands),
       f"{len(round_trip)} vs {len(stands)}")
report("CRS survives the round trip",
       round_trip.crs is not None and round_trip.crs.to_epsg() == CRS_ANALYSIS)
report("geometry survives the round trip",
       bool(round_trip.geometry.is_valid.all()), "all geometries valid")

original_area = stands.set_index("stand_id")["area_ha"].sort_index()
returned_area = round_trip.assign(recomputed=round_trip.geometry.area / 10_000).set_index("stand_id")["recomputed"].sort_index()
max_drift = float((original_area - returned_area).abs().max())
report("areas match after the round trip", max_drift < 1e-6, f"max drift {max_drift:.2e} ha")

# %% [markdown]
# ## Step 7 · Add display centroids for Power BI
#
# Power BI map visuals want points in WGS84 degrees. Compute the centroid in the
# projected system so it lands in the geometrically correct place, then convert
# that point to degrees. Doing it the other way round puts the marker slightly
# wrong, and the error grows with latitude.

# %%
#@todo Compute centroids from the projected geometry, then convert them to CRS_WGS84
#@todo Add lon and lat columns to the stands frame
#@hint stands.geometry.centroid.to_crs(CRS_WGS84) gives you a GeoSeries of points in degrees
#@stub stands["lon"], stands["lat"] = None, None
#@solution
centroids = stands.geometry.centroid.to_crs(CRS_WGS84)
stands["lon"] = centroids.x.to_numpy()
stands["lat"] = centroids.y.to_numpy()
#@end

west, south, east, north = AOI_BBOX
inside = stands["lon"].between(west, east) & stands["lat"].between(south, north)
report("centroids fall inside the area of interest", bool(inside.all()),
       f"{int(inside.sum())}/{len(stands)} inside")

geodataframe_to_spark(stands, spark).write.format("delta").mode("overwrite") \
    .option("overwriteSchema", "true").saveAsTable(TABLE_STAND_REGISTER)
print(f"{TABLE_STAND_REGISTER} updated with display centroids")

# %% [markdown]
# ## Step 8 · Look at what you built
#
# Open the SQL analytics endpoint from the Lakehouse view and run this. It is the
# same Delta files you just wrote, read by a different engine, with no copy and
# no load step.
#
# ```sql
# SELECT species_group,
#        COUNT(*)        AS stands,
#        ROUND(SUM(area_ha), 1) AS total_ha
# FROM bronze_stand_register
# GROUP BY species_group
# ORDER BY total_ha DESC;
# ```

# %%
display(
    spark.sql(f"""
        SELECT species_group,
               management_regime,
               COUNT(*) AS stands,
               ROUND(SUM(area_ha), 1) AS total_ha,
               ROUND(AVG(area_ha), 1) AS mean_ha
        FROM {TABLE_STAND_REGISTER}
        GROUP BY species_group, management_regime
        ORDER BY total_ha DESC
    """)
)

# %% [markdown]
# ## Checkpoint
#
# You are done when every validation cell above prints `PASS`. If any print
# `FAIL`, open the solution notebook for that step, read the cell, and carry on.
# Nobody should be stuck here at 3:25.
#
# ## What you now have
#
# - A Delta table a planner could query today
# - Geometry stored in a form Spark, T-SQL and Power BI all understand
# - Areas in hectares that survive a round trip through storage
# - A bounding box validated well before it can waste an hour in Session 2
#
# ## Homework
#
# Change `AOI_NAME` and `AOI_BBOX` to a block you know, re-run the notebook, and
# check the areas against something real. Full brief in `docs/07-homework.md`.
#
# **Next:** `01_bronze_stac_ingest` opens Session 2 by fetching the imagery.
