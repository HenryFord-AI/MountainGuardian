"""G03A – region.json schema, monitoring points, provenance, no post-event."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from riskwatch.region import (  # noqa: E402
    REGIONS_DIR,
    RegionConfigError,
    load_region,
)
from tests.g03a_helpers import post_event_case_keys, walk_keys  # noqa: E402

REGION_PATH = REGIONS_DIR / "jilong_port" / "region.json"


class TestRegionSchema:
    def test_region_file_exists_and_is_tracked_data(self):
        assert REGION_PATH.is_file()

    def test_loads_with_expected_identity(self):
        region = load_region()
        assert region.region_id == "jilong_port"
        assert region.schema_version == "1.0"
        assert region.config_version
        assert region.scoring_config_version == "risk-watch-static-v1.0-5factors"

    def test_source_zone_exists(self):
        region = load_region()
        point = region.point("source_zone")
        assert point.latitude == pytest.approx(28.28, abs=0.05)
        assert point.longitude == pytest.approx(85.481, abs=0.05)
        assert point.elevation_m == pytest.approx(5200, abs=1)

    def test_port_zone_exists(self):
        region = load_region()
        point = region.point("port_zone")
        assert point.latitude == pytest.approx(28.279, abs=1e-9)
        assert point.longitude == pytest.approx(85.379, abs=1e-9)
        assert point.elevation_m == pytest.approx(1800, abs=1)

    def test_exactly_the_two_frozen_p0_points(self):
        region = load_region()
        assert {p.point_id for p in region.monitoring_points} == {
            "source_zone",
            "port_zone",
        }

    def test_climatology_baseline_frozen_period(self):
        region = load_region()
        assert region.climatology_baseline == ("1991-01-01", "2020-12-31")


class TestCoordinateProvenance:
    def test_every_point_has_full_provenance(self):
        region = load_region()
        for point in region.monitoring_points:
            prov = point.coordinate_provenance
            assert prov.get("type") in {"representative", "representative_derived"}
            assert prov.get("exact") is False  # nothing pretends to be surveyed
            assert prov.get("meaning")
            assert "uncertainty_km" in prov
            assert prov.get("reference") or prov.get("anchor")
            if "anchor" in prov:
                assert prov.get("method")  # derived coords must state method
            assert prov.get("source_ids")

    def test_port_coordinate_matches_traceable_case_pack_fields(self):
        region = load_region()
        prov = region.point("port_zone").coordinate_provenance
        assert "C004" in prov["reference"] and "C005" in prov["reference"]
        assert "S09" in prov["source_ids"]

    def test_source_coordinate_anchor_and_method_documented(self):
        region = load_region()
        prov = region.point("source_zone").coordinate_provenance
        assert prov["anchor"]["value"] == [28.279, 85.379]
        assert "04_disaster_path_official.jpg" in prov["method"]
        assert prov["uncertainty_km"] >= 1.0

    def test_no_invented_coordinate_path_in_loader(self):
        # The loader refuses configs whose points lack provenance entirely.
        bad = {
            "schema_version": "1.0",
            "config_version": "x",
            "region_id": "bad",
            "region_name": "bad",
            "monitoring_points": [
                {"point_id": "a", "name": "a", "latitude": 1, "longitude": 2},
                {"point_id": "b", "name": "b", "latitude": 1, "longitude": 2},
            ],
            "static_terrain_baseline": {},
            "cryosphere_baseline": {},
            "historical_hazard_baseline": {},
            "static_susceptibility_inputs": {"factors": [], "scoring_config_version": "x"},
            "source_references": [],
            "provenance": {},
            "scientific_limitations": [],
        }
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            rdir = Path(td) / "bad"
            rdir.mkdir(parents=True)
            (rdir / "region.json").write_text(json.dumps(bad), encoding="utf-8")
            with pytest.raises(RegionConfigError):
                load_region("bad", regions_dir=Path(td))


class TestStaticBaselineAndWeights:
    def test_five_retained_factors_with_frozen_normalized_weights(self):
        region = load_region()
        factors = region.data["static_susceptibility_inputs"]["factors"]
        assert [f["factor_id"] for f in factors] == ["R1", "R2", "R3", "R4", "R6"]
        weights = [f["normalized_weight_pct"] for f in factors]
        assert weights == pytest.approx([22.22, 27.78, 22.22, 16.67, 11.11], abs=0.01)

    def test_monsoon_factor_excluded_to_avoid_double_counting(self):
        region = load_region()
        ssi = region.data["static_susceptibility_inputs"]
        assert [f["factor_id"] for f in ssi["excluded_factors"]] == ["R5"]
        assert all(f["factor_id"] != "R5" for f in ssi["factors"])

    def test_no_derived_b_stored(self):
        region = load_region()
        keys = walk_keys(region.data["static_susceptibility_inputs"])
        assert not any(k.lower() in {"b", "baseline_index", "static_baseline_value"} for k in keys)
        assert "derivation_boundary" in region.data["static_susceptibility_inputs"]

    def test_static_baselines_present(self):
        region = load_region()
        assert region.data["static_terrain_baseline"]["vertical_drop_m"] == 3400
        assert region.data["cryosphere_baseline"]["glacierized_source_zone"] is True
        assert region.data["historical_hazard_baseline"]["prior_event_date"] == "2025-07-08"
        assert region.data["source_references"]
        assert region.data["scientific_limitations"]


class TestNoPostEventContent:
    def test_region_config_has_no_post_event_keys(self):
        data = json.loads(REGION_PATH.read_text(encoding="utf-8"))
        forbidden = post_event_case_keys()
        present = walk_keys(data) & forbidden
        assert not present

    def test_region_config_has_no_post_event_marker_strings(self):
        text = REGION_PATH.read_text(encoding="utf-8")
        for marker in (
            "actual_runout",
            "actual_travel_time",
            "actual_avg_speed",
            "actual_structures_destroyed",
            "actual_disaster_chain",
            "actual_trigger",
            "source_fracture_time_later_report",
        ):
            assert marker not in text

    def test_region_config_is_not_a_copy_of_case_pack(self):
        case = json.loads(
            (REGIONS_DIR.parent.parent / "data" / "cases" / "jilong_20260826" / "case.json")
            .read_text(encoding="utf-8")
        )
        region = json.loads(REGION_PATH.read_text(encoding="utf-8"))
        assert "data_fields" not in region
        assert "demo_risk_model" not in region
        assert "agent_mapping" not in region
        # post-event case values (runout 22 km, 27 structures, 6-7 min...)
        # must not appear anywhere in the region config values
        region_text = REGION_PATH.read_text(encoding="utf-8")
        assert '"value": 22,' not in region_text
        case_post_values = {
            f["value"]
            for f in case["data_fields"]
            if f.get("phase") == "post_event_validation"
        }
        region_values = set()

        def collect(obj):
            if isinstance(obj, dict):
                for v in obj.values():
                    collect(v)
            elif isinstance(obj, list):
                for v in obj:
                    collect(v)
            else:
                region_values.add(obj)

        collect(region)
        assert not (region_values & case_post_values)
