"""Run a solution notebook cell by cell in Fabric and report the first cell that raises.

Fabric returns `System_Cancelled_Session_Statements_Failed` for any notebook job
whose code raises. That error names no cell, no line and no exception type, which
makes a failing notebook nearly undebuggable from the API alone.

This tool takes the real notebook, base64-encodes each code cell, and executes
them in order inside one harness cell that catches everything. The first failure
is recorded with its traceback and the run stops there, mirroring what a real run
does while leaving the evidence behind in OneLake.

Usage:
    python scripts/fabric_trace_notebook.py 01_bronze_stac_ingest bronze
"""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SOLUTIONS = REPO_ROOT / "notebooks" / "solutions"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fabric_environment import find_environment  # noqa: E402
from fabric_notebook_runner import ENVIRONMENT, deploy, get_token, run  # noqa: E402

HARNESS = '''
import base64
import json
import traceback

SOURCES = {sources}
OUTPUT = "/lakehouse/default/Files/{output}"

results = []
namespace = globals()

for index, encoded in enumerate(SOURCES):
    source = base64.b64decode(encoded).decode()
    head = next((line for line in source.splitlines() if line.strip()), "")[:120]
    try:
        exec(compile(source, f"<cell-{{index}}>", "exec"), namespace)
        results.append({{"cell": index, "ok": True, "head": head}})
        print(f"[ok  ] cell {{index}}: {{head}}")
    except Exception:
        detail = traceback.format_exc()
        results.append({{"cell": index, "ok": False, "head": head, "error": detail[-3000:]}})
        print(f"[FAIL] cell {{index}}: {{head}}")
        print(detail[-3000:])
        break

with open(OUTPUT, "w") as handle:
    json.dump(results, handle, indent=2)

failed = [r for r in results if not r["ok"]]
print(f"\\n{{len(results)}} cells executed, {{len(failed)}} failed -> {{OUTPUT}}")
'''


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    stem, layer = sys.argv[1], sys.argv[2]

    path = SOLUTIONS / f"{stem}.ipynb"
    if not path.exists():
        raise SystemExit(f"missing notebook: {path}")

    source_notebook = json.loads(path.read_text(encoding="utf-8"))
    code_cells = [
        "".join(cell["source"]) if isinstance(cell["source"], list) else cell["source"]
        for cell in source_notebook["cells"]
        if cell["cell_type"] == "code"
    ]
    encoded = [base64.b64encode(cell.encode()).decode() for cell in code_cells]
    print(f"{stem}: {len(code_cells)} code cells")

    harness = HARNESS.format(
        sources=json.dumps(encoded, indent=0),
        output=f"trace_{stem}.json",
    )

    token = get_token()
    env = ENVIRONMENT[layer]
    environment_id = find_environment(env["workspace_id"], token)
    if not environment_id:
        raise SystemExit(f"no env_forestops Environment in {layer}")

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
            {"cell_type": "code", "source": harness.splitlines(keepends=True),
             "metadata": {}, "execution_count": None, "outputs": []}
        ],
    }

    name = f"zz_trace_{stem}"
    print(f"deploying {name} to {layer}...")
    notebook_id = deploy(notebook, layer, name, token)
    print("running...")
    job = run(notebook_id, layer, token, timeout_s=3600)
    print(f"status: {job.get('status')}")
    print(f"\nfetch the trace:")
    print(f"  pwsh -NoProfile -File scripts/fabric_fetch_json.ps1 {layer} trace_{stem}.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
