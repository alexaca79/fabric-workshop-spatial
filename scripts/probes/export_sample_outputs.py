"""Export a small, representative sample of every pipeline table.

These become notebooks/sample-outputs/ so a student can compare their own run
against a known-good one without needing access to this capacity. Sampled from
the verified run, not hand written, so the shapes and value ranges are real.
"""

import json

TABLES = [
    "bronze_stand_register",
    "silver_stand_observations",
    "gold_stand_classification",
    "gold_stand_change",
    "gold_stand_narrative",
    "gold_stand_facts",
    "gold_dim_stand",
    "gold_dim_date",
    "gold_dim_forest_class",
    "gold_pipeline_run_summary",
]

SAMPLE_ROWS = 3


def summarise(name):
    df = spark.table(name)
    fields = [(f.name, f.dataType.simpleString()) for f in df.schema.fields]
    rows = [r.asDict() for r in df.limit(SAMPLE_ROWS).collect()]

    # Trim anything that would dominate the file. Geometry WKB and the model
    # narrative are both long and neither is useful as a shape reference.
    for row in rows:
        for key, value in list(row.items()):
            if isinstance(value, (bytes, bytearray)):
                row[key] = f"<{len(value)} bytes of WKB>"
            elif isinstance(value, str) and len(value) > 160:
                row[key] = value[:157] + "..."

    return {
        "row_count": df.count(),
        "column_count": len(fields),
        "schema": [f"{n} : {t}" for n, t in fields],
        "sample": rows,
    }


for table in TABLES:
    try:
        findings[table] = {"ok": True, "value": summarise(table)}
    except Exception as exc:
        findings[table] = {"ok": False, "value": f"{type(exc).__name__}: {exc}"[:300]}

# Write the full structure separately, because the probe harness truncates
# values and these samples are the point of the exercise.
payload = {k: v["value"] for k, v in findings.items() if v["ok"]}
with open("/lakehouse/default/Files/sample_outputs.json", "w") as handle:
    json.dump(payload, handle, indent=2, default=str)

findings = {
    "__written__": {
        "ok": True,
        "value": f"{len(payload)} tables sampled to Files/sample_outputs.json",
    }
}
