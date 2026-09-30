"""G03A – 1991-2020 climatology: rolling 7-day, monthly reference, cache."""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from riskwatch.climatology import (  # noqa: E402
    ALGORITHM_VERSION,
    CLIMATOLOGY_BASELINE_END,
    CLIMATOLOGY_BASELINE_START,
    HISTORICAL_ENDPOINT,
    HISTORICAL_MODEL_PREFERRED,
    HISTORICAL_MODEL_PRECIP_FALLBACK,
    ClimatologyStore,
    HistoricalWeatherClient,
    build_climatology,
    generate_reference,
    percentile_of,
)
from riskwatch.region import MonitoringPoint  # noqa: E402
from tests.g03a_helpers import make_historical_payload  # noqa: E402

POINT = MonitoringPoint(
    point_id="source_zone",
    name="Source Zone",
    latitude=28.28,
    longitude=85.481,
    elevation_m=5200.0,
    coordinate_provenance={"type": "representative_derived"},
)
GEN_AT = "2026-10-01T06:00:00+00:00"


def series(start: str, end: str, value: float = 1.0, missing: set[str] | None = None):
    missing = missing or set()
    s, e = date.fromisoformat(start), date.fromisoformat(end)
    dates, values = [], []
    day = s
    while day <= e:
        dates.append(day.isoformat())
        values.append(None if day.isoformat() in missing else value)
        day += timedelta(days=1)
    return dates, values


class FakeArchive:
    def __init__(self, precip: float = 1.0, null_precip_for_models: set[str] | None = None):
        self.calls: list[dict] = []
        self.precip = precip
        self.null_precip_for_models = null_precip_for_models or set()

    def __call__(self, url, params, timeout):
        self.calls.append({"url": url, "params": dict(params), "timeout": timeout})
        precip = (
            None if params["models"] in self.null_precip_for_models else self.precip
        )
        return make_historical_payload(
            params["start_date"], params["end_date"], precip=precip
        )


class TestFrozenContract:
    def test_baseline_period_is_frozen(self):
        assert CLIMATOLOGY_BASELINE_START == "1991-01-01"
        assert CLIMATOLOGY_BASELINE_END == "2020-12-31"

    def test_client_requests_frozen_preferred_model_for_frozen_period(self):
        archive = FakeArchive()
        client = HistoricalWeatherClient(http_get=archive, sleep=lambda s: None)
        response = client.fetch_daily(POINT)
        call = archive.calls[0]
        assert call["url"] == HISTORICAL_ENDPOINT
        p = call["params"]
        assert p["models"] == HISTORICAL_MODEL_PREFERRED == "era5_land"
        assert p["start_date"] == "1991-01-01"
        assert p["end_date"] == "2020-12-31"
        assert "precipitation_sum" in p["daily"]
        assert p["timezone"] == "UTC"
        assert response.model_used == "era5_land"
        assert response.fallback_note is None

    def test_validated_fallback_when_preferred_model_lacks_precipitation(self):
        # Current official API reality: ERA5-Land carries no precipitation.
        archive = FakeArchive(null_precip_for_models={"era5_land"})
        client = HistoricalWeatherClient(http_get=archive, sleep=lambda s: None)
        response = client.fetch_daily(POINT)
        assert [c["params"]["models"] for c in archive.calls] == [
            "era5_land",
            HISTORICAL_MODEL_PRECIP_FALLBACK,
        ]
        assert response.model_used == HISTORICAL_MODEL_PRECIP_FALLBACK == "era5"
        assert response.fallback_note
        assert any(
            v is not None for v in response.payload["daily"]["precipitation_sum"]
        )

    def test_no_fabrication_when_all_models_lack_precipitation(self):
        from riskwatch.weather import WeatherMalformedResponseError

        archive = FakeArchive(null_precip_for_models={"era5_land", "era5"})
        client = HistoricalWeatherClient(http_get=archive, sleep=lambda s: None)
        with pytest.raises(WeatherMalformedResponseError):
            client.fetch_daily(POINT)

    def test_client_rejects_malformed_archive_response(self):
        from riskwatch.weather import WeatherMalformedResponseError

        client = HistoricalWeatherClient(
            http_get=lambda u, p, t: {"daily": {}}, sleep=lambda s: None
        )
        with pytest.raises(WeatherMalformedResponseError):
            client.fetch_daily(POINT, "1991-01-01", "1991-01-10")


class TestRollingSevenDay:
    def test_constant_series_gives_seven_mm_windows(self):
        dates, values = series("1991-01-01", "1991-01-14", value=1.0)
        ref = build_climatology(
            POINT, dates, values, GEN_AT, GEN_AT,
            baseline_start="1991-01-01", baseline_end="1991-01-14",
        )
        assert ref.monthly_sorted_totals["1"] == [7.0] * 8
        assert ref.skipped_windows == 0
        assert ref.missing_days == 0

    def test_windows_grouped_by_window_end_month(self):
        dates, values = series("1991-01-01", "1991-02-10", value=1.0)
        ref = build_climatology(
            POINT, dates, values, GEN_AT, GEN_AT,
            baseline_start="1991-01-01", baseline_end="1991-02-10",
        )
        # January windows end 01-07..01-31 (25), February windows end 02-01..02-10 (10)
        assert ref.window_counts == {"1": 25, "2": 10}
        assert ref.month_assignment == "window_end_month"

    def test_missing_days_are_skipped_never_interpolated(self):
        missing = {"1991-01-10"}
        dates, values = series("1991-01-01", "1991-01-20", value=1.0, missing=missing)
        ref = build_climatology(
            POINT, dates, values, GEN_AT, GEN_AT,
            baseline_start="1991-01-01", baseline_end="1991-01-20",
        )
        # windows ending 01-10 .. 01-16 contain the gap -> skipped
        assert ref.skipped_windows == 7
        assert ref.missing_days == 1
        assert ref.valid_days == 19
        assert ref.monthly_sorted_totals["1"] == [7.0] * 7  # 01-07..01-09 + 01-17..01-20
        assert 7.0 in ref.monthly_sorted_totals["1"]

    def test_length_mismatch_rejected(self):
        with pytest.raises(Exception):
            build_climatology(
                POINT, ["1991-01-01"], [1.0, 2.0], GEN_AT, GEN_AT,
                baseline_start="1991-01-01", baseline_end="1991-01-10",
            )


class TestReferenceAndPercentiles:
    def _ref(self):
        dates, values = series("1991-01-01", "1991-01-31")
        vals = [float(i % 10 + 1) for i in range(len(dates))]
        return build_climatology(
            POINT, dates, vals, GEN_AT, GEN_AT,
            baseline_start="1991-01-01", baseline_end="1991-01-31",
        )

    def test_full_distribution_retained_not_only_quantiles(self):
        ref = self._ref()
        assert len(ref.monthly_sorted_totals["1"]) == ref.window_counts["1"] > 5
        assert set(ref.monthly_quantiles["1"]) == {"p50", "p75", "p90", "p95", "p99"}

    def test_percentile_lookup_mean_rank(self):
        dates = [f"1991-01-{d:02d}" for d in range(1, 18)]
        # strictly increasing daily values -> distinct 7-day window totals
        vals = [float(i + 1) for i in range(len(dates))]
        ref = build_climatology(
            POINT, dates, vals, GEN_AT, GEN_AT,
            baseline_start="1991-01-01", baseline_end="1991-01-17",
        )
        dist = ref.monthly_sorted_totals["1"]
        assert dist == sorted(dist)
        assert len(dist) == 11
        # percentile of a value below everything is 0, above everything is 100
        assert percentile_of(ref, 1, dist[0] - 1) == 0.0
        n = len(dist)
        assert percentile_of(ref, 1, dist[-1] + 1) == 100.0
        # mean-rank: top value has n-1 below and 1 equal (itself)
        assert percentile_of(ref, 1, dist[-1]) == pytest.approx(100.0 * (n - 0.5) / n)
        # a value between two neighbours ranks by count below
        mid = (dist[4] + dist[5]) / 2
        assert percentile_of(ref, 1, mid) == pytest.approx(100.0 * 5 / n)

    def test_reproducibility_identical_input_identical_output(self):
        dates, values = series("1991-01-01", "1991-03-31", value=2.0)
        a = build_climatology(
            POINT, dates, values, GEN_AT, GEN_AT,
            baseline_start="1991-01-01", baseline_end="1991-03-31",
        )
        b = build_climatology(
            POINT, list(dates), list(values), GEN_AT, GEN_AT,
            baseline_start="1991-01-01", baseline_end="1991-03-31",
        )
        assert a.to_dict() == b.to_dict()
        assert a.checksum == b.checksum
        assert a.algorithm_version == ALGORITHM_VERSION

    def test_provenance_fields_present(self):
        ref = self._ref()
        d = ref.to_dict()
        for key in (
            "baseline_start", "baseline_end", "source_model", "algorithm_version",
            "requested_coordinate", "returned_coordinate", "elevation_m",
            "generated_at", "retrieval_time", "units", "valid_days",
            "missing_days", "skipped_windows", "checksum",
        ):
            assert key in d


class TestClimatologyCache:
    def test_store_roundtrip_and_version_gate(self, tmp_path):
        store = ClimatologyStore(tmp_path)
        dates, values = series("1991-01-01", "1991-01-31")
        ref = build_climatology(
            POINT, dates, values, GEN_AT, GEN_AT,
            baseline_start="1991-01-01", baseline_end="1991-01-31",
        )
        store.save(ref)
        loaded = store.load(
            POINT.point_id, baseline_start="1991-01-01", baseline_end="1991-01-31"
        )
        assert loaded is not None
        assert loaded.to_dict() == ref.to_dict()
        # a different baseline period must not reuse this reference
        assert store.load(POINT.point_id, "1990-01-01", "2020-12-31") is None
        assert (
            store.load(
                POINT.point_id, baseline_start="1991-01-01", baseline_end="2020-12-31"
            )
            is None
        )

    def test_generate_reference_downloads_once_then_caches(self, tmp_path):
        archive = FakeArchive()
        client = HistoricalWeatherClient(http_get=archive, sleep=lambda s: None)
        store = ClimatologyStore(tmp_path)
        ref1, generated1 = generate_reference(POINT, client, store, GEN_AT)
        ref2, generated2 = generate_reference(POINT, client, store, GEN_AT)
        assert generated1 is True and generated2 is False
        assert len(archive.calls) == 1
        assert ref1.checksum == ref2.checksum
        # the cached file is under runtime storage, not the repo data dirs
        assert store.path_for(POINT.point_id).parent == tmp_path
