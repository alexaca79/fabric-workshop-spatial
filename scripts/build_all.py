"""Regenerate the current workshop notebooks, screenshots and single deck.

Run from the repository root::

    python scripts/build_all.py
    python scripts/build_all.py --check   # fail if committed output is stale
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def run(label: str, command: list[str], cwd: Path) -> bool:
    print(f"\n== {label}")
    result = subprocess.run(command, cwd=cwd)
    if result.returncode != 0:
        print(f"   FAILED: {' '.join(command)}", file=sys.stderr)
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify committed output is current")
    args = parser.parse_args()

    python = sys.executable
    ok = True

    if args.check:
        ok &= run("notebooks (check)", [python, "scripts/build_notebooks.py", "--check"], REPO_ROOT)
        ok &= run("notebook validation", [python, "scripts/validate_notebooks.py"], REPO_ROOT)
        print("\nall checks passed" if ok else "\ncheck failed", file=sys.stderr if not ok else sys.stdout)
        return 0 if ok else 1

    ok &= run("notebooks", [python, "scripts/build_notebooks.py"], REPO_ROOT)
    ok &= run("notebook validation", [python, "scripts/validate_notebooks.py"], REPO_ROOT)
    for name in ("manual", "manual-download"):
        ok &= run(f"screenshots: {name}", [python, "scripts/annotate_manual_screenshots.py",
                  "--plan", f"scripts/verification/screenshots/{name}/annotations.json"], REPO_ROOT)
    ok &= run("workshop deck", [python, "scripts/deck/build_manual_deck.py"], REPO_ROOT)

    print("\nBuild complete." if ok else "\nBuild finished with failures.", file=sys.stdout if ok else sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
