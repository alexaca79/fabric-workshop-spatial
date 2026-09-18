"""Exercise the real Lab 05 map export without starting Spark or contacting Fabric."""

import ast
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

import geopandas as gpd
import nbformat
import numpy as np
import pandas as pd
import pytest
import yaml
from markdown_it import MarkdownIt
from shapely.geometry import Polygon, box

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_notebooks import SRC_DIR, build_notebook, parse_source


@pytest.fixture(params=["source", "student", "solutions"])
def export_namespace(request):
    name = "05_publish_and_validate"
    if request.param == "source":
        notebook = build_notebook(parse_source(SRC_DIR / f"{name}.py"), "solution", name)
    else:
        filename = f"{name}_STUDENT.ipynb" if request.param == "student" else f"{name}.ipynb"
        notebook = nbformat.read(SRC_DIR.parent / request.param / filename, as_version=4)
    namespace = {"gpd": gpd, "pd": pd, "np": np, "CRS_ANALYSIS": 2953, "CRS_WGS84": 4326}
    definitions = [cell.source for cell in notebook.cells
                   if cell.cell_type == "code" and "def build_map_features(" in cell.source]
    assert len(definitions) == 1
    tree = ast.parse(definitions[0])
    tree.body = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef))]
    exec(compile(tree, name, "exec"), namespace)
    return namespace


@pytest.fixture
def map_inputs():
    register = gpd.GeoDataFrame({
        "stand_id": ["CEN-00001", "CEN-00002", "CEN-00003"],
        "licence_block": ["LB-A", "LB-A", "LB-B"],
        "source": ["synthetic"] * 3,
        "private_url": ["https://example.invalid/imagery?sig=do-not-export"] * 3,
    }, geometry=[box(-66.8 + offset, 46.2, -66.79 + offset, 46.21)
                 for offset in (0, 0.02, 0.04)], crs=4326).to_crs(2953)
    facts = pd.DataFrame({
        "stand_id": ["CEN-00001", "CEN-00002", "CEN-00003"],
        "period_end": [pd.Timestamp("2026-08-31"), pd.Timestamp("2026-08-31"),
                       pd.Timestamp("2026-07-31")],
        "forest_class": ["softwood", "regenerating", "softwood"],
        "class_confidence": [0.8, np.nan, 0.7],
        "is_trusted": [True, True, True],
        "valid_pixel_fraction": [0.9, 0.8, 0.7],
        "requires_review": [False, True, False],
        "change_type": ["none", "harvest", "none"],
        "validation_status": ["stubbed", None, "stubbed"],
    })
    classes = pd.DataFrame({"forest_class": ["softwood", "regenerating"],
                            "colour_hex": ["#1B7F4B", "#9DD08A"]})
    return register, facts, classes


def test_given_missing_stand_when_exported_then_all_stands_and_unknowns_survive(
    export_namespace, map_inputs, tmp_path,
):
    output = tmp_path / "maps" / "stands.geojson"

    summary = export_namespace["export_stand_map"](*map_inputs, output)
    payload = json.loads(output.read_text(encoding="utf-8"))
    missing = payload["features"][2]["properties"]

    assert summary["registered_stands"] == 3
    assert summary["retained_stands"] == 2
    assert summary["stands_without_result"] == 1
    assert summary["register_coverage"] == pytest.approx(2 / 3)
    assert summary["readback"] == "PASS"
    assert missing["coverage_status"] == "no_classified_result"
    assert missing["map_class"] == "no_classified_result"
    assert missing["forest_class"] is None
    assert missing["is_trusted"] is None
    assert missing["requires_review"] is None
    assert missing["period_end"] == "2026-08-31"


def test_given_projected_polygons_when_exported_then_coordinates_are_wgs84(
    export_namespace, map_inputs,
):
    payload = export_namespace["build_map_features"](*map_inputs)
    frame = gpd.GeoDataFrame.from_features(payload, crs=4326)

    assert frame.total_bounds == pytest.approx([-66.8, 46.2, -66.75, 46.21], abs=0.00001)
    assert frame.geometry.is_valid.all()
    assert (frame["area_ha"] > 0).all()
    assert payload["type"] == "FeatureCollection"
    assert "crs" not in payload


def test_given_nullable_fields_when_serialized_then_json_has_nulls_and_no_secrets(
    export_namespace, map_inputs,
):
    payload = export_namespace["build_map_features"](*map_inputs)
    encoded = json.dumps(payload, allow_nan=False)
    properties = payload["features"][1]["properties"]

    assert properties["class_confidence"] is None
    assert properties["validation_status"] is None
    assert properties["is_trusted"] is True
    assert properties["stand_source"] == "synthetic"
    assert "private_url" not in encoded
    assert "do-not-export" not in encoded
    assert "geometry_wkb" not in encoded


def test_given_explicit_period_when_exported_then_other_periods_are_not_mixed(
    export_namespace, map_inputs,
):
    payload = export_namespace["build_map_features"](*map_inputs, period_end="2026-07-31")
    properties = [feature["properties"] for feature in payload["features"]]

    assert {item["period_end"] for item in properties} == {"2026-07-31"}
    assert [item["stand_id"] for item in properties if item["coverage_status"] == "retained"] == ["CEN-00003"]


def test_given_missing_period_when_exported_then_export_is_rejected(export_namespace, map_inputs):
    with pytest.raises(ValueError, match="No facts exist"):
        export_namespace["build_map_features"](*map_inputs, period_end="2020-01-31")


@pytest.mark.parametrize("duplicate_target", ["register", "facts", "classes"])
def test_given_duplicate_keys_when_exported_then_ambiguous_join_is_rejected(
    export_namespace, map_inputs, duplicate_target,
):
    register, facts, classes = map_inputs
    if duplicate_target == "register":
        register = pd.concat([register, register.iloc[[0]]])
    elif duplicate_target == "facts":
        facts = pd.concat([facts, facts.iloc[[0]]])
    else:
        classes = pd.concat([classes, classes.iloc[[0]]])

    with pytest.raises(ValueError, match="unique|one row"):
        export_namespace["build_map_features"](register, facts, classes)


@pytest.mark.parametrize("geometry", [None, Polygon(), Polygon([(0, 0), (1, 1), (0, 1), (1, 0), (0, 0)])])
def test_given_invalid_polygon_when_exported_then_export_is_rejected(
    export_namespace, map_inputs, geometry,
):
    register, facts, classes = map_inputs
    register.loc[0, "geometry"] = geometry

    with pytest.raises(ValueError, match="valid, nonempty polygon"):
        export_namespace["build_map_features"](register, facts, classes)


def test_given_unknown_crs_when_exported_then_projection_is_not_guessed(export_namespace, map_inputs):
    register, facts, classes = map_inputs
    register = register.set_crs(None, allow_override=True)

    with pytest.raises(ValueError, match="actual CRS"):
        export_namespace["build_map_features"](register, facts, classes)


def test_given_orphan_fact_when_exported_then_export_is_rejected(export_namespace, map_inputs):
    register, facts, classes = map_inputs
    facts.loc[0, "stand_id"] = "CEN-99999"

    with pytest.raises(ValueError, match="unknown stand_id"):
        export_namespace["build_map_features"](register, facts, classes)


def test_given_nonfinite_metric_when_exported_then_existing_file_is_preserved(
    export_namespace, map_inputs, tmp_path,
):
    register, facts, classes = map_inputs
    output = tmp_path / "stands.geojson"
    output.write_text("existing-file", encoding="utf-8")
    facts.loc[0, "class_confidence"] = np.inf

    with pytest.raises(ValueError, match="JSON"):
        export_namespace["export_stand_map"](register, facts, classes, output)

    assert output.read_text(encoding="utf-8") == "existing-file"


@pytest.mark.parametrize("variant", ["student", "solutions"])
def test_given_shipped_notebook_when_checked_then_export_matches_authoring_source(variant):
    name = "05_publish_and_validate"
    source = build_notebook(parse_source(SRC_DIR / f"{name}.py"), "solution", name)
    export_cells = [cell.source for cell in source.cells if cell.cell_type == "code"
                    and ("def build_map_features(" in cell.source or "map_export = export_stand_map(" in cell.source)]
    filename = f"{name}_STUDENT.ipynb" if variant == "student" else f"{name}.ipynb"
    notebook = nbformat.read(SRC_DIR.parent / variant / filename, as_version=4)
    shipped = [cell.source for cell in notebook.cells if cell.cell_type == "code"
               and "def build_map_features(" in cell.source]

    nbformat.validate(notebook)
    assert len(shipped) == 1
    assert ast.dump(ast.parse(shipped[0])) == ast.dump(ast.parse("\n\n".join(export_cells)))
    assert "dependencies" not in notebook.metadata
    for cell in notebook.cells:
        if cell.cell_type == "code":
            ast.parse(cell.source)
    if variant == "student":
        assert sum("# TODO " in cell.source for cell in notebook.cells if cell.cell_type == "code") == 3


@pytest.mark.parametrize("variant", ["student", "solutions"])
def test_given_complete_export_cell_when_executed_then_it_writes_and_reports_counts(
    variant, map_inputs, tmp_path, monkeypatch, capsys,
):
    name = "05_publish_and_validate"
    filename = f"{name}_STUDENT.ipynb" if variant == "student" else f"{name}.ipynb"
    notebook = nbformat.read(SRC_DIR.parent / variant / filename, as_version=4)
    code = next(cell.source for cell in notebook.cells
                if cell.cell_type == "code" and "def build_map_features(" in cell.source)
    target = tmp_path / "stand_classification.geojson"
    path_type = type(tmp_path)

    def isolated_path(value):
        if str(value) == "/lakehouse/default/Files/gold/maps/stand_classification.geojson":
            return target
        return path_type(value)

    register, facts, classes = map_inputs
    namespace = {"register": register, "facts": facts, "dim_class": classes,
                 "gpd": gpd, "pd": pd, "np": np, "CRS_ANALYSIS": 2953, "CRS_WGS84": 4326}
    with monkeypatch.context() as patch:
        patch.setattr("pathlib.Path", isolated_path)
        exec(compile(code, filename, "exec"), namespace)

    output = json.loads(capsys.readouterr().out)
    assert target.is_file()
    assert output["registered_stands"] == 3
    assert output["retained_stands"] == 2
    assert output["readback"] == "PASS"


@pytest.mark.parametrize("relative_path", [
    "README.md", "docs/00-prerequisites.md", "docs/04-facilitator-guide.md",
    "docs/12-spark-environment.md", "docs/16-manual-upload-labs.md",
])
def test_given_manual_documentation_when_parsed_then_metadata_and_local_links_resolve(relative_path):
    root = SRC_DIR.parents[1]
    path = root / relative_path
    text = path.read_text(encoding="utf-8")
    frontmatter = text.split("---", 2)
    assert len(frontmatter) == 3
    metadata = yaml.safe_load(frontmatter[1])
    assert metadata["title"] and metadata["description"]

    for token in MarkdownIt().parse(frontmatter[2]):
        for child in token.children or []:
            address = child.attrGet("href") or child.attrGet("src")
            if not address:
                continue
            target = urlsplit(address)
            if target.scheme or target.netloc:
                continue
            destination = (path.parent / unquote(target.path)).resolve() if target.path else path
            assert destination.exists(), f"{relative_path}: missing {address}"
            if target.fragment and destination.suffix == ".md":
                headings = re.findall(r"^#{1,6}\s+(.+)$", destination.read_text(encoding="utf-8"), re.MULTILINE)
                anchors = {re.sub(r"[^\w\s-]", "", heading.lower()).replace(" ", "-") for heading in headings}
                assert unquote(target.fragment) in anchors, f"{relative_path}: missing anchor {address}"


def test_given_environment_definition_when_imported_then_keys_and_constraints_are_supported():
    definition = yaml.safe_load(
        (SRC_DIR.parents[1] / "environments" / "environment.yml").read_text(encoding="utf-8")
    )
    expected = [
        "numpy<2", "pandas>=2.1,<3", "typing-extensions>=4.15",
        "shapely>=2.0,<3", "geopandas>=1.0,<2", "pyproj>=3.6",
        "rasterio>=1.3,<2", "xarray>=2024.3", "rioxarray>=0.15",
        "zarr>=2.16", "affine<3", "pystac-client>=0.8,<1",
        "planetary-computer>=1.0,<2", "odc-stac>=0.3.10",
    ]

    assert set(definition) == {"dependencies"}
    assert definition["dependencies"] == [{"pip": expected}]


def test_given_capture_manifest_when_release_is_complete_then_every_screenshot_exists():
    root = SRC_DIR.parents[1]
    docs = root / "docs"
    manifest = json.loads((docs / "training-manual-evidence.json").read_text(encoding="utf-8"))
    guide_text = (docs / "16-manual-upload-labs.md").read_text(encoding="utf-8")
    environment_text = (docs / "12-spark-environment.md").read_text(encoding="utf-8")
    screenshots = manifest["screenshots"]
    assert len(screenshots) == 45
    assert len({item["file"] for item in screenshots}) == len(screenshots)

    for item in screenshots:
        assert item["file"] in guide_text + environment_text
        if item["status"] == "captured" or manifest["status"] == "ready_for_classroom":
            image = docs / manifest["screenshot_directory"] / item["file"]
            assert image.is_file(), f"Missing claimed screenshot: {image}"
            assert item["status"] == "captured"
        else:
            assert manifest["status"] != "ready_for_classroom"
