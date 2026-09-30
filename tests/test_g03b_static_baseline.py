"""G03B – Regional Static Susceptibility Baseline B (items 1-7).

Covers: five authorized factors, R5 exclusion, normalized weights,
deterministic B derivation, no Historical Replay 91 shortcut, stored derived
B verification, contribution sum integrity.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from riskwatch.engine.formulas import ALGORITHM_VERSION  # noqa: E402
from riskwatch.engine.static_baseline import (  # noqa: E402
    DERIVED_SECTION_KEY,
    STATIC_BASELINE_ALGORITHM,
    StaticBaselineError,
    StaticBaselineValidationError,
    compute_static_baseline,
    derive_static_baseline_section,
    verify_stored_baseline,
)
from riskwatch.region import REGIONS_DIR, load_region  # noqa: E402
from tests.g03b_helpers import (  # noqa: E402
    DEFAULT_FACTORS,
    direct_region,
    write_region,
)


@pytest.fixture(scope="module")
def real_region():
    return load_region()


@pytest.fixture()
def test_region(tmp_path):
    return write_region(tmp_path)


class TestFactorInputs:
    def test_loads_five_authorized_factors(self, real_region):
        baseline = compute_static_baseline(real_region)
        assert [f.factor_id for f in baseline.factors] == [
            "R1", "R2", "R3", "R4", "R6",
        ]
        assert [f.score_0_to_5 for f in baseline.factors] == [4, 5, 5, 4, 5]

    def test_r5_excluded_from_static_baseline(self, real_region):
        baseline = compute_static_baseline(real_region)
        assert "R5" in baseline.excluded_factor_ids
        assert all(f.factor_id != "R5" for f in baseline.factors)

    def test_region_containing_r5_among_factors_is_rejected(self):
        factors = copy.deepcopy(DEFAULT_FACTORS)
        factors.append({
            "factor_id": "R5", "key": "monsoon", "name": "Monsoon background",
            "score_0_to_5": 4, "original_weight_pct": 10,
            "normalized_weight_pct": 10.0, "source_ids": ["S01"],
        })
        region = direct_region(factors=factors, original_weight_ratio=None)
        with pytest.raises(StaticBaselineError, match="R5"):
            compute_static_baseline(region)

    def test_missing_r5_exclusion_record_is_rejected(self):
        region = direct_region(excluded=[])
        with pytest.raises(StaticBaselineError, match="R5"):
            compute_static_baseline(region)

    def test_normalized_weights_are_frozen_values(self, real_region):
        baseline = compute_static_baseline(real_region)
        weights = {f.factor_id: f.normalized_weight_pct for f in baseline.factors}
        assert weights == pytest.approx(
            {"R1": 22.22, "R2": 27.78, "R3": 22.22, "R4": 16.67, "R6": 11.11},
            abs=1e-9,
        )
        assert sum(weights.values()) == pytest.approx(100.0, abs=0.05)

    def test_normalized_weights_must_match_frozen_renormalization(self):
        factors = copy.deepcopy(DEFAULT_FACTORS)
        factors[0]["normalized_weight_pct"] = 40.0  # inconsistent with 20/90
        region = direct_region(factors=factors)
        with pytest.raises(StaticBaselineError, match="renormalization"):
            compute_static_baseline(region)

    def test_declared_original_ratio_contradiction_is_rejected(self):
        region = direct_region(original_weight_ratio="10 : 10 : 10 : 10 : 10")
        with pytest.raises(StaticBaselineError, match="frozen ratio"):
            compute_static_baseline(region)

    def test_score_out_of_frozen_range_is_rejected(self):
        factors = copy.deepcopy(DEFAULT_FACTORS)
        factors[1]["score_0_to_5"] = 6
        with pytest.raises(StaticBaselineError, match="0-5"):
            compute_static_baseline(direct_region(factors=factors))
        factors[1]["score_0_to_5"] = -1
        with pytest.raises(StaticBaselineError, match="0-5"):
            compute_static_baseline(direct_region(factors=factors))


class TestBaselineDerivation:
    def test_factor_contribution_formula(self, test_region):
        baseline = compute_static_baseline(test_region)
        for f in baseline.factors:
            expected = (f.score_0_to_5 / 5.0) * f.normalized_weight_pct
            assert f.contribution == pytest.approx(expected, abs=0.0)

    def test_contribution_sum_equals_b(self, test_region):
        baseline = compute_static_baseline(test_region)
        assert sum(f.contribution for f in baseline.factors) == baseline.value

    def test_b_derived_value_matches_authorized_inputs(self, real_region):
        baseline = compute_static_baseline(real_region)
        inputs = real_region.data["static_susceptibility_inputs"]["factors"]
        expected = sum(
            (f["score_0_to_5"] / 5.0) * f["normalized_weight_pct"] for f in inputs
        )
        assert baseline.value == pytest.approx(expected, abs=0.0)
        # Commander sanity expectation (~92.22) — derived, never hard-coded
        # into the engine: it emerges from the frozen region.json inputs.
        assert baseline.value == pytest.approx(92.22, abs=0.005)
        assert baseline.value_rounded == 92.22

    def test_b_is_not_historical_replay_91_shortcut(self, real_region):
        baseline = compute_static_baseline(real_region)
        assert baseline.value != 91.0
        assert baseline.value_rounded != 91.0

    def test_b_is_deterministic_across_repeated_calls(self, real_region):
        runs = [compute_static_baseline(real_region) for _ in range(3)]
        assert [r.value for r in runs] == [runs[0].value] * 3
        assert [r.to_dict() for r in runs] == [runs[0].to_dict()] * 3

    def test_b_full_precision_no_intermediate_rounding(self, test_region):
        baseline = compute_static_baseline(test_region)
        # Unrounded sum of exact factor contributions (92.22200000000001 for
        # the frozen inputs) must be preserved internally; only the display
        # value is rounded to 2 decimals.
        exact = sum(
            (f["score_0_to_5"] / 5.0) * f["normalized_weight_pct"]
            for f in DEFAULT_FACTORS
        )
        assert baseline.value == exact
        assert baseline.value_rounded == round(exact, 2)

    def test_bounded_zero_to_hundred(self):
        factors = copy.deepcopy(DEFAULT_FACTORS)
        for f in factors:
            f["score_0_to_5"] = 0
        baseline = compute_static_baseline(direct_region(factors=factors))
        assert baseline.value == 0.0
        for f in factors:
            f["score_0_to_5"] = 5
        baseline = compute_static_baseline(direct_region(factors=factors))
        assert baseline.value == pytest.approx(100.0, abs=0.05)

    def test_versions_recorded(self, test_region):
        baseline = compute_static_baseline(test_region)
        assert baseline.derivation_algorithm == STATIC_BASELINE_ALGORITHM
        assert baseline.risk_engine_algorithm_version == ALGORITHM_VERSION
        assert baseline.scoring_config_version == "risk-watch-static-v1.0-5factors"


class TestStoredDerivedSection:
    def test_real_region_json_contains_derived_section(self, real_region):
        derived = real_region.data[DERIVED_SECTION_KEY]
        assert derived["status"] == "DERIVED"
        assert derived["risk_engine_algorithm_version"] == ALGORITHM_VERSION
        assert derived["scoring_config_version"] == "risk-watch-static-v1.0-5factors"
        assert derived["source_factor_ids"] == ["R1", "R2", "R3", "R4", "R6"]
        assert "generated_from" in derived

    def test_stored_b_matches_recomputed(self, real_region):
        baseline = verify_stored_baseline(real_region)
        derived = real_region.data[DERIVED_SECTION_KEY]
        assert derived["value_full_precision"] == pytest.approx(
            baseline.value, abs=1e-9)
        assert derived["regional_static_susceptibility_baseline"] == pytest.approx(
            baseline.value_rounded, abs=1e-9)
        assert baseline.stored_derived_match is True

    def test_stored_factor_contributions_match_recomputation(self, real_region):
        baseline = compute_static_baseline(real_region)
        stored = {
            f["factor_id"]: f["contribution"]
            for f in real_region.data[DERIVED_SECTION_KEY]["factor_contributions"]
        }
        for f in baseline.factors:
            assert stored[f.factor_id] == pytest.approx(f.contribution, abs=1e-9)
        assert sum(stored.values()) == pytest.approx(baseline.value, abs=1e-6)

    def test_derived_section_states_semantics(self, real_region):
        semantics = real_region.data[DERIVED_SECTION_KEY]["semantics"]
        assert "NOT the Current Risk Index" in semantics
        assert "probability" in semantics.lower()
        assert "91" in semantics

    def test_tampered_stored_b_fails_validation(self):
        derived = {
            "status": "DERIVED",
            "regional_static_susceptibility_baseline": 95.0,
            "value_full_precision": 95.0,
            "scoring_config_version": "risk-watch-static-v1.0-5factors",
            "source_factor_ids": ["R1", "R2", "R3", "R4", "R6"],
            "factor_contributions": [
                {"factor_id": f["factor_id"], "contribution": 19.0}
                for f in DEFAULT_FACTORS
            ],
        }
        region = direct_region(derived=derived)
        with pytest.raises(StaticBaselineValidationError, match="tampered"):
            compute_static_baseline(region)

    def test_missing_derived_section_fails_strict_verify(self, test_region):
        with pytest.raises(StaticBaselineValidationError, match="missing"):
            verify_stored_baseline(test_region)
        # But ordinary computation still works and records the absence.
        baseline = compute_static_baseline(test_region)
        assert baseline.stored_derived_match is None

    def test_stored_factor_contribution_mismatch_fails(self, real_region):
        data = copy.deepcopy(real_region.data)
        data[DERIVED_SECTION_KEY]["factor_contributions"][0]["contribution"] = 1.0
        from riskwatch.region import RegionConfig

        region = RegionConfig(region_id=data["region_id"], data=data,
                              path=real_region.path)
        with pytest.raises(StaticBaselineValidationError, match="R1"):
            compute_static_baseline(region)

    def test_section_generation_is_reproducible(self, real_region):
        baseline = compute_static_baseline(real_region)
        stored = real_region.data[DERIVED_SECTION_KEY]
        regenerated = derive_static_baseline_section(
            baseline, generated_at=stored["generated_at"]
        )
        # Same authorized inputs -> same derived section, key for key.
        for key, value in regenerated.items():
            if key == "notice":
                continue
            assert stored.get(key) == value, key


class TestRegionFileIntegrity:
    def test_source_inputs_untouched_by_derived_section(self):
        text = (REGIONS_DIR / "jilong_port" / "region.json").read_text(
            encoding="utf-8")
        data = json.loads(text)
        ssi = data["static_susceptibility_inputs"]
        assert [f["score_0_to_5"] for f in ssi["factors"]] == [4, 5, 5, 4, 5]
        assert ssi["original_weight_ratio"] == "20 : 25 : 20 : 15 : 10"
        assert ssi["derivation_boundary"].startswith(
            "No B / R / F / D / C / O7 value is stored or computed in G03A.")
        assert len(data["source_references"]) == 6
        assert data["provenance"]["prepared_by"].startswith("MountainGuardian G03A")
