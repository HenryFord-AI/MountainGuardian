"""G03A – raw weather cache semantics (TTL, honesty, corruption)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from riskwatch.cache import CACHE_TTL_SECONDS, WeatherRawCache  # noqa: E402

ENDPOINT = "https://api.open-meteo.com/v1/forecast"
PARAMS = {"latitude": 28.279, "longitude": 85.379, "daily": "precipitation_sum"}
T0 = 1_700_000_000.0


class TestRawCache:
    def test_default_ttl_is_frozen_thirty_minutes(self):
        assert CACHE_TTL_SECONDS == 30 * 60

    def test_put_get_roundtrip(self, tmp_path):
        cache = WeatherRawCache(tmp_path, clock=lambda: T0 + 10)
        cache.put(ENDPOINT, PARAMS, {"daily": {"time": ["x"]}}, "2026-10-01T06:00:00+00:00", T0)
        hit = cache.get(ENDPOINT, PARAMS)
        assert hit is not None
        assert hit.payload == {"daily": {"time": ["x"]}}
        assert hit.cached is True

    def test_original_retrieval_time_preserved(self, tmp_path):
        cache = WeatherRawCache(tmp_path, clock=lambda: T0 + 60)
        cache.put(ENDPOINT, PARAMS, {"a": 1}, "2026-10-01T06:00:00+00:00", T0)
        hit = cache.get(ENDPOINT, PARAMS)
        assert hit.original_retrieval_time == "2026-10-01T06:00:00+00:00"
        assert hit.retrieved_at_epoch == T0
        assert hit.cache_age_seconds == pytest.approx(60)

    def test_hit_within_window_then_expiry(self, tmp_path):
        cache_in = WeatherRawCache(tmp_path, clock=lambda: T0)
        cache_in.put(ENDPOINT, PARAMS, {"a": 1}, "t", T0)
        fresh = WeatherRawCache(tmp_path, clock=lambda: T0 + 29 * 60)
        assert fresh.get(ENDPOINT, PARAMS) is not None
        expired = WeatherRawCache(tmp_path, clock=lambda: T0 + 31 * 60)
        assert expired.get(ENDPOINT, PARAMS) is None

    def test_different_params_do_not_collide(self, tmp_path):
        cache = WeatherRawCache(tmp_path, clock=lambda: T0)
        cache.put(ENDPOINT, PARAMS, {"a": 1}, "t", T0)
        other = dict(PARAMS, latitude=28.28)
        assert cache.get(ENDPOINT, other) is None

    def test_corrupt_entry_is_a_miss_not_a_crash(self, tmp_path):
        cache = WeatherRawCache(tmp_path, clock=lambda: T0)
        cache.put(ENDPOINT, PARAMS, {"a": 1}, "t", T0)
        path = cache._path(cache.key_for(ENDPOINT, PARAMS))
        path.write_text("{not json", encoding="utf-8")
        assert cache.get(ENDPOINT, PARAMS) is None

    def test_cache_files_live_outside_git(self, tmp_path):
        cache = WeatherRawCache(tmp_path, clock=lambda: T0)
        cache.put(ENDPOINT, PARAMS, {"a": 1}, "t", T0)
        gitignore = (Path(__file__).parent.parent / ".gitignore").read_text(encoding="utf-8")
        assert "data/runtime/" in gitignore
