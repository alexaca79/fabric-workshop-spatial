"""Verify bound rehearsal copies preserve the source code inside each checkpoint."""

import ast
import base64
import hashlib
from uuid import uuid4

import nbformat
import pytest

from scripts.prepare_independent_rehearsal import ROOT, prepare_definition, retarget_labels


@pytest.fixture
def target():
    return {"workspace_id": str(uuid4()), "workspace_name": "new-verification-workspace",
            "lakehouse_id": str(uuid4()), "lakehouse_name": "lh_woodlands",
            "environment_id": str(uuid4()), "input_mode": "stac", "runtime_version": "1.3"}


@pytest.mark.parametrize("source_path", sorted((ROOT / "notebooks/solutions").glob("*.ipynb")), ids=lambda path: path.stem)
@pytest.mark.parametrize("mode", ["stac", "manual"])
def test_given_solution_when_prepared_then_preserves_code_ids_metadata_and_new_bindings(source_path, target, mode):
    target["input_mode"] = mode
    before = source_path.read_bytes()
    original = nbformat.reads(before.decode("utf-8"), as_version=4)

    payload, receipt = prepare_definition(source_path, target, str(uuid4()))
    decoded = base64.b64decode(payload["definition"]["parts"][0]["payload"])
    notebook = nbformat.reads(decoded.decode("utf-8"), as_version=4)

    assert source_path.read_bytes() == before
    assert receipt["sha256"] == hashlib.sha256(before).hexdigest()
    assert receipt["definition_sha256"] == hashlib.sha256(decoded).hexdigest()
    assert receipt["input_mode"] == mode
    assert notebook.metadata.dependencies.environment.environmentId == target["environment_id"]
    assert notebook.metadata.dependencies.lakehouse.default_lakehouse_workspace_id == target["workspace_id"]
    assert len(notebook.cells) == len(original.cells) + 2
    for number, (expected, actual) in enumerate(zip(original.cells, notebook.cells[1:-1], strict=True), 1):
        assert actual.id == expected.id
        assert actual.metadata == expected.metadata
        if expected.cell_type == "code":
            wrapper = ast.parse(actual.source).body
            assert len(wrapper) == 1 and isinstance(wrapper[0], ast.With)
            assert wrapper[0].items[0].context_expr.args[0].value == number
            expected_code = retarget_labels(expected.source, target["workspace_name"], target["lakehouse_name"], mode)
            assert [ast.dump(node) for node in wrapper[0].body] == [ast.dump(node) for node in ast.parse(expected_code).body]
        else:
            assert actual.source == expected.source


def test_given_unexpected_workspace_label_when_prepared_then_rejects_silent_retargeting():
    with pytest.raises(ValueError, match="WORKSPACE"):
        retarget_labels('WORKSPACE = "user-modified"', "new", "lh_woodlands")


def test_given_unknown_route_when_prepared_then_rejects_run(target):
    target["input_mode"] = "unknown"
    source_path = next((ROOT / "notebooks/solutions").glob("00_*.ipynb"))

    with pytest.raises(ValueError, match="supported input route"):
        prepare_definition(source_path, target, str(uuid4()))
