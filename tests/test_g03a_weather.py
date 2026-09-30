"""G03A – weather request construction, normalization, failures, cache."""

from __future__ import annotations

import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from riskwatch.cache import WeatherRawCache  # noqa: E402
from riskwatch.region import MonitoringPoint, load_region  # noqa: E402
from riskwatch.weather import (  # noqa: E402
    FORECAST_ENDPOINT,
    FORECAST_MODEL,
    QUALITY_FRESH,
    QUALITY_MISSING,
    QUALITY_STALE,
    STATUS_FAILED,
    STATUS_OK,
    STATUS_PARTIAL,
    PointWeather,
    PointWeatherFailure,
    WeatherCollector,
    WeatherMalformedResponseError,
    WeatherTimeoutError,
    WeatherTransientError,
    build_request_params,
    normalize_weather,
)
from tests.g03a_helpers import make_daily_payload  # noqa: E402

TODAY = date(2026, 10, 1)
NOW = datetime(2026, 10, 1, 6, 0, 0, tzinfo=timezone.utc)

SOURCE = MonitoringPoint(
    point_id="source_zone",
    name="Source Zone",
    latitude=28.28,
    longitude=85.481,
    elevation_m=5200.0,
    coordinate_provenance={"type": "representative_derived"},
)
PORT = MonitoringPoint(
    point_id="port_zone",
    name="Port Zone",
    latitude=28.279,
    longitude=85.379,
    elevation_m=1800.0,
    coordinate_provenance={"type": "representative"},
)


class FakeTransport:
    """Deterministic transport: per-point payloads or raised exceptions."""

    def __init__(self, payload=None, error=None, per_point=None, record=None):
        self.payload = payload
        self.error = error
        self.per_point = per_point or {}
        self.calls: list[tuple[str, dict]] = []
        self.record = record if record is not None else []

    def __call__(self, url, params, timeout):
        self.calls.append((url, params))
        self.record.append((url, dict(params), timeout))
        entry = self.per_point.get(params["latitude"])
        if entry is not None:
            if isinstance(entry, Exception):
                raise entry
            return entry
        if self.error is not None:
            raise self.error
        return self.payload if self.payload is not None else make_daily_payload(TODAY)


def collector(transport, **kw):
    return WeatherCollector(
        http_get=transport,
        clock=lambda: NOW,
        sleep=lambda s: None,
        **kw,
    )


class TestRequestConstruction:
    def test_request_params_match_frozen_contract(self):
        params = build_request_params(SOURCE)
        assert params["latitude"] == 28.28
        assert params["longitude"] == 85.481
        assert params["models"] == FORECAST_MODEL == "ecmwf_ifs"
        assert params["daily"] == "precipitation_sum,temperature_2m_max,temperature_2m_min"
        assert params["past_days"] == 7
        assert params["forecast_days"] == 7
        assert params["timezone"] == "UTC"

    def test_request_uses_endpoint_and_explicit_timeout(self):
        transport = FakeTransport()
        collector(transport, timeout_s=7.5).collect_point(PORT)
        url, params, timeout = transport.record[0]
        assert url == FORECAST_ENDPOINT
        assert timeout == 7.5


class TestNormalization:
    def setup_method(self):
        self.payload = make_daily_payload(TODAY)
        self.weather = normalize_weather(
            self.payload, PORT, NOW.isoformat(), NOW.isoformat()
        )

    def test_recent_seven_day_precipitation(self):
        recent = self.weather.recent
        assert recent["start"] == (TODAY - timedelta(days=7)).isoformat()
        assert recent["end"] == (TODAY - timedelta(days=1)).isoformat()
        assert recent["expected_days"] == 7
        assert recent["available_days"] == 7
        assert recent["cumulative_precipitation_mm"] == pytest.approx(7 * 2.5)
        assert recent["max_daily_precipitation_mm"] == pytest.approx(2.5)
        assert recent["missing_days"] == []

    def test_forecast_seven_day_precipitation(self):
        fc = self.weather.forecast
        assert fc["start"] == TODAY.isoformat()
        assert fc["end"] == (TODAY + timedelta(days=6)).isoformat()
        assert fc["expected_days"] == 7
        assert fc["cumulative_precipitation_mm"] == pytest.approx(7 * 2.5)

    def test_temperature_evidence_present(self):
        assert self.weather.recent["temperature_range_c"] == {"min": -2.0, "max": 10.0}
        assert self.weather.forecast["temperature_range_c"] == {"min": -2.0, "max": 10.0}

    def test_units_recorded(self):
        assert self.weather.units == {"precipitation": "mm", "temperature": "degC"}
        assert self.weather.provenance["units"]["precipitation_sum"] == "mm"

    def test_requested_vs_returned_coordinates(self):
        prov = self.weather.provenance
        assert prov["requested_coordinate"] == {"latitude": 28.279, "longitude": 85.379}
        assert prov["returned_coordinate"] == {"latitude": 28.25, "longitude": 85.5}
        assert prov["elevation_m"] == 4321.0

    def test_retrieval_time_and_provider_metadata(self):
        prov = self.weather.provenance
        assert prov["retrieval_time"] == NOW.isoformat()
        assert prov["request_time"] == NOW.isoformat()
        assert prov["provider"] == "Open-Meteo"
        assert prov["endpoint"] == FORECAST_ENDPOINT
        assert prov["model_requested"] == "ecmwf_ifs"
        assert prov["timezone"] == "UTC"
        assert prov["generationtime_ms"] == 1.25
        assert prov["from_cache"] is False

    def test_quality_fresh_for_complete_recent_window(self):
        assert self.weather.quality == QUALITY_FRESH

    def test_missing_day_is_not_zero_filled(self):
        missing_day = (TODAY - timedelta(days=3)).isoformat()
        payload = make_daily_payload(TODAY, missing_recent_days=[missing_day])
        weather = normalize_weather(payload, PORT, NOW.isoformat(), NOW.isoformat())
        assert weather.recent["cumulative_precipitation_mm"] is None
        assert weather.recent["missing_days"] == [missing_day]
        assert weather.recent["available_days"] == 6
        assert weather.quality == QUALITY_STALE
        assert weather.missing["recent_missing_days"] == [missing_day]

    def test_all_missing_is_missing_quality(self):
        missing = [
            (TODAY - timedelta(days=i)).isoformat() for i in range(1, 8)
        ] + [(TODAY + timedelta(days=i)).isoformat() for i in range(7)]
        payload = make_daily_payload(TODAY, missing_recent_days=missing[:7], missing_forecast_days=missing[7:])
        weather = normalize_weather(payload, PORT, NOW.isoformat(), NOW.isoformat())
        assert weather.quality == QUALITY_MISSING
        assert weather.recent["cumulative_precipitation_mm"] is None


class TestMalformedResponses:
    def test_missing_daily_object(self):
        with pytest.raises(WeatherMalformedResponseError):
            normalize_weather({"latitude": 1}, PORT, NOW.isoformat(), NOW.isoformat())

    def test_missing_required_field(self):
        payload = make_daily_payload(TODAY)
        del payload["daily"]["precipitation_sum"]
        with pytest.raises(WeatherMalformedResponseError):
            normalize_weather(payload, PORT, NOW.isoformat(), NOW.isoformat())

    def test_inconsistent_array_lengths(self):
        payload = make_daily_payload(TODAY)
        payload["daily"]["precipitation_sum"] = payload["daily"]["precipitation_sum"][:-1]
        with pytest.raises(WeatherMalformedResponseError):
            normalize_weather(payload, PORT, NOW.isoformat(), NOW.isoformat())

    def test_collector_reports_malformed_as_point_failure(self):
        transport = FakeTransport(payload={"daily": {"time": []}})
        result = collector(transport).collect_point(PORT)
        assert isinstance(result, PointWeatherFailure)
        assert result.error_type == "WeatherMalformedResponseError"


class TestTimeoutAndRetry:
    def test_timeout_becomes_point_failure(self):
        transport = FakeTransport(error=WeatherTimeoutError("boom"))
        result = collector(transport).collect_point(PORT)
        assert isinstance(result, PointWeatherFailure)
        assert result.error_type == "WeatherTimeoutError"
        assert len(transport.calls) == 3  # bounded: 1 + 2 retries

    def test_transient_failure_retried_then_succeeds(self):
        state = {"n": 0}

        def flaky(url, params, timeout):
            state["n"] += 1
            if state["n"] < 3:
                raise WeatherTransientError("503")
            return make_daily_payload(TODAY)

        sleeps: list[float] = []
        coll = WeatherCollector(
            http_get=flaky, clock=lambda: NOW, sleep=sleeps.append
        )
        result = coll.collect_point(PORT)
        assert isinstance(result, PointWeather)
        assert state["n"] == 3
        assert sleeps == [0.5, 1.0]

    def test_retry_is_bounded(self):
        transport = FakeTransport(error=WeatherTransientError("503"))
        coll = collector(transport, max_attempts=2)
        result = coll.collect_point(PORT)
        assert isinstance(result, PointWeatherFailure)
        assert len(transport.calls) == 2

    def test_config_error_not_retried(self):
        from riskwatch.weather import WeatherConfigError

        transport = FakeTransport(error=WeatherConfigError("400"))
        collector(transport).collect_point(PORT)
        assert len(transport.calls) == 1


class TestRegionLevelFailures:
    class _Region:
        region_id = "jilong_port"

        def __init__(self):
            self._points = [SOURCE, PORT]

        @property
        def monitoring_points(self):
            return self._points

    def test_partial_point_failure(self):
        transport = FakeTransport(
            per_point={PORT.latitude: WeatherTimeoutError("port down")}
        )
        result = collector(transport).collect_region(self._Region())
        assert result.status == STATUS_PARTIAL
        assert isinstance(result.points["source_zone"], PointWeather)
        assert isinstance(result.points["port_zone"], PointWeatherFailure)
        assert result.coverage["required_points_ok"] == 1
        assert result.coverage["required_points_failed"] == 1
        assert result.coverage["evidence_coverage_reduced"] is True
        assert result.coverage["failed_points"][0]["reason"]

    def test_all_points_failure(self):
        transport = FakeTransport(error=WeatherTransientError("down"))
        result = collector(transport).collect_region(self._Region())
        assert result.status == STATUS_FAILED
        assert result.ok_points == []
        assert sorted(result.failed_points) == ["port_zone", "source_zone"]
        # no fabricated values anywhere
        dumped = result.to_dict()
        assert dumped["coverage"]["required_points_ok"] == 0

    def test_success_at_both_points(self):
        transport = FakeTransport()
        result = collector(transport).collect_region(self._Region())
        assert result.status == STATUS_OK
        assert result.coverage["required_points_ok"] == 2


class TestWeatherCache:
    def test_cache_hit_reuses_raw_and_preserves_original_retrieval(self, tmp_path):
        cache = WeatherRawCache(tmp_path / "wc", clock=lambda: NOW.timestamp())
        transport = FakeTransport()
        coll = collector(transport, cache=cache)
        first = coll.collect_point(PORT)
        assert isinstance(first, PointWeather)
        assert len(transport.calls) == 1
        original_retrieval = first.provenance["retrieval_time"]

        later = datetime(2026, 10, 1, 6, 20, 0, tzinfo=timezone.utc)
        cache2 = WeatherRawCache(tmp_path / "wc", clock=lambda: later.timestamp())
        coll2 = WeatherCollector(
            http_get=transport, clock=lambda: later, sleep=lambda s: None, cache=cache2
        )
        second = coll2.collect_point(PORT)
        assert isinstance(second, PointWeather)
        assert len(transport.calls) == 1  # no second HTTP request
        assert second.provenance["from_cache"] is True
        assert second.provenance["retrieval_time"] == original_retrieval
        assert second.provenance["original_retrieval_time"] == original_retrieval
        assert second.provenance["request_time"] == later.isoformat()
        assert second.provenance["cache_age_seconds"] == pytest.approx(20 * 60, abs=5)

    def test_cache_expiry_forces_fresh_retrieval(self, tmp_path):
        cache = WeatherRawCache(
            tmp_path / "wc", ttl_seconds=60, clock=lambda: NOW.timestamp()
        )
        transport = FakeTransport()
        coll = collector(transport, cache=cache)
        coll.collect_point(PORT)
        much_later = NOW + timedelta(hours=2)
        cache2 = WeatherRawCache(
            tmp_path / "wc", ttl_seconds=60, clock=lambda: much_later.timestamp()
        )
        coll2 = WeatherCollector(
            http_get=transport, clock=lambda: much_later, sleep=lambda s: None, cache=cache2
        )
        coll2.collect_point(PORT)
        assert len(transport.calls) == 2


class TestNoNetworkInOrdinaryTests:
    def test_default_transport_blocked_socket_produces_failure_not_fabrication(
        self, monkeypatch
    ):
        import socket

        def deny(*args, **kwargs):
            raise AssertionError("ordinary tests must not open sockets")

        monkeypatch.setattr(socket, "create_connection", deny)
        monkeypatch.setattr(socket, "socket", deny)
        monkeypatch.setattr(socket, "getaddrinfo", deny)
        coll = WeatherCollector(sleep=lambda s: None, timeout_s=1, max_attempts=1)
        result = coll.collect_point(PORT)
        assert isinstance(result, PointWeatherFailure)
