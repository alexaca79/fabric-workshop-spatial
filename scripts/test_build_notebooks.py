"""Protect repeatable notebook generation and existing cell identities."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_notebooks import Cell, build_notebook, preserve_metadata, render_code


def test_given_same_source_when_built_twice_then_notebooks_are_identical():
    cells = [Cell("code", lines=["value = 2"])]

    first = build_notebook(cells, "solution", "example")
    second = build_notebook(cells, "solution", "example")

    assert first == second
    assert first.cells[1].metadata.language == "python"


def test_given_existing_ids_when_rebuilt_then_metadata_and_ids_survive():
    original = build_notebook([Cell("code", lines=["value = 1"])], "student", "example")
    original.cells[1].id = "existing-cell"
    original.cells[1].metadata.update({"id": "fabric-existing-id", "tags": ["parameters"]})
    regenerated = build_notebook([Cell("code", lines=["value = 2"])], "student", "example")

    preserve_metadata(regenerated, original)

    assert regenerated.cells[1].id == "existing-cell"
    assert regenerated.cells[1].metadata == original.cells[1].metadata
    assert regenerated.cells[1].source == "value = 2"


def test_given_structural_change_when_rebuilt_then_identity_guessing_is_rejected():
    original = build_notebook([], "solution", "example")
    regenerated = build_notebook([Cell("code", lines=["value = 2"])], "solution", "example")

    with pytest.raises(ValueError, match="structure changed"):
        preserve_metadata(regenerated, original)


def test_given_removed_optional_cell_when_rebuilt_then_remaining_identity_survives():
    original = build_notebook([Cell("code", lines=["value = 1"]),
                               Cell("markdown", lines=["# optional"]),
                               Cell("code", lines=["value = 2"])], "solution", "example")
    regenerated = build_notebook([Cell("code", lines=["value = 1"]),
                                  Cell("code", lines=["value = 2"])], "solution", "example")

    preserve_metadata(regenerated, original)

    assert regenerated.cells[2].id == original.cells[3].id


def test_given_manual_validator_include_when_rendered_then_notebook_is_self_contained():
    code = render_code(Cell("code", lines=["#@include manual_imagery.py"]), "solution")

    namespace = {}
    exec(compile(code, "included-validator", "exec"), namespace)

    assert callable(namespace["read_manual_items"])
    assert "from forestops" not in code
    assert "#@include" not in code
