"""Reject unproven Fabric-first releases before constructing a learner ZIP."""

import copy

import pytest

from release_verification import AGENT_CHECKS, BROWSER_LAB_CHECKS, MAP_CHECKS, artifact_digest, validate_live_release


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
    evidence["target"] = {"workspace_id": "workspace", "lakehouse_id": "lakehouse", "environment_id": "environment"}
    evidence["map_verification"]["lakehouse_id"] = "lakehouse"
    evidence["data_agent_verification"] = {"status": "passed", "lakehouse_id": "lakehouse",
                                           "workspace_id": "workspace", **dict.fromkeys(AGENT_CHECKS, True)}
    evidence["labs"] = []
    for lab, (count, checks) in BROWSER_LAB_CHECKS.items():
        positions = sorted(set(checks) | set(range(100, 100 + count - len(checks))))
        evidence["labs"].append({
            "lab": lab, "status": "passed", "session_stopped": True, "input_mode": "stac",
            "validation_counts_verified": True, "code_cells": count, "checks_passed": sum(checks.values()),
            "saved_sha256": "a" * 64, "solution_sha256": "b" * 64,
            "bindings": {"lakehouse": {"default_lakehouse": "lakehouse", "default_lakehouse_workspace_id": "workspace"},
                         "environment": {"environmentId": "environment", "workspaceId": "workspace"}},
            "cells": [{"number": number, "status": "passed", "execution_count": index + 1,
                       "checks_passed": checks.get(number, 0), "answer_key_ast": "matched"}
                      for index, number in enumerate(positions)],
        })
    return evidence


def test_given_complete_browser_rehearsal_when_validated_then_no_scheduler_job_is_required(browser_evidence):
    assert validate_live_release(browser_evidence) is None


@pytest.mark.parametrize("defect", ["missing_lab", "missing_check", "duplicate_cell", "unexecuted",
                                    "wrong_binding", "missing_hash", "running_session", "unknown_method"])
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
