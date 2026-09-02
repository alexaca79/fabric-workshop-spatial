"""End-to-end data verification for the workshop pipeline.

A notebook job reporting `Completed` only means nothing raised. This checks the
data the pipeline actually produced: grain, ranges, joins and the AI guard.
Run in the gold workspace, which reaches silver and bronze through shortcuts.

Column names here are the real ones, confirmed against the published schema:
silver carries `ndvi_mean` / `ndvi_p10` / `ndvi_p90` rather than a bare `ndvi`,
the date column is `scene_date`, and the map centroid is `lat` / `lon`.
"""

TOTAL_STANDS = 120
MIN_VALID_FRACTION = 0.60


def record(key, fn):
    try:
        findings[key] = {"ok": True, "value": str(fn())[:600]}
    except Exception as exc:
        findings[key] = {"ok": False, "value": f"{type(exc).__name__}: {exc}"[:600]}


def check(key, fn, predicate, detail=""):
    try:
        value = fn()
        findings[key] = {
            "ok": bool(predicate(value)),
            "value": f"{value}{(' | ' + detail) if detail else ''}",
        }
    except Exception as exc:
        findings[key] = {"ok": False, "value": f"{type(exc).__name__}: {exc}"[:600]}


def scalar(sql):
    return spark.sql(sql).collect()[0][0]


# --- grain and row counts ---------------------------------------------------
check("bronze_stand_register_rows",
      lambda: spark.table("bronze_stand_register").count(),
      lambda v: v == TOTAL_STANDS, f"expect {TOTAL_STANDS} synthetic stands")

check("bronze_scene_catalog_rows",
      lambda: spark.table("bronze_scene_catalog").count(),
      lambda v: v >= 2, "checkpoint requires at least two scenes")

check("bronze_stores_no_signed_hrefs",
      lambda: scalar("SELECT COUNT(*) FROM bronze_scene_catalog WHERE assets_json LIKE '%?%'"),
      lambda v: v == 0, "a signed URL in a table is a credential in a table")

check("silver_observations_rows",
      lambda: spark.table("silver_stand_observations").count(),
      lambda v: v == TOTAL_STANDS, "one row per stand per scene_date, one composite date per run")

check("silver_grain_is_unique",
      lambda: scalar("SELECT COUNT(*) - COUNT(DISTINCT stand_id, scene_date) "
                     "FROM silver_stand_observations"),
      lambda v: v == 0, "duplicate stand/date pairs would double count")

# --- physical plausibility --------------------------------------------------
for index in ("ndvi", "ndmi", "nbr", "evi"):
    check(f"{index}_within_physical_range",
          lambda i=index: scalar(
              f"SELECT COUNT(*) FROM silver_stand_observations "
              f"WHERE {i}_mean IS NOT NULL AND ({i}_mean < -1 OR {i}_mean > 1)"),
          lambda v: v == 0, "outside -1..1 means the arithmetic is wrong")

record("index_ranges",
       lambda: spark.sql(
           "SELECT ROUND(MIN(ndvi_mean),3) ndvi_lo, ROUND(MAX(ndvi_mean),3) ndvi_hi, "
           "ROUND(MIN(ndmi_mean),3) ndmi_lo, ROUND(MAX(ndmi_mean),3) ndmi_hi "
           "FROM silver_stand_observations").collect()[0].asDict())

# --- the provenance habit: every aggregate carries its count -----------------
check("valid_pixel_fraction_populated",
      lambda: scalar("SELECT COUNT(*) FROM silver_stand_observations "
                     "WHERE valid_pixel_fraction IS NULL"),
      lambda v: v == 0, "a median with no pixel count behind it is not a fact")

# --- classification, including the deliberate exclusions ---------------------
record("class_distribution",
       lambda: {r[0]: r[1] for r in spark.sql(
           "SELECT forest_class, COUNT(*) FROM gold_stand_classification "
           "GROUP BY forest_class ORDER BY 2 DESC").collect()})

# Stands are dropped on purpose when too much of the canopy was cloud. The test
# is not that every stand is classified, it is that every unclassified stand is
# explained by the valid-pixel gate rather than lost silently.
check("every_exclusion_is_explained",
      lambda: scalar(
          "SELECT COUNT(*) FROM silver_stand_observations s "
          "LEFT ANTI JOIN gold_stand_classification g ON s.stand_id = g.stand_id "
          f"WHERE s.valid_pixel_fraction >= {MIN_VALID_FRACTION}"),
      lambda v: v == 0, "a trusted stand with no class would be a real bug")

record("stands_excluded_for_cloud",
       lambda: scalar("SELECT COUNT(*) FROM silver_stand_observations "
                      f"WHERE valid_pixel_fraction < {MIN_VALID_FRACTION}"))

check("classes_are_from_the_dimension",
      lambda: scalar("SELECT COUNT(*) FROM gold_stand_classification g "
                     "LEFT ANTI JOIN gold_dim_forest_class d "
                     "ON g.forest_class = d.forest_class"),
      lambda v: v == 0, "a class not in the dimension breaks the star schema")

# --- the AI guard -------------------------------------------------------------
record("narrative_validation_status",
       lambda: {r[0]: r[1] for r in spark.sql(
           "SELECT validation_status, COUNT(*) FROM gold_stand_narrative "
           "GROUP BY validation_status ORDER BY 2 DESC").collect()})

check("narratives_exist",
      lambda: spark.table("gold_stand_narrative").count(), lambda v: v > 0)

# --- star schema integrity ----------------------------------------------------
check("facts_join_to_dim_stand",
      lambda: scalar("SELECT COUNT(*) FROM gold_stand_facts f "
                     "LEFT ANTI JOIN gold_dim_stand d ON f.stand_id = d.stand_id"),
      lambda v: v == 0, "orphaned facts")

check("facts_join_to_dim_date",
      lambda: scalar("SELECT COUNT(*) FROM gold_stand_facts f "
                     "LEFT ANTI JOIN gold_dim_date d ON f.date_key = d.date_key"),
      lambda v: v == 0, "Direct Lake time intelligence needs a complete date dimension")

check("dim_stand_has_map_centroids",
      lambda: scalar("SELECT COUNT(*) FROM gold_dim_stand WHERE lat IS NULL OR lon IS NULL"),
      lambda v: v == 0, "the Power BI map visual needs points")

check("centroids_land_in_new_brunswick",
      lambda: scalar("SELECT COUNT(*) FROM gold_dim_stand "
                     "WHERE lat NOT BETWEEN 45 AND 48 OR lon NOT BETWEEN -69 AND -63"),
      lambda v: v == 0, "catches a dropped minus sign or a swapped lat/lon")

record("facts_rows", lambda: spark.table("gold_stand_facts").count())
record("run_summary", lambda: spark.table("gold_pipeline_run_summary").collect()[0].asDict())

failed = [k for k, v in findings.items() if not v["ok"]]
findings["__verdict__"] = {
    "ok": not failed,
    "value": f"{len(findings) - len(failed)}/{len(findings)} passed"
             + (f" | FAILURES: {failed}" if failed else " | all checks passed"),
}
