"""Validate scripts/env.json before running any deploy script.

A wrong or half-filled env.json fails late and confusingly: the Fabric API
returns a 400 or an empty listing rather than saying the id was malformed.
This checks the shape up front and prints what the scripts will actually use.

Usage:
    python scripts/check_env_config.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

GUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")

problems: list[str] = []

try:
    from fabric_config import CONFIG_PATH, ENVIRONMENT, ENVIRONMENT_NAME, LAYERS
except SystemExit as exc:
    print(f"env.json rejected: {exc}")
    raise

print(f"config: {CONFIG_PATH}")
print(f"environment name: {ENVIRONMENT_NAME}\n")

for layer in LAYERS:
    entry = ENVIRONMENT[layer]
    print(f"[{layer}]")
    print(f"  workspace  {entry['workspace']}  {entry['workspace_id']}")
    print(f"  lakehouse  {entry['lakehouse']}  {entry['lakehouse_id']}")

    for field in ("workspace_id", "lakehouse_id"):
        if not GUID.match(entry[field]):
            problems.append(f"{layer}.{field} is not a GUID: {entry[field]!r}")

ids = [ENVIRONMENT[layer]["workspace_id"] for layer in LAYERS]
if len(set(ids)) != len(ids):
    problems.append(
        "two layers share a workspace id. If you are deliberately running all "
        "three layers in one workspace, that is fine, but the shortcut scripts "
        "will try to create a shortcut from a lakehouse to itself."
    )

lakehouse_ids = [ENVIRONMENT[layer]["lakehouse_id"] for layer in LAYERS]
if len(set(lakehouse_ids)) != len(lakehouse_ids):
    problems.append("two layers share a lakehouse id, which cannot be right")

print()
if problems:
    for problem in problems:
        print(f"PROBLEM: {problem}")
    sys.exit(1)
print("env.json looks usable")
