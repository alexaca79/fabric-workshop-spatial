"""Prepare bound, instrumented Fabric definitions without editing learner notebooks.

Usage: python scripts/prepare_independent_rehearsal.py STATE_JSON OUTPUT_DIRECTORY
"""

from __future__ import annotations

import argparse
import ast
import base64
import copy
import hashlib
import io
import json
import sys
import textwrap
import tokenize
from pathlib import Path
from uuid import UUID

import nbformat

ROOT = Path(__file__).resolve().parents[1]
LAB_TABLES = (
    ("bronze_stand_register",),
    ("bronze_scene_catalog",),
    ("silver_stand_observations",),
    ("gold_stand_classification", "gold_stand_change"),
    ("gold_stand_narrative",),
    ("bronze_stand_register", "bronze_scene_catalog", "silver_stand_observations",
     "gold_stand_classification", "gold_stand_change", "gold_stand_narrative",
     "gold_stand_facts", "gold_dim_stand", "gold_dim_date", "gold_dim_forest_class",
     "gold_pipeline_run_summary"),
)


def retarget_labels(source: str, workspace_name: str, lakehouse_name: str, input_mode: str | None = None) -> str:
    """Change only known display labels and an explicitly selected input route."""
    lines = source.splitlines(keepends=True)
    targets = {"WORKSPACE": ({"fabric-training"}, workspace_name),
               "LAKEHOUSE": ({"lh_woodlands"}, lakehouse_name)}
    if input_mode is not None:
        if input_mode not in {"stac", "manual"}:
            raise ValueError("Unsupported rehearsal input route")
        targets["INPUT_MODE"] = ({"stac", "manual"}, input_mode)
    for node in ast.parse(source).body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            continue
        name = node.targets[0].id
        if name not in targets:
            continue
        previous, replacement = targets[name]
        if not isinstance(node.value, ast.Constant) or node.value.value not in previous or node.lineno != node.end_lineno:
            raise ValueError(f"Unexpected {name} assignment in released solution")
        ending = "\n" if lines[node.lineno - 1].endswith("\n") else ""
        lines[node.lineno - 1] = f"{name} = {replacement!r}{ending}"
    return "".join(lines)


def indent_code(source: str) -> str:
    """Indent statements without adding whitespace inside multiline literals."""
    continuations = set()
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.STRING:
            continuations.update(range(token.start[0] + 1, token.end[0] + 1))
    return "".join(line if number in continuations or not line.strip() else "    " + line
                   for number, line in enumerate(source.splitlines(keepends=True), 1))


def prepare_definition(source_path: Path, target: dict, notebook_id: str) -> tuple[dict, dict]:
    """Build one isolated verification definition and its local source receipt."""
    for value in (target["workspace_id"], target["lakehouse_id"], target["environment_id"], notebook_id):
        UUID(value)
    if target["input_mode"] not in {"stac", "manual"} or target["runtime_version"] != "1.3":
        raise ValueError("Independent rehearsal requires a supported input route and Runtime 1.3")
    source_bytes = source_path.read_bytes()
    original = nbformat.reads(source_bytes.decode("utf-8"), as_version=4)
    notebook = copy.deepcopy(original)
    lab = int(source_path.name[:2])
    source_info = {
        "notebook": source_path.name,
        "notebook_id": notebook_id,
        "sha256": hashlib.sha256(source_bytes).hexdigest(),
        "input_mode": target["input_mode"],
        "code_cells": [number for number, cell in enumerate(original.cells, 1) if cell.cell_type == "code"],
    }
    bindings = {
        "environment": {"environmentId": target["environment_id"], "workspaceId": target["workspace_id"]},
        "lakehouse": {
            "default_lakehouse": target["lakehouse_id"],
            "default_lakehouse_name": target["lakehouse_name"],
            "default_lakehouse_workspace_id": target["workspace_id"],
            "known_lakehouses": [{"id": target["lakehouse_id"]}],
        },
    }
    notebook.metadata["dependencies"] = bindings
    helper = (ROOT / "scripts/probes/lab_verification.py").read_text(encoding="utf-8")
    prelude = helper + "\n" + textwrap.dedent(f"""\
        import importlib.metadata
        import notebookutils
        import planetary_computer
        import pystac_client

        _verification_context = notebookutils.runtime.context
        _verification_runtime = {{key: str(_verification_context[key]) for key in (
            "currentWorkspaceId", "currentNotebookId", "defaultLakehouseId", "environmentId", "activityId")}}
        assert _verification_runtime["currentWorkspaceId"] == {target['workspace_id']!r}
        assert _verification_runtime["currentNotebookId"] == {notebook_id!r}
        assert _verification_runtime["defaultLakehouseId"] == {target['lakehouse_id']!r}
        assert _verification_runtime["environmentId"] == {target['environment_id']!r}
        assert sys.version_info[:2] == (3, 11)
        assert spark.version.startswith("3.5.")
        _verification_runtime["application_id"] = spark.sparkContext.applicationId
        _verification_runtime["spark_version"] = spark.version
        _verification_runtime["python_version"] = sys.version.split()[0]
        _verification_runtime["packages"] = {{name: importlib.metadata.version(name) for name in (
            "numpy", "pandas", "affine", "geopandas", "rasterio", "xarray", "rioxarray",
            "pystac-client", "planetary-computer", "odc-stac", "zarr")}}
        assert _verification_runtime["packages"]["numpy"].startswith("1.")
        assert _verification_runtime["packages"]["pandas"].startswith("2.")
        assert _verification_runtime["packages"]["affine"].startswith("2.")

        def _reject_verification_ingestion(*args, **kwargs):
            raise AssertionError("Manual verification attempted online STAC/signing")

        if {target['input_mode']!r} == "manual":
            pystac_client.Client.open = _reject_verification_ingestion
            planetary_computer.sign = _reject_verification_ingestion
            planetary_computer.sign_inplace = _reject_verification_ingestion
        _verification_activity = _verification_runtime["activityId"]
        assert all(character.isalnum() or character == "-" for character in _verification_activity)
        _verification_path = Path("/lakehouse/default/Files/verification/labs") / {source_path.stem!r} / (_verification_activity + ".json")
        _rehearsal = LabVerification(_verification_path, {source_info!r}, _verification_runtime)
        print("Verification target and Runtime 1.3 bindings confirmed")
        """)
    for number, cell in enumerate(notebook.cells, 1):
        if cell.cell_type == "code":
            source = retarget_labels(cell.source, target["workspace_name"], target["lakehouse_name"], target["input_mode"])
            cell.source = f"with _rehearsal.cell({number}):\n" + indent_code(source)
            cell.outputs = []
            cell.execution_count = None
    footer = textwrap.dedent(f"""\
        if "INPUT_MODE" in globals():
            assert INPUT_MODE == {target['input_mode']!r}
        _verification_tables = {{name: spark.table(name).count() for name in {LAB_TABLES[lab]!r}}}
        _verification_record = _rehearsal.finish(_verification_tables, map_export=globals().get("map_export"))
        print(json.dumps({{"status": _verification_record["status"], "cells": len(_verification_record["cells"]),
            "checks_passed": _verification_record["checks_passed"], "tables": _verification_tables,
            "receipt": str(_verification_path)}}, indent=2))
        """)
    notebook.cells.insert(0, nbformat.v4.new_code_cell(prelude, metadata={"language": "python"}))
    notebook.cells.append(nbformat.v4.new_code_cell(footer, metadata={"language": "python"}))
    for cell in notebook.cells:
        if cell.cell_type == "code":
            ast.parse(cell.source)
    nbformat.validate(notebook)
    encoded_bytes = nbformat.writes(notebook).encode("utf-8")
    receipt = {**source_info, "definition_sha256": hashlib.sha256(encoded_bytes).hexdigest(),
               "bindings": bindings, "original_code_cells": len(source_info["code_cells"])}
    payload = {"definition": {"format": "ipynb", "parts": [{"path": "notebook-content.ipynb",
        "payloadType": "InlineBase64", "payload": base64.b64encode(encoded_bytes).decode("ascii")} ]}}
    return payload, receipt


def create_parser() -> argparse.ArgumentParser:
    """Create the definition-preparation command parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("state", type=Path)
    parser.add_argument("output", type=Path)
    return parser


def main() -> int:
    """Write API payloads only, leaving shipped notebook artifacts unchanged."""
    arguments = create_parser().parse_args()
    state = json.loads(arguments.state.read_text(encoding="utf-8-sig"))
    arguments.output.mkdir(parents=True, exist_ok=False)
    receipts = []
    for item in state["notebooks"]:
        payload, receipt = prepare_definition(ROOT / item["source"], state, item["id"])
        if receipt["sha256"] != item["source_sha256"]:
            raise ValueError(f"Source changed after target discovery: {item['name']}")
        (arguments.output / (item["name"] + ".json")).write_text(json.dumps(payload), encoding="utf-8")
        receipts.append(receipt)
    (arguments.output / "receipts.json").write_text(json.dumps(receipts, indent=2) + "\n", encoding="utf-8")
    print(f"Prepared {len(receipts)} notebook definitions and {sum(item['original_code_cells'] for item in receipts)} original code-cell checkpoints")
    return 0


if __name__ == "__main__":
    sys.exit(main())
