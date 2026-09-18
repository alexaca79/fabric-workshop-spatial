"""Exercise uploaded Sentinel-2 validation against real local GeoTIFF fixtures."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pystac
import pytest
import rasterio
import rioxarray
import xarray as xr
from rasterio.transform import from_origin
from rasterio.warp import transform_bounds

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_notebooks import SRC_DIR, build_notebook, parse_source
from forestops.manual_imagery import MANUAL_BANDS, read_manual_items, validate_scene_selection


@pytest.fixture
def uploaded_scene(tmp_path):
    folder = tmp_path / "scene-a"
    folder.mkdir()
    transform = from_origin(650000, 5120000, 20, 20)
    bbox = transform_bounds("EPSG:32619", "EPSG:4326", 650000, 5119880, 650120, 5120000)
    west, south, east, north = bbox
    geometry = {"type": "Polygon", "coordinates": [[[west, south], [east, south], [east, north], [west, north], [west, south]]]}
    item = pystac.Item("scene-a", geometry, list(bbox), datetime(2026, 8, 6, tzinfo=timezone.utc), {"eo:cloud_cover": 1.0})
    item.collection_id = "sentinel-2-l2a"
    item.stac_extensions = ["https://stac-extensions.github.io/projection/v2.0.0/schema.json",
                            "https://stac-extensions.github.io/raster/v1.1.0/schema.json"]
    for band in MANUAL_BANDS:
        filename = f"scene-a_{band}.tif"
        dtype = "uint8" if band == "SCL" else "uint16"
        value = 4 if band == "SCL" else 2000
        with rasterio.open(folder / filename, "w", driver="GTiff", width=6, height=6,
                           count=1, dtype=dtype, crs="EPSG:32619", transform=transform, nodata=0) as raster:
            raster.write(np.full((6, 6), value, dtype=dtype), 1)
        item.add_asset(band, pystac.Asset(
            f"https://sentinel2l2a01.blob.core.windows.net/sentinel2-l2/scene-a/{filename}",
            media_type=pystac.MediaType.COG, roles=["data"],
            extra_fields={"proj:code": "EPSG:32619", "proj:shape": [6, 6], "proj:transform": list(transform),
                          "raster:bands": [{"data_type": dtype, "nodata": 0, "spatial_resolution": 20}]},
        ))
    (folder / "item.json").write_text(json.dumps(item.to_dict()), encoding="utf-8")
    return folder


def test_given_five_uploaded_bands_when_read_then_only_local_assets_are_used(uploaded_scene, monkeypatch):
    def reject_network(*args, **kwargs):
        pytest.fail("Manual imagery must not contact the network")

    monkeypatch.setattr("socket.create_connection", reject_network)

    items = read_manual_items(uploaded_scene)

    assert len(items) == 1
    assert set(items[0].assets) == set(MANUAL_BANDS)
    assert all(Path(asset.href).is_file() for asset in items[0].assets.values())
    assert all(asset.extra_fields["source_href"].startswith("https://") for asset in items[0].assets.values())
    assert items[0].properties["input_mode"] == "manual"
    assert all(asset.owner is items[0] for asset in items[0].assets.values())


def test_given_missing_band_when_read_then_upload_error_names_the_band(uploaded_scene):
    (uploaded_scene / "scene-a_SCL.tif").unlink()

    with pytest.raises(FileNotFoundError, match="original SCL TIFF"):
        read_manual_items(uploaded_scene)


def test_given_wrong_scene_grid_when_read_then_validation_stops(uploaded_scene):
    with rasterio.open(uploaded_scene / "scene-a_B08.tif", "r+") as raster:
        raster.transform = from_origin(750000, 5120000, 20, 20)

    with pytest.raises(ValueError, match="B08 grid does not match"):
        read_manual_items(uploaded_scene)


def test_given_original_tiffs_without_nodata_tag_when_read_then_upload_is_accepted(uploaded_scene):
    for band in MANUAL_BANDS:
        with rasterio.open(uploaded_scene / f"scene-a_{band}.tif", "r+") as raster:
            raster.nodata = None

    items = read_manual_items(uploaded_scene)

    assert len(items) == 1


def test_given_item_level_projection_when_read_then_assets_inherit_native_epsg(uploaded_scene):
    from pystac.extensions.projection import ProjectionExtension

    manifest = uploaded_scene / "item.json"
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["properties"]["proj:epsg"] = 32619
    for asset in payload["assets"].values():
        asset.pop("proj:code")
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    item = read_manual_items(uploaded_scene)[0]

    assert all(ProjectionExtension.ext(asset).epsg == 32619 for asset in item.assets.values())


def test_given_signed_source_metadata_when_read_then_provenance_has_no_token(uploaded_scene):
    manifest = uploaded_scene / "item.json"
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["assets"]["B04"]["href"] += "?sig=expired-example&st=2026-01-01"
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    item = read_manual_items(uploaded_scene)[0]

    assert "?" not in item.assets["B04"].extra_fields["source_href"]
    assert "expired-example" not in json.dumps(item.to_dict())


@pytest.mark.parametrize("invalid", ["date", "area", "cloud", "empty"])
def test_given_invalid_selection_when_validated_then_analysis_does_not_start(uploaded_scene, invalid):
    items = read_manual_items(uploaded_scene)
    bbox = tuple(items[0].bbox)
    if invalid == "date":
        items[0].datetime = datetime(2025, 8, 6, tzinfo=timezone.utc)
    elif invalid == "area":
        bbox = (-80, 20, -79, 21)
    elif invalid == "cloud":
        items[0].properties["eo:cloud_cover"] = 99
    else:
        items = []

    with pytest.raises(ValueError):
        validate_scene_selection(items, bbox, "2026-06-01", "2026-08-31", 20, 6)


def source_code_cells(stem):
    """Build the exact self-contained code shipped to learners."""
    notebook = build_notebook(parse_source(SRC_DIR / f"{stem}.py"), "solution", stem)
    return [cell.source for cell in notebook.cells if cell.cell_type == "code"]


@pytest.mark.parametrize("mode", ["manual", "stac"])
def test_given_selected_route_when_notebook_loads_then_silver_uses_same_pixels(
    uploaded_scene, tmp_path, monkeypatch, mode,
):
    bronze = source_code_cells("01_bronze_stac_ingest")
    silver = source_code_cells("02_silver_reproject_and_indices")
    local_items = read_manual_items(uploaded_scene)
    calls = []

    class Catalog:
        def search(self, **parameters):
            calls.append(parameters)
            return self

        def items(self):
            return local_items

    def open_catalog(*args, **kwargs):
        if mode == "manual":
            pytest.fail("Manual notebook cells opened the online catalogue")
        calls.append(kwargs)
        return Catalog()

    def reject_network(*args, **kwargs):
        pytest.fail("Local TIFF loading contacted the network")

    monkeypatch.setattr("pystac_client.Client.open", open_catalog)
    monkeypatch.setattr("requests.sessions.Session.request", reject_network)
    namespace = {}
    exec(next(code for code in bronze if "def require_environment(" in code), namespace)
    exec(next(code for code in bronze if 'INPUT_MODE = "manual"' in code), namespace)
    namespace.update({"INPUT_MODE": mode, "MANUAL_SCENE_ROOT": str(uploaded_scene),
                      "AOI_BBOX": tuple(local_items[0].bbox), "BRONZE_SCENE_ROOT": str(tmp_path / "bronze")})

    exec(next(code for code in bronze if "def read_manual_items(" in code), namespace)
    exec(next(code for code in bronze if "def search_scenes(" in code), namespace)
    exec(next(code for code in bronze if "def report(" in code), namespace)
    exec(next(code for code in bronze if "raw = odc.stac.load(" in code), namespace)
    exec(next(code for code in bronze if 'report("dataset loaded"' in code), namespace)
    namespace["raw"] = namespace["raw"].compute()
    exec(next(code for code in bronze if "raw.to_zarr(" in code), namespace)
    namespace["xr"] = xr
    exec(next(code for code in silver if "def restore_crs(" in code), namespace)

    raw = namespace["raw"]
    assert raw.rio.crs.to_epsg() == 32619
    assert raw.attrs["input_mode"] == mode
    assert raw.attrs["scene_ids"] == ["scene-a"]
    assert str(raw.time.values[0])[:10] == "2026-08-06"
    assert np.all(raw.B04.values[raw.B04.values != 0] == 2000)
    assert np.all(raw.SCL.values[raw.SCL.values != 0] == 4)
    assert bool(calls) == (mode == "stac")


def test_given_missing_bronze_cache_when_silver_runs_then_no_download_fallback(tmp_path, monkeypatch):
    silver = source_code_cells("02_silver_reproject_and_indices")

    def reject_network(*args, **kwargs):
        pytest.fail("Silver attempted an online fallback")

    monkeypatch.setattr("requests.sessions.Session.request", reject_network)
    namespace = {"xr": xr, "BRONZE_SCENE_ROOT": str(tmp_path), "BANDS": MANUAL_BANDS,
                 "AOI_BBOX": (-66.9, 46.1, -66.4, 46.4)}

    with pytest.raises(RuntimeError, match="no online fallback"):
        exec(next(code for code in silver if "def restore_crs(" in code), namespace)
