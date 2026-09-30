"""
MountainGuardian G03A – Open-Meteo operational weather collector.

Frozen P0 source (doc 04 §7 / §48): Open-Meteo ECMWF Forecast API
(https://api.open-meteo.com/v1/forecast with models=ecmwf_ifs).

Per monitoring point the collector retrieves, for a UTC retrieval instant:
  * previous 7 complete days (today-7 .. today-1): daily precipitation,
    cumulative precipitation, maximum daily precipitation, temperature range;
  * next 7 days (today .. today+6): daily forecast precipitation, cumulative
    forecast precipitation, temperature range.

Every normalized result keeps full provenance (requested vs returned
coordinate, elevation, observation/forecast windows, retrieval time,
provider/model metadata, units, quality, missing fields). Missing values are
never zero-filled and never inferred: missing means missing.

Failure model: explicit timeout, bounded retry for transient network/HTTP
failures, no retry for configuration errors (4xx) or malformed payloads,
partial-point and all-point failure are representable results, not crashes.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Optional

import requests

from riskwatch.cache import WeatherRawCache
from riskwatch.region import MonitoringPoint

FORECAST_ENDPOINT = "https://api.open-meteo.com/v1/forecast"
FORECAST_MODEL = "ecmwf_ifs"  # frozen: Open-Meteo ECMWF Forecast API
DAILY_VARIABLES = "precipitation_sum,temperature_2m_max,temperature_2m_min"

RECENT_WINDOW_DAYS = 7
FORECAST_WINDOW_DAYS = 7

DEFAULT_TIMEOUT_S = 15.0
MAX_ATTEMPTS = 3            # 1 initial + 2 retries: bounded by construction
RETRY_BACKOFF_S = 0.5
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})

# Freshness threshold (doc 04 §34: thresholds defined centrally in config):
# daily model/reanalysis products lag reality; an observation window whose
# newest day is older than this many days behind the retrieval date is STALE.
FRESH_MAX_OBSERVATION_AGE_DAYS = 3

QUALITY_FRESH = "FRESH"
QUALITY_STALE = "STALE"
QUALITY_MISSING = "MISSING"

STATUS_OK = "OK"
STATUS_PARTIAL = "PARTIAL"
STATUS_FAILED = "FAILED"

UNITS = {
    "precipitation": "mm",
    "temperature": "degC",
}


class WeatherCollectionError(Exception):
    """Base class for weather collection failures."""


class WeatherConfigError(WeatherCollectionError):
    """Non-retryable request/configuration error (HTTP 4xx)."""


class WeatherTimeoutError(WeatherCollectionError):
    """Request exceeded the explicit timeout."""


class WeatherTransientError(WeatherCollectionError):
    """Retryable network failure or retryable HTTP status (429/5xx)."""


class WeatherMalformedResponseError(WeatherCollectionError):
    """Provider response is not usable (bad JSON or missing required field)."""


HttpGet = Callable[[str, dict, float], dict]


def default_http_get(url: str, params: dict, timeout: float) -> dict:
    """requests-based transport with explicit timeout and error mapping."""
    try:
        resp = requests.get(url, params=params, timeout=timeout)
    except requests.Timeout as exc:
        raise WeatherTimeoutError(f"timeout after {timeout}s: {url}") from exc
    except requests.ConnectionError as exc:
        raise WeatherTransientError(f"network failure: {exc}") from exc
    if resp.status_code in RETRYABLE_STATUS:
        raise WeatherTransientError(f"HTTP {resp.status_code} from {url}")
    if 400 <= resp.status_code < 500:
        raise WeatherConfigError(f"HTTP {resp.status_code} from {url}")
    if resp.status_code >= 500:
        raise WeatherTransientError(f"HTTP {resp.status_code} from {url}")
    try:
        payload = resp.json()
    except ValueError as exc:
        raise WeatherMalformedResponseError(f"non-JSON response from {url}") from exc
    if not isinstance(payload, dict):
        raise WeatherMalformedResponseError(f"unexpected JSON type from {url}")
    return payload


@dataclass
class PointWeather:
    """Normalized weather evidence for one monitoring point."""

    point_id: str
    quality: str
    recent: dict[str, Any]
    forecast: dict[str, Any]
    provenance: dict[str, Any]
    missing: dict[str, Any] = field(default_factory=dict)
    units: dict[str, str] = field(default_factory=lambda: dict(UNITS))

    def to_dict(self) -> dict[str, Any]:
        return {
            "point_id": self.point_id,
            "status": STATUS_OK,
            "quality": self.quality,
            "units": dict(self.units),
            "recent": dict(self.recent),
            "forecast": dict(self.forecast),
            "missing": dict(self.missing),
            "provenance": dict(self.provenance),
        }


@dataclass
class PointWeatherFailure:
    """Explicit, non-fabricated failure record for one monitoring point."""

    point_id: str
    error_type: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "point_id": self.point_id,
            "status": STATUS_FAILED,
            "quality": QUALITY_MISSING,
            "error_type": self.error_type,
            "message": self.message,
            "missing": {"reason": self.message, "error_type": self.error_type},
        }


@dataclass
class RegionWeatherResult:
    region_id: str
    retrieval_time: str
    status: str
    points: dict[str, Any]
    coverage: dict[str, Any]

    @property
    def ok_points(self) -> list[str]:
        return [
            pid
            for pid, p in self.points.items()
            if isinstance(p, PointWeather)
        ]

    @property
    def failed_points(self) -> list[str]:
        return [
            pid
            for pid, p in self.points.items()
            if isinstance(p, PointWeatherFailure)
        ]

    def to_dict(self) -> dict[str, Any]:
        return {
            "region_id": self.region_id,
            "retrieval_time": self.retrieval_time,
            "status": self.status,
            "coverage": dict(self.coverage),
            "monitoring_points": {
                pid: p.to_dict() for pid, p in self.points.items()
            },
        }


def build_request_params(point: MonitoringPoint) -> dict[str, Any]:
    return {
        "latitude": point.latitude,
        "longitude": point.longitude,
        "daily": DAILY_VARIABLES,
        "past_days": RECENT_WINDOW_DAYS,
        "forecast_days": FORECAST_WINDOW_DAYS,
        "timezone": "UTC",
        "models": FORECAST_MODEL,
    }


def _window_series(
    daily: dict[str, Any],
    start: date,
    end: date,
) -> tuple[list[str], list[Optional[float]], list[Optional[float]], list[Optional[float]]]:
    times = daily["time"]
    precip = daily["precipitation_sum"]
    tmax = daily["temperature_2m_max"]
    tmin = daily["temperature_2m_min"]
    index = {t: i for i, t in enumerate(times)}
    dates: list[str] = []
    p: list[Optional[float]] = []
    hi: list[Optional[float]] = []
    lo: list[Optional[float]] = []
    day = start
    while day <= end:
        iso = day.isoformat()
        dates.append(iso)
        i = index.get(iso)
        if i is None:
            p.append(None)
            hi.append(None)
            lo.append(None)
        else:
            p.append(precip[i])
            hi.append(tmax[i])
            lo.append(tmin[i])
        day += timedelta(days=1)
    return dates, p, hi, lo


def _aggregate(
    dates: list[str],
    precip: list[Optional[float]],
    tmax: list[Optional[float]],
    tmin: list[Optional[float]],
) -> tuple[dict[str, Any], list[str]]:
    missing_days = [d for d, v in zip(dates, precip) if v is None]
    present = [v for v in precip if v is not None]
    present_hi = [v for v in tmax if v is not None]
    present_lo = [v for v in tmin if v is not None]
    window = {
        "start": dates[0],
        "end": dates[-1],
        "daily_precipitation_mm": list(precip),
        "daily_temperature_max_c": list(tmax),
        "daily_temperature_min_c": list(tmin),
        # Never zero-fill: a window with any missing day has no honest total.
        "cumulative_precipitation_mm": (
            round(sum(present), 3) if not missing_days else None
        ),
        "max_daily_precipitation_mm": (
            round(max(present), 3) if present else None
        ),
        "temperature_range_c": (
            {
                "min": round(min(present_lo), 2),
                "max": round(max(present_hi), 2),
            }
            if present_lo and present_hi
            else None
        ),
        "missing_days": list(missing_days),
        "available_days": len(present),
        "expected_days": len(dates),
    }
    return window, missing_days


def _quality(
    today: date,
    recent: dict[str, Any],
    forecast: dict[str, Any],
) -> str:
    recent_ok = recent["available_days"] == recent["expected_days"]
    forecast_ok = forecast["available_days"] == forecast["expected_days"]
    if recent["available_days"] == 0 and forecast["available_days"] == 0:
        return QUALITY_MISSING
    newest = None
    for iso, v in zip(_dates(recent), recent["daily_precipitation_mm"]):
        if v is not None:
            newest = iso
    if newest is None:
        return QUALITY_STALE
    age = (today - date.fromisoformat(newest)).days
    if recent_ok and forecast_ok and age <= FRESH_MAX_OBSERVATION_AGE_DAYS:
        return QUALITY_FRESH
    return QUALITY_STALE


def _dates(window: dict[str, Any]) -> list[str]:
    start = date.fromisoformat(window["start"])
    end = date.fromisoformat(window["end"])
    out = []
    day = start
    while day <= end:
        out.append(day.isoformat())
        day += timedelta(days=1)
    return out


def normalize_weather(
    payload: dict[str, Any],
    point: MonitoringPoint,
    retrieval_time: str,
    request_time: str,
    cached: bool = False,
    cache_age_seconds: float | None = None,
    original_retrieval_time: str | None = None,
) -> PointWeather:
    """Validate and normalize one raw Open-Meteo forecast response."""
    daily = payload.get("daily")
    if not isinstance(daily, dict):
        raise WeatherMalformedResponseError(
            f"point {point.point_id}: response has no 'daily' object"
        )
    for field_name in (
        "time",
        "precipitation_sum",
        "temperature_2m_max",
        "temperature_2m_min",
    ):
        if not isinstance(daily.get(field_name), list):
            raise WeatherMalformedResponseError(
                f"point {point.point_id}: missing required daily field '{field_name}'"
            )
    lengths = {
        len(daily["time"]),
        len(daily["precipitation_sum"]),
        len(daily["temperature_2m_max"]),
        len(daily["temperature_2m_min"]),
    }
    if len(lengths) != 1:
        raise WeatherMalformedResponseError(
            f"point {point.point_id}: inconsistent daily array lengths"
        )
    if not daily["time"]:
        raise WeatherMalformedResponseError(
            f"point {point.point_id}: empty daily arrays"
        )

    today = date.fromisoformat(retrieval_time[:10])
    recent_start = today - timedelta(days=RECENT_WINDOW_DAYS)
    recent_end = today - timedelta(days=1)
    forecast_start = today
    forecast_end = today + timedelta(days=FORECAST_WINDOW_DAYS - 1)

    r_dates, r_p, r_hi, r_lo = _window_series(daily, recent_start, recent_end)
    f_dates, f_p, f_hi, f_lo = _window_series(daily, forecast_start, forecast_end)
    recent, recent_missing = _aggregate(r_dates, r_p, r_hi, r_lo)
    forecast, forecast_missing = _aggregate(f_dates, f_p, f_hi, f_lo)
    quality = _quality(today, recent, forecast)

    daily_units = payload.get("daily_units", {}) or {}
    provenance = {
        "provider": "Open-Meteo",
        "endpoint": FORECAST_ENDPOINT,
        "model_requested": FORECAST_MODEL,
        "model_reported": payload.get("model", payload.get("current_weather_units", None)),
        "requested_coordinate": {
            "latitude": point.latitude,
            "longitude": point.longitude,
        },
        "returned_coordinate": {
            "latitude": payload.get("latitude"),
            "longitude": payload.get("longitude"),
        },
        "elevation_m": payload.get("elevation"),
        "utc_offset_seconds": payload.get("utc_offset_seconds"),
        "timezone": payload.get("timezone"),
        "timezone_abbreviation": payload.get("timezone_abbreviation"),
        "generationtime_ms": payload.get("generationtime_ms"),
        "observation_window": {"start": recent["start"], "end": recent["end"]},
        "forecast_window": {"start": forecast["start"], "end": forecast["end"]},
        "request_time": request_time,
        "retrieval_time": retrieval_time,
        "from_cache": cached,
        "cache_age_seconds": cache_age_seconds,
        "original_retrieval_time": original_retrieval_time or retrieval_time,
        "units": dict(daily_units),
    }
    missing = {
        "recent_missing_days": recent_missing,
        "forecast_missing_days": forecast_missing,
        "missing_fields": [],
    }
    return PointWeather(
        point_id=point.point_id,
        quality=quality,
        recent=recent,
        forecast=forecast,
        provenance=provenance,
        missing=missing,
    )


class WeatherCollector:
    """Collects operational weather for all monitoring points of a region."""

    def __init__(
        self,
        http_get: HttpGet | None = None,
        cache: WeatherRawCache | None = None,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        max_attempts: int = MAX_ATTEMPTS,
        retry_backoff_s: float = RETRY_BACKOFF_S,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], datetime] | None = None,
    ):
        self.http_get = http_get or default_http_get
        self.cache = cache
        self.timeout_s = float(timeout_s)
        self.max_attempts = int(max_attempts)
        self.retry_backoff_s = float(retry_backoff_s)
        self._sleep = sleep
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    # -- raw retrieval with timeout + bounded retry -------------------------
    def fetch_raw(self, point: MonitoringPoint) -> tuple[dict, str, bool, float | None]:
        """Return (payload, retrieval_time_iso, cached, cache_age_seconds)."""
        params = build_request_params(point)
        if self.cache is not None:
            hit = self.cache.get(FORECAST_ENDPOINT, params)
            if hit is not None:
                return hit.payload, hit.original_retrieval_time, True, hit.cache_age_seconds

        request_time = self._clock().isoformat()
        last_error: Exception | None = None
        payload: dict | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                payload = self.http_get(FORECAST_ENDPOINT, params, self.timeout_s)
                last_error = None
                break
            except (WeatherTransientError, WeatherTimeoutError) as exc:
                last_error = exc
                if attempt >= self.max_attempts:
                    break
                self._sleep(self.retry_backoff_s * attempt)
        if last_error is not None or payload is None:
            raise last_error or WeatherCollectionError("no payload retrieved")

        now = self._clock()
        retrieval_time = now.isoformat()
        if self.cache is not None:
            self.cache.put(
                FORECAST_ENDPOINT, params, payload, retrieval_time, now.timestamp()
            )
        return payload, retrieval_time, False, None

    # -- per point ----------------------------------------------------------
    def collect_point(self, point: MonitoringPoint):
        try:
            payload, retrieval_time, cached, age = self.fetch_raw(point)
        except WeatherCollectionError as exc:
            return PointWeatherFailure(
                point_id=point.point_id,
                error_type=type(exc).__name__,
                message=str(exc),
            )
        except Exception as exc:  # unexpected provider shape etc.
            return PointWeatherFailure(
                point_id=point.point_id,
                error_type=type(exc).__name__,
                message=str(exc),
            )
        request_time = self._clock().isoformat()
        try:
            return normalize_weather(
                payload,
                point,
                retrieval_time=retrieval_time,
                request_time=request_time,
                cached=cached,
                cache_age_seconds=age,
                original_retrieval_time=retrieval_time if cached else None,
            )
        except WeatherCollectionError as exc:
            return PointWeatherFailure(
                point_id=point.point_id,
                error_type=type(exc).__name__,
                message=str(exc),
            )

    # -- region level -------------------------------------------------------
    def collect_region(self, region) -> RegionWeatherResult:
        retrieval_time = self._clock().isoformat()
        points: dict[str, Any] = {}
        for point in region.monitoring_points:
            points[point.point_id] = self.collect_point(point)
        ok = [pid for pid, p in points.items() if isinstance(p, PointWeather)]
        failed = [pid for pid, p in points.items() if isinstance(p, PointWeatherFailure)]
        if ok and failed:
            status = STATUS_PARTIAL
        elif ok:
            status = STATUS_OK
        else:
            status = STATUS_FAILED
        coverage = {
            "required_points_total": len(points),
            "required_points_ok": len(ok),
            "required_points_failed": len(failed),
            "failed_points": [
                {
                    "point_id": pid,
                    "reason": points[pid].message,
                    "error_type": points[pid].error_type,
                }
                for pid in failed
            ],
            "evidence_coverage_reduced": bool(failed),
        }
        return RegionWeatherResult(
            region_id=region.region_id,
            retrieval_time=retrieval_time,
            status=status,
            points=points,
            coverage=coverage,
        )
