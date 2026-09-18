"""Verify rehearsal edits remain confined to exercises and approved labels."""

import ast
import hashlib

import nbformat
import pytest

from prepare_manual_rehearsal import ROOT, configure_labels, normalize, prepare_payload


@pytest.mark.parametrize("lab", range(6))
def test_given_shipped_pair_when_prepared_then_only_exercises_and_labels_change(lab):
    student_path = next((ROOT / "notebooks/student").glob(f"{lab:02d}_*_STUDENT.ipynb"))
    before = hashlib.sha256(student_path.read_bytes()).hexdigest()
    notebook = nbformat.read(student_path, as_version=4)

    payload = prepare_payload(lab)
    edits = {entry["cell_number"]: entry for entry in payload["edits"]}

    assert payload["workspace_id"] == "5785367c-0109-4ea9-beb5-05fb0edbe4dc"
    assert payload["student_sha256"] == before
    assert hashlib.sha256(student_path.read_bytes()).hexdigest() == before
    for position, cell in enumerate(notebook.cells, 1):
        if position in edits:
            edit = edits[position]
            assert cell.cell_type == "code"
            assert edit["expected_source"] == normalize(cell.source)
            assert "# TODO " not in edit["source"]
            ast.parse(edit["source"])
            if "# TODO " not in cell.source:
                assert edit["source"] == configure_labels(normalize(cell.source))
        elif cell.cell_type == "code":
            assert "# TODO " not in cell.source


def test_given_other_workspace_label_when_prepared_then_unexpected_context_is_rejected():
    with pytest.raises(ValueError, match="Unexpected WORKSPACE"):
        configure_labels('WORKSPACE = "production"')
