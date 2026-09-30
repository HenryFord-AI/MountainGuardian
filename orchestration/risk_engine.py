"""
MountainGuardian v1.0 – Deterministic Historical Risk Engine (G02B).

Frozen design references:
  - 02_MountainGuardian_Scientific_Data_Baseline_v1.0.md §6 (Risk Index ≠
    Probability; Risk Level bands), §7 (frozen six-factor Jilong demo model,
    Baseline Risk Index = 91 / 100), §8.1 (deterministic engine owns Risk
    Index, weights, factor contributions, thresholds — reproducible, same
    input → same output)
  - 03_MountainGuardian_AI_Agent_Architecture_v1.0.md §13 (Risk Engine is
    independent of any LLM; the Synthesizer may NOT override its numbers),
    §22.3 (Risk Engine is on the critical path: if it cannot run, no formal
    Risk Index may be produced)
  - 04_MountainGuardian_Risk_Watch_Design_v1.0.md §16 (frozen Risk Level
    bands: 0–39 LOW, 40–59 MODERATE, 60–79 ELEVATED, 80–100 HIGH)

The six-factor formula frozen in the Case Pack is:

    contribution_i = round(weight_pct_i * score_i / 5, 1)
    risk_index     = round(sum(contribution_i), 1)

This module NEVER consults a model, the network, or any mutable state.
The result is an immutable (frozen dataclass) structured object that is the
ONLY authorized source of the Risk Index for synthesis and display.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


class RiskEngineError(RuntimeError):
    """Raised when the deterministic engine cannot produce a formal Risk
    Index (doc 03 §22.3: risk calculation unavailable — the pipeline must
    stop rather than let any narrative replace the number)."""


#: Frozen Risk Level bands (doc 04 §16 — Prototype Risk Bands)
RISK_LEVEL_BANDS = (
    (0, 39, "LOW"),
    (40, 59, "MODERATE"),
    (60, 79, "ELEVATED"),
    (80, 100, "HIGH"),
)

#: Frozen semantics statement — must accompany the index everywhere.
RISK_INDEX_SEMANTICS = (
    "基础易灾风险指数（Baseline Susceptibility Index，0-100），"
    "由确定性引擎计算；不是灾害发生概率，不是预测准确率。")


def risk_level_for(index: float) -> str:
    """Map a 0–100 index onto the frozen Risk Level bands."""
    value = float(index)
    for low, high, level in RISK_LEVEL_BANDS:
        if low <= value <= high:
            return level
    raise RiskEngineError(f"risk index {value} outside 0-100 range")


@dataclass(frozen=True)
class RiskFactorContribution:
    """One frozen factor's recomputed contribution. Immutable."""

    factor_id: str
    name: str
    weight_pct: float
    score_0_to_5: float
    contribution: float
    evidence: str
    source_ids: tuple = ()

    def to_dict(self) -> dict:
        return {
            "id": self.factor_id,
            "name": self.name,
            "weight_pct": self.weight_pct,
            "score": self.score_0_to_5,
            "contribution": self.contribution,
            "evidence": self.evidence,
            "source_ids": list(self.source_ids),
        }


@dataclass(frozen=True)
class HistoricalRiskResult:
    """Immutable output of the deterministic Historical Replay risk engine.

    This object — not any model output — is the authoritative Risk Index.
    Downstream consumers (Risk Synthesizer, Critic, UI) receive it as
    controlled structured input and may explain it, never modify it
    (doc 03 §13.3, §14.3).
    """

    run_id: str
    case_id: str
    risk_index: float
    risk_level: str
    pack_stated_index: float
    weight_sum: float
    factors: tuple
    semantics: str = RISK_INDEX_SEMANTICS
    interpretation: str = ""
    model_name: str = ""
    model_type: str = ""
    computed_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "case_id": self.case_id,
            "risk_index": self.risk_index,
            "risk_level": self.risk_level,
            "pack_stated_index": self.pack_stated_index,
            "weight_sum": self.weight_sum,
            "model_name": self.model_name,
            "model_type": self.model_type,
            "semantics": self.semantics,
            "interpretation": self.interpretation,
            "factors": [f.to_dict() for f in self.factors],
            "computed_at": self.computed_at,
        }

    def top_drivers(self, n: int = 3) -> list:
        """Deterministic top risk drivers: highest-contribution factors."""
        ordered = sorted(self.factors, key=lambda f: f.contribution,
                         reverse=True)
        return [f"{f.name}（贡献 {f.contribution:.1f}，权重 {f.weight_pct:.0f}%，"
                f"评分 {f.score_0_to_5:.0f}/5）" for f in ordered[:n]]


def compute_historical_risk(case: Optional[dict] = None,
                            run_id: str = "") -> HistoricalRiskResult:
    """Recompute the frozen six-factor Historical Replay Risk Index.

    Deterministic: same Case Pack → same result, always. Validates its own
    integrity (weights sum to 100; recomputation matches the pack-stated
    index) and raises RiskEngineError otherwise — a mismatch means the
    frozen baseline was tampered with and NO formal index may be issued.
    """
    if case is None:
        from tools.case_loader import load_case
        case = load_case()

    model = case.get("risk_model")
    if not model or not model.get("factors"):
        raise RiskEngineError(
            "demo_risk_model missing from Case Pack — risk calculation "
            "unavailable (doc 03 §22.3)")

    factors = []
    for f in model["factors"]:
        weight = float(f["weight_pct"])
        score = float(f["score_0_to_5"])
        if not (0.0 <= score <= 5.0):
            raise RiskEngineError(
                f"factor {f.get('id')} score {score} outside frozen 0-5 range")
        contribution = round(weight * score / 5.0, 1)
        factors.append(RiskFactorContribution(
            factor_id=str(f.get("id", "")),
            name=str(f.get("name", "")),
            weight_pct=weight,
            score_0_to_5=score,
            contribution=contribution,
            evidence=str(f.get("evidence", "")),
            source_ids=tuple(str(s) for s in (f.get("source_ids") or [])),
        ))

    weight_sum = float(sum(f.weight_pct for f in factors))
    if round(weight_sum, 6) != 100.0:
        raise RiskEngineError(
            f"frozen model integrity violated: weights sum {weight_sum} != 100")

    index = round(sum(f.contribution for f in factors), 1)
    stated = float(model.get("calculated_index_0_to_100", index))
    if abs(index - stated) > 0.05:
        raise RiskEngineError(
            f"recomputed index {index} != pack-stated index {stated} — "
            "frozen baseline integrity violated")

    result = HistoricalRiskResult(
        run_id=run_id,
        case_id=str(case.get("meta", {}).get("case_id", "")),
        risk_index=index,
        risk_level=risk_level_for(index),
        pack_stated_index=stated,
        weight_sum=weight_sum,
        factors=tuple(factors),
        interpretation=str(model.get("interpretation", "")),
        model_name=str(model.get("name", "")),
        model_type=str(model.get("type", "")),
    )
    logger.info("[risk_engine] run=%s risk_index=%.1f level=%s factors=%d "
                "(deterministic, no LLM)", run_id, index, result.risk_level,
                len(factors))
    return result
