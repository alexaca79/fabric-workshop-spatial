"""Remove the throwaway notebooks and files left behind while debugging.

The tracer, the probes and the smoke test all create real items in the live
workspaces. They are useful while investigating and clutter afterwards, and a
workshop workspace that students will look at should not be full of `zz_probe_`
notebooks.

Usage:
    python scripts/fabric_cleanup.py list     # show what would be removed
    python scripts/fabric_cleanup.py remove   # actually remove it
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fabric_notebook_runner import ENVIRONMENT, call, get_token  # noqa: E402

FABRIC = "https://api.fabric.microsoft.com"

# Anything matching these is scaffolding, not workshop material.
NOTEBOOK_PREFIXES = ("zz_probe_", "zz_trace_", "00_stac_diagnostic", "00_environment_verify")
SMOKE_TABLES = ("smoke_stand_register",)


def scaffolding_notebooks(layer: str, token: str) -> list[tuple[str, str]]:
    workspace_id = ENVIRONMENT[layer]["workspace_id"]
    _, listing = call("GET", f"{FABRIC}/v1/workspaces/{workspace_id}/notebooks", token)
    return [
        (item["id"], item["displayName"])
        for item in listing.get("value", [])
        if item.get("displayName", "").startswith(NOTEBOOK_PREFIXES)
    ]


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else "list"
    if action not in ("list", "remove"):
        print(__doc__)
        return 2

    token = get_token()
    total = 0

    for layer in ENVIRONMENT:
        workspace_id = ENVIRONMENT[layer]["workspace_id"]
        found = scaffolding_notebooks(layer, token)
        if not found:
            print(f"[{layer}] nothing to remove")
            continue

        print(f"[{layer}] {len(found)} scaffolding notebooks")
        for notebook_id, name in found:
            total += 1
            if action == "list":
                print(f"    would remove  {name}")
                continue
            status, _ = call(
                "DELETE", f"{FABRIC}/v1/workspaces/{workspace_id}/items/{notebook_id}", token
            )
            print(f"    {'removed ' if status in (200, 204) else f'FAILED {status}'}  {name}")

    if action == "list":
        print(f"\n{total} items would be removed. Re-run with 'remove' to do it.")
        print("\nThe smoke test table is not removed automatically. Drop it from a")
        print("notebook if you want it gone:")
        for table in SMOKE_TABLES:
            print(f"    spark.sql('DROP TABLE IF EXISTS {table}')")
    else:
        print(f"\n{total} items removed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
