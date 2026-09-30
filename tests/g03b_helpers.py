"""Shared deterministic fixtures/helpers for G03B Risk Watch engine tests.

Everything here is offline and clock-free: synthetic region configs,
synthetic 1991-2020 climatology references with known distributions and
normalized PointWeather objects built through the real G03A
normalize_weather contract.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from riskwatch.climatology import (  # noqa: E402
    ALGORITHM_VERSION as CLIMATOLOGY_ALGORITHM_VERSION,
)
from riskwatch.climatology import ClimatologyReference  # noqa: E402
from riskwatch.region import RegionConfig, load_region  # noqa: E402
from riskwatch.weather import PointWeather, normalize_weather  # noqa: E402

FIXED_RETRIEVAL_TIME = "2026-08-15T06:00:00+00:00"

# The five authorized static factors (same scores/weights as the tracked
# production region.json): B = 92.222...
DEFAULT_FACTORS = [
    {"factor_id": "R1", "key": "glacierized_source_zone",
     "name": "High-altitude cryosphere source zone",
     "score_0_to_5": 4, "original_weight_pct": 20,
     "normalized_weight_pct": 22.22, "source_ids": ["S03", "S04"]},
    {"factor_id": "R2", "key": "terrain_relief_channel",
     "name": "Huge vertical drop and narrow gorge",
     "score_0_to_5": 5, "original_weight_pct": 25,
     "normalized_weight_pct": 27.78, "source_ids": ["S03", "S04", "S05"]},
    {"factor_id": "R3", "key": "loose_material_supply",
     "name": "Loose channel material supply",
     "score_0_to_5": 5, "original_weight_pct": 20,
     "normalized_weight_pct": 22.22, "source_ids": ["S03", "S04"]},
    {"factor_id": "R4", "key": "historical_recurrence",
     "name": "Historical chained-hazard recurrence",
     "score_0_to_5": 4, "original_weight_pct": 15,
     "normalized_weight_pct": 16.67, "source_ids": ["S04"]},
    {"factor_id": "R6", "key": "downstream_exposure",
     "name": "Downstream exposure and port facilities",
     "score_0_to_5": 5, "original_weight_pct": 10,
     "normalized_weight_pct": 11.11, "source_ids": ["S01", "S05"]},
]

EXACT_FACTORS = [
    # B == 80.0 exactly: five factors, equal weights, score 4/5 each.
    {"factor_id": f"E{i}", "key": f"exact_factor_{i}", "name": f"Exact factor {i}",
     "score_0_to_5": 4, "original_weight_pct": 16,
     "normalized_weight_pct": 20.0, "source_ids": ["S01"]}
    for i in range(1, 6)
]

EXCLUDED_R5 = [
    {"factor_id": "R5", "name": "Monsoon and high-precipitation background",
     "reason": "Excluded to avoid double counting with dynamic precipitation."}
]


def make_region_data(
    factors: list[dict] | None = None,
    derived: dict | None = None,
    config_version: str = "test-g03b-1",
    region_id: str = "test_region",
    excluded: list[dict] | None = None,
    original_weight_ratio: str | None = "20 : 25 : 20 : 15 : 10",
) -> dict[str, Any]:
    factors = DEFAULT_FACTORS if factors is None else factors
    inputs: dict[str, Any] = {
        "description": "test static inputs",
        "excluded_factors": EXCLUDED_R5 if excluded is None else excluded,
        "factors": factors,
        "scoring_config_version": "risk-watch-static-v1.0-5factors",
    }
    if original_weight_ratio is not None:
        inputs["original_weight_ratio"] = original_weight_ratio
    data: dict[str, Any] = {
        "schema_version": "1.0",
        "config_version": config_version,
        "region_id": region_id,
        "region_name": "Test region",
        "monitoring_points": [
            {
                "point_id": "source_zone",
                "name": "Source Zone",
                "latitude": 28.28,
                "longitude": 85.481,
                "elevation_m": 5200,
                "coordinate_provenance": {
                    "type": "representative_derived", "exact": False,
                    "reference": "test", "method": "test",
                    "meaning": "test anchor",
                },
            },
            {
                "point_id": "port_zone",
                "name": "Port Zone",
                "latitude": 28.279,
                "longitude": 85.379,
                "elevation_m": 1800,
                "coordinate_provenance": {
                    "type": "representative", "exact": False,
                    "reference": "test", "meaning": "test anchor",
                },
            },
        ],
        "static_terrain_baseline": {"terrain_class": "test"},
        "cryosphere_baseline": {"glacierized_source_zone": True},
        "historical_hazard_baseline": {"prior_event_date": "2025-07-08"},
        "static_susceptibility_inputs": inputs,
        "weather_data_policy": {
            "climatology_baseline": {"start": "1991-01-01", "end": "2020-12-31"}
        },
        "source_references": [{"id": "S01", "name": "t", "authority": "t",
                               "url": "https://example.test", "use": "t"}],
        "provenance": {"prepared_by": "test"},
        "scientific_limitations": ["test limitation"],
    }
    if derived is not None:
        data["derived_static_baseline"] = derived
    return data


def write_region(tmp_path: Path, data: dict[str, Any] | None = None,
                 region_id: str = "test_region", **kwargs) -> RegionConfig:
    """Write region.json under tmp_path and load it through the real loader."""
    data = data if data is not None else make_region_data(region_id=region_id, **kwargs)
    region_dir = tmp_path / region_id
    region_dir.mkdir(parents=True, exist_ok=True)
    (region_dir / "region.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return load_region(region_id, regions_dir=tmp_path)


def direct_region(data: dict[str, Any] | None = None, **kwargs) -> RegionConfig:
    """RegionConfig without loader validation (for tamper/malformed tests)."""
    data = data if data is not None else make_region_data(**kwargs)
    return RegionConfig(region_id=data["region_id"], data=data,
                        path=Path("synthetic/region.json"))


def uniform_totals(n: int = 100) -> list[float]:
    """Distribution 0.0 .. n-1.0: percentile_of(x in [k, k+1)) == k + 0.5."""
    return [float(i) for i in range(n)]


def make_reference(
    point_id: str,
    monthly_totals: dict[int, list[float]],
    checksum: str | None = None,
    source_model: str = "era5",
    model_fallback_note: str | None = None,
) -> ClimatologyReference:
    monthly = {str(m): sorted(float(v) for v in vals)
               for m, vals in monthly_totals.items()}
    return ClimatologyReference(
        point_id=point_id,
        baseline_start="1991-01-01",
        baseline_end="2020-12-31",
        source_model=source_model,
        algorithm_version=CLIMATOLOGY_ALGORITHM_VERSION,
        requested_coordinate={"latitude": 28.28, "longitude": 85.481},
        returned_coordinate={"latitude": 28.25, "longitude": 85.5},
        elevation_m=5200.0,
        generated_at=FIXED_RETRIEVAL_TIME,
        retrieval_time=FIXED_RETRIEVAL_TIME,
        units="mm",
        valid_days=10957,
        missing_days=0,
        skipped_windows=0,
        window_counts={m: len(v) for m, v in monthly.items()},
        monthly_sorted_totals=monthly,
        monthly_quantiles={},
        checksum=checksum or hashlib.sha256(point_id.encode("utf-8")).hexdigest(),
        model_fallback_note=model_fallback_note,
    )


def make_point_weather(
    point_id: str,
    center: date,
    recent_daily: list[Optional[float]],
    forecast_daily: list[Optional[float]],
    tmax: float = 8.0,
    tmin: float = -3.0,
    retrieval_time: str | None = None,
) -> PointWeather:
    """Normalized PointWeather through the real G03A contract.

    recent_daily covers center-7 .. center-1 (7 values);
    forecast_daily covers center .. center+6 (7 values).
    None means a missing day (never zero-filled by G03A).
    """
    assert len(recent_daily) == 7 and len(forecast_daily) == 7
    retrieval_time = retrieval_time or f"{center.isoformat()}T06:00:00+00:00"
    times, precip = [], []
    day = center - timedelta(days=7)
    for i in range(14):
        times.append(day.isoformat())
        precip.append(recent_daily[i] if i < 7 else forecast_daily[i - 7])
        day += timedelta(days=1)
    payload = {
        "latitude": 28.25,
        "longitude": 85.5,
        "generationtime_ms": 0.0,
        "utc_offset_seconds": 0,
        "timezone": "UTC",
        "timezone_abbreviation": "UTC",
        "elevation": 4321.0,
        "daily_units": {
            "time": "iso8601",
            "precipitation_sum": "mm",
            "temperature_2m_max": "degC",
            "temperature_2m_min": "degC",
        },
        "daily": {
            "time": times,
            "precipitation_sum": precip,
            "temperature_2m_max": [tmax] * 14,
            "temperature_2m_min": [tmin] * 14,
        },
    }
    from riskwatch.region import MonitoringPoint

    point = MonitoringPoint(
        point_id=point_id, name=point_id, latitude=28.28, longitude=85.4,
        elevation_m=5000.0, coordinate_provenance={}, raw={},
    )
    return normalize_weather(
        payload, point, retrieval_time=retrieval_time, request_time=retrieval_time
    )


def flat_weather(
    center: date,
    source_recent_mm: float = 70.0,
    source_forecast_mm: float = 30.0,
    port_recent_mm: float = 50.0,
    port_forecast_mm: float = 90.0,
) -> dict[str, Any]:
    """Two-point weather map with exact cumulative totals (single wet day)."""
    def daily(total: float) -> list[Optional[float]]:
        return [total] + [0.0] * 6

    return {
        "source_zone": make_point_weather(
            "source_zone", center, daily(source_recent_mm), daily(source_forecast_mm)
        ),
        "port_zone": make_point_weather(
            "port_zone", center, daily(port_recent_mm), daily(port_forecast_mm)
        ),
    }


def flat_climatologies(months: tuple[int, ...] = (8,)) -> dict[str, ClimatologyReference]:
    refs = {}
    for pid in ("source_zone", "port_zone"):
        refs[pid] = make_reference(
            pid, {m: uniform_totals(100) for m in months}
        )
    return refs
