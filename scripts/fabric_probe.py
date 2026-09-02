"""Run an arbitrary Python probe in a Fabric session and bring the findings back.

The probe file must build a dict named `findings`. This harness dumps it to
OneLake so it can be downloaded, because notebook stdout is not retrievable
through the jobs API.

Usage:
    python scripts/fabric_probe.py bronze scripts/probes/versions.py versions.json
"""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fabric_environment import find_environment  # noqa: E402
from fabric_notebook_runner import ENVIRONMENT, deploy, get_token, run  # noqa: E402

HARNESS = '''
import base64
import json
import traceback

findings = {{}}
source = base64.b64decode("{encoded}").decode()
try:
    exec(compile(source, "<probe>", "exec"), globals())
except Exception:
    findings["__harness__"] = {{"ok": False, "value": traceback.format_exc()[-2000:]}}

with open("/lakehouse/default/Files/{output}", "w") as handle:
    json.dump(findings, handle, indent=2, default=str)
print(json.dumps(findings, indent=2, default=str)[:4000])
'''


def main() -> int:
    if len(sys.argv) < 4:
        print(__doc__)
        return 2
    layer, probe_path, output = sys.argv[1], Path(sys.argv[2]), sys.argv[3]

    encoded = base64.b64encode(probe_path.read_text(encoding="utf-8").encode()).decode()
    harness = HARNESS.format(encoded=encoded, output=output)

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

    name = f"zz_probe_{probe_path.stem}"
    print(f"deploying {name} to {layer}...")
    notebook_id = deploy(notebook, layer, name, token)
    print("running...")
    job = run(notebook_id, layer, token, timeout_s=1800)
    print(f"status: {job.get('status')}")
    print(f"  pwsh -NoProfile -File scripts/fabric_fetch_json.ps1 {layer} {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
