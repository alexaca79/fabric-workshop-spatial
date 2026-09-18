# %% [markdown]
# # Lab 05 - Publish Gold tables and the Fabric Map layer
#
# Build and validate the Gold fact and dimension tables, write the run summary,
# and export every stand as a WGS84 polygon. These outputs support the native
# Fabric Map and Fabric Data Agent that you create from the handout.
#
# No semantic model, report, scheduled pipeline or external application is needed.

# %%
from datetime import date, datetime, timezone

import numpy as np
import pandas as pd
from pyspark.sql import SparkSession

spark = SparkSession.builder.getOrCreate()

AOI_NAME = "central-nb-block-a"
CRS_WGS84 = 4326
CRS_ANALYSIS = 2953

# --- Medallion layer --------------------------------------------------------
# Writes Gold publishing tables and reads the Bronze register from the shared
# lab lakehouse.
LAYER = "gold"
WORKSPACE = "jdi-training"
LAKEHOUSE = "lh_woodlands"

TABLE_STAND_REGISTER = "bronze_stand_register"
TABLE_CLASSIFICATION = "gold_stand_classification"
TABLE_CHANGE = "gold_stand_change"
TABLE_NARRATIVE = "gold_stand_narrative"

TABLE_FACTS = "gold_stand_facts"
TABLE_DIM_STAND = "gold_dim_stand"
TABLE_DIM_DATE = "gold_dim_date"
TABLE_DIM_CLASS = "gold_dim_forest_class"

def report(name, ok, detail=""):
    print(f"[{'PASS' if ok else 'FAIL'}] {name:<44} {detail}")

# %% [markdown]
# ## Step 1 · The star schema
#
# ```
#              gold_dim_date
#                    |
#  gold_dim_stand ── gold_stand_facts ── gold_dim_forest_class
#                    |
#              (narrative attached to the fact grain)
# ```
#
# Grain of the fact table: one row per stand per period. Everything descriptive
# moves to a dimension so the fact table stays narrow and the model stays fast.

# %% [markdown]
# ## Step 2 · Build the stand dimension
#
# One row per stand, with the display centroid. This is the table the map visual
# binds to, so latitude and longitude must be WGS84 degrees as doubles.

# %%
from shapely import wkb
import geopandas as gpd

def load_stand_register(table):
    pdf = spark.table(table).toPandas()
    srids = pdf["srid"].dropna().unique()
    geometry = [wkb.loads(bytes(v)) if v is not None else None for v in pdf["geometry_wkb"]]
    return gpd.GeoDataFrame(pdf.drop(columns=["geometry_wkb"]), geometry=geometry, crs=int(srids[0]))

register = load_stand_register(TABLE_STAND_REGISTER)

#@todo Build dim_stand with stand_id, licence_block, species_group, planted_year,
#@todo management_regime, area_ha, lat and lon
#@todo Compute lat and lon from the projected centroid, converted to WGS84
#@todo Deliberately exclude geometry_wkb, because a binary column forces a DirectQuery fallback
#@hint register.geometry.centroid.to_crs(CRS_WGS84) gives points in degrees
#@stub dim_stand = pd.DataFrame({"stand_id": register["stand_id"]})
#@solution
centroids = register.geometry.centroid.to_crs(CRS_WGS84)
dim_stand = pd.DataFrame({
    "stand_id": register["stand_id"],
    "licence_block": register["licence_block"],
    "species_group_declared": register["species_group"],
    "planted_year": register["planted_year"],
    "management_regime": register["management_regime"],
    "area_ha": register.geometry.area.to_numpy() / 10_000.0,
    "lat": centroids.y.to_numpy(),
    "lon": centroids.x.to_numpy(),
})
#@end

print(f"{len(dim_stand)} stands")
report("stand_id is unique", dim_stand["stand_id"].is_unique)
report("no binary columns", not any(dim_stand[c].dtype == object and isinstance(dim_stand[c].iloc[0], bytes)
                                    for c in dim_stand.columns))
report("coordinates look like degrees",
       bool(dim_stand["lat"].between(-90, 90).all() and dim_stand["lon"].between(-180, 180).all()),
       f"lat {dim_stand['lat'].min():.2f} to {dim_stand['lat'].max():.2f}, "
       f"lon {dim_stand['lon'].min():.2f} to {dim_stand['lon'].max():.2f}")

# %% [markdown]
# ### The map failure everyone hits once
#
# If the map shows nothing, latitude and longitude are reversed or still in
# projected metres. Coordinates in the millions with a column called `lat` is the
# signature. The check above catches both before Power BI does.

# %% [markdown]
# ## Step 3 · Build the date dimension
#
# Power BI needs a real date table marked as a date table, with contiguous dates
# and no gaps. Generating it here rather than as a DAX calculated table keeps
# Direct Lake from falling back.

# %%
classification = spark.table(TABLE_CLASSIFICATION).toPandas()
periods = pd.to_datetime(classification["period_end"]).dropna()

#@todo Build a contiguous daily date range covering the full span of periods,
#@todo padded to whole calendar years at both ends
#@todo Add date_key as YYYYMMDD integer, year, quarter, month, month_name and is_month_end
#@hint pd.date_range with freq="D". Contiguity matters; Power BI rejects a date table with gaps.
#@stub dim_date = pd.DataFrame({"date": periods.unique()})
#@solution
start = date(periods.min().year, 1, 1)
end = date(periods.max().year, 12, 31)
calendar = pd.date_range(start, end, freq="D")
dim_date = pd.DataFrame({
    "date": calendar.date,
    "date_key": calendar.strftime("%Y%m%d").astype(int),
    "year": calendar.year,
    "quarter": calendar.quarter,
    "month": calendar.month,
    "month_name": calendar.strftime("%b"),
    "is_month_end": calendar.is_month_end,
})
#@end

print(f"{len(dim_date)} dates, {dim_date['date'].min()} to {dim_date['date'].max()}")
report("date table is contiguous", len(dim_date) == (pd.to_datetime(dim_date["date"].max())
                                                     - pd.to_datetime(dim_date["date"].min())).days + 1)
report("date_key is unique", dim_date["date_key"].is_unique)

# %% [markdown]
# ## Step 4 · Build the class dimension
#
# Small, but it earns its place. It carries the display order and the map colour,
# so those live in the model rather than being re-entered in every report.

# %%
dim_class = pd.DataFrame([
    {"forest_class": "softwood",           "display_order": 1, "colour_hex": "#1B7F4B", "is_forest": True},
    {"forest_class": "hardwood",           "display_order": 2, "colour_hex": "#C77A2B", "is_forest": True},
    {"forest_class": "mixedwood",          "display_order": 3, "colour_hex": "#7A9E3F", "is_forest": True},
    {"forest_class": "regenerating",       "display_order": 4, "colour_hex": "#9DD08A", "is_forest": True},
    {"forest_class": "recently_harvested", "display_order": 5, "colour_hex": "#B5651D", "is_forest": False},
    {"forest_class": "non_forest",         "display_order": 6, "colour_hex": "#9AA5B1", "is_forest": False},
    {"forest_class": "unclassified",       "display_order": 7, "colour_hex": "#D9DEE4", "is_forest": False},
])
print(dim_class)

# %% [markdown]
# ## Step 5 · Build the fact table
#
# Narrow, numeric, and at one grain. Descriptive attributes stay in the
# dimensions.

# %%
change = spark.table(TABLE_CHANGE).toPandas()
narrative = spark.table(TABLE_NARRATIVE).toPandas()

#@todo Start from classification and select the fact columns
#@todo Left join the change columns on stand_id
#@todo Left join narrative and attention on stand_id
#@todo Fill a null forest_class with "unclassified" so every fact row joins to dim_class
#@todo Add date_key derived from period_end
#@hint An unmatched key in a star schema shows up as a blank in every visual. Fill it here.
#@stub facts = classification
#@solution
facts = classification[[
    "stand_id", "period_start", "period_end", "forest_class", "class_confidence",
    "class_method", "is_trusted", "observation_count", "register_agreement",
    "area_ha", "ndvi_p90", "ndmi_mean", "nbr_mean", "evi_mean", "valid_pixel_fraction",
]].copy()

facts = facts.merge(
    change[["stand_id", "change_type", "severity", "requires_review", "delta_nbr"]],
    on="stand_id", how="left",
)
facts = facts.merge(
    narrative[["stand_id", "narrative", "attention", "validation_status"]],
    on="stand_id", how="left",
)

facts["forest_class"] = facts["forest_class"].fillna("unclassified")
facts["change_type"] = facts["change_type"].fillna("none")
facts["requires_review"] = facts["requires_review"].fillna(False)
facts["date_key"] = pd.to_datetime(facts["period_end"]).dt.strftime("%Y%m%d").astype(int)
#@end

print(f"{len(facts)} fact rows, {len(facts.columns)} columns")
facts.head(3)

# %% [markdown]
# ### Referential integrity
#
# Check the joins before Power BI does. A blank in a visual is a much more
# expensive way to discover an unmatched key.

# %%
report("fact grain is unique",
       not facts.duplicated(subset=["stand_id", "period_end"]).any())
report("every stand key resolves",
       facts["stand_id"].isin(dim_stand["stand_id"]).all(),
       f"{(~facts['stand_id'].isin(dim_stand['stand_id'])).sum()} orphans")
report("every date key resolves",
       facts["date_key"].isin(dim_date["date_key"]).all(),
       f"{(~facts['date_key'].isin(dim_date['date_key'])).sum()} orphans")
report("every class key resolves",
       facts["forest_class"].isin(dim_class["forest_class"]).all(),
       f"unmatched: {set(facts['forest_class']) - set(dim_class['forest_class']) or 'none'}")

# %% [markdown]
# ## Step 6 · Write the model tables

# %%
def write_gold(df, table):
    (
        spark.createDataFrame(df).write
        .format("delta").mode("overwrite").option("overwriteSchema", "true")
        .saveAsTable(table)
    )
    return spark.table(table).count()

for frame, table in [
    (facts, TABLE_FACTS),
    (dim_stand, TABLE_DIM_STAND),
    (dim_date, TABLE_DIM_DATE),
    (dim_class, TABLE_DIM_CLASS),
]:
    print(f"  {table:<28} {write_gold(frame, table):>6} rows")

# %% [markdown]
# ## Step 7 · Answer the problem statement in SQL first
#
# Before building a report, prove the data can answer the question. If the SQL is
# awkward, the model is wrong, and no amount of visual design fixes that.
#
# > Which stands are softwood, hardwood or mixedwood, which have been harvested
# > since the last look, and which are showing moisture stress.

# %%
display(spark.sql(f"""
    SELECT c.forest_class,
           COUNT(*)                                  AS stands,
           ROUND(SUM(f.area_ha), 1)                  AS total_ha,
           ROUND(AVG(f.class_confidence), 2)         AS mean_confidence,
           SUM(CASE WHEN f.change_type = 'harvest' THEN 1 ELSE 0 END)         AS harvested,
           SUM(CASE WHEN f.change_type = 'moisture_stress' THEN 1 ELSE 0 END) AS stressed,
           SUM(CASE WHEN f.requires_review THEN 1 ELSE 0 END)                 AS needs_review
    FROM {TABLE_FACTS} f
    JOIN {TABLE_DIM_CLASS} c ON f.forest_class = c.forest_class
    GROUP BY c.forest_class, c.display_order
    ORDER BY c.display_order
"""))

# %% [markdown]
# ## Step 8 · The planner work queue
#
# The single most useful output of the whole pipeline: which stands need a human
# to look at them, in priority order.

# %%
display(spark.sql(f"""
    SELECT f.stand_id,
           s.licence_block,
           f.forest_class,
           f.change_type,
           f.severity,
           ROUND(f.area_ha, 1)  AS area_ha,
           ROUND(f.delta_nbr, 3) AS delta_nbr,
           f.narrative
    FROM {TABLE_FACTS} f
    JOIN {TABLE_DIM_STAND} s ON f.stand_id = s.stand_id
    WHERE f.requires_review = true
    ORDER BY f.severity DESC, f.area_ha DESC
    LIMIT 20
"""))

# %% [markdown]
# ## Step 9 - Publish the run summary
#
# One row per pipeline run, written every time. This is what you look at when
# someone asks why last month's numbers moved.

# %%
run_summary = pd.DataFrame([{
    "aoi_name": AOI_NAME,
    "run_completed_utc": datetime.now(timezone.utc),
    "stands_total": int(len(dim_stand)),
    "stands_classified": int(facts["is_trusted"].sum()),
    "trusted_coverage": float(facts["is_trusted"].mean()),
    "area_total_ha": float(facts["area_ha"].sum()),
    "area_harvested_ha": float(facts.loc[facts.change_type == "harvest", "area_ha"].sum()),
    "stands_needing_review": int(facts["requires_review"].sum()),
    "narratives_generated": int(facts["narrative"].notna().sum()),
    "class_method": str(facts["class_method"].dropna().iloc[0]) if facts["class_method"].notna().any() else "unknown",
}])

(
    spark.createDataFrame(run_summary).write
    .format("delta").mode("append").option("mergeSchema", "true")
    .saveAsTable("gold_pipeline_run_summary")
)

print(run_summary.T)

# %% [markdown]
# ## Export the native Fabric Map layer
#
# Run the supplied cell below after completing the Gold exercises. It exports the latest reporting period as WGS84 polygons to `Files/gold/maps/stand_classification.geojson` in your default lakehouse. It keeps every registered stand, including stands without a classified result. The `no_classified_result` display category is different from the classifier's `unclassified` class.
#
# Confirm `readback` is `PASS` and `registered_stands = retained_stands + stands_without_result`. `register_coverage` uses all registered stands as its denominator. The export is a file snapshot: rerun it and refresh the map after changing the data.
#
# Next, follow [the manual walkthrough](../../docs/16-manual-upload-labs.md) to create a native Fabric Map and Fabric Data Agent in the portal. Neither item is created by this notebook, and neither requires a Power BI semantic model.

# %%
import json
from pathlib import Path

from shapely import get_coordinates


def build_map_features(register, facts, dim_class, period_end=None):
    """Build a one-period GeoJSON snapshot without hiding missing stand results."""
    if register.empty or len(register) > 100_000:
        raise ValueError("The map requires 1 to 100,000 registered stands")
    if register["stand_id"].isna().any() or not register["stand_id"].is_unique:
        raise ValueError("Register stand_id must be non-null and unique")
    if register.crs is None:
        raise ValueError("Register geometry needs its actual CRS before export")
    if (register.geometry.isna().any() or register.geometry.is_empty.any()
            or not register.geometry.is_valid.all()
            or not register.geometry.geom_type.isin(["Polygon", "MultiPolygon"]).all()):
        raise ValueError("Every registered stand must have a valid, nonempty polygon")
    if not np.isfinite(get_coordinates(register.geometry)).all():
        raise ValueError("Stand coordinates must be finite")
    if facts.empty or facts["stand_id"].isna().any():
        raise ValueError("Complete the Gold facts before exporting a map")

    periods = pd.to_datetime(facts["period_end"], errors="raise").dt.normalize()
    if periods.isna().any():
        raise ValueError("Every fact needs a reporting period")
    chosen_period = periods.max() if period_end is None else pd.Timestamp(period_end).normalize()
    selected = facts.loc[periods.eq(chosen_period)].copy()
    if selected.empty:
        raise ValueError("No facts exist for the selected reporting period")
    if not selected["stand_id"].is_unique:
        raise ValueError("Selected-period facts must have one row per stand")
    if not selected["stand_id"].isin(register["stand_id"]).all():
        raise ValueError("Selected-period facts contain an unknown stand_id")
    if (dim_class["forest_class"].isna().any()
            or not dim_class["forest_class"].is_unique
            or not selected["forest_class"].isin(dim_class["forest_class"]).all()):
        raise ValueError("Every retained forest class must resolve uniquely")

    properties = [
        "stand_id", "forest_class", "class_confidence", "is_trusted",
        "valid_pixel_fraction", "requires_review", "change_type", "validation_status",
    ]
    spatial = register[["stand_id", "licence_block", "geometry"]].copy()
    spatial["area_ha"] = register.to_crs(CRS_ANALYSIS).geometry.area / 10_000.0
    spatial["stand_source"] = register["source"] if "source" in register else "unknown"
    spatial = spatial.to_crs(CRS_WGS84)
    coordinates = get_coordinates(spatial.geometry)
    if (not np.isfinite(coordinates).all()
            or (np.abs(coordinates[:, 0]) > 180).any()
            or (np.abs(coordinates[:, 1]) > 90).any()):
        raise ValueError("Reprojected coordinates must be finite WGS84 degrees")

    spatial = spatial.merge(selected[properties], on="stand_id", how="left",
                            validate="one_to_one", indicator=True)
    retained = spatial.pop("_merge").eq("both")
    spatial["period_end"] = chosen_period.date().isoformat()
    spatial["coverage_status"] = np.where(retained, "retained", "no_classified_result")
    spatial["map_class"] = spatial["forest_class"].where(retained, "no_classified_result")
    for column in ("is_trusted", "requires_review"):
        spatial[column] = pd.array(spatial[column], dtype="boolean")
    colours = dim_class.set_index("forest_class")["colour_hex"]
    spatial["colour_hex"] = spatial["forest_class"].map(colours).where(retained, "#61717D")
    return json.loads(spatial.to_json(na="null", drop_id=True, to_wgs84=True, allow_nan=False))


def export_stand_map(register, facts, dim_class, output_path, period_end=None):
    """Validate, write and read back the GeoJSON file for the manual map lesson."""
    payload = build_map_features(register, facts, dim_class, period_end)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, allow_nan=False) + "\n", encoding="utf-8")
    if json.loads(output_path.read_text(encoding="utf-8")) != payload:
        raise RuntimeError("Map export readback did not match the generated features")
    features = payload["features"]
    retained = sum(feature["properties"]["coverage_status"] == "retained" for feature in features)
    return {
        "path": str(output_path),
        "period_end": features[0]["properties"]["period_end"],
        "registered_stands": len(features),
        "retained_stands": retained,
        "stands_without_result": len(features) - retained,
        "register_coverage": retained / len(features),
        "readback": "PASS",
    }


map_export = export_stand_map(
    register, facts, dim_class,
    Path("/lakehouse/default/Files/gold/maps/stand_classification.geojson"),
)
print(json.dumps(map_export, indent=2))

# %% [markdown]
# ## Final checkpoint
#
# The notebook work is complete when:
#
# - Four Gold model tables exist with clean referential integrity
# - All required checks pass and the run summary is written
# - The map GeoJSON readback passes and includes all registered stands
# - The reporting period, coverage exclusions and offline narratives are explained
#
# Next, follow the supplied manual walkthrough to create and test your native
# Fabric Map and Fabric Data Agent. Both are required for the full manual
# workshop, but neither is created by this notebook. Open the guide from the
# extracted bundle's handouts folder; notebook import does not upload that guide.
