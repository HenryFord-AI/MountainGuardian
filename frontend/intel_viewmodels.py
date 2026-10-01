"""
MountainGuardian G04B – Intelligence Center view model (read-only).

Doc 05 §32–§37 / doc 03 §2–§3: AI system observability, explainability,
evidence provenance and audit & safety. This is NOT a chatbot surface and
exposes NO chain of thought, NO system prompts, NO provider secrets.

Data sources (all existing contracts, read-only):
  * latest Risk Watch result snapshot  ← riskwatch.snapshot_store
  * run history (audit log rows)       ← riskwatch.snapshot_store
  * per-run agent / synthesis / critic audit records ← snapshot payload
  * Evidence provenance pool           ← tools.case_loader + schemas.evidence
  * frozen safety-control architecture ← descriptive indicators bound to
    their real enforcement modules; per-run guard signals come from the
    persisted critic programmatic checks and quarantine counts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from riskwatch.region import DEFAULT_REGION_ID, RegionConfig, load_region
from riskwatch.snapshot_store import SnapshotStore
from schemas.evidence import (
    TYPE_CLIMATE_CONTEXT,
    TYPE_CRYOSPHERE,
    TYPE_GEOLOGY,
    TYPE_HISTORICAL_EVENT,
    TYPE_HYDROLOGY_STATIC,
    TYPE_RS_IMAGE,
    TYPE_RS_METADATA,
    TYPE_TERRAIN,
    TYPE_WEATHER_CONTEXT,
    build_evidence_pool,
)
from schemas.synthesis import CRITIC_CHECK_IDS
from tools.case_loader import load_case

from frontend.viewmodels import (
    AGENT_DISPLAY_NAMES,
    CRITIC_DISPLAY,
    SYNTHESIZER_DISPLAY,
    _latest_valid_snapshot,
)

# Evidence Center categories (doc 05 §34) mapped to frozen evidence types.
EVIDENCE_CATEGORIES = (
    ("Satellite", "卫星遥感", (TYPE_RS_IMAGE, TYPE_RS_METADATA)),
    ("Weather", "气象", (TYPE_WEATHER_CONTEXT, TYPE_CLIMATE_CONTEXT)),
    ("Terrain", "地形地质", (TYPE_TERRAIN, TYPE_GEOLOGY)),
    ("Cryosphere", "冰冻圈", (TYPE_CRYOSPHERE,)),
    ("Historical", "历史事件", (TYPE_HISTORICAL_EVENT,)),
    ("Hydrology", "水文", (TYPE_HYDROLOGY_STATIC,)),
)

# Frozen safety controls (doc 03 §2 外围 Guard, doc 06 §76–§77) with their
# real enforcement points in the codebase. Descriptive ONLY — the product
# exposes no control that can disable any of these protections.
SAFETY_CONTROLS = (
    ("Prompt Injection Guard",
     "agents/professional_base.py — 不可信证据文本隔离（quarantine）"),
    ("Data Leakage Guard",
     "orchestration/context_builder.py — 灾后证据硬性排除于灾前上下文"),
    ("Post-event Leakage Guard",
     "Critic 程序化检查 POST_EVENT_LEAKAGE（每次运行）"),
    ("Output Schema Validation",
     "schemas/agent_outputs.py + schemas/synthesis.py — 每次模型调用后校验"),
    ("External Actions Disabled",
     "v1.0 Agent 无工具 / 无外部写入面（doc 03 §3）"),
)


@dataclass(frozen=True)
class IntelAgentVM:
    key: str
    name_en: str
    name_zh: str
    status: str
    confidence: Optional[float]
    evidence_ids: tuple
    findings: tuple
    missing_data: tuple
    limitations: tuple
    model_id: str
    provider: str
    provider_status: str
    latency_ms: Optional[int]
    fallback_used: bool
    is_model_output: bool
    quarantined: tuple
    is_ai_layer: bool = False
    input_summary: str = ""


@dataclass(frozen=True)
class IntelEvidenceVM:
    evidence_id: str
    evidence_type: str
    source: str
    source_reference: str
    observed: str
    phase: str
    quality: str
    raw_or_derived: str
    used_by: tuple
    summary: str


@dataclass(frozen=True)
class IntelCriticVM:
    review_result: str
    severity: str
    issues: tuple
    scientific_limitations: tuple
    required_corrections: tuple
    programmatic_checks: tuple
    risk_index_before: Optional[float]
    risk_index_after: Optional[float]
    fallback_used: bool


@dataclass(frozen=True)
class IntelligenceViewModel:
    region_label: str
    has_run: bool
    run_id: str
    created_at: str
    scan_status: str
    scan_mode: str
    duration_s: Optional[float]
    model_runtime: str
    fallback_mode: bool

    agents: tuple                 # IntelAgentVM (3 professional + AI layer)
    critic: Optional[IntelCriticVM]
    risk_index_rounded: Optional[float]
    risk_level: Optional[str]
    outlook_index_rounded: Optional[float]
    outlook_level: Optional[str]

    evidence_categories: tuple    # (label_en, label_zh, tuple[IntelEvidenceVM])
    run_history: tuple            # (run_id, created_at, status, scan_mode)
    audit_rows: tuple             # (ts, run_id, agent, model, status, latency, fallback)
    safety_rows: tuple            # (name, state, color_key, detail)

    @property
    def system_state(self) -> str:
        if not self.has_run:
            return "NO DATA"
        if self.fallback_mode or any(
            a.status in ("DEGRADED", "FAILED") for a in self.agents
        ):
            return "DEGRADED"
        return "ONLINE"


def _agent_detail(key: str, name_en: str, name_zh: str, entry: dict,
                  is_ai_layer: bool = False) -> IntelAgentVM:
    out = entry.get("output") or {}
    audit = entry.get("audit") or {}
    evidence_ids = tuple(out.get("evidence_ids") or ())
    return IntelAgentVM(
        key=key, name_en=name_en, name_zh=name_zh,
        status=str(out.get("status") or "PENDING"),
        confidence=out.get("confidence", out.get("explanation_confidence")),
        evidence_ids=evidence_ids,
        findings=tuple(str(x) for x in (out.get("key_findings")
                                        or ([out["summary"]] if out.get("summary") else []))),
        missing_data=tuple(str(x) for x in (out.get("missing_data") or ())),
        limitations=tuple(str(x) for x in (out.get("limitations") or ())),
        model_id=str(audit.get("model_id") or "—"),
        provider=str(audit.get("provider") or "—"),
        provider_status=str(audit.get("provider_status") or "UNKNOWN"),
        latency_ms=audit.get("latency_ms"),
        fallback_used=bool(out.get("fallback_used")),
        is_model_output=bool(out.get("is_model_output")),
        quarantined=tuple(audit.get("quarantined_evidence_ids") or ()),
        is_ai_layer=is_ai_layer,
        input_summary=str(audit.get("input_evidence_ids") and
                          f"{len(audit.get('input_evidence_ids') or ())} evidence ids authorized"
                          or ""),
    )


def build_intelligence_viewmodel(
    region_id: str = DEFAULT_REGION_ID,
    db_path: Path | str | None = None,
    region: Optional[RegionConfig] = None,
    store: Optional[SnapshotStore] = None,
    case_id: str = "jilong_20260826",
) -> IntelligenceViewModel:
    """Assemble the Intelligence Center view model. Pure reads."""
    region = region or load_region(region_id)
    region_label = str(region.data.get("region_name_zh")
                       or region.data.get("region_name") or region.region_id)

    # Evidence provenance pool (frozen Case Pack EvidenceItems).
    categories: list[tuple] = []
    try:
        pool = build_evidence_pool(load_case(case_id))
    except Exception:
        pool = []
    for label_en, label_zh, types in EVIDENCE_CATEGORIES:
        items = tuple(
            IntelEvidenceVM(
                evidence_id=item.evidence_id,
                evidence_type=str(item.evidence_type),
                source=str(item.source_name or "—"),
                source_reference=str(item.source_reference or "—"),
                observed=str(item.observation_time or "—"),
                phase=str(item.phase),
                quality=str(item.quality.value if hasattr(item.quality, "value")
                            else item.quality),
                raw_or_derived=str(item.raw_or_derived or "—"),
                used_by=tuple(item.allowed_agents or ()),
                summary=str(item.summary or ""),
            )
            for item in pool if item.evidence_type in types
        )
        categories.append((label_en, label_zh, items))

    own_store = store is None
    store = store or SnapshotStore(db_path)
    try:
        rows = store.list_snapshots(region_id)
        row = _latest_valid_snapshot(store, region_id)
    finally:
        if own_store:
            store.close()

    history = tuple(
        (str(r.get("run_id") or ""), str(r.get("created_at") or ""),
         str(r.get("status") or ""), str(r.get("scan_mode") or ""))
        for r in rows[-8:][::-1]
    )

    if row is None:
        return IntelligenceViewModel(
            region_label=region_label,
            has_run=False, run_id="", created_at="", scan_status="",
            scan_mode="", duration_s=None, model_runtime="UNKNOWN",
            fallback_mode=False, agents=(), critic=None,
            risk_index_rounded=None, risk_level=None,
            outlook_index_rounded=None, outlook_level=None,
            evidence_categories=tuple(categories),
            run_history=history, audit_rows=(),
            safety_rows=tuple(
                (name, "ENFORCED", "GREEN", detail)
                for name, detail in SAFETY_CONTROLS
            ),
        )

    payload: dict[str, Any] = row["payload"]
    agent_results = payload.get("agent_results") or {}
    agents = [
        _agent_detail(key, AGENT_DISPLAY_NAMES[key][0], AGENT_DISPLAY_NAMES[key][1],
                      agent_results.get(key) or {})
        for key in ("glacier_geology", "weather_hydrology", "remote_sensing")
    ]
    syn_entry = payload.get("synthesis") or {}
    if syn_entry:
        agents.append(_agent_detail(
            "synthesizer", SYNTHESIZER_DISPLAY[0], SYNTHESIZER_DISPLAY[1],
            syn_entry, is_ai_layer=True))
    critic_raw = (payload.get("critic") or {}).get("verdict") or {}
    critic = None
    failed_checks = dict(critic_raw.get("programmatic_check_status") or {})
    if critic_raw:
        critic = IntelCriticVM(
            review_result=str(critic_raw.get("review_result") or "UNAVAILABLE"),
            severity=str(critic_raw.get("severity") or ""),
            issues=tuple(
                (str(i.get("check_id", "")), str(i.get("severity", "")),
                 str(i.get("message", "")))
                for i in (critic_raw.get("issues") or ())),
            scientific_limitations=tuple(
                str(x) for x in (critic_raw.get("scientific_limitations") or ())),
            required_corrections=tuple(
                str(x) for x in (critic_raw.get("required_corrections") or ())),
            programmatic_checks=tuple(
                (str(cid), str(cid) not in failed_checks)
                for cid in CRITIC_CHECK_IDS),
            risk_index_before=critic_raw.get("risk_index_before"),
            risk_index_after=critic_raw.get("risk_index_after"),
            fallback_used=bool(critic_raw.get("fallback_used")),
        )
        agents.append(IntelAgentVM(
            key="critic", name_en=CRITIC_DISPLAY[0], name_zh=CRITIC_DISPLAY[1],
            status=str(critic_raw.get("review_result") or "UNAVAILABLE"),
            confidence=None, evidence_ids=(), findings=(),
            missing_data=(),
            limitations=critic.scientific_limitations,
            model_id=str(((payload.get("critic") or {}).get("audit") or {}).get("model_id") or "—"),
            provider=str(((payload.get("critic") or {}).get("audit") or {}).get("provider") or "—"),
            provider_status=str(((payload.get("critic") or {}).get("audit") or {}).get("provider_status") or "UNKNOWN"),
            latency_ms=((payload.get("critic") or {}).get("audit") or {}).get("latency_ms"),
            fallback_used=critic.fallback_used,
            is_model_output=bool(critic_raw.get("is_model_output")),
            quarantined=(), is_ai_layer=True,
        ))

    # Audit rows: per-agent / AI-layer audit records of the latest run.
    audit_rows: list[tuple] = []
    for a in agents:
        audit_rows.append((
            str(row.get("created_at") or "")[:19].replace("T", " "),
            str(payload.get("run_id") or row.get("run_id") or "")[:24],
            a.name_en, a.model_id, a.status,
            f"{a.latency_ms} ms" if a.latency_ms is not None else "—",
            "yes" if a.fallback_used else "no",
        ))

    # Safety rows: frozen controls + per-run guard signals from this snapshot.
    quarantined_total = sum(len(a.quarantined) for a in agents)
    # Per-run Critic guards (Risk Index — not event probability):
    prob_ok = "PROBABILITY_MISUSE" not in failed_checks
    leak_ok = "POST_EVENT_LEAKAGE" not in failed_checks
    safety_rows = (
        (SAFETY_CONTROLS[0][0], "ACTIVE", "GREEN",
         SAFETY_CONTROLS[0][1] + f" · 本轮隔离证据 {quarantined_total} 条"),
        (SAFETY_CONTROLS[1][0], "ACTIVE", "GREEN", SAFETY_CONTROLS[1][1]),
        (SAFETY_CONTROLS[2][0],
         "PASS" if leak_ok else "FLAGGED",
         "GREEN" if leak_ok else "RED",
         SAFETY_CONTROLS[2][1] + (" · 本轮检查通过" if leak_ok else " · 本轮检查发现问题")),
        (SAFETY_CONTROLS[3][0],
         "PASS" if prob_ok else "FLAGGED",
         "GREEN" if prob_ok else "RED",
         SAFETY_CONTROLS[3][1] + (" · 表述误用检查通过" if prob_ok else " · 表述误用检查发现问题")),
        (SAFETY_CONTROLS[4][0], "DISABLED BY DESIGN", "CYAN",
         SAFETY_CONTROLS[4][1]),
    )

    stamps = [str(e[1]) for e in (payload.get("stage_trace") or ())
              if isinstance(e, (list, tuple)) and len(e) >= 2]
    duration: Optional[float] = None
    if len(stamps) >= 2:
        from datetime import datetime

        try:
            duration = round((datetime.fromisoformat(stamps[-1])
                              - datetime.fromisoformat(stamps[0])).total_seconds(), 1)
        except ValueError:
            duration = None

    fallback_mode = any(a.fallback_used for a in agents)
    audits = [a.provider_status for a in agents]
    if fallback_mode:
        runtime = "FALLBACK"
    elif audits and all(s == "CONNECTED" for s in audits):
        runtime = "CONNECTED"
    elif audits:
        runtime = "DEGRADED"
    else:
        runtime = "OFFLINE"

    engine = payload.get("deterministic_result") or {}
    display = engine.get("display") or {}
    c_raw = payload.get("current_risk_index", payload.get("C"))
    o7_raw = payload.get("outlook_7d_index", engine.get("O7"))

    return IntelligenceViewModel(
        region_label=region_label,
        has_run=True,
        run_id=str(payload.get("run_id") or row.get("run_id") or ""),
        created_at=str(row.get("created_at") or ""),
        scan_status=str(row.get("status") or ""),
        scan_mode=str(row.get("scan_mode") or ""),
        duration_s=duration,
        model_runtime=runtime,
        fallback_mode=fallback_mode,
        agents=tuple(agents),
        critic=critic,
        risk_index_rounded=(
            display.get("C") if display.get("C") is not None
            else (round(float(c_raw), 2) if isinstance(c_raw, (int, float))
                  and not isinstance(c_raw, bool) else None)),
        risk_level=str(payload.get("current_risk_level") or "") or None,
        outlook_index_rounded=(
            display.get("O7") if display.get("O7") is not None
            else (round(float(o7_raw), 2) if isinstance(o7_raw, (int, float))
                  and not isinstance(o7_raw, bool) else None)),
        outlook_level=str(payload.get("outlook_7d_level") or "") or None,
        evidence_categories=tuple(categories),
        run_history=history,
        audit_rows=tuple(audit_rows),
        safety_rows=safety_rows,
    )
