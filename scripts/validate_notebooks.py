"""Static checks over the generated notebooks.

Runs without Fabric, Spark or any geospatial dependency, so it works in CI and
on a laptop. It checks three things:

1. Every code cell in a solution notebook parses as Python.
2. Every student notebook actually contains TODO markers, so a broken build
   cannot silently ship the solution as the student copy.
3. No solution code leaked into a student notebook.

Usage::

    python scripts/validate_notebooks.py
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import nbformat

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "notebooks" / "_src"
SOLUTION_DIR = REPO_ROOT / "notebooks" / "solutions"
STUDENT_DIR = REPO_ROOT / "notebooks" / "student"

MAGIC_RE = re.compile(r"^\s*[%!]")
TODO_RE = re.compile(r"^\s*# TODO \d+\.", re.MULTILINE)

# Consecutive lines that must match before a solution block counts as leaked.
MIN_LEAK_RUN = 3


def strip_magics(source: str) -> str:
    """Blank out IPython magics and shell escapes so ast.parse can run."""
    return "\n".join("" if MAGIC_RE.match(line) else line for line in source.splitlines())


def check_parses(path: Path) -> list[str]:
    problems: list[str] = []
    nb = nbformat.read(path, as_version=4)
    for index, cell in enumerate(nb.cells):
        if cell.cell_type != "code":
            continue
        try:
            ast.parse(strip_magics(cell.source))
        except SyntaxError as exc:
            problems.append(f"{path.name} cell {index}: {exc.msg} at line {exc.lineno}")
    return problems


def check_student_has_todos(path: Path) -> list[str]:
    nb = nbformat.read(path, as_version=4)
    todo_cells = sum(1 for c in nb.cells if c.cell_type == "code" and TODO_RE.search(c.source))
    if todo_cells == 0:
        return [f"{path.name}: no TODO cells found; the student notebook is not a skeleton"]
    return []


def check_no_leaked_solutions(student: Path, source: Path) -> list[str]:
    """No multi-line run from a solution block may appear in the student notebook.

    Comparing lengths would be simpler and wrong: a well-written TODO is often
    longer than the code it replaces, which is the point.

    Matching is done on runs of three or more consecutive lines. Single lines
    such as ``.option("overwriteSchema", "true")`` legitimately appear in shared
    scaffolding elsewhere in the same notebook, and flagging those produces
    noise that trains people to ignore the check.
    """
    if not source.exists():
        return [f"{student.name}: no matching source at {source.name}"]

    blocks: list[list[str]] = []
    current: list[str] = []
    in_solution = False

    for raw in source.read_text(encoding="utf-8").splitlines():
        stripped = raw.strip()
        if stripped.startswith("#@solution"):
            in_solution, current = True, []
            continue
        if stripped.startswith("#@end"):
            if len(current) >= MIN_LEAK_RUN:
                blocks.append(current)
            in_solution, current = False, []
            continue
        if in_solution and stripped and not stripped.startswith("#"):
            current.append(stripped)

    if not blocks:
        return []

    student_lines = [
        line.strip()
        for cell in nbformat.read(student, as_version=4).cells
        if cell.cell_type == "code"
        for line in cell.source.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]

    problems: list[str] = []
    for block in blocks:
        window = block[:MIN_LEAK_RUN]
        for start in range(len(student_lines) - MIN_LEAK_RUN + 1):
            if student_lines[start : start + MIN_LEAK_RUN] == window:
                problems.append(f"{student.name}: solution block leaked, starting '{window[0][:60]}'")
                break
    return problems


def check_markers_consumed(path: Path) -> list[str]:
    """No raw authoring marker should survive into a generated notebook."""
    text = path.read_text(encoding="utf-8")
    leaked = [m for m in ("#@todo", "#@hint", "#@stub", "#@solution", "#@end") if m in text]
    return [f"{path.name}: unconsumed authoring markers {leaked}"] if leaked else []


def main() -> int:
    problems: list[str] = []
    checked = 0

    solutions = sorted(SOLUTION_DIR.glob("*.ipynb"))
    if not solutions:
        print("no notebooks found; run python scripts/build_notebooks.py first", file=sys.stderr)
        return 1

    for solution in solutions:
        checked += 1
        problems += check_parses(solution)
        problems += check_markers_consumed(solution)

        student = STUDENT_DIR / f"{solution.stem}_STUDENT.ipynb"
        if not student.exists():
            problems.append(f"{solution.name}: no matching student notebook")
            continue

        checked += 1
        problems += check_markers_consumed(student)
        problems += check_student_has_todos(student)
        problems += check_no_leaked_solutions(student, SRC_DIR / f"{solution.stem}.py")

    print(f"checked {checked} notebooks")
    if problems:
        print(f"\n{len(problems)} problems:\n", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1

    print("all notebooks valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
