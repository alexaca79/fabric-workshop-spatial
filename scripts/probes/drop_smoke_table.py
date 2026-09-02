"""Drop the smoke-test table left over from the first capacity check."""

def record(key, fn):
    try:
        findings[key] = {"ok": True, "value": str(fn())[:400]}
    except Exception as exc:
        findings[key] = {"ok": False, "value": f"{type(exc).__name__}: {exc}"[:400]}


record("drop_smoke_table",
       lambda: spark.sql("DROP TABLE IF EXISTS smoke_stand_register") and "dropped")
record("remaining_tables",
       lambda: [t.name for t in spark.catalog.listTables()])
