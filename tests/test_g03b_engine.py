"""G03B – deterministic engine: percentiles, aggregation, formulas, bands,
direction, failure handling, scientific separation and determinism.

Test item mapping (gate contract): 8-22, 23-28, 29-34, 35-40, 63-65, 68-70.
"""

from __future__ import annotations

import json
import math
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from riskwatch.climatology import percentile_of  # noqa: E402
from riskwatch.engine.comparison import PreviousState  # noqa: E402
from riskwatch.engine.core import (  # noqa: E402
    collect_point_percentile,
    compute_risk_watch,
)
from riskwatch.engine.formulas import (  # noqa: E402
    ALGORITHM_VERSION,
    FORMULA_VERSION,
    RiskFormulaError,
    classify_band,
    classify_direction,
    compute_C,
    compute_D,
    compute_O7,
    validate_index,
)
from riskwatch.weather import PointWeatherFailure  # noqa: E402
from tests.g03b_helpers import (  # noqa: E402
    EXACT_FACTORS,
    direct_region,
    flat_climatologies,
    flat_weather,
    make_point_weather,
    make_reference,
    uniform_totals,
    write_region,
)

CENTER = date(2026, 8, 15)  # recent 08-08..08-14, forecast 08-15..08-21 (month 8)


def even_totals() -> list[float]:
    """0, 2, 4, ..., 198: percentile_of(99.0) == exactly 50.0."""
    return [2.0 * i for i in range(100)]


def positive_totals() -> list[float]:
    """1.0 .. 100.0: percentile_of(0.0) == exactly 0.0."""
    return [float(i + 1) for i in range(100)]


def make_exact_weather(total: float = 99.0):
    """All four windows: cumulative == total (percentile 50.0 on evens)."""
    from tests.g03b_helpers import flat_weather as _fw

    return _fw(CENTER, source_recent_mm=total, source_forecast_mm=total,
               port_recent_mm=total, port_forecast_mm=total)


def exact_climatologies():
    from tests.g03b_helpers import make_reference as _mr

    return {pid: _mr(pid, {8: even_totals()})
            for pid in ("source_zone", "port_zone")}


@pytest.fixture()
def region(tmp_path):
    return write_region(tmp_path)


@pytest.fixture()
def exact_region(tmp_path):
    """B == 80.0 exactly; with R == F == 50.0 -> D == 50.0, C == O7 == 71.0."""
    return write_region(
        tmp_path,
        factors=EXACT_FACTORS,
        region_id="exact_region",
        original_weight_ratio=None,
    )


@pytest.fixture()
def climatologies():
    return flat_climatologies(months=(8,))


@pytest.fixture()
def weather():
    return flat_weather(CENTER)


def run(region, weather, climatologies, **kwargs):
    return compute_risk_watch(
        region, weather, climatologies, run_id="test-run", **kwargs
    )


class TestPointPercentiles:
    def test_recent_point_percentile_matches_g03a_method(self, region, weather,
                                                          climatologies):
        result, exclusion = collect_point_percentile(
            "source_zone", "recent", weather["source_zone"],
            climatologies["source_zone"],
        )
        assert exclusion is None
        ref = climatologies["source_zone"]
        # SAME G03A percentile algorithm — no second implementation
        assert result.percentile == percentile_of(ref, 8, 70.0) == 70.5
        assert result.percentile_method == "mean_rank"

    def test_forecast_point_percentile(self, region, weather, climatologies):
        result, _ = collect_point_percentile(
            "port_zone", "forecast", weather["port_zone"],
            climatologies["port_zone"],
        )
        assert result.percentile == percentile_of(climatologies["port_zone"], 8, 90.0)
        assert result.percentile == 90.5
        assert result.cumulative_precip_mm == 90.0

    def test_point_output_fields_complete(self, region, weather, climatologies):
        result, _ = collect_point_percentile(
            "source_zone", "recent", weather["source_zone"],
            climatologies["source_zone"],
        )
        d = result.to_dict()
        assert d["point_id"] == "source_zone"
        assert d["cumulative_precip_mm"] == 70.0
        assert d["climatology_month"] == 8
        assert d["month_assignment"] == "window_end_month"
        assert d["climatology"]["checksum"] == climatologies["source_zone"].checksum
        assert d["climatology"]["algorithm_version"]
        assert d["climatology"]["baseline"] == ["1991-01-01", "2020-12-31"]
        assert d["weather_quality"] == "FRESH"

    def test_month_selection_uses_window_end(self, region, climatologies):
        # retrieval 2026-09-15: recent window ends 09-14 -> month 9
        refs = flat_climatologies(months=(8, 9))
        w = flat_weather(date(2026, 9, 15))
        result, _ = collect_point_percentile(
            "source_zone", "recent", w["source_zone"], refs["source_zone"])
        assert result.window_end == "2026-09-14"
        assert result.climatology_month == 9

    def test_cross_month_forecast_uses_window_end_month(self, region):
        # retrieval 2026-10-28: forecast window 10-28..11-03 -> month 11
        refs = flat_climatologies(months=(10, 11))
        w = flat_weather(date(2026, 10, 28))
        result, _ = collect_point_percentile(
            "port_zone", "forecast", w["port_zone"], refs["port_zone"])
        assert result.window_start == "2026-10-28"
        assert result.window_end == "2026-11-03"
        assert result.climatology_month == 11
        assert result.percentile == percentile_of(refs["port_zone"], 11, 90.0)

    def test_missing_climatology_month_excludes_point(self, region, weather):
        refs = flat_climatologies(months=(9,))  # no month 8 distribution
        _, exclusion = collect_point_percentile(
            "source_zone", "recent", weather["source_zone"], refs["source_zone"])
        assert exclusion.reason == "climatology_month_distribution_missing"

    def test_both_zones_calculated(self, region, weather, climatologies):
        result = run(region, weather, climatologies)
        assert set(result.recent_aggregation.all_point_values) == {
            "source_zone", "port_zone"}
        assert set(result.forecast_aggregation.all_point_values) == {
            "source_zone", "port_zone"}


class TestRegionalAggregation:
    def test_R_is_max_point_recent_percentile(self, region, weather, climatologies):
        result = run(region, weather, climatologies)
        assert result.R == 70.5  # max(70.5 source, 50.5 port)

    def test_F_is_max_point_forecast_percentile(self, region, weather, climatologies):
        result = run(region, weather, climatologies)
        assert result.F == 90.5  # max(30.5 source, 90.5 port)

    def test_driver_point_identity_recorded(self, region, weather, climatologies):
        result = run(region, weather, climatologies)
        assert result.recent_aggregation.driver_point_id == "source_zone"
        assert result.forecast_aggregation.driver_point_id == "port_zone"
        d = result.to_dict()
        assert d["R_driver_point"] == "source_zone"
        assert d["F_driver_point"] == "port_zone"

    def test_all_point_values_never_hidden(self, region, weather, climatologies):
        result = run(region, weather, climatologies)
        d = result.to_dict()
        assert d["R_all_point_values"] == {"source_zone": 70.5, "port_zone": 50.5}
        assert d["F_all_point_values"] == {"source_zone": 30.5, "port_zone": 90.5}

    def test_aggregation_is_conservative_max_not_average(self, region, weather,
                                                         climatologies):
        result = run(region, weather, climatologies)
        mean_recent = (70.5 + 50.5) / 2
        assert result.R == 70.5 != mean_recent
        assert result.recent_aggregation.aggregation_rule == (
            "max_of_successful_points_conservative")

    def test_driver_tie_break_is_first_point_in_config_order(self, region,
                                                             climatologies):
        w = flat_weather(CENTER, source_recent_mm=70.0, port_recent_mm=70.0,
                         source_forecast_mm=30.0, port_forecast_mm=30.0)
        result = run(region, w, climatologies)
        assert result.R == 70.5
        assert result.recent_aggregation.driver_point_id == "source_zone"
        assert result.forecast_aggregation.driver_point_id == "source_zone"


class TestFormulas:
    def test_D_formula_exact(self):
        assert compute_D(70.5, 90.5) == 0.60 * 70.5 + 0.40 * 90.5

    def test_C_formula_exact(self):
        assert compute_C(92.222, 78.5) == 0.70 * 92.222 + 0.30 * 78.5

    def test_O7_formula_exact(self):
        assert compute_O7(92.222, 90.5) == 0.70 * 92.222 + 0.30 * 90.5

    def test_engine_applies_frozen_formulas(self, region, weather, climatologies):
        result = run(region, weather, climatologies)
        B = result.B
        assert result.D == compute_D(result.R, result.F)
        assert result.C == compute_C(B, result.D)
        assert result.O7 == compute_O7(B, result.F)

    def test_bounds_zero(self, exact_region):
        refs = {pid: make_reference(pid, {8: positive_totals()})
                for pid in ("source_zone", "port_zone")}
        w = make_exact_weather(0.0)  # dry windows: percentile exactly 0.0
        result = run(exact_region, w, refs)
        assert result.R == 0.0 and result.F == 0.0
        assert result.D == 0.0
        assert result.C == 0.70 * 80.0
        assert result.O7 == 0.70 * 80.0
        assert 0.0 <= result.C <= 100.0 and 0.0 <= result.O7 <= 100.0

    def test_bounds_hundred(self, exact_region):
        refs = {pid: make_reference(pid, {8: positive_totals()})
                for pid in ("source_zone", "port_zone")}
        w = make_exact_weather(500.0)  # above every historical value
        result = run(exact_region, w, refs)
        assert result.R == 100.0 and result.F == 100.0 and result.D == 100.0
        assert result.C == pytest.approx(0.70 * 80.0 + 30.0)
        assert result.O7 == pytest.approx(0.70 * 80.0 + 30.0)
        assert result.C <= 100.0 and result.O7 <= 100.0

    def test_validate_index_rejects_out_of_range(self):
        for bad in (-0.001, -1.0, 100.001, 101.0, math.nan, math.inf, -math.inf):
            with pytest.raises(RiskFormulaError):
                validate_index(bad, "X")

    def test_D_components_sum_to_D(self, region, weather, climatologies):
        result = run(region, weather, climatologies)
        comp = result.to_dict()["D_components"]
        assert comp["recent_component"] == pytest.approx(0.60 * result.R, abs=0.0)
        assert comp["forecast_component"] == pytest.approx(0.40 * result.F, abs=0.0)
        assert comp["recent_component"] + comp["forecast_component"] == pytest.approx(
            result.D, abs=1e-9)

    def test_C_components_sum_to_C(self, region, weather, climatologies):
        result = run(region, weather, climatologies)
        comp = result.to_dict()["C_components"]
        assert comp["static_component"] + comp["dynamic_component"] == pytest.approx(
            result.C, abs=1e-9)

    def test_O7_components_sum_to_O7(self, region, weather, climatologies):
        result = run(region, weather, climatologies)
        comp = result.to_dict()["O7_components"]
        assert comp["static_component"] + comp["forecast_component"] == pytest.approx(
            result.O7, abs=1e-9)

    def test_full_precision_chain_no_premature_rounding(self, region, weather,
                                                        climatologies):
        result = run(region, weather, climatologies)
        # Recompute the full-precision chain by hand from raw inputs.
        B = sum((f["score_0_to_5"] / 5.0) * f["normalized_weight_pct"]
                for f in [
                    {"score_0_to_5": 4, "normalized_weight_pct": 22.22},
                    {"score_0_to_5": 5, "normalized_weight_pct": 27.78},
                    {"score_0_to_5": 5, "normalized_weight_pct": 22.22},
                    {"score_0_to_5": 4, "normalized_weight_pct": 16.67},
                    {"score_0_to_5": 5, "normalized_weight_pct": 11.11},
                ])
        D = 0.60 * 70.5 + 0.40 * 90.5
        C = 0.70 * B + 0.30 * D
        O7 = 0.70 * B + 0.30 * 90.5
        assert result.B == B
        assert result.D == D
        assert result.C == C
        assert result.O7 == O7
        # unrounded values preserved in the serialized result
        d = result.to_dict()
        assert d["C"] == C and d["C_rounded"] == round(C, 2)


class TestRiskBands:
    @pytest.mark.parametrize(
        "value,band",
        [
            (0, "LOW"), (39, "LOW"), (39.999, "LOW"),
            (40, "MODERATE"), (59.999, "MODERATE"),
            (60, "ELEVATED"), (79.999, "ELEVATED"),
            (80, "HIGH"), (100, "HIGH"),
        ],
    )
    def test_frozen_band_boundaries(self, value, band):
        assert classify_band(float(value)) == band

    @pytest.mark.parametrize(
        "bad", [-0.001, -1, 100.001, 101, math.nan, math.inf, -math.inf, "x", None]
    )
    def test_invalid_values_rejected(self, bad):
        with pytest.raises(RiskFormulaError):
            classify_band(bad)

    def test_band_uses_unrounded_value_not_display(self, region, weather,
                                                   climatologies):
        result = run(region, weather, climatologies)
        # A value whose 2-decimal display crosses a boundary must still be
        # classified with the actual calculated value.
        assert classify_band(39.9996) == "LOW"          # displays as 40.0
        assert classify_band(result.C) == result.current_risk_level
        assert classify_band(result.O7) == result.outlook_7d_level

    def test_engine_levels_are_prototype_bands(self, region, weather, climatologies):
        result = run(region, weather, climatologies)
        assert result.current_risk_level in {"LOW", "MODERATE", "ELEVATED", "HIGH"}
        assert result.outlook_7d_level in {"LOW", "MODERATE", "ELEVATED", "HIGH"}
        blob = result.to_json().lower()
        for statutory in ("蓝色预警", "黄色预警", "橙色预警", "红色预警"):
            assert statutory not in blob


class TestRiskDirection:
    def prev(self, c):
        return PreviousState(
            snapshot_id="prev-1", created_at="2026-08-14T06:00:00+00:00",
            scan_mode="LIVE", current_C=c,
        )

    def test_first_scan_is_no_history(self, region, weather, climatologies):
        result = run(region, weather, climatologies, previous=None)
        assert result.risk_direction == "NO_HISTORY"
        assert result.previous_C is None and result.delta_C is None

    def test_exact_plus_five_is_rising(self, exact_region):
        refs = exact_climatologies()
        w = make_exact_weather()
        result = run(exact_region, w, refs)
        assert result.C == 71.0  # exact binary-friendly fixture
        result = run(exact_region, w, refs, previous=self.prev(66.0))
        assert result.delta_C == 5.0
        assert result.risk_direction == "RISING"

    def test_above_plus_five_is_rising(self, region, weather, climatologies):
        base = run(region, weather, climatologies)
        result = run(region, weather, climatologies,
                     previous=self.prev(base.C - 5.001))
        assert result.risk_direction == "RISING"

    def test_exact_minus_five_is_falling(self, exact_region):
        refs = exact_climatologies()
        w = make_exact_weather()
        base = run(exact_region, w, refs)
        assert base.C == 71.0
        result = run(exact_region, w, refs, previous=self.prev(76.0))
        assert result.delta_C == -5.0
        assert result.risk_direction == "FALLING"

    def test_below_minus_five_is_falling(self, region, weather, climatologies):
        base = run(region, weather, climatologies)
        result = run(region, weather, climatologies,
                     previous=self.prev(base.C + 5.001))
        assert result.risk_direction == "FALLING"

    def test_between_thresholds_is_stable(self, region, weather, climatologies):
        base = run(region, weather, climatologies)
        for delta in (-4.999, -1.0, 0.0, 1.0, 4.999):
            result = run(region, weather, climatologies,
                         previous=self.prev(base.C - delta))
            assert result.risk_direction == "STABLE", delta

    def test_classifier_boundaries_pure(self):
        assert classify_direction(5.0) == "RISING"
        assert classify_direction(5.0000001) == "RISING"
        assert classify_direction(4.9999999) == "STABLE"
        assert classify_direction(0.0) == "STABLE"
        assert classify_direction(-4.9999999) == "STABLE"
        assert classify_direction(-5.0) == "FALLING"
        assert classify_direction(-5.0000001) == "FALLING"

    def test_backfill_previous_is_labeled(self, region, weather, climatologies):
        prev = PreviousState(
            snapshot_id="bf-1", created_at="2026-08-01T00:00:00+00:00",
            scan_mode="BACKFILL", current_C=50.0)
        result = run(region, weather, climatologies, previous=prev)
        assert result.what_changed["previous_scan_mode"] == "BACKFILL"
        assert any("BACKFILL" in lim for lim in result.limitations)


class TestFailureHandling:
    def test_one_point_failed_completes_with_limitations(self, region,
                                                         climatologies):
        w = flat_weather(CENTER)
        w["port_zone"] = PointWeatherFailure(
            point_id="port_zone", error_type="WeatherTimeoutError",
            message="timeout after 15.0s")
        result = run(region, w, climatologies)
        assert result.status == "COMPLETED_WITH_LIMITATIONS"
        assert result.R == 70.5 and result.F == 30.5  # surviving point only
        assert result.recent_aggregation.driver_point_id == "source_zone"
        reasons = {(m["point_id"], m["window_kind"], m["reason"])
                   for m in result.missing_data}
        assert ("port_zone", "recent", "weather_collection_failed") in reasons
        assert ("port_zone", "forecast", "weather_collection_failed") in reasons
        assert any("reduced" in lim for lim in result.limitations)

    def test_all_points_failed_no_official_result(self, region, climatologies):
        w = {
            "source_zone": PointWeatherFailure("source_zone", "E", "boom"),
            "port_zone": PointWeatherFailure("port_zone", "E", "boom"),
        }
        result = run(region, w, climatologies)
        assert result.status == "FAILED"
        assert result.C is None and result.O7 is None and result.D is None
        assert result.R is None and result.F is None
        assert result.current_risk_level is None
        assert result.outlook_7d_level is None
        assert result.risk_direction is None
        assert result.top_drivers == ()
        # Static B remains independently reportable
        assert result.B == pytest.approx(92.222, abs=0.001)
        assert any("UNAVAILABLE" in lim for lim in result.limitations)

    def test_missing_climatology_for_one_point(self, region, weather):
        refs = flat_climatologies(months=(8,))
        del refs["port_zone"]
        result = run(region, weather, refs)
        assert result.status == "COMPLETED_WITH_LIMITATIONS"
        assert result.R == 70.5 and result.F == 30.5
        assert all(m["point_id"] == "port_zone" for m in result.missing_data)
        assert all(m["reason"] == "climatology_reference_unavailable"
                   for m in result.missing_data)

    def test_forecast_side_failure_blocks_official_C_and_O7(self, region,
                                                            climatologies):
        # recent OK for both points, forecast window incomplete for both
        w = {}
        for pid, recent_mm in (("source_zone", 70.0), ("port_zone", 50.0)):
            w[pid] = make_point_weather(
                pid, CENTER, [recent_mm] + [0.0] * 6,
                [None] + [5.0] * 6,  # forecast day missing
            )
        result = run(region, w, climatologies)
        assert result.status == "FAILED"
        assert result.C is None and result.O7 is None
        assert result.recent_aggregation.value == 70.5  # computed but not official C
        assert any("no successful forecast-precipitation point" in lim
                   for lim in result.limitations)

    def test_missing_precip_day_never_zero_filled(self, region, climatologies):
        # 6 wet days (100 mm each) + 1 missing day: an honest total does not
        # exist; the point must be excluded, NOT scored as 600 mm or as 0.
        w = {
            "source_zone": make_point_weather(
                "source_zone", CENTER, [100.0] * 6 + [None], [10.0] * 7),
            "port_zone": make_point_weather(
                "port_zone", CENTER, [10.0] * 7, [10.0] * 7),
        }
        result = run(region, w, climatologies)
        excluded = {m["point_id"] for m in result.missing_data
                    if m["reason"] == "precipitation_window_incomplete"}
        assert excluded == {"source_zone"}
        assert result.recent_aggregation.driver_point_id == "port_zone"
        # port_zone recent cumulative = 7 x 10.0 = 70.0 -> percentile 70.5
        assert result.recent_aggregation.value == 70.5
        detail = [m for m in result.missing_data
                  if m["reason"] == "precipitation_window_incomplete"][0]
        assert "2026-08-14" in detail["detail"]

    def test_missing_values_never_interpreted_as_zero(self, region):
        refs = flat_climatologies(months=(8,))
        w = {
            "source_zone": make_point_weather(
                "source_zone", CENTER, [None] * 7, [None] * 7),
            "port_zone": PointWeatherFailure("port_zone", "E", "down"),
        }
        result = run(region, w, refs)
        assert result.status == "FAILED"
        # If missing had been zero-filled, R/F percentiles would exist (0.5).
        assert result.R is None and result.F is None
        assert result.C is None

    def test_stale_weather_included_with_explicit_limitation(self, region):
        refs = flat_climatologies(months=(8,))
        # recent complete, forecast incomplete -> quality STALE but recent OK
        src = make_point_weather("source_zone", CENTER, [70.0] + [0.0] * 6,
                                 [None] + [0.0] * 6)
        w = {"source_zone": src,
             "port_zone": make_point_weather(
                 "port_zone", CENTER, [50.0] + [0.0] * 6, [20.0] + [0.0] * 6)}
        assert src.quality == "STALE"
        result = run(region, w, refs)
        assert result.recent_aggregation.value == 70.5
        recent_src = result.recent_aggregation.point_percentiles[0]
        assert any("weather_quality_stale" in lim for lim in recent_src.limitations)

    def test_optional_evidence_missing_does_not_affect_numbers(self, region,
                                                               weather,
                                                               climatologies):
        base = run(region, weather, climatologies)
        with_optional = run(region, weather, climatologies,
                            optional_evidence=[
                                {"evidence_id": "sentinel2_scene", "cloud_pct": 12},
                                "soil_moisture",
                            ])
        assert (base.B, base.R, base.F, base.D, base.C, base.O7) == (
            with_optional.B, with_optional.R, with_optional.F,
            with_optional.D, with_optional.C, with_optional.O7)
        assert with_optional.optional_evidence_availability == (
            "sentinel2_scene", "soil_moisture")
        assert base.optional_evidence_availability == ()


class TestScientificSeparation:
    def test_temperature_never_changes_numeric_outputs(self, region,
                                                       climatologies):
        warm = {
            pid: make_point_weather(pid, CENTER, [70.0 if pid == "source_zone"
                                                  else 50.0] + [0.0] * 6,
                                    [30.0 if pid == "source_zone"
                                     else 90.0] + [0.0] * 6,
                                    tmax=35.0, tmin=20.0)
            for pid in ("source_zone", "port_zone")
        }
        cold = {
            pid: make_point_weather(pid, CENTER, [70.0 if pid == "source_zone"
                                                  else 50.0] + [0.0] * 6,
                                    [30.0 if pid == "source_zone"
                                     else 90.0] + [0.0] * 6,
                                    tmax=-25.0, tmin=-40.0)
            for pid in ("source_zone", "port_zone")
        }
        r_warm = run(region, warm, climatologies)
        r_cold = run(region, cold, climatologies)
        for attr in ("B", "R", "F", "D", "C", "O7", "current_risk_level",
                     "outlook_7d_level"):
            assert getattr(r_warm, attr) == getattr(r_cold, attr), attr

    def test_no_probability_semantics_in_schema(self, region, weather,
                                                climatologies):
        result = run(region, weather, climatologies)
        blob = result.to_dict()

        def keys(obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    yield str(k)
                    yield from keys(v)
            elif isinstance(obj, list):
                for item in obj:
                    yield from keys(item)

        assert not any("probability" in k.lower() for k in keys(blob))
        assert "NOT a disaster occurrence" in result.semantics or \
               "not a disaster occurrence" in result.semantics.lower()

    def test_result_is_not_called_warning_level(self, region, weather,
                                                climatologies):
        result = run(region, weather, climatologies)
        assert "official warning level" in result.semantics.lower() or \
               "NOT an official warning level" in result.semantics


class TestDeterminismAndNoAI:
    def test_identical_input_repeated_is_identical(self, region, weather,
                                                   climatologies):
        runs = [run(region, weather, climatologies) for _ in range(3)]
        serialized = [r.to_json() for r in runs]
        assert serialized[0] == serialized[1] == serialized[2]
        for attr in ("B", "R", "F", "D", "C", "O7", "current_risk_level",
                     "outlook_7d_level", "risk_direction"):
            values = [getattr(r, attr) for r in runs]
            assert values[0] == values[1] == values[2], attr
        assert [d.to_dict() for d in runs[0].top_drivers] == \
               [d.to_dict() for d in runs[1].top_drivers]

    def test_works_without_deepseek_key_and_with_sockets_blocked(
            self, region, weather, climatologies, monkeypatch):
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        import socket

        def deny(*args, **kwargs):
            raise AssertionError("G03B deterministic engine must not open sockets")

        monkeypatch.setattr(socket, "create_connection", deny)
        monkeypatch.setattr(socket, "socket", deny)
        monkeypatch.setattr(socket, "getaddrinfo", deny)
        result = run(region, weather, climatologies)
        assert result.status.startswith("COMPLETED")
        assert result.C is not None

    def test_no_time_dependence_in_pure_calculation(self, region, weather,
                                                    climatologies):
        # Same inputs, different wall-clock moments between calls (the engine
        # never reads the clock): results must still be byte-identical.
        import time

        first = run(region, weather, climatologies).to_json()
        time.sleep(0.01)
        second = run(region, weather, climatologies).to_json()
        assert first == second

    def test_versions_exposed(self, region, weather, climatologies):
        result = run(region, weather, climatologies)
        assert result.algorithm_version == ALGORITHM_VERSION
        assert result.formula_version == FORMULA_VERSION
        d = result.to_dict()
        assert d["provenance"]["region_config_version"]
        assert d["provenance"]["scoring_config_version"] == (
            "risk-watch-static-v1.0-5factors")
        assert d["provenance"]["static_baseline_derivation_algorithm"]
        assert d["numeric_method"]["percentile_method"].startswith("mean_rank")


class TestResultSchema:
    def test_required_result_fields_present(self, region, weather, climatologies):
        d = run(region, weather, climatologies).to_dict()
        required = [
            "algorithm_version", "formula_version", "region_id", "run_id",
            "status", "B", "point_recent_percentiles", "R", "R_driver_point",
            "R_all_point_values", "point_forecast_percentiles", "F",
            "F_driver_point", "F_all_point_values", "D", "C",
            "current_risk_level", "O7", "outlook_7d_level", "risk_direction",
            "previous_C", "delta_C", "top_drivers", "what_changed",
            "missing_data", "limitations", "provenance", "numeric_method",
        ]
        for key in required:
            assert key in d, key

    def test_doc04_snapshot_field_names_present(self, region, weather,
                                                climatologies):
        d = run(region, weather, climatologies).to_dict()
        # doc 04 §30 canonical snapshot field names
        for key in ("recent_precip_percentile", "forecast_precip_percentile",
                    "dynamic_trigger_index", "current_risk_index",
                    "current_risk_level", "outlook_7d_index",
                    "outlook_7d_level", "risk_direction", "static_baseline"):
            assert key in d, key
        assert d["current_risk_index"] == d["C"]
        assert d["dynamic_trigger_index"] == d["D"]
        assert d["outlook_7d_index"] == d["O7"]

    def test_serialization_is_stable_json(self, region, weather, climatologies):
        result = run(region, weather, climatologies)
        s1 = json.dumps(result.to_dict(), sort_keys=True)
        s2 = json.dumps(result.to_dict(), sort_keys=True)
        assert s1 == s2
        assert result.to_json() == json.dumps(
            result.to_dict(), ensure_ascii=False, sort_keys=True)

    def test_no_llm_narrative_fields(self, region, weather, climatologies):
        d = run(region, weather, climatologies).to_dict()
        blob = json.dumps(d).lower()
        for forbidden in ("llm_summary", "agent_output", "synthesizer",
                          "critic", "narrative"):
            assert forbidden not in blob
