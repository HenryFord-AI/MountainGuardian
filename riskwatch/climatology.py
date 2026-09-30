"""
MountainGuardian G03A – 1991-2020 precipitation climatology reference.

Frozen design (doc 04 §8 / §10):
  * historical source: Open-Meteo Historical Weather (Archive) API with a
    consistent long-term reanalysis - frozen preference ERA5-Land. Verified
    2026-10-01: the current official API provides no precipitation variable
    for ERA5-Land, so precipitation uses the consistent ERA5 reanalysis on the
    same endpoint (validated fallback, recorded in reference provenance).
    Mixed "best match" series are never used;
  * baseline period frozen: 1991-01-01 .. 2020-12-31;
  * per monitoring point: continuous rolling 7-day precipitation totals,
    grouped by the natural month of the window END date, persisted as a
    reproducible monthly reference for later percentile lookup (G03B).

Reproducibility rules:
  * identical historical input -> identical reference (checksum recorded);
  * missing/invalid historical days are NEVER interpolated: any 7-day window
    containing a missing day is excluded and counted;
  * representation keeps the FULL sorted monthly distributions (not only
    P50/P75/P90/P95/P99), so exact percentile lookup stays reproducible.

The derived reference is cached under the runtime directory; the expensive
30-year download happens once per point/model/version.
"""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable, Optional

from riskwatch.region import MonitoringPoint, load_region
from riskwatch.weather import (
    DEFAULT_TIMEOUT_S,
    MAX_ATTEMPTS,
    RETRY_BACKOFF_S,
    WeatherMalformedResponseError,
    WeatherTimeoutError,
    WeatherTransientError,
    default_http_get,
)

HISTORICAL_ENDPOINT = "https://archive-api.open-meteo.com/v1/archive"
# Frozen preference (doc 04 §8 / §48): ERA5-Land, the consistent ~0.1 deg
# long-term dataset. Verified 2026-10-01 against the current official docs and
# live API: ERA5-Land provides NO precipitation variable (nulls only), so the
# precipitation climatology falls back to the consistent ERA5 reanalysis on the
# SAME endpoint/provider/period. The fallback is validated at retrieval time,
# recorded in every reference's provenance and reported as an external API
# contract change. Mixed "best match" series remain prohibited.
HISTORICAL_MODEL_PREFERRED = "era5_land"
HISTORICAL_MODEL_PRECIP_FALLBACK = "era5"

CLIMATOLOGY_BASELINE_START = "1991-01-01"
CLIMATOLOGY_BASELINE_END = "2020-12-31"

WINDOW_DAYS = 7
REFERENCE_MONTH_ASSIGNMENT = "window_end_month"
PERCENTILE_METHOD = "mean_rank"  # 100 * (below + 0.5 * equal) / n
ALGORITHM_VERSION = "g03a-rolling7-monthly-v1"

REFERENCE_QUANTILES = (50.0, 75.0, 90.0, 95.0, 99.0)

HttpGet = Callable[[str, dict, float], dict]


class ClimatologyError(Exception):
    """Climatology build/load failure."""


@dataclass(frozen=True)
class HistoricalResponse:
    payload: dict[str, Any]
    model_used: str
    fallback_note: str | None = None


@dataclass(frozen=True)
class ClimatologyReference:
    """Reproducible monthly 7-day precipitation reference for one point."""

    point_id: str
    baseline_start: str
    baseline_end: str
    source_model: str
    algorithm_version: str
    requested_coordinate: dict[str, float]
    returned_coordinate: dict[str, Optional[float]]
    elevation_m: Optional[float]
    generated_at: str
    retrieval_time: str
    units: str
    valid_days: int
    missing_days: int
    skipped_windows: int
    window_counts: dict[str, int]
    monthly_sorted_totals: dict[str, list[float]]
    monthly_quantiles: dict[str, dict[str, float]]
    checksum: str
    month_assignment: str = REFERENCE_MONTH_ASSIGNMENT
    percentile_method: str = PERCENTILE_METHOD
    preferred_model: str = HISTORICAL_MODEL_PREFERRED
    model_fallback_note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "point_id": self.point_id,
            "baseline_start": self.baseline_start,
            "baseline_end": self.baseline_end,
            "source_model": self.source_model,
            "algorithm_version": self.algorithm_version,
            "month_assignment": self.month_assignment,
            "percentile_method": self.percentile_method,
            "requested_coordinate": dict(self.requested_coordinate),
            "returned_coordinate": dict(self.returned_coordinate),
            "elevation_m": self.elevation_m,
            "generated_at": self.generated_at,
            "retrieval_time": self.retrieval_time,
            "units": self.units,
            "valid_days": self.valid_days,
            "missing_days": self.missing_days,
            "skipped_windows": self.skipped_windows,
            "window_counts": dict(self.window_counts),
            "monthly_sorted_totals": {
                m: list(v) for m, v in self.monthly_sorted_totals.items()
            },
            "monthly_quantiles": {
                m: dict(v) for m, v in self.monthly_quantiles.items()
            },
            "checksum": self.checksum,
            "preferred_model": self.preferred_model,
            "model_fallback_note": self.model_fallback_note,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "ClimatologyReference":
        return ClimatologyReference(
            point_id=data["point_id"],
            baseline_start=data["baseline_start"],
            baseline_end=data["baseline_end"],
            source_model=data["source_model"],
            algorithm_version=data["algorithm_version"],
            requested_coordinate=dict(data["requested_coordinate"]),
            returned_coordinate=dict(data["returned_coordinate"]),
            elevation_m=data.get("elevation_m"),
            generated_at=data["generated_at"],
            retrieval_time=data["retrieval_time"],
            units=data["units"],
            valid_days=int(data["valid_days"]),
            missing_days=int(data["missing_days"]),
            skipped_windows=int(data["skipped_windows"]),
            window_counts=dict(data["window_counts"]),
            monthly_sorted_totals={
                m: [float(x) for x in v]
                for m, v in data["monthly_sorted_totals"].items()
            },
            monthly_quantiles={
                m: {k: float(v) for k, v in q.items()}
                for m, q in data["monthly_quantiles"].items()
            },
            checksum=data["checksum"],
            month_assignment=data.get("month_assignment", REFERENCE_MONTH_ASSIGNMENT),
            percentile_method=data.get("percentile_method", PERCENTILE_METHOD),
            preferred_model=data.get("preferred_model", HISTORICAL_MODEL_PREFERRED),
            model_fallback_note=data.get("model_fallback_note"),
        )


def _quantile(sorted_values: list[float], pct: float) -> float:
    """Linear-interpolation quantile of an already sorted list."""
    if not sorted_values:
        raise ClimatologyError("cannot compute quantile of empty distribution")
    if len(sorted_values) == 1:
        return round(sorted_values[0], 4)
    pos = (len(sorted_values) - 1) * (pct / 100.0)
    lo = int(pos)
    hi = min(lo + 1, len(sorted_values) - 1)
    frac = pos - lo
    value = sorted_values[lo] * (1 - frac) + sorted_values[hi] * frac
    return round(value, 4)


def percentile_of(reference: ClimatologyReference, month: int, value: float) -> float:
    """Percentile position (0-100) of a 7-day total in a monthly reference.

    Mean-rank convention: percentage of the historical distribution strictly
    below the value, plus half of the values equal to it. Deterministic and
    reproducible from the stored sorted distribution alone.
    """
    key = str(int(month))
    dist = reference.monthly_sorted_totals.get(key)
    if not dist:
        raise ClimatologyError(f"no historical distribution for month {month}")
    below = 0
    equal = 0
    for v in dist:
        if v < value:
            below += 1
        elif v == value:
            equal += 1
    return round(100.0 * (below + 0.5 * equal) / len(dist), 4)


def build_climatology(
    point: MonitoringPoint,
    dates: list[str],
    precipitation: list[Optional[float]],
    retrieval_time: str,
    generated_at: str,
    returned_coordinate: dict[str, Optional[float]] | None = None,
    elevation_m: Optional[float] = None,
    baseline_start: str = CLIMATOLOGY_BASELINE_START,
    baseline_end: str = CLIMATOLOGY_BASELINE_END,
    source_model: str = HISTORICAL_MODEL_PREFERRED,
    model_fallback_note: str | None = None,
) -> ClimatologyReference:
    """Roll 7-day windows over daily precipitation and group by month.

    Window = 7 consecutive days ending at day d; the total belongs to the
    natural month of d (documented frozen-methodology choice). Windows with
    any missing day are skipped and counted - never interpolated.
    """
    if len(dates) != len(precipitation):
        raise ClimatologyError("dates and precipitation length mismatch")
    by_date = {d: v for d, v in zip(dates, precipitation)}

    start = date.fromisoformat(baseline_start)
    end = date.fromisoformat(baseline_end)
    first_window_end = start + timedelta(days=WINDOW_DAYS - 1)

    monthly: dict[str, list[float]] = {}
    window_counts: dict[str, int] = {}
    skipped = 0
    valid_days = sum(1 for v in precipitation if v is not None)
    missing_days = len(precipitation) - valid_days

    day = first_window_end
    while day <= end:
        window = [day - timedelta(days=i) for i in range(WINDOW_DAYS - 1, -1, -1)]
        values = [by_date.get(d.isoformat()) for d in window]
        if any(v is None for v in values):
            skipped += 1
        else:
            total = round(sum(float(v) for v in values), 4)  # type: ignore[arg-type]
            key = str(day.month)
            monthly.setdefault(key, []).append(total)
            window_counts[key] = window_counts.get(key, 0) + 1
        day += timedelta(days=1)

    for totals in monthly.values():
        totals.sort()
    quantiles = {
        m: {f"p{int(q)}": _quantile(totals, q) for q in REFERENCE_QUANTILES}
        for m, totals in monthly.items()
    }

    canonical = json.dumps(
        {
            "point_id": point.point_id,
            "baseline": [baseline_start, baseline_end],
            "model": source_model,
            "algorithm": ALGORITHM_VERSION,
            "dates": dates,
            "precipitation": precipitation,
        },
        sort_keys=True,
    )
    checksum = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    return ClimatologyReference(
        point_id=point.point_id,
        baseline_start=baseline_start,
        baseline_end=baseline_end,
        source_model=source_model,
        algorithm_version=ALGORITHM_VERSION,
        requested_coordinate={
            "latitude": point.latitude,
            "longitude": point.longitude,
        },
        returned_coordinate=returned_coordinate or {"latitude": None, "longitude": None},
        elevation_m=elevation_m,
        generated_at=generated_at,
        retrieval_time=retrieval_time,
        units="mm",
        valid_days=valid_days,
        missing_days=missing_days,
        skipped_windows=skipped,
        window_counts=window_counts,
        monthly_sorted_totals=monthly,
        monthly_quantiles=quantiles,
        checksum=checksum,
        preferred_model=HISTORICAL_MODEL_PREFERRED,
        model_fallback_note=model_fallback_note,
    )


class HistoricalWeatherClient:
    """Bounded-retry client for the Open-Meteo Archive (ERA5-Land) API."""

    def __init__(
        self,
        http_get: HttpGet | None = None,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        max_attempts: int = MAX_ATTEMPTS,
        retry_backoff_s: float = RETRY_BACKOFF_S,
        sleep: Callable[[float], None] | None = None,
    ):
        self.http_get = http_get or default_http_get
        self.timeout_s = float(timeout_s)
        self.max_attempts = int(max_attempts)
        self.retry_backoff_s = float(retry_backoff_s)
        import time as _time

        self._sleep = sleep or _time.sleep

    def fetch_daily(
        self,
        point: MonitoringPoint,
        start: str = CLIMATOLOGY_BASELINE_START,
        end: str = CLIMATOLOGY_BASELINE_END,
        model: str | None = None,
    ) -> HistoricalResponse:
        """Fetch daily historical series; validate precipitation availability.

        With model=None the frozen preferred model (ERA5-Land) is requested
        first; if it returns no precipitation at all (current official API:
        ERA5-Land carries no precipitation variable), the consistent ERA5
        reanalysis on the same endpoint is used and the fallback is reported
        in HistoricalResponse.fallback_note. Mixed best-match is never used.
        """
        models = [model] if model else [
            HISTORICAL_MODEL_PREFERRED,
            HISTORICAL_MODEL_PRECIP_FALLBACK,
        ]
        fallback_note = None
        payload = None
        used = models[0]
        for i, candidate in enumerate(models):
            payload = self._fetch_with_model(point, start, end, candidate)
            used = candidate
            precip = payload["daily"]["precipitation_sum"]
            if any(v is not None for v in precip):
                if i > 0:
                    fallback_note = (
                        f"preferred model {models[0]} returned no precipitation "
                        f"(current Open-Meteo API: ERA5-Land has no precipitation "
                        f"variable); consistent single-model fallback to "
                        f"{candidate} on the same endpoint/period"
                    )
                break
        else:
            raise WeatherMalformedResponseError(
                f"point {point.point_id}: no precipitation data from any "
                f"consistent historical model ({models})"
            )
        return HistoricalResponse(
            payload=payload, model_used=used, fallback_note=fallback_note
        )

    def _fetch_with_model(
        self, point: MonitoringPoint, start: str, end: str, model: str
    ) -> dict[str, Any]:
        params = {
            "latitude": point.latitude,
            "longitude": point.longitude,
            "start_date": start,
            "end_date": end,
            "daily": "precipitation_sum,temperature_2m_max,temperature_2m_min",
            "timezone": "UTC",
            "models": model,
        }
        last_error: Exception | None = None
        payload: dict | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                payload = self.http_get(HISTORICAL_ENDPOINT, params, self.timeout_s)
                last_error = None
                break
            except (WeatherTransientError, WeatherTimeoutError) as exc:
                last_error = exc
                if attempt >= self.max_attempts:
                    break
                self._sleep(self.retry_backoff_s * attempt)
        if last_error is not None or payload is None:
            raise last_error or ClimatologyError("no payload retrieved")

        daily = payload.get("daily")
        if not isinstance(daily, dict) or not isinstance(daily.get("time"), list):
            raise WeatherMalformedResponseError(
                f"point {point.point_id}: archive response lacks daily.time"
            )
        if not isinstance(daily.get("precipitation_sum"), list):
            raise WeatherMalformedResponseError(
                f"point {point.point_id}: archive response lacks precipitation_sum"
            )
        return payload


class ClimatologyStore:
    """Persistent local cache of derived climatology references (runtime)."""

    def __init__(self, cache_dir: Path):
        self.cache_dir = Path(cache_dir)

    def path_for(self, point_id: str) -> Path:
        return self.cache_dir / f"climatology_{point_id}_{ALGORITHM_VERSION}.json"

    def save(self, reference: ClimatologyReference) -> Path:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        path = self.path_for(reference.point_id)
        path.write_text(
            json.dumps(reference.to_dict(), ensure_ascii=False), encoding="utf-8"
        )
        return path

    def load(
        self,
        point_id: str,
        baseline_start: str = CLIMATOLOGY_BASELINE_START,
        baseline_end: str = CLIMATOLOGY_BASELINE_END,
    ) -> ClimatologyReference | None:
        path = self.path_for(point_id)
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            ref = ClimatologyReference.from_dict(data)
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            return None
        if (
            ref.baseline_start != baseline_start
            or ref.baseline_end != baseline_end
            or ref.algorithm_version != ALGORITHM_VERSION
        ):
            return None  # stale reference: caller regenerates
        return ref


def runtime_dir() -> Path:
    import os

    env = os.environ.get("MOUNTAINGUARDIAN_RUNTIME_DIR", "")
    if env:
        return Path(env)
    return Path(__file__).resolve().parent.parent / "data" / "runtime"


def generate_reference(
    point: MonitoringPoint,
    client: HistoricalWeatherClient,
    store: ClimatologyStore,
    generated_at: str,
    retrieval_time: str | None = None,
    force: bool = False,
    baseline: tuple[str, str] = (CLIMATOLOGY_BASELINE_START, CLIMATOLOGY_BASELINE_END),
) -> tuple[ClimatologyReference, bool]:
    """Load the cached reference or download + build + cache it.

    Returns (reference, generated_now). Cached references are reused only
    when baseline period and algorithm version match.
    """
    if not force:
        cached = store.load(point.point_id, baseline[0], baseline[1])
        if cached is not None:
            return cached, False
    response = client.fetch_daily(point, baseline[0], baseline[1])
    payload = response.payload
    daily = payload["daily"]
    ref = build_climatology(
        point,
        dates=daily["time"],
        precipitation=daily["precipitation_sum"],
        retrieval_time=retrieval_time or generated_at,
        generated_at=generated_at,
        returned_coordinate={
            "latitude": payload.get("latitude"),
            "longitude": payload.get("longitude"),
        },
        elevation_m=payload.get("elevation"),
        baseline_start=baseline[0],
        baseline_end=baseline[1],
        source_model=response.model_used,
        model_fallback_note=response.fallback_note,
    )
    store.save(ref)
    return ref, True


def main(argv: list[str] | None = None) -> int:
    """CLI: materialize the production 1991-2020 reference for all points."""
    from datetime import datetime, timezone

    region = load_region()
    store = ClimatologyStore(runtime_dir() / "climatology")
    calls = {"n": 0}
    base_get = default_http_get

    def counting_get(url, params, timeout):
        calls["n"] += 1
        return base_get(url, params, timeout)

    client = HistoricalWeatherClient(http_get=counting_get)
    now = datetime.now(timezone.utc).isoformat()
    generated = 0
    for point in region.monitoring_points:
        cached_before = store.load(point.point_id) is not None
        ref, generated_now = generate_reference(point, client, store, now)
        generated += 1 if generated_now else 0
        print(
            f"{point.point_id}: baseline {ref.baseline_start}..{ref.baseline_end} "
            f"model={ref.source_model} windows={sum(ref.window_counts.values())} "
            f"missing_days={ref.missing_days} skipped={ref.skipped_windows} "
            f"generated_now={generated_now} cached_before={cached_before} "
            f"fallback={ref.model_fallback_note is not None} "
            f"checksum={ref.checksum[:16]}"
        )
    print(f"references generated: {generated}; live archive HTTP requests: {calls['n']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
