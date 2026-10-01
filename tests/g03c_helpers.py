"""Shared deterministic fixtures/helpers for G03C Risk Watch workflow tests.

Everything here is OFFLINE: synthetic region configs (via the G03B
helpers), fake weather collectors built on the real G03A normalized
contracts, cached synthetic climatology references, temporary snapshot
databases and scripted model providers. Ordinary pytest never touches the
network or a paid model through these helpers.
"""

from __future__ import annotations

import copy
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from providers.base_provider import (  # noqa: E402
    ModelProvider,
    ModelRequest,
    ModelResult,
    ProviderErrorCategory,
    ProviderStatus,
    validate_json_schema,
)
from riskwatch.climatology import ClimatologyStore  # noqa: E402
from riskwatch.engine.core import compute_risk_watch  # noqa: E402
from riskwatch.engine.static_baseline import (  # noqa: E402
    compute_static_baseline,
    derive_static_baseline_section,
)
from riskwatch.region import RegionConfig  # noqa: E402
from riskwatch.weather import (  # noqa: E402
    PointWeather,
    PointWeatherFailure,
    RegionWeatherResult,
)
from tests.g03b_helpers import (  # noqa: E402
    FIXED_RETRIEVAL_TIME,
    flat_climatologies,
    flat_weather,
    write_region,
)

FIXED_CENTER = date(2026, 8, 15)
FIXED_CLOCK = datetime(2026, 8, 15, 6, 0, 0, tzinfo=timezone.utc)


def fixed_clock() -> Callable[[], datetime]:
    return lambda: FIXED_CLOCK


# ─── region + runtime fixture ────────────────────────────────────────────────
def make_test_region(tmp_path: Path, with_derived: bool = True,
                     region_id: str = "test_region", **kwargs) -> RegionConfig:
    """Write a synthetic region.json (through the real G03A loader).

    with_derived=True attaches a machine-derived DERIVED static-baseline
    section so the engine reports stored_derived_match=True (the same
    discipline as the production region.json).
    """
    regions_dir = tmp_path / "regions"
    region = write_region(regions_dir, region_id=region_id, **kwargs)
    if with_derived:
        baseline = compute_static_baseline(region)
        derived = derive_static_baseline_section(
            baseline, generated_at=FIXED_RETRIEVAL_TIME)
        region = write_region(regions_dir, region_id=region_id,
                              derived=derived, **kwargs)
    return region


def make_runtime(tmp_path: Path,
                 climatologies: Optional[dict] = None) -> Path:
    """Runtime dir with cached synthetic climatology references."""
    runtime = tmp_path / "runtime"
    store = ClimatologyStore(runtime / "climatology")
    for ref in (climatologies if climatologies is not None
                else flat_climatologies()).values():
        store.save(ref)
    return runtime


def expected_engine_result(region: RegionConfig,
                           weather_map: Optional[dict] = None,
                           run_id: str = "expected") -> Any:
    """Direct G03B computation over the same fixtures — the authoritative
    expected deterministic result for workflow assertions (pure function,
    same input → same output)."""
    weather_map = weather_map if weather_map is not None \
        else flat_weather(FIXED_CENTER)
    return compute_risk_watch(
        region, weather_map, flat_climatologies(),
        previous=None, run_id=run_id)


# ─── fake G03A collector ─────────────────────────────────────────────────────
class FakeCollector:
    """Stands in for WeatherCollector.collect_region (records invocations).

    Builds a real RegionWeatherResult from a point map of PointWeather /
    PointWeatherFailure objects — the exact G03A contract the engine and
    the workflow consume.
    """

    def __init__(self, points: dict, retrieval_time: str = FIXED_RETRIEVAL_TIME,
                 status: Optional[str] = None):
        self.points = points
        self.retrieval_time = retrieval_time
        self._status = status
        self.calls: list = []
        self.result: Optional[RegionWeatherResult] = None

    def collect_region(self, region: RegionConfig) -> RegionWeatherResult:
        self.calls.append(region.region_id)
        ok = [pid for pid, p in self.points.items()
              if isinstance(p, PointWeather)]
        failed = [pid for pid, p in self.points.items()
                  if isinstance(p, PointWeatherFailure)]
        status = self._status or ("OK" if ok and not failed
                                  else "PARTIAL" if ok else "FAILED")
        self.result = RegionWeatherResult(
            region_id=region.region_id,
            retrieval_time=self.retrieval_time,
            status=status,
            points=dict(self.points),
            coverage={
                "required_points_total": len(self.points),
                "required_points_ok": len(ok),
                "required_points_failed": len(failed),
                "failed_points": [
                    {"point_id": pid,
                     "reason": self.points[pid].message,
                     "error_type": self.points[pid].error_type}
                    for pid in failed],
                "evidence_coverage_reduced": bool(failed),
            })
        return self.result


def failing_collector(error_type: str = "WeatherTimeoutError",
                      message: str = "timeout after 15.0s") -> FakeCollector:
    """All-point weather failure (doc 04 §36: required data unavailable)."""
    return FakeCollector({
        "source_zone": PointWeatherFailure("source_zone", error_type, message),
        "port_zone": PointWeatherFailure("port_zone", error_type, message),
    })


def partial_collector() -> FakeCollector:
    """Source Zone OK, Port Zone failed (doc 04 §37 partial point failure)."""
    weather = flat_weather(FIXED_CENTER)
    weather["port_zone"] = PointWeatherFailure(
        "port_zone", "WeatherTransientError", "HTTP 503 from provider")
    return FakeCollector(weather)


# ─── scripted model provider (adapted from the G02B test harness) ────────────
def agent_payload(agent_name: str, evidence_ids: Optional[list] = None,
                  risk_signal: str = "ELEVATED",
                  confidence: float = 0.7) -> dict:
    """Minimal VALID structured payload per agent output schema."""
    base = {
        "agent": agent_name,
        "status": "COMPLETED",
        "risk_signal": risk_signal,
        "confidence": confidence,
        "key_findings": [
            "evidence suggests elevated background susceptibility",
            "indications are consistent with the authorized evidence only",
        ],
        "evidence_ids": list(evidence_ids or []),
        "missing_data": ["源区实时位移/微震监测数据（未获得公开数据）"],
        "limitations": ["结论仅限于授权证据范围；置信度不是灾害发生概率。"],
    }
    specific = {
        "glacier_geology": {"risk_drivers": ["静态易灾背景"]},
        "weather_hydrology": {"recent_conditions": ["近7天降水偏多"],
                              "forecast_signals": ["未来7天仍有降水"]},
        "remote_sensing": {"image_ids": [], "observations": [],
                           "quality_notes": ["无可用授权影像"]},
    }
    base.update(specific.get(agent_name, {}))
    return base


def synthesis_payload(risk_index: float, risk_level: str) -> dict:
    """Valid synthesis payload echoing the deterministic values."""
    return {
        "risk_index": risk_index,
        "risk_level": risk_level,
        "summary": (f"当前风险指数 C={risk_index:.2f}（{risk_level} 原型风险"
                    f"带），主要由静态易灾背景与降水百分位驱动。该指数不是"
                    f"灾害发生概率。"),
        "risk_explanation": (
            f"确定性引擎给出 C={risk_index:.2f}，风险带 {risk_level}；"
            "静态易灾基线 B 贡献最大，近期与预报降水百分位提供动态触发"
            "背景。风险指数不是灾害发生概率，也不指示具体发生时刻。"),
        "top_drivers": ["静态易灾背景（B）", "近期降水百分位（R）",
                        "预报降水百分位（F）"],
        "agent_agreement": "AGREEMENT",
        "disagreements": [],
        "evidence_coverage": 0.8,
        "missing_data": ["源区实时动态监测数据（未获得公开数据）"],
        "limitations": ["网格化模型天气非现场实测。"],
        "explanation_confidence": 0.6,
        "evidence_ids": ["RW-ENGINE-C", "RW-STATIC-B",
                         "RW-WX-source_zone-RECENT"],
    }


def critic_payload(review_result: str = "PASS_WITH_LIMITATIONS") -> dict:
    return {
        "review_result": review_result,
        "issues": [],
        "scientific_limitations": ["缺少源区实时动态监测数据。"],
        "required_corrections": [],
    }


class ScriptedProvider(ModelProvider):
    """Mock provider applying the SAME validation pipeline as the real one.

    Dispatch by request kind (synthesis / critic / agent:<name>);
    `fail_kinds` forces provider failure for a kind; callable responses are
    invoked with the request. Records every call for audit assertions.
    """

    provider_name = "mock"
    model_id = "mock-flash"

    def __init__(self, agent_responses: Optional[dict] = None,
                 synthesis_response=None, critic_response=None,
                 fail_kinds=(), default_agent=None):
        self.agent_responses = agent_responses or {}
        self.synthesis_response = synthesis_response
        self.critic_response = critic_response
        self.fail_kinds = set(fail_kinds)
        self.default_agent = default_agent
        self.calls: list = []

    @staticmethod
    def _kind(request: ModelRequest) -> str:
        schema = request.schema or {}
        props = schema.get("properties", {})
        if "risk_explanation" in props:
            return "synthesis"
        if "review_result" in props:
            return "critic"
        agent_enum = props.get("agent", {}).get("enum")
        if agent_enum:
            return f"agent:{agent_enum[0]}"
        return "unknown"

    def _response_for(self, kind: str, request: ModelRequest):
        if kind == "synthesis":
            return self.synthesis_response
        if kind == "critic":
            return self.critic_response
        if kind.startswith("agent:"):
            name = kind.split(":", 1)[1]
            if name in self.agent_responses:
                return self.agent_responses[name]
            return self.default_agent
        return None

    def _handle(self, request: ModelRequest, images) -> ModelResult:
        kind = self._kind(request)
        self.calls.append({
            "kind": kind, "request_id": request.request_id,
            "run_id": request.run_id,
            "system_prompt": request.system_prompt,
            "user_prompt": request.user_prompt,
            "images": list(images) if images else None,
        })

        def failure(message: str = "scripted provider failure") -> ModelResult:
            has_fb = request.fallback_data is not None
            return ModelResult(
                success=False,
                data=request.fallback_data if has_fb else None,
                status=(ProviderStatus.FALLBACK_ACTIVE if has_fb
                        else ProviderStatus.OFFLINE),
                fallback_used=has_fb,
                error_category=ProviderErrorCategory.SERVICE_UNAVAILABLE,
                error_message=message,
                provider=self.provider_name, model_id=self.model_id,
                request_id=request.request_id, run_id=request.run_id,
                latency_ms=1)

        if kind in self.fail_kinds:
            return failure()
        resp = self._response_for(kind, request)
        if callable(resp):
            resp = resp(request)
        if isinstance(resp, Exception):
            raise resp
        if resp is None:
            return failure("no scripted response")
        data = resp
        errors = validate_json_schema(data, request.schema)
        if not errors and request.output_validator is not None:
            errors = request.output_validator(data) or []
        if errors:
            return ModelResult(
                success=False,
                data=request.fallback_data,
                status=(ProviderStatus.FALLBACK_ACTIVE
                        if request.fallback_data is not None
                        else ProviderStatus.DEGRADED),
                fallback_used=request.fallback_data is not None,
                error_category=ProviderErrorCategory.SCHEMA_ERROR,
                error_message="; ".join(str(e) for e in errors[:5]),
                provider=self.provider_name, model_id=self.model_id,
                request_id=request.request_id, run_id=request.run_id,
                latency_ms=1)
        return ModelResult(
            success=True, data=copy.deepcopy(data),
            status=ProviderStatus.CONNECTED, fallback_used=False,
            provider=self.provider_name, model_id=self.model_id,
            request_id=request.request_id, run_id=request.run_id,
            latency_ms=1, http_status=200,
            token_usage={"prompt_tokens": 10, "completion_tokens": 5,
                         "total_tokens": 15})

    def generate_structured(self, request: ModelRequest) -> ModelResult:
        return self._handle(request, None)

    def generate_multimodal(self, request: ModelRequest,
                            images: Optional[list] = None) -> ModelResult:
        return self._handle(request, images)

    def health_check(self):
        from providers.base_provider import ProviderHealth

        return ProviderHealth(status=ProviderStatus.CONNECTED,
                              model_id=self.model_id, detail="scripted")


def fully_scripted_provider(expected: Any) -> ScriptedProvider:
    """Provider whose scripted outputs are all valid for `expected` (the
    direct G03B engine result over the same fixtures)."""
    return ScriptedProvider(
        agent_responses={
            "glacier_geology": agent_payload(
                "glacier_geology",
                evidence_ids=["RW-STATIC-TERRAIN", "RW-STATIC-B"]),
            "weather_hydrology": agent_payload(
                "weather_hydrology",
                evidence_ids=["RW-WX-source_zone-RECENT", "RW-ENGINE-D-RF"]),
            "remote_sensing": agent_payload("remote_sensing"),
        },
        synthesis_response=synthesis_payload(
            expected.C, expected.current_risk_level),
        critic_response=critic_payload(),
    )
