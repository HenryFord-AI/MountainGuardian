"""
MountainGuardian G03B – traceable Top Risk Driver contribution objects.

Deterministic decomposition, no LLM ranking (doc 04 §40):

For the Current Risk Index C = 0.70 x B + 0.30 x (0.60 x R + 0.40 x F):
  * each static factor:   0.70 x its B contribution;
  * recent precipitation: 0.30 x 0.60 x R = 0.18 x R;
  * forecast precipitation: 0.30 x 0.40 x F = 0.12 x F.
  The sum of all contributions equals C within numerical tolerance.

For the 7-Day Outlook O7 = 0.70 x B + 0.30 x F:
  * each static factor:   0.70 x its B contribution;
  * forecast precipitation: 0.30 x F.
  The sum equals O7 within numerical tolerance.

Ordering is deterministic: contribution_points descending with a stable
tie-break on driver_id ascending. Every static driver stays traceable to
region.json; every dynamic driver records the monitoring point that drove
the regional percentile and the climatology reference identity.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from riskwatch.engine.formulas import (
    WEIGHT_FORECAST_IN_C,
    WEIGHT_FORECAST_IN_O7,
    WEIGHT_RECENT_IN_C,
    WEIGHT_STATIC_IN_C,
    WEIGHT_STATIC_IN_O7,
    round_display,
)
from riskwatch.engine.static_baseline import StaticBaseline

DRIVER_TYPE_STATIC = "STATIC"
DRIVER_TYPE_DYNAMIC = "DYNAMIC"

DRIVER_ID_RECENT = "dynamic:recent_precipitation"
DRIVER_ID_FORECAST = "dynamic:forecast_precipitation"

LABEL_RECENT = "Recent 7-day precipitation percentile (conservative regional maximum)"
LABEL_FORECAST = "Forecast 7-day precipitation percentile (conservative regional maximum)"

RAW_KIND_SCORE = "score_0_to_5"
RAW_KIND_PERCENTILE = "percentile_0_to_100"

#: Tolerance for the "contributions sum to the index" audit checks.
CONTRIBUTION_SUM_TOLERANCE = 1e-9


@dataclass(frozen=True)
class RiskDriverContribution:
    """One traceable contribution point of a risk index."""

    driver_id: str
    driver_type: str                       # STATIC | DYNAMIC
    label: str
    raw_value: float                       # factor score or percentile
    raw_value_kind: str
    weight_or_coefficient: float           # coefficient applied to raw value
    contribution_points: float             # full precision
    provenance: dict
    monitoring_point_id: Optional[str] = None

    @property
    def contribution_points_rounded(self) -> float:
        return round_display(self.contribution_points)

    def to_dict(self) -> dict[str, Any]:
        return {
            "driver_id": self.driver_id,
            "driver_type": self.driver_type,
            "label": self.label,
            "raw_value": self.raw_value,
            "raw_value_kind": self.raw_value_kind,
            "weight_or_coefficient": self.weight_or_coefficient,
            "contribution_points": self.contribution_points,
            "contribution_points_rounded": self.contribution_points_rounded,
            "monitoring_point_id": self.monitoring_point_id,
            "provenance": dict(self.provenance),
        }


def sort_drivers(drivers) -> tuple:
    """Deterministic order: contribution descending, stable tie-break on id."""
    return tuple(
        sorted(drivers, key=lambda d: (-d.contribution_points, d.driver_id))
    )


def contribution_sum(drivers) -> float:
    return sum(d.contribution_points for d in drivers)


def sums_to_index(drivers, index: float, tolerance: float = CONTRIBUTION_SUM_TOLERANCE) -> bool:
    return abs(contribution_sum(drivers) - float(index)) <= tolerance


def _static_drivers(
    baseline: StaticBaseline, static_weight: float
) -> list[RiskDriverContribution]:
    drivers = []
    for f in baseline.factors:
        drivers.append(
            RiskDriverContribution(
                driver_id=f"static:{f.factor_id}",
                driver_type=DRIVER_TYPE_STATIC,
                label=f.name,
                raw_value=f.score_0_to_5,
                raw_value_kind=RAW_KIND_SCORE,
                weight_or_coefficient=static_weight * (f.normalized_weight_pct / 5.0),
                contribution_points=static_weight * f.contribution,
                provenance={
                    "source": "region.json static_susceptibility_inputs",
                    "factor_id": f.factor_id,
                    "factor_key": f.key,
                    "score_0_to_5": f.score_0_to_5,
                    "normalized_weight_pct": f.normalized_weight_pct,
                    "b_contribution": f.contribution,
                    "static_coefficient": static_weight,
                    "source_ids": list(f.source_ids),
                    "region_id": baseline.region_id,
                    "region_config_version": baseline.region_config_version,
                    "scoring_config_version": baseline.scoring_config_version,
                },
            )
        )
    return drivers


def _dynamic_driver(
    driver_id: str,
    label: str,
    percentile: float,
    coefficient: float,
    aggregation,
) -> RiskDriverContribution:
    clim = {}
    driver_point = getattr(aggregation, "driver_point", None)
    if driver_point is not None:
        clim = dict(driver_point.climatology)
    return RiskDriverContribution(
        driver_id=driver_id,
        driver_type=DRIVER_TYPE_DYNAMIC,
        label=label,
        raw_value=percentile,
        raw_value_kind=RAW_KIND_PERCENTILE,
        weight_or_coefficient=coefficient,
        contribution_points=coefficient * percentile,
        monitoring_point_id=getattr(aggregation, "driver_point_id", None),
        provenance={
            "driver_point_id": getattr(aggregation, "driver_point_id", None),
            "regional_percentile": percentile,
            "aggregation_rule": getattr(
                aggregation, "aggregation_rule", "max_of_successful_points"
            ),
            "all_point_percentiles": dict(getattr(aggregation, "all_point_values", {})),
            "climatology_checksum": clim.get("checksum"),
            "climatology_algorithm_version": clim.get("algorithm_version"),
            "climatology_source_model": clim.get("source_model"),
            "climatology_baseline": clim.get("baseline"),
            "percentile_method": clim.get("percentile_method"),
        },
    )


def build_current_risk_drivers(baseline: StaticBaseline, R: float, F: float,
                               recent_aggregation, forecast_aggregation) -> tuple:
    """Traceable decomposition of C; contributions sum to C."""
    drivers = _static_drivers(baseline, WEIGHT_STATIC_IN_C)
    drivers.append(
        _dynamic_driver(
            DRIVER_ID_RECENT, LABEL_RECENT, R, WEIGHT_RECENT_IN_C, recent_aggregation
        )
    )
    drivers.append(
        _dynamic_driver(
            DRIVER_ID_FORECAST, LABEL_FORECAST, F, WEIGHT_FORECAST_IN_C, forecast_aggregation
        )
    )
    return sort_drivers(drivers)


def build_outlook_drivers(baseline: StaticBaseline, F: float,
                          forecast_aggregation) -> tuple:
    """Traceable decomposition of O7; contributions sum to O7."""
    drivers = _static_drivers(baseline, WEIGHT_STATIC_IN_O7)
    drivers.append(
        _dynamic_driver(
            DRIVER_ID_FORECAST, LABEL_FORECAST, F, WEIGHT_FORECAST_IN_O7, forecast_aggregation
        )
    )
    return sort_drivers(drivers)
