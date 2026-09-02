"""Build and publish the Fabric Environment carrying the workshop library stack.

The Fabric Spark base runtime has none of the geospatial or STAC packages, and
installing them ad hoc via %pip corrupts the base (see environments/environment.yml).
A published Environment resolves the set once and attaches cleanly to notebooks.

Dependency free on purpose: urllib only, auth borrowed from the Azure CLI.

Usage:
    python scripts/fabric_environment.py build  <layer>   # create + upload + publish
    python scripts/fabric_environment.py status <layer>   # poll publish state
    python scripts/fabric_environment.py verify <layer>   # run an import check
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

FABRIC = "https://api.fabric.microsoft.com"
ENVIRONMENT_NAME = "env_forestops"
REPO_ROOT = Path(__file__).resolve().parent.parent
ENVIRONMENT_YML = REPO_ROOT / "environments" / "environment.yml"

WORKSPACES = {
    "bronze": "de310cba-1e49-4608-9c25-55f297fb6dc7",
    "silver": "0f742d8e-000b-4280-bf8e-c9157d5235c1",
    "gold": "da08264c-b08a-49c3-9dc1-e219913cbea7",
}

LAKEHOUSES = {
    "bronze": ("lh_bronze", "207c2a7d-52eb-4c1b-badc-162c21a5292d"),
    "silver": ("lh_silver", "a5e9f744-5d18-4552-990f-a04a121a6466"),
    "gold": ("lh_gold", "e42f056d-3e4b-42bf-9ed7-6e7effdc78ab"),
}


def get_token() -> str:
    result = subprocess.run(
        ["az", "account", "get-access-token", "--resource", FABRIC,
         "--query", "accessToken", "-o", "tsv"],
        capture_output=True, text=True, shell=True, check=True,
    )
    return result.stdout.strip()


def _decode(raw: str) -> dict:
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


def post_file(url: str, token: str, path: Path) -> tuple[int, dict]:
    """Raw octet-stream upload.

    The API rejects multipart/form-data with EnvironmentValidationFailed
    ("Expected content type application/octet-stream"), so send the bare bytes.
    """
    request = urllib.request.Request(url, data=path.read_bytes(), method="POST")
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("Content-Type", "application/octet-stream")
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, _decode(response.read().decode())
    except urllib.error.HTTPError as error:
        return error.code, _decode(error.read().decode())


def find_environment(workspace_id: str, token: str) -> str | None:
    _, listing = call("GET", f"{FABRIC}/v1/workspaces/{workspace_id}/environments", token)
    for item in listing.get("value", []):
        if item.get("displayName") == ENVIRONMENT_NAME:
            return item["id"]
    return None


def ensure_environment(workspace_id: str, token: str) -> str:
    existing = find_environment(workspace_id, token)
    if existing:
        print(f"  environment exists: {existing}")
        return existing

    status, body = call(
        "POST", f"{FABRIC}/v1/workspaces/{workspace_id}/environments", token,
        {
            "displayName": ENVIRONMENT_NAME,
            "description": "Geospatial + STAC stack for the JDI Woodlands workshop.",
        },
    )
    if status not in (200, 201, 202):
        raise SystemExit(f"create environment failed ({status}): {json.dumps(body)[:600]}")

    environment_id = body.get("id")
    if environment_id:
        print(f"  environment created: {environment_id}")
        return environment_id

    for _ in range(30):
        time.sleep(4)
        found = find_environment(workspace_id, token)
        if found:
            print(f"  environment created: {found}")
            return found
    raise SystemExit("environment created but id never surfaced")


def publish_state(workspace_id: str, environment_id: str, token: str) -> str:
    _, body = call(
        "GET", f"{FABRIC}/v1/workspaces/{workspace_id}/environments/{environment_id}", token
    )
    details = (body.get("properties") or {}).get("publishDetails") or {}
    return details.get("state", "Unknown")


def build(layer: str, token: str) -> None:
    workspace_id = WORKSPACES[layer]
    print(f"[{layer}] ensuring environment...")
    environment_id = ensure_environment(workspace_id, token)

    print(f"[{layer}] uploading environment.yml...")
    status, body = post_file(
        f"{FABRIC}/v1/workspaces/{workspace_id}/environments/{environment_id}"
        "/staging/libraries/importExternalLibraries",
        token,
        ENVIRONMENT_YML,
    )
    if status not in (200, 201, 202):
        raise SystemExit(f"library import failed ({status}): {json.dumps(body)[:800]}")
    print("  libraries staged")

    print(f"[{layer}] publishing (first build resolves the whole stack, expect 10-20 min)...")
    status, body = call(
        "POST",
        f"{FABRIC}/v1/workspaces/{workspace_id}/environments/{environment_id}/staging/publish",
        token, {},
    )
    if status not in (200, 201, 202):
        raise SystemExit(f"publish failed ({status}): {json.dumps(body)[:800]}")

    print(f"  publish triggered. environment id: {environment_id}")
    print(f"  poll with: python scripts/fabric_environment.py status {layer}")


def status(layer: str, token: str) -> None:
    workspace_id = WORKSPACES[layer]
    environment_id = find_environment(workspace_id, token)
    if not environment_id:
        raise SystemExit(f"no environment named {ENVIRONMENT_NAME} in {layer}")
    print(f"[{layer}] {environment_id}: {publish_state(workspace_id, environment_id, token)}")


def wait(layer: str, token: str, timeout_s: int = 2700) -> None:
    """Block until the publish reaches a terminal state.

    Refreshes the token each poll because a first build can outlive it.
    """
    workspace_id = WORKSPACES[layer]
    environment_id = find_environment(workspace_id, token)
    if not environment_id:
        raise SystemExit(f"no environment named {ENVIRONMENT_NAME} in {layer}")

    terminal = {"Success", "Failed", "Cancelled"}
    deadline = time.time() + timeout_s
    last = ""
    started = time.time()

    while time.time() < deadline:
        state = publish_state(workspace_id, environment_id, get_token())
        if state != last:
            print(f"  [{int(time.time() - started):5d}s] {state}", flush=True)
            last = state
        if state in terminal:
            if state != "Success":
                raise SystemExit(f"publish ended in {state}")
            print(f"[{layer}] published successfully: {environment_id}")
            return
        time.sleep(30)

    raise SystemExit(f"timed out after {timeout_s}s, last state {last}")


VERIFY_CELLS = [
    """# Verify the published Environment WITHOUT raising, so the job always
# completes and always leaves a readable result behind in OneLake.
# A bare assert here cancels the Spark session and hides which check failed.
findings = {}


def record(key, fn):
    try:
        findings[key] = {"ok": True, "value": str(fn())[:400]}
    except Exception as error:  # noqa: BLE001 - verifying, capture everything
        findings[key] = {"ok": False, "value": f"{type(error).__name__}: {error}"[:400]}


import importlib
import sys

record("python", lambda: sys.version.split()[0])
record("spark", lambda: spark.version)

for name in [
    "numpy", "pandas", "shapely", "geopandas", "pyproj",
    "rasterio", "xarray", "rioxarray",
    "pystac_client", "planetary_computer", "odc.stac",
]:
    def probe(n=name):
        return importlib.import_module(n).__version__

    record(f"import::{name}", probe)

print("imports probed")
""",
    """# The base runtime must survive: pandas 3.x here means the resolver won.
def pandas_guard():
    import pandas as pd

    major = int(pd.__version__.split(".")[0])
    if major != 2:
        raise RuntimeError(f"pandas upgraded to {pd.__version__}, base runtime compromised")
    return f"pandas {pd.__version__} intact"


def numpy_guard():
    import numpy as np

    major = int(np.__version__.split(".")[0])
    if major != 1:
        raise RuntimeError(f"numpy upgraded to {np.__version__}, base runtime compromised")
    return f"numpy {np.__version__} intact"


record("guard::pandas", pandas_guard)
record("guard::numpy", numpy_guard)
print("guards probed")
""",
    """# End to end: sign and query the Planetary Computer STAC API.
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
    if not items:
        raise RuntimeError("STAC search returned no scenes")
    return f"{len(items)} scenes: " + ", ".join(i.id for i in items[:3])


record("stac_search", stac_probe)
print("stac probed")
""",
    """# Persist findings to OneLake so the result survives regardless of job status.
import json
import os

payload = json.dumps(findings, indent=2)
path = "/lakehouse/default/Files/environment_verify.json"
os.makedirs(os.path.dirname(path), exist_ok=True)
with open(path, "w", encoding="utf-8") as handle:
    handle.write(payload)

failures = [k for k, v in findings.items() if not v["ok"]]
print(payload)
print()
print(f"FAILURES: {failures}" if failures else "ENVIRONMENT VERIFIED - all checks passed")
""",
]


def verify(layer: str, token: str) -> None:
    """Deploy and run an import check bound to the published Environment."""
    workspace_id = WORKSPACES[layer]
    environment_id = find_environment(workspace_id, token)
    if not environment_id:
        raise SystemExit(f"no environment named {ENVIRONMENT_NAME} in {layer}")

    state = publish_state(workspace_id, environment_id, token)
    if state != "Success":
        raise SystemExit(f"environment publish state is {state}, not Success - wait and retry")

    lakehouse_name, lakehouse_id = LAKEHOUSES[layer]
    notebook = {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "language_info": {"name": "python"},
            "kernelspec": {"name": "synapse_pyspark", "display_name": "Synapse PySpark"},
            "dependencies": {
                "environment": {
                    "environmentId": environment_id,
                    "workspaceId": workspace_id,
                },
                "lakehouse": {
                    "default_lakehouse": lakehouse_id,
                    "default_lakehouse_name": lakehouse_name,
                    "default_lakehouse_workspace_id": workspace_id,
                },
            },
        },
        "cells": [
            {"cell_type": "code", "source": source.splitlines(keepends=True),
             "metadata": {}, "execution_count": None, "outputs": []}
            for source in VERIFY_CELLS
        ],
    }

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from fabric_notebook_runner import deploy, run  # noqa: PLC0415 - reuse the runner

    name = "00_environment_verify"
    print(f"[{layer}] deploying {name} bound to environment {environment_id}...")
    notebook_id = deploy(notebook, layer, name, token)
    print(f"  notebook id {notebook_id}")
    print("  running (Environment-backed sessions start slower, allow ~5 min)...")
    job = run(notebook_id, layer, token)
    print(f"\nfinal status: {job.get('status')}")
    if job.get("failureReason"):
        print(f"failure: {json.dumps(job['failureReason'])[:900]}")


def main() -> None:
    actions = ("build", "status", "wait", "verify")
    if len(sys.argv) < 3 or sys.argv[1] not in actions:
        print(__doc__)
        raise SystemExit(1)

    action, layer = sys.argv[1], sys.argv[2]
    if layer not in WORKSPACES:
        raise SystemExit(f"unknown layer '{layer}', expected one of {list(WORKSPACES)}")

    token = get_token()
    {"build": build, "status": status, "wait": wait, "verify": verify}[action](layer, token)


if __name__ == "__main__":
    main()
