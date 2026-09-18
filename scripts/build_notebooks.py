"""Generate the solution and student notebooks from a single source of truth.

Each notebook is authored once as a percent-format Python file in
``notebooks/_src``. This script emits two ``.ipynb`` files from it: the complete
solution, and a student skeleton where the interesting lines are replaced by
numbered TODO instructions.

Authoring markers
-----------------

Cell boundaries::

    # %%                      start a code cell
    # %% [markdown]           start a markdown cell
    # %% @solution            cell appears only in the solution notebook
    # %% [markdown] @student  cell appears only in the student notebook

Inside a code cell::

    #@todo Write the STAC search      student only, becomes "# TODO 1. Write the STAC search"
    #@hint bbox order is W, S, E, N   student only, becomes "#      hint: bbox order is W, S, E, N"
    #@stub items = None               student only, emitted verbatim at the marker's indent
    #@solution ... #@end              solution only

Anything not inside a ``#@solution`` block and not a student-only marker appears
in both notebooks. That is the scaffolding: imports, configuration, print
statements and the assertions that tell a participant whether their answer works.

Usage::

    python scripts/build_notebooks.py
    python scripts/build_notebooks.py --check   # fail if committed output is stale
"""

from __future__ import annotations

import argparse
import ast
import copy
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import nbformat

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "notebooks" / "_src"
SOLUTION_DIR = REPO_ROOT / "notebooks" / "solutions"
STUDENT_DIR = REPO_ROOT / "notebooks" / "student"

CELL_RE = re.compile(r"^#\s*%%(?P<md>\s*\[markdown\])?(?P<tags>(?:\s+@\w+)*)\s*$")
MARKER_RE = re.compile(r"^(?P<indent>\s*)#@(?P<marker>todo|hint|stub|solution|end|include)\b\s?(?P<body>.*)$")

SOLUTION_BANNER = (
    "> **Solution notebook.** Every cell is complete and runnable. Use it to unblock "
    "yourself at a checkpoint, then go back and finish your own version. Reading a "
    "working answer is not the same as having written one."
)

STUDENT_BANNER = (
    "> **Student notebook.** Cells marked with `TODO` are yours to write. The "
    "scaffolding, imports and validation cells are already in place, so a finished "
    "cell should make the validation below it print `PASS`. If you get stuck for more "
    "than five minutes, open the matching solution notebook, read the cell, and carry on."
)


@dataclass
class Cell:
    kind: str  # "code" or "markdown"
    tags: list[str] = field(default_factory=list)
    lines: list[str] = field(default_factory=list)


def parse_source(path: Path) -> list[Cell]:
    cells: list[Cell] = []
    current: Cell | None = None

    for raw in path.read_text(encoding="utf-8").splitlines():
        match = CELL_RE.match(raw)
        if match:
            if current is not None:
                cells.append(current)
            tags = [t.strip().lstrip("@") for t in (match.group("tags") or "").split() if t.strip()]
            current = Cell(kind="markdown" if match.group("md") else "code", tags=tags)
            continue
        if current is None:
            # Anything before the first cell marker is a module docstring or a
            # header comment. Skipping it keeps the notebook clean.
            continue
        current.lines.append(raw)

    if current is not None:
        cells.append(current)
    return cells


def render_markdown(cell: Cell) -> str:
    out: list[str] = []
    for line in cell.lines:
        stripped = line.rstrip()
        if stripped.startswith("# "):
            out.append(stripped[2:])
        elif stripped == "#":
            out.append("")
        else:
            out.append(stripped)
    return "\n".join(out).strip("\n")


def render_code(cell: Cell, variant: str) -> str:
    out: list[str] = []
    in_solution = False
    todo_index = 0

    for line in cell.lines:
        match = MARKER_RE.match(line)
        if match:
            marker = match.group("marker")
            indent = match.group("indent")
            body = match.group("body").rstrip()

            if marker == "include":
                module = REPO_ROOT / "src" / "forestops" / body
                if Path(body).name != body or module.suffix != ".py":
                    raise ValueError("Notebook includes must name a forestops Python module")
                source = module.read_text(encoding="utf-8")
                for node in ast.parse(source).body:
                    if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                        continue
                    if isinstance(node, ast.ImportFrom) and node.module == "__future__":
                        continue
                    out.extend((ast.get_source_segment(source, node) or "").splitlines())
                    out.append("")
                continue
            if marker == "solution":
                in_solution = True
                continue
            if marker == "end":
                in_solution = False
                continue
            if variant != "student":
                continue
            if marker == "todo":
                todo_index += 1
                out.append(f"{indent}# TODO {todo_index}. {body}")
            elif marker == "hint":
                out.append(f"{indent}#        hint: {body}")
            elif marker == "stub":
                out.append(f"{indent}{body}")
            continue

        if in_solution and variant != "solution":
            continue
        out.append(line.rstrip())

    # Collapse the runs of blank lines that marker removal leaves behind.
    cleaned: list[str] = []
    for line in out:
        if not line.strip() and cleaned and not cleaned[-1].strip():
            continue
        cleaned.append(line)
    return "\n".join(cleaned).strip("\n")


def build_notebook(cells: list[Cell], variant: str, title: str) -> nbformat.NotebookNode:
    nb = nbformat.v4.new_notebook()
    banner = SOLUTION_BANNER if variant == "solution" else STUDENT_BANNER
    nb.cells.append(nbformat.v4.new_markdown_cell(f"{banner}\n"))

    for cell in cells:
        if cell.tags and variant not in cell.tags:
            continue
        if cell.kind == "markdown":
            body = render_markdown(cell)
            if body:
                nb.cells.append(nbformat.v4.new_markdown_cell(body))
        else:
            body = render_code(cell, variant)
            if body:
                nb.cells.append(nbformat.v4.new_code_cell(body))

    nb.metadata.update(
        {
            "kernelspec": {"display_name": "Synapse PySpark", "language": "python", "name": "synapse_pyspark"},
            "language_info": {"name": "python"},
            "microsoft": {"language": "python"},
            "widgets": {},
            "workshop": {"variant": variant, "title": title},
        }
    )
    for position, cell in enumerate(nb.cells):
        cell.id = uuid5(NAMESPACE_URL, f"forestops/{title}/{variant}/{position}").hex[:16]
        cell.metadata["language"] = "python" if cell.cell_type == "code" else "markdown"
    return nb


def preserve_metadata(notebook: nbformat.NotebookNode, existing: nbformat.NotebookNode) -> None:
    """Preserve cell identities for an in-place, same-structure regeneration."""
    originals = existing.cells
    if [cell.cell_type for cell in notebook.cells] != [cell.cell_type for cell in originals]:
        remaining = iter(originals)
        originals = []
        for cell in notebook.cells:
            original = next((candidate for candidate in remaining
                             if candidate.cell_type == cell.cell_type
                             and candidate.source.rstrip() == cell.source.rstrip()), None)
            if original is None:
                raise ValueError("Notebook structure changed; reconcile cells in the notebook editor before rebuilding")
            originals.append(original)
    notebook.metadata = copy.deepcopy(existing.metadata)
    for cell, original in zip(notebook.cells, originals, strict=True):
        cell.id = original.id
        cell.metadata = copy.deepcopy(original.metadata)
        cell.metadata["language"] = "python" if cell.cell_type == "code" else "markdown"


def target_name(stem: str, variant: str) -> str:
    return f"{stem}.ipynb" if variant == "solution" else f"{stem}_STUDENT.ipynb"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if the committed notebooks are stale")
    parser.add_argument("--only", nargs="+", help="source stems to rebuild; other notebooks are left untouched")
    args = parser.parse_args()

    if not SRC_DIR.exists():
        print(f"no notebook sources found at {SRC_DIR}", file=sys.stderr)
        return 1

    SOLUTION_DIR.mkdir(parents=True, exist_ok=True)
    STUDENT_DIR.mkdir(parents=True, exist_ok=True)

    stale: list[str] = []
    written = 0

    for source in sorted(SRC_DIR.glob("*.py")):
        if args.only and source.stem not in args.only:
            continue
        cells = parse_source(source)
        if not cells:
            print(f"  skipped {source.name}, no cell markers found")
            continue

        for variant, directory in (("solution", SOLUTION_DIR), ("student", STUDENT_DIR)):
            nb = build_notebook(cells, variant, source.stem)
            out_path = directory / target_name(source.stem, variant)
            if out_path.exists():
                preserve_metadata(nb, nbformat.read(out_path, as_version=4))
            rendered = nbformat.writes(nb, version=4) + "\n"

            if args.check:
                if not out_path.exists() or nbformat.read(out_path, as_version=4) != nb:
                    stale.append(str(out_path.relative_to(REPO_ROOT)))
                continue

            out_path.write_text(rendered, encoding="utf-8")
            written += 1
            print(f"  wrote {out_path.relative_to(REPO_ROOT)}  ({len(nb.cells)} cells)")

    if args.check:
        if stale:
            print("stale notebooks, run python scripts/build_notebooks.py:", file=sys.stderr)
            for path in stale:
                print(f"  {path}", file=sys.stderr)
            return 1
        print("all notebooks up to date")
        return 0

    print(f"\n{written} notebooks generated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
