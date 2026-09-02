"""Bronze-layer checks, run from silver where the scene catalogue shortcut exists.

Gold has no shortcut to `bronze_scene_catalog` on purpose: it never needs the
scene metadata. Silver does, so the catalogue assertions belong here.
"""


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


check("bronze_scene_catalog_rows",
      lambda: spark.table("bronze_scene_catalog").count(),
      lambda v: v >= 2, "checkpoint requires at least two scenes")

check("bronze_stores_no_signed_hrefs",
      lambda: scalar("SELECT COUNT(*) FROM bronze_scene_catalog WHERE assets_json LIKE '%?%'"),
      lambda v: v == 0, "a signed URL in a table is a credential in a table")

check("every_scene_has_a_run_id",
      lambda: scalar("SELECT COUNT(*) FROM bronze_scene_catalog WHERE pipeline_run_id IS NULL"),
      lambda v: v == 0, "the run id is how a published number traces back to its scenes")

check("cloud_cover_recorded",
      lambda: scalar("SELECT COUNT(*) FROM bronze_scene_catalog WHERE cloud_cover_pct IS NULL"),
      lambda v: v == 0)

check("scenes_below_cloud_threshold",
      lambda: scalar("SELECT COUNT(*) FROM bronze_scene_catalog WHERE cloud_cover_pct >= 20"),
      lambda v: v == 0, "the search filtered on eo:cloud_cover < 20")

findings["scene_summary"] = {
    "ok": True,
    "value": str([r.asDict() for r in spark.sql(
        "SELECT scene_id, ROUND(cloud_cover_pct,1) cloud, epsg "
        "FROM bronze_scene_catalog ORDER BY cloud_cover_pct").collect()])[:600],
}

failed = [k for k, v in findings.items() if not v["ok"]]
findings["__verdict__"] = {
    "ok": not failed,
    "value": f"{len(findings) - len(failed)}/{len(findings)} passed"
             + (f" | FAILURES: {failed}" if failed else " | all checks passed"),
}
