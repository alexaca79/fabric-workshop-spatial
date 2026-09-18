# %% [markdown]
# # Lab 03 - Classify the stands and detect what changed
#
# **Session 2, Step 2 continued.** Turn silver observations into a forest class
# per stand and a change record per stand, both traceable back to the logic that
# produced them.
#
# ## What gold promises
#
# Meaning, for a named decision. Every gold number answers part of the problem
# statement from the start of the session:
#
# > Which stands are softwood, hardwood or mixedwood, which have been harvested
# > since the last look, and which are showing moisture stress.
#
# ## Why thresholds rather than a trained model
#
# A forester can argue with a number in a threshold dictionary. Nobody can argue
# with a weight inside a model. Until you have labels you trust, a holdout you
# did not tune on, and a story for what happens when the imagery distribution
# shifts between seasons, the auditable option is the honest one.
#
# The trained-model path is in `src/forestops/classify.py` and is offered as an
# assignment extension, not as today's default.

# %% [markdown]
# ## Step 1 · Configuration
#
# Every threshold in one dictionary. When a forester disagrees with a class, the
# conversation is about a number in this cell, not about a model.

# %%
import numpy as np
import pandas as pd
from pyspark.sql import SparkSession

spark = SparkSession.builder.getOrCreate()

AOI_NAME = "central-nb-block-a"
CRS_ANALYSIS = 2953

THRESHOLDS = {
    "non_forest_ndvi_max": 0.30,
    "recently_harvested_nbr_max": 0.20,
    "regenerating_ndvi_max": 0.55,
    "softwood_ndmi_min": 0.18,
    "hardwood_ndmi_max": 0.10,
    "moisture_stress_ndmi_max": 0.05,
    "harvest_delta_nbr_min": 0.25,
    "min_valid_pixel_fraction": 0.60,
}

FOREST_CLASSES = (
    "softwood", "hardwood", "mixedwood",
    "regenerating", "recently_harvested", "non_forest",
)

RULE_VERSION = "rule_v1"

# --- Medallion layer --------------------------------------------------------
# Writes Gold tables and reads Silver from the shared lab lakehouse.
LAYER = "gold"
WORKSPACE = "jdi-training"
LAKEHOUSE = "lh_woodlands"

TABLE_OBSERVATIONS = "silver_stand_observations"
TABLE_CLASSIFICATION = "gold_stand_classification"  # written here
TABLE_CHANGE = "gold_stand_change"                  # written here

def report(name, ok, detail=""):
    print(f"[{'PASS' if ok else 'FAIL'}] {name:<42} {detail}")

observations = spark.table(TABLE_OBSERVATIONS).toPandas()
print(f"{len(observations)} silver observations, {observations['stand_id'].nunique()} stands")
print(f"scene dates: {sorted(observations['scene_date'].unique())}")

# %% [markdown]
# ## Step 2 · Composite by period
#
# Many scene dates per stand collapse to one row per period. Trusted rows only.
#
# Averaging a cloudy row with a clear one produces a number that is defensible in
# neither direction, which is the whole reason `valid_pixel_fraction` exists.

# %%
def composite_by_period(df, period_start, period_end):
    """Reduce scene-date observations to one row per stand for the period."""
    #@todo Filter to rows whose scene_date falls inside the period
    #@todo Filter out rows where valid_pixel_fraction is below the threshold
    #@todo Group by stand_id and take the median of every ndvi/ndmi/nbr/evi column
    #@todo Carry valid_pixel_fraction as a mean, pixel_count as a max, area_ha as first
    #@todo Carry licence_block, species_group and management_regime as first
    #@todo Add observation_count as the number of distinct scene dates per stand
    #@todo Add period_start and period_end columns
    #@hint Median rather than mean, for the same reason silver composited with a median
    #@stub return df
#@solution
    dates = pd.to_datetime(df["scene_date"])
    window = df[
        (dates >= pd.to_datetime(period_start))
        & (dates <= pd.to_datetime(period_end))
        & (df["valid_pixel_fraction"] >= THRESHOLDS["min_valid_pixel_fraction"])
    ]
    if window.empty:
        return pd.DataFrame(columns=df.columns)

    numeric = [c for c in window.columns if c.startswith(("ndvi", "ndmi", "nbr", "evi"))]
    agg = {c: "median" for c in numeric}
    agg["valid_pixel_fraction"] = "mean"
    agg["pixel_count"] = "max"
    agg["area_ha"] = "first"
    for col in ("licence_block", "species_group", "management_regime"):
        if col in window.columns:
            agg[col] = "first"

    composite = window.groupby("stand_id", as_index=False).agg(agg)
    composite["observation_count"] = (
        window.groupby("stand_id")["scene_date"].nunique().reindex(composite["stand_id"]).to_numpy()
    )
    composite["period_start"] = pd.to_datetime(period_start).date()
    composite["period_end"] = pd.to_datetime(period_end).date()
    return composite
#@end

current = composite_by_period(observations, "2026-06-01", "2026-08-31")
print(f"{len(current)} stands with a trusted composite for the period")
report("composite produced rows", len(current) > 0)
report("one row per stand", current["stand_id"].is_unique if len(current) else False)
dropped = observations["stand_id"].nunique() - len(current)
report("untrusted stands excluded", True, f"{dropped} stands dropped for insufficient valid pixels")

# %% [markdown]
# ## Step 3 · The rule-based classifier
#
# Gates run from most certain to least certain. A clear-cut is identified as
# harvested before anything tries to decide what species used to grow there.
#
# ```
#   valid_pixel_fraction < 0.60           ->  untrusted, no class
#   NDVI p90 < 0.30                       ->  non_forest
#   NBR < 0.20                            ->  recently_harvested
#   NDVI p90 < 0.55                       ->  regenerating
#   NDMI >= 0.18                          ->  softwood
#   NDMI <= 0.10                          ->  hardwood
#   otherwise                             ->  mixedwood
# ```
#
# ### On confidence
#
# The confidence column is distance from the nearest decision boundary,
# normalised to 0.5 to 1.0. It says how close the call was. It is **not** a
# probability, and the column documentation says so, because a number called
# confidence gets read as a probability by everyone who did not write it.
#
# Mixedwood is the residual class, so its confidence is genuinely low by
# construction. Reporting it as high would be dishonest.

# %%
def margin(distance, scale):
    """Map distance from a decision boundary onto a 0.5 to 1.0 range."""
    with np.errstate(invalid="ignore"):
        return 0.5 + 0.5 * np.clip(np.abs(distance) / scale, 0.0, 1.0)

def classify_rule_based(df, thresholds=THRESHOLDS):
    """Assign a forest class from spectral indices using explicit thresholds."""
    out = df.copy()
    t = thresholds

    ndvi = out["ndvi_p90"].to_numpy(dtype="float64")
    ndmi = out["ndmi_mean"].to_numpy(dtype="float64")
    nbr = out["nbr_mean"].to_numpy(dtype="float64")
    valid = out["valid_pixel_fraction"].to_numpy(dtype="float64")

    classes = np.full(len(out), "mixedwood", dtype=object)
    confidence = np.full(len(out), 0.5, dtype="float64")

    #@todo Build the untrusted mask: valid_pixel_fraction below the threshold
    #@todo Gate 1: non_forest where NDVI p90 is below non_forest_ndvi_max
    #@todo Gate 2: recently_harvested where NBR is below recently_harvested_nbr_max
    #@todo Gate 3: regenerating where NDVI p90 is below regenerating_ndvi_max
    #@todo Gate 4: softwood where NDMI is at or above softwood_ndmi_min
    #@todo Gate 5: hardwood where NDMI is at or below hardwood_ndmi_max
    #@todo Everything remaining stays mixedwood with confidence 0.45
    #@todo Set class to None and confidence to 0 for untrusted rows
    #@hint Each gate must exclude the rows already claimed by earlier gates
    #@hint Use margin(distance_from_threshold, scale) for confidence, scale around 0.15 to 0.25
    #@stub pass
#@solution
    untrusted = valid < t["min_valid_pixel_fraction"]

    non_forest = (~untrusted) & (ndvi < t["non_forest_ndvi_max"])
    classes[non_forest] = "non_forest"
    confidence[non_forest] = margin(t["non_forest_ndvi_max"] - ndvi[non_forest], 0.20)

    harvested = (~untrusted) & (~non_forest) & (nbr < t["recently_harvested_nbr_max"])
    classes[harvested] = "recently_harvested"
    confidence[harvested] = margin(t["recently_harvested_nbr_max"] - nbr[harvested], 0.20)

    regen = (~untrusted) & (~non_forest) & (~harvested) & (ndvi < t["regenerating_ndvi_max"])
    classes[regen] = "regenerating"
    confidence[regen] = margin(t["regenerating_ndvi_max"] - ndvi[regen], 0.25)

    remaining = (~untrusted) & (~non_forest) & (~harvested) & (~regen)

    softwood = remaining & (ndmi >= t["softwood_ndmi_min"])
    classes[softwood] = "softwood"
    confidence[softwood] = margin(ndmi[softwood] - t["softwood_ndmi_min"], 0.15)

    hardwood = remaining & (ndmi <= t["hardwood_ndmi_max"])
    classes[hardwood] = "hardwood"
    confidence[hardwood] = margin(t["hardwood_ndmi_max"] - ndmi[hardwood], 0.15)

    mixed = remaining & (~softwood) & (~hardwood)
    classes[mixed] = "mixedwood"
    confidence[mixed] = 0.45

    classes[untrusted] = None
    confidence[untrusted] = 0.0
#@end

    out["forest_class"] = classes
    out["class_confidence"] = np.clip(np.nan_to_num(confidence, nan=0.0), 0.0, 1.0).round(3)
    out["class_method"] = RULE_VERSION
    out["is_trusted"] = ~untrusted
    return out

classified = classify_rule_based(current)
summary = (
    classified.groupby("forest_class", dropna=False)
    .agg(stands=("stand_id", "count"), area_ha=("area_ha", "sum"), mean_confidence=("class_confidence", "mean"))
    .sort_values("area_ha", ascending=False)
    .round(2)
)
print(summary)

# %% [markdown]
# ### Validation

# %%
report("every stand has a row", len(classified) == len(current))
unexpected = set(classified["forest_class"].dropna().unique()) - set(FOREST_CLASSES)
report("no unexpected class values", not unexpected, f"{unexpected or 'none'}")
report("confidence in range", bool(classified["class_confidence"].between(0, 1).all()))
report("class_method recorded", classified["class_method"].notna().all(), RULE_VERSION)
report("untrusted rows have no class",
       bool(classified.loc[~classified["is_trusted"], "forest_class"].isna().all()))
report("mixedwood confidence is honest",
       bool((classified.loc[classified.forest_class == "mixedwood", "class_confidence"] <= 0.5).all()),
       "residual class, low by construction")

# %% [markdown]
# ## Step 4 · Compare against the register
#
# Disagreement is not automatically an error. The inventory can be out of date,
# the stand can have been harvested, or the spectral signal can genuinely be
# ambiguous in mixedwood.
#
# This column builds a review queue. It does not overwrite the register.

# %%
#@todo Add register_agreement with values agrees, disagrees or not_comparable
#@todo Only compare when forest_class is one of the three species classes and species_group is present
#@hint np.where nested twice, or a small function applied row-wise
#@stub classified["register_agreement"] = "not_comparable"
#@solution
comparable = (
    classified["forest_class"].isin(["softwood", "hardwood", "mixedwood"])
    & classified["species_group"].notna()
)
classified["register_agreement"] = np.where(
    ~comparable,
    "not_comparable",
    np.where(classified["forest_class"] == classified["species_group"], "agrees", "disagrees"),
)
#@end

agreement = classified["register_agreement"].value_counts()
print(agreement)

comparable_rows = classified[classified["register_agreement"] != "not_comparable"]
if len(comparable_rows):
    rate = (comparable_rows["register_agreement"] == "agrees").mean()
    print(f"\nAgreement rate on comparable stands: {rate:.1%}")
    print("Expect roughly 55 to 75 percent on synthetic data. On real inventory,")
    print("a rate above 90 percent usually means the classifier is reading the")
    print("register rather than the imagery, which is worth checking for.")

# %% [markdown]
# ### Where does it disagree, and does that make sense
#
# Mixedwood is where a spectral classifier should struggle, because the mixture
# is exactly what the index values average out. If your disagreements cluster in
# mixedwood, the classifier is behaving as expected. If they cluster in softwood,
# something is wrong with the NDMI threshold.

# %%
if len(comparable_rows):
    crosstab = pd.crosstab(
        comparable_rows["species_group"], comparable_rows["forest_class"], margins=True
    )
    print("Rows: register species group.  Columns: spectral class.\n")
    print(crosstab)

# %% [markdown]
# ## Step 5 · Change detection
#
# The operational question is not "what class is this stand" but "what changed
# since I last looked, and does anyone need to go and stand in it".
#
# A drop in NBR is the primary canopy-removal signal. It cannot distinguish
# harvest from windthrow or fire, which is why the output carries a change type
# a human confirms rather than a decision the pipeline makes alone.

# %%
baseline = composite_by_period(observations, "2025-06-01", "2025-08-31")

if baseline.empty:
    print("No baseline period available in this dataset.")
    print("Simulating a baseline so the change logic can be exercised and validated.")
    rng = np.random.default_rng(7)
    baseline = current.copy()
    # Most stands unchanged, a handful with materially higher prior canopy.
    shift = rng.choice([0.0, 0.0, 0.0, 0.35, 0.45], size=len(baseline))
    baseline["nbr_mean"] = np.clip(baseline["nbr_mean"] + shift, -1, 1)
    baseline["ndvi_p90"] = np.clip(baseline["ndvi_p90"] + shift * 0.4, -1, 1)
    baseline["ndmi_mean"] = np.clip(baseline["ndmi_mean"] + shift * 0.2, -1, 1)
    baseline["period_start"] = pd.to_datetime("2025-06-01").date()
    baseline["period_end"] = pd.to_datetime("2025-08-31").date()

print(f"baseline: {len(baseline)} stands   current: {len(current)} stands")

# %%
def detect_change(current_df, baseline_df, thresholds=THRESHOLDS):
    """Compare two period composites and label what changed per stand."""
    joined = current_df.merge(
        baseline_df, on="stand_id", suffixes=("", "_base"), how="inner", validate="one_to_one"
    )

    #@todo Compute delta_nbr as baseline NBR minus current NBR, so canopy loss is positive
    #@todo Compute delta_ndvi and delta_ndmi as current minus baseline
    #@hint Sign conventions matter here. Loss should read as a positive delta_nbr.
    #@stub joined["delta_nbr"] = 0.0
#@solution
    joined["delta_nbr"] = joined["nbr_mean_base"] - joined["nbr_mean"]
    joined["delta_ndvi"] = joined["ndvi_p90"] - joined["ndvi_p90_base"]
    joined["delta_ndmi"] = joined["ndmi_mean"] - joined["ndmi_mean_base"]
#@end

    change_type = np.full(len(joined), "none", dtype=object)

    #@todo Flag canopy loss where delta_nbr is at or above harvest_delta_nbr_min
    #@todo Label it harvest where management_regime is plantation or thinned, disturbance otherwise
    #@todo Label moisture_stress where there is no canopy loss, NDMI is low, and delta_ndmi is negative
    #@todo Label regrowth where there is no canopy loss and delta_ndvi is at or above 0.10
    #@hint A planned regime plus canopy loss is almost certainly a harvest. Everything else is
    #@hint disturbance until a human confirms otherwise, which is the safer default.
    #@stub canopy_loss = pd.Series(False, index=joined.index)
#@solution
    canopy_loss = joined["delta_nbr"] >= thresholds["harvest_delta_nbr_min"]
    planned = joined.get("management_regime", pd.Series("unknown", index=joined.index)).isin(
        ["plantation", "thinned"]
    )
    change_type[(canopy_loss & planned).to_numpy()] = "harvest"
    change_type[(canopy_loss & ~planned).to_numpy()] = "disturbance"

    stressed = (
        (~canopy_loss)
        & (joined["ndmi_mean"] <= thresholds["moisture_stress_ndmi_max"])
        & (joined["delta_ndmi"] < -0.05)
    )
    change_type[stressed.to_numpy()] = "moisture_stress"

    regrowth = (~canopy_loss) & (joined["delta_ndvi"] >= 0.10)
    change_type[regrowth.to_numpy()] = "regrowth"
#@end

    joined["change_type"] = change_type

    severity = np.full(len(joined), "low", dtype=object)
    severity[joined["delta_nbr"] >= thresholds["harvest_delta_nbr_min"]] = "moderate"
    severity[joined["delta_nbr"] >= thresholds["harvest_delta_nbr_min"] * 2] = "high"
    joined["severity"] = severity

    #@todo Set requires_review True for disturbance, moisture_stress, and high-severity harvest
    #@hint A routine harvest on a plantation does not need a planner to look at it. A disturbance does.
    #@stub joined["requires_review"] = False
#@solution
    joined["requires_review"] = (
        joined["change_type"].isin(["disturbance", "moisture_stress"])
        | ((joined["change_type"] == "harvest") & (joined["severity"] == "high"))
    )
#@end

    joined["detected_on"] = joined["period_end"]
    columns = ["stand_id", "detected_on", "change_type", "delta_nbr", "delta_ndvi",
               "delta_ndmi", "severity", "requires_review", "area_ha", "licence_block"]
    return joined[[c for c in columns if c in joined.columns]]

change = detect_change(current, baseline)
print(
    change.groupby("change_type")
    .agg(stands=("stand_id", "nunique"), area_ha=("area_ha", "sum"), review=("requires_review", "sum"))
    .round(1)
)

# %% [markdown]
# ### Validation

# %%
report("change rows produced", len(change) > 0, f"{len(change)} stands compared")
report("no unexpected change types",
       set(change["change_type"].unique()).issubset({"harvest", "disturbance", "moisture_stress", "regrowth", "none"}))
report("severity only on real change",
       bool((change.loc[change.change_type == "none", "severity"] == "low").all()))
report("review queue is a sensible size",
       change["requires_review"].sum() < len(change) * 0.5,
       f"{int(change['requires_review'].sum())} of {len(change)} stands flagged")

# %% [markdown]
# If more than half the stands need review, the thresholds are wrong, not the
# forest. A review queue nobody can work through is the same as no review queue.

# %% [markdown]
# ## Step 6 · Write gold

# %%
classification_out = classified[[
    "stand_id", "period_start", "period_end", "forest_class", "class_confidence",
    "class_method", "is_trusted", "observation_count", "register_agreement",
    "species_group", "licence_block", "management_regime", "area_ha",
    "ndvi_p90", "ndmi_mean", "nbr_mean", "evi_mean", "valid_pixel_fraction",
]].copy()

#@todo Write classification_out to TABLE_CLASSIFICATION as Delta, overwriting
#@todo Write change to TABLE_CHANGE as Delta, overwriting
#@stub pass
#@solution
(
    spark.createDataFrame(classification_out).write
    .format("delta").mode("overwrite").option("overwriteSchema", "true")
    .saveAsTable(TABLE_CLASSIFICATION)
)
(
    spark.createDataFrame(change).write
    .format("delta").mode("overwrite").option("overwriteSchema", "true")
    .saveAsTable(TABLE_CHANGE)
)
#@end

print(f"{TABLE_CLASSIFICATION}: {spark.table(TABLE_CLASSIFICATION).count()} rows")
print(f"{TABLE_CHANGE}: {spark.table(TABLE_CHANGE).count()} rows")

# %% [markdown]
# ## Step 7 · Sanity check the answer, not just the code
#
# The code can be correct and the answer still wrong. Two questions worth asking
# before anyone builds a report on this.

# %%
total_area = classification_out["area_ha"].sum()
harvested_area = change.loc[change.change_type == "harvest", "area_ha"].sum()
print(f"Total area classified:  {total_area:,.0f} ha")
print(f"Area detected harvested: {harvested_area:,.0f} ha  ({harvested_area / total_area:.1%})")
print()
print("Question 1: is that harvest percentage plausible for one season on this")
print("            licence area? If it is 30 percent, the NBR threshold is wrong.")
print()

softwood_share = (
    classification_out.loc[classification_out.forest_class == "softwood", "area_ha"].sum() / total_area
)
print(f"Softwood share of classified area: {softwood_share:.1%}")
print("Question 2: does that match what you know about this licence area? A")
print("            spectral classifier that disagrees with local knowledge by 30")
print("            points is telling you about the thresholds, not the forest.")

# %% [markdown]
# ## Checkpoint
#
# You are done when `gold_stand_classification` and `gold_stand_change` exist,
# every validation prints `PASS`, and you have looked at the two sanity questions
# above and formed an opinion.
#
# ## What this does not do
#
# It does not detect change below the resolution of a Sentinel-2 pixel, so
# selective thinning is largely invisible at 20 metres. It does not replace field
# cruising. It narrows where a crew goes, which is a smaller claim and a more
# defensible one.
#
# **Next:** `04_gold_ai_enrichment_foundry` adds language, carefully.
