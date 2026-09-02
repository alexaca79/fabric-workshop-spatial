"""Run the whole workshop pipeline end to end in the live Fabric workspaces.

Each solution notebook is uploaded into the workspace for its medallion layer,
bound to the published `env_forestops` Environment and to that layer's default
lakehouse, then executed. Cross-layer reads travel over OneLake shortcuts, so
the shortcut script has to run between stages, not before them: a shortcut to a
table that does not exist yet is rejected.

Dependency free on purpose: urllib only, token borrowed from the Azure CLI.

Usage:
    python scripts/fabric_run_pipeline.py all
    python scripts/fabric_run_pipeline.py stage 00 01
    python scripts/fabric_run_pipeline.py from 03
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SOLUTIONS = REPO_ROOT / "notebooks" / "solutions"
LOG_DIR = REPO_ROOT / "scripts" / ".run-logs"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fabric_environment import find_environment, publish_state  # noqa: E402
from fabric_notebook_runner import ENVIRONMENT, deploy, get_token, run  # noqa: E402

# Execution order. Notebooks 00 and 01 both write bronze but do not read each
# other, so their relative order does not matter. Everything after that is a
# strict chain.
PIPELINE: list[tuple[str, str]] = [
    ("00_setup_lakehouse_and_config", "bronze"),
    ("01_bronze_stac_ingest", "bronze"),
    ("02_silver_reproject_and_indices", "silver"),
    ("03_gold_forest_classification", "gold"),
    ("04_gold_ai_enrichment_foundry", "gold"),
    ("05_publish_and_validate", "gold"),
    ("06_publish_fabric_app_snapshot", "gold"),
]

# After these stages, new upstream tables exist, so the table shortcuts that
# feed the next layer can finally be created.
SHORTCUT_AFTER = {"01_bronze_stac_ingest", "02_silver_reproject_and_indices"}


def bind(path: Path, layer: str, environment_id: str) -> dict:
    """Load a solution notebook and point it at the right Environment and lakehouse.

    The notebook source is untouched. Only the Fabric-specific `dependencies`
    metadata is injected, which is exactly what the portal writes when a user
    picks an Environment and a default lakehouse from the ribbon.
    """
    notebook = json.loads(path.read_text(encoding="utf-8"))
    env = ENVIRONMENT[layer]
    notebook.setdefault("metadata", {})
    notebook["metadata"]["dependencies"] = {
        "environment": {
            "environmentId": environment_id,
            "workspaceId": env["workspace_id"],
        },
        "lakehouse": {
            "default_lakehouse": env["lakehouse_id"],
            "default_lakehouse_name": env["lakehouse"],
            "default_lakehouse_workspace_id": env["workspace_id"],
        },
    }
    # Fabric wants a kernel it recognises; nbformat writes a generic one.
    notebook["metadata"]["kernelspec"] = {
        "name": "synapse_pyspark",
        "display_name": "Synapse PySpark",
        "language": "python",
    }
    return notebook


def create_shortcuts() -> None:
    """Run the shortcut script. PENDING rows are expected and not fatal."""
    script = REPO_ROOT / "scripts" / "fabric_create_shortcuts.ps1"
    print("\n--- creating table shortcuts ---")
    result = subprocess.run(
        ["pwsh", "-NoProfile", "-File", str(script), "-Tables"],
        capture_output=True,
        text=True,
        check=False,
    )
    print(result.stdout.strip() or "(no output)")
    if result.stderr.strip():
        print(f"  stderr: {result.stderr.strip()[:500]}")
    print("--- shortcuts done ---\n")


def resolve_environments(token: str) -> dict[str, str]:
    """Look the Environment id up per layer, and refuse to run if it is not published."""
    resolved = {}
    for layer, env in ENVIRONMENT.items():
        environment_id = find_environment(env["workspace_id"], token)
        if not environment_id:
            raise SystemExit(f"no env_forestops Environment in {layer}; run fabric_environment.py build")
        state = publish_state(env["workspace_id"], environment_id, token)
        if state != "Success":
            raise SystemExit(f"{layer} Environment publish state is {state}, not Success")
        resolved[layer] = environment_id
        print(f"  {layer:<7} environment {environment_id} ({state})")
    return resolved


def execute(stages: list[tuple[str, str]]) -> int:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc)
    log_path = LOG_DIR / f"pipeline-{started.strftime('%Y%m%dT%H%M%SZ')}.json"

    token = get_token()
    print("resolving environments...")
    environments = resolve_environments(token)

    results = []
    for index, (stem, layer) in enumerate(stages, start=1):
        path = SOLUTIONS / f"{stem}.ipynb"
        if not path.exists():
            raise SystemExit(f"missing notebook: {path}")

        print(f"\n=== [{index}/{len(stages)}] {stem}  ->  {layer} ===")
        token = get_token()  # long runs outlive a single token
        notebook = bind(path, layer, environments[layer])

        print("  deploying...")
        notebook_id = deploy(notebook, layer, stem, token)
        print(f"  notebook id {notebook_id}")

        print("  running (Environment-backed sessions start slowly)...")
        began = time.time()
        job = run(notebook_id, layer, token, timeout_s=3600)
        elapsed = round(time.time() - began)
        status = job.get("status", "?")

        entry = {
            "notebook": stem,
            "layer": layer,
            "notebook_id": notebook_id,
            "status": status,
            "seconds": elapsed,
        }
        failure = job.get("failureReason") or {}
        if failure:
            entry["failure"] = str(failure)[:1000]
        results.append(entry)

        print(f"  {status} in {elapsed}s")
        if status != "Completed":
            print(f"  FAILURE DETAIL: {json.dumps(failure)[:800]}")
            log_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
            print(f"\nstopped at {stem}. log: {log_path}")
            return 1

        if stem in SHORTCUT_AFTER:
            create_shortcuts()

    log_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    total = sum(r["seconds"] for r in results)
    print(f"\nall {len(results)} notebooks completed in {total}s ({total // 60}m)")
    print(f"log: {log_path}")
    return 0


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 2

    mode = args[0]
    if mode == "all":
        stages = PIPELINE
    elif mode == "stage":
        wanted = set(args[1:])
        stages = [(s, l) for s, l in PIPELINE if s.split("_")[0] in wanted]
    elif mode == "from":
        prefix = args[1]
        start = next(i for i, (s, _) in enumerate(PIPELINE) if s.startswith(prefix))
        stages = PIPELINE[start:]
    else:
        print(__doc__)
        return 2

    if not stages:
        print("no matching stages")
        return 2
    return execute(stages)


if __name__ == "__main__":
    raise SystemExit(main())
