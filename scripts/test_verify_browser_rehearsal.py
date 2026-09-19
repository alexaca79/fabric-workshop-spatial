"""Reject incomplete or altered browser notebook evidence."""

import copy

import nbformat
import pytest

from verify_browser_rehearsal import output_text, verify_notebook


@pytest.fixture
def rehearsal():
    target = {"workspace_id": "workspace", "workspace_name": "learner-workspace",
              "lakehouse_id": "lakehouse", "lakehouse_name": "learner_lakehouse", "environment_id": "environment"}
    solution = nbformat.v4.new_notebook(cells=[nbformat.v4.new_code_cell('print("[PASS] validation")')])
    saved = copy.deepcopy(solution)
    saved.metadata.dependencies = {
        "lakehouse": {"default_lakehouse": "lakehouse", "default_lakehouse_workspace_id": "workspace"},
        "environment": {"environmentId": "environment", "workspaceId": "workspace"},
    }
    saved.cells[0].execution_count = 1
    saved.cells[0].outputs = [nbformat.v4.new_output("stream", name="stdout", text="[PASS] validation\n")]
    return saved, solution, target


def test_given_executed_matching_notebook_when_verified_then_checks_are_recorded(rehearsal):
    result = verify_notebook(*rehearsal)

    assert result["status"] == "passed"
    assert result["code_cells"] == result["checks_passed"] == 1
    assert result["cells"][0]["answer_key_ast"] == "matched"


@pytest.mark.parametrize("defect", ["changed_code", "unexecuted", "error", "fail", "no_checks", "shifted_cells"])
def test_given_invalid_cell_evidence_when_verified_then_rejected(rehearsal, defect):
    saved, solution, target = rehearsal
    if defect == "changed_code":
        saved.cells[0].source = 'print("fake result")'
    elif defect == "unexecuted":
        saved.cells[0].execution_count = None
    elif defect == "error":
        saved.cells[0].outputs = [nbformat.v4.new_output("error", ename="ValueError", evalue="failed", traceback=[])]
    elif defect == "fail":
        saved.cells[0].outputs[0].text = "[FAIL] validation"
    elif defect == "no_checks":
        saved.cells[0].outputs = []
    else:
        saved.cells.insert(0, nbformat.v4.new_markdown_cell("Unexpected inserted cell"))

    with pytest.raises(ValueError):
        verify_notebook(saved, solution, target)


@pytest.mark.parametrize(("dependency", "field"), [
    ("lakehouse", "default_lakehouse"), ("lakehouse", "default_lakehouse_workspace_id"),
    ("environment", "environmentId"), ("environment", "workspaceId"),
])
def test_given_wrong_binding_when_verified_then_rejected(rehearsal, dependency, field):
    saved, solution, target = rehearsal
    saved.metadata.dependencies[dependency][field] = "other-target"

    with pytest.raises(ValueError, match="attachments"):
        verify_notebook(saved, solution, target)


def test_given_display_plain_text_when_read_then_html_is_not_used():
    output = {"data": {"text/plain": ["[PASS]", " actual check"], "text/html": "<script>untrusted</script>"}}

    assert output_text(output) == "[PASS] actual check"


@pytest.mark.parametrize("expected", [0, 2])
def test_given_inexact_validation_count_when_verified_then_rejected(rehearsal, expected):
    with pytest.raises(ValueError, match="expected validation"):
        verify_notebook(*rehearsal, required_checks={1: expected})


def test_given_exact_validation_count_when_verified_then_contract_is_recorded(rehearsal):
    result = verify_notebook(*rehearsal, required_checks={1: 1})

    assert result["validation_counts_verified"] is True
