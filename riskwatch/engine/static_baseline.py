"""
MountainGuardian G03B – Regional Static Susceptibility Baseline (B).

B is derived deterministically from the five authorized static factors frozen
in ``data/regions/<region_id>/region.json`` (``static_susceptibility_inputs``).
Factor R5 (monsoon / high-precipitation background) is excluded to prevent
double counting with the dynamic precipitation trigger (doc 04 §13).

Frozen derivation (doc 04 §13, G03B gate contract):

    factor_contribution = (score_0_to_5 / 5.0) x normalized_weight_pct
    B                   = sum(factor_contribution over the five factors)

Rules enforced here:
  * B is NEVER hard-coded and NEVER copied from the Historical Replay
    Baseline Susceptibility Index (91); it is recomputed from region.json on
    every call;
  * full float precision internally — no intermediate rounding;
  * if region.json carries the DERIVED section required by doc 04, the engine
    verifies the stored value against the recomputation within an explicit
    numerical tolerance and fails validation on any mismatch;
  * this module never reads the Historical Replay Case Pack.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from riskwatch.engine.formulas import (
    ALGORITHM_VERSION,
    DISPLAY_DECIMALS,
    ROUNDING_POLICY,
    round_display,
    validate_index,
)
from riskwatch.region import RegionConfig

#: Key of the DERIVED section stored in region.json (doc 04 §13 requirement
#: that the final derived B is reproducibly available in the region config).
DERIVED_SECTION_KEY = "derived_static_baseline"

#: Version of this derivation algorithm (independent of the engine version).
STATIC_BASELINE_ALGORITHM = "static-baseline-derivation-v1.0"

#: The frozen excluded factor (doc 04 §13: prevent double counting).
EXCLUDED_FACTOR_ID = "R5"

MAX_FACTOR_SCORE = 5.0

#: Explicit numerical tolerances for stored-vs-recomputed validation.
STORED_FULL_PRECISION_TOLERANCE = 1e-6
STORED_ROUNDED_TOLERANCE = 0.005
FACTOR_CONTRIBUTION_TOLERANCE = 1e-6
#: Stored normalized weights must match the frozen renormalization of the
#: original weights (original / sum(originals) * 100) within this tolerance.
NORMALIZED_WEIGHT_TOLERANCE = 0.01
WEIGHT_SUM_TOLERANCE = 0.05

B_SEMANTICS = (
    "B is the Regional Static Susceptibility Baseline (0-100): the static "
    "long-term hazard background of the region derived from the five "
    "authorized static factors. It is NOT the Current Risk Index, NOT a "
    "disaster probability and NOT the Historical Replay Baseline "
    "Susceptibility Index (91)."
)


class StaticBaselineError(ValueError):
    """Static susceptibility inputs violate the frozen contract."""


class StaticBaselineValidationError(StaticBaselineError):
    """The stored DERIVED section does not match the deterministic recomputation."""


@dataclass(frozen=True)
class StaticFactorContribution:
    """One authorized static factor's full-precision contribution to B."""

    factor_id: str
    key: str
    name: str
    score_0_to_5: float
    original_weight_pct: float
    normalized_weight_pct: float
    contribution: float  # full precision, never rounded here
    source_ids: tuple

    def to_dict(self) -> dict[str, Any]:
        return {
            "factor_id": self.factor_id,
            "key": self.key,
            "name": self.name,
            "score_0_to_5": self.score_0_to_5,
            "original_weight_pct": self.original_weight_pct,
            "normalized_weight_pct": self.normalized_weight_pct,
            "contribution": self.contribution,
            "contribution_rounded": round_display(self.contribution),
            "source_ids": list(self.source_ids),
        }


@dataclass(frozen=True)
class StaticBaseline:
    """Deterministic Regional Static Susceptibility Baseline result."""

    region_id: str
    value: float                     # B, full precision
    value_rounded: float             # display value, 2 decimals
    factors: tuple                   # tuple[StaticFactorContribution, ...]
    excluded_factor_ids: tuple
    scoring_config_version: str
    region_config_version: str
    derivation_algorithm: str
    risk_engine_algorithm_version: str
    stored_derived_match: Optional[bool]  # None = no DERIVED section present
    rounding_policy: str = ROUNDING_POLICY
    semantics: str = B_SEMANTICS

    @property
    def B(self) -> float:
        return self.value

    def to_dict(self) -> dict[str, Any]:
        return {
            "regional_static_susceptibility_baseline": self.value_rounded,
            "value_full_precision": self.value,
            "derivation": (
                "B = sum over retained static factors of "
                "(score_0_to_5 / 5.0) * normalized_weight_pct"
            ),
            "factor_contributions": [f.to_dict() for f in self.factors],
            "excluded_factor_ids": list(self.excluded_factor_ids),
            "scoring_config_version": self.scoring_config_version,
            "region_config_version": self.region_config_version,
            "derivation_algorithm": self.derivation_algorithm,
            "risk_engine_algorithm_version": self.risk_engine_algorithm_version,
            "stored_derived_match": self.stored_derived_match,
            "rounding_policy": self.rounding_policy,
            "semantics": self.semantics,
        }


def _inputs(region: RegionConfig) -> dict[str, Any]:
    try:
        return region.data["static_susceptibility_inputs"]
    except (KeyError, TypeError) as exc:
        raise StaticBaselineError(
            f"region {region.region_id}: static_susceptibility_inputs missing"
        ) from exc


def compute_static_baseline(
    region: RegionConfig,
    verify_stored: bool = True,
) -> StaticBaseline:
    """Recompute B from the authorized region.json static factors.

    Never trusts a stored value blindly: when the DERIVED section exists it
    is verified against this recomputation (``verify_stored=True``) and any
    mismatch beyond the explicit tolerance fails validation.
    """
    inputs = _inputs(region)
    factors_raw = inputs.get("factors")
    if not isinstance(factors_raw, list) or not factors_raw:
        raise StaticBaselineError(
            f"region {region.region_id}: static susceptibility factors missing"
        )

    excluded = tuple(
        str(e.get("factor_id", ""))
        for e in inputs.get("excluded_factors", [])
        if isinstance(e, dict)
    )
    if EXCLUDED_FACTOR_ID not in excluded:
        raise StaticBaselineError(
            f"region {region.region_id}: frozen contract violated — factor "
            f"{EXCLUDED_FACTOR_ID} (monsoon / high-precipitation background) "
            "must be excluded from the static baseline to avoid double "
            "counting with dynamic precipitation"
        )
    factor_ids = [str(f.get("factor_id", "")) for f in factors_raw]
    if EXCLUDED_FACTOR_ID in factor_ids:
        raise StaticBaselineError(
            f"region {region.region_id}: excluded factor {EXCLUDED_FACTOR_ID} "
            "must not appear among retained static factors"
        )
    if len(set(factor_ids)) != len(factor_ids):
        raise StaticBaselineError(
            f"region {region.region_id}: duplicate static factor ids {factor_ids}"
        )

    # Frozen renormalization cross-check: retained normalized weights must be
    # the original weights renormalized to 100% (doc 04 §13: 20:25:20:15:10).
    originals = []
    for f in factors_raw:
        try:
            originals.append(float(f["original_weight_pct"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise StaticBaselineError(
                f"region {region.region_id}: factor {f.get('factor_id')} lacks "
                "a numeric original_weight_pct"
            ) from exc
    original_sum = sum(originals)
    if original_sum <= 0:
        raise StaticBaselineError(
            f"region {region.region_id}: original weights sum to {original_sum}"
        )
    declared_ratio = inputs.get("original_weight_ratio")
    if isinstance(declared_ratio, str) and declared_ratio.strip():
        try:
            declared = [float(part) for part in declared_ratio.split(":")]
        except ValueError:
            declared = []
        if declared and declared != originals:
            raise StaticBaselineError(
                f"region {region.region_id}: factor original weights {originals} "
                f"contradict the declared frozen ratio '{declared_ratio}'"
            )

    normalized_sum = 0.0
    contributions: list[StaticFactorContribution] = []
    for f, original in zip(factors_raw, originals):
        fid = str(f.get("factor_id", ""))
        try:
            score = float(f["score_0_to_5"])
            normalized = float(f["normalized_weight_pct"])
        except (KeyError, TypeError, ValueError) as exc:
            raise StaticBaselineError(
                f"region {region.region_id}: factor {fid} lacks numeric "
                "score_0_to_5 / normalized_weight_pct"
            ) from exc
        if not (0.0 <= score <= MAX_FACTOR_SCORE):
            raise StaticBaselineError(
                f"region {region.region_id}: factor {fid} score {score} "
                f"outside frozen 0-{MAX_FACTOR_SCORE} range"
            )
        expected_normalized = original / original_sum * 100.0
        if abs(normalized - expected_normalized) > NORMALIZED_WEIGHT_TOLERANCE:
            raise StaticBaselineError(
                f"region {region.region_id}: factor {fid} normalized weight "
                f"{normalized} inconsistent with frozen renormalization "
                f"{expected_normalized!r} (tolerance {NORMALIZED_WEIGHT_TOLERANCE})"
            )
        normalized_sum += normalized
        contributions.append(
            StaticFactorContribution(
                factor_id=fid,
                key=str(f.get("key", "")),
                name=str(f.get("name", "")),
                score_0_to_5=score,
                original_weight_pct=original,
                normalized_weight_pct=normalized,
                # Full precision; no intermediate rounding (frozen policy).
                contribution=(score / MAX_FACTOR_SCORE) * normalized,
                source_ids=tuple(str(s) for s in (f.get("source_ids") or [])),
            )
        )
    if abs(normalized_sum - 100.0) > WEIGHT_SUM_TOLERANCE:
        raise StaticBaselineError(
            f"region {region.region_id}: normalized static weights sum to "
            f"{normalized_sum}, not 100 (tolerance {WEIGHT_SUM_TOLERANCE})"
        )

    # B = sum of the five full-precision factor contributions.
    value = validate_index(
        sum(c.contribution for c in contributions),
        "B",
    )

    stored_match: Optional[bool] = None
    derived = region.data.get(DERIVED_SECTION_KEY)
    if derived is not None:
        if not isinstance(derived, dict):
            raise StaticBaselineValidationError(
                f"region {region.region_id}: {DERIVED_SECTION_KEY} is not a JSON object"
            )
        if verify_stored:
            _verify_stored_section(region, derived, value, contributions, inputs)
            stored_match = True

    return StaticBaseline(
        region_id=region.region_id,
        value=value,
        value_rounded=round(value, DISPLAY_DECIMALS),
        factors=tuple(contributions),
        excluded_factor_ids=excluded,
        scoring_config_version=str(inputs.get("scoring_config_version", "")),
        region_config_version=str(region.data.get("config_version", "")),
        derivation_algorithm=STATIC_BASELINE_ALGORITHM,
        risk_engine_algorithm_version=ALGORITHM_VERSION,
        stored_derived_match=stored_match,
    )


def _verify_stored_section(
    region: RegionConfig,
    derived: dict[str, Any],
    value: float,
    contributions: list[StaticFactorContribution],
    inputs: dict[str, Any],
) -> None:
    """Fail validation when the stored DERIVED B diverges from recomputation."""
    where = f"region {region.region_id}: {DERIVED_SECTION_KEY}"
    stored_full = derived.get("value_full_precision")
    if not isinstance(stored_full, (int, float)):
        raise StaticBaselineValidationError(f"{where}: value_full_precision missing")
    if abs(float(stored_full) - value) > STORED_FULL_PRECISION_TOLERANCE:
        raise StaticBaselineValidationError(
            f"{where}: stored B {stored_full} != recomputed B {value!r} "
            f"(tolerance {STORED_FULL_PRECISION_TOLERANCE}) — stored derived "
            "baseline is stale or was tampered with"
        )
    stored_rounded = derived.get("regional_static_susceptibility_baseline")
    if not isinstance(stored_rounded, (int, float)):
        raise StaticBaselineValidationError(
            f"{where}: regional_static_susceptibility_baseline missing"
        )
    if abs(float(stored_rounded) - round(value, DISPLAY_DECIMALS)) > STORED_ROUNDED_TOLERANCE:
        raise StaticBaselineValidationError(
            f"{where}: stored rounded B {stored_rounded} != recomputed "
            f"{round(value, DISPLAY_DECIMALS)} (tolerance {STORED_ROUNDED_TOLERANCE})"
        )
    stored_factors = derived.get("factor_contributions")
    if not isinstance(stored_factors, list) or len(stored_factors) != len(contributions):
        raise StaticBaselineValidationError(
            f"{where}: factor_contributions missing or wrong count"
        )
    by_id = {c.factor_id: c for c in contributions}
    for sf in stored_factors:
        fid = str(sf.get("factor_id", ""))
        if fid not in by_id:
            raise StaticBaselineValidationError(
                f"{where}: unknown stored factor contribution {fid}"
            )
        expected = by_id[fid].contribution
        got = sf.get("contribution")
        if not isinstance(got, (int, float)) or abs(float(got) - expected) > FACTOR_CONTRIBUTION_TOLERANCE:
            raise StaticBaselineValidationError(
                f"{where}: factor {fid} stored contribution {got} != "
                f"recomputed {expected!r} (tolerance {FACTOR_CONTRIBUTION_TOLERANCE})"
            )
    stored_ids = derived.get("source_factor_ids")
    if isinstance(stored_ids, list) and sorted(str(x) for x in stored_ids) != sorted(by_id):
        raise StaticBaselineValidationError(
            f"{where}: source_factor_ids {stored_ids} != recomputed factors {sorted(by_id)}"
        )
    stored_scoring = derived.get("scoring_config_version")
    if stored_scoring is not None and str(stored_scoring) != str(
        inputs.get("scoring_config_version", "")
    ):
        raise StaticBaselineValidationError(
            f"{where}: scoring_config_version {stored_scoring!r} != "
            f"{inputs.get('scoring_config_version')!r}"
        )


def derive_static_baseline_section(
    baseline: StaticBaseline,
    generated_at: str,
    generated_by: str = (
        f"MountainGuardian G03B deterministic engine ({ALGORITHM_VERSION})"
    ),
) -> dict[str, Any]:
    """Build the DERIVED region.json section from a verified computation.

    The section is generated deterministically from the authorized inputs —
    never typed by hand — and is clearly marked as derived, not as a source
    fact. It must not alter source factor scores, provenance or references.
    """
    return {
        "status": "DERIVED",
        "notice": (
            "DERIVED section — deterministically computed from "
            "static_susceptibility_inputs by the G03B Risk Watch engine. Not "
            "a source fact and not an engine input: the engine always "
            "recomputes B and verifies it against this record within explicit "
            "numerical tolerance."
        ),
        "regional_static_susceptibility_baseline": baseline.value_rounded,
        "value_full_precision": baseline.value,
        "rounding_policy": baseline.rounding_policy,
        "derivation": (
            "B = sum over the five retained static factors of "
            "(score_0_to_5 / 5.0) * normalized_weight_pct; R5 excluded to "
            "prevent double counting with the dynamic precipitation trigger"
        ),
        "derivation_algorithm": baseline.derivation_algorithm,
        "risk_engine_algorithm_version": baseline.risk_engine_algorithm_version,
        "scoring_config_version": baseline.scoring_config_version,
        "generated_from": [
            "static_susceptibility_inputs",
        ],
        "source_factor_ids": [f.factor_id for f in baseline.factors],
        "factor_contributions": [
            {
                "factor_id": f.factor_id,
                "key": f.key,
                "name": f.name,
                "score_0_to_5": f.score_0_to_5,
                "normalized_weight_pct": f.normalized_weight_pct,
                "contribution": f.contribution,
                "contribution_rounded": round_display(f.contribution),
                "source_ids": list(f.source_ids),
            }
            for f in baseline.factors
        ],
        "contribution_sum_check": (
            "sum(factor_contributions[].contribution) == value_full_precision "
            f"within {STORED_FULL_PRECISION_TOLERANCE}"
        ),
        "excluded_factors": [
            {
                "factor_id": fid,
                "reason": (
                    "Excluded from the static baseline to avoid double "
                    "counting with the dynamic precipitation trigger "
                    "(doc 04 §13)."
                ),
            }
            for fid in baseline.excluded_factor_ids
        ],
        "semantics": baseline.semantics,
        "generated_at": generated_at,
        "generated_by": generated_by,
    }


def verify_stored_baseline(
    region: RegionConfig,
    baseline: StaticBaseline | None = None,
) -> StaticBaseline:
    """Strict production check: the DERIVED section must exist and match.

    Used by tests/verification tooling for the tracked production region;
    raises StaticBaselineValidationError when the section is absent or when
    stored and recomputed B differ beyond the explicit tolerance.
    """
    derived = region.data.get(DERIVED_SECTION_KEY)
    if not isinstance(derived, dict):
        raise StaticBaselineValidationError(
            f"region {region.region_id}: required {DERIVED_SECTION_KEY} "
            "section is missing from region.json (doc 04 §13 requires the "
            "derived B to be reproducibly available)"
        )
    if baseline is None:
        baseline = compute_static_baseline(region, verify_stored=True)
    return baseline
