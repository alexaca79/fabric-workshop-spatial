"""Gold layer classification: turning index values into a forest class.

Two implementations. The rule-based classifier is the default because a forester
can argue with a number in a threshold dictionary, and because every class it
produces can be explained without opening a model. The random forest is offered
for the assignment, once labelled inventory is available.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import FOREST_CLASSES, THRESHOLDS

RULE_VERSION = "rule_v1"
MODEL_VERSION = "rf_v1"


def classify_rule_based(
    df: pd.DataFrame,
    thresholds: dict[str, float] | None = None,
) -> pd.DataFrame:
    """Assign a forest class from spectral indices using explicit thresholds.

    Order matters. The gates run from most to least certain, so a clear-cut is
    identified as harvested before anything tries to decide what species used to
    grow there.

    Confidence is distance from the nearest decision boundary, normalised. It is
    a statement about how close the call was, not a probability, and the column
    name and the documentation both say so.
    """
    t = {**THRESHOLDS, **(thresholds or {})}
    out = df.copy()

    ndvi = out["ndvi_p90"].to_numpy(dtype="float64")
    ndmi = out["ndmi_mean"].to_numpy(dtype="float64")
    nbr = out["nbr_mean"].to_numpy(dtype="float64")
    valid = out["valid_pixel_fraction"].to_numpy(dtype="float64")

    classes = np.full(len(out), "mixedwood", dtype=object)
    confidence = np.full(len(out), 0.5, dtype="float64")

    # Gate 1: not enough usable pixels to say anything at all.
    untrusted = valid < t["min_valid_pixel_fraction"]

    # Gate 2: not forest.
    non_forest = (~untrusted) & (ndvi < t["non_forest_ndvi_max"])
    classes[non_forest] = "non_forest"
    confidence[non_forest] = _margin(t["non_forest_ndvi_max"] - ndvi[non_forest], 0.20)

    # Gate 3: canopy removed recently. Low burn ratio with vegetation present.
    harvested = (~untrusted) & (~non_forest) & (nbr < t["recently_harvested_nbr_max"])
    classes[harvested] = "recently_harvested"
    confidence[harvested] = _margin(t["recently_harvested_nbr_max"] - nbr[harvested], 0.20)

    # Gate 4: regenerating. Green but not yet closed canopy.
    regen = (~untrusted) & (~non_forest) & (~harvested) & (ndvi < t["regenerating_ndvi_max"])
    classes[regen] = "regenerating"
    confidence[regen] = _margin(t["regenerating_ndvi_max"] - ndvi[regen], 0.25)

    remaining = (~untrusted) & (~non_forest) & (~harvested) & (~regen)

    # Gate 5: species group from canopy moisture. Conifer retains more moisture
    # in the shortwave infrared through the season than deciduous canopy.
    softwood = remaining & (ndmi >= t["softwood_ndmi_min"])
    classes[softwood] = "softwood"
    confidence[softwood] = _margin(ndmi[softwood] - t["softwood_ndmi_min"], 0.15)

    hardwood = remaining & (ndmi <= t["hardwood_ndmi_max"])
    classes[hardwood] = "hardwood"
    confidence[hardwood] = _margin(t["hardwood_ndmi_max"] - ndmi[hardwood], 0.15)

    mixed = remaining & (~softwood) & (~hardwood)
    classes[mixed] = "mixedwood"
    # Mixedwood is the residual class, so confidence is genuinely low by
    # construction. Reporting it as high would be dishonest.
    confidence[mixed] = 0.45

    classes[untrusted] = None
    confidence[untrusted] = 0.0

    out["forest_class"] = classes
    out["class_confidence"] = np.clip(np.nan_to_num(confidence, nan=0.0), 0.0, 1.0).round(3)
    out["class_method"] = RULE_VERSION
    out["is_trusted"] = ~untrusted
    return out


def _margin(distance: np.ndarray, scale: float) -> np.ndarray:
    """Map distance from a decision boundary onto a 0.5 to 1.0 confidence range."""
    with np.errstate(invalid="ignore"):
        return 0.5 + 0.5 * np.clip(np.abs(distance) / scale, 0.0, 1.0)


def composite_by_period(
    observations: pd.DataFrame,
    period_start,
    period_end,
    min_valid_fraction: float | None = None,
) -> pd.DataFrame:
    """Reduce many scene-date observations per stand to one row per period.

    Trusted observations only. Averaging a cloudy row with a clear one produces
    a number that is defensible in neither direction.
    """
    threshold = min_valid_fraction if min_valid_fraction is not None else THRESHOLDS["min_valid_pixel_fraction"]

    window = observations[
        (pd.to_datetime(observations["scene_date"]) >= pd.to_datetime(period_start))
        & (pd.to_datetime(observations["scene_date"]) <= pd.to_datetime(period_end))
        & (observations["valid_pixel_fraction"] >= threshold)
    ]

    if window.empty:
        return pd.DataFrame(columns=observations.columns)

    numeric = [c for c in window.columns if c.startswith(("ndvi", "ndmi", "nbr", "evi"))]
    agg = {col: "median" for col in numeric}
    agg["valid_pixel_fraction"] = "mean"
    agg["pixel_count"] = "max"
    agg["area_ha"] = "first"

    for col in ("licence_block", "species_group", "management_regime"):
        if col in window.columns:
            agg[col] = "first"

    composite = window.groupby("stand_id", as_index=False).agg(agg)
    composite["observation_count"] = (
        window.groupby("stand_id")["scene_id"].nunique().reindex(composite["stand_id"]).to_numpy()
    )
    composite["period_start"] = pd.to_datetime(period_start).date()
    composite["period_end"] = pd.to_datetime(period_end).date()
    return composite


def agreement_with_register(df: pd.DataFrame) -> pd.DataFrame:
    """Compare the spectral class against the declared inventory species group.

    Disagreement is not automatically an error. The inventory can be out of
    date, the stand can have been harvested, or the spectral signal can be
    ambiguous in mixedwood. The column exists to build a review queue, not to
    overwrite the register.
    """
    out = df.copy()
    declared = out.get("species_group")
    if declared is None:
        out["register_agreement"] = "no_register_value"
        return out

    spectral = out["forest_class"]
    comparable = spectral.isin(["softwood", "hardwood", "mixedwood"]) & declared.notna()

    out["register_agreement"] = np.where(
        ~comparable,
        "not_comparable",
        np.where(spectral == declared, "agrees", "disagrees"),
    )
    return out


def train_random_forest(labelled: pd.DataFrame, feature_cols: list[str], label_col: str = "species_group"):
    """Train a random forest on labelled inventory. Assignment extension only.

    Offered as a path, not a default. A trained model needs labels you trust, a
    holdout you did not tune on, and a story for what happens when the imagery
    distribution shifts between seasons. Until those exist, thresholds are the
    more honest tool.
    """
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import classification_report

    frame = labelled.dropna(subset=[*feature_cols, label_col])
    if frame[label_col].nunique() < 2:
        raise ValueError("need at least two classes present to train a classifier")

    x_train, x_test, y_train, y_test = train_test_split(
        frame[feature_cols], frame[label_col], test_size=0.25, random_state=42, stratify=frame[label_col]
    )
    model = RandomForestClassifier(n_estimators=300, min_samples_leaf=3, random_state=42, class_weight="balanced")
    model.fit(x_train, y_train)
    report = classification_report(y_test, model.predict(x_test), zero_division=0)
    return model, report


def validate_classes(df: pd.DataFrame) -> None:
    """Fail the run if an unexpected class value reached the gold layer."""
    seen = set(df["forest_class"].dropna().unique())
    unexpected = seen - set(FOREST_CLASSES)
    if unexpected:
        raise ValueError(f"unexpected forest_class values in gold output: {sorted(unexpected)}")
