"""Change detection between two periods.

The operational question is not "what class is this stand" but "what changed
since I last looked, and does anyone need to go and stand in it".
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import THRESHOLDS

CHANGE_TYPES = ("harvest", "disturbance", "moisture_stress", "regrowth", "none")


def detect_change(
    current: pd.DataFrame,
    baseline: pd.DataFrame,
    thresholds: dict[str, float] | None = None,
) -> pd.DataFrame:
    """Compare two period composites and label what changed per stand.

    A drop in the normalised burn ratio is the primary canopy-removal signal.
    It cannot distinguish harvest from windthrow or fire, which is why the
    output carries a change type that a human confirms rather than a decision
    the pipeline makes alone.
    """
    t = {**THRESHOLDS, **(thresholds or {})}

    keys = ["stand_id"]
    joined = current.merge(baseline, on=keys, suffixes=("", "_base"), how="inner", validate="one_to_one")

    joined["delta_nbr"] = joined["nbr_mean_base"] - joined["nbr_mean"]
    joined["delta_ndvi"] = joined["ndvi_p90"] - joined["ndvi_p90_base"]
    joined["delta_ndmi"] = joined["ndmi_mean"] - joined["ndmi_mean_base"]

    change_type = np.full(len(joined), "none", dtype=object)

    canopy_loss = joined["delta_nbr"] >= t["harvest_delta_nbr_min"]
    # A stand the register calls plantation or thinned that loses canopy is
    # almost certainly a planned harvest. Everything else is disturbance until
    # someone confirms otherwise.
    planned = joined.get("management_regime", pd.Series("unknown", index=joined.index)).isin(
        ["plantation", "thinned"]
    )
    change_type[(canopy_loss & planned).to_numpy()] = "harvest"
    change_type[(canopy_loss & ~planned).to_numpy()] = "disturbance"

    stressed = (~canopy_loss) & (joined["ndmi_mean"] <= t["moisture_stress_ndmi_max"]) & (joined["delta_ndmi"] < -0.05)
    change_type[stressed.to_numpy()] = "moisture_stress"

    regrowth = (~canopy_loss) & (joined["delta_ndvi"] >= 0.10)
    change_type[regrowth.to_numpy()] = "regrowth"

    joined["change_type"] = change_type
    joined["severity"] = _severity(joined["delta_nbr"].to_numpy(), t["harvest_delta_nbr_min"])
    joined["requires_review"] = (
        joined["change_type"].isin(["disturbance", "moisture_stress"])
        | ((joined["change_type"] == "harvest") & (joined["severity"] == "high"))
    )
    joined["detected_on"] = joined["period_end"]

    columns = [
        "stand_id",
        "detected_on",
        "change_type",
        "delta_nbr",
        "delta_ndvi",
        "delta_ndmi",
        "severity",
        "requires_review",
        "area_ha",
    ]
    return joined[[c for c in columns if c in joined.columns]]


def _severity(delta_nbr: np.ndarray, threshold: float) -> np.ndarray:
    severity = np.full(delta_nbr.shape, "low", dtype=object)
    severity[delta_nbr >= threshold] = "moderate"
    severity[delta_nbr >= threshold * 2] = "high"
    return severity


def summarise_change(change: pd.DataFrame) -> pd.DataFrame:
    """One row per change type with area and stand counts, for the report header."""
    if change.empty:
        return pd.DataFrame(columns=["change_type", "stand_count", "area_ha", "review_count"])
    grouped = change.groupby("change_type", as_index=False).agg(
        stand_count=("stand_id", "nunique"),
        area_ha=("area_ha", "sum"),
        review_count=("requires_review", "sum"),
    )
    return grouped.sort_values("area_ha", ascending=False).reset_index(drop=True)
