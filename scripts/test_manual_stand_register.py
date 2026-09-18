"""Exercise the Lab 00 synthetic generator without Spark or cloud writes."""

import ast
import math

import geopandas as gpd
import nbformat
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import Polygon, box

from build_notebooks import SRC_DIR, build_notebook, parse_source


@pytest.mark.parametrize("variant", ["source", "solutions"])
@pytest.mark.parametrize("seed", [0, 20260902])
def test_given_workshop_aoi_when_stands_generated_then_all_120_are_inside(variant, seed):
    name = "00_setup_lakehouse_and_config"
    notebook = (build_notebook(parse_source(SRC_DIR / f"{name}.py"), "solution", name)
                if variant == "source" else nbformat.read(
                    SRC_DIR.parent / "solutions" / f"{name}.ipynb", as_version=4))
    namespace = {"math": math, "gpd": gpd, "np": np, "pd": pd,
                 "Polygon": Polygon, "box": box, "CRS_WGS84": 4326,
                 "CRS_ANALYSIS": 2953, "AOI_NAME": "central-nb-block-a",
                 "SYNTHETIC_STAND_COUNT": 120, "RANDOM_SEED": seed}
    for cell in notebook.cells:
        if cell.cell_type != "code":
            continue
        tree = ast.parse(cell.source)
        tree.body = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                     and node.name in {"hex_grid", "build_stand_register"}]
        if tree.body:
            exec(compile(tree, name, "exec"), namespace)
    bounds = (-66.90, 46.10, -66.40, 46.40)
    aoi = gpd.GeoDataFrame(geometry=[box(*bounds)], crs=4326).to_crs(2953)

    stands = namespace["build_stand_register"](bounds)
    centroids = stands.geometry.centroid.to_crs(4326)
    inside = centroids.x.between(bounds[0], bounds[2]) & centroids.y.between(bounds[1], bounds[3])
    expected_area = aoi.envelope.area.iloc[0] / (120 * 1.6) / 10_000

    assert len(stands) == 120
    assert inside.all(), f"Only {inside.sum()}/120 centroids are inside the workshop AOI"
    assert stands.geometry.is_valid.all()
    assert stands.within(aoi.geometry.iloc[0]).all()
    assert stands["area_ha"].between(expected_area * 0.5, expected_area * 1.5).all()
    assert stands["stand_id"].is_unique
