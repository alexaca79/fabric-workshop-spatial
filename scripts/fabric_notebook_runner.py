"""Upload and run Fabric notebooks via the Fabric REST API.

Dependency free on purpose: uses urllib so it runs on a bare interpreter.
Auth comes from the already-signed-in Azure CLI.

Usage:
    python scripts/fabric_notebook_runner.py smoke
    python scripts/fabric_notebook_runner.py deploy <ipynb-path> <workspace> <display-name>
"""

from __future__ import annotations

import base64
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request

FABRIC = "https://api.fabric.microsoft.com"

# Environment provisioned by scripts/fabric_create_lakehouses.ps1.
ENVIRONMENT = {
    "bronze": {
        "workspace": "jdi-mock-training-bronze",
        "workspace_id": "de310cba-1e49-4608-9c25-55f297fb6dc7",
        "lakehouse": "lh_bronze",
        "lakehouse_id": "207c2a7d-52eb-4c1b-badc-162c21a5292d",
    },
    "silver": {
        "workspace": "jdi-mock-training-silver",
        "workspace_id": "0f742d8e-000b-4280-bf8e-c9157d5235c1",
        "lakehouse": "lh_silver",
        "lakehouse_id": "a5e9f744-5d18-4552-990f-a04a121a6466",
    },
    "gold": {
        "workspace": "jdi-mock-training-gold",
        "workspace_id": "da08264c-b08a-49c3-9dc1-e219913cbea7",
        "lakehouse": "lh_gold",
        "lakehouse_id": "e42f056d-3e4b-42bf-9ed7-6e7effdc78ab",
    },
}


def get_token() -> str:
    """Borrow an access token from the signed-in Azure CLI."""
    result = subprocess.run(
        [
            "az",
            "account",
            "get-access-token",
            "--resource",
            FABRIC,
            "--query",
            "accessToken",
            "-o",
            "tsv",
        ],
        capture_output=True,
        text=True,
        shell=True,
        check=True,
    )
    return result.stdout.strip()


def _decode(raw: str) -> dict:
    """Always hand back a dict, even for empty or null response bodies."""
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {"raw": raw}
    return parsed if isinstance(parsed, dict) else {"value": parsed}


def call(method: str, url: str, token: str, body: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request) as response:
            payload = _decode(response.read().decode())
            payload["_location"] = response.headers.get("Location", "")
            return response.status, payload
    except urllib.error.HTTPError as error:
        payload = _decode(error.read().decode())
        payload["_location"] = error.headers.get("Location", "")
        return error.code, payload


def build_notebook(cells: list[str], layer: str) -> dict:
    """Wrap source cells in an ipynb with the default lakehouse attached."""
    env = ENVIRONMENT[layer]
    return {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "language_info": {"name": "python"},
            "kernelspec": {"name": "synapse_pyspark", "display_name": "Synapse PySpark"},
            "dependencies": {
                "lakehouse": {
                    "default_lakehouse": env["lakehouse_id"],
                    "default_lakehouse_name": env["lakehouse"],
                    "default_lakehouse_workspace_id": env["workspace_id"],
                }
            },
        },
        "cells": [
            {
                "cell_type": "code",
                "source": source.splitlines(keepends=True),
                "metadata": {},
                "execution_count": None,
                "outputs": [],
            }
            for source in cells
        ],
    }


def find_notebook(display_name: str, layer: str, token: str) -> str | None:
    env = ENVIRONMENT[layer]
    _, listing = call("GET", f"{FABRIC}/v1/workspaces/{env['workspace_id']}/notebooks", token)
    for item in listing.get("value", []):
        if item.get("displayName") == display_name:
            return item["id"]
    return None


def deploy(notebook: dict, layer: str, display_name: str, token: str) -> str:
    env = ENVIRONMENT[layer]
    payload = base64.b64encode(json.dumps(notebook).encode()).decode()
    definition = {
        "format": "ipynb",
        "parts": [
            {
                "path": "notebook-content.ipynb",
                "payload": payload,
                "payloadType": "InlineBase64",
            }
        ],
    }

    status, body = call(
        "POST",
        f"{FABRIC}/v1/workspaces/{env['workspace_id']}/notebooks",
        token,
        {"displayName": display_name, "definition": definition},
    )

    if status == 409 or body.get("errorCode") == "ItemDisplayNameAlreadyInUse":
        # Already present: overwrite its definition so re-runs pick up edits.
        existing = find_notebook(display_name, layer, token)
        if not existing:
            raise SystemExit(f"name '{display_name}' taken but item not found")
        update_status, update_body = call(
            "POST",
            f"{FABRIC}/v1/workspaces/{env['workspace_id']}/items/{existing}/updateDefinition",
            token,
            {"definition": definition},
        )
        if update_status not in (200, 202):
            raise SystemExit(
                f"update failed ({update_status}): {json.dumps(update_body)[:600]}"
            )
        print(f"  reused existing notebook, definition updated")
        return existing

    if status not in (200, 201, 202):
        raise SystemExit(f"deploy failed ({status}): {json.dumps(body)[:600]}")

    notebook_id = body.get("id")
    if notebook_id:
        return notebook_id

    # Long-running create: poll until the item materialises.
    for _ in range(30):
        time.sleep(4)
        found = find_notebook(display_name, layer, token)
        if found:
            return found
    raise SystemExit("notebook created but id never surfaced")


def run(notebook_id: str, layer: str, token: str, timeout_s: int = 1500) -> dict:
    env = ENVIRONMENT[layer]
    base = f"{FABRIC}/v1/workspaces/{env['workspace_id']}/items/{notebook_id}"
    status, body = call("POST", f"{base}/jobs/instances?jobType=RunNotebook", token, {})
    if status not in (200, 201, 202):
        raise SystemExit(f"run failed ({status}): {json.dumps(body)[:600]}")

    location = body.get("_location", "")
    instance_id = location.rstrip("/").split("/")[-1] if location else None
    if not instance_id:
        raise SystemExit(f"no job instance id returned: {json.dumps(body)[:400]}")

    print(f"  job instance {instance_id}")
    deadline = time.time() + timeout_s
    last = ""
    while time.time() < deadline:
        time.sleep(15)
        _, job = call("GET", f"{base}/jobs/instances/{instance_id}", token)
        state = job.get("status", "?")
        if state != last:
            print(f"  status: {state}")
            last = state
        if state in ("Completed", "Failed", "Cancelled", "Deduped"):
            return job
    return {"status": "TimedOut"}


SMOKE_CELLS = [
    """# Smoke test: does Spark + Delta + OneLake actually work on this capacity?
import sys

print("python:", sys.version.split()[0])
print("spark :", spark.version)
""",
    """from pyspark.sql import Row

rows = [
    Row(stand_id=f"S-{i:03d}", licence_block="central-nb-block-a", area_ha=float(12 + i))
    for i in range(1, 6)
]
df = spark.createDataFrame(rows)
df.write.format("delta").mode("overwrite").saveAsTable("smoke_stand_register")
print("wrote smoke_stand_register")
""",
    """back = spark.table("smoke_stand_register")
print("row count:", back.count())
back.show()
assert back.count() == 5, "Delta round trip lost rows"
print("SMOKE TEST PASSED")
""",
]


DEPS_CELLS = [
    """# Probe the runtime WITHOUT ever raising, so the job always completes and
# always leaves a readable result behind in OneLake.
findings = {}


def record(key, fn):
    try:
        findings[key] = {"ok": True, "value": str(fn())[:400]}
    except Exception as error:  # noqa: BLE001 - probing, capture everything
        findings[key] = {"ok": False, "value": f"{type(error).__name__}: {error}"[:400]}


import sys

record("python", lambda: sys.version.split()[0])
record("spark", lambda: spark.version)
print("stage 1 done")
""",
    """# What is already in the runtime, before installing anything?
import importlib

BASELINE = [
    "geopandas", "shapely", "rasterio", "xarray", "numpy", "pandas",
    "pystac_client", "planetary_computer", "odc.stac", "rioxarray",
]

for name in BASELINE:
    def probe(n=name):
        return importlib.import_module(n).__version__

    record(f"baseline::{name}", probe)

print("stage 2 done")
""",
    """# Try the install. Use pip via subprocess rather than the %pip magic, because
# the magic aborts the whole session on failure during a scheduled job run.
import subprocess

def pip_install():
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--quiet",
         "pystac-client", "planetary-computer", "odc-stac", "rioxarray"],
        capture_output=True, text=True, timeout=900,
    )
    return f"rc={result.returncode} err={result.stderr[-300:]}"

record("pip_install", pip_install)
print("stage 3 done")
""",
    """# Re-probe the packages that mattered, after the install attempt.
for name in ["pystac_client", "planetary_computer", "odc.stac", "rioxarray"]:
    importlib.invalidate_caches()

    def probe(n=name):
        return importlib.import_module(n).__version__

    record(f"postinstall::{name}", probe)

print("stage 4 done")
""",
    """# Can we reach the Planetary Computer STAC API from Fabric Spark?
def stac_probe():
    import planetary_computer as pc
    from pystac_client import Client

    catalog = Client.open(
        "https://planetarycomputer.microsoft.com/api/stac/v1",
        modifier=pc.sign_inplace,
    )
    items = list(
        catalog.search(
            collections=["sentinel-2-l2a"],
            bbox=[-66.90, 46.10, -66.40, 46.40],
            datetime="2024-07-01/2024-08-31",
            query={"eo:cloud_cover": {"lt": 20}},
            max_items=5,
        ).items()
    )
    return f"{len(items)} scenes: " + ", ".join(i.id for i in items[:3])

record("stac_search", stac_probe)
print("stage 5 done")
""",
    """# Persist findings to OneLake so the result survives regardless of job status.
import json

payload = json.dumps(findings, indent=2)
path = "/lakehouse/default/Files/probe_result.json"
import os

os.makedirs(os.path.dirname(path), exist_ok=True)
with open(path, "w", encoding="utf-8") as handle:
    handle.write(payload)

print(payload)
print("stage 6 done - findings written to Files/probe_result.json")
""",
]


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode not in ("smoke", "deps"):
        print(__doc__)
        raise SystemExit(1)

    cells, name, note = {
        "smoke": (SMOKE_CELLS, "00_smoke_test", "Spark session startup, ~2-4 min"),
        "deps": (DEPS_CELLS, "00_dependency_probe", "pip install + STAC call, ~5-8 min"),
    }[mode]

    token = get_token()
    print(f"deploying {name} to bronze...")
    notebook_id = deploy(build_notebook(cells, "bronze"), "bronze", name, token)
    print(f"  notebook id {notebook_id}")

    print(f"running ({note})...")
    job = run(notebook_id, "bronze", token)
    print(f"\nfinal status: {job.get('status')}")
    if job.get("failureReason"):
        print(f"failure: {json.dumps(job['failureReason'])[:900]}")


if __name__ == "__main__":
    main()
