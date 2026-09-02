"""Data quality gates.

One gate sits between silver and gold. Its job is to stop a month that looks
complete and is not from reaching a report that someone will act on.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import pandas as pd

from .config import THRESHOLDS


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str
    blocking: bool = True


@dataclass
class QualityReport:
    results: list[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.results if r.blocking)

    def add(self, result: CheckResult) -> None:
        self.results.append(result)

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame([r.__dict__ for r in self.results])

    def render(self) -> str:
        width = max((len(r.name) for r in self.results), default=10)
        lines = []
        for r in self.results:
            status = "PASS" if r.passed else ("FAIL" if r.blocking else "WARN")
            lines.append(f"[{status:<4}] {r.name.ljust(width)}  {r.detail}")
        verdict = "gate open" if self.passed else "GATE CLOSED, run stopped"
        lines.append("")
        lines.append(verdict)
        return "\n".join(lines)

    def raise_if_failed(self) -> None:
        if not self.passed:
            failures = [r.name for r in self.results if r.blocking and not r.passed]
            raise RuntimeError(
                f"quality gate closed on {failures}. Publishing a period that fails these checks "
                "produces a report that looks complete and is not."
            )


def check_observations(
    observations: pd.DataFrame,
    expected_stands: int,
    min_trusted_fraction: float = 0.70,
) -> QualityReport:
    """Run the silver-to-gold gate."""
    report = QualityReport()
    threshold = THRESHOLDS["min_valid_pixel_fraction"]

    report.add(_not_empty(observations))
    report.add(_unique_grain(observations, ["stand_id", "scene_date"]))
    report.add(_trusted_coverage(observations, expected_stands, threshold, min_trusted_fraction))
    report.add(_index_ranges(observations))
    report.add(_area_plausible(observations))
    report.add(_no_all_null_indices(observations))
    return report


def _not_empty(df: pd.DataFrame) -> CheckResult:
    return CheckResult(
        name="observations present",
        passed=not df.empty,
        detail=f"{len(df)} rows",
    )


def _unique_grain(df: pd.DataFrame, keys: list[str]) -> CheckResult:
    if df.empty or not set(keys).issubset(df.columns):
        return CheckResult("grain is unique", False, f"cannot evaluate, missing {keys}")
    duplicates = int(df.duplicated(subset=keys).sum())
    return CheckResult(
        name="grain is unique",
        passed=duplicates == 0,
        detail=f"{duplicates} duplicate rows on {keys}",
    )


def _trusted_coverage(
    df: pd.DataFrame,
    expected_stands: int,
    valid_threshold: float,
    min_fraction: float,
) -> CheckResult:
    if df.empty or expected_stands == 0:
        return CheckResult("trusted stand coverage", False, "no observations to evaluate")
    trusted = df[df["valid_pixel_fraction"] >= valid_threshold]["stand_id"].nunique()
    fraction = trusted / expected_stands
    return CheckResult(
        name="trusted stand coverage",
        passed=fraction >= min_fraction,
        detail=f"{trusted}/{expected_stands} stands trusted ({fraction:.0%}), floor {min_fraction:.0%}",
    )


def _index_ranges(df: pd.DataFrame) -> CheckResult:
    """Normalised indices must sit between -1 and 1.

    A value outside that range means the reflectance scale factor was skipped or
    a band was mapped to the wrong asset, and both produce plausible-looking
    output further down.
    """
    offenders: list[str] = []
    for col in [c for c in df.columns if c.startswith(("ndvi", "ndmi", "nbr"))]:
        series = df[col].dropna()
        if series.empty:
            continue
        if series.min() < -1.001 or series.max() > 1.001:
            offenders.append(f"{col} [{series.min():.2f}, {series.max():.2f}]")
    return CheckResult(
        name="index values in range",
        passed=not offenders,
        detail="all within -1 to 1" if not offenders else "; ".join(offenders),
    )


def _area_plausible(df: pd.DataFrame, min_ha: float = 0.5, max_ha: float = 5_000.0) -> CheckResult:
    """Stand areas outside this range usually mean a projection problem.

    Square degrees come out near zero. A double projection comes out enormous.
    Both are caught here rather than in a report review three weeks later.
    """
    if "area_ha" not in df.columns or df.empty:
        return CheckResult("stand area plausible", False, "area_ha column absent", blocking=False)
    series = df["area_ha"].dropna()
    if series.empty:
        return CheckResult("stand area plausible", False, "all area values null")
    bad = int(((series < min_ha) | (series > max_ha)).sum())
    return CheckResult(
        name="stand area plausible",
        passed=bad == 0,
        detail=f"{bad} rows outside {min_ha} to {max_ha} ha, range {series.min():.1f} to {series.max():.1f}",
    )


def _no_all_null_indices(df: pd.DataFrame) -> CheckResult:
    offenders = [
        col
        for col in df.columns
        if col.startswith(("ndvi", "ndmi", "nbr", "evi")) and df[col].notna().sum() == 0
    ]
    return CheckResult(
        name="indices populated",
        passed=not offenders,
        detail="all populated" if not offenders else f"entirely null: {offenders}",
    )


def check_narratives(narratives: pd.DataFrame, max_failure_rate: float = 0.20) -> QualityReport:
    """Gate on AI enrichment quality without blocking the pipeline.

    Narrative failures are warnings rather than blockers. A suppressed sentence
    costs a planner a tooltip; a blocked pipeline costs them the whole report.
    """
    report = QualityReport()
    if narratives.empty:
        report.add(CheckResult("narratives present", False, "no rows", blocking=False))
        return report

    failed = int((~narratives["validation_status"].isin(["ok", "stubbed"])).sum())
    rate = failed / len(narratives)
    report.add(
        CheckResult(
            name="narrative validation rate",
            passed=rate <= max_failure_rate,
            detail=f"{failed}/{len(narratives)} failed validation ({rate:.0%}), ceiling {max_failure_rate:.0%}",
            blocking=False,
        )
    )
    report.add(
        CheckResult(
            name="failed narratives suppressed",
            passed=bool(narratives.loc[~narratives["validation_status"].isin(["ok", "stubbed"]), "narrative"].isna().all()),
            detail="unvalidated narratives must not be published",
            blocking=True,
        )
    )
    return report


def run_checks(checks: dict[str, Callable[[], bool]]) -> QualityReport:
    """Adapter for ad-hoc checks written inline in a notebook."""
    report = QualityReport()
    for name, fn in checks.items():
        try:
            passed = bool(fn())
            report.add(CheckResult(name, passed, "" if passed else "assertion returned False"))
        except Exception as exc:  # noqa: BLE001
            report.add(CheckResult(name, False, f"{type(exc).__name__}: {exc}"))
    return report
