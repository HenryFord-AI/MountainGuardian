"""Shared deterministic fixtures/helpers for G03A Risk Watch data tests."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
CASE_JSON = REPO_ROOT / "data" / "cases" / "jilong_20260826" / "case.json"


def make_daily_payload(
    today: date,
    precip: float = 2.5,
    tmax: float = 10.0,
    tmin: float = -2.0,
    missing_recent_days: list[str] | None = None,
    missing_forecast_days: list[str] | None = None,
    returned_lat: float = 28.25,
    returned_lon: float = 85.5,
    elevation: float = 4321.0,
) -> dict[str, Any]:
    """A well-formed Open-Meteo forecast response covering today-7..today+6."""
    missing_recent = set(missing_recent_days or [])
    missing_forecast = set(missing_forecast_days or [])
    start = today - timedelta(days=7)
    times: list[str] = []
    p: list[Optional[float]] = []
    hi: list[Optional[float]] = []
    lo: list[Optional[float]] = []
    for i in range(15):
        day = start + timedelta(days=i)
        iso = day.isoformat()
        times.append(iso)
        if iso in missing_recent or iso in missing_forecast:
            p.append(None)
            hi.append(None)
            lo.append(None)
        else:
            p.append(precip)
            hi.append(tmax)
            lo.append(tmin)
    return {
        "latitude": returned_lat,
        "longitude": returned_lon,
        "generationtime_ms": 1.25,
        "utc_offset_seconds": 0,
        "timezone": "UTC",
        "timezone_abbreviation": "UTC",
        "elevation": elevation,
        "daily_units": {
            "time": "iso8601",
            "precipitation_sum": "mm",
            "temperature_2m_max": "°C",
            "temperature_2m_min": "°C",
        },
        "daily": {
            "time": times,
            "precipitation_sum": p,
            "temperature_2m_max": hi,
            "temperature_2m_min": lo,
        },
    }


def make_historical_payload(
    start: str, end: str, precip: float | None = 1.0
) -> dict[str, Any]:
    """Well-formed Open-Meteo archive response for [start, end] inclusive."""
    s = date.fromisoformat(start)
    e = date.fromisoformat(end)
    times: list[str] = []
    p: list[Optional[float]] = []
    day = s
    while day <= e:
        times.append(day.isoformat())
        p.append(precip)
        day += timedelta(days=1)
    return {
        "latitude": 28.25,
        "longitude": 85.5,
        "generationtime_ms": 2.5,
        "utc_offset_seconds": 0,
        "timezone": "UTC",
        "timezone_abbreviation": "UTC",
        "elevation": 4321.0,
        "daily_units": {"time": "iso8601", "precipitation_sum": "mm"},
        "daily": {
            "time": times,
            "precipitation_sum": p,
            "temperature_2m_max": [5.0] * len(times),
            "temperature_2m_min": [-5.0] * len(times),
        },
    }


def post_event_case_keys() -> set[str]:
    """Keys of all Historical Replay post-event validation fields."""
    data = json.loads(CASE_JSON.read_text(encoding="utf-8"))
    keys = {
        f["key"]
        for f in data["data_fields"]
        if f.get("phase") == "post_event_validation"
    }
    keys |= {
        "satellite_post_datetime",
        "satellite_post_cloud_pct",
        "satellite_visible_change",
    }
    return keys


def walk_keys(obj: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            keys.add(str(k))
            keys |= walk_keys(v)
    elif isinstance(obj, list):
        for item in obj:
            keys |= walk_keys(item)
    return keys
