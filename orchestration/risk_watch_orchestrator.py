"""
MountainGuardian G03C – Risk Watch end-to-end workflow orchestrator.

Connects the frozen G03A data foundation and G03B deterministic engine with
the G02A professional agents and G02B synthesis/critic into ONE auditable
execution pipeline (doc 04 §29/§36-§39, doc 03 §36.2, doc 07 §17):

    run_risk_scan(region_id)

    Step 1  Load Region Config              (G03A riskwatch.region)
    Step 2  Collect current weather         (G03A WeatherCollector + cache)
    Step 3  Validate data quality           (deterministic quality summary)
    Step 4  Create immutable data Snapshot  (G03A SnapshotStore, insert-only)
    Step 5  Run G03B deterministic engine   (compute_risk_watch — CALLED,
                                             never reimplemented)
    Step 6  Prepare evidence package        (AnalysisContext, mode=risk_watch)
    Step 7  Invoke Professional Agents      (G02A, isolated failures)
    Step 8  Invoke Risk Synthesizer         (G02B specialization)
    Step 9  Invoke Critic                   (G02B specialization + doc 04 §43)
    Step 10 Persist final Risk Watch result (immutable result snapshot)

Two-layer architecture (gate G03C §5):
  Layer 1 (authoritative): G03A data + G03B formulas → B/R/F/D/C/O7 + bands.
  Layer 2 (interpretation): agents / synthesizer / critic explain and check;
  they NEVER change C, O7 or any Risk Level — enforced by the G02B
  validators, by the read-only adapter and by the workflow tests.

Hard boundaries:
  * no Historical Replay Case Pack is ever loaded (Risk Watch reads only
    data/regions/<region_id>/region.json + live weather + climatology);
  * no risk formula is duplicated here — the engine is CALLED (gate §7);
  * no UI, no Streamlit session dependency (doc 04 §46: scheduler-ready);
  * failures are explicit: required-weather failure produces NO fabricated
    risk (the AI layer is skipped and the scan is FAILED); agent / model /
    synthesizer / critic failures degrade with honest labels and are never
    hidden (gate §15);
  * every scan creates NEW snapshots — data snapshot before the engine runs,
    result snapshot after the Critic — inserts only, never overwrites;
    snapshot creation failure aborts the scan fail-safe.

Snapshot payload compatibility: the result snapshot exposes the G03B
trend/previous-state keys (current_risk_index, point_recent_percentiles,
point_forecast_percentiles, missing_data, optional_evidence_availability)
at the payload top level, so riskwatch.engine.comparison / trend read
G03C snapshots with their frozen contracts, unmodified.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Optional, Sequence

from orchestration.context_builder import (
    BASE_SCIENTIFIC_CONSTRAINTS,
    MODE_RISK_WATCH,
    AnalysisContext,
)
from orchestration.risk_watch_adapter import (
    RiskWatchScanRecord,
    risk_watch_adapter,
)
from providers.base_provider import ModelProvider, ModelRequest, ModelResult
from riskwatch.cache import WeatherRawCache
from riskwatch.climatology import (
    ClimatologyReference,
    ClimatologyStore,
    HistoricalWeatherClient,
    generate_reference,
    runtime_dir as default_runtime_dir,
)
from riskwatch.engine.core import RiskWatchResult, compute_risk_watch
from riskwatch.engine.comparison import PreviousState, load_previous_state
from riskwatch.engine.formulas import (
    STATUS_COMPLETED,
    STATUS_COMPLETED_WITH_LIMITATIONS,
    STATUS_FAILED,
)
from riskwatch.engine.trend import HistoricalTrend, query_historical_trend
from riskwatch.region import RegionConfig, load_region
from riskwatch.snapshot_store import (
    ALLOWED_SCAN_MODES,
    SCAN_MODE_LIVE,
    SnapshotStore,
)
from riskwatch.weather import (
    FORECAST_ENDPOINT,
    FORECAST_MODEL,
    QUALITY_MISSING,
    PointWeather,
    PointWeatherFailure,
    RegionWeatherResult,
    WeatherCollector,
)
from schemas.agent_outputs import AgentStatus
from schemas.evidence import (
    AGENT_GLACIER_GEOLOGY,
    AGENT_REMOTE_SENSING,
    AGENT_WEATHER_HYDROLOGY,
    TYPE_CLIMATE_CONTEXT,
    TYPE_CRYOSPHERE,
    TYPE_EXPOSURE,
    TYPE_HISTORICAL_EVENT,
    TYPE_MISSING_INPUT,
    TYPE_REGION,
    TYPE_TERRAIN,
    TYPE_WEATHER_CONTEXT,
    EvidenceItem,
    EvidenceQuality,
)
from schemas.synthesis import (
    CriticReviewResult,
    CriticVerdictResult,
    SynthesisResult,
)

logger = logging.getLogger(__name__)

WORKFLOW_VERSION = "risk-watch-workflow-v1.0"

# ─── scan state machine (doc 04 §29) ─────────────────────────────────────────
STAGE_CREATED = "CREATED"
STAGE_CONFIG_LOADED = "CONFIG_LOADED"
STAGE_COLLECTING = "COLLECTING"
STAGE_NORMALIZED = "NORMALIZED"
STAGE_VALIDATED = "VALIDATED"
STAGE_SNAPSHOT_SAVED = "SNAPSHOT_SAVED"
STAGE_COMPARED = "COMPARED"
STAGE_ENGINE_COMPLETED = "ENGINE_COMPLETED"
STAGE_CONTEXT_BUILT = "CONTEXT_BUILT"
STAGE_AGENTS_COMPLETED = "AGENTS_COMPLETED"
STAGE_SYNTHESIZED = "SYNTHESIZED"
STAGE_REVIEWED = "REVIEWED"
STAGE_COMPLETED = "COMPLETED"

# ─── evidence phases (Risk Watch has no event; these are NOT replay phases) ──
PHASE_RW_STATIC = "risk_watch_static"
PHASE_RW_OPERATIONAL = "risk_watch_operational"
PHASE_MISSING = "missing_input"

# ─── optional evidence sources declared missing in v1.0 G03C (doc 04 §19-26) ─
#: (evidence_id, summary, allowed_agents) — summaries double as the labels
#: recorded in data_quality.optional_coverage.missing (Critic check 9).
OPTIONAL_EVIDENCE_SOURCES = (
    ("RW-OPT-SATELLITE",
     "卫星影像（Sentinel-2 STAC 可选管线，v1.0 G03C 未接入）",
     (AGENT_REMOTE_SENSING,)),
    ("RW-OPT-HYDRO",
     "实时水文/水位数据（v1.0 非 P0 数据源，未接入）",
     (AGENT_WEATHER_HYDROLOGY,)),
    ("RW-OPT-SOIL",
     "土壤湿度数据（可选辅助证据，未接入数值公式）",
     (AGENT_WEATHER_HYDROLOGY,)),
    ("RW-OPT-ENSO",
     "ENSO 气候背景（context-only 可选数据源，未接入）",
     (AGENT_WEATHER_HYDROLOGY,)),
)

#: Risk Watch scientific constraints (doc 04 §44/§45 + engine semantics).
RISK_WATCH_CONSTRAINTS = (
    "网格化模型/再分析天气数据（ECMWF / ERA5）不等同于现场自动站或源区"
    "传感器实测；高山复杂地形与局地微气候只能被部分表达。",
    "系统没有源区高频冰川位移、裂缝、微震、冰崩等实时监测数据，不能可靠"
    "判断某个高位冰岩体将在未来几小时或几天内崩塌；不得输出具体发生时刻"
    "预测。",
    "C（Current Risk Index）与 O7（7-Day Outlook Index）是确定性风险状态"
    "指标，不是灾害发生概率、不是官方预警等级；O7 只表示如果当前 7 天"
    "预报兑现，区域可能处于的风险背景。",
    "专业 Agent 只解释证据，不计算、不修改 B/R/F/D/C/O7 与风险带。",
    "Optional Evidence（卫星/水文/土壤湿度/ENSO）缺失不阻塞主扫描流程，"
    "且永远不改变数值公式。",
)

_ALL_AGENTS = (AGENT_GLACIER_GEOLOGY, AGENT_WEATHER_HYDROLOGY,
               AGENT_REMOTE_SENSING)


class RiskScanError(RuntimeError):
    """Fail-safe abort: the scan cannot proceed honestly (snapshot store
    failure, invalid scan mode, ...). Nothing is fabricated on abort."""


# ─── DeepSeek call accounting (gate G03C §18 audit) ──────────────────────────
class CountingProvider(ModelProvider):
    """Transparent wrapper counting real model-generation calls.

    Delegates everything to the wrapped provider; records per-call audit
    facts (request id, latency, success, provider status, fallback) so the
    live verification can report the exact number of DeepSeek calls without
    touching provider internals.
    """

    def __init__(self, inner: ModelProvider):
        self.inner = inner
        self.provider_name = getattr(inner, "provider_name", "wrapped")
        self.model_id = getattr(inner, "model_id", "")
        self.calls: list = []

    def _record(self, request: ModelRequest, result: ModelResult,
                started: float) -> ModelResult:
        self.calls.append({
            "request_id": result.request_id or request.request_id,
            "run_id": request.run_id,
            "latency_ms": int((time.monotonic() - started) * 1000),
            "success": bool(result.success),
            "provider_status": result.status.value,
            "fallback_used": bool(result.fallback_used),
            "token_usage": dict(result.token_usage or {}),
        })
        return result

    def generate_structured(self, request: ModelRequest) -> ModelResult:
        started = time.monotonic()
        return self._record(request,
                            self.inner.generate_structured(request), started)

    def generate_multimodal(self, request: ModelRequest,
                            images: Optional[list] = None) -> ModelResult:
        started = time.monotonic()
        return self._record(
            request,
            self.inner.generate_multimodal(request, images=images), started)

    def health_check(self):
        return self.inner.health_check()

    def summary(self) -> dict:
        return {
            "provider_name": self.provider_name,
            "model_id": self.model_id,
            "generation_calls": len(self.calls),
            "total_latency_ms": sum(c["latency_ms"] for c in self.calls),
            "successful_calls": sum(1 for c in self.calls if c["success"]),
            "calls": list(self.calls),
        }


# ─── final result schema (gate G03C §14) ─────────────────────────────────────
@dataclass(frozen=True)
class RiskWatchRunResult:
    """Immutable structured result of one end-to-end Risk Watch scan."""

    run_id: str
    region_id: str
    created_time: str
    status: str                        # COMPLETED / COMPLETED_WITH_LIMITATIONS / FAILED
    scan_mode: str
    deterministic_result: RiskWatchResult
    agent_results: dict                # {agent_name: AgentRunResult}
    synthesis: Optional[SynthesisResult]
    synthesis_status: str              # COMPLETED / FALLBACK / UNAVAILABLE...
    critic: Optional[CriticVerdictResult]
    critic_status: str                 # frozen verdict taxonomy or UNAVAILABLE...
    limitations: tuple
    provenance: dict
    data_quality: dict
    ai_layer: dict = field(default_factory=dict)
    data_snapshot_id: str = ""
    result_snapshot_id: str = ""
    historical_trend: Optional[HistoricalTrend] = None
    stage_trace: tuple = ()

    # ── convenience accessors (read-only views of the deterministic layer) ──
    @property
    def risk_index(self) -> Optional[float]:
        return self.deterministic_result.C

    @property
    def risk_level(self) -> Optional[str]:
        return self.deterministic_result.current_risk_level

    @property
    def outlook_7d_index(self) -> Optional[float]:
        return self.deterministic_result.O7

    @property
    def outlook_7d_level(self) -> Optional[str]:
        return self.deterministic_result.outlook_7d_level

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "region_id": self.region_id,
            "created_time": self.created_time,
            "status": self.status,
            "scan_mode": self.scan_mode,
            "risk_index": self.risk_index,
            "risk_level": self.risk_level,
            "outlook_7d_index": self.outlook_7d_index,
            "outlook_7d_level": self.outlook_7d_level,
            "risk_direction": self.deterministic_result.risk_direction,
            "deterministic_result": self.deterministic_result.to_dict(),
            "agent_results": {
                name: {"output": res.to_dict(), "audit": res.to_audit_dict()}
                for name, res in self.agent_results.items()},
            "agent_status_summary": {
                name: res.status.value
                for name, res in self.agent_results.items()},
            "synthesis": ({"output": self.synthesis.to_dict(),
                           "audit": self.synthesis.to_audit_dict()}
                          if self.synthesis is not None else None),
            "synthesis_status": self.synthesis_status,
            "critic": ({"verdict": self.critic.to_dict(),
                        "audit": self.critic.to_audit_dict()}
                       if self.critic is not None else None),
            "critic_status": self.critic_status,
            "limitations": list(self.limitations),
            "provenance": dict(self.provenance),
            "data_quality": dict(self.data_quality),
            "ai_layer": dict(self.ai_layer),
            "data_snapshot_id": self.data_snapshot_id,
            "result_snapshot_id": self.result_snapshot_id,
            "historical_trend": (self.historical_trend.to_dict()
                                 if self.historical_trend is not None
                                 else None),
            "stage_trace": [list(s) for s in self.stage_trace],
        }

    def to_json(self, indent: int | None = None) -> str:
        import json

        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True,
                          indent=indent, default=str)

    # ── snapshot payload ────────────────────────────────────────────────────
    def snapshot_payload(self) -> dict[str, Any]:
        """Result-snapshot payload: the full result PLUS the G03B
        trend/previous-state compatibility keys at the top level (frozen
        reader contracts of riskwatch.engine.comparison / trend)."""
        payload = self.to_dict()
        payload.pop("result_snapshot_id", None)   # not known before insert
        payload.pop("historical_trend", None)     # queried after insert
        payload["snapshot_kind"] = "risk_watch_result"
        engine = self.deterministic_result.to_dict()
        payload.update({
            "current_risk_index": engine.get("current_risk_index"),
            "current_risk_level": engine.get("current_risk_level"),
            "outlook_7d_index": engine.get("outlook_7d_index"),
            "outlook_7d_level": engine.get("outlook_7d_level"),
            "B": engine.get("B"),
            "R": engine.get("R"),
            "F": engine.get("F"),
            "D": engine.get("D"),
            "C": engine.get("C"),
            "O7": engine.get("O7"),
            "risk_direction": engine.get("risk_direction"),
            "point_recent_percentiles": engine.get("point_recent_percentiles"),
            "point_forecast_percentiles": engine.get("point_forecast_percentiles"),
            "missing_data": engine.get("missing_data"),
            "optional_evidence_availability":
                engine.get("optional_evidence_availability"),
            "what_changed": engine.get("what_changed"),
        })
        return payload


# ─── Step 3: deterministic data-quality validation ───────────────────────────
def compute_data_quality(
    region: RegionConfig,
    weather: RegionWeatherResult,
    climatologies: Mapping[str, Optional[ClimatologyReference]],
) -> dict[str, Any]:
    """Required vs optional coverage, per-point quality — kept SEPARATE so a
    missing optional source never drags the required-coverage number down
    (doc 04 §42)."""
    point_quality: dict[str, str] = {}
    for point in region.monitoring_points:
        pw = weather.points.get(point.point_id)
        if isinstance(pw, PointWeather):
            point_quality[point.point_id] = pw.quality
        else:
            point_quality[point.point_id] = QUALITY_MISSING
    ok_points = list(weather.ok_points)
    failed_points = list(weather.failed_points)
    return {
        "weather_status": weather.status,
        "retrieval_time": weather.retrieval_time,
        "point_quality": point_quality,
        "required_coverage": {
            "total": len(region.monitoring_points),
            "ok": len(ok_points),
            "failed": failed_points,
            "note": "monitoring points with normalized operational weather",
        },
        "optional_coverage": {
            "total": len(OPTIONAL_EVIDENCE_SOURCES),
            "available": 0,
            "missing": [summary for _eid, summary, _agents
                        in OPTIONAL_EVIDENCE_SOURCES],
            "note": ("optional evidence never changes B/R/F/D/C/O7 "
                     "(doc 04 §19); missing optional sources are declared "
                     "explicitly, never silently dropped"),
        },
        "satellite_pipeline_available": False,
        "climatology_references": {
            pid: ({
                "baseline": [ref.baseline_start, ref.baseline_end],
                "source_model": ref.source_model,
                "algorithm_version": ref.algorithm_version,
                "checksum": ref.checksum,
                "generated_at": ref.generated_at,
                "model_fallback_note": ref.model_fallback_note,
            } if (ref := climatologies.get(pid)) is not None else None)
            for pid in point_quality
        },
    }


# ─── Step 6: evidence package (Risk Watch AnalysisContext) ───────────────────
def _quality_label(weather_quality: str) -> str:
    return {
        "FRESH": EvidenceQuality.GOOD.value,
        "STALE": EvidenceQuality.STALE.value,
        "MISSING": EvidenceQuality.MISSING.value,
    }.get(weather_quality, EvidenceQuality.LIMITED.value)


def _fmt_window(win: dict[str, Any]) -> str:
    total = win.get("cumulative_precipitation_mm")
    total_s = (f"{total:.1f} mm" if total is not None
               else "不完整（存在缺失日，绝不零填充）")
    tmax = win.get("max_daily_precipitation_mm")
    trange = win.get("temperature_range_c")
    parts = [
        f"{win.get('start')}..{win.get('end')}",
        f"累计降水 {total_s}",
        f"最大日降水 {tmax:.1f} mm" if tmax is not None else "最大日降水 缺失",
        (f"温度范围 {trange['min']:.1f}..{trange['max']:.1f} degC"
         if trange else "温度范围 缺失"),
        f"可用天数 {win.get('available_days')}/{win.get('expected_days')}",
    ]
    return "；".join(parts)


def build_risk_watch_context(
    region: RegionConfig,
    weather: RegionWeatherResult,
    climatologies: Mapping[str, Optional[ClimatologyReference]],
    watch_result: RiskWatchResult,
    data_quality: dict[str, Any],
    run_id: str,
    created_time: str,
) -> AnalysisContext:
    """Build the Risk Watch evidence package (gate G03C step 6).

    Sources are ONLY the Risk Watch Source of Truth (region.json), the live
    G03A weather collection, the G03A climatology references and the G03B
    deterministic result. The Historical Replay Case Pack is NEVER read
    (structural anti-leakage, doc 04 §3). Every item carries provenance;
    missing sources are explicit EvidenceItems, never fabrications.
    """
    data = region.data
    allowed: list = []
    missing: list = []
    src_refs = {str(s.get("id")): s for s in (data.get("source_references") or [])}

    def src_names(ids: Sequence[str]) -> tuple:
        names = [str(src_refs.get(i, {}).get("name", i)) for i in (ids or [])]
        orgs = [str(src_refs.get(i, {}).get("authority", "")) for i in (ids or [])]
        return (",".join(n for n in names if n),
                ";".join(o for o in orgs if o))

    def static_item(eid: str, etype: str, summary: str, value: Any,
                    source_ids: Sequence[str], limitations: str = "",
                    agents: tuple = (AGENT_GLACIER_GEOLOGY,)) -> EvidenceItem:
        sname, sorg = src_names(source_ids)
        return EvidenceItem(
            evidence_id=eid, evidence_type=etype, phase=PHASE_RW_STATIC,
            summary=summary, value=value,
            source_name=sname, source_organization=sorg,
            source_reference=",".join(source_ids or []),
            observation_time="", quality=EvidenceQuality.GOOD.value,
            raw_or_derived="raw", allowed_agents=agents,
            limitations=limitations,
        )

    # ── static susceptibility evidence (region.json — Risk Watch SoT) ──
    tb = data.get("static_terrain_baseline", {})
    allowed.append(static_item(
        "RW-STATIC-TERRAIN", TYPE_TERRAIN,
        "地形与沟谷静态背景（region.json 静态基线）",
        (f"terrain_class={tb.get('terrain_class')}; "
         f"vertical_drop_m={tb.get('vertical_drop_m')}; "
         f"loose_material_supply={tb.get('loose_material_supply')}; "
         f"tectonic_context={tb.get('tectonic_context')}"),
        (tb.get("provenance", {}) or {}).get("source_ids", []),
        limitations=str(tb.get("vertical_drop_note") or "")))
    cb = data.get("cryosphere_baseline", {})
    allowed.append(static_item(
        "RW-STATIC-CRYO", TYPE_CRYOSPHERE,
        "冰冻圈源区静态背景（region.json 静态基线）",
        (f"glacierized_source_zone={cb.get('glacierized_source_zone')}; "
         f"upstream_glacial_lake_count={cb.get('upstream_glacial_lake_count')}; "
         f"upstream_glacial_lake_area_km2="
         f"{cb.get('upstream_glacial_lake_area_km2')}"),
        (cb.get("provenance", {}) or {}).get("source_ids", []),
        limitations=str(cb.get("basin_note") or "")))
    hb = data.get("historical_hazard_baseline", {})
    allowed.append(static_item(
        "RW-STATIC-HIST", TYPE_HISTORICAL_EVENT,
        "历史链式灾害背景（region.json 静态基线，历史背景非未来预测）",
        (f"prior_event_date={hb.get('prior_event_date')}; "
         f"prior_event_type={hb.get('prior_event_type')}"),
        (hb.get("provenance", {}) or {}).get("source_ids", []),
        limitations=str(hb.get("recurrence_note") or "")))
    de = data.get("downstream_exposure", {})
    allowed.append(static_item(
        "RW-STATIC-EXPOSURE", TYPE_EXPOSURE,
        "下游暴露（口岸与居民区）静态背景",
        str(de.get("description", ""))[:400],
        (de.get("provenance", {}) or {}).get("source_ids", [])))

    baseline = watch_result.static_baseline
    factor_lines = "; ".join(
        f"{f.factor_id} {f.name}: {f.score_0_to_5:.0f}/5 × "
        f"{f.normalized_weight_pct:.2f}% → 贡献 {f.contribution:.2f}"
        for f in baseline.factors)
    allowed.append(EvidenceItem(
        evidence_id="RW-STATIC-B", evidence_type="terrain",
        phase=PHASE_RW_STATIC,
        summary="区域静态易灾基线 B（G03B 确定性推导，region.json 五因子）",
        value=(f"B={baseline.value_rounded}（全精度 {baseline.value!r}）; "
               f"excluded={list(baseline.excluded_factor_ids)}; "
               f"scoring_config={baseline.scoring_config_version}; "
               f"stored_derived_match={baseline.stored_derived_match}; "
               f"factors: {factor_lines}"),
        source_name="region.json static_susceptibility_inputs",
        source_organization="MountainGuardian Risk Watch Source of Truth",
        source_reference=f"region.json@{region.config_version}",
        quality=EvidenceQuality.GOOD.value, raw_or_derived="derived",
        allowed_agents=(AGENT_GLACIER_GEOLOGY,),
        limitations=baseline.semantics))

    # ── monitoring points (all agents) ──
    point_lines = "; ".join(
        f"{p.point_id}（{p.name[:40]}, lat={p.latitude}, lon={p.longitude}, "
        f"elev={p.elevation_m}, coordinate={p.coordinate_type}）"
        for p in region.monitoring_points)
    allowed.append(EvidenceItem(
        evidence_id="RW-POINTS", evidence_type=TYPE_REGION,
        phase=PHASE_RW_STATIC,
        summary=f"监测点配置（{len(region.monitoring_points)} 个，"
                f"代表性网格锚点坐标）",
        value=point_lines,
        source_name="region.json monitoring_points",
        source_organization="MountainGuardian Risk Watch Source of Truth",
        source_reference=f"region.json@{region.config_version}",
        quality=EvidenceQuality.GOOD.value, raw_or_derived="raw",
        allowed_agents=_ALL_AGENTS,
        limitations="坐标为代表性网格锚点（derived/representative），"
                    "非实测仪器位置。"))

    # ── operational weather per point (Weather / Hydrology agent) ──
    for point in region.monitoring_points:
        pid = point.point_id
        pw = weather.points.get(pid)
        if isinstance(pw, PointWeather):
            prov = pw.provenance or {}
            common = dict(
                evidence_type=TYPE_WEATHER_CONTEXT,
                phase=PHASE_RW_OPERATIONAL,
                source_name=f"{prov.get('provider', 'Open-Meteo')} "
                            f"{prov.get('model_requested', FORECAST_MODEL)}",
                source_organization="Open-Meteo（网格化模型数据，非现场实测）",
                source_reference=str(prov.get("endpoint", FORECAST_ENDPOINT)),
                quality=_quality_label(pw.quality),
                raw_or_derived="raw",
                allowed_agents=(AGENT_WEATHER_HYDROLOGY,),
            )
            allowed.append(EvidenceItem(
                evidence_id=f"RW-WX-{pid}-RECENT",
                summary=f"{pid} 过去 7 天观测窗口（{pw.quality}）",
                value=_fmt_window(pw.recent),
                observation_time=str(pw.recent.get("end", "")),
                limitations=(f"retrieval_time={prov.get('retrieval_time')}; "
                             f"from_cache={prov.get('from_cache')}"),
                **common))
            allowed.append(EvidenceItem(
                evidence_id=f"RW-WX-{pid}-FORECAST",
                summary=f"{pid} 未来 7 天预报窗口（{pw.quality}）",
                value=_fmt_window(pw.forecast),
                observation_time=str(pw.forecast.get("end", "")),
                limitations=(f"预报为模型输出，存在不确定性；"
                             f"retrieval_time={prov.get('retrieval_time')}"),
                **common))
        elif isinstance(pw, PointWeatherFailure):
            missing.append(EvidenceItem(
                evidence_id=f"RW-WX-{pid}-FAILED",
                evidence_type=TYPE_MISSING_INPUT,
                phase=PHASE_MISSING,
                summary=f"{pid} 实时天气获取失败（{pw.error_type}）",
                value=pw.message[:300],
                quality=EvidenceQuality.MISSING.value,
                allowed_agents=(AGENT_WEATHER_HYDROLOGY,),
                limitations="缺失即缺失：绝不零填充、绝不由模型猜测天气。"))
        # climatology identity (Weather agent — percentile provenance)
        ref = climatologies.get(pid)
        if ref is not None:
            allowed.append(EvidenceItem(
                evidence_id=f"RW-CLIM-{pid}",
                evidence_type=TYPE_CLIMATE_CONTEXT,
                phase=PHASE_RW_OPERATIONAL,
                summary=f"{pid} 1991-2020 七天滚动降水气候基线（G03A 缓存）",
                value=(f"baseline={ref.baseline_start}..{ref.baseline_end}; "
                       f"model={ref.source_model}; "
                       f"algorithm={ref.algorithm_version}; "
                       f"percentile_method={ref.percentile_method}; "
                       f"windows={sum(ref.window_counts.values())}"),
                source_name="Open-Meteo Historical Weather API (archive)",
                source_organization="Open-Meteo / ERA5(-Land) 再分析",
                source_reference=f"checksum={ref.checksum[:16]}",
                quality=EvidenceQuality.GOOD.value, raw_or_derived="derived",
                allowed_agents=(AGENT_WEATHER_HYDROLOGY,),
                limitations=str(ref.model_fallback_note or "")))
        else:
            missing.append(EvidenceItem(
                evidence_id=f"RW-CLIM-{pid}-MISSING",
                evidence_type=TYPE_MISSING_INPUT, phase=PHASE_MISSING,
                summary=f"{pid} 1991-2020 气候基线不可用（该点百分位被排除）",
                quality=EvidenceQuality.MISSING.value,
                allowed_agents=(AGENT_WEATHER_HYDROLOGY,),
                limitations="无气候基线则该点不参与 R/F 聚合；绝不替代或伪造。"))

    # ── deterministic engine result (all agents — read-only truth layer) ──
    d = watch_result.to_dict()
    disp = d["display"]
    allowed.append(EvidenceItem(
        evidence_id="RW-ENGINE-C", evidence_type="risk_watch_deterministic",
        phase=PHASE_RW_OPERATIONAL,
        summary="确定性引擎当前风险指数 C（权威数值，只读，禁止修改）",
        value=(f"C={disp['C']}（全精度 {d['C']!r}）；风险带="
               f"{d['current_risk_level']}；方向={d['risk_direction']}"
               f"（previous_C={d['previous_C']}, delta_C={d['delta_C']}）；"
               f"status={d['status']}"),
        source_name="riskwatch.engine (G03B)",
        source_organization="MountainGuardian 确定性风险引擎",
        source_reference=f"{d['algorithm_version']}@{d['formula_version']}",
        quality=EvidenceQuality.GOOD.value, raw_or_derived="derived",
        allowed_agents=_ALL_AGENTS,
        limitations=d["semantics"]))
    allowed.append(EvidenceItem(
        evidence_id="RW-ENGINE-O7", evidence_type="risk_watch_deterministic",
        phase=PHASE_RW_OPERATIONAL,
        summary="确定性引擎 7 天展望指数 O7（权威数值，只读，禁止修改）",
        value=(f"O7={disp['O7']}（全精度 {d['O7']!r}）；展望带="
               f"{d['outlook_7d_level']}；O7=0.70×B+0.30×F（冻结公式）"),
        source_name="riskwatch.engine (G03B)",
        source_organization="MountainGuardian 确定性风险引擎",
        source_reference=f"{d['algorithm_version']}@{d['formula_version']}",
        quality=EvidenceQuality.GOOD.value, raw_or_derived="derived",
        allowed_agents=_ALL_AGENTS,
        limitations="O7 表示如果当前 7 天预报兑现区域可能处于的风险背景；"
                    "不是未来灾害概率。"))
    allowed.append(EvidenceItem(
        evidence_id="RW-ENGINE-D-RF", evidence_type=TYPE_WEATHER_CONTEXT,
        phase=PHASE_RW_OPERATIONAL,
        summary="降水百分位与动态触发指数（G03B 确定性特征，只读）",
        value=(f"R={disp['R']}（驱动点 {d['R_driver_point']}）；"
               f"F={disp['F']}（驱动点 {d['F_driver_point']}）；"
               f"D={disp['D']}（D=0.60×R+0.40×F）；B={disp['B']}；"
               f"聚合规则=成功点保守最大；百分位方法=mean_rank；"
               f"月份归属=窗口结束月"),
        source_name="riskwatch.engine (G03B)",
        source_organization="MountainGuardian 确定性风险引擎",
        source_reference=f"{d['algorithm_version']}@{d['formula_version']}",
        quality=EvidenceQuality.GOOD.value, raw_or_derived="derived",
        allowed_agents=(AGENT_WEATHER_HYDROLOGY,),
        limitations="百分位是相对当地 1991-2020 气候分布的位置，"
                    "不是降水概率。"))
    top_lines = "; ".join(
        f"{drv['label'][:60]}→{drv['contribution_points_rounded']}点"
        for drv in d["top_drivers"][:5])
    allowed.append(EvidenceItem(
        evidence_id="RW-ENGINE-DRIVERS", evidence_type="risk_watch_deterministic",
        phase=PHASE_RW_OPERATIONAL,
        summary="Top Risk Drivers（贡献可追溯，合计等于 C，代码排序）",
        value=top_lines,
        source_name="riskwatch.engine.drivers (G03B)",
        source_organization="MountainGuardian 确定性风险引擎",
        source_reference=f"{d['algorithm_version']}",
        quality=EvidenceQuality.GOOD.value, raw_or_derived="derived",
        allowed_agents=_ALL_AGENTS,
        limitations="排序由确定性贡献分解产生，LLM 只可解释不可重排。"))

    # ── optional evidence sources declared missing (v1.0 G03C) ──
    for eid, summary, agents in OPTIONAL_EVIDENCE_SOURCES:
        missing.append(EvidenceItem(
            evidence_id=eid, evidence_type=TYPE_MISSING_INPUT,
            phase=PHASE_MISSING, summary=summary,
            value="MISSING_OPTIONAL",
            quality=EvidenceQuality.MISSING.value,
            allowed_agents=agents,
            limitations="可选证据缺失不阻塞主扫描流程，且永远不改变数值"
                        "公式；不得用其他地区数据替代。"))

    points = region.monitoring_points
    primary = points[-1] if points else None
    constraints = (list(BASE_SCIENTIFIC_CONSTRAINTS)
                   + list(RISK_WATCH_CONSTRAINTS)
                   + [str(x) for x in (data.get("scientific_limitations") or [])])
    ctx = AnalysisContext(
        run_id=run_id,
        mode=MODE_RISK_WATCH,
        region_id=region.region_id,
        analysis_time=created_time,
        case_metadata={
            "case_id": region.region_id,
            "case_name": f"Risk Watch 实时扫描 — {data.get('region_name', region.region_id)}",
            "location": str(data.get("region_name", "")),
            "lat": primary.latitude if primary else "",
            "lon": primary.longitude if primary else "",
            "event_date": "",   # Risk Watch has no event
            "pack_version": region.config_version,
            "run_id": run_id,
            "scan_mode": "",    # filled by caller-side provenance; kept neutral
            "retrieval_time": weather.retrieval_time,
            "mode_note": ("Risk Watch operational scan — independent Source "
                          "of Truth; no Historical Replay Case Pack input"),
        },
        allowed_evidence=allowed,
        context_only_evidence=[],
        missing_sources=missing,
        scientific_constraints=constraints,
        pre_event_imagery=[],
    )
    ctx.assert_no_post_event()   # trivially true — built without any Case Pack
    logger.info("[risk_watch] context built: run=%s allowed=%d missing=%d "
                "(no case pack)", run_id, len(allowed), len(missing))
    return ctx


# ─── the workflow ─────────────────────────────────────────────────────────────
def _resolve_provider(provider: Any) -> Optional[ModelProvider]:
    """'auto' → real DeepSeekProvider (key read from env at call time);
    None → no provider (explicit OFFLINE fallback path); instance → as-is."""
    if isinstance(provider, str):
        if provider != "auto":
            raise RiskScanError(f"unknown provider selector {provider!r}")
        from providers.deepseek_provider import DeepSeekProvider

        return DeepSeekProvider()
    return provider


def run_risk_scan(
    region_id: str = "jilong_port",
    *,
    provider: Any = "auto",
    regions_dir: Path | str | None = None,
    runtime_dir: Path | str | None = None,
    db_path: Path | str | None = None,
    collector: Optional[WeatherCollector] = None,
    store: Optional[SnapshotStore] = None,
    synthesizer: Any = None,
    critic: Any = None,
    agents: Optional[list] = None,
    scan_mode: str = SCAN_MODE_LIVE,
    run_id: Optional[str] = None,
    clock: Optional[Callable[[], datetime]] = None,
    historical_client: Optional[HistoricalWeatherClient] = None,
    generate_climatology: bool = True,
) -> RiskWatchRunResult:
    """Execute ONE end-to-end Risk Watch scan (gate G03C §6 steps 1-10).

    Scheduler-ready (doc 04 §46): no Streamlit session, no UI dependency;
    callable from CLI / API / scheduler. Injectables exist for testing;
    production defaults use the real G03A collector (with 30-minute raw
    cache), the cached 1991-2020 climatology (generated once on demand),
    the G03A snapshot store and the real DeepSeek provider when
    DEEPSEEK_API_KEY is present.

    Failure contract (gate §15):
      * weather failure  → engine FAILED, no fabricated risk, AI layer
        skipped, both snapshots persisted, scan status FAILED;
      * agent failure    → isolated; scan continues on the deterministic
        result; limitation recorded;
      * DeepSeek unavailable → deterministic fallbacks everywhere, labeled
        fallback_used=True / is_model_output=False (never disguised);
      * synthesizer failure  → deterministic result returned WITHOUT any
        fake explanation (synthesis=None + limitation);
      * critic failure       → critic_status UNAVAILABLE, failure disclosed;
      * snapshot creation failure → RiskScanError, fail-safe abort.
    """
    # lazy imports: agents.* import orchestration.* — avoid a package cycle
    from agents.professional_base import run_professional_agents
    from agents.riskwatch_critic import RiskWatchCritic
    from agents.riskwatch_synthesizer import RiskWatchSynthesizer

    if scan_mode not in ALLOWED_SCAN_MODES:
        raise RiskScanError(
            f"scan_mode must be one of {ALLOWED_SCAN_MODES} — BACKFILL must "
            "be explicit, never disguised as LIVE")

    _clock = clock or (lambda: datetime.now(timezone.utc))
    trace: list = []

    def _stage(name: str) -> str:
        ts = _clock().isoformat()
        trace.append((name, ts))
        return ts

    created_time = _stage(STAGE_CREATED)
    run_id = run_id or (
        f"rw-{_clock().strftime('%Y%m%dT%H%M%S%fZ')}-{uuid.uuid4().hex[:8]}")
    limitations: list = []

    # ── Step 1: region config (Risk Watch Source of Truth; never Case Pack) ──
    region = load_region(region_id, regions_dir=regions_dir)
    _stage(STAGE_CONFIG_LOADED)

    runtime = Path(runtime_dir) if runtime_dir is not None \
        else default_runtime_dir()

    # ── Step 2: collect current weather through the G03A collector ──
    _stage(STAGE_COLLECTING)
    clim_store = ClimatologyStore(runtime / "climatology")
    baseline_window = region.climatology_baseline
    climatologies: dict[str, Optional[ClimatologyReference]] = {}
    climatology_generated_now: dict[str, bool] = {}
    for point in region.monitoring_points:
        ref = clim_store.load(point.point_id, *baseline_window)
        generated_now = False
        if ref is None and generate_climatology:
            try:
                client = historical_client or HistoricalWeatherClient()
                now_iso = _clock().isoformat()
                ref, generated_now = generate_reference(
                    point, client, clim_store,
                    generated_at=now_iso, retrieval_time=now_iso,
                    baseline=baseline_window)
            except Exception as exc:
                ref = None
                limitations.append(
                    f"climatology reference unavailable for "
                    f"{point.point_id}: {type(exc).__name__}: {exc} — the "
                    "point is excluded from percentile aggregation (never "
                    "substituted or fabricated)")
        climatologies[point.point_id] = ref
        climatology_generated_now[point.point_id] = generated_now

    if collector is None:
        collector = WeatherCollector(cache=WeatherRawCache(runtime / "cache"))
    weather = collector.collect_region(region)
    _stage(STAGE_NORMALIZED)

    # ── Step 3: validate data quality (deterministic summary) ──
    data_quality = compute_data_quality(region, weather, climatologies)
    _stage(STAGE_VALIDATED)

    owns_store = store is None
    if owns_store:
        store = SnapshotStore(db_path)
    try:
        # ── Step 4: immutable data snapshot (fail-safe on any store error) ──
        weather_provenance = {
            pid: ({"status": "OK", **{
                       k: pw.provenance.get(k) for k in (
                           "provider", "endpoint", "model_requested",
                           "requested_coordinate", "returned_coordinate",
                           "elevation_m", "retrieval_time", "request_time",
                           "from_cache", "cache_age_seconds",
                           "original_retrieval_time", "observation_window",
                           "forecast_window")}}
                  if isinstance(pw, PointWeather)
                  else {"status": "FAILED",
                        "error_type": pw.error_type,
                        "message": pw.message})
            for pid, pw in weather.points.items()
        }
        data_payload = {
            "snapshot_kind": "risk_watch_data",
            "run_id": run_id,
            "region_id": region.region_id,
            "scan_mode": scan_mode,
            "created_time": created_time,
            "region_config_version": region.config_version,
            "scoring_config_version": region.scoring_config_version,
            "weather": weather.to_dict(),
            "weather_provenance": weather_provenance,
            "data_quality": data_quality,
            "note": ("Immutable data snapshot of one Risk Watch scan "
                     "(insert-only; never overwritten). Data-only rows are "
                     "NOT eligible trend history (status DATA_*)."),
        }
        try:
            data_snapshot_id = store.insert_snapshot(
                run_id=run_id, region_id=region.region_id,
                status=f"DATA_{weather.status}", payload=data_payload,
                created_at=created_time, scan_mode=scan_mode,
                config_version=region.config_version)
        except Exception as exc:
            raise RiskScanError(
                f"data snapshot creation failed — scan aborted fail-safe, "
                f"no result fabricated: {type(exc).__name__}: {exc}") from exc
        _stage(STAGE_SNAPSHOT_SAVED)

        # ── Compare: previous eligible result (real snapshots only) ──
        previous: Optional[PreviousState] = load_previous_state(
            store, region.region_id)
        _stage(STAGE_COMPARED)

        # ── Step 5: run the G03B deterministic engine (CALLED, not copied) ──
        watch_result = compute_risk_watch(
            region, weather, climatologies,
            previous=previous, run_id=run_id, optional_evidence=())
        _stage(STAGE_ENGINE_COMPLETED)
        limitations.extend(watch_result.limitations)

        agent_results: dict = {}
        synthesis: Optional[SynthesisResult] = None
        synthesis_status = "NOT_INVOKED"
        verdict: Optional[CriticVerdictResult] = None
        critic_status = "NOT_INVOKED"
        ai_layer: dict = {"status": "NOT_INVOKED"}
        counting: Optional[CountingProvider] = None

        if watch_result.status == STATUS_FAILED:
            # ── required weather failure: NO fabricated risk (doc 04 §36) ──
            synthesis_status = "UNAVAILABLE_NO_DETERMINISTIC_RESULT"
            critic_status = "UNAVAILABLE_NO_DETERMINISTIC_RESULT"
            ai_layer = {
                "status": "SKIPPED_NO_DETERMINISTIC_RESULT",
                "note": ("AI interpretation layer not invoked: the "
                         "deterministic engine produced no official Current "
                         "Risk Index (required weather data insufficient). "
                         "No risk and no explanation were fabricated."),
            }
            limitations.append(
                "Scan incomplete — required weather data unavailable: no "
                "official Current Risk Index / 7-Day Outlook was produced "
                "(doc 04 §36). Static baseline B remains independently "
                "reportable; the AI interpretation layer was skipped.")
            run_status = STATUS_FAILED
        else:
            # ── Steps 6-9: AI interpretation layer (never touches numbers) ──
            adapter = risk_watch_adapter(watch_result)
            context = build_risk_watch_context(
                region, weather, climatologies, watch_result, data_quality,
                run_id, created_time)
            context.case_metadata["scan_mode"] = scan_mode
            _stage(STAGE_CONTEXT_BUILT)

            resolved = _resolve_provider(provider)
            counting = CountingProvider(resolved) if resolved is not None \
                else None

            # Step 7: professional agents (G02A, strict failure isolation)
            try:
                agent_results = run_professional_agents(
                    context, counting, agents=agents)
            except Exception as exc:  # absolute isolation, belt and braces
                logger.error("[risk_watch] agent stage crashed: %r", exc)
                agent_results = {}
                limitations.append(
                    f"professional agent stage failed entirely "
                    f"({type(exc).__name__}); the deterministic result "
                    "stands on its own — no agent interpretation available")
            for name, res in sorted(agent_results.items()):
                if res.status == AgentStatus.FAILED:
                    limitations.append(
                        f"agent {name} FAILED "
                        f"({res.error_category}: {res.error_message}); "
                        "workflow continued on the deterministic result")
                elif res.status == AgentStatus.DEGRADED or res.fallback_used:
                    limitations.append(
                        f"agent {name} used the deterministic rule fallback "
                        "(fallback_used=True) — not model output")
                elif res.status == AgentStatus.SKIPPED:
                    limitations.append(
                        f"agent {name} SKIPPED ({res.skip_reason}) — a valid "
                        "formal output, not an error")
            _stage(STAGE_AGENTS_COMPLETED)

            # Step 8: Risk Synthesizer (explains, never alters)
            try:
                synth = synthesizer or RiskWatchSynthesizer(provider=counting)
                synthesis = synth.run(agent_results, adapter, context)
            except Exception as exc:
                logger.error("[risk_watch] synthesizer crashed: %r", exc)
                synthesis = None
            if synthesis is None:
                synthesis_status = "UNAVAILABLE"
                limitations.append(
                    "Risk Synthesizer failure: NO explanation was produced "
                    "and none was fabricated — the deterministic result is "
                    "returned as-is (gate G03C §15).")
            elif synthesis.fallback_used:
                synthesis_status = "FALLBACK"
                limitations.append(
                    "Risk Synthesizer used the deterministic rule fallback "
                    "(AI Analysis: Fallback Mode; fallback_used=True, "
                    "is_model_output=False) — not model synthesis.")
            else:
                synthesis_status = "COMPLETED"
            _stage(STAGE_SYNTHESIZED)

            # Step 9: Critic (reviews; failure disclosed, never hidden)
            if synthesis is None:
                critic_status = "UNAVAILABLE_NO_SYNTHESIS"
                limitations.append(
                    "Critic not invoked: no synthesis to review "
                    "(critic_status=UNAVAILABLE_NO_SYNTHESIS). The failure "
                    "is disclosed, not hidden.")
            else:
                try:
                    crit = critic or RiskWatchCritic(provider=counting)
                    if isinstance(crit, RiskWatchCritic) and crit.scan is None:
                        crit.scan = RiskWatchScanRecord(
                            region=region, weather=weather,
                            climatologies=climatologies,
                            watch_result=watch_result,
                            data_quality=data_quality)
                    verdict = crit.run(synthesis, adapter, agent_results,
                                       context)
                except Exception as exc:
                    logger.error("[risk_watch] critic crashed: %r", exc)
                    verdict = None
                if verdict is None:
                    critic_status = "UNAVAILABLE"
                    limitations.append(
                        "Critic failure: review was not performed "
                        "(critic_status=UNAVAILABLE). The deterministic "
                        "result and agent/synthesis outputs are returned "
                        "unreviewed — the failure is disclosed, not hidden.")
                else:
                    critic_status = verdict.review_result
                    if verdict.review_result in (
                            CriticReviewResult.NEEDS_REVISION.value,
                            CriticReviewResult.BLOCKED.value):
                        limitations.append(
                            f"Critic verdict {verdict.review_result}: "
                            f"{len(verdict.issues)} issue(s) recorded; the "
                            "narrative layer did not pass clean review "
                            "(deterministic numbers are unaffected).")
            _stage(STAGE_REVIEWED)

            ai_layer = {
                "status": "EXECUTED",
                "agent_status_summary": {
                    n: r.status.value for n, r in agent_results.items()},
                "synthesis_status": synthesis_status,
                "critic_status": critic_status,
            }

            degraded = (
                watch_result.status == STATUS_COMPLETED_WITH_LIMITATIONS
                or any(r.status in (AgentStatus.FAILED, AgentStatus.DEGRADED)
                       or r.fallback_used
                       for r in agent_results.values())
                or synthesis is None or synthesis.fallback_used
                or verdict is None
                or verdict.review_result in (
                    CriticReviewResult.NEEDS_REVISION.value,
                    CriticReviewResult.BLOCKED.value)
            )
            run_status = (STATUS_COMPLETED_WITH_LIMITATIONS if degraded
                          else STATUS_COMPLETED)

        # ── provenance (gate §8/§14 + §18 DeepSeek usage record) ──
        provenance = {
            "gate": "G03C",
            "workflow_version": WORKFLOW_VERSION,
            "scan_mode": scan_mode,
            "region_config_version": region.config_version,
            "scoring_config_version": region.scoring_config_version,
            "algorithm_version": watch_result.algorithm_version,
            "formula_version": watch_result.formula_version,
            "engine_provenance": dict(watch_result.provenance),
            "weather": {
                "status": weather.status,
                "retrieval_time": weather.retrieval_time,
                "endpoint": FORECAST_ENDPOINT,
                "model": FORECAST_MODEL,
                "coverage": dict(weather.coverage),
                "from_cache": {
                    pid: (pw.provenance.get("from_cache")
                          if isinstance(pw, PointWeather) else None)
                    for pid, pw in weather.points.items()},
            },
            "climatology": {
                "references": data_quality["climatology_references"],
                "generated_now": dict(climatology_generated_now),
            },
            "previous_state": previous.to_dict() if previous else None,
            "provider": (counting.summary() if counting is not None
                         else {"provider_name": None,
                               "generation_calls": 0,
                               "note": "no model provider — deterministic "
                                       "fallback path only"}),
        }

        result = RiskWatchRunResult(
            run_id=run_id,
            region_id=region.region_id,
            created_time=created_time,
            status=run_status,
            scan_mode=scan_mode,
            deterministic_result=watch_result,
            agent_results=dict(agent_results),
            synthesis=synthesis,
            synthesis_status=synthesis_status,
            critic=verdict,
            critic_status=critic_status,
            limitations=tuple(_dedupe(limitations)),
            provenance=provenance,
            data_quality=data_quality,
            ai_layer=ai_layer,
            data_snapshot_id=data_snapshot_id,
        )

        # ── Step 10: persist the final Risk Watch result (immutable) ──
        try:
            result_snapshot_id = store.insert_snapshot(
                run_id=run_id, region_id=region.region_id,
                status=run_status, payload=result.snapshot_payload(),
                created_at=_clock().isoformat(), scan_mode=scan_mode,
                config_version=region.config_version)
        except Exception as exc:
            raise RiskScanError(
                f"result snapshot persistence failed — scan fails safe; "
                f"no result is presented without its immutable record: "
                f"{type(exc).__name__}: {exc}") from exc

        trend = query_historical_trend(store, region.region_id)
        _stage(STAGE_COMPLETED)
        final = replace(
            result,
            result_snapshot_id=result_snapshot_id,
            historical_trend=trend,
            stage_trace=tuple(trace))
        logger.info(
            "[risk_watch] scan %s finished: status=%s C=%r level=%s "
            "critic=%s snapshots=(%s, %s)",
            run_id, final.status, final.risk_index, final.risk_level,
            final.critic_status, data_snapshot_id, result_snapshot_id)
        return final
    finally:
        if owns_store:
            store.close()


def _dedupe(items: Sequence[str]) -> list:
    seen, out = set(), []
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(str(x))
    return out
