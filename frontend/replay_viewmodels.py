"""
MountainGuardian G04B – Historical Replay view model (read-only consumer).

Doc 05 §15–§22 / doc 04 / gate G04B §9: the Historical Replay page is a
research-validation view over the FROZEN 2026 Jilong 8·26 case. This module
consumes existing backend contracts and nothing else:

  * case facts + evidence pool      ← tools.case_loader / schemas.evidence
  * Baseline Susceptibility Index   ← orchestration.risk_engine (called,
                                       never reimplemented; 91/100 HIGH)
  * Stage A freeze / Stage B check  ← orchestration.replay_orchestrator
                                       (provider=None → deterministic
                                       fallback outputs, honestly labeled)

Hard boundaries kept from G04A:
  * Stage A evidence and Stage B (post-event) evidence stay in SEPARATE
    tuples — post-event items can never render inside the pre-event panel;
  * the Risk Index is consumed from the deterministic engine result, never
    recomputed or reinterpreted here (no misuse as event likelihood, ever);
  * no provider / agent class imports, no writes, no fabricated values —
    every missing piece surfaces as an explicit empty state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from orchestration.replay_orchestrator import run_stage_a, run_stage_b
from orchestration.risk_engine import compute_historical_risk
from schemas.evidence import (
    TYPE_CLIMATE_CONTEXT,
    TYPE_CRYOSPHERE,
    TYPE_GEOLOGY,
    TYPE_HISTORICAL_EVENT,
    TYPE_RS_IMAGE,
    TYPE_RS_METADATA,
    TYPE_TERRAIN,
    TYPE_WEATHER_CONTEXT,
    build_evidence_pool,
)
from schemas.synthesis import CRITIC_CHECK_IDS
from tools.case_loader import load_case

# Frozen display grouping of pre-event evidence (doc 05 §18).
EVIDENCE_CATEGORIES = (
    ("Terrain", "地形地质", (TYPE_TERRAIN, TYPE_GEOLOGY)),
    ("Glacier / Cryosphere", "冰冻圈", (TYPE_CRYOSPHERE,)),
    ("Historical Events", "历史事件", (TYPE_HISTORICAL_EVENT,)),
    ("Weather Context", "气象背景", (TYPE_WEATHER_CONTEXT, TYPE_CLIMATE_CONTEXT)),
    ("Satellite", "卫星遥感", (TYPE_RS_IMAGE, TYPE_RS_METADATA)),
)

# Deterministic, offline replay run identity for the product page.
UI_REPLAY_RUN_ID = "g04b-ui-replay"


@dataclass(frozen=True)
class ReplayEvidenceVM:
    evidence_id: str
    type_label: str
    source: str
    source_reference: str
    observed: str
    phase: str                 # PRE-EVENT / POST-EVENT display vocabulary
    quality: str
    raw_or_derived: str
    allowed_agents: tuple
    summary: str
    note: str = ""


@dataclass(frozen=True)
class ReplayAgentVM:
    key: str
    name_en: str
    name_zh: str
    status: str
    confidence: Optional[float]
    evidence_ids: tuple
    findings: tuple
    missing_data: tuple
    limitations: tuple
    fallback_used: bool
    is_model_output: bool
    model_id: str
    provider_status: str
    latency_ms: Optional[int]
    is_ai_layer: bool = False


@dataclass(frozen=True)
class ReplayCriticVM:
    review_result: str
    severity: str
    issues: tuple              # (check_id, severity, message)
    scientific_limitations: tuple
    required_corrections: tuple
    programmatic_checks: tuple  # (check_id, ok)
    risk_index_before: Optional[float]
    risk_index_after: Optional[float]
    fallback_used: bool


@dataclass(frozen=True)
class HistoricalReplayViewModel:
    case_id: str
    case_name: str
    location: str
    event_date: str

    timeline: tuple            # (label_en, label_zh, when, color_key, note)
    pre_event_evidence: tuple  # ReplayEvidenceVM (Stage A inputs only)
    post_event_evidence: tuple  # ReplayEvidenceVM (validation only)

    risk_index: float
    risk_level: str
    semantics: str
    interpretation: str
    factors: tuple             # (id, name, weight, score, contribution)
    top_drivers: tuple         # (name, contribution)

    agents: tuple              # ReplayAgentVM (3 professional agents)
    synthesizer: Optional[ReplayAgentVM]
    synthesis_summary: str
    synthesis_agreement: str
    synthesis_coverage: Optional[float]
    synthesis_limitations: tuple

    critic: Optional[ReplayCriticVM]

    stage_b_statement: str
    stage_b_findings: tuple
    stage_b_could_not_know: tuple
    stage_b_post_event_ids: tuple
    stage_a_unchanged: bool
    post_event_facts: tuple    # (label, value) official investigation facts
    post_satellite: tuple      # (label, value) post-event imagery facts

    limitations: tuple
    model_runtime: str
    fallback_mode: bool
    run_id: str
    frozen_at: str

    @property
    def system_state(self) -> str:
        if self.fallback_mode:
            return "DEGRADED"
        return "ONLINE"


_PHASE_DISPLAY = {
    "pre_event_static": "PRE-EVENT",
    "derived_pre_event_static": "PRE-EVENT",
    "pre_event_context": "PRE-EVENT",
    "pre_event_evidence": "PRE-EVENT",
    "post_event_validation": "POST-EVENT",
    "context_only": "CONTEXT",
}


def _evidence_vm(item, phase_display: str) -> ReplayEvidenceVM:
    return ReplayEvidenceVM(
        evidence_id=item.evidence_id,
        type_label=str(item.evidence_type),
        source=str(item.source_name or ""),
        source_reference=str(item.source_reference or ""),
        observed=str(item.observation_time or "—"),
        phase=phase_display,
        quality=str(item.quality.value if hasattr(item.quality, "value")
                    else item.quality),
        raw_or_derived=str(item.raw_or_derived or ""),
        allowed_agents=tuple(item.allowed_agents or ()),
        summary=str(item.summary or ""),
        note=str(item.limitations or ""),
    )


def _agent_vm(key: str, name_en: str, name_zh: str, entry: dict,
              is_ai_layer: bool = False) -> ReplayAgentVM:
    out = entry.get("output") or {}
    audit = entry.get("audit") or {}
    return ReplayAgentVM(
        key=key, name_en=name_en, name_zh=name_zh,
        status=str(out.get("status") or "PENDING"),
        confidence=out.get("confidence"),
        evidence_ids=tuple(out.get("evidence_ids") or ()),
        findings=tuple(str(x) for x in (out.get("key_findings") or ())),
        missing_data=tuple(str(x) for x in (out.get("missing_data") or ())),
        limitations=tuple(str(x) for x in (out.get("limitations") or ())),
        fallback_used=bool(out.get("fallback_used")),
        is_model_output=bool(out.get("is_model_output")),
        model_id=str(audit.get("model_id") or out.get("model_id") or "—"),
        provider_status=str(audit.get("provider_status") or "UNKNOWN"),
        latency_ms=audit.get("latency_ms"),
        is_ai_layer=is_ai_layer,
    )


def build_historical_replay_viewmodel(
    case_id: str = "jilong_20260826",
    run_id: str = UI_REPLAY_RUN_ID,
) -> HistoricalReplayViewModel:
    """Assemble the Historical Replay view model.

    Deterministic and offline: the professional agents / synthesizer /
    critic run through the frozen Stage-A pipeline with provider=None, so
    every AI-layer output is a labeled deterministic fallback unless a real
    persisted run is wired in later. No network, no writes, no fabrication.
    """
    case = load_case(case_id)
    meta = case.get("meta") or {}

    # Deterministic Baseline Susceptibility Index — consumed, never recomputed.
    risk = compute_historical_risk(case, run_id=run_id)

    # Stage A freeze + Stage B validation through the frozen orchestrator.
    freeze = run_stage_a(provider=None, case=case, run_id=run_id)
    stage_b = run_stage_b(freeze, case=case)
    payload = freeze.to_dict()

    # Evidence pool, strictly separated by phase (doc 05 §17–§18).
    pool = build_evidence_pool(case)
    pre = tuple(
        _evidence_vm(item, _PHASE_DISPLAY.get(item.phase, "PRE-EVENT"))
        for item in pool if item.is_pre_event()
    )
    post = tuple(
        _evidence_vm(item, "POST-EVENT") for item in pool if item.is_post_event()
    )

    agent_results = payload.get("agent_results") or {}
    from frontend.viewmodels import AGENT_DISPLAY_NAMES, CRITIC_DISPLAY, \
        SYNTHESIZER_DISPLAY

    agents = tuple(
        _agent_vm(key, AGENT_DISPLAY_NAMES[key][0], AGENT_DISPLAY_NAMES[key][1],
                  agent_results.get(key) or {})
        for key in ("glacier_geology", "weather_hydrology", "remote_sensing")
    )
    synthesizer = _agent_vm(
        "synthesizer", SYNTHESIZER_DISPLAY[0], SYNTHESIZER_DISPLAY[1],
        payload.get("synthesis") or {}, is_ai_layer=True,
    )
    syn_out = (payload.get("synthesis") or {}).get("output") or {}
    if syn_out:
        # SynthesisResult carries no status field: the step either produced
        # a result (COMPLETED, fallback badge shown separately) or is absent.
        synthesizer = ReplayAgentVM(
            key=synthesizer.key, name_en=synthesizer.name_en,
            name_zh=synthesizer.name_zh,
            status="COMPLETED",
            confidence=syn_out.get("explanation_confidence"),
            evidence_ids=synthesizer.evidence_ids,
            findings=(str(syn_out.get("summary") or ""),) if syn_out.get("summary") else (),
            missing_data=tuple(str(x) for x in (syn_out.get("missing_data") or ())),
            limitations=synthesizer.limitations,
            fallback_used=synthesizer.fallback_used,
            is_model_output=synthesizer.is_model_output,
            model_id=synthesizer.model_id,
            provider_status=synthesizer.provider_status,
            latency_ms=synthesizer.latency_ms,
            is_ai_layer=True,
        )

    critic_raw = (payload.get("critic") or {}).get("verdict") or {}
    critic = None
    if critic_raw:
        failed_checks = dict(critic_raw.get("programmatic_check_status") or {})
        critic = ReplayCriticVM(
            review_result=str(critic_raw.get("review_result") or "UNAVAILABLE"),
            severity=str(critic_raw.get("severity") or ""),
            issues=tuple(
                (str(i.get("check_id", "")), str(i.get("severity", "")),
                 str(i.get("message", "")))
                for i in (critic_raw.get("issues") or ())
            ),
            scientific_limitations=tuple(
                str(x) for x in (critic_raw.get("scientific_limitations") or ())),
            required_corrections=tuple(
                str(x) for x in (critic_raw.get("required_corrections") or ())),
            programmatic_checks=tuple(
                (str(cid), str(cid) not in failed_checks)
                for cid in CRITIC_CHECK_IDS
            ),
            risk_index_before=critic_raw.get("risk_index_before"),
            risk_index_after=critic_raw.get("risk_index_after"),
            fallback_used=bool(critic_raw.get("fallback_used")),
        )

    # Timeline markers from real case facts (satellite scenes + event date).
    sat = case.get("satellite") or {}
    pub = sat.get("public_sentinel2") or {}
    pre_dt = str((pub.get("pre") or {}).get("datetime_utc", ""))[:10] or "≤ event"
    post_dt = str((pub.get("post") or {}).get("datetime_utc", ""))[:10] or "≥ event"
    timeline = (
        ("PRE-EVENT", "灾前分析（仅使用灾前数据）", pre_dt or "—", "CYAN",
         "公开灾前数据截止日"),
        ("EVENT", "事件发生", str(meta.get("event_date") or "—"), "ORANGE", ""),
        ("POST-EVENT", "灾后验证（仅用于验证）", post_dt or "—", "PURPLE",
         "灾后资料不进入灾前分析"),
    )

    # Official post-event investigation facts (Case Pack, post_event phase).
    post_fields = {f["key"]: f for f in (case.get("post_event") or [])}

    def _fact(key: str, label: str) -> tuple:
        f = post_fields.get(key)
        return (label, str(f.get("value", "—")) if f else "—")

    post_event_facts = (
        _fact("source_area", "调查确认源区"),
        _fact("actual_trigger", "实际触发机制"),
        _fact("actual_disaster_chain", "实际灾害链"),
        _fact("actual_runout_km", "运动距离"),
        _fact("actual_avg_speed_mps", "平均速度"),
        _fact("actual_affected_area_km2", "影响面积"),
        _fact("actual_structures_destroyed", "损毁建筑"),
    )
    post_satellite = (
        ("灾后影像", str((pub.get("post") or {}).get("item_id", "—"))),
        ("获取时间 (UTC)", str((pub.get("post") or {}).get("datetime_utc", "—"))),
        ("云量（约）", f"{(pub.get('post') or {}).get('cloud_pct_approx', '—')}%"),
        ("分辨率", f"{(pub.get('post') or {}).get('resolution_m', '—')} m"),
    )

    fallback_state = payload.get("fallback_state") or {}
    fallback_mode = bool(
        fallback_state.get("synthesis_fallback_used")
        or fallback_state.get("critic_fallback_used")
        or any((fallback_state.get("agents_fallback_used") or {}).values())
        or any(a.fallback_used for a in agents)
    )
    provider_meta = payload.get("provider_metadata") or {}
    statuses = [
        str(v.get("provider_status") or "")
        for v in (provider_meta.get("agents") or {}).values()
    ]
    if fallback_mode:
        model_runtime = "FALLBACK"
    elif statuses and all(s == "CONNECTED" for s in statuses):
        model_runtime = "CONNECTED"
    elif statuses:
        model_runtime = "DEGRADED"
    else:
        model_runtime = "OFFLINE"

    limitations = tuple(
        dict.fromkeys(
            list(critic.scientific_limitations if critic else ())
            + list(syn_out.get("limitations") or ())
            + [risk.interpretation]
        )
    )

    return HistoricalReplayViewModel(
        case_id=str(meta.get("case_id") or case_id),
        case_name=str(meta.get("case_name") or ""),
        location=str(meta.get("location") or ""),
        event_date=str(meta.get("event_date") or ""),
        timeline=timeline,
        pre_event_evidence=pre,
        post_event_evidence=post,
        risk_index=float(risk.risk_index),
        risk_level=str(risk.risk_level),
        semantics=str(risk.semantics),
        interpretation=str(risk.interpretation),
        factors=tuple(
            (f.factor_id, f.name, f.weight_pct, f.score_0_to_5, f.contribution)
            for f in risk.factors
        ),
        top_drivers=tuple((d[0], d[1]) for d in (
            (f.name, f.contribution)
            for f in sorted(risk.factors, key=lambda x: -x.contribution)[:4]
        )),
        agents=agents,
        synthesizer=synthesizer,
        synthesis_summary=str(syn_out.get("summary") or ""),
        synthesis_agreement=str(syn_out.get("agent_agreement") or ""),
        synthesis_coverage=syn_out.get("evidence_coverage"),
        synthesis_limitations=tuple(
            str(x) for x in (syn_out.get("limitations") or ())),
        critic=critic,
        stage_b_statement=str(stage_b.statement or ""),
        stage_b_findings=tuple(str(x) for x in (stage_b.directional_findings or ())),
        stage_b_could_not_know=tuple(
            str(x) for x in (stage_b.stage_a_could_not_know or ())),
        stage_b_post_event_ids=tuple(
            str(x) for x in (stage_b.post_event_evidence_ids or ())),
        stage_a_unchanged=bool(stage_b.stage_a_unchanged),
        post_event_facts=post_event_facts,
        post_satellite=post_satellite,
        limitations=limitations,
        model_runtime=model_runtime,
        fallback_mode=fallback_mode,
        run_id=str(freeze.run_id),
        frozen_at=str(freeze.frozen_at),
    )
