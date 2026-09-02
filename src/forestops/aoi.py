"""Area of interest helpers and the synthetic Woodlands stand register.

The stand register is generated rather than shipped so that the workshop runs
before anyone has been granted access to production inventory. Swap it for the
real register by setting ``use_synthetic_stands = False`` and pointing
``load_stand_register`` at your source.
"""

from __future__ import annotations

import math

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Polygon, box

from .config import CRS_ANALYSIS, CRS_WGS84, AreaOfInterest

SPECIES_GROUPS = ("softwood", "hardwood", "mixedwood")


def aoi_geometry(aoi: AreaOfInterest) -> gpd.GeoDataFrame:
    """The area of interest as a single-row GeoDataFrame in WGS84."""
    return gpd.GeoDataFrame(
        {"aoi_name": [aoi.name]},
        geometry=[box(*aoi.bbox)],
        crs=CRS_WGS84,
    )


def _hex_grid(bounds: tuple[float, float, float, float], spacing_m: float) -> list[Polygon]:
    """A hexagonal tessellation covering ``bounds`` in a projected CRS.

    Hexagons rather than squares because real stands are not axis-aligned, and a
    square grid makes reprojection bugs invisible: everything stays square.
    """
    minx, miny, maxx, maxy = bounds
    r = spacing_m / math.sqrt(3)
    dx = spacing_m
    dy = spacing_m * math.sqrt(3) / 2

    cells: list[Polygon] = []
    row = 0
    y = miny
    while y < maxy + dy:
        x_offset = 0.0 if row % 2 == 0 else dx / 2
        x = minx + x_offset
        while x < maxx + dx:
            cells.append(
                Polygon(
                    [
                        (x + r * math.cos(math.radians(angle)), y + r * math.sin(math.radians(angle)))
                        for angle in range(0, 360, 60)
                    ]
                )
            )
            x += dx
        y += dy
        row += 1
    return cells


def synthetic_stand_register(
    aoi: AreaOfInterest,
    n_stands: int = 120,
    seed: int = 20260902,
) -> gpd.GeoDataFrame:
    """Generate a plausible Woodlands stand register inside the area of interest.

    Stand shapes are hexagonal cells, jittered so no two are identical, with
    attributes drawn to give a realistic species and age mix for managed forest
    in the Maritimes.
    """
    rng = np.random.default_rng(seed)

    frame = aoi_geometry(aoi).to_crs(CRS_ANALYSIS)
    minx, miny, maxx, maxy = frame.total_bounds

    # Spacing chosen so the grid yields comfortably more cells than requested,
    # then a random sample keeps the register from looking machine-made.
    area_m2 = (maxx - minx) * (maxy - miny)
    target_cell_area = area_m2 / max(n_stands * 1.6, 1)
    spacing = math.sqrt(target_cell_area * 2 / math.sqrt(3))

    cells = _hex_grid((minx, miny, maxx, maxy), spacing)
    grid = gpd.GeoDataFrame(geometry=cells, crs=CRS_ANALYSIS)
    grid = grid[grid.intersects(frame.geometry.iloc[0])].reset_index(drop=True)

    if len(grid) > n_stands:
        keep = rng.choice(len(grid), size=n_stands, replace=False)
        grid = grid.iloc[sorted(keep)].reset_index(drop=True)

    # Jitter the vertices so stands look surveyed rather than tessellated.
    jitter = spacing * 0.06
    grid["geometry"] = [
        Polygon(
            [(x + rng.normal(0, jitter), y + rng.normal(0, jitter)) for x, y in geom.exterior.coords[:-1]]
        )
        for geom in grid.geometry
    ]

    n = len(grid)
    species = rng.choice(SPECIES_GROUPS, size=n, p=[0.52, 0.28, 0.20])
    planted = rng.integers(1968, 2023, size=n)
    # Natural stands carry no planting year, which is the nullable case that
    # breaks naive downstream code if it is never exercised.
    natural = rng.random(n) < 0.30

    grid["stand_id"] = [f"{aoi.name[:3].upper()}-{i:05d}" for i in range(1, n + 1)]
    grid["licence_block"] = rng.choice([f"LB-{c}" for c in "ABCDEF"], size=n)
    grid["species_group"] = species
    grid["planted_year"] = pd.array(np.where(natural, None, planted), dtype="Int64")
    grid["management_regime"] = np.where(natural, "natural", rng.choice(["plantation", "thinned"], size=n))
    grid["area_ha"] = grid.geometry.area / 10_000.0
    grid["source"] = "synthetic"

    return grid[
        [
            "stand_id",
            "licence_block",
            "species_group",
            "planted_year",
            "management_regime",
            "area_ha",
            "source",
            "geometry",
        ]
    ]


def load_stand_register(path: str, layer: str | None = None) -> gpd.GeoDataFrame:
    """Load a real stand register from a Lakehouse file.

    Accepts anything GeoPandas can open: GeoPackage, shapefile, GeoParquet or
    FlatGeobuf. The CRS is never assumed; if the source does not declare one the
    caller has to say what it is, because guessing here is how geometry ends up
    in the ocean.
    """
    gdf = gpd.read_file(path, layer=layer) if layer else gpd.read_file(path)
    if gdf.crs is None:
        raise ValueError(
            f"{path} declares no CRS. Call .set_crs(<epsg>) explicitly rather than letting the "
            "pipeline guess; a wrong guess produces geometry in the wrong place and no error."
        )
    required = {"stand_id", "species_group"}
    missing = required - set(gdf.columns)
    if missing:
        raise ValueError(f"stand register is missing required columns: {sorted(missing)}")
    return gdf


def ensure_projected(gdf: gpd.GeoDataFrame, epsg: int = CRS_ANALYSIS) -> gpd.GeoDataFrame:
    """Reproject to the analysis CRS, refusing to act on undeclared geometry."""
    if gdf.crs is None:
        raise ValueError(
            "GeoDataFrame has no CRS. Use .set_crs() to declare what the coordinates already are, "
            "then .to_crs() to transform them."
        )
    if gdf.crs.to_epsg() == epsg:
        return gdf
    return gdf.to_crs(epsg)


def add_display_centroids(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Add WGS84 latitude and longitude columns for Power BI map visuals.

    The centroid is computed in the projected CRS so it is geometrically
    correct, then converted to degrees for display. Doing it the other way round
    puts the point in a subtly wrong place, and the error grows with latitude.
    """
    projected = ensure_projected(gdf, CRS_ANALYSIS)
    centroids = projected.geometry.centroid.to_crs(CRS_WGS84)
    out = gdf.copy()
    out["lon"] = centroids.x.to_numpy()
    out["lat"] = centroids.y.to_numpy()
    return out
