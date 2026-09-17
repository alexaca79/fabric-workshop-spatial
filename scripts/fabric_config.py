"""Load the Fabric target environment from scripts/env.json.

Every deploy script used to carry its own copy of the workspace and lakehouse
GUIDs, which meant a new tenant needed nine files edited consistently or
nothing worked. They all read this instead.

The exported names and shapes match what the scripts expected before, so
importing modules did not have to change:

    ENVIRONMENT[layer] -> {workspace, workspace_id, lakehouse, lakehouse_id}
    WORKSPACES[layer]  -> workspace id
    LAKEHOUSES[layer]  -> (lakehouse name, lakehouse id)
"""

from __future__ import annotations

import json
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent / "env.json"
LAYERS = ("bronze", "silver", "gold")


def _load() -> dict:
    if not CONFIG_PATH.exists():
        raise SystemExit(
            f"missing {CONFIG_PATH}. Copy the workspace and lakehouse ids for your "
            "tenant into it before running any deploy script."
        )
    try:
        raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{CONFIG_PATH} is not valid JSON: {exc}") from exc

    layers = raw.get("layers")
    if not isinstance(layers, dict):
        raise SystemExit(f"{CONFIG_PATH} has no 'layers' object")

    for layer in LAYERS:
        entry = layers.get(layer)
        if not isinstance(entry, dict):
            raise SystemExit(f"{CONFIG_PATH} is missing the '{layer}' layer")
        for field in ("workspace", "workspaceId", "lakehouse", "lakehouseId"):
            if not entry.get(field):
                raise SystemExit(
                    f"{CONFIG_PATH}: layer '{layer}' has no '{field}'. "
                    "Lakehouse ids are only known after fabric_create_lakehouses.ps1 "
                    "has run; paste them in before continuing."
                )
    return raw


_CONFIG = _load()

ENVIRONMENT_NAME: str = _CONFIG.get("environmentName", "env_forestops")

ENVIRONMENT: dict[str, dict[str, str]] = {
    layer: {
        "workspace": _CONFIG["layers"][layer]["workspace"],
        "workspace_id": _CONFIG["layers"][layer]["workspaceId"],
        "lakehouse": _CONFIG["layers"][layer]["lakehouse"],
        "lakehouse_id": _CONFIG["layers"][layer]["lakehouseId"],
    }
    for layer in LAYERS
}

WORKSPACES: dict[str, str] = {
    layer: ENVIRONMENT[layer]["workspace_id"] for layer in LAYERS
}

LAKEHOUSES: dict[str, tuple[str, str]] = {
    layer: (ENVIRONMENT[layer]["lakehouse"], ENVIRONMENT[layer]["lakehouse_id"])
    for layer in LAYERS
}
