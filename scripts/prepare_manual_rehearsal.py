"""Prepare verified solution edits for the approved manual portal rehearsal.

This command prints a JSON clipboard payload; it never writes notebook files.
Usage: python scripts/prepare_manual_rehearsal.py 00
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
from pathlib import Path

import nbformat

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = "jdi-training-manual"
LAKEHOUSE = "lh_woodlands_demo"


def normalize(source: str) -> str:
    """Ignore only transport line endings and trailing whitespace at cell end."""
    return source.replace("\r\n", "\n").rstrip()


def configure_labels(source: str) -> str:
    """Retarget the two display labels, rejecting unexpected existing values."""
    labels = {"WORKSPACE": ("jdi-training", WORKSPACE),
              "LAKEHOUSE": ("lh_woodlands", LAKEHOUSE)}

    def replace(match: re.Match[str]) -> str:
        name, assignment, quote, value = match.groups()
        old, target = labels[name]
        if value not in (old, target):
            raise ValueError(f"Unexpected {name} value: {value}")
        return f"{name}{assignment}{quote}{target}{quote}"

    return re.sub(r'(?m)^(WORKSPACE|LAKEHOUSE)([ \t]*=[ \t]*)([\"\'])([^\"\']*)\3',
                  replace, source)


def prepare_payload(lab: int) -> dict:
    """Compare the shipped variants and prepare bounded, source-checked edits."""
    if lab not in range(6):
        raise ValueError("Lab must be 00 through 05")
    paths = list((ROOT / "notebooks/student").glob(f"{lab:02d}_*_STUDENT.ipynb"))
    if len(paths) != 1:
        raise ValueError(f"Expected one student notebook for Lab {lab:02d}")
    student_path = paths[0]
    solution_path = ROOT / "notebooks/solutions" / student_path.name.replace("_STUDENT", "")
    student = nbformat.read(student_path, as_version=4)
    solution = nbformat.read(solution_path, as_version=4)
    student_code = [(position, cell) for position, cell in enumerate(student.cells, 1)
                    if cell.cell_type == "code"]
    solution_code = [cell for cell in solution.cells if cell.cell_type == "code"]
    if len(student_code) != len(solution_code):
        raise ValueError("Student and solution code-cell counts differ")
    edits = []
    for (position, cell), answer in zip(student_code, solution_code, strict=True):
        expected = normalize(cell.source)
        if "# TODO " in expected:
            replacement = normalize(answer.source)
            if "# TODO " in replacement:
                raise ValueError(f"Solution at student cell {position} still contains TODOs")
        else:
            if expected != normalize(answer.source):
                raise ValueError(f"Non-exercise code differs at student cell {position}")
            replacement = expected
        replacement = configure_labels(replacement)
        ast.parse(replacement)
        if replacement != expected:
            edits.append({"cell_number": position, "expected_source": expected,
                          "source": replacement})
    evidence = json.loads((ROOT / "docs/training-manual-evidence.json").read_text(encoding="utf-8"))
    if evidence["workspace"]["name"] != WORKSPACE or evidence["lakehouse"]["name"] != LAKEHOUSE:
        raise ValueError("The evidence does not identify the approved rehearsal workspace and lakehouse")
    target = next(item for item in evidence["notebooks"] if item["lab"] == f"{lab:02d}")
    return {"purpose": "jdi-manual-rehearsal-v1", "lab": f"{lab:02d}",
            "workspace_id": evidence["workspace"]["id"], "notebook_id": target["id"],
            "notebook_name": student_path.stem, "total_cells": len(student.cells),
            "student_sha256": hashlib.sha256(student_path.read_bytes()).hexdigest(),
            "edits": edits}


def create_parser() -> argparse.ArgumentParser:
    """Create the read-only clipboard payload command parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("lab", type=int, choices=range(6))
    return parser


def main() -> int:
    """Print the prepared payload for the browser rehearsal automation."""
    arguments = create_parser().parse_args()
    try:
        print(json.dumps(prepare_payload(arguments.lab)))
        return 0
    except (OSError, ValueError, KeyError, StopIteration) as error:
        print(f"Rehearsal preparation failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
