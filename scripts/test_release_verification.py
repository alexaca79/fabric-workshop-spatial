"""Reject unproven Fabric-first releases before constructing a learner ZIP."""

import ast
import copy
import hashlib
import json
from pathlib import Path

import pytest

from prepare_independent_rehearsal import retarget_labels
from release_verification import (
    AGENT_CHECKS, BROWSER_CODE_CELLS, BROWSER_LAB_CHECKS, EVIDENCE_FILE, MAP_CHECKS,
    artifact_digest, load_release_evidence, validate_live_release,
)


@pytest.fixture
def evidence():
    return {"status": "verified", "input_mode": "stac",
            "jobs": [{"lab": f"{number:02d}", "status": "Completed", "verified": True,
                      "input_mode": "stac", "application_id": f"application-{number}"} for number in range(6)],
            "map_verification": {"status": "passed", **dict.fromkeys(MAP_CHECKS, True)}}


def test_given_complete_independent_run_when_validated_then_release_passes(evidence):
    assert validate_live_release(evidence) is None


@pytest.mark.parametrize("check", MAP_CHECKS)
def test_given_missing_map_check_when_validated_then_release_is_rejected(evidence, check):
    evidence["map_verification"][check] = False

    with pytest.raises(ValueError, match="Native Map"):
        validate_live_release(evidence)


@pytest.mark.parametrize("defect", ["missing", "failed", "scheduler_only", "shared_session", "manual_route"])
def test_given_incomplete_lab_evidence_when_validated_then_release_is_rejected(evidence, defect):
    candidate = copy.deepcopy(evidence)
    if defect == "missing":
        candidate["jobs"].pop()
    elif defect == "failed":
        candidate["jobs"][1]["status"] = "Failed"
    elif defect == "scheduler_only":
        candidate["jobs"][1]["verified"] = False
    elif defect == "shared_session":
        candidate["jobs"][1]["application_id"] = candidate["jobs"][0]["application_id"]
    else:
        candidate["jobs"][1]["input_mode"] = "manual"

    with pytest.raises(ValueError):
        validate_live_release(candidate)


def test_given_markdown_checkout_line_endings_when_hashed_then_content_hash_is_stable(tmp_path):
    artifact = tmp_path / "guide.md"
    artifact.write_bytes(b"## Route\nFabric first\n")
    original = artifact_digest(artifact)
    artifact.write_bytes(b"## Route\r\nFabric first\r\n")

    assert artifact_digest(artifact) == original
    artifact.write_bytes(b"## Route\r\nManual first\r\n")
    assert artifact_digest(artifact) != original


@pytest.fixture
def browser_evidence(evidence):
    evidence.pop("jobs")
    evidence["execution_method"] = "interactive_ui"
    evidence["target"] = {"workspace_id": "workspace", "lakehouse_id": "lakehouse", "environment_id": "environment",
                          "workspace_name": "learner-workspace", "lakehouse_name": "learner-lakehouse"}
    evidence["map_verification"]["lakehouse_id"] = "lakehouse"
    evidence["data_agent_verification"] = {"status": "passed", "lakehouse_id": "lakehouse",
                                           "workspace_id": "workspace", **dict.fromkeys(AGENT_CHECKS, True)}
    evidence["labs"] = []
    for lab, (count, checks) in BROWSER_LAB_CHECKS.items():
        positions = BROWSER_CODE_CELLS[lab]
        evidence["labs"].append({
            "lab": lab, "status": "passed", "session_stopped": True, "input_mode": "stac",
            "validation_counts_verified": True, "code_cells": count, "checks_passed": sum(checks.values()),
            "saved_sha256": "a" * 64, "solution_sha256": "b" * 64,
            "bindings": {"lakehouse": {"default_lakehouse": "lakehouse", "default_lakehouse_workspace_id": "workspace"},
                         "environment": {"environmentId": "environment", "workspaceId": "workspace"}},
            "cells": [{"number": number, "status": "passed", "execution_count": index + 1,
                       "source_sha256": "c" * 64, "answer_key_ast_sha256": "d" * 64,
                       "checks_passed": checks.get(number, 0), "answer_key_ast": "matched"}
                      for index, number in enumerate(positions)],
        })
    return evidence


def test_given_complete_browser_rehearsal_when_validated_then_no_scheduler_job_is_required(browser_evidence):
    assert validate_live_release(browser_evidence) is None


@pytest.mark.parametrize("defect", ["missing_lab", "missing_check", "duplicate_cell", "unexecuted",
                                    "wrong_binding", "missing_hash", "running_session", "unknown_method",
                                    "substituted_cell", "reordered_cells", "missing_cell_hash"])
def test_given_incomplete_browser_evidence_when_validated_then_rejected(browser_evidence, defect):
    lab = browser_evidence["labs"][0]
    if defect == "missing_lab":
        browser_evidence["labs"].pop()
    elif defect == "missing_check":
        lab["cells"][0]["checks_passed"] -= 1
    elif defect == "duplicate_cell":
        lab["cells"][1]["number"] = lab["cells"][0]["number"]
    elif defect == "unexecuted":
        lab["cells"][0]["execution_count"] = None
    elif defect == "wrong_binding":
        lab["bindings"]["lakehouse"]["default_lakehouse"] = "wrong"
    elif defect == "missing_hash":
        lab["saved_sha256"] = ""
    elif defect == "running_session":
        lab["session_stopped"] = False
    elif defect == "substituted_cell":
        lab["cells"][0]["number"] = 999
    elif defect == "reordered_cells":
        lab["cells"][0], lab["cells"][1] = lab["cells"][1], lab["cells"][0]
    elif defect == "missing_cell_hash":
        lab["cells"][0].pop("source_sha256")
    else:
        browser_evidence["execution_method"] = "unknown"

    with pytest.raises(ValueError):
        validate_live_release(browser_evidence)


@pytest.mark.parametrize("check", AGENT_CHECKS)
def test_given_missing_agent_check_when_browser_release_validated_then_rejected(browser_evidence, check):
    browser_evidence["data_agent_verification"][check] = False

    with pytest.raises(ValueError, match="Data Agent"):
        validate_live_release(browser_evidence)


def test_given_old_agent_target_when_browser_release_validated_then_rejected(browser_evidence):
    browser_evidence["data_agent_verification"]["lakehouse_id"] = "previous-lakehouse"

    with pytest.raises(ValueError, match="Data Agent uses a different"):
        validate_live_release(browser_evidence)


@pytest.fixture
def browser_release(tmp_path, browser_evidence):
    root = Path(__file__).resolve().parents[1]
    browser_evidence["evidence_sha256"] = {}
    for lab in browser_evidence["labs"]:
        original = next((root / "notebooks/solutions").glob(f"{lab['lab']}_*.ipynb"))
        solution = tmp_path / "notebooks/solutions" / original.name
        solution.parent.mkdir(parents=True, exist_ok=True)
        solution.write_bytes(original.read_bytes())
        lab["solution_sha256"] = artifact_digest(solution)
        notebook = json.loads(solution.read_text(encoding="utf-8"))
        for recorded in lab["cells"]:
            source = "".join(notebook["cells"][recorded["number"] - 1]["source"])
            source = retarget_labels(source, "learner-workspace", "learner-lakehouse")
            recorded["answer_key_ast_sha256"] = hashlib.sha256(ast.dump(ast.parse(source)).encode()).hexdigest()
        lab["receipt"] = f"scripts/verification/receipts/lab-{lab['lab']}.json"
        receipt = tmp_path / lab["receipt"]
        receipt.parent.mkdir(parents=True, exist_ok=True)
        receipt.write_text(json.dumps(lab), encoding="utf-8")
        browser_evidence["evidence_sha256"][lab["receipt"]] = hashlib.sha256(receipt.read_bytes()).hexdigest()
    manifest = tmp_path / EVIDENCE_FILE
    manifest.write_text(json.dumps(browser_evidence), encoding="utf-8")
    return tmp_path, browser_evidence, manifest


def test_given_bound_browser_receipts_when_loaded_then_deck_gate_passes(browser_release):
    root, _, _ = browser_release

    assert load_release_evidence(root, verify_hashes=False)["status"] == "verified"


@pytest.mark.parametrize("defect", ["changed_receipt", "missing_receipt", "wrong_digest", "missing_hashes",
                                    "outside_root", "aggregate_mismatch", "wrong_ast"])
def test_given_stale_browser_receipts_when_loaded_then_rejected(browser_release, defect):
    root, evidence, manifest = browser_release
    lab = evidence["labs"][0]
    receipt = root / lab["receipt"]
    if defect == "changed_receipt":
        receipt.write_text("{}", encoding="utf-8")
    elif defect == "missing_receipt":
        receipt.unlink()
    elif defect == "wrong_digest":
        evidence["evidence_sha256"][lab["receipt"]] = "0" * 64
    elif defect == "missing_hashes":
        evidence["evidence_sha256"] = {}
    elif defect == "outside_root":
        evidence["evidence_sha256"]["../outside.json"] = "0" * 64
    elif defect == "aggregate_mismatch":
        lab["saved_sha256"] = "f" * 64
    else:
        lab["cells"][0]["answer_key_ast_sha256"] = "0" * 64
        receipt.write_text(json.dumps(lab), encoding="utf-8")
        evidence["evidence_sha256"][lab["receipt"]] = hashlib.sha256(receipt.read_bytes()).hexdigest()
    manifest.write_text(json.dumps(evidence), encoding="utf-8")

    with pytest.raises(ValueError):
        load_release_evidence(root, verify_hashes=False)
