"""G03B – Historical Trend query and What Changed comparison (items 41-54,
29, plus snapshot eligibility rules).

Read-only queries over the G03A append-only snapshot store: no fabricated
history, no pre-filled future values, BACKFILL explicitly separated, invalid
and data-only snapshots excluded.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from riskwatch.engine.comparison import (  # noqa: E402
    PreviousState,
    build_what_changed,
    load_previous_state,
    previous_state_from_snapshot,
)
from riskwatch.engine.core import compute_risk_watch  # noqa: E402
from riskwatch.engine.trend import (  # noqa: E402
    TREND_AVAILABLE,
    TREND_INSUFFICIENT_HISTORY,
    TREND_NO_HISTORY,
    TREND_SIMPLE_COMPARISON,
    query_historical_trend,
)
from riskwatch.snapshot_store import SnapshotStore  # noqa: E402
from tests.g03b_helpers import (  # noqa: E402
    flat_climatologies,
    flat_weather,
    make_point_weather,
    write_region,
)

CENTER = date(2026, 8, 15)
REGION_ID = "test_region"


@pytest.fixture()
def store(tmp_path):
    with SnapshotStore(tmp_path / "trend.db") as s:
        yield s


@pytest.fixture()
def region(tmp_path):
    return write_region(tmp_path)


def insert_result(store, c_value, snapshot_id=None, created_at="2026-08-10T06:00:00+00:00",
                  scan_mode="LIVE", status="COMPLETED", level="ELEVATED",
                  recent_precip=None, forecast_precip=None, missing=None,
                  optional=None):
    payload = {
        "current_risk_index": c_value,
        "current_risk_level": level,
        "point_recent_percentiles": recent_precip or {},
        "point_forecast_percentiles": forecast_precip or {},
        "missing_data": missing or [],
        "optional_evidence_availability": optional or [],
    }
    return store.insert_snapshot(
        run_id=f"run-{snapshot_id or c_value}",
        region_id=REGION_ID,
        status=status,
        payload=payload,
        created_at=created_at,
        scan_mode=scan_mode,
        snapshot_id=snapshot_id,
    )


class TestTrendStatuses:
    def test_no_history_on_empty_store(self, store):
        trend = query_historical_trend(store, REGION_ID)
        assert trend.status == TREND_NO_HISTORY
        assert trend.entries == ()

    def test_one_valid_snapshot_is_insufficient_history(self, store):
        insert_result(store, 70.0)
        trend = query_historical_trend(store, REGION_ID)
        assert trend.status == TREND_INSUFFICIENT_HISTORY
        assert len(trend.entries) == 1
        assert trend.entries[0].risk_direction == "NO_HISTORY"

    def test_two_valid_snapshots_allow_simple_comparison(self, store):
        insert_result(store, 70.0, "s1", created_at="2026-08-09T06:00:00+00:00")
        insert_result(store, 76.0, "s2", created_at="2026-08-10T06:00:00+00:00")
        trend = query_historical_trend(store, REGION_ID)
        assert trend.status == TREND_SIMPLE_COMPARISON
        assert trend.entries[0].risk_direction == "NO_HISTORY"
        assert trend.entries[1].risk_direction == "RISING"  # +6 >= +5

    def test_three_or_more_snapshots_form_trend_series(self, store):
        insert_result(store, 70.0, "s1", created_at="2026-08-08T06:00:00+00:00")
        insert_result(store, 76.0, "s2", created_at="2026-08-09T06:00:00+00:00")
        insert_result(store, 55.0, "s3", created_at="2026-08-10T06:00:00+00:00")
        trend = query_historical_trend(store, REGION_ID)
        assert trend.status == TREND_AVAILABLE
        assert [e.current_risk_index for e in trend.entries] == [70.0, 76.0, 55.0]
        assert [e.risk_direction for e in trend.entries] == [
            "NO_HISTORY", "RISING", "FALLING"]  # +6 >= +5; -21 <= -5
        assert [e.risk_level for e in trend.entries] == [
            "ELEVATED", "ELEVATED", "MODERATE"]

    def test_invalid_snapshots_excluded(self, store):
        sid = insert_result(store, 70.0, "s1")
        insert_result(store, 71.0, "s2", created_at="2026-08-11T06:00:00+00:00")
        store.mark_invalid(sid, "correction: bad run")
        trend = query_historical_trend(store, REGION_ID)
        assert len(trend.entries) == 1
        assert trend.entries[0].snapshot_id == "s2"
        assert trend.status == TREND_INSUFFICIENT_HISTORY

    def test_failed_and_data_only_snapshots_excluded(self, store):
        insert_result(store, 70.0, "failed", status="FAILED")
        # G03A-style data-only snapshot: status OK, no current risk index
        store.insert_snapshot(
            run_id="g03a-data", region_id=REGION_ID, status="OK",
            payload={"region_id": REGION_ID, "monitoring_points": {}},
            created_at="2026-08-09T06:00:00+00:00")
        insert_result(store, 72.0, "good", created_at="2026-08-10T06:00:00+00:00")
        trend = query_historical_trend(store, REGION_ID)
        assert [e.snapshot_id for e in trend.entries] == ["good"]

    def test_backfill_excluded_by_default(self, store):
        insert_result(store, 65.0, "bf1", scan_mode="BACKFILL",
                      created_at="2026-08-08T06:00:00+00:00")
        insert_result(store, 70.0, "live1", created_at="2026-08-09T06:00:00+00:00")
        trend = query_historical_trend(store, REGION_ID)
        assert [e.snapshot_id for e in trend.entries] == ["live1"]
        assert trend.include_backfill is False

    def test_backfill_included_only_explicitly_and_labeled(self, store):
        insert_result(store, 65.0, "bf1", scan_mode="BACKFILL",
                      created_at="2026-08-08T06:00:00+00:00")
        insert_result(store, 70.0, "live1", created_at="2026-08-09T06:00:00+00:00")
        trend = query_historical_trend(store, REGION_ID, include_backfill=True)
        assert [e.snapshot_id for e in trend.entries] == ["bf1", "live1"]
        assert trend.entries[0].scan_mode == "BACKFILL"
        assert trend.entries[1].scan_mode == "LIVE"
        assert trend.include_backfill is True
        assert "BACKFILL" in trend.policy

    def test_no_fabricated_trend_points(self, store):
        insert_result(store, 70.0, "s1")
        trend = query_historical_trend(store, REGION_ID)
        assert len(trend.entries) == 1  # never padded or pre-filled

    def test_other_regions_isolated(self, store):
        insert_result(store, 70.0, "s1")
        trend = query_historical_trend(store, "other_region")
        assert trend.status == TREND_NO_HISTORY

    def test_limit_returns_most_recent_entries_with_full_series_direction(
            self, store):
        for i, c in enumerate((70.0, 76.0, 74.0, 80.0)):
            insert_result(store, c, f"s{i}",
                          created_at=f"2026-08-{8 + i}T06:00:00+00:00")
        trend = query_historical_trend(store, REGION_ID, limit=2)
        assert [e.snapshot_id for e in trend.entries] == ["s2", "s3"]
        # direction still computed from the full valid series
        assert trend.entries[0].risk_direction == "STABLE"   # 74 vs 76
        assert trend.entries[1].risk_direction == "RISING"   # 80 vs 74 (+6)
        assert trend.status == TREND_AVAILABLE

    def test_store_never_mutated_by_query(self, store):
        sid = insert_result(store, 70.0, "s1")
        before = store.get(sid)
        query_historical_trend(store, REGION_ID)
        after = store.get(sid)
        assert before == after
        assert store.count() == 1


class TestPreviousStateResolution:
    def test_previous_state_from_valid_snapshot(self, store):
        insert_result(
            store, 70.0, "s1",
            recent_precip={"source_zone": {"cumulative_precip_mm": 40.0}},
            forecast_precip={"source_zone": {"cumulative_precip_mm": 20.0}},
            missing=[{"point_id": "port_zone", "window_kind": "recent",
                      "reason": "weather_collection_failed"}],
            optional=["sentinel2_scene"],
        )
        state = previous_state_from_snapshot(store.get("s1"))
        assert state is not None
        assert state.current_C == 70.0
        assert state.recent_precip_by_point == {"source_zone": 40.0}
        assert state.missing_point_ids == ("port_zone",)
        assert state.optional_evidence_ids == ("sentinel2_scene",)

    def test_invalid_and_data_only_snapshots_not_eligible(self, store):
        sid = insert_result(store, 70.0, "s1")
        store.mark_invalid(sid, "bad")
        assert previous_state_from_snapshot(store.get("s1")) is None
        store.insert_snapshot(
            run_id="data", region_id=REGION_ID, status="OK", payload={},
            created_at="2026-08-09T06:00:00+00:00", snapshot_id="data1")
        assert previous_state_from_snapshot(store.get("data1")) is None

    def test_load_previous_state_picks_latest_valid(self, store):
        insert_result(store, 70.0, "s1", created_at="2026-08-08T06:00:00+00:00")
        insert_result(store, 72.0, "s2", created_at="2026-08-09T06:00:00+00:00")
        sid = insert_result(store, 74.0, "s3", created_at="2026-08-10T06:00:00+00:00")
        store.mark_invalid(sid, "bad")
        state = load_previous_state(store, REGION_ID)
        assert state.snapshot_id == "s2"

    def test_load_previous_state_skips_backfill_by_default(self, store):
        insert_result(store, 70.0, "live1", created_at="2026-08-08T06:00:00+00:00")
        insert_result(store, 90.0, "bf1", scan_mode="BACKFILL",
                      created_at="2026-08-09T06:00:00+00:00")
        state = load_previous_state(store, REGION_ID)
        assert state.snapshot_id == "live1"
        state = load_previous_state(store, REGION_ID, include_backfill=True)
        assert state.snapshot_id == "bf1"
        assert state.scan_mode == "BACKFILL"

    def test_load_previous_state_empty_store(self, store):
        assert load_previous_state(store, REGION_ID) is None


class TestEngineDirectionFromStore:
    def test_first_scan_direction_no_history(self, region, store):
        result = compute_risk_watch(
            region, flat_weather(CENTER), flat_climatologies(months=(8,)),
            previous=load_previous_state(store, region.region_id), run_id="r1")
        assert result.risk_direction == "NO_HISTORY"

    def test_direction_from_stored_previous(self, region, store):
        insert_result(store, 80.0, "s1")
        prev = load_previous_state(store, REGION_ID)
        result = compute_risk_watch(
            region, flat_weather(CENTER), flat_climatologies(months=(8,)),
            previous=prev, run_id="r2")
        assert result.previous_C == 80.0
        assert result.delta_C == pytest.approx(result.C - 80.0)
        assert result.risk_direction in {"RISING", "STABLE", "FALLING"}


class TestWhatChanged:
    def prev(self, c=80.0, recent=None, forecast=None, missing=(), optional=()):
        return PreviousState(
            snapshot_id="s-prev", created_at="2026-08-14T06:00:00+00:00",
            scan_mode="LIVE", current_C=c,
            recent_precip_by_point=dict(recent or {}),
            forecast_precip_by_point=dict(forecast or {}),
            missing_point_ids=tuple(missing),
            optional_evidence_ids=tuple(optional),
        )

    def test_no_previous_is_no_history(self, region):
        result = compute_risk_watch(
            region, flat_weather(CENTER), flat_climatologies(months=(8,)),
            previous=None, run_id="r")
        assert result.what_changed["status"] == "NO_HISTORY"

    def test_precipitation_increase_decrease_unchanged(self, region):
        weather = flat_weather(CENTER)  # source recent 70, port recent 50
        prev = self.prev(
            c=80.0,
            recent={"source_zone": 50.0,   # 70 now -> UP
                    "port_zone": 50.0},    # 50 now -> UNCHANGED
            forecast={"source_zone": 40.0,  # 30 now -> DOWN
                      "port_zone": 90.0},   # 90 now -> UNCHANGED
        )
        result = compute_risk_watch(
            region, weather, flat_climatologies(months=(8,)),
            previous=prev, run_id="r")
        wc = result.what_changed
        assert wc["status"] == "COMPARISON_AVAILABLE"
        assert wc["recent_precipitation"]["source_zone"]["direction"] == "UP"
        assert wc["recent_precipitation"]["source_zone"]["delta"] == \
            pytest.approx(20.0)
        assert wc["recent_precipitation"]["port_zone"]["direction"] == "UNCHANGED"
        assert wc["forecast_precipitation"]["source_zone"]["direction"] == "DOWN"
        assert wc["forecast_precipitation"]["source_zone"]["delta"] == \
            pytest.approx(-10.0)
        assert wc["forecast_precipitation"]["port_zone"]["direction"] == "UNCHANGED"

    def test_current_risk_delta_reported(self, region):
        prev = self.prev(c=80.0)
        result = compute_risk_watch(
            region, flat_weather(CENTER), flat_climatologies(months=(8,)),
            previous=prev, run_id="r")
        wc = result.what_changed["current_risk"]
        assert wc["previous"] == 80.0
        assert wc["current"] == result.C
        assert wc["delta"] == pytest.approx(result.C - 80.0)
        assert wc["direction"] == result.risk_direction
        assert wc["threshold_points"] == 5.0
        assert "not statistical significance" in wc["note"]

    def test_newly_missing_and_newly_available(self, region):
        weather = flat_weather(CENTER)
        prev = self.prev(c=80.0, missing=("source_zone",))
        result = compute_risk_watch(
            region, weather, flat_climatologies(months=(8,)),
            previous=prev, run_id="r")
        md = result.what_changed["missing_data"]
        assert md["previous_missing"] == ["source_zone"]
        assert md["current_missing"] == []
        assert md["newly_available"] == ["source_zone"]
        assert md["newly_missing"] == []

        # and the reverse: port_zone fails now
        from riskwatch.weather import PointWeatherFailure

        weather2 = flat_weather(CENTER)
        weather2["port_zone"] = PointWeatherFailure("port_zone", "E", "down")
        prev2 = self.prev(c=80.0)
        result2 = compute_risk_watch(
            region, weather2, flat_climatologies(months=(8,)),
            previous=prev2, run_id="r")
        md2 = result2.what_changed["missing_data"]
        assert md2["newly_missing"] == ["port_zone"]
        assert md2["newly_available"] == []

    def test_optional_evidence_availability_change_only(self, region):
        prev = self.prev(c=80.0, optional=("soil_moisture",))
        result = compute_risk_watch(
            region, flat_weather(CENTER), flat_climatologies(months=(8,)),
            previous=prev, run_id="r",
            optional_evidence=["sentinel2_scene"])
        oe = result.what_changed["optional_evidence"]
        assert oe["added"] == ["sentinel2_scene"]
        assert oe["removed"] == ["soil_moisture"]
        assert "never modifies" in oe["note"]
        # availability changes did NOT alter numeric outputs
        base = compute_risk_watch(
            region, flat_weather(CENTER), flat_climatologies(months=(8,)),
            previous=prev, run_id="r")
        assert (base.B, base.R, base.F, base.D, base.C, base.O7) == (
            result.B, result.R, result.F, result.D, result.C, result.O7)

    def test_not_comparable_when_point_data_absent(self, region):
        prev = self.prev(c=80.0, recent={"source_zone": 40.0})
        weather = flat_weather(CENTER)
        result = compute_risk_watch(
            region, weather, flat_climatologies(months=(8,)),
            previous=prev, run_id="r")
        entry = result.what_changed["recent_precipitation"]["port_zone"]
        assert entry["previous"] is None
        assert entry["direction"] == "NOT_COMPARABLE"

    def test_build_what_changed_is_pure(self):
        prev = self.prev(c=80.0, recent={"source_zone": 40.0})
        a = build_what_changed(88.0, {"source_zone": 70.0}, {}, [], [], prev)
        b = build_what_changed(88.0, {"source_zone": 70.0}, {}, [], [], prev)
        assert a == b
