"""
MountainGuardian G03B – deterministic Risk Watch engine core.

Pure offline computation over already-normalized G03A contracts:
  * region config (riskwatch.region.RegionConfig),
  * operational weather (riskwatch.weather PointWeather / PointWeatherFailure
    / RegionWeatherResult),
  * 1991–2020 climatology references (riskwatch.climatology).

It computes point precipitation percentiles with the SAME G03A percentile
algorithm (mean_rank via climatology.percentile_of) and the SAME frozen
month assignment (window-end natural month), aggregates the conservative
regional maxima R and F, and applies the frozen formulas:

    D  = 0.60 x R + 0.40 x F
    C  = 0.70 x B + 0.30 x D
    O7 = 0.70 x B + 0.30 x F

Hard boundaries: no network, no LLM, no clock inside the computation, no
Historical Replay Case Pack, no zero-filling of missing values, no official
C/O7 when required inputs are insufficient. Temperature and any optional
evidence never modify the numeric formulas (doc 04 §19/§20).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Mapping, Optional, Sequence

from riskwatch.climatology import ClimatologyReference, percentile_of
from riskwatch.engine.comparison import (
    PreviousState,
    build_what_changed,
)
from riskwatch.engine.drivers import (
    build_current_risk_drivers,
    build_outlook_drivers,
)
from riskwatch.engine.formulas import (
    ALGORITHM_VERSION,
    DIRECTION_NO_HISTORY,
    FORMULA_VERSION,
    NUMERIC_METHOD,
    RISK_INDEX_SEMANTICS,
    ROUNDING_POLICY,
    STATUS_COMPLETED,
    STATUS_COMPLETED_WITH_LIMITATIONS,
    STATUS_FAILED,
    WEIGHT_DYNAMIC_IN_C,
    WEIGHT_FORECAST_IN_D,
    WEIGHT_FORECAST_IN_O7,
    WEIGHT_RECENT_IN_D,
    WEIGHT_STATIC_IN_C,
    WEIGHT_STATIC_IN_O7,
    classify_band,
    classify_direction,
    compute_C,
    compute_D,
    compute_O7,
    round_display,
    validate_index,
)
from riskwatch.engine.static_baseline import (
    StaticBaseline,
    compute_static_baseline,
)
from riskwatch.region import RegionConfig
from riskwatch.snapshot_store import SCAN_MODE_BACKFILL
from riskwatch.weather import (
    QUALITY_MISSING,
    QUALITY_STALE,
    PointWeather,
    PointWeatherFailure,
    RegionWeatherResult,
)

WINDOW_RECENT = "recent"
WINDOW_FORECAST = "forecast"

AGGREGATION_RULE = "max_of_successful_points_conservative"


class RiskWatchInputError(ValueError):
    """Supplied engine inputs violate the required contract."""


@dataclass(frozen=True)
class PointPercentileResult:
    """Per-point precipitation percentile with full traceability."""

    point_id: str
    window_kind: str                 # recent | forecast
    window_start: str
    window_end: str
    cumulative_precip_mm: float
    climatology_month: int
    month_assignment: str
    percentile: float                # full precision (G03A mean-rank output)
    percentile_method: str
    weather_quality: str
    climatology: dict                # reference identity: baseline/model/version/checksum
    limitations: tuple = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "point_id": self.point_id,
            "window_kind": self.window_kind,
            "window_start": self.window_start,
            "window_end": self.window_end,
            "cumulative_precip_mm": self.cumulative_precip_mm,
            "climatology_month": self.climatology_month,
            "month_assignment": self.month_assignment,
            "percentile": self.percentile,
            "percentile_rounded": round_display(self.percentile),
            "percentile_method": self.percentile_method,
            "weather_quality": self.weather_quality,
            "climatology": dict(self.climatology),
            "limitations": list(self.limitations),
        }


@dataclass(frozen=True)
class PointExclusion:
    """Explicit, non-fabricated exclusion of one point from one aggregation."""

    point_id: str
    window_kind: str
    reason: str
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "point_id": self.point_id,
            "window_kind": self.window_kind,
            "reason": self.reason,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class RegionalAggregation:
    """Conservative regional max-percentile aggregation with driver identity."""

    kind: str                        # recent -> R, forecast -> F
    index_name: str                  # "R" | "F"
    value: Optional[float]
    driver_point_id: Optional[str]
    point_percentiles: tuple         # tuple[PointPercentileResult, ...] config order
    exclusions: tuple                # tuple[PointExclusion, ...]
    aggregation_rule: str = AGGREGATION_RULE

    @property
    def all_point_values(self) -> dict[str, float]:
        return {p.point_id: p.percentile for p in self.point_percentiles}

    @property
    def driver_point(self) -> Optional[PointPercentileResult]:
        for p in self.point_percentiles:
            if p.point_id == self.driver_point_id:
                return p
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "index_name": self.index_name,
            "value": self.value,
            "value_rounded": round_display(self.value),
            "driver_point_id": self.driver_point_id,
            "all_point_values": self.all_point_values,
            "aggregation_rule": self.aggregation_rule,
            "point_percentiles": [p.to_dict() for p in self.point_percentiles],
            "exclusions": [e.to_dict() for e in self.exclusions],
        }


@dataclass(frozen=True)
class RiskWatchResult:
    """Structured deterministic Risk Watch result (no LLM narrative)."""

    algorithm_version: str
    formula_version: str
    region_id: str
    run_id: str
    status: str
    static_baseline: StaticBaseline
    recent_aggregation: RegionalAggregation
    forecast_aggregation: RegionalAggregation
    R: Optional[float]
    F: Optional[float]
    D: Optional[float]
    C: Optional[float]
    O7: Optional[float]
    current_risk_level: Optional[str]
    outlook_7d_level: Optional[str]
    risk_direction: Optional[str]
    previous_C: Optional[float]
    delta_C: Optional[float]
    top_drivers: tuple
    outlook_drivers: tuple
    what_changed: dict
    missing_data: tuple
    limitations: tuple
    optional_evidence_availability: tuple
    provenance: dict
    numeric_method: dict
    semantics: str = RISK_INDEX_SEMANTICS
    rounding_policy: str = ROUNDING_POLICY

    @property
    def B(self) -> float:
        return self.static_baseline.value

    def to_dict(self) -> dict[str, Any]:
        baseline = self.static_baseline
        recent = self.recent_aggregation
        forecast = self.forecast_aggregation
        d_components = None
        if self.D is not None:
            d_components = {
                "recent_component": WEIGHT_RECENT_IN_D * self.R,
                "forecast_component": WEIGHT_FORECAST_IN_D * self.F,
                "formula": "D = 0.60 x R + 0.40 x F (frozen v1.0)",
            }
        c_components = None
        if self.C is not None:
            c_components = {
                "static_component": WEIGHT_STATIC_IN_C * baseline.value,
                "dynamic_component": WEIGHT_DYNAMIC_IN_C * self.D,
                "formula": "C = 0.70 x B + 0.30 x D (frozen v1.0)",
            }
        o7_components = None
        if self.O7 is not None:
            o7_components = {
                "static_component": WEIGHT_STATIC_IN_O7 * baseline.value,
                "forecast_component": WEIGHT_FORECAST_IN_O7 * self.F,
                "formula": "O7 = 0.70 x B + 0.30 x F (frozen v1.0)",
            }
        return {
            "algorithm_version": self.algorithm_version,
            "formula_version": self.formula_version,
            "region_id": self.region_id,
            "run_id": self.run_id,
            "status": self.status,
            "provenance": dict(self.provenance),
            "static_baseline": baseline.to_dict(),
            "B": baseline.value,
            "B_rounded": baseline.value_rounded,
            "point_recent_percentiles": {
                p.point_id: p.to_dict() for p in recent.point_percentiles
            },
            "R": recent.value,
            "R_rounded": round_display(recent.value),
            "R_driver_point": recent.driver_point_id,
            "R_all_point_values": recent.all_point_values,
            "recent_aggregation": recent.to_dict(),
            "point_forecast_percentiles": {
                p.point_id: p.to_dict() for p in forecast.point_percentiles
            },
            "F": forecast.value,
            "F_rounded": round_display(forecast.value),
            "F_driver_point": forecast.driver_point_id,
            "F_all_point_values": forecast.all_point_values,
            "forecast_aggregation": forecast.to_dict(),
            "D": self.D,
            "D_rounded": round_display(self.D),
            "D_components": d_components,
            "dynamic_trigger_index": self.D,
            "C": self.C,
            "C_rounded": round_display(self.C),
            "C_components": c_components,
            "current_risk_index": self.C,
            "current_risk_level": self.current_risk_level,
            "O7": self.O7,
            "O7_rounded": round_display(self.O7),
            "O7_components": o7_components,
            "outlook_7d_index": self.O7,
            "outlook_7d_level": self.outlook_7d_level,
            "recent_precip_percentile": recent.value,
            "forecast_precip_percentile": forecast.value,
            "risk_direction": self.risk_direction,
            "previous_C": self.previous_C,
            "delta_C": self.delta_C,
            "top_drivers": [d.to_dict() for d in self.top_drivers],
            "outlook_drivers": [d.to_dict() for d in self.outlook_drivers],
            "what_changed": self.what_changed,
            "missing_data": [m for m in self.missing_data],
            "limitations": list(self.limitations),
            "optional_evidence_availability": list(self.optional_evidence_availability),
            "numeric_method": dict(self.numeric_method),
            "display": {
                "decimals": 2,
                "policy": self.rounding_policy,
                "B": baseline.value_rounded,
                "R": round_display(recent.value),
                "F": round_display(forecast.value),
                "D": round_display(self.D),
                "C": round_display(self.C),
                "O7": round_display(self.O7),
            },
            "semantics": self.semantics,
        }

    def to_json(self, indent: int | None = None) -> str:
        """Stable serialization: identical input -> byte-identical JSON."""
        import json

        return json.dumps(
            self.to_dict(), ensure_ascii=False, sort_keys=True, indent=indent
        )


def _weather_points(
    weather: RegionWeatherResult | Mapping[str, Any],
) -> dict[str, Any]:
    if isinstance(weather, RegionWeatherResult):
        return dict(weather.points)
    if isinstance(weather, Mapping):
        return dict(weather)
    raise RiskWatchInputError(
        "weather must be a RegionWeatherResult or a mapping of point_id -> "
        "PointWeather/PointWeatherFailure"
    )


def _optional_evidence_ids(optional_evidence: Optional[Sequence[Any]]) -> tuple:
    if not optional_evidence:
        return ()
    ids = []
    for item in optional_evidence:
        if isinstance(item, str):
            ids.append(item)
        elif isinstance(item, Mapping):
            ident = item.get("evidence_id") or item.get("id") or item.get("type")
            if ident is not None:
                ids.append(str(ident))
    return tuple(ids)


def _climatology_identity(ref: ClimatologyReference) -> dict[str, Any]:
    return {
        "baseline": [ref.baseline_start, ref.baseline_end],
        "source_model": ref.source_model,
        "preferred_model": ref.preferred_model,
        "model_fallback_note": ref.model_fallback_note,
        "algorithm_version": ref.algorithm_version,
        "month_assignment": ref.month_assignment,
        "percentile_method": ref.percentile_method,
        "checksum": ref.checksum,
    }


def collect_point_percentile(
    point_id: str,
    window_kind: str,
    point_weather: Any,
    reference: Optional[ClimatologyReference],
) -> tuple[Optional[PointPercentileResult], Optional[PointExclusion]]:
    """Percentile one point's 7-day cumulative precipitation, or exclude it.

    Uses the G03A percentile method (mean_rank) and the G03A frozen month
    assignment (natural month of the window END date) — never a second
    incompatible method. Missing values are never interpreted as zero.
    """
    if point_weather is None:
        return None, PointExclusion(
            point_id, window_kind, "weather_result_absent",
            "no normalized weather result supplied for this point",
        )
    if isinstance(point_weather, PointWeatherFailure):
        return None, PointExclusion(
            point_id, window_kind, "weather_collection_failed",
            f"{point_weather.error_type}: {point_weather.message}",
        )
    if not isinstance(point_weather, PointWeather):
        return None, PointExclusion(
            point_id, window_kind, "weather_result_unusable",
            f"unexpected weather object type {type(point_weather).__name__}",
        )
    if point_weather.quality == QUALITY_MISSING:
        return None, PointExclusion(
            point_id, window_kind, "weather_quality_missing",
            "normalized weather quality is MISSING",
        )
    window = (
        point_weather.recent if window_kind == WINDOW_RECENT
        else point_weather.forecast
    )
    cumulative = window.get("cumulative_precipitation_mm")
    if cumulative is None:
        # Never zero-fill: an incomplete window has no honest total.
        return None, PointExclusion(
            point_id, window_kind, "precipitation_window_incomplete",
            "missing days: "
            + ", ".join(str(d) for d in window.get("missing_days", [])),
        )
    if reference is None:
        return None, PointExclusion(
            point_id, window_kind, "climatology_reference_unavailable",
            "no G03A 1991-2020 climatology reference for this point",
        )
    window_end = str(window.get("end", ""))
    try:
        month = date.fromisoformat(window_end).month
    except ValueError:
        return None, PointExclusion(
            point_id, window_kind, "window_end_invalid",
            f"unparseable window end date {window_end!r}",
        )
    if str(month) not in reference.monthly_sorted_totals:
        return None, PointExclusion(
            point_id, window_kind, "climatology_month_distribution_missing",
            f"climatology reference has no distribution for month {month}",
        )

    percentile = percentile_of(reference, month, float(cumulative))
    limitations = []
    if point_weather.quality == QUALITY_STALE:
        limitations.append(
            "weather_quality_stale: included with explicit limitation "
            "(conservative v1.0 behavior; never presented as fresh)"
        )
    if reference.model_fallback_note:
        limitations.append(
            f"climatology_model_fallback: {reference.model_fallback_note}"
        )
    return PointPercentileResult(
        point_id=point_id,
        window_kind=window_kind,
        window_start=str(window.get("start", "")),
        window_end=window_end,
        cumulative_precip_mm=float(cumulative),
        climatology_month=month,
        month_assignment=reference.month_assignment,
        percentile=percentile,
        percentile_method=reference.percentile_method,
        weather_quality=point_weather.quality,
        climatology=_climatology_identity(reference),
        limitations=tuple(limitations),
    ), None


def _aggregate(
    region: RegionConfig,
    weather_points: Mapping[str, Any],
    climatologies: Mapping[str, Optional[ClimatologyReference]],
    window_kind: str,
    index_name: str,
) -> RegionalAggregation:
    """Regional conservative max aggregation over successful points.

    Iteration follows region.json monitoring_points order, so the driver
    tie-break (first point attaining the maximum) is fully deterministic.
    """
    results: list[PointPercentileResult] = []
    exclusions: list[PointExclusion] = []
    refs: Mapping[str, Optional[ClimatologyReference]] = climatologies or {}
    for point in region.monitoring_points:
        result, exclusion = collect_point_percentile(
            point.point_id,
            window_kind,
            weather_points.get(point.point_id),
            refs.get(point.point_id),
        )
        if result is not None:
            results.append(result)
        if exclusion is not None:
            exclusions.append(exclusion)

    value: Optional[float] = None
    driver_point_id: Optional[str] = None
    if results:
        value = max(r.percentile for r in results)
        value = validate_index(value, index_name)
        for r in results:  # config order: stable tie-break
            if r.percentile == value:
                driver_point_id = r.point_id
                break
    return RegionalAggregation(
        kind=window_kind,
        index_name=index_name,
        value=value,
        driver_point_id=driver_point_id,
        point_percentiles=tuple(results),
        exclusions=tuple(exclusions),
    )


def compute_risk_watch(
    region: RegionConfig,
    weather: RegionWeatherResult | Mapping[str, Any],
    climatologies: Mapping[str, Optional[ClimatologyReference]],
    previous: Optional[PreviousState] = None,
    run_id: str = "",
    optional_evidence: Optional[Sequence[Any]] = None,
) -> RiskWatchResult:
    """Run the full deterministic Risk Watch computation.

    Pure function of its inputs: no clock, no network, no LLM, no state.
    Same validated input always produces exactly the same result.
    """
    weather_points = _weather_points(weather)
    climatologies = dict(climatologies or {})
    optional_ids = _optional_evidence_ids(optional_evidence)

    baseline = compute_static_baseline(region)
    limitations: list[str] = []
    if baseline.stored_derived_match is None:
        limitations.append(
            "region config carries no DERIVED static-baseline section; B was "
            "recomputed from static_susceptibility_inputs alone"
        )

    recent = _aggregate(region, weather_points, climatologies, WINDOW_RECENT, "R")
    forecast = _aggregate(region, weather_points, climatologies, WINDOW_FORECAST, "F")

    missing_data: list[dict[str, Any]] = [e.to_dict() for e in recent.exclusions]
    missing_data += [e.to_dict() for e in forecast.exclusions]

    for agg in (recent, forecast):
        for p in agg.point_percentiles:
            for lim in p.limitations:
                note = f"{p.point_id} ({agg.kind}): {lim}"
                if note not in limitations:
                    limitations.append(note)

    if isinstance(weather, RegionWeatherResult) and weather.status != "OK":
        limitations.append(
            f"weather collection status {weather.status}: evidence coverage "
            "reduced; regional R/F use only successful points"
        )
    if recent.exclusions or forecast.exclusions:
        limitations.append(
            "reduced monitoring-point coverage: regional aggregation is based "
            "only on successful eligible points; missing points are recorded "
            "in missing_data and were never fabricated or zero-filled"
        )

    R = recent.value
    F = forecast.value

    provenance = {
        "region_config_version": baseline.region_config_version,
        "scoring_config_version": baseline.scoring_config_version,
        "static_baseline_derivation_algorithm": baseline.derivation_algorithm,
        "climatology_references": {
            p.point_id: {
                "checksum": (climatologies.get(p.point_id).checksum
                             if climatologies.get(p.point_id) else None),
                "algorithm_version": (climatologies.get(p.point_id).algorithm_version
                                      if climatologies.get(p.point_id) else None),
                "source_model": (climatologies.get(p.point_id).source_model
                                 if climatologies.get(p.point_id) else None),
                "baseline": ([climatologies[p.point_id].baseline_start,
                              climatologies[p.point_id].baseline_end]
                             if climatologies.get(p.point_id) else None),
            }
            for p in region.monitoring_points
        },
    }

    previous_c = previous.current_C if previous is not None else None
    if previous is not None and previous.scan_mode == SCAN_MODE_BACKFILL:
        limitations.append(
            "previous comparison snapshot is explicitly labeled BACKFILL"
        )

    if R is None or F is None:
        # Required input insufficient: NO official D / C / O7 (doc 04 §36/§37).
        reasons = []
        if R is None:
            reasons.append("no successful recent-precipitation point")
        if F is None:
            reasons.append("no successful forecast-precipitation point")
        limitations.append(
            "official Current Risk Index and 7-Day Outlook Index are "
            "UNAVAILABLE: " + "; ".join(reasons) + ". No value was "
            "substituted, zero-filled, carried over from a previous scan or "
            "estimated by any model. Static baseline B remains independently "
            "reportable."
        )
        what_changed = build_what_changed(
            None, {}, {}, _missing_pids(missing_data), optional_ids, previous
        )
        return RiskWatchResult(
            algorithm_version=ALGORITHM_VERSION,
            formula_version=FORMULA_VERSION,
            region_id=region.region_id,
            run_id=run_id,
            status=STATUS_FAILED,
            static_baseline=baseline,
            recent_aggregation=recent,
            forecast_aggregation=forecast,
            R=None, F=None, D=None, C=None, O7=None,
            current_risk_level=None,
            outlook_7d_level=None,
            risk_direction=None,
            previous_C=None,
            delta_C=None,
            top_drivers=(),
            outlook_drivers=(),
            what_changed=what_changed,
            missing_data=tuple(missing_data),
            limitations=tuple(limitations),
            optional_evidence_availability=optional_ids,
            provenance=provenance,
            numeric_method=dict(NUMERIC_METHOD),
        )

    D = compute_D(R, F)
    C = compute_C(baseline.value, D)
    O7 = compute_O7(baseline.value, F)
    current_level = classify_band(C, "C")
    outlook_level = classify_band(O7, "O7")

    if previous_c is not None:
        delta_c: Optional[float] = C - previous_c
        direction: Optional[str] = classify_direction(delta_c)
    else:
        delta_c = None
        direction = DIRECTION_NO_HISTORY

    top_drivers = build_current_risk_drivers(baseline, R, F, recent, forecast)
    outlook = build_outlook_drivers(baseline, F, forecast)

    recent_by_point = {p.point_id: p.cumulative_precip_mm for p in recent.point_percentiles}
    forecast_by_point = {p.point_id: p.cumulative_precip_mm for p in forecast.point_percentiles}
    what_changed = build_what_changed(
        C, recent_by_point, forecast_by_point,
        _missing_pids(missing_data), optional_ids, previous,
    )

    status = (
        STATUS_COMPLETED_WITH_LIMITATIONS
        if (recent.exclusions or forecast.exclusions or limitations)
        else STATUS_COMPLETED
    )
    return RiskWatchResult(
        algorithm_version=ALGORITHM_VERSION,
        formula_version=FORMULA_VERSION,
        region_id=region.region_id,
        run_id=run_id,
        status=status,
        static_baseline=baseline,
        recent_aggregation=recent,
        forecast_aggregation=forecast,
        R=R, F=F, D=D, C=C, O7=O7,
        current_risk_level=current_level,
        outlook_7d_level=outlook_level,
        risk_direction=direction,
        previous_C=previous_c,
        delta_C=delta_c,
        top_drivers=top_drivers,
        outlook_drivers=outlook,
        what_changed=what_changed,
        missing_data=tuple(missing_data),
        limitations=tuple(limitations),
        optional_evidence_availability=optional_ids,
        provenance=provenance,
        numeric_method=dict(NUMERIC_METHOD),
    )


def _missing_pids(missing_data: Sequence[dict[str, Any]]) -> list[str]:
    return sorted({str(m["point_id"]) for m in missing_data if m.get("point_id")})
