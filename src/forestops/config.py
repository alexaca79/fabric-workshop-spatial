"""Single source of truth for pipeline configuration.

Every notebook and every pipeline activity resolves its settings from here, so
that changing the area of interest is a one-line change rather than a search
across six notebooks.
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field, asdict
from datetime import date

# --------------------------------------------------------------------------
# Coordinate reference systems
# --------------------------------------------------------------------------
# WGS84 geographic. STAC search geometry and Power BI map points.
CRS_WGS84 = 4326

# NAD83(CSRS) / New Brunswick Stereographic Double Projection, in metres.
# Every area, distance and buffer in silver and gold is computed in this CRS.
CRS_ANALYSIS = 2953

# Native Sentinel-2 grids covering New Brunswick.
CRS_UTM_19N = 32619
CRS_UTM_20N = 32620


# --------------------------------------------------------------------------
# Sentinel-2 bands
# --------------------------------------------------------------------------
# Asset keys as published by the Planetary Computer sentinel-2-l2a collection.
BANDS: tuple[str, ...] = ("B04", "B08", "B11", "B12", "SCL")

# Level 2A surface reflectance is stored as integers. Divide by this to get
# reflectance between 0 and 1. Omitting it cancels out in normalised ratios and
# silently moves every absolute threshold.
REFLECTANCE_SCALE = 10_000.0

# Scene classification layer values that must be masked out before any index is
# computed. See the Sentinel-2 L2A product definition for the full list.
SCL_INVALID: tuple[int, ...] = (
    0,   # no data
    1,   # saturated or defective
    2,   # dark area pixels
    3,   # cloud shadow
    8,   # cloud, medium probability
    9,   # cloud, high probability
    10,  # thin cirrus
    11,  # snow or ice
)


# --------------------------------------------------------------------------
# Classification thresholds
# --------------------------------------------------------------------------
# Deliberately explicit and auditable. A forester can argue with a number in
# this dictionary. Nobody can argue with a weight inside a language model.
THRESHOLDS: dict[str, float] = {
    "non_forest_ndvi_max": 0.30,
    "recently_harvested_nbr_max": 0.20,
    "regenerating_ndvi_max": 0.55,
    "softwood_ndmi_min": 0.18,
    "hardwood_ndmi_max": 0.10,
    "moisture_stress_ndmi_max": 0.05,
    "harvest_delta_nbr_min": 0.25,
    "min_valid_pixel_fraction": 0.60,
}

FOREST_CLASSES: tuple[str, ...] = (
    "softwood",
    "hardwood",
    "mixedwood",
    "regenerating",
    "recently_harvested",
    "non_forest",
)


@dataclass(frozen=True)
class AreaOfInterest:
    """A named bounding box in WGS84, ordered west, south, east, north."""

    name: str
    bbox: tuple[float, float, float, float]

    def __post_init__(self) -> None:
        west, south, east, north = self.bbox
        if west >= east:
            raise ValueError(f"west {west} must be less than east {east}; check the bbox order")
        if south >= north:
            raise ValueError(f"south {south} must be less than north {north}; check the bbox order")
        if not (-180 <= west <= 180 and -180 <= east <= 180):
            raise ValueError(f"longitudes out of range in {self.bbox}")
        if not (-90 <= south <= 90 and -90 <= north <= 90):
            raise ValueError(f"latitudes out of range in {self.bbox}")

    @property
    def width_km(self) -> float:
        west, south, east, north = self.bbox
        mid_lat_rad = math.radians((south + north) / 2)
        return (east - west) * 111.32 * abs(math.cos(mid_lat_rad))

    @property
    def height_km(self) -> float:
        _, south, _, north = self.bbox
        return (north - south) * 110.57


# Default area of interest: a block of managed forest in central New Brunswick.
# Participants replace this with their own operating area in the homework.
DEFAULT_AOI = AreaOfInterest(
    name="central-nb-block-a",
    bbox=(-66.90, 46.10, -66.40, 46.40),
)


@dataclass
class PipelineConfig:
    """Everything one pipeline run needs to know."""

    aoi: AreaOfInterest = DEFAULT_AOI
    date_start: str = "2026-06-01"
    date_end: str = "2026-08-31"
    max_cloud_cover: float = 20.0
    target_epsg: int = CRS_ANALYSIS
    resolution_m: int = 20
    max_scenes: int = 6
    enable_ai: bool = True
    use_synthetic_stands: bool = True
    synthetic_stand_count: int = 120
    random_seed: int = 20260902

    lakehouse_name: str = "lh_woodlands"
    bronze_files_root: str = "Files/bronze"
    silver_files_root: str = "Files/silver"

    tables: dict[str, str] = field(
        default_factory=lambda: {
            "scene_catalog": "bronze_scene_catalog",
            "stand_register": "bronze_stand_register",
            "observations": "silver_stand_observations",
            "classification": "gold_stand_classification",
            "change": "gold_stand_change",
            "narrative": "gold_stand_narrative",
            "facts": "gold_stand_facts",
            "dim_stand": "gold_dim_stand",
            "dim_date": "gold_dim_date",
        }
    )

    @classmethod
    def from_parameters(cls, **overrides: object) -> "PipelineConfig":
        """Build a config from Fabric pipeline parameters.

        Pipeline parameters arrive as strings, so values are coerced here rather
        than being trusted. An area of interest arriving as the string
        "[-66.9, 46.1, -66.4, 46.4]" is the normal case, not an edge case.
        """
        cfg = cls()
        aoi_name = overrides.pop("aoi_name", None)
        aoi_bbox = overrides.pop("aoi_bbox", None)
        if aoi_name or aoi_bbox:
            if isinstance(aoi_bbox, str):
                aoi_bbox = json.loads(aoi_bbox)
            cfg.aoi = AreaOfInterest(
                name=str(aoi_name or cfg.aoi.name),
                bbox=tuple(float(v) for v in (aoi_bbox or cfg.aoi.bbox)),  # type: ignore[arg-type]
            )
        for key, value in overrides.items():
            if not hasattr(cfg, key):
                raise KeyError(f"unknown pipeline parameter '{key}'")
            current = getattr(cfg, key)
            if isinstance(current, bool):
                value = str(value).strip().lower() in {"1", "true", "yes"}
            elif isinstance(current, int) and not isinstance(current, bool):
                value = int(float(value))  # type: ignore[arg-type]
            elif isinstance(current, float):
                value = float(value)  # type: ignore[arg-type]
            setattr(cfg, key, value)
        return cfg

    def table_path(self, key: str) -> str:
        """Fully qualified Spark table name for one of the pipeline tables."""
        return self.tables[key]

    def scene_dir(self, scene_id: str) -> str:
        return f"{self.bronze_files_root}/scenes/{self.aoi.name}/{scene_id}"

    def describe(self) -> str:
        payload = asdict(self)
        payload["aoi"] = {"name": self.aoi.name, "bbox": list(self.aoi.bbox)}
        payload["aoi_width_km"] = round(self.aoi.width_km, 1)
        payload["aoi_height_km"] = round(self.aoi.height_km, 1)
        return json.dumps(payload, indent=2, default=str)


def foundry_settings() -> dict[str, str | None]:
    """Foundry connection details, read from the environment.

    Returns None values rather than raising so that a notebook can decide to
    fall back to the offline stub instead of failing the whole run.
    """
    return {
        "endpoint": os.environ.get("FOUNDRY_ENDPOINT"),
        "deployment": os.environ.get("FOUNDRY_DEPLOYMENT", "gpt-4o-mini"),
        "api_version": os.environ.get("FOUNDRY_API_VERSION", "2024-10-21"),
        "api_key": os.environ.get("FOUNDRY_API_KEY"),
    }


def run_id(prefix: str = "run") -> str:
    """Correlation id written to every table produced by a single run."""
    from datetime import datetime, timezone

    return f"{prefix}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"


def today_iso() -> str:
    return date.today().isoformat()
