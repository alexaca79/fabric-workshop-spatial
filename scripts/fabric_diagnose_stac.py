"""Reproduce notebook 01's ingest steps defensively to find where it actually fails.

A raise inside a Fabric notebook job cancels the Spark session and the API
returns only `System_Cancelled_Session_Statements_Failed`, which names no cell
and no exception. So this probe never raises: every step is wrapped, the result
is recorded, and the findings are written to OneLake as JSON for download.

Usage:
    python scripts/fabric_diagnose_stac.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fabric_environment import find_environment  # noqa: E402
from fabric_notebook_runner import ENVIRONMENT, deploy, get_token, run  # noqa: E402

LAYER = "bronze"

PROBE_CELLS = [
    '''findings = {}


def step(key, fn):
    """Record the outcome of one step without ever letting it raise."""
    try:
        findings[key] = {"ok": True, "value": str(fn())[:800]}
    except Exception as exc:
        findings[key] = {"ok": False, "value": f"{type(exc).__name__}: {exc}"[:800]}
    print(f"[{'ok ' if findings[key]['ok'] else 'FAIL'}] {key}: {findings[key]['value'][:200]}")


step("import_pystac_client", lambda: __import__("pystac_client").__version__)
step("import_planetary_computer", lambda: __import__("planetary_computer").__version__)
step("import_odc_stac", lambda: __import__("odc.stac", fromlist=["load"]).__name__)
step("import_rioxarray", lambda: __import__("rioxarray").__version__)
''',
    '''import planetary_computer as pc
import pystac_client

AOI_BBOX = (-66.90, 46.10, -66.40, 46.40)
STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
COLLECTION = "sentinel-2-l2a"

catalog = None


def open_catalog():
    global catalog
    catalog = pystac_client.Client.open(STAC_URL, modifier=pc.sign_inplace)
    return catalog.id


step("open_catalog", open_catalog)


def search(date_start, date_end, max_cloud):
    result = catalog.search(
        collections=[COLLECTION],
        bbox=list(AOI_BBOX),
        datetime=f"{date_start}/{date_end}",
        query={"eo:cloud_cover": {"lt": max_cloud}},
    )
    items = list(result.items())
    return f"{len(items)} items: " + ", ".join(
        f"{i.id[:30]}@{i.properties['datetime'][:10]}" for i in items[:4]
    )


# The exact window notebook 01 asks for.
step("search_2026_summer_cloud20", lambda: search("2026-06-01", "2026-08-31", 20.0))
# Widen progressively so we can tell a bad window from a bad query.
step("search_2026_summer_cloud60", lambda: search("2026-06-01", "2026-08-31", 60.0))
step("search_2026_full_year", lambda: search("2026-01-01", "2026-12-31", 100.0))
step("search_2025_summer", lambda: search("2025-06-01", "2025-08-31", 20.0))
step("search_any_cloud_any_date", lambda: search("2020-01-01", "2026-12-31", 100.0))
''',
    '''import json

path = "/lakehouse/default/Files/stac_diagnostic.json"
with open(path, "w") as handle:
    json.dump(findings, handle, indent=2)
print(f"wrote {path}")

failures = [k for k, v in findings.items() if not v["ok"]]
print(f"FAILURES: {failures}" if failures else "no step raised")
''',
]


def main() -> int:
    token = get_token()
    env = ENVIRONMENT[LAYER]
    environment_id = find_environment(env["workspace_id"], token)
    if not environment_id:
        raise SystemExit("no env_forestops Environment in bronze")

    notebook = {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "language_info": {"name": "python"},
            "kernelspec": {"name": "synapse_pyspark", "display_name": "Synapse PySpark"},
            "dependencies": {
                "environment": {"environmentId": environment_id, "workspaceId": env["workspace_id"]},
                "lakehouse": {
                    "default_lakehouse": env["lakehouse_id"],
                    "default_lakehouse_name": env["lakehouse"],
                    "default_lakehouse_workspace_id": env["workspace_id"],
                },
            },
        },
        "cells": [
            {"cell_type": "code", "source": source.splitlines(keepends=True),
             "metadata": {}, "execution_count": None, "outputs": []}
            for source in PROBE_CELLS
        ],
    }

    name = "00_stac_diagnostic"
    print(f"deploying {name}...")
    notebook_id = deploy(notebook, LAYER, name, token)
    print("running...")
    job = run(notebook_id, LAYER, token, timeout_s=1200)
    print(f"status: {job.get('status')}")
    print(json.dumps(job.get("failureReason") or {}, indent=2)[:600])
    print("\nnow download the findings:")
    print("  pwsh -File scripts/fabric_fetch_json.ps1 bronze stac_diagnostic.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
