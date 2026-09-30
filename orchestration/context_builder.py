"""
MountainGuardian v1.0 – AnalysisContext builder.

Frozen design references:
  - 03_MountainGuardian_AI_Agent_Architecture_v1.0.md §7 (AnalysisContext),
    §25 (prompts do NOT carry safety boundaries — isolation happens in
    Data Loader / Context Builder / Agent Input Schema BEFORE the model
    call), §26 (Minimum Necessary Context)
  - 02_MountainGuardian_Scientific_Data_Baseline_v1.0.md §5 (Data Leakage
    red line, implementation priority: loader partitions by phase →
    context builder trims per agent → agent input schema excludes
    post-event → automated tests), §19 (missing data is explicit)

This module is the PRIMARY programmatic phase filter for the professional
agents. In historical_replay risk-analysis mode:

  * post_event_validation evidence is physically excluded from the
    AnalysisContext — it never reaches any agent view or prompt;
  * context_only (ENSO) evidence is kept in a separate bucket that only
    the Weather / Hydrology Agent may see, as background, never causal;
  * each agent view is further trimmed to evidence authorized for that
    agent's professional scope (minimum necessary context);
  * missing inputs and scientific/safety boundaries are represented
    explicitly, never filled in.

Risk Watch mode is declared for interface completeness but intentionally
not populated in G02A (Risk Watch is a later gate).
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from schemas.evidence import (
    AGENT_GLACIER_GEOLOGY,
    AGENT_REMOTE_SENSING,
    AGENT_WEATHER_HYDROLOGY,
    BOUNDARY_PHASES,
    CONTEXT_ONLY_PHASES,
    POST_EVENT_PHASES,
    PRE_EVENT_RISK_PHASES,
    EvidenceItem,
    EvidenceQuality,
    build_evidence_pool,
)

logger = logging.getLogger(__name__)

MODE_HISTORICAL_REPLAY = "historical_replay"
MODE_RISK_WATCH = "risk_watch"

#: Frozen scientific constraints injected into every professional agent
#: context (doc 03 §24.E). Prompts repeat them, but they are listed here
#: so tests and the UI can rely on them structurally.
BASE_SCIENTIFIC_CONSTRAINTS = (
    "Risk Index 仅由确定性风险引擎计算；专业 Agent 不得自行计算或修改 Risk Index。",
    "Risk Index 与 confidence 都不是灾害发生概率。",
    "不得补造缺失数据；缺失必须作为 missing_data 显式输出。",
    "ENSO / 气候背景只能作为背景解释，不得包装为具体事件的直接触发因果。",
    "不得引用或推测灾后（post-event）验证信息。",
    "关键结论必须能够回指被授权 Evidence 的 evidence_id。",
)


class PhaseSafetyError(RuntimeError):
    """Raised when post-event evidence is detected where it is forbidden.

    Raised BEFORE any provider invocation (doc 03 §25).
    """


@dataclass
class AnalysisContext:
    """Controlled per-run context (doc 03 §7). Agents never read the whole
    Case Pack or database — only this object."""

    run_id: str
    mode: str
    region_id: str
    analysis_time: str
    case_metadata: dict = field(default_factory=dict)
    #: pre-event evidence only (in historical_replay mode)
    allowed_evidence: list = field(default_factory=list)
    #: context_only background (ENSO etc.) — weather/hydrology agent only
    context_only_evidence: list = field(default_factory=list)
    #: explicit missing-data representation (phase missing_input / MISSING)
    missing_sources: list = field(default_factory=list)
    #: scientific / safety boundary statements from the Case Pack
    scientific_constraints: list = field(default_factory=list)
    #: pre-event satellite imagery evidence authorized for Remote Sensing
    pre_event_imagery: list = field(default_factory=list)

    def evidence_by_id(self) -> dict:
        by_id = {}
        for bucket in (self.allowed_evidence, self.context_only_evidence,
                       self.missing_sources, self.pre_event_imagery):
            for item in bucket:
                by_id[item.evidence_id] = item
        return by_id

    def assert_no_post_event(self) -> None:
        """Structural self-check: the context must not contain post-event
        evidence in any agent-consumable bucket."""
        for bucket_name, bucket in (
                ("allowed_evidence", self.allowed_evidence),
                ("context_only_evidence", self.context_only_evidence),
                ("pre_event_imagery", self.pre_event_imagery)):
            for item in bucket:
                if item.phase in POST_EVENT_PHASES:
                    raise PhaseSafetyError(
                        f"post-event evidence {item.evidence_id!r} found in "
                        f"AnalysisContext.{bucket_name}")


@dataclass
class AgentEvidenceView:
    """The minimum-necessary slice of an AnalysisContext for ONE agent."""

    agent_name: str
    run_id: str
    mode: str
    case_metadata: dict
    evidence: list                       # authorized analysis evidence
    background_evidence: list            # context_only (weather agent only)
    missing_sources: list                # explicit gaps
    constraints: list                    # scientific constraints (strings)
    pre_event_imagery: list              # RS agent only

    def allowed_evidence_ids(self) -> frozenset:
        ids = set()
        for bucket in (self.evidence, self.background_evidence,
                       self.missing_sources, self.pre_event_imagery):
            for item in bucket:
                ids.add(item.evidence_id)
        return frozenset(ids)

    def all_items(self) -> list:
        return list(self.evidence) + list(self.background_evidence) \
            + list(self.missing_sources) + list(self.pre_event_imagery)

    def assert_no_post_event(self) -> None:
        for item in self.all_items():
            if item.phase in POST_EVENT_PHASES:
                raise PhaseSafetyError(
                    f"post-event evidence {item.evidence_id!r} reached agent "
                    f"{self.agent_name!r} input view")


def build_analysis_context(case: Optional[dict] = None,
                           mode: str = MODE_HISTORICAL_REPLAY,
                           run_id: Optional[str] = None) -> AnalysisContext:
    """Build the controlled AnalysisContext for one run.

    Phase filtering happens HERE, in code, before any agent or provider
    sees the data (doc 02 §5.3 priority 1–2).
    """
    if mode not in (MODE_HISTORICAL_REPLAY, MODE_RISK_WATCH):
        raise ValueError(f"unknown mode {mode!r}")
    if mode == MODE_RISK_WATCH:
        raise NotImplementedError(
            "Risk Watch context building is out of G02A scope (later gate).")

    if case is None:
        from tools.case_loader import load_case
        case = load_case()

    pool = build_evidence_pool(case)
    meta = dict(case.get("meta") or {})

    allowed: list = []
    context_only: list = []
    missing: list = []
    imagery: list = []
    constraint_texts: list = list(BASE_SCIENTIFIC_CONSTRAINTS)

    for item in pool:
        if item.phase in POST_EVENT_PHASES:
            # Hard exclusion: post-event evidence never enters the analysis
            # context in replay mode. It remains in the Case Pack for the
            # future Validation stage (G02B) only.
            continue
        if item.phase in CONTEXT_ONLY_PHASES:
            if AGENT_WEATHER_HYDROLOGY in item.allowed_agents:
                context_only.append(item)
            continue
        if item.phase == "missing_input" or \
                item.quality == EvidenceQuality.MISSING.value:
            missing.append(item)
            continue
        if item.phase in ("scientific_boundary", "safety_boundary"):
            text = f"{item.summary}：{item.value}" if item.value else item.summary
            constraint_texts.append(text)
            continue
        if item.phase in BOUNDARY_PHASES:  # design_input etc.
            continue
        if item.phase in PRE_EVENT_RISK_PHASES:
            if item.evidence_type == "remote_sensing_image":
                imagery.append(item)
            elif item.allowed_agents:
                allowed.append(item)
            # pre-event items with no authorized agent (unknown keys,
            # metadata-ish) are conservatively dropped from agent views.
            continue
        # metadata phase → not agent evidence (case_metadata covers it)

    ctx = AnalysisContext(
        run_id=run_id or f"run-{uuid.uuid4().hex[:12]}",
        mode=mode,
        region_id=str(meta.get("case_id") or ""),
        analysis_time=datetime.now(timezone.utc).isoformat(),
        case_metadata={
            "case_id": meta.get("case_id", ""),
            "case_name": meta.get("case_name", ""),
            "location": meta.get("location", ""),
            "lat": meta.get("lat", ""),
            "lon": meta.get("lon", ""),
            "event_date": meta.get("event_date", ""),
            "pack_version": meta.get("pack_version", ""),
        },
        allowed_evidence=allowed,
        context_only_evidence=context_only,
        missing_sources=missing,
        scientific_constraints=constraint_texts,
        pre_event_imagery=imagery,
    )
    ctx.assert_no_post_event()
    logger.info(
        "[context_builder] run=%s mode=%s evidence=%d context_only=%d "
        "missing=%d imagery=%d (post-event excluded)",
        ctx.run_id, ctx.mode, len(allowed), len(context_only),
        len(missing), len(imagery))
    return ctx


def agent_evidence_view(ctx: AnalysisContext, agent_name: str,
                        ) -> AgentEvidenceView:
    """Trim the AnalysisContext to the minimum necessary slice for one
    professional agent (doc 03 §26). Re-filters by phase as defense in
    depth: even a tampered context cannot pass post-event evidence here.
    """
    if agent_name not in (AGENT_GLACIER_GEOLOGY, AGENT_WEATHER_HYDROLOGY,
                          AGENT_REMOTE_SENSING):
        raise ValueError(f"unknown professional agent {agent_name!r}")

    def _safe(items):
        out = []
        for it in items:
            if it.phase in POST_EVENT_PHASES:
                raise PhaseSafetyError(
                    f"post-event evidence {it.evidence_id!r} blocked while "
                    f"building view for {agent_name!r}")
            out.append(it)
        return out

    evidence = _safe([e for e in ctx.allowed_evidence
                      if agent_name in e.allowed_agents])
    background = []
    if agent_name == AGENT_WEATHER_HYDROLOGY:
        background = _safe([e for e in ctx.context_only_evidence
                            if agent_name in e.allowed_agents])
    missing = _safe([m for m in ctx.missing_sources
                     if agent_name in m.allowed_agents])
    imagery = []
    if agent_name == AGENT_REMOTE_SENSING:
        imagery = _safe([e for e in ctx.pre_event_imagery
                         if agent_name in e.allowed_agents
                         and e.phase in PRE_EVENT_RISK_PHASES])

    view = AgentEvidenceView(
        agent_name=agent_name,
        run_id=ctx.run_id,
        mode=ctx.mode,
        case_metadata=dict(ctx.case_metadata),
        evidence=evidence,
        background_evidence=background,
        missing_sources=missing,
        constraints=list(ctx.scientific_constraints),
        pre_event_imagery=imagery,
    )
    view.assert_no_post_event()
    return view
