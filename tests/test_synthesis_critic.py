"""
MountainGuardian G02B – Risk Synthesizer, Critic, Stage-A freeze and
Stage-B validation tests (mock only).

Covers (Gate spec §22):
   1 Risk Index 91 regression        16 causal-overclaim detection
   2 Synthesizer cannot change 91    17 probability-misuse detection
   3 Synthesizer structured output   18 missing-data honesty
   4 top drivers                     19 disagreement handling
   5 evidence coverage               20 satellite-overclaim detection
   6 missing-data propagation        21 Critic model failure
   7 agent agreement                 22 schema repair (degraded success)
   8 agent disagreement              23 Stage-A freeze
   9 one agent failed                24 Stage-B cannot alter Stage A
  10 one agent skipped               25 Stage-B cannot alter Risk Index
  11 Synthesizer fallback            26 Stage-B evidence never in Stage-A
  12 Critic structured verdict          provider calls
  13 evidence support check          27 full Historical Replay mock workflow
  14 hallucinated Evidence ID        28 professional-agent failure isolation
  15 post-event leakage detection    29 no paid/network call in pytest

All tests use scripted/mock providers (or none). A module-wide network
guard fails any test that attempts real socket access — ordinary pytest can
never reach a paid model.
"""

import copy
import dataclasses
import json
import socket
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.critic import Critic
from agents.professional_base import run_professional_agents
from agents.risk_synthesizer import RiskSynthesizer
from agents.remote_sensing_agent import SKIP_NO_USABLE_IMAGERY
from orchestration.context_builder import (
    AnalysisContext,
    agent_evidence_view,
    build_analysis_context,
)
from orchestration.replay_orchestrator import (
    FrozenStateError,
    StageAFreeze,
    run_historical_replay,
    run_stage_a,
    run_stage_b,
)
from orchestration.risk_engine import (
    HistoricalRiskResult,
    RiskEngineError,
    compute_historical_risk,
    risk_level_for,
)
from providers.base_provider import (
    ModelProvider,
    ModelRequest,
    ModelResult,
    ProviderErrorCategory,
    ProviderHealth,
    ProviderStatus,
    validate_json_schema,
)
from schemas.agent_outputs import AgentRunResult, AgentStatus, RiskSignal
from schemas.evidence import (
    AGENT_GLACIER_GEOLOGY,
    AGENT_REMOTE_SENSING,
    AGENT_WEATHER_HYDROLOGY,
)
from schemas.synthesis import (
    SYNTHESIS_OUTPUT_SCHEMA,
    AgentAgreement,
    CriticReviewResult,
    IssueSeverity,
    SynthesisResult,
    make_synthesis_validator,
)


# ─── network guard: no test may touch the network (no paid calls) ─────────────
@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def _guard(*args, **kwargs):
        raise AssertionError(
            "network access attempted in mock test suite — ordinary pytest "
            "must never call a paid model")
    monkeypatch.setattr(socket, "socket", _guard)
    monkeypatch.setattr(socket, "create_connection", _guard)


# ─── scripted provider: dispatches validated responses per component ──────────
class ScriptedProvider(ModelProvider):
    """Mock provider applying the SAME validation pipeline as the real one.

    Responses are dispatched by request kind:
      * synthesis schema  → synthesis_response
      * critic schema     → critic_response
      * agent schema      → agent_responses[agent_name] (or default)
      * callable          → called with the request
    A `fail_kinds` set forces provider failure for that kind
    ("agent:<name>", "synthesis", "critic").
    """

    provider_name = "mock"
    model_id = "mock-flash"

    def __init__(self, agent_responses=None, synthesis_response=None,
                 critic_response=None, fail_kinds=(), default_agent=None):
        self.agent_responses = agent_responses or {}
        self.synthesis_response = synthesis_response
        self.critic_response = critic_response
        self.fail_kinds = set(fail_kinds)
        self.default_agent = default_agent
        self.calls = []

    # kind detection
    @staticmethod
    def _kind(request):
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

    def _response_for(self, kind, request):
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

    def _handle(self, request, images):
        kind = self._kind(request)
        self.calls.append({
            "kind": kind, "request": request,
            "system_prompt": request.system_prompt,
            "user_prompt": request.user_prompt,
            "images": list(images) if images else None,
        })

        def failure(message="scripted provider failure"):
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
            latency_ms=5, http_status=200,
            token_usage={"prompt_tokens": 100, "completion_tokens": 50,
                         "total_tokens": 150})

    def generate_structured(self, request):
        return self._handle(request, None)

    def generate_multimodal(self, request, images=None):
        return self._handle(request, images)

    def health_check(self):
        return ProviderHealth(status=ProviderStatus.CONNECTED,
                              model_id=self.model_id)


# ─── fixtures & helpers ───────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def ctx():
    return build_analysis_context()


@pytest.fixture(scope="module")
def risk(ctx):
    return compute_historical_risk(run_id=ctx.run_id)


def _agent_ids(ctx, name):
    return sorted(agent_evidence_view(ctx, name).allowed_evidence_ids())


def _agent_response(name, ctx, signal="HIGH", **overrides):
    base_extra = {
        AGENT_GLACIER_GEOLOGY: {"risk_drivers": ["高位冰岩源区", "陡峭沟谷"]},
        AGENT_WEATHER_HYDROLOGY: {"recent_conditions": ["雨季背景"],
                                  "forecast_signals": []},
        AGENT_REMOTE_SENSING: {"image_ids": [], "observations": ["河谷基线形态"],
                               "quality_notes": ["云量与分辨率限制"]},
    }[name]
    data = {
        "agent": name,
        "status": "COMPLETED",
        "risk_signal": signal,
        "confidence": 0.8,
        "key_findings": [f"{name} mock 专业判断：静态易灾条件显著"],
        "evidence_ids": _agent_ids(ctx, name)[:3],
        "missing_data": ["灾前实时源区动态监测数据缺失"],
        "limitations": ["历史回放分析，不构成实时预警"],
        **base_extra,
    }
    data.update(overrides)
    return data


def _all_agent_responses(ctx, signal="HIGH"):
    return {
        name: _agent_response(name, ctx, signal=signal)
        for name in (AGENT_GLACIER_GEOLOGY, AGENT_WEATHER_HYDROLOGY,
                     AGENT_REMOTE_SENSING)
    }


def _synthesis_response(risk, ctx, **overrides):
    allowed = sorted(ctx.evidence_by_id().keys())
    data = {
        "risk_index": risk.risk_index,
        "risk_level": risk.risk_level,
        "summary": "静态易灾条件组合导致基础易灾风险指数处于高位（确定性引擎结果，非概率）。",
        "risk_explanation": ("六因子冻结模型复算得到 91.0 / 100（HIGH）。"
                             "巨大高差与狭窄沟谷、沟道松散物源和高海拔冰冻圈源区"
                             "是主要贡献因子。该指数不是灾害发生概率。"),
        "top_drivers": ["巨大高差与狭窄沟谷", "沟道松散物源", "高海拔冰冻圈源区"],
        "agent_agreement": AgentAgreement.AGREEMENT.value,
        "disagreements": [],
        "evidence_coverage": 1.0,
        "missing_data": ["灾前实时源区动态监测数据（位移/微震）缺失"],
        "limitations": ["缺少灾前动态前兆数据，无法判断事件具体发生时刻。"],
        "explanation_confidence": 0.75,
        "evidence_ids": allowed[:5],
    }
    data.update(overrides)
    return data


def _critic_response(result="PASS_WITH_LIMITATIONS"):
    return {
        "review_result": result,
        "issues": ["mock 审查：部分结论表述可更保守"],
        "scientific_limitations": ["缺少灾前动态监测数据"],
        "required_corrections": [],
    }


def _full_provider(ctx, risk, **kwargs):
    kwargs.setdefault("synthesis_response", _synthesis_response(risk, ctx))
    kwargs.setdefault("critic_response", _critic_response())
    kwargs.setdefault("default_agent", None)
    if kwargs.get("agent_responses") is None:
        kwargs["agent_responses"] = _all_agent_responses(ctx)
    return ScriptedProvider(**kwargs)


def _make_agent_result(name, status=AgentStatus.COMPLETED, signal="HIGH",
                       run_id="t", findings=None, missing=None,
                       fallback=False, is_model=True, **kw):
    return AgentRunResult(
        agent_name=name, status=status, run_id=run_id,
        risk_signal=signal, confidence=0.7,
        key_findings=findings if findings is not None else ["mock 判断"],
        evidence_ids=[], missing_data=missing if missing is not None
        else ["动态监测数据缺失"],
        limitations=[], fallback_used=fallback,
        is_model_output=is_model and not fallback, **kw)


def _run_synthesis(ctx, risk, provider, agent_results=None):
    agent_results = agent_results if agent_results is not None else {
        name: _make_agent_result(name) for name in (
            AGENT_GLACIER_GEOLOGY, AGENT_WEATHER_HYDROLOGY,
            AGENT_REMOTE_SENSING)}
    return RiskSynthesizer(provider=provider).run(
        agent_results, risk, ctx), agent_results


def _post_event_markers():
    """Markers that must NEVER appear in any Stage-A provider prompt.

    Values are restricted to distinctive outcome observations (mirrors
    Critic._OUTCOME_VALUE_KEYS): mechanism vocabulary (e.g. the actual
    trigger phrase) legitimately overlaps pre-event susceptibility
    language and is therefore not a prompt-leak marker.
    """
    from agents.critic import Critic
    from tools.case_loader import load_case
    case = load_case()
    values = {str(f.get("value")) for f in case["post_event"]
              if str(f.get("key")) in Critic._OUTCOME_VALUE_KEYS
              and len(str(f.get("value") or "")) >= 4}
    ids = {"EV-SAT-POST", "post_event_validation",
           "actual_runout_km", "actual_travel_time_min"}
    return case, values, ids


# ═══════════════════════════════════════════════════════════════════════════════
# 1 — deterministic risk engine: 91/100 regression & immutability
# ═══════════════════════════════════════════════════════════════════════════════
class TestDeterministicRiskEngine:
    def test_risk_index_91_regression(self, risk):
        assert risk.risk_index == 91.0
        assert risk.risk_level == "HIGH"
        assert risk.pack_stated_index == 91.0
        assert risk.weight_sum == 100.0
        assert len(risk.factors) == 6
        assert "不是灾害发生概率" in risk.semantics

    def test_deterministic_recomputation(self, risk):
        again = compute_historical_risk(run_id=risk.run_id)
        assert again.risk_index == risk.risk_index
        assert [f.contribution for f in again.factors] == \
            [f.contribution for f in risk.factors]

    def test_result_is_immutable(self, risk):
        with pytest.raises(dataclasses.FrozenInstanceError):
            risk.risk_index = 50.0
        with pytest.raises(dataclasses.FrozenInstanceError):
            risk.risk_level = "LOW"

    def test_risk_level_bands(self):
        assert risk_level_for(0) == "LOW"
        assert risk_level_for(39) == "LOW"
        assert risk_level_for(40) == "MODERATE"
        assert risk_level_for(59) == "MODERATE"
        assert risk_level_for(60) == "ELEVATED"
        assert risk_level_for(79) == "ELEVATED"
        assert risk_level_for(80) == "HIGH"
        assert risk_level_for(100) == "HIGH"

    def test_tampered_weights_raise(self):
        from tools.case_loader import load_case
        case = load_case()
        case = copy.deepcopy(case)
        case["risk_model"]["factors"][0]["weight_pct"] = 30
        with pytest.raises(RiskEngineError):
            compute_historical_risk(case)

    def test_tampered_score_breaking_stated_index_raises(self):
        from tools.case_loader import load_case
        case = copy.deepcopy(load_case())
        case["risk_model"]["factors"][0]["score_0_to_5"] = 1
        with pytest.raises(RiskEngineError):
            compute_historical_risk(case)

    def test_top_drivers_sorted_by_contribution(self, risk):
        drivers = risk.top_drivers(3)
        assert len(drivers) == 3
        assert "巨大高差与狭窄沟谷" in drivers[0]


# ═══════════════════════════════════════════════════════════════════════════════
# 3/4/5/6/7/22 — Synthesizer structured output
# ═══════════════════════════════════════════════════════════════════════════════
class TestSynthesizerStructured:
    def test_structured_output(self, ctx, risk):
        provider = _full_provider(ctx, risk)
        result, agents = _run_synthesis(ctx, risk, provider)
        assert result.is_model_output is True
        assert result.fallback_used is False
        assert result.deterministic_risk_index == 91.0
        assert result.risk_level == "HIGH"
        assert result.summary and result.risk_explanation
        assert result.top_drivers, "top drivers produced (#4)"
        assert 0.0 <= result.evidence_coverage <= 1.0, "(#5)"
        assert result.missing_data, "missing-data propagated (#6)"
        assert result.agent_agreement in {a.value for a in AgentAgreement}
        assert 0.0 <= result.explanation_confidence <= 1.0
        allowed = set(ctx.evidence_by_id().keys())
        assert set(result.evidence_ids) <= allowed
        assert result.provider == "mock" and result.model_id == "mock-flash"
        assert result.run_id == risk.run_id
        assert result.prompt_id == "risk_synthesizer_v1"
        assert result.token_usage.get("total_tokens") == 150
        synth_calls = [c for c in provider.calls if c["kind"] == "synthesis"]
        assert len(synth_calls) == 1, "exactly one bounded synthesis call"

    def test_agent_status_summary_exposed(self, ctx, risk):
        provider = _full_provider(ctx, risk)
        agents = {
            AGENT_GLACIER_GEOLOGY: _make_agent_result(
                AGENT_GLACIER_GEOLOGY),
            AGENT_WEATHER_HYDROLOGY: _make_agent_result(
                AGENT_WEATHER_HYDROLOGY, status=AgentStatus.FAILED,
                signal=None),
            AGENT_REMOTE_SENSING: _make_agent_result(
                AGENT_REMOTE_SENSING, status=AgentStatus.SKIPPED,
                signal=None),
        }
        result = RiskSynthesizer(provider=provider).run(agents, risk, ctx)
        assert result.agent_status_summary == {
            AGENT_GLACIER_GEOLOGY: "COMPLETED",
            AGENT_WEATHER_HYDROLOGY: "FAILED",
            AGENT_REMOTE_SENSING: "SKIPPED",
        }
        # coverage: documented blend of agent credit and evidence ratio
        expected = RiskSynthesizer.compute_evidence_coverage(agents, ctx)
        assert result.evidence_coverage == expected
        assert result.evidence_coverage < 1.0, \
            "reduced agent availability must lower coverage"

    def test_schema_repair_success_is_degraded_not_fallback(self, ctx, risk):
        """A provider that succeeded after bounded repair reports DEGRADED
        status; the synthesis is still real model output (#22 at the
        synthesis layer — repair itself is provider-level, G01-tested)."""
        provider = _full_provider(ctx, risk)
        orig = provider._handle

        def patched(request, images):
            res = orig(request, images)
            if res.success and provider._kind(request) == "synthesis":
                res.status = ProviderStatus.DEGRADED
            return res
        provider._handle = patched
        result, _ = _run_synthesis(ctx, risk, provider)
        assert result.is_model_output is True
        assert result.fallback_used is False
        assert result.provider_status == ProviderStatus.DEGRADED.value

    def test_missing_data_union_from_agents_and_context(self, ctx, risk):
        provider = _full_provider(ctx, risk)
        agents = {
            AGENT_GLACIER_GEOLOGY: _make_agent_result(
                AGENT_GLACIER_GEOLOGY, missing=["缺口A"]),
            AGENT_WEATHER_HYDROLOGY: _make_agent_result(
                AGENT_WEATHER_HYDROLOGY, missing=["缺口B"]),
            AGENT_REMOTE_SENSING: _make_agent_result(
                AGENT_REMOTE_SENSING, missing=["缺口A"]),
        }
        result = RiskSynthesizer(provider=provider).run(agents, risk, ctx)
        assert "缺口A" in result.missing_data
        assert "缺口B" in result.missing_data
        # context missing sources are also represented
        assert any("未获得公开灾前数据" in m for m in result.missing_data)

    def test_validator_rejects_index_change(self, risk, ctx):
        v = make_synthesis_validator(91.0, "HIGH",
                                     frozenset(ctx.evidence_by_id()))
        bad = _synthesis_response(risk, ctx, risk_index=50)
        assert any("risk_index" in e for e in v(bad))
        bad2 = _synthesis_response(risk, ctx, risk_level="LOW")
        assert any("risk_level" in e for e in v(bad2))
        ok = _synthesis_response(risk, ctx)
        assert v(ok) == []


# ═══════════════════════════════════════════════════════════════════════════════
# 2/11/14 — score protection, fallback, hallucinated ids
# ═══════════════════════════════════════════════════════════════════════════════
class TestScoreProtectionAndFallback:
    def test_synthesizer_cannot_change_91(self, ctx, risk):
        """Model output altering the index is rejected → deterministic
        fallback keeps 91 (#2). No unbounded retries."""
        provider = _full_provider(
            ctx, risk,
            synthesis_response=_synthesis_response(risk, ctx,
                                                   risk_index=42.0))
        result, _ = _run_synthesis(ctx, risk, provider)
        assert result.deterministic_risk_index == 91.0
        assert result.risk_level == "HIGH"
        assert result.is_model_output is False
        assert result.fallback_used is True
        synth_calls = [c for c in provider.calls if c["kind"] == "synthesis"]
        assert len(synth_calls) == 1, "no unbounded retries"

    def test_hallucinated_evidence_id_rejected(self, ctx, risk):
        provider = _full_provider(
            ctx, risk,
            synthesis_response=_synthesis_response(
                risk, ctx, evidence_ids=["EV-FAKE-0001"]))
        result, _ = _run_synthesis(ctx, risk, provider)
        assert result.is_model_output is False
        assert result.fallback_used is True
        assert "EV-FAKE-0001" not in result.evidence_ids, \
            "hallucinated id must never be accepted (#14)"

    def test_synthesizer_fallback_explicit(self, ctx, risk):
        provider = _full_provider(ctx, risk, fail_kinds={"synthesis"})
        result, _ = _run_synthesis(ctx, risk, provider)
        assert result.fallback_used is True
        assert result.is_model_output is False
        assert result.deterministic_risk_index == 91.0
        assert result.top_drivers, "fallback summarizes deterministic drivers"
        assert result.missing_data, "fallback exposes missing data"
        assert any("回退" in l or "fallback" in l.lower()
                   for l in result.limitations)
        assert result.error_category is not None
        assert result.provider_status in (
            ProviderStatus.FALLBACK_ACTIVE.value,
            ProviderStatus.OFFLINE.value)

    def test_no_provider_fallback(self, ctx, risk):
        result, _ = _run_synthesis(ctx, risk, None)
        assert result.fallback_used is True
        assert result.is_model_output is False
        assert result.deterministic_risk_index == 91.0
        assert result.error_category == "NO_PROVIDER"

    def test_fallback_never_masquerades(self, ctx, risk):
        provider = _full_provider(ctx, risk, fail_kinds={"synthesis"})
        result, _ = _run_synthesis(ctx, risk, provider)
        d = result.to_dict()
        assert d["is_model_output"] is False
        assert d["fallback_used"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# 7/8/9/10/19/28 — agreement, disagreement, failure isolation
# ═══════════════════════════════════════════════════════════════════════════════
class TestAgreementAndIsolation:
    def test_agreement_computed(self, ctx, risk):
        agents = {n: _make_agent_result(n, signal="HIGH") for n in (
            AGENT_GLACIER_GEOLOGY, AGENT_WEATHER_HYDROLOGY,
            AGENT_REMOTE_SENSING)}
        agreement, disagreements, absent =             RiskSynthesizer.compute_agreement(agents)
        assert agreement == AgentAgreement.AGREEMENT.value
        assert disagreements == [] and absent == []

    def test_partial_agreement(self, ctx, risk):
        agents = {
            AGENT_GLACIER_GEOLOGY: _make_agent_result(
                AGENT_GLACIER_GEOLOGY, signal="HIGH"),
            AGENT_WEATHER_HYDROLOGY: _make_agent_result(
                AGENT_WEATHER_HYDROLOGY, signal="ELEVATED"),
            AGENT_REMOTE_SENSING: _make_agent_result(
                AGENT_REMOTE_SENSING, signal="HIGH"),
        }
        agreement, disagreements, absent =             RiskSynthesizer.compute_agreement(agents)
        assert agreement == AgentAgreement.PARTIAL_AGREEMENT.value
        assert disagreements

    def test_significant_disagreement(self, ctx, risk):
        agents = {
            AGENT_GLACIER_GEOLOGY: _make_agent_result(
                AGENT_GLACIER_GEOLOGY, signal="HIGH"),
            AGENT_WEATHER_HYDROLOGY: _make_agent_result(
                AGENT_WEATHER_HYDROLOGY, signal="LOW"),
            AGENT_REMOTE_SENSING: _make_agent_result(
                AGENT_REMOTE_SENSING, signal="MODERATE"),
        }
        agreement, disagreements, absent =             RiskSynthesizer.compute_agreement(agents)
        assert agreement == AgentAgreement.SIGNIFICANT_DISAGREEMENT.value
        assert disagreements, "disagreement must never be hidden (#8)"

    def test_failed_and_skipped_agents_do_not_vote(self, ctx):
        agents = {
            AGENT_GLACIER_GEOLOGY: _make_agent_result(
                AGENT_GLACIER_GEOLOGY, signal="HIGH"),
            AGENT_WEATHER_HYDROLOGY: _make_agent_result(
                AGENT_WEATHER_HYDROLOGY, status=AgentStatus.FAILED,
                signal=None),
            AGENT_REMOTE_SENSING: _make_agent_result(
                AGENT_REMOTE_SENSING, status=AgentStatus.SKIPPED,
                signal=None),
        }
        agreement, disagreements, absent =             RiskSynthesizer.compute_agreement(agents)
        assert agreement == AgentAgreement.AGREEMENT.value
        # absence is disclosed separately — never conflated with conflict
        assert disagreements == []
        assert any("FAILED" in a for a in absent)
        assert any("SKIPPED" in a for a in absent)
        credit_only = RiskSynthesizer.compute_evidence_coverage(agents)
        assert credit_only == pytest.approx(0.33, abs=0.01)
        blended = RiskSynthesizer.compute_evidence_coverage(agents, ctx)
        available = (len(ctx.allowed_evidence)
                     + len(ctx.context_only_evidence)
                     + len(ctx.pre_event_imagery))
        ratio = available / (available + len(ctx.missing_sources))
        assert blended == pytest.approx(
            round(0.5 * (1.0 / 3.0) + 0.5 * ratio, 2), abs=0.01)
        assert blended < 1.0, "coverage must honestly reflect gaps"

    def test_one_failed_one_skipped_full_synthesis(self, ctx, risk):
        provider = _full_provider(ctx, risk)
        agents = {
            AGENT_GLACIER_GEOLOGY: _make_agent_result(
                AGENT_GLACIER_GEOLOGY, status=AgentStatus.FAILED,
                signal=None, findings=[], missing=[]),
            AGENT_WEATHER_HYDROLOGY: _make_agent_result(
                AGENT_WEATHER_HYDROLOGY),
            AGENT_REMOTE_SENSING: _make_agent_result(
                AGENT_REMOTE_SENSING, status=AgentStatus.SKIPPED,
                signal=None, findings=[], missing=["无可用授权灾前影像"]),
        }
        result = RiskSynthesizer(provider=provider).run(agents, risk, ctx)
        # explicit status for EVERY agent reaches the synthesizer (#9/#10)
        prompt = [c for c in provider.calls if c["kind"] == "synthesis"][0]
        assert "FAILED" in prompt["user_prompt"]
        assert "SKIPPED" in prompt["user_prompt"]
        assert result.deterministic_risk_index == 91.0
        assert result.agent_status_summary[AGENT_GLACIER_GEOLOGY] == "FAILED"
        assert result.agent_status_summary[AGENT_REMOTE_SENSING] == "SKIPPED"

    def test_professional_agent_failure_isolation_in_stage_a(self, ctx):
        """One professional agent crashing must not affect the others
        (#28) — G02A behavior preserved inside the Stage-A DAG."""
        class CrashProvider(ScriptedProvider):
            def _handle(self, request, images):
                kind = self._kind(request)
                if kind == f"agent:{AGENT_WEATHER_HYDROLOGY}":
                    raise RuntimeError("simulated catastrophic crash")
                return super()._handle(request, images)

        provider = CrashProvider(
            agent_responses=_all_agent_responses(ctx))
        results = run_professional_agents(ctx, provider)
        assert results[AGENT_WEATHER_HYDROLOGY].status == AgentStatus.FAILED
        assert results[AGENT_GLACIER_GEOLOGY].status == AgentStatus.COMPLETED
        assert results[AGENT_REMOTE_SENSING].status == AgentStatus.COMPLETED


# ═══════════════════════════════════════════════════════════════════════════════
# 12/13/15/16/17/18/20/21 — Critic programmatic checks & verdicts
# ═══════════════════════════════════════════════════════════════════════════════
def _clean_synthesis(ctx, risk, **overrides) -> SynthesisResult:
    """A well-formed synthesis result (defaults to model output)."""
    data = _synthesis_response(risk, ctx, **overrides)
    return SynthesisResult(
        run_id=risk.run_id,
        deterministic_risk_index=risk.risk_index,
        risk_level=risk.risk_level,
        summary=data["summary"],
        risk_explanation=data["risk_explanation"],
        top_drivers=data["top_drivers"],
        agent_agreement=data["agent_agreement"],
        disagreements=data["disagreements"],
        evidence_coverage=data["evidence_coverage"],
        missing_data=data["missing_data"],
        limitations=data["limitations"],
        explanation_confidence=data["explanation_confidence"],
        evidence_ids=data["evidence_ids"],
        is_model_output=True,
        fallback_used=False,
        provider_status="CONNECTED",
        input_evidence_ids=sorted(ctx.evidence_by_id().keys()),
    )


def _agents_all_completed():
    return {n: _make_agent_result(n) for n in (
        AGENT_GLACIER_GEOLOGY, AGENT_WEATHER_HYDROLOGY, AGENT_REMOTE_SENSING)}


class TestCriticProgrammatic:
    def test_clean_stage_a_passes(self, ctx, risk):
        synthesis = _clean_synthesis(ctx, risk)
        verdict = Critic(provider=None).run(
            synthesis, risk, _agents_all_completed(), ctx)
        assert verdict.review_result in (
            CriticReviewResult.PASS.value,
            CriticReviewResult.PASS_WITH_LIMITATIONS.value)
        assert not [i for i in verdict.issues
                    if i.severity == IssueSeverity.CRITICAL.value]
        assert verdict.risk_index_before == 91.0
        assert verdict.risk_index_after == 91.0

    def test_structured_verdict_taxonomy(self, ctx, risk):
        synthesis = _clean_synthesis(ctx, risk)
        verdict = Critic(provider=None).run(
            synthesis, risk, _agents_all_completed(), ctx)
        assert verdict.review_result in {r.value for r in CriticReviewResult}
        d = verdict.to_dict()
        json.dumps(d, default=str)  # serializable
        assert "issues" in d and "scientific_limitations" in d
        assert set(CriticReviewResult.__members__) == {
            "PASS", "PASS_WITH_LIMITATIONS", "NEEDS_REVISION", "BLOCKED"}

    def test_probability_misuse_detected(self, ctx, risk):
        synthesis = _clean_synthesis(
            ctx, risk,
            summary="本次灾害发生概率为91%，请紧急撤离。")
        verdict = Critic(provider=None).run(
            synthesis, risk, _agents_all_completed(), ctx)
        checks = verdict.programmatic_check_status
        assert "PROBABILITY_MISUSE" in checks
        assert verdict.review_result == CriticReviewResult.NEEDS_REVISION.value

    def test_index_as_percentage_detected(self, ctx, risk):
        synthesis = _clean_synthesis(
            ctx, risk,
            risk_explanation="风险指数91意味着91% 的可能性发生灾害。")
        verdict = Critic(provider=None).run(
            synthesis, risk, _agents_all_completed(), ctx)
        assert "PROBABILITY_MISUSE" in verdict.programmatic_check_status

    def test_timing_probability_detected(self, ctx, risk):
        synthesis = _clean_synthesis(
            ctx, risk, summary="未来3天内发生灾害的可能性为60%。")
        verdict = Critic(provider=None).run(
            synthesis, risk, _agents_all_completed(), ctx)
        assert "PROBABILITY_MISUSE" in verdict.programmatic_check_status

    def test_negated_probability_statement_not_flagged(self, ctx, risk):
        synthesis = _clean_synthesis(
            ctx, risk,
            summary="该指数不是灾害发生概率，不得表述为91%的概率。")
        verdict = Critic(provider=None).run(
            synthesis, risk, _agents_all_completed(), ctx)
        assert "PROBABILITY_MISUSE" not in verdict.programmatic_check_status

    def test_postfixed_negation_disclaimer_not_leakage(self, ctx, risk):
        """Chinese disclaimers put the negation AFTER the topic
        ("实际灾害路径无法预知") — this is honest limitation language,
        not post-event leakage (live-run false positive, fixed)."""
        synthesis = _clean_synthesis(
            ctx, risk,
            limitations=["实际灾害路径与具体发生时刻无法提前预知，"
                         "只能给出静态易灾背景。"])
        verdict = Critic(provider=None).run(
            synthesis, risk, _agents_all_completed(), ctx)
        assert "POST_EVENT_LEAKAGE" not in verdict.programmatic_check_status

    def test_assertive_post_event_phrase_still_flagged(self, ctx, risk):
        synthesis = _clean_synthesis(
            ctx, risk, summary="分析显示实际灾害路径沿主沟向下。")
        verdict = Critic(provider=None).run(
            synthesis, risk, _agents_all_completed(), ctx)
        assert "POST_EVENT_LEAKAGE" in verdict.programmatic_check_status

    def test_causal_overclaim_detected(self, ctx, risk):
        synthesis = _clean_synthesis(
            ctx, risk,
            risk_explanation="厄尔尼诺导致的异常高温直接造成了本次冰崩灾害。")
        verdict = Critic(provider=None).run(
            synthesis, risk, _agents_all_completed(), ctx)
        assert "CAUSAL_OVERCLAIM" in verdict.programmatic_check_status
        assert verdict.review_result in (
            CriticReviewResult.NEEDS_REVISION.value,
            CriticReviewResult.BLOCKED.value)

    def test_caveated_enso_context_not_flagged(self, ctx, risk):
        synthesis = _clean_synthesis(
            ctx, risk,
            risk_explanation="ENSO 背景可能影响区域气候，但因果关系未证实，"
                             "仅作为背景信息。")
        verdict = Critic(provider=None).run(
            synthesis, risk, _agents_all_completed(), ctx)
        assert "CAUSAL_OVERCLAIM" not in verdict.programmatic_check_status

    def test_post_event_leakage_detected(self, ctx, risk):
        synthesis = _clean_synthesis(
            ctx, risk,
            summary="灾后影像显示河槽明显展宽、泥沙覆盖范围扩大、物质沿狭窄河谷输移。")
        verdict = Critic(provider=None).run(
            synthesis, risk, _agents_all_completed(), ctx)
        assert "POST_EVENT_LEAKAGE" in verdict.programmatic_check_status
        assert verdict.review_result == CriticReviewResult.BLOCKED.value

    def test_post_event_outcome_value_leakage_detected(self, ctx, risk):
        synthesis = _clean_synthesis(
            ctx, risk,
            risk_explanation="灾害运动距离为22公里，实际传播时间仅数分钟。")
        verdict = Critic(provider=None).run(
            synthesis, risk, _agents_all_completed(), ctx)
        assert "POST_EVENT_LEAKAGE" in verdict.programmatic_check_status

    def test_post_event_evidence_id_cited_blocks(self, ctx, risk):
        synthesis = _clean_synthesis(ctx, risk)
        synthesis.evidence_ids = list(synthesis.evidence_ids) + [
            "EV-SAT-POST-S2B_45RUM_20260827_0_L2A"]
        verdict = Critic(provider=None).run(
            synthesis, risk, _agents_all_completed(), ctx)
        assert "EVIDENCE_ID_INTEGRITY" in verdict.programmatic_check_status
        assert verdict.review_result == CriticReviewResult.BLOCKED.value

    def test_hallucinated_evidence_id_blocks(self, ctx, risk):
        synthesis = _clean_synthesis(ctx, risk)
        synthesis.evidence_ids = ["EV-HALLUCINATED-999"]
        verdict = Critic(provider=None).run(
            synthesis, risk, _agents_all_completed(), ctx)
        assert verdict.programmatic_check_status.get(
            "EVIDENCE_ID_INTEGRITY") == IssueSeverity.CRITICAL.value

    def test_missing_data_dishonesty_detected(self, ctx, risk):
        synthesis = _clean_synthesis(ctx, risk, missing_data=[])
        verdict = Critic(provider=None).run(
            synthesis, risk, _agents_all_completed(), ctx)
        assert "MISSING_DATA_HONESTY" in verdict.programmatic_check_status

    def test_missing_data_honesty_passes_when_disclosed(self, ctx, risk):
        synthesis = _clean_synthesis(
            ctx, risk,
            missing_data=["灾前实时源区动态监测数据（位移/微震）缺失"],
            limitations=["缺少灾前动态监测数据，无法判断具体发生时刻。"])
        verdict = Critic(provider=None).run(
            synthesis, risk, _agents_all_completed(), ctx)
        assert "MISSING_DATA_HONESTY" not in verdict.programmatic_check_status

    def test_hidden_disagreement_detected(self, ctx, risk):
        synthesis = _clean_synthesis(
            ctx, risk,
            agent_agreement=AgentAgreement.SIGNIFICANT_DISAGREEMENT.value,
            summary="各专业分析结论完全一致，风险很高。",
            risk_explanation="综合各 Agent 结论，风险条件明确。")
        verdict = Critic(provider=None).run(
            synthesis, risk, _agents_all_completed(), ctx)
        assert "AGENT_DISAGREEMENT" in verdict.programmatic_check_status

    def test_disclosed_disagreement_not_flagged(self, ctx, risk):
        synthesis = _clean_synthesis(
            ctx, risk,
            agent_agreement=AgentAgreement.SIGNIFICANT_DISAGREEMENT.value,
            summary="专业 Agent 之间存在显著分歧，需谨慎解读。",
            risk_explanation="冰川地质判断为高风险，气象水文判断为低风险，"
                             "分歧已如实说明。")
        verdict = Critic(provider=None).run(
            synthesis, risk, _agents_all_completed(), ctx)
        assert "AGENT_DISAGREEMENT" not in verdict.programmatic_check_status

    def test_satellite_overclaim_with_skipped_rs(self, ctx, risk):
        agents = _agents_all_completed()
        agents[AGENT_REMOTE_SENSING] = _make_agent_result(
            AGENT_REMOTE_SENSING, status=AgentStatus.SKIPPED, signal=None,
            findings=[], skip_reason=SKIP_NO_USABLE_IMAGERY)
        synthesis = _clean_synthesis(
            ctx, risk,
            summary="卫星影像确认源区已发生大规模破坏。")
        verdict = Critic(provider=None).run(synthesis, risk, agents, ctx)
        assert "SATELLITE_OVERCLAIM" in verdict.programmatic_check_status

    def test_satellite_overclaim_with_degraded_rs(self, ctx, risk):
        agents = _agents_all_completed()
        agents[AGENT_REMOTE_SENSING] = _make_agent_result(
            AGENT_REMOTE_SENSING, status=AgentStatus.DEGRADED,
            signal="DATA_LIMITED", fallback=True, is_model=False)
        synthesis = _clean_synthesis(
            ctx, risk, summary="遥感证实沟谷已出现明显变形破坏。")
        verdict = Critic(provider=None).run(synthesis, risk, agents, ctx)
        assert "SATELLITE_OVERCLAIM" in verdict.programmatic_check_status

    def test_ai_observation_never_upgraded_to_official(self, ctx, risk):
        agents = _agents_all_completed()
        agents[AGENT_REMOTE_SENSING] = _make_agent_result(
            AGENT_REMOTE_SENSING, status=AgentStatus.SKIPPED, signal=None,
            findings=[])
        synthesis = _clean_synthesis(
            ctx, risk, summary="官方确认影像解译结果显示源区失稳。")
        verdict = Critic(provider=None).run(synthesis, risk, agents, ctx)
        assert "SATELLITE_OVERCLAIM" in verdict.programmatic_check_status

    def test_evidence_support_missing_citations(self, ctx, risk):
        synthesis = _clean_synthesis(ctx, risk, evidence_ids=[])
        synthesis.evidence_ids = []
        verdict = Critic(provider=None).run(
            synthesis, risk, _agents_all_completed(), ctx)
        assert "EVIDENCE_SUPPORT" in verdict.programmatic_check_status

    def test_score_integrity_violation_blocks(self, ctx, risk):
        synthesis = _clean_synthesis(ctx, risk)
        synthesis.deterministic_risk_index = 50.0  # tampered downstream
        verdict = Critic(provider=None).run(
            synthesis, risk, _agents_all_completed(), ctx)
        assert verdict.programmatic_check_status.get(
            "SCORE_INTEGRITY") == IssueSeverity.CRITICAL.value
        assert verdict.review_result == CriticReviewResult.BLOCKED.value

    def test_narrative_restates_wrong_index(self, ctx, risk):
        synthesis = _clean_synthesis(
            ctx, risk,
            risk_explanation="综合判断风险指数为85，属于高风险。")
        verdict = Critic(provider=None).run(
            synthesis, risk, _agents_all_completed(), ctx)
        assert "SCORE_INTEGRITY" in verdict.programmatic_check_status

    def test_fallback_masquerade_blocks(self, ctx, risk):
        synthesis = _clean_synthesis(ctx, risk)
        synthesis.fallback_used = True
        synthesis.is_model_output = True   # masquerading
        verdict = Critic(provider=None).run(
            synthesis, risk, _agents_all_completed(), ctx)
        assert verdict.programmatic_check_status.get(
            "FALLBACK_LABELING") == IssueSeverity.CRITICAL.value
        assert verdict.review_result == CriticReviewResult.BLOCKED.value

    def test_undisclosed_fallback_flagged(self, ctx, risk):
        synthesis = _clean_synthesis(ctx, risk, limitations=["普通限制说明"])
        synthesis.fallback_used = True
        synthesis.is_model_output = False
        verdict = Critic(provider=None).run(
            synthesis, risk, _agents_all_completed(), ctx)
        assert "FALLBACK_LABELING" in verdict.programmatic_check_status

    def test_critic_never_changes_risk_index(self, ctx, risk):
        before = risk.risk_index
        synthesis = _clean_synthesis(ctx, risk)
        Critic(provider=None).run(
            synthesis, risk, _agents_all_completed(), ctx)
        assert risk.risk_index == before == 91.0
        with pytest.raises(dataclasses.FrozenInstanceError):
            risk.risk_index = 10.0


class TestCriticModelReview:
    def test_critic_model_failure_falls_back_to_programmatic(self, ctx, risk):
        provider = _full_provider(ctx, risk, fail_kinds={"critic"})
        synthesis = _clean_synthesis(ctx, risk)
        verdict = Critic(provider=provider).run(
            synthesis, risk, _agents_all_completed(), ctx)
        assert verdict.fallback_used is True
        assert verdict.is_model_output is False
        assert verdict.review_result in {r.value for r in CriticReviewResult}
        assert any("程序化检查" in l
                   for l in verdict.scientific_limitations)
        critic_calls = [c for c in provider.calls if c["kind"] == "critic"]
        assert len(critic_calls) == 1, "bounded — no retry storm"

    def test_model_review_merges_and_cannot_loosen(self, ctx, risk):
        """Programmatic BLOCKED stays BLOCKED even if the model says PASS;
        a stricter model verdict upgrades a lenient programmatic one."""
        # programmatic clean, model stricter → stricter wins
        provider = _full_provider(
            ctx, risk,
            critic_response=_critic_response(
                result=CriticReviewResult.NEEDS_REVISION.value))
        synthesis = _clean_synthesis(ctx, risk)
        verdict = Critic(provider=provider).run(
            synthesis, risk, _agents_all_completed(), ctx)
        assert verdict.review_result == \
            CriticReviewResult.NEEDS_REVISION.value
        assert verdict.is_model_output is True
        assert any(i.origin == "model_review" for i in verdict.issues)

        # programmatic BLOCKED, model PASS → BLOCKED survives
        provider2 = _full_provider(
            ctx, risk, critic_response=_critic_response(
                result=CriticReviewResult.PASS.value))
        bad = _clean_synthesis(ctx, risk)
        bad.deterministic_risk_index = 12.0
        verdict2 = Critic(provider=provider2).run(
            bad, risk, _agents_all_completed(), ctx)
        assert verdict2.review_result == CriticReviewResult.BLOCKED.value

    def test_critic_prompt_contains_no_post_event_data(self, ctx, risk):
        provider = _full_provider(ctx, risk)
        synthesis = _clean_synthesis(ctx, risk)
        Critic(provider=provider).run(
            synthesis, risk, _agents_all_completed(), ctx)
        case, values, ids = _post_event_markers()
        for call in provider.calls:
            if call["kind"] != "critic":
                continue
            text = call["system_prompt"] + call["user_prompt"]
            for marker in ids:
                assert marker not in text
            for value in values:
                assert value not in text


# ═══════════════════════════════════════════════════════════════════════════════
# 23/24/25/26 — Stage-A freeze & Stage-B immutability
# ═══════════════════════════════════════════════════════════════════════════════
class TestStageFreeze:
    def test_stage_a_freeze_contents(self, ctx):
        freeze = run_stage_a(provider=None, run_id="freeze-test")
        assert isinstance(freeze, StageAFreeze)
        assert freeze.verify_integrity()
        assert freeze.risk_index == 91.0
        assert freeze.risk_level == "HIGH"
        payload = freeze.to_dict()
        for key in ("run_id", "risk_engine", "risk_index", "agent_results",
                    "synthesis", "critic", "stage_a_evidence_ids",
                    "provider_metadata", "fallback_state"):
            assert key in payload
        assert payload["synthesis"]["audit"]["timestamp"]
        assert payload["critic"]["verdict"]["risk_index_before"] == 91.0

    def test_freeze_is_immutable(self):
        freeze = run_stage_a(provider=None, run_id="immutable-test")
        with pytest.raises(dataclasses.FrozenInstanceError):
            freeze.risk_index = 50.0
        with pytest.raises(dataclasses.FrozenInstanceError):
            freeze.payload_json = "{}"
        with pytest.raises(dataclasses.FrozenInstanceError):
            freeze.content_digest = "0" * 64

    def test_to_dict_returns_copy_not_reference(self):
        freeze = run_stage_a(provider=None, run_id="copy-test")
        d = freeze.to_dict()
        d["risk_index"] = 1.0
        d["synthesis"]["output"]["summary"] = "tampered"
        assert freeze.to_dict()["risk_index"] == 91.0
        assert "tampered" not in json.dumps(freeze.to_dict(),
                                            ensure_ascii=False)
        assert freeze.verify_integrity()

    def test_stage_b_requires_freeze(self):
        with pytest.raises(FrozenStateError):
            run_stage_b({"risk_index": 91.0})  # not a StageAFreeze

    def test_stage_b_cannot_alter_stage_a_or_index(self):
        replay = run_historical_replay(provider=None, run_id="stageb-test")
        b = replay.stage_b
        assert b.stage_a_unchanged is True
        assert b.stage_a_digest_before == b.stage_a_digest_after
        assert b.risk_index_before == 91.0
        assert b.risk_index_after == 91.0
        assert replay.stage_a.verify_integrity()
        # aggressive mutation attempts on the frozen record
        with pytest.raises(dataclasses.FrozenInstanceError):
            replay.stage_a.risk_index = 0.0
        assert replay.stage_a.risk_index == 91.0

    def test_stage_b_validation_content(self):
        replay = run_historical_replay(provider=None, run_id="stageb-content")
        b = replay.stage_b
        assert b.directional_findings, "directional correspondence produced"
        unknown = " ".join(b.stage_a_could_not_know)
        for expected in ("灾害传播时间", "灾害运动距离", "平均运动速度",
                         "灾害影响面积", "受损建筑数量"):
            assert expected in unknown, \
                f"Stage B must document that Stage A could not know: {expected}"
        assert any("EV-SAT-POST" in i for i in b.post_event_evidence_ids)
        assert "未修改" in b.statement

    def test_stage_b_makes_no_provider_calls(self, ctx, risk):
        provider = _full_provider(ctx, risk)
        freeze = run_stage_a(provider=provider, run_id="nocalls-test")
        calls_before = len(provider.calls)
        run_stage_b(freeze)
        assert len(provider.calls) == calls_before, \
            "Stage B is deterministic — zero provider calls (#26)"

    def test_stage_b_evidence_never_in_stage_a_prompts(self, ctx, risk):
        provider = _full_provider(ctx, risk)
        run_stage_a(provider=provider, run_id="prompt-leak-test")
        case, values, ids = _post_event_markers()
        assert provider.calls, "expected scripted calls"
        for call in provider.calls:
            text = call["system_prompt"] + call["user_prompt"]
            for marker in ids:
                assert marker not in text, \
                    f"post-event marker {marker} in {call['kind']} prompt"
            for value in values:
                assert value not in text, \
                    f"post-event value {value!r} in {call['kind']} prompt"
            assert "post_event_validation" not in text


# ═══════════════════════════════════════════════════════════════════════════════
# 27 — full Historical Replay mock workflow (real agents, scripted provider)
# ═══════════════════════════════════════════════════════════════════════════════
class TestFullReplayMock:
    def test_full_mock_workflow(self, ctx, risk):
        provider = _full_provider(ctx, risk)
        replay = run_historical_replay(provider=provider,
                                       run_id="full-mock-replay")
        payload = replay.stage_a.to_dict()
        # three professional agents ran through the scripted provider
        assert payload["agent_status_summary"][AGENT_GLACIER_GEOLOGY] == \
            "COMPLETED"
        assert payload["agent_status_summary"][AGENT_WEATHER_HYDROLOGY] == \
            "COMPLETED"
        rs_status = payload["agent_status_summary"][AGENT_REMOTE_SENSING]
        assert rs_status in ("COMPLETED", "SKIPPED")
        # synthesis + critic were real structured model outputs
        assert payload["synthesis"]["output"]["is_model_output"] is True
        assert payload["synthesis"]["output"]["fallback_used"] is False
        assert payload["critic"]["verdict"]["is_model_output"] is True
        # score integrity through the whole DAG
        assert replay.risk_index == 91.0
        assert replay.stage_b.risk_index_after == 91.0
        assert replay.stage_a.verify_integrity()
        assert replay.critic_review_result in {
            r.value for r in CriticReviewResult}
        assert replay.critic_review_result != \
            CriticReviewResult.BLOCKED.value, json.dumps(
                payload["critic"]["verdict"]["issues"], ensure_ascii=False)

    def test_full_mock_workflow_all_fallback(self):
        """Even with no provider at all, the DAG completes with explicit
        fallback labeling and the frozen score."""
        replay = run_historical_replay(provider=None,
                                       run_id="full-fallback-replay")
        payload = replay.stage_a.to_dict()
        assert payload["synthesis"]["output"]["fallback_used"] is True
        assert payload["synthesis"]["output"]["is_model_output"] is False
        assert replay.risk_index == 91.0
        assert replay.stage_b.stage_a_unchanged is True

    def test_replay_agent_crash_isolated_end_to_end(self, ctx, risk):
        provider = _full_provider(ctx, risk,
                                  fail_kinds={"agent:weather_hydrology"})
        replay = run_historical_replay(provider=provider,
                                       run_id="crash-isolated")
        payload = replay.stage_a.to_dict()
        assert payload["agent_status_summary"][AGENT_WEATHER_HYDROLOGY] == \
            "DEGRADED"  # fallback path, isolated
        assert payload["agent_status_summary"][AGENT_GLACIER_GEOLOGY] == \
            "COMPLETED"
        assert replay.risk_index == 91.0
        assert replay.stage_a.verify_integrity()
