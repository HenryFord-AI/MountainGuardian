"""
MountainGuardian G03A – opt-in LIVE Open-Meteo verification (no secret).

Runs ONLY with RUN_LIVE_TESTS=1. Performs the minimum bounded number of
real requests:

  1. Source Zone operational forecast (past 7 + next 7 days)
  2. Port Zone operational forecast (past 7 + next 7 days)
  3. One bounded historical archive probe (1991-01) proving the ERA5-Land
     contract for the frozen baseline period.

Full 1991-2020 climatology generation is executed once via
`python -m riskwatch.climatology` during Gate verification (2 more requests,
then cached), not inside ordinary or repeated test runs.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from riskwatch.cache import WeatherRawCache  # noqa: E402
from riskwatch.climatology import HistoricalWeatherClient  # noqa: E402
from riskwatch.region import load_region  # noqa: E402
from riskwatch.weather import (  # noqa: E402
    STATUS_OK,
    PointWeather,
    WeatherCollector,
)

_LIVE_ENABLED = os.environ.get("RUN_LIVE_TESTS", "") == "1"

pytestmark = [
    pytest.mark.live_openmeteo,
    pytest.mark.skipif(
        not _LIVE_ENABLED,
        reason="opt-in live Open-Meteo test: set RUN_LIVE_TESTS=1",
    ),
]


@pytest.fixture(scope="module")
def region():
    return load_region()


@pytest.fixture(scope="module")
def live_result(region, tmp_path_factory):
    cache = WeatherRawCache(tmp_path_factory.mktemp("live_cache"))
    collector = WeatherCollector(cache=cache, timeout_s=20.0)
    return collector.collect_region(region)


class TestLiveOperationalWeather:
    def test_both_points_return_real_data(self, live_result):
        assert live_result.status == STATUS_OK
        for point_id in ("source_zone", "port_zone"):
            point = live_result.points[point_id]
            assert isinstance(point, PointWeather), point_id

    def test_precipitation_and_temperature_available(self, live_result):
        for point_id in ("source_zone", "port_zone"):
            point = live_result.points[point_id]
            assert point.recent["available_days"] == 7, point_id
            assert point.forecast["available_days"] == 7, point_id
            assert point.recent["cumulative_precipitation_mm"] is not None
            assert point.forecast["cumulative_precipitation_mm"] is not None
            assert point.recent["temperature_range_c"] is not None
            assert point.forecast["temperature_range_c"] is not None

    def test_windows_cover_frozen_requirements(self, live_result):
        # "today" is the UTC retrieval date, matching normalization semantics
        today = datetime.fromisoformat(live_result.retrieval_time).date()
        for point_id in ("source_zone", "port_zone"):
            point = live_result.points[point_id]
            assert point.recent["end"] == (today - timedelta(days=1)).isoformat()
            assert point.forecast["end"] >= (today + timedelta(days=6)).isoformat()

    def test_requested_and_returned_metadata_captured(self, region, live_result):
        for point in region.monitoring_points:
            prov = live_result.points[point.point_id].provenance
            assert prov["requested_coordinate"] == {
                "latitude": point.latitude,
                "longitude": point.longitude,
            }
            assert prov["returned_coordinate"]["latitude"] is not None
            assert prov["returned_coordinate"]["longitude"] is not None
            assert prov["elevation_m"] is not None
            assert prov["provider"] == "Open-Meteo"
            assert prov["model_requested"] == "ecmwf_ifs"
            datetime.fromisoformat(prov["retrieval_time"])
            assert prov["from_cache"] is False


class TestLiveHistoricalContract:
    def test_archive_serves_frozen_baseline_period_with_consistent_model(self, region):
        client = HistoricalWeatherClient(timeout_s=60.0)
        response = client.fetch_daily(
            region.point("source_zone"), "1991-01-01", "1991-01-31"
        )
        daily = response.payload["daily"]
        assert len(daily["time"]) == 31
        assert len(daily["precipitation_sum"]) == 31
        assert response.payload["latitude"] is not None
        assert response.payload["elevation"] is not None
        assert any(v is not None for v in daily["precipitation_sum"])
        assert response.model_used in ("era5_land", "era5")
        if response.fallback_note:
            # frozen preference unavailable for precipitation on current API:
            # the consistent single-model fallback must be what we got
            assert response.model_used == "era5"
