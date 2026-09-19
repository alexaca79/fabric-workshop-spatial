"""Verify saved, UI-executed student cells against the current answer key.

Usage: python scripts/verify_browser_rehearsal.py SAVED SOLUTION TARGET OUTPUT
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import sys
from pathlib import Path

import nbformat

from prepare_independent_rehearsal import retarget_labels
from release_verification import BROWSER_LAB_CHECKS


def output_text(output: dict) -> str:
    """Extract plain output without executing notebook HTML or image payloads."""
    text = output.get("text", output.get("data", {}).get("text/plain", ""))
    return "".join(text) if isinstance(text, list) else text


def verify_notebook(saved: dict, solution: dict, target: dict,
                    required_checks: dict[int, int] | None = None) -> dict:
    """Require correct attachments, answer-key ASTs and clean executed outputs."""
    dependencies = saved["metadata"]["dependencies"]
    lakehouse = dependencies["lakehouse"]
    environment = dependencies["environment"]
    if (lakehouse["default_lakehouse"] != target["lakehouse_id"]
            or lakehouse["default_lakehouse_workspace_id"] != target["workspace_id"]
            or environment["environmentId"] != target["environment_id"]
            or environment["workspaceId"] != target["workspace_id"]):
        raise ValueError("Saved notebook attachments differ from the rehearsal target")
    expected_cells = [(number, cell) for number, cell in enumerate(solution["cells"], 1)
                      if cell["cell_type"] == "code"]
    actual_cells = [(number, cell) for number, cell in enumerate(saved["cells"], 1)
                    if cell["cell_type"] == "code"]
    if [number for number, _ in actual_cells] != [number for number, _ in expected_cells]:
        raise ValueError("Saved notebook code-cell positions differ from the answer key")
    cells = []
    for (number, actual), (_, expected) in zip(actual_cells, expected_cells, strict=True):
        actual_source = actual["source"]
        expected_source = retarget_labels(expected["source"], target["workspace_name"], target["lakehouse_name"])
        actual_ast = ast.dump(ast.parse(actual_source))
        if actual_ast != ast.dump(ast.parse(expected_source)):
            raise ValueError(f"Cell {number} code differs from the answer key")
        if not isinstance(actual.get("execution_count"), int) or actual["execution_count"] < 1:
            raise ValueError(f"Cell {number} has no saved execution")
        outputs = actual.get("outputs", [])
        if any(output["output_type"] == "error" for output in outputs):
            raise ValueError(f"Cell {number} contains a saved execution error")
        text = "\n".join(output_text(output) for output in outputs)
        if "[FAIL]" in text:
            raise ValueError(f"Cell {number} contains a failed validation")
        if required_checks is not None and text.count("[PASS]") != required_checks.get(number, 0):
            raise ValueError(f"Cell {number} is missing expected validation output or has extra checks")
        cells.append({"number": number, "status": "passed", "execution_count": actual["execution_count"],
                      "checks_passed": text.count("[PASS]"),
                      "source_sha256": hashlib.sha256(actual_source.encode("utf-8")).hexdigest(),
                      "answer_key_ast_sha256": hashlib.sha256(actual_ast.encode("utf-8")).hexdigest(),
                      "answer_key_ast": "matched"})
    if not cells or not sum(cell["checks_passed"] for cell in cells):
        raise ValueError("Saved notebook contains no passing validation output")
    return {"status": "passed", "code_cells": len(cells),
            "checks_passed": sum(cell["checks_passed"] for cell in cells), "cells": cells,
            "validation_counts_verified": required_checks is not None,
            "bindings": dependencies, "method": "Saved UI execution outputs plus answer-key AST comparison"}


def create_parser() -> argparse.ArgumentParser:
    """Create the saved-notebook verification command."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("saved", type=Path)
    parser.add_argument("solution", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("output", type=Path)
    return parser


def main() -> int:
    """Write a report only after the saved student notebook passes every gate."""
    arguments = create_parser().parse_args()
    try:
        saved = nbformat.read(arguments.saved, as_version=4)
        solution = nbformat.read(arguments.solution, as_version=4)
        target = json.loads(arguments.target.read_text(encoding="utf-8"))
        lab = arguments.solution.name[:2]
        expected_count, required_checks = BROWSER_LAB_CHECKS[lab]
        result = verify_notebook(saved, solution, target, required_checks)
        if result["code_cells"] != expected_count:
            raise ValueError(f"Lab {lab} code-cell contract changed; review its validation coverage")
        result.update({"saved_sha256": hashlib.sha256(arguments.saved.read_bytes()).hexdigest(),
                       "solution_sha256": hashlib.sha256(arguments.solution.read_bytes()).hexdigest()})
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({key: result[key] for key in ("status", "code_cells", "checks_passed")}))
        return 0
    except (OSError, ValueError, KeyError, SyntaxError) as error:
        print(f"Browser rehearsal verification failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
