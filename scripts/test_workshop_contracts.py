"""Focused local checks for the manually imported forestry labs."""

import sys
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_notebooks import SRC_DIR, build_notebook, parse_source


@pytest.fixture
def setup_namespace():
    """Execute the real setup exercise through its geometry validation only."""
    name = "00_setup_lakehouse_and_config"
    notebook = build_notebook(parse_source(SRC_DIR / f"{name}.py"), "solution", name)
    namespace = {}
    output = StringIO()
    for cell in notebook.cells:
        if cell.cell_type != "code":
            continue
        with redirect_stdout(output):
            exec(compile(cell.source, name, "exec"), namespace)
        if 'report("areas match expected scale"' in cell.source:
            namespace["validation_output"] = output.getvalue()
            return namespace
    pytest.fail("Missing setup area validation")


def test_given_default_synthetic_register_when_validated_then_all_checks_pass(
    setup_namespace,
):
    namespace = setup_namespace
    areas = namespace["stands"]["area_ha"]

    assert len(areas) == 120
    assert areas.between(namespace["area_min_ha"], namespace["area_max_ha"]).all()
    assert "[FAIL]" not in namespace["validation_output"]


@pytest.mark.parametrize("scale", [0.0001, 10000.0])
def test_given_wrong_area_units_when_validated_then_values_are_rejected(
    setup_namespace, scale
):
    namespace = setup_namespace
    incorrect_areas = namespace["stands"]["area_ha"] * scale

    assert not incorrect_areas.between(
        namespace["area_min_ha"], namespace["area_max_ha"]
    ).any()
