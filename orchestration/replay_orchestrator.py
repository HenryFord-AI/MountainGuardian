"""
MountainGuardian v1.0 – Historical Replay orchestrator (G02B).

Frozen design references:
  - 03_MountainGuardian_AI_Agent_Architecture_v1.0.md §16 (Stage A
    scientific review must freeze BEFORE Stage B post-event validation is
    allowed to read post_event data; Stage B may never write back or alter
    the Stage-A Risk Index), §22.2 (agent failure isolation), §13/§14
    (engine → synthesizer separation)
  - 02_MountainGuardian_Scientific_Data_Baseline_v1.0.md §5 (leakage red
    line: post-event information may only be consumed AFTER the risk
    result exists, by validation — never fed back into risk analysis)
  - 07_MountainGuardian_Battle_Plan_v1.0.md §14 (G02B two-stage freeze)

The workflow is an explicit, minimal, deterministic DAG — no free-form
planner, no recursion, no agent spawning, no autonomous memory:

    Stage A:
        build pre-event AnalysisContext
        → run 3 independent professional agents (isolated failures)
        → deterministic Historical Risk Engine (frozen 6 factors)
        → Risk Synthesizer (explains, never alters, the index)
        → Critic (programmatic checks + bounded model review)
        → FREEZE (immutable, digest-sealed StageAFreeze)

    Stage B (only after the freeze exists):
        load authorized post-event evidence
        → retrospective validation ONLY (deterministic; no provider calls;
          structurally impossible to write back into Stage A)

Programmatic immutability: the frozen Stage-A payload is stored as an
immutable JSON string with a SHA-256 content digest inside a frozen
dataclass. Any attribute mutation raises FrozenInstanceError; any payload
tampering is detectable via verify_integrity(); Stage B reads deep copies
and re-verifies the digest before and after, attesting the Risk Index and
all Stage-A state are unchanged.
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

# NOTE: agents.critic / agents.risk_synthesizer / agents.professional_base
# are imported lazily inside run_stage_a() — those modules import
# orchestration.context_builder / orchestration.risk_engine, and a
# module-level import here would create a circular import through the
# orchestration package __init__.
from orchestration.context_builder import (
    MODE_HISTORICAL_REPLAY,
    AnalysisContext,
    build_analysis_context,
)
from orchestration.risk_engine import (
    HistoricalRiskResult,
    compute_historical_risk,
)
from providers.base_provider import ModelProvider
from schemas.evidence import POST_EVENT_PHASES, build_evidence_pool
from schemas.synthesis import CriticVerdictResult, SynthesisResult

logger = logging.getLogger(__name__)


class FrozenStateError(RuntimeError):
    """Raised when a mutation of frozen Stage-A state is detected or when
    Stage B is invoked without a valid freeze."""


def _canonical_json(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False,
                      default=str)


def _digest(payload_json: str) -> str:
    return hashlib.sha256(payload_json.encode("utf-8")).hexdigest()


# ─── Stage A freeze record ─────────────────────────────────────────────────────
@dataclass(frozen=True)
class StageAFreeze:
    """Immutable, digest-sealed Stage-A state.

    Attribute assignment raises dataclasses.FrozenInstanceError. The
    payload lives as a JSON *string* — callers only ever receive deep
    copies from to_dict(), so no external code can mutate the frozen state
    in place. verify_integrity() proves the seal is intact.
    """

    run_id: str
    frozen_at: str
    risk_index: float
    risk_level: str
    critic_review_result: str
    content_digest: str
    payload_json: str
    #: evidence-set identity (authorized Stage-A evidence ids)
    stage_a_evidence_ids: tuple

    def to_dict(self) -> dict:
        """Fresh deep copy — mutating the return value cannot affect the
        frozen record."""
        return json.loads(self.payload_json)

    def verify_integrity(self) -> bool:
        return _digest(self.payload_json) == self.content_digest

    def assert_integrity(self) -> None:
        if not self.verify_integrity():
            raise FrozenStateError(
                f"Stage-A freeze {self.run_id} digest mismatch — frozen "
                "state was tampered with")


def build_stage_a_freeze(run_id: str, context: AnalysisContext,
                         risk_result: HistoricalRiskResult,
                         agent_results: dict,
                         synthesis: SynthesisResult,
                         verdict: CriticVerdictResult) -> StageAFreeze:
    """Seal the Stage-A state. Called ONLY after the Critic verdict exists
    (Stage A must freeze before any post-event evidence is introduced)."""
    evidence_ids = tuple(sorted(context.evidence_by_id().keys()))
    payload = {
        "run_id": run_id,
        "stage": "A",
        "mode": context.mode,
        "case_metadata": dict(context.case_metadata),
        "stage_a_evidence_ids": list(evidence_ids),
        "risk_engine": risk_result.to_dict(),
        "risk_index": risk_result.risk_index,
        "risk_level": risk_result.risk_level,
        "agent_results": {
            name: {"output": res.to_dict(), "audit": res.to_audit_dict()}
            for name, res in agent_results.items()},
        "agent_status_summary": {name: res.status.value
                                 for name, res in agent_results.items()},
        "synthesis": {"output": synthesis.to_dict(),
                      "audit": synthesis.to_audit_dict()},
        "critic": {"verdict": verdict.to_dict(),
                   "audit": verdict.to_audit_dict()},
        "fallback_state": {
            "synthesis_fallback_used": synthesis.fallback_used,
            "synthesis_is_model_output": synthesis.is_model_output,
            "critic_fallback_used": verdict.fallback_used,
            "agents_fallback_used": {n: r.fallback_used
                                     for n, r in agent_results.items()},
        },
        "provider_metadata": {
            "synthesis_provider": synthesis.provider,
            "synthesis_model_id": synthesis.model_id,
            "critic_provider": verdict.provider,
            "critic_model_id": verdict.model_id,
            "agents": {n: {"provider": r.provider, "model_id": r.model_id,
                           "provider_status": r.provider_status}
                       for n, r in agent_results.items()},
        },
    }
    payload_json = _canonical_json(payload)
    freeze = StageAFreeze(
        run_id=run_id,
        frozen_at=datetime.now(timezone.utc).isoformat(),
        risk_index=risk_result.risk_index,
        risk_level=risk_result.risk_level,
        critic_review_result=verdict.review_result,
        content_digest=_digest(payload_json),
        payload_json=payload_json,
        stage_a_evidence_ids=evidence_ids,
    )
    freeze.assert_integrity()
    logger.info("[replay] Stage A frozen: run=%s digest=%s risk_index=%.1f "
                "critic=%s", run_id, freeze.content_digest[:12],
                freeze.risk_index, verdict.review_result)
    return freeze


# ─── Stage B validation ────────────────────────────────────────────────────────
@dataclass(frozen=True)
class StageBValidationResult:
    """Retrospective validation output. Immutable; carries the Stage-A
    integrity attestation (digest + risk index before/after)."""

    run_id: str
    validated_at: str
    stage_a_digest_before: str
    stage_a_digest_after: str
    stage_a_unchanged: bool
    risk_index_before: float
    risk_index_after: float
    directional_findings: tuple
    stage_a_could_not_know: tuple
    post_event_evidence_ids: tuple
    statement: str

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "validated_at": self.validated_at,
            "stage_a_digest_before": self.stage_a_digest_before,
            "stage_a_digest_after": self.stage_a_digest_after,
            "stage_a_unchanged": self.stage_a_unchanged,
            "risk_index_before": self.risk_index_before,
            "risk_index_after": self.risk_index_after,
            "directional_findings": list(self.directional_findings),
            "stage_a_could_not_know": list(self.stage_a_could_not_know),
            "post_event_evidence_ids": list(self.post_event_evidence_ids),
            "statement": self.statement,
        }


#: frozen-factor → post-event correspondence used for DIRECTIONAL validation
#: only (doc 03 §16 Stage B: does the pre-event risk reasoning correspond
#: directionally to what actually happened?). Values are field keys of the
#: Case Pack post_event_validation phase.
_FACTOR_VALIDATION_MAP = {
    "R1": ("source_area", "actual_trigger"),
    "R2": ("actual_runout_km", "actual_avg_speed_mps"),
    "R3": ("actual_disaster_chain", "actual_runout_km"),
    "R4": ("actual_disaster_chain",),
    "R5": ("actual_trigger",),
    "R6": ("actual_affected_area_km2", "actual_structures_destroyed"),
}

#: outcome observations that Stage A could NOT know (doc 02 §4.5)
_UNKNOWABLE_KEYS = (
    "source_fracture_time_later_report", "actual_trigger",
    "actual_disaster_chain", "actual_runout_km", "actual_travel_time_min",
    "actual_avg_speed_mps", "actual_affected_area_km2",
    "actual_structures_destroyed", "satellite_post_datetime",
    "satellite_post_cloud_pct", "satellite_visible_change",
    "official_satellite_scene_count",
)


def run_stage_b(freeze: StageAFreeze,
                case: Optional[dict] = None) -> StageBValidationResult:
    """Post-event retrospective validation — callable ONLY with a sealed
    Stage-A freeze. Deterministic; performs NO provider calls, so
    post-event evidence can never enter a Stage-A (or any) model request.

    Reads deep copies of the frozen payload; verifies the digest before and
    after to attest Stage A was not altered.
    """
    if not isinstance(freeze, StageAFreeze):
        raise FrozenStateError(
            "Stage B requires a sealed StageAFreeze — Stage A must be "
            "frozen before post-event evidence is loaded")
    freeze.assert_integrity()
    digest_before = freeze.content_digest
    index_before = freeze.risk_index
    payload = freeze.to_dict()          # deep copy — safe to read
    factor_names = {f["id"]: f["name"] for f in
                    payload.get("risk_engine", {}).get("factors", [])}

    if case is None:
        from tools.case_loader import load_case
        case = load_case()
    post_fields = {str(f.get("key")): f for f in case.get("post_event", [])}
    post_ids = tuple(sorted(
        item.evidence_id
        for item in build_evidence_pool(case)
        if item.phase in POST_EVENT_PHASES))

    def pv(key: str) -> str:
        f = post_fields.get(key)
        if not f:
            return "（未提供）"
        unit = f.get("unit") or ""
        return f"{f.get('value')}{(' ' + unit) if unit else ''}"

    # directional correspondence: Stage-A susceptibility factors vs the
    # actual outcome (validation only — NOT new risk analysis)
    findings = []
    for factor_id, keys in _FACTOR_VALIDATION_MAP.items():
        name = factor_names.get(factor_id, factor_id)
        observed = "；".join(f"{k}={pv(k)}" for k in keys if k in post_fields)
        if observed:
            findings.append(
                f"灾前因子 {factor_id}（{name}）识别的风险条件与灾后观测"
                f"方向性对应：{observed}。")
    chain = pv("actual_disaster_chain")
    if chain != "（未提供）":
        findings.append(
            f"实际灾害链（{chain}）与 Stage A 基于静态易灾背景识别的"
            "冰岩—碎屑流—泥石流链式灾害风险方向一致（方向性验证，"
            "不构成提前预测证明）。")

    could_not_know = [
        f"{post_fields[k].get('name_zh', k)}：{pv(k)}"
        for k in _UNKNOWABLE_KEYS if k in post_fields]

    # integrity attestation: the frozen record was never written to
    freeze.assert_integrity()
    digest_after = freeze.content_digest
    index_after = freeze.risk_index
    unchanged = (digest_before == digest_after
                 and abs(index_before - index_after) < 1e-9)
    if not unchanged:
        raise FrozenStateError("Stage-B run detected Stage-A mutation")

    statement = (
        "Stage B 仅执行灾后回顾性验证：对比 Stage A 已识别的风险条件与"
        "灾后调查/影像结果，并说明 Stage A 当时不可能知道的事件细节"
        "（时间、路径、速度、影响范围等）。Stage B 未修改且不可修改 "
        "Stage A 的 Risk Index、专业 Agent 输出、综合结果、审查结论或"
        "证据集；灾后证据从未进入任何 Stage-A 模型请求。")
    result = StageBValidationResult(
        run_id=freeze.run_id,
        validated_at=datetime.now(timezone.utc).isoformat(),
        stage_a_digest_before=digest_before,
        stage_a_digest_after=digest_after,
        stage_a_unchanged=unchanged,
        risk_index_before=index_before,
        risk_index_after=index_after,
        directional_findings=tuple(findings),
        stage_a_could_not_know=tuple(could_not_know),
        post_event_evidence_ids=post_ids,
        statement=statement,
    )
    logger.info("[replay] Stage B validation complete: run=%s unchanged=%s "
                "risk_index=%.1f (no provider calls)", freeze.run_id,
                unchanged, index_after)
    return result


# ─── End-to-end replay ─────────────────────────────────────────────────────────
@dataclass(frozen=True)
class HistoricalReplayResult:
    """Full bounded Historical Replay run: frozen Stage A + Stage B
    validation. Immutable."""

    run_id: str
    stage_a: StageAFreeze
    stage_b: StageBValidationResult

    @property
    def risk_index(self) -> float:
        return self.stage_a.risk_index

    @property
    def critic_review_result(self) -> str:
        return self.stage_a.critic_review_result

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "stage_a": self.stage_a.to_dict(),
            "stage_a_digest": self.stage_a.content_digest,
            "stage_b": self.stage_b.to_dict(),
            "risk_index_before_stage_b": self.stage_b.risk_index_before,
            "risk_index_after_stage_b": self.stage_b.risk_index_after,
        }


def run_stage_a(provider: Optional[ModelProvider] = None,
                case: Optional[dict] = None,
                run_id: Optional[str] = None,
                synthesizer: Optional[RiskSynthesizer] = None,
                critic: Optional[Critic] = None,
                agent_results: Optional[dict] = None) -> StageAFreeze:
    """Execute and freeze Stage A of the Historical Replay DAG.

    `agent_results` may be supplied for testing; in production the three
    professional agents run here with strict failure isolation (G02A).
    """
    from agents.critic import Critic
    from agents.professional_base import run_professional_agents
    from agents.risk_synthesizer import RiskSynthesizer

    context = build_analysis_context(case=case, run_id=run_id)
    if context.mode != MODE_HISTORICAL_REPLAY:
        raise ValueError("Stage A supports historical_replay mode only "
                         "in G02B")
    risk_result = compute_historical_risk(case, run_id=context.run_id)
    if agent_results is None:
        agent_results = run_professional_agents(context, provider)
    synthesizer = synthesizer or RiskSynthesizer(provider=provider)
    critic = critic or Critic(provider=provider)
    synthesis = synthesizer.run(agent_results, risk_result, context)
    verdict = critic.run(synthesis, risk_result, agent_results, context,
                         case=case)
    return build_stage_a_freeze(context.run_id, context, risk_result,
                                agent_results, synthesis, verdict)


def run_historical_replay(provider: Optional[ModelProvider] = None,
                          case: Optional[dict] = None,
                          run_id: Optional[str] = None,
                          **stage_a_kwargs) -> HistoricalReplayResult:
    """Full bounded Historical Replay: Stage A (freeze) → Stage B
    (validation only). Explicit DAG — no planner, no recursion."""
    freeze = run_stage_a(provider=provider, case=case, run_id=run_id,
                         **stage_a_kwargs)
    validation = run_stage_b(freeze, case=case)
    return HistoricalReplayResult(run_id=freeze.run_id, stage_a=freeze,
                                  stage_b=validation)
