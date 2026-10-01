"""
MountainGuardian G04A – UI View Models (read-only).

Doc 05 §59–§60: the UI never computes risk. It only reads structured
results produced by the frozen backend layers:

  * region identity / monitoring points  ← riskwatch.region (region.json)
  * latest valid Risk Watch result       ← riskwatch.snapshot_store (SQLite)
  * historical trend                     ← riskwatch.engine.trend query

Hard boundaries of this module:
  * NO risk recomputation — stored engine values are displayed as-is;
  * NO model provider, agent or orchestrator imports — opening a page
    must never call DeepSeek or trigger a Risk Scan (doc 06 §72);
  * NO writes to the snapshot store, ever;
  * NO fabricated data — missing values surface as explicit empty states.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from riskwatch.engine.formulas import VALID_RESULT_STATUSES, round_display
from riskwatch.engine.trend import (
    TREND_NO_HISTORY,
    HistoricalTrend,
    query_historical_trend,
)
from riskwatch.region import DEFAULT_REGION_ID, RegionConfig, load_region
from riskwatch.snapshot_store import SnapshotStore

# Frozen display names (doc 05 §61).
AGENT_DISPLAY_NAMES = {
    "glacier_geology": ("Glacier & Geology Agent", "冰川地质智能体"),
    "weather_hydrology": ("Weather & Hydrology Agent", "气象水文智能体"),
    "remote_sensing": ("Remote Sensing Agent", "遥感解译智能体"),
}
SYNTHESIZER_DISPLAY = ("Risk Synthesizer", "风险综合智能体")
CRITIC_DISPLAY = ("Critic · Reviewer", "评审智能体")

# Agent statuses that count as "executed" for the header Agents chip.
_EXECUTED_STATUSES = {"COMPLETED", "DEGRADED", "RUNNING", "PENDING"}
# Critic verdicts that mean the review actually ran.
_CRITIC_EXECUTED = {"PASS", "PASS_WITH_LIMITATIONS", "NEEDS_REVISION"}


def _counts_as_executed(card: "AgentCardVM") -> bool:
    status = card.status.upper()
    if card.key == "critic":
        return status in _CRITIC_EXECUTED
    return status in _EXECUTED_STATUSES


@dataclass(frozen=True)
class AgentCardVM:
    """One agent tile for the Overview collaboration component."""
    key: str
    name_en: str
    name_zh: str
    status: str                     # frozen status vocabulary, or critic result
    confidence: Optional[float]
    evidence_count: Optional[int]
    evidence_ids: tuple = ()
    is_ai_layer: bool = False       # synthesizer / critic (purple family)
    fallback_used: bool = False
    extra: str = ""                 # e.g. skip reason, critic severity


@dataclass(frozen=True)
class CoverageVM:
    """Evidence / data coverage for the Overview card (doc 05 §31)."""
    required_ok: Optional[int] = None
    required_total: Optional[int] = None
    optional_available: Optional[int] = None
    optional_total: Optional[int] = None
    optional_missing: tuple = ()
    point_quality: dict = field(default_factory=dict)
    satellite_pipeline_available: Optional[bool] = None
    weather_status: Optional[str] = None
    synthesis_evidence_coverage: Optional[float] = None


@dataclass(frozen=True)
class TrendPointVM:
    created_at: str
    risk_index_rounded: float
    risk_level: str
    risk_direction: str
    status: str
    scan_mode: str


@dataclass(frozen=True)
class OverviewViewModel:
    """Everything the Overview page renders — assembled once, read-only."""
    region_id: str
    region_name: str
    region_name_zh: str
    region_label: str               # short header label, e.g. 西藏 · 吉隆口岸
    monitoring_points: tuple        # (point_id, name, lat, lon, elevation, uncertainty_km)
    data_source_count: int

    has_result: bool
    # current risk (stored engine values — never recomputed)
    risk_index_rounded: Optional[float]
    risk_level: Optional[str]
    risk_direction: Optional[str]
    trend_delta: Optional[float]    # vs previous valid snapshot, when known
    last_updated: Optional[str]     # ISO timestamp of latest valid result
    last_scan_status: Optional[str]
    last_scan_mode: Optional[str]
    run_id: Optional[str]
    top_drivers: tuple              # (label, contribution_points_rounded, driver_type)

    agents: tuple                   # AgentCardVM in presentation order
    agents_executed: int
    agents_total: int
    model_runtime: str              # CONNECTED / FALLBACK / OFFLINE / UNKNOWN
    fallback_mode: bool
    critic_result: Optional[str]

    coverage: CoverageVM
    trend_status: str               # HistoricalTrend status vocabulary
    trend_points: tuple             # TrendPointVM, chronological

    limitations: tuple = ()

    @property
    def system_state(self) -> str:
        """Bottom-of-nav system chip: ONLINE / DEGRADED / NO DATA."""
        if not self.has_result:
            return "NO DATA"
        if self.fallback_mode or any(
            a.status in ("DEGRADED", "FAILED") for a in self.agents
        ) or str(self.last_scan_status) == "COMPLETED_WITH_LIMITATIONS":
            return "DEGRADED"
        return "ONLINE"


def _uncertainty_km(point) -> Optional[float]:
    prov = point.coordinate_provenance or {}
    value = prov.get("uncertainty_km")
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _latest_valid_snapshot(store: SnapshotStore, region_id: str) -> Optional[dict]:
    """Most recent valid, completed Risk Watch RESULT snapshot (read-only).

    Data-only snapshots (status OK / DATA_OK) and invalidated rows never
    qualify — same frozen semantics as riskwatch.engine.trend.
    """
    best: Optional[dict] = None
    for row in store.list_snapshots(region_id):
        if int(row.get("is_invalid", 0) or 0) != 0:
            continue
        if str(row.get("status", "")) not in VALID_RESULT_STATUSES:
            continue
        payload = row.get("payload")
        if not isinstance(payload, dict):
            continue
        value = payload.get("current_risk_index", payload.get("C"))
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        if best is None or row.get("id", 0) > best.get("id", 0):
            best = row
    return best


def _agent_cards(payload: dict) -> tuple:
    cards: list[AgentCardVM] = []
    results = payload.get("agent_results") or {}
    for key in ("glacier_geology", "weather_hydrology", "remote_sensing"):
        name_en, name_zh = AGENT_DISPLAY_NAMES[key]
        entry = results.get(key) or {}
        out = entry.get("output") or {}
        evidence_ids = tuple(out.get("evidence_ids") or ())
        extra = ""
        status = str(out.get("status") or "PENDING")
        if status == "SKIPPED" and out.get("skip_reason"):
            extra = str(out["skip_reason"]).replace("_", " ").lower()
        if out.get("fallback_used"):
            extra = (extra + " · " if extra else "") + "deterministic fallback"
        cards.append(AgentCardVM(
            key=key, name_en=name_en, name_zh=name_zh,
            status=status,
            confidence=out.get("confidence"),
            evidence_count=len(evidence_ids),
            evidence_ids=evidence_ids,
            fallback_used=bool(out.get("fallback_used")),
            extra=extra,
        ))

    # AI layer: synthesizer → critic (doc 03 / doc 05 §13).
    ai = payload.get("ai_layer") or {}
    syn_out = (payload.get("synthesis") or {}).get("output") or {}
    syn_ids = tuple(syn_out.get("evidence_ids") or ())
    syn_status = str(ai.get("synthesis_status") or "PENDING")
    cards.append(AgentCardVM(
        key="synthesizer",
        name_en=SYNTHESIZER_DISPLAY[0], name_zh=SYNTHESIZER_DISPLAY[1],
        status=syn_status,
        confidence=syn_out.get("explanation_confidence"),
        evidence_count=len(syn_ids),
        evidence_ids=syn_ids,
        is_ai_layer=True,
        fallback_used=bool(syn_out.get("fallback_used")),
        extra="deterministic fallback" if syn_out.get("fallback_used") else "",
    ))

    critic_out = (payload.get("critic") or {}).get("verdict") or {}
    critic_status = str(
        critic_out.get("review_result")
        or ai.get("critic_status")
        or "UNAVAILABLE"
    )
    severity = critic_out.get("severity")
    cards.append(AgentCardVM(
        key="critic",
        name_en=CRITIC_DISPLAY[0], name_zh=CRITIC_DISPLAY[1],
        status=critic_status,
        confidence=None,            # critic publishes verdicts, not confidence
        evidence_count=None,
        is_ai_layer=True,
        fallback_used=bool(critic_out.get("fallback_used")),
        extra=f"severity {severity}" if severity else "",
    ))
    return tuple(cards)


def _coverage(payload: dict) -> CoverageVM:
    dq = payload.get("data_quality") or {}
    req = dq.get("required_coverage") or {}
    opt = dq.get("optional_coverage") or {}
    syn_out = (payload.get("synthesis") or {}).get("output") or {}
    return CoverageVM(
        required_ok=req.get("ok"),
        required_total=req.get("total"),
        optional_available=opt.get("available"),
        optional_total=opt.get("total"),
        optional_missing=tuple(opt.get("missing") or ()),
        point_quality=dict(dq.get("point_quality") or {}),
        satellite_pipeline_available=dq.get("satellite_pipeline_available"),
        weather_status=dq.get("weather_status"),
        synthesis_evidence_coverage=syn_out.get("evidence_coverage"),
    )


def _top_drivers(payload: dict, limit: int = 4) -> tuple:
    det = payload.get("deterministic_result") or {}
    drivers = det.get("top_drivers") or []
    out = []
    for d in drivers[:limit]:
        out.append((
            str(d.get("label", "")),
            d.get("contribution_points_rounded"),
            str(d.get("driver_type", "")),
        ))
    return tuple(out)


def _trend_delta(trend: HistoricalTrend) -> tuple:
    """(direction, delta) for the newest valid entry — from the frozen
    trend query only; never recomputed in the UI."""
    if len(trend.entries) < 2:
        return (TREND_NO_HISTORY, None)
    last, prev = trend.entries[-1], trend.entries[-2]
    delta = round_display(last.current_risk_index - prev.current_risk_index)
    return (last.risk_direction, delta)


def _model_runtime(payload: Optional[dict], fallback_mode: bool) -> str:
    if payload is None:
        return "UNKNOWN"
    ai = payload.get("ai_layer") or {}
    if ai.get("status") != "EXECUTED":
        return "OFFLINE"
    if fallback_mode:
        return "FALLBACK"
    audits = [
        ((payload.get(k) or {}).get("audit") or {}).get("provider_status")
        for k in ("synthesis", "critic")
    ]
    if audits and all(a == "CONNECTED" for a in audits):
        return "CONNECTED"
    return "DEGRADED"


def build_overview_viewmodel(
    region_id: str = DEFAULT_REGION_ID,
    db_path: Path | str | None = None,
    region: Optional[RegionConfig] = None,
    store: Optional[SnapshotStore] = None,
) -> OverviewViewModel:
    """Assemble the Overview view model. Pure reads; safe on every rerun."""
    region = region or load_region(region_id)
    own_store = store is None
    store = store or SnapshotStore(db_path)
    try:
        row = _latest_valid_snapshot(store, region_id)
        trend = query_historical_trend(store, region_id)
    finally:
        if own_store:
            store.close()

    points = tuple(
        (p.point_id, p.name, p.latitude, p.longitude, p.elevation_m,
         _uncertainty_km(p))
        for p in region.monitoring_points
    )
    data_source_count = len(region.data.get("source_references") or ())
    region_name = str(region.data.get("region_name") or region.region_id)
    region_name_zh = str(region.data.get("region_name_zh") or "")
    region_label = region_name_zh or region_name

    if row is None:
        return OverviewViewModel(
            region_id=region.region_id,
            region_name=region_name,
            region_name_zh=region_name_zh,
            region_label=region_label,
            monitoring_points=points,
            data_source_count=data_source_count,
            has_result=False,
            risk_index_rounded=None, risk_level=None, risk_direction=None,
            trend_delta=None, last_updated=None, last_scan_status=None,
            last_scan_mode=None, run_id=None, top_drivers=(),
            agents=(), agents_executed=0, agents_total=5,
            model_runtime="UNKNOWN", fallback_mode=False, critic_result=None,
            coverage=CoverageVM(),
            trend_status=trend.status, trend_points=(),
        )

    payload: dict[str, Any] = row["payload"]
    agents = _agent_cards(payload)
    executed = sum(1 for a in agents if _counts_as_executed(a))
    fallback_mode = any(a.fallback_used for a in agents)
    direction, delta = _trend_delta(trend)

    det = payload.get("deterministic_result") or {}
    display = det.get("display") or {}
    risk_index = payload.get("current_risk_index", payload.get("C"))
    risk_index_rounded = display.get("C", round_display(float(risk_index)))

    trend_points = tuple(
        TrendPointVM(
            created_at=e.created_at,
            risk_index_rounded=e.current_risk_index_rounded,
            risk_level=e.risk_level,
            risk_direction=e.risk_direction,
            status=e.status,
            scan_mode=e.scan_mode,
        )
        for e in trend.entries
    )

    return OverviewViewModel(
        region_id=region.region_id,
        region_name=region_name,
        region_name_zh=region_name_zh,
        region_label=region_label,
        monitoring_points=points,
        data_source_count=data_source_count,
        has_result=True,
        risk_index_rounded=risk_index_rounded,
        risk_level=str(payload.get("current_risk_level") or ""),
        risk_direction=direction,
        trend_delta=delta,
        last_updated=str(row.get("created_at") or ""),
        last_scan_status=str(row.get("status") or ""),
        last_scan_mode=str(row.get("scan_mode") or ""),
        run_id=str(payload.get("run_id") or row.get("run_id") or ""),
        top_drivers=_top_drivers(payload),
        agents=agents,
        agents_executed=executed,
        agents_total=len(agents),
        model_runtime=_model_runtime(payload, fallback_mode),
        fallback_mode=fallback_mode,
        critic_result=str(payload.get("critic_status") or "") or None,
        coverage=_coverage(payload),
        trend_status=trend.status,
        trend_points=trend_points,
        limitations=tuple(payload.get("limitations") or ()),
    )
