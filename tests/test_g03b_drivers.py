"""G03B – Top Risk Driver contribution objects (items 55-62).

Deterministic, traceable decomposition of C and O7; descending order with a
stable tie-break; contributions must sum to the respective index.
"""

from __future__ import annotations

import copy
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from riskwatch.engine import (  # noqa: E402
    build_current_risk_drivers,
    build_outlook_drivers,
    compute_risk_watch,
    contribution_sum,
    sums_to_index,
)
from tests.g03b_helpers import (  # noqa: E402
    DEFAULT_FACTORS,
    direct_region,
    flat_climatologies,
    flat_weather,
    write_region,
)

CENTER = date(2026, 8, 15)


@pytest.fixture()
def result(tmp_path):
    region = write_region(tmp_path)
    return compute_risk_watch(
        region, flat_weather(CENTER), flat_climatologies(months=(8,)),
        run_id="drivers-test",
    )


class TestStaticDrivers:
    def test_static_contribution_objects_exist(self, result):
        static = [d for d in result.top_drivers if d.driver_type == "STATIC"]
        assert {d.driver_id for d in static} == {
            "static:R1", "static:R2", "static:R3", "static:R4", "static:R6"}

    def test_static_contribution_is_seventy_percent_of_b_contribution(self,
                                                                      result):
        for d in result.top_drivers:
            if d.driver_type != "STATIC":
                continue
            b_contrib = d.provenance["b_contribution"]
            assert d.contribution_points == pytest.approx(0.70 * b_contrib, abs=0.0)
            assert d.raw_value_kind == "score_0_to_5"
            # coefficient x raw score reproduces the contribution
            assert d.weight_or_coefficient * d.raw_value == pytest.approx(
                d.contribution_points, abs=1e-12)

    def test_static_drivers_traceable_to_region_json(self, result):
        for d in result.top_drivers:
            if d.driver_type != "STATIC":
                continue
            prov = d.provenance
            assert prov["source"] == "region.json static_susceptibility_inputs"
            assert prov["source_ids"], d.driver_id
            assert prov["region_config_version"]
            assert prov["scoring_config_version"] == (
                "risk-watch-static-v1.0-5factors")
            assert prov["factor_id"] == d.driver_id.split(":", 1)[1]


class TestDynamicDrivers:
    def test_recent_precipitation_contribution(self, result):
        d = next(x for x in result.top_drivers
                 if x.driver_id == "dynamic:recent_precipitation")
        assert d.driver_type == "DYNAMIC"
        assert d.raw_value == result.R
        assert d.contribution_points == pytest.approx(0.30 * 0.60 * result.R,
                                                      abs=0.0)
        assert d.contribution_points == pytest.approx(0.18 * result.R, abs=1e-12)
        assert d.monitoring_point_id == "source_zone"  # R driver point

    def test_forecast_precipitation_contribution(self, result):
        d = next(x for x in result.top_drivers
                 if x.driver_id == "dynamic:forecast_precipitation")
        assert d.raw_value == result.F
        assert d.contribution_points == pytest.approx(0.30 * 0.40 * result.F,
                                                      abs=0.0)
        assert d.monitoring_point_id == "port_zone"  # F driver point

    def test_dynamic_driver_provenance(self, result):
        for did in ("dynamic:recent_precipitation",
                    "dynamic:forecast_precipitation"):
            d = next(x for x in result.top_drivers if x.driver_id == did)
            prov = d.provenance
            assert prov["driver_point_id"] == d.monitoring_point_id
            assert prov["climatology_checksum"]
            assert prov["climatology_algorithm_version"]
            assert prov["climatology_baseline"] == ["1991-01-01", "2020-12-31"]
            assert prov["percentile_method"] == "mean_rank"
            assert set(prov["all_point_percentiles"]) == {
                "source_zone", "port_zone"}


class TestContributionSums:
    def test_current_risk_contributions_sum_to_C(self, result):
        assert sums_to_index(result.top_drivers, result.C, 1e-9)
        assert contribution_sum(result.top_drivers) == pytest.approx(
            result.C, abs=1e-9)

    def test_outlook_contributions_sum_to_O7(self, result):
        assert sums_to_index(result.outlook_drivers, result.O7, 1e-9)
        static = [d for d in result.outlook_drivers if d.driver_type == "STATIC"]
        forecast = [d for d in result.outlook_drivers if d.driver_type == "DYNAMIC"]
        assert len(forecast) == 1
        assert forecast[0].contribution_points == pytest.approx(
            0.30 * result.F, abs=0.0)
        for d in static:
            assert d.contribution_points == pytest.approx(
                0.70 * d.provenance["b_contribution"], abs=0.0)

    def test_outlook_has_no_recent_driver(self, result):
        ids = {d.driver_id for d in result.outlook_drivers}
        assert "dynamic:recent_precipitation" not in ids
        assert "dynamic:forecast_precipitation" in ids


class TestOrdering:
    def test_sorted_descending_by_contribution(self, result):
        points = [d.contribution_points for d in result.top_drivers]
        assert points == sorted(points, reverse=True)
        points7 = [d.contribution_points for d in result.outlook_drivers]
        assert points7 == sorted(points7, reverse=True)

    def test_stable_tie_break_on_driver_id(self):
        # Two static factors with identical contributions plus identical
        # dynamic contributions: order must be deterministic by driver_id.
        factors = copy.deepcopy(DEFAULT_FACTORS)
        for f in factors:
            f["score_0_to_5"] = 4
            f["original_weight_pct"] = 16
            f["normalized_weight_pct"] = 20.0
        factors[0]["factor_id"] = "Z9"
        factors[1]["factor_id"] = "A1"
        region = direct_region(factors=factors, original_weight_ratio=None)
        from riskwatch.engine.static_baseline import compute_static_baseline

        baseline = compute_static_baseline(region)
        from riskwatch.engine.core import RegionalAggregation

        agg = RegionalAggregation(
            kind="recent", index_name="R", value=50.0,
            driver_point_id=None, point_percentiles=(), exclusions=())
        agg_f = RegionalAggregation(
            kind="forecast", index_name="F", value=50.0,
            driver_point_id=None, point_percentiles=(), exclusions=())
        drivers = build_current_risk_drivers(baseline, 50.0, 50.0, agg, agg_f)
        tied = [d for d in drivers
                if d.contribution_points == pytest.approx(0.70 * 16.0)]
        # all five static contributions are equal -> driver_id ascending
        static_order = [d.driver_id for d in drivers if d.driver_type == "STATIC"]
        assert static_order == sorted(static_order)
        assert "static:A1" in static_order and "static:Z9" in static_order
        assert tied  # sanity: ties really occurred

    def test_ordering_deterministic_across_runs(self, tmp_path):
        region = write_region(tmp_path)
        runs = [
            compute_risk_watch(region, flat_weather(CENTER),
                               flat_climatologies(months=(8,)), run_id="x")
            for _ in range(3)
        ]
        orders = [[d.driver_id for d in r.top_drivers] for r in runs]
        assert orders[0] == orders[1] == orders[2]


class TestNoLLMRanking:
    def test_drivers_are_pure_function_of_inputs(self, tmp_path):
        region = write_region(tmp_path)
        weather = flat_weather(CENTER)
        refs = flat_climatologies(months=(8,))
        r1 = compute_risk_watch(region, weather, refs, run_id="x")
        r2 = compute_risk_watch(region, weather, refs, run_id="x")
        assert [d.to_dict() for d in r1.top_drivers] == \
               [d.to_dict() for d in r2.top_drivers]
        assert [d.to_dict() for d in r1.outlook_drivers] == \
               [d.to_dict() for d in r2.outlook_drivers]
