"""Build and verify the six-lab handout archive without local credentials or caches."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import nbformat

ROOT = Path(__file__).resolve().parents[1]
FOLDERS = ("docs", "notebooks", "environments", "powerbi", "pipelines", "src", "decks", "scripts")
ROOT_FILES = ("README.md", "DEPLOY.md", "requirements-build.txt", "requirements-fabric.txt")
SUFFIXES = {".md", ".ipynb", ".json", ".yml", ".yaml", ".py", ".ps1", ".png", ".svg", ".pptx", ".txt", ".xml", ".dax", ".tmdl"}
MAINTAINER_ONLY = {"update_training_release.py", "verify_training_setup.py"}


def files_to_ship() -> list[Path]:
    paths = [ROOT / name for name in ROOT_FILES]
    for folder in FOLDERS:
        for path in (ROOT / folder).rglob("*"):
            relative = path.relative_to(ROOT)
            if not path.is_file() or path.suffix.lower() not in SUFFIXES:
                continue
            if any(part.startswith(".") or part == "__pycache__" for part in relative.parts):
                continue
            if path.name.startswith("_qa_") or path.name.startswith("qa-training-"):
                continue
            if path.name in MAINTAINER_ONLY:
                continue
            paths.append(path)
    return sorted(paths)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    output = parser.parse_args().output
    if output.exists():
        raise FileExistsError(f"Archive already exists: {output}")
    paths = files_to_ship()
    names = [path.relative_to(ROOT).as_posix() for path in paths]
    students = [name for name in names if name.startswith("notebooks/student/") and name.endswith(".ipynb")]
    solutions = [name for name in names if name.startswith("notebooks/solutions/") and name.endswith(".ipynb")]
    if len(students) != 6 or len(solutions) != 6:
        raise RuntimeError("Expected exactly six student and six solution notebooks")
    for name in names:
        if "rayfin" in name.lower() or "chief-forester" in name or "06_publish_fabric_app" in name:
            raise RuntimeError(f"Retired app file in archive: {name}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for path, name in zip(paths, names, strict=True):
            archive.write(path, name)
    with ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("Archive integrity check failed")
        for name in students + solutions:
            notebook = nbformat.reads(archive.read(name).decode("utf-8"), as_version=4)
            nbformat.validate(notebook)
            if "dependencies" in notebook.metadata:
                raise RuntimeError(f"Learner artifact must not carry cloud bindings: {name}")
        print(json.dumps({"archive": str(output), "files": len(names), "student_notebooks": len(students),
                          "solution_notebooks": len(solutions), "integrity": "PASS"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
