"""Verify Fabric-first execution evidence before publishing learner artifacts."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

from prepare_independent_rehearsal import retarget_labels

EVIDENCE_FILE = "scripts/verification/training-browser-evidence.json"
MAP_CHECKS = ("polygons_visible", "tooltip_verified", "filter_verified", "layer_toggle_verified",
              "saved", "reopened", "bound_to_target_lakehouse")
BROWSER_LAB_CHECKS = {
    "00": (14, {10: 3, 16: 6, 25: 4, 27: 1}),
    "01": (14, {13: 4, 19: 5, 28: 6, 30: 2}),
    "02": (16, {8: 2, 12: 3, 14: 1, 18: 2, 20: 2, 22: 2, 34: 5}),
    "03": (11, {6: 3, 10: 6, 19: 4}),
    "04": (17, {22: 3, 34: 5}),
    "05": (11, {6: 3, 9: 2, 15: 4}),
}
BROWSER_CODE_CELLS = {
    "00": [4, 6, 8, 10, 12, 14, 16, 18, 20, 21, 23, 25, 27, 29],
    "01": [4, 6, 9, 11, 13, 15, 17, 19, 21, 24, 26, 28, 30, 32],
    "02": [4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 27, 29, 31, 32, 34],
    "03": [4, 6, 8, 10, 12, 14, 16, 17, 19, 22, 24],
    "04": [3, 5, 7, 9, 11, 14, 16, 18, 20, 22, 24, 26, 27, 30, 32, 34, 36],
    "05": [3, 6, 9, 11, 13, 15, 17, 19, 21, 23, 25],
}
AGENT_CHECKS = ("selected_four_tables", "instructions_saved", "examples_validated",
                "answers_match_sql", "published", "reopened", "published_coverage_verified")


def artifact_digest(path: Path) -> str:
    """Hash Markdown with canonical newlines; preserve all other artifact bytes."""
    content = path.read_bytes()
    if path.suffix == ".md":
        content = content.replace(b"\r\n", b"\n")
    return hashlib.sha256(content).hexdigest()


def validate_browser_rehearsal(evidence: dict) -> None:
    """Require saved UI executions without assigning them scheduler job states."""
    labs = evidence.get("labs", [])
    if len(labs) != 6 or {lab.get("lab") for lab in labs} != set(BROWSER_LAB_CHECKS):
        raise ValueError("Browser rehearsal needs all six labs")
    target = evidence.get("target", {})
    if not all(target.get(key) for key in ("workspace_id", "lakehouse_id", "environment_id")):
        raise ValueError("Browser rehearsal target is incomplete")
    for lab in labs:
        expected_count, expected_checks = BROWSER_LAB_CHECKS[lab["lab"]]
        cells = lab.get("cells", [])
        if (lab.get("status") != "passed" or lab.get("session_stopped") is not True
                or lab.get("validation_counts_verified") is not True
                or lab.get("input_mode") != "stac"
                or lab.get("code_cells") != expected_count or len(cells) != expected_count
                or len({cell.get("number") for cell in cells}) != expected_count
                or lab.get("checks_passed") != sum(expected_checks.values())):
            raise ValueError(f"Browser Lab {lab['lab']} execution evidence is incomplete")
        if [cell.get("number") for cell in cells] != BROWSER_CODE_CELLS[lab["lab"]]:
            raise ValueError(f"Browser Lab {lab['lab']} code-cell sequence differs from the contract")
        for cell in cells:
            if (cell.get("status") != "passed" or cell.get("answer_key_ast") != "matched"
                    or type(cell.get("execution_count")) is not int or cell["execution_count"] < 1
                    or cell.get("checks_passed") != expected_checks.get(cell.get("number"), 0)):
                raise ValueError(f"Browser Lab {lab['lab']} has unverified cell output")
            for field in ("source_sha256", "answer_key_ast_sha256"):
                digest = cell.get(field, "")
                if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
                    raise ValueError(f"Browser Lab {lab['lab']} has no cell source hash")
        for field in ("solution_sha256", "saved_sha256"):
            digest = lab.get(field, "")
            if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
                raise ValueError(f"Browser Lab {lab['lab']} is missing source hashes")
        bindings = lab.get("bindings", {})
        lakehouse = bindings.get("lakehouse", {})
        environment = bindings.get("environment", {})
        if (lakehouse.get("default_lakehouse") != target["lakehouse_id"]
                or lakehouse.get("default_lakehouse_workspace_id") != target["workspace_id"]
                or environment.get("environmentId") != target["environment_id"]
                or environment.get("workspaceId") != target["workspace_id"]):
            raise ValueError(f"Browser Lab {lab['lab']} is bound to a different target")
    agent = evidence.get("data_agent_verification", {})
    if agent.get("status") != "passed" or any(agent.get(check) is not True for check in AGENT_CHECKS):
        raise ValueError("Native Data Agent SQL, publication and readback checks are incomplete")
    if (agent.get("lakehouse_id") != target["lakehouse_id"]
            or agent.get("workspace_id") != target["workspace_id"]):
        raise ValueError("Native Data Agent uses a different browser-rehearsal target")
    if evidence.get("map_verification", {}).get("lakehouse_id") != target["lakehouse_id"]:
        raise ValueError("Native Map uses a different browser-rehearsal lakehouse")


def validate_independent_jobs(evidence: dict) -> None:
    """Retain the separate scheduler-and-durable-output gate for historical jobs."""
    jobs = evidence.get("jobs", [])
    if len(jobs) != 6 or {job.get("lab") for job in jobs} != {f"{number:02d}" for number in range(6)}:
        raise ValueError("Fabric-first release needs all six lab jobs")
    if any(job.get("status") != "Completed" or job.get("verified") is not True for job in jobs):
        raise ValueError("Every lab needs completed scheduler and durable validation evidence")
    applications = {job.get("application_id") for job in jobs}
    if len(applications) != 6 or None in applications or "" in applications:
        raise ValueError("Each lab must use an independent Spark application")
    if any(job.get("input_mode") != "stac" for job in jobs if job["lab"] != "00"):
        raise ValueError("Downstream evidence must use the primary STAC route")


def validate_live_release(evidence: dict) -> None:
    """Require a verified primary route and the actual execution method's gates."""
    if evidence.get("status") != "verified" or evidence.get("input_mode") != "stac":
        raise ValueError("Fabric-first release needs verified STAC execution evidence")
    method = evidence.get("execution_method", "independent_jobs")
    if method == "interactive_ui":
        validate_browser_rehearsal(evidence)
    elif method == "independent_jobs":
        validate_independent_jobs(evidence)
    else:
        raise ValueError("Unknown Fabric rehearsal execution method")
    map_result = evidence.get("map_verification", {})
    if map_result.get("status") != "passed" or any(map_result.get(check) is not True for check in MAP_CHECKS):
        raise ValueError("Native Map interaction, binding, save and reopen verification is incomplete")


def load_release_evidence(root: Path, *, verify_hashes: bool = True) -> dict:
    """Load fresh-run evidence, optionally requiring all shipped artifact hashes."""
    path = root / EVIDENCE_FILE
    if not path.is_file():
        raise ValueError("Fabric-first verification evidence is missing; use a draft during rehearsal")
    evidence = json.loads(path.read_text(encoding="utf-8"))
    validate_live_release(evidence)
    supporting = evidence.get("evidence_sha256", {})
    if evidence.get("execution_method") == "interactive_ui" and not supporting:
        raise ValueError("Browser release supporting evidence hashes are missing")
    for relative, expected_hash in supporting.items():
        receipt = (root / relative).resolve()
        if not receipt.is_relative_to(root.resolve()) or not receipt.is_file():
            raise ValueError(f"Invalid supporting evidence path: {relative}")
        if hashlib.sha256(receipt.read_bytes()).hexdigest() != expected_hash:
            raise ValueError(f"Supporting evidence is stale: {relative}")
    if evidence.get("execution_method") == "interactive_ui":
        for lab in evidence["labs"]:
            solutions = list((root / "notebooks" / "solutions").glob(f"{lab['lab']}_*.ipynb"))
            if len(solutions) != 1 or artifact_digest(solutions[0]) != lab["solution_sha256"]:
                raise ValueError(f"Browser Lab {lab['lab']} answer-key evidence is stale")
            relative = lab.get("receipt")
            if relative not in supporting:
                raise ValueError(f"Browser Lab {lab['lab']} has no bound supporting receipt")
            if json.loads((root / relative).read_text(encoding="utf-8")) != lab:
                raise ValueError(f"Browser Lab {lab['lab']} differs from its supporting receipt")
            solution = json.loads(solutions[0].read_text(encoding="utf-8"))
            code_cells = [(number, cell) for number, cell in enumerate(solution["cells"], 1)
                          if cell["cell_type"] == "code"]
            if [number for number, _ in code_cells] != BROWSER_CODE_CELLS[lab["lab"]]:
                raise ValueError(f"Browser Lab {lab['lab']} answer-key cell sequence changed")
            target = evidence["target"]
            for recorded, (_, cell) in zip(lab["cells"], code_cells, strict=True):
                source = retarget_labels("".join(cell["source"]), target["workspace_name"], target["lakehouse_name"])
                digest = hashlib.sha256(ast.dump(ast.parse(source)).encode("utf-8")).hexdigest()
                if recorded["answer_key_ast_sha256"] != digest:
                    raise ValueError(f"Browser Lab {lab['lab']} cell AST evidence is stale")
    if not verify_hashes:
        return evidence
    expected = evidence.get("artifact_sha256", {})
    required = {path.relative_to(root).as_posix() for variant in ("student", "solutions")
                for path in (root / "notebooks" / variant).glob("*.ipynb")}
    required.update({"environments/environment.yml", "docs/download-imagery.html",
                     "decks/woodlands-manual-workshop.pptx", "README.md",
                     "docs/07-homework.md", "docs/12-spark-environment.md",
                     "docs/16-manual-upload-labs.md", "docs/17-manual-imagery-download.md"})
    if not required.issubset(expected):
        raise ValueError("Fabric-first artifact hash coverage is incomplete")
    for relative, expected_hash in expected.items():
        artifact = (root / relative).resolve()
        if not artifact.is_relative_to(root.resolve()) or not artifact.is_file():
            raise ValueError(f"Invalid release artifact path: {relative}")
        if artifact_digest(artifact) != expected_hash:
            raise ValueError(f"Fabric-first verification is stale: {relative}")
    return evidence
