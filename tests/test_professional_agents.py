"""
MountainGuardian G02A – professional agent tests (Layer 1/2, mock only).

Covers (Gate spec §12):
   3 minimum-context behavior         12 missing-data representation
   4 glacier/geology structured out   13 agent failure isolation
   5 weather/hydrology structured out 14 provider failure → fallback
   6 remote sensing structured out    15 malformed model JSON
   7 evidence ID validation           16 schema validation
   8 unknown evidence ID rejection    17 RS no-image → SKIPPED
   9 post-event evidence blocked      18 RS cannot substitute post-event
  10 phase filtering                  19 no paid model call in pytest
  11 confidence validation

All tests use MockProvider (or no provider). A module-wide network guard
fails any test that attempts real socket access — ordinary pytest can never
reach a paid model (Engineering Spec §26/§27).
"""

import copy
import json
import socket
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.glacier_geology_agent import GlacierGeologyAgent
from agents.professional_base import run_professional_agents
from agents.remote_sensing_agent import (
    SKIP_NO_USABLE_IMAGERY,
    RemoteSensingAgent,
)
from agents.weather_hydrology_agent import WeatherHydrologyAgent
from orchestration.context_builder import (
    AnalysisContext,
    PhaseSafetyError,
    agent_evidence_view,
    build_analysis_context,
)
from providers.base_provider import (
    ModelProvider,
    ModelResult,
    ProviderErrorCategory,
    ProviderHealth,
    ProviderStatus,
    validate_json_schema,
)
from schemas.agent_outputs import AgentStatus, RiskSignal
from schemas.evidence import (
    AGENT_GLACIER_GEOLOGY,
    AGENT_REMOTE_SENSING,
    AGENT_WEATHER_HYDROLOGY,
    EvidenceItem,
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


# ─── MockProvider: mirrors the DeepSeekProvider validation contract ──────────
class MockProvider(ModelProvider):
    """In-memory provider that applies the SAME pipeline semantics as the
    real provider: schema validation → output_validator → success, or
    failure with deterministic fallback (post-repair-failure semantics)."""

    provider_name = "mock"
    model_id = "mock-flash"

    def __init__(self, response=None, raw_response=None,
                 fail_category=None, fail_message="mock provider failure",
                 raise_on_substring=None, success_status=None):
        self.response = response
        self.raw_response = raw_response
        self.fail_category = fail_category
        self.fail_message = fail_message
        self.raise_on_substring = raise_on_substring
        self.success_status = success_status or ProviderStatus.CONNECTED
        self.calls = []

    def _record(self, request, images):
        self.calls.append({
            "request": request,
            "system_prompt": request.system_prompt,
            "user_prompt": request.user_prompt,
            "images": list(images) if images else None,
            "run_id": request.run_id,
        })
        if self.raise_on_substring and \
                self.raise_on_substring in request.system_prompt:
            raise RuntimeError("simulated catastrophic agent-side failure")

    def _failure(self, request, category, message):
        has_fb = request.fallback_data is not None
        return ModelResult(
            success=False,
            data=request.fallback_data if has_fb else None,
            status=(ProviderStatus.FALLBACK_ACTIVE if has_fb
                    else ProviderStatus.OFFLINE),
            fallback_used=has_fb,
            error_category=category,
            error_message=message,
            provider=self.provider_name, model_id=self.model_id,
            request_id=request.request_id, run_id=request.run_id,
            latency_ms=1)

    def _handle(self, request, images):
        self._record(request, images)
        if self.fail_category is not None:
            return self._failure(request, self.fail_category,
                                 self.fail_message)
        data = self.response
        if data is None:
            category = ProviderErrorCategory.INVALID_RESPONSE
            try:
                data = json.loads(self.raw_response or "")
            except (json.JSONDecodeError, ValueError):
                return self._failure(request, category,
                                     "output is not valid JSON")
        category = ProviderErrorCategory.SCHEMA_ERROR
        errors = validate_json_schema(data, request.schema)
        if not errors and request.output_validator is not None:
            errors = request.output_validator(data) or []
        if errors:
            return self._failure(request, category, "; ".join(errors[:5]))
        return ModelResult(
            success=True, data=copy.deepcopy(data),
            status=self.success_status, fallback_used=False,
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


# ─── fixtures ─────────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def ctx():
    return build_analysis_context()


def _valid_response(agent_name, allowed_ids, extra=None, **overrides):
    base = {
        AGENT_GLACIER_GEOLOGY: {"risk_drivers": ["高位冰岩源区", "松散物源"]},
        AGENT_WEATHER_HYDROLOGY: {"recent_conditions": ["雨季背景"],
                                  "forecast_signals": []},
        AGENT_REMOTE_SENSING: {"image_ids": [], "observations": ["基线河谷形态"],
                               "quality_notes": ["真彩色目视"]},
    }[agent_name]
    data = {
        "agent": agent_name,
        "status": "COMPLETED",
        "risk_signal": "ELEVATED",
        "confidence": 0.8,
        "key_findings": ["mock 专业判断一", "mock 专业判断二"],
        "evidence_ids": sorted(allowed_ids)[:3],
        "missing_data": ["灾前动态监测数据缺失"],
        "limitations": ["历史回放，非实时预警"],
        **base,
        **(extra or {}),
    }
    data.update(overrides)
    return data


def _allowed_ids(ctx, agent_name):
    return set(agent_evidence_view(ctx, agent_name).allowed_evidence_ids())


AGENT_CLASSES = {
    AGENT_GLACIER_GEOLOGY: GlacierGeologyAgent,
    AGENT_WEATHER_HYDROLOGY: WeatherHydrologyAgent,
    AGENT_REMOTE_SENSING: RemoteSensingAgent,
}


def _run_agent(ctx, agent_name, provider):
    return AGENT_CLASSES[agent_name](provider=provider).run(ctx)


# ═══════════════════════════════════════════════════════════════════════════════
# 4/5/6 — structured outputs for all three agents
# ═══════════════════════════════════════════════════════════════════════════════
class TestStructuredOutputs:
    @pytest.mark.parametrize("agent_name", list(AGENT_CLASSES))
    def test_completed_structured_output(self, ctx, agent_name):
        provider = MockProvider(
            response=_valid_response(agent_name, _allowed_ids(ctx, agent_name)))
        result = _run_agent(ctx, agent_name, provider)

        assert result.status == AgentStatus.COMPLETED
        assert result.is_model_output is True
        assert result.fallback_used is False
        assert result.agent_name == agent_name
        assert result.risk_signal in {s.value for s in RiskSignal}
        assert 0.0 <= result.confidence <= 1.0
        assert result.key_findings and isinstance(result.key_findings, list)
        assert result.evidence_ids
        assert isinstance(result.missing_data, list)
        assert isinstance(result.limitations, list)
        # provider/model status + audit metadata exposed
        assert result.provider_status == ProviderStatus.CONNECTED.value
        assert result.provider == "mock"
        assert result.model_id == "mock-flash"
        assert result.run_id == ctx.run_id
        assert result.request_id
        assert result.prompt_id == f"{agent_name}_v1"
        assert result.prompt_version == "v1"
        assert result.schema_version == "v1"
        assert result.token_usage.get("total_tokens") == 150
        assert len(provider.calls) == 1, "exactly one bounded provider call"

    @pytest.mark.parametrize("agent_name", list(AGENT_CLASSES))
    def test_agent_specific_fields_present(self, ctx, agent_name):
        provider = MockProvider(
            response=_valid_response(agent_name, _allowed_ids(ctx, agent_name)))
        result = _run_agent(ctx, agent_name, provider)
        d = result.to_dict()
        if agent_name == AGENT_GLACIER_GEOLOGY:
            assert d["risk_drivers"]
        elif agent_name == AGENT_WEATHER_HYDROLOGY:
            assert "recent_conditions" in d and "forecast_signals" in d
        else:
            assert "observations" in d and "quality_notes" in d

    @pytest.mark.parametrize("agent_name", list(AGENT_CLASSES))
    def test_audit_dict_complete_and_serializable(self, ctx, agent_name):
        provider = MockProvider(
            response=_valid_response(agent_name, _allowed_ids(ctx, agent_name)))
        result = _run_agent(ctx, agent_name, provider)
        audit = result.to_audit_dict()
        json.dumps(audit, default=str)  # must serialize
        for key in ("run_id", "agent_id", "model_id", "status",
                    "input_evidence_ids", "schema_version", "fallback_used",
                    "latency_ms", "timestamp", "prompt_id", "prompt_version"):
            assert key in audit
        assert audit["input_evidence_ids"], "audit must record input evidence"

    def test_confidence_is_not_probability_in_prompts(self, ctx):
        provider = MockProvider(response=_valid_response(
            AGENT_GLACIER_GEOLOGY, _allowed_ids(ctx, AGENT_GLACIER_GEOLOGY)))
        _run_agent(ctx, AGENT_GLACIER_GEOLOGY, provider)
        system_prompt = provider.calls[0]["system_prompt"]
        assert "不是灾害发生概率" in system_prompt
        assert "禁止" in system_prompt and "不得给出灾害发生概率" in system_prompt

    def test_provider_degraded_success_is_completed_with_degraded_status(
            self, ctx):
        """Real validated model output after a bounded repair/retry: agent
        status COMPLETED, provider impairment surfaced via provider_status
        (doc 03 §21/§23/§28)."""
        provider = MockProvider(
            response=_valid_response(
                AGENT_GLACIER_GEOLOGY,
                _allowed_ids(ctx, AGENT_GLACIER_GEOLOGY)),
            success_status=ProviderStatus.DEGRADED)
        result = _run_agent(ctx, AGENT_GLACIER_GEOLOGY, provider)
        assert result.status == AgentStatus.COMPLETED
        assert result.is_model_output is True
        assert result.fallback_used is False
        assert result.provider_status == ProviderStatus.DEGRADED.value


# ═══════════════════════════════════════════════════════════════════════════════
# 3/10 — minimum context & phase filtering in what reaches the prompt
# ═══════════════════════════════════════════════════════════════════════════════
class TestMinimumContextAndPhaseFiltering:
    def test_prompt_contains_only_authorized_evidence_ids(self, ctx):
        for agent_name in AGENT_CLASSES:
            provider = MockProvider(response=_valid_response(
                agent_name, _allowed_ids(ctx, agent_name)))
            _run_agent(ctx, agent_name, provider)
            prompt = provider.calls[0]["user_prompt"]
            authorized = _allowed_ids(ctx, agent_name)
            # every C-id token appearing in the prompt must be authorized
            import re
            cited = set(re.findall(r"\bC0\d\d\b", prompt))
            assert cited <= authorized, \
                f"{agent_name} prompt cites unauthorized ids: " \
                f"{cited - authorized}"

    def test_weather_prompt_excludes_glacier_evidence(self, ctx):
        provider = MockProvider(response=_valid_response(
            AGENT_WEATHER_HYDROLOGY, _allowed_ids(ctx, AGENT_WEATHER_HYDROLOGY)))
        _run_agent(ctx, AGENT_WEATHER_HYDROLOGY, provider)
        prompt = provider.calls[0]["user_prompt"]
        glacier_view = agent_evidence_view(ctx, AGENT_GLACIER_GEOLOGY)
        glacier_only = [i for i in glacier_view.evidence
                        if AGENT_WEATHER_HYDROLOGY not in i.allowed_agents]
        assert glacier_only
        for item in glacier_only:
            assert f"[{item.evidence_id}]" not in prompt

    def test_no_post_event_content_in_any_prompt(self, ctx):
        from tools.case_loader import load_case
        case = load_case()
        post_fields = [f for f in case["raw"]["data_fields"]
                       if f["phase"] == "post_event_validation"]
        assert post_fields
        # Unambiguous post-event RESULT measurements (the leakage red line,
        # doc 02 §5.1). Short chain-description words are skipped because
        # the public case NAME (metadata, allowed in prompts) legitimately
        # contains the official disaster-chain phrasing.
        measurement_keys = {
            "source_area", "actual_runout_km", "actual_travel_time_min",
            "actual_avg_speed_mps", "actual_affected_area_km2",
            "actual_structures_destroyed", "satellite_post_datetime",
            "satellite_post_cloud_pct", "satellite_visible_change",
            "official_satellite_scene_count",
            "source_fracture_time_later_report",
        }
        for agent_name in AGENT_CLASSES:
            provider = MockProvider(response=_valid_response(
                agent_name, _allowed_ids(ctx, agent_name)))
            _run_agent(ctx, agent_name, provider)
            call = provider.calls[0]
            full = call["system_prompt"] + call["user_prompt"]
            assert "post_event_validation" not in full
            for f in post_fields:
                assert f"[{f['id']}]" not in full
                if f["key"] in measurement_keys:
                    value = str(f.get("value", ""))
                    if len(value) >= 4:
                        assert value not in full, \
                            f"post-event measurement {f['id']} leaked into " \
                            f"{agent_name} prompt"

    def test_enso_background_flagged_non_causal_in_weather_prompt(self, ctx):
        provider = MockProvider(response=_valid_response(
            AGENT_WEATHER_HYDROLOGY, _allowed_ids(ctx, AGENT_WEATHER_HYDROLOGY)))
        _run_agent(ctx, AGENT_WEATHER_HYDROLOGY, provider)
        prompt = provider.calls[0]["user_prompt"]
        assert "context_only" in prompt
        assert "禁止作为直接因果" in prompt

    def test_constraints_repeated_in_prompt_second_line(self, ctx):
        provider = MockProvider(response=_valid_response(
            AGENT_GLACIER_GEOLOGY, _allowed_ids(ctx, AGENT_GLACIER_GEOLOGY)))
        _run_agent(ctx, AGENT_GLACIER_GEOLOGY, provider)
        system_prompt = provider.calls[0]["system_prompt"]
        for section in ("【角色】", "【任务】", "【禁止】", "【科学约束】",
                        "【证据要求】", "【输出】"):
            assert section in system_prompt

    def test_evidence_wrapped_as_untrusted_data(self, ctx):
        provider = MockProvider(response=_valid_response(
            AGENT_GLACIER_GEOLOGY, _allowed_ids(ctx, AGENT_GLACIER_GEOLOGY)))
        _run_agent(ctx, AGENT_GLACIER_GEOLOGY, provider)
        prompt = provider.calls[0]["user_prompt"]
        assert "[EVIDENCE_DATA_START" in prompt and "[EVIDENCE_DATA_END]" in prompt


# ═══════════════════════════════════════════════════════════════════════════════
# 9 — post-event evidence blocked BEFORE provider invocation
# ═══════════════════════════════════════════════════════════════════════════════
class TestPostEventBlocking:
    def _tampered_ctx(self, ctx):
        trojan = EvidenceItem(
            evidence_id="C028", evidence_type="terrain",
            phase="post_event_validation", summary="灾后验证字段（篡改注入）",
            value="TAMPERED", allowed_agents=tuple(AGENT_CLASSES))
        return AnalysisContext(
            run_id=ctx.run_id, mode=ctx.mode, region_id=ctx.region_id,
            analysis_time=ctx.analysis_time,
            case_metadata=ctx.case_metadata,
            allowed_evidence=list(ctx.allowed_evidence) + [trojan],
            context_only_evidence=list(ctx.context_only_evidence),
            missing_sources=list(ctx.missing_sources),
            scientific_constraints=list(ctx.scientific_constraints),
            pre_event_imagery=list(ctx.pre_event_imagery))

    @pytest.mark.parametrize("agent_name", list(AGENT_CLASSES))
    def test_blocked_before_provider_invocation(self, ctx, agent_name):
        trojan_ctx = self._tampered_ctx(ctx)
        provider = MockProvider(response=_valid_response(
            agent_name, _allowed_ids(ctx, agent_name)))
        result = _run_agent(trojan_ctx, agent_name, provider)

        assert result.status == AgentStatus.FAILED
        assert "post-event" in (result.error_message or ""), \
            "failure must be identified as a phase-safety block"
        assert provider.calls == [], \
            "provider must NEVER be invoked when post-event evidence present"
        assert result.is_model_output is False

    def test_context_view_builder_raises_first(self, ctx):
        with pytest.raises(PhaseSafetyError):
            agent_evidence_view(self._tampered_ctx(ctx),
                                AGENT_GLACIER_GEOLOGY)


# ═══════════════════════════════════════════════════════════════════════════════
# 7/8/11/15/16 — evidence ID, confidence, JSON, schema validation
# ═══════════════════════════════════════════════════════════════════════════════
class TestOutputValidation:
    def test_authorized_evidence_ids_accepted(self, ctx):
        allowed = _allowed_ids(ctx, AGENT_GLACIER_GEOLOGY)
        provider = MockProvider(response=_valid_response(
            AGENT_GLACIER_GEOLOGY, allowed))
        result = _run_agent(ctx, AGENT_GLACIER_GEOLOGY, provider)
        assert result.status == AgentStatus.COMPLETED
        assert set(result.evidence_ids) <= allowed

    def test_unknown_evidence_id_rejected_to_fallback(self, ctx):
        provider = MockProvider(response=_valid_response(
            AGENT_GLACIER_GEOLOGY, _allowed_ids(ctx, AGENT_GLACIER_GEOLOGY),
            evidence_ids=["C010", "EV-HALLUCINATED-999"]))
        result = _run_agent(ctx, AGENT_GLACIER_GEOLOGY, provider)
        assert result.status == AgentStatus.DEGRADED
        assert result.fallback_used is True
        assert result.is_model_output is False
        assert "EV-HALLUCINATED-999" not in result.evidence_ids
        assert "unknown or unauthorized evidence ids" in \
            (result.error_message or "")

    def test_post_event_id_citation_rejected(self, ctx):
        provider = MockProvider(response=_valid_response(
            AGENT_GLACIER_GEOLOGY, _allowed_ids(ctx, AGENT_GLACIER_GEOLOGY),
            evidence_ids=["C028"]))  # post-event field id
        result = _run_agent(ctx, AGENT_GLACIER_GEOLOGY, provider)
        assert result.fallback_used is True
        assert "C028" not in result.evidence_ids

    @pytest.mark.parametrize("bad_confidence", [1.7, -0.2, "high", None, True])
    def test_invalid_confidence_rejected(self, ctx, bad_confidence):
        provider = MockProvider(response=_valid_response(
            AGENT_GLACIER_GEOLOGY, _allowed_ids(ctx, AGENT_GLACIER_GEOLOGY),
            confidence=bad_confidence))
        result = _run_agent(ctx, AGENT_GLACIER_GEOLOGY, provider)
        assert result.status == AgentStatus.DEGRADED
        assert result.fallback_used is True
        assert 0.0 <= result.confidence <= 1.0

    def test_confidence_boundaries_accepted(self, ctx):
        for conf in (0.0, 1.0, 0.86):
            provider = MockProvider(response=_valid_response(
                AGENT_GLACIER_GEOLOGY,
                _allowed_ids(ctx, AGENT_GLACIER_GEOLOGY), confidence=conf))
            result = _run_agent(ctx, AGENT_GLACIER_GEOLOGY, provider)
            assert result.status == AgentStatus.COMPLETED
            assert result.confidence == pytest.approx(conf)

    def test_malformed_json_falls_back(self, ctx):
        provider = MockProvider(raw_response="this is { not valid json !!")
        result = _run_agent(ctx, AGENT_GLACIER_GEOLOGY, provider)
        assert result.status == AgentStatus.DEGRADED
        assert result.fallback_used is True
        assert result.is_model_output is False
        assert result.error_category == \
            ProviderErrorCategory.INVALID_RESPONSE.value

    def test_schema_violation_falls_back(self, ctx):
        broken = _valid_response(
            AGENT_GLACIER_GEOLOGY, _allowed_ids(ctx, AGENT_GLACIER_GEOLOGY))
        del broken["limitations"]          # required field missing
        broken["risk_drivers"] = "not-a-list"
        provider = MockProvider(response=broken)
        result = _run_agent(ctx, AGENT_GLACIER_GEOLOGY, provider)
        assert result.status == AgentStatus.DEGRADED
        assert result.fallback_used is True
        assert result.error_category == ProviderErrorCategory.SCHEMA_ERROR.value

    def test_wrong_agent_identity_rejected(self, ctx):
        provider = MockProvider(response=_valid_response(
            AGENT_WEATHER_HYDROLOGY,
            _allowed_ids(ctx, AGENT_GLACIER_GEOLOGY)))
        result = _run_agent(ctx, AGENT_GLACIER_GEOLOGY, provider)
        assert result.fallback_used is True

    def test_empty_findings_rejected(self, ctx):
        provider = MockProvider(response=_valid_response(
            AGENT_GLACIER_GEOLOGY, _allowed_ids(ctx, AGENT_GLACIER_GEOLOGY),
            key_findings=[]))
        result = _run_agent(ctx, AGENT_GLACIER_GEOLOGY, provider)
        assert result.fallback_used is True


# ═══════════════════════════════════════════════════════════════════════════════
# 12 — missing-data representation
# ═══════════════════════════════════════════════════════════════════════════════
class TestMissingData:
    def test_missing_gap_visible_in_prompt(self, ctx):
        provider = MockProvider(response=_valid_response(
            AGENT_GLACIER_GEOLOGY, _allowed_ids(ctx, AGENT_GLACIER_GEOLOGY)))
        _run_agent(ctx, AGENT_GLACIER_GEOLOGY, provider)
        assert "已知数据缺口" in provider.calls[0]["user_prompt"]

    def test_fallback_declares_missing_data(self, ctx):
        provider = MockProvider(fail_category=
                                ProviderErrorCategory.SERVICE_UNAVAILABLE)
        for agent_name in AGENT_CLASSES:
            result = _run_agent(ctx, agent_name, provider)
            assert result.missing_data, \
                f"{agent_name} fallback must declare missing data"

    def test_weather_fallback_declares_data_limited(self, ctx):
        provider = MockProvider(fail_category=
                                ProviderErrorCategory.SERVICE_UNAVAILABLE)
        result = _run_agent(ctx, AGENT_WEATHER_HYDROLOGY, provider)
        assert any("Data Limited" in m or "水文" in m
                   for m in result.missing_data)


# ═══════════════════════════════════════════════════════════════════════════════
# 13/14 — failure isolation & provider fallback
# ═══════════════════════════════════════════════════════════════════════════════
class TestFailureHandling:
    def test_provider_failure_activates_explicit_fallback(self, ctx):
        provider = MockProvider(
            fail_category=ProviderErrorCategory.TIMEOUT,
            fail_message="simulated timeout")
        for agent_name in AGENT_CLASSES:
            result = _run_agent(ctx, agent_name, provider)
            assert result.status == AgentStatus.DEGRADED
            assert result.fallback_used is True
            assert result.is_model_output is False, \
                "fallback must never masquerade as model output"
            assert result.provider_status == \
                ProviderStatus.FALLBACK_ACTIVE.value
            assert result.error_category == \
                ProviderErrorCategory.TIMEOUT.value
            assert result.key_findings, "deterministic fallback still useful"
            assert any("规则回退" in f for f in result.key_findings)
            assert any("确定性规则回退" in lim
                       for lim in result.limitations)

    def test_no_provider_degrades_safely(self, ctx):
        results = run_professional_agents(ctx, provider=None)
        assert len(results) == 3
        for result in results.values():
            assert result.status == AgentStatus.DEGRADED
            assert result.fallback_used is True
            assert result.provider_status == ProviderStatus.OFFLINE.value
            assert result.error_category == "NO_PROVIDER"

    def test_agent_failure_isolation(self, ctx):
        """One agent crashing catastrophically must not affect the others."""
        results = {}
        for agent_name in AGENT_CLASSES:
            if agent_name == AGENT_WEATHER_HYDROLOGY:
                # raises RuntimeError from inside the provider call
                p = MockProvider(raise_on_substring="气象与水文")
            else:
                p = MockProvider(response=_valid_response(
                    agent_name, _allowed_ids(ctx, agent_name)))
            results[agent_name] = _run_agent(ctx, agent_name, p)

        assert results[AGENT_WEATHER_HYDROLOGY].status == AgentStatus.FAILED
        assert results[AGENT_WEATHER_HYDROLOGY].is_model_output is False
        assert results[AGENT_GLACIER_GEOLOGY].status == AgentStatus.COMPLETED
        assert results[AGENT_REMOTE_SENSING].status == AgentStatus.COMPLETED

    def test_run_professional_agents_isolates_crash(self, ctx):
        class CrashProvider(MockProvider):
            def generate_structured(self, request):
                raise MemoryError("simulated unrecoverable crash")

            def generate_multimodal(self, request, images=None):
                raise MemoryError("simulated unrecoverable crash")

        results = run_professional_agents(ctx, CrashProvider())
        assert len(results) == 3
        assert all(r.status in (AgentStatus.FAILED, AgentStatus.DEGRADED)
                   for r in results.values())


# ═══════════════════════════════════════════════════════════════════════════════
# 6/17/18 — Remote Sensing specifics
# ═══════════════════════════════════════════════════════════════════════════════
class TestRemoteSensing:
    def test_uses_local_pre_event_image_only(self, ctx):
        provider = MockProvider(response=_valid_response(
            AGENT_REMOTE_SENSING, _allowed_ids(ctx, AGENT_REMOTE_SENSING),
            extra={"image_ids": [
                i for i in _allowed_ids(ctx, AGENT_REMOTE_SENSING)
                if i.startswith("EV-SAT-PRE")][:1]}))
        result = _run_agent(ctx, AGENT_REMOTE_SENSING, provider)
        assert result.status == AgentStatus.COMPLETED
        images = provider.calls[0]["images"]
        assert images and len(images) == 1
        assert "pre" in Path(images[0]).name.lower()
        assert all("post" not in Path(p).name.lower() for p in images)
        # AI observations must be labeled as non-official
        assert any("AI 目视观察" in lim for lim in result.limitations)

    def test_no_usable_image_returns_skipped(self, ctx):
        empty_ctx = AnalysisContext(
            run_id=ctx.run_id, mode=ctx.mode, region_id=ctx.region_id,
            analysis_time=ctx.analysis_time,
            case_metadata=ctx.case_metadata,
            allowed_evidence=list(ctx.allowed_evidence),
            context_only_evidence=list(ctx.context_only_evidence),
            missing_sources=list(ctx.missing_sources),
            scientific_constraints=list(ctx.scientific_constraints),
            pre_event_imagery=[])
        provider = MockProvider(response=_valid_response(
            AGENT_REMOTE_SENSING, _allowed_ids(ctx, AGENT_REMOTE_SENSING)))
        result = _run_agent(empty_ctx, AGENT_REMOTE_SENSING, provider)
        assert result.status == AgentStatus.SKIPPED
        assert result.skip_reason == SKIP_NO_USABLE_IMAGERY
        assert result.is_model_output is False
        assert result.confidence == 0.0
        assert provider.calls == [], "SKIPPED must not invoke the provider"

    def test_post_event_image_cannot_be_substituted(self, ctx):
        """A post-event scene smuggled into the imagery bucket must never
        reach the provider and must never be analyzed as a pre-event
        baseline — the agent SKIPS instead of substituting (doc 03 §12.1)."""
        from tools.case_loader import load_case
        case = load_case()
        post_scene = None
        from schemas.evidence import build_evidence_pool
        for item in build_evidence_pool(case):
            if item.evidence_id.startswith("EV-SAT-POST"):
                post_scene = item
        assert post_scene is not None
        tampered = AnalysisContext(
            run_id=ctx.run_id, mode=ctx.mode, region_id=ctx.region_id,
            analysis_time=ctx.analysis_time,
            case_metadata=ctx.case_metadata,
            allowed_evidence=list(ctx.allowed_evidence),
            context_only_evidence=list(ctx.context_only_evidence),
            missing_sources=list(ctx.missing_sources),
            scientific_constraints=list(ctx.scientific_constraints),
            pre_event_imagery=[post_scene])  # smuggled post-event scene
        provider = MockProvider(response=_valid_response(
            AGENT_REMOTE_SENSING, _allowed_ids(ctx, AGENT_REMOTE_SENSING)))
        result = _run_agent(tampered, AGENT_REMOTE_SENSING, provider)
        assert result.status == AgentStatus.SKIPPED
        assert result.skip_reason == SKIP_NO_USABLE_IMAGERY
        assert result.is_model_output is False
        assert provider.calls == [], "post-event image must never reach provider"
        for call in provider.calls:
            assert not call["images"]

    def test_misdated_image_rejected_and_skipped(self, ctx):
        """An image claiming pre_event phase but dated after the event is
        rejected by the agent's own date discipline → SKIPPED."""
        suspicious = EvidenceItem(
            evidence_id="EV-SAT-SUSPECT", evidence_type="remote_sensing_image",
            phase="pre_event_evidence", summary="日期可疑影像",
            value="S2X_misdated", observation_time="2026-08-27 05:10",
            allowed_agents=(AGENT_REMOTE_SENSING,),
            media_ref=str(Path(ctx.pre_event_imagery[0].media_ref)))
        tampered = AnalysisContext(
            run_id=ctx.run_id, mode=ctx.mode, region_id=ctx.region_id,
            analysis_time=ctx.analysis_time,
            case_metadata=ctx.case_metadata,
            allowed_evidence=list(ctx.allowed_evidence),
            context_only_evidence=list(ctx.context_only_evidence),
            missing_sources=list(ctx.missing_sources),
            scientific_constraints=list(ctx.scientific_constraints),
            pre_event_imagery=[suspicious])
        provider = MockProvider(response=_valid_response(
            AGENT_REMOTE_SENSING, _allowed_ids(ctx, AGENT_REMOTE_SENSING)))
        result = _run_agent(tampered, AGENT_REMOTE_SENSING, provider)
        assert result.status == AgentStatus.SKIPPED
        assert result.skip_reason == SKIP_NO_USABLE_IMAGERY
        assert provider.calls == []

    def test_unauthorized_image_ids_stripped(self, ctx):
        pre_id = ctx.pre_event_imagery[0].evidence_id
        provider = MockProvider(response=_valid_response(
            AGENT_REMOTE_SENSING, _allowed_ids(ctx, AGENT_REMOTE_SENSING),
            extra={"image_ids": [pre_id, "EV-SAT-POST-FAKE"]}))
        result = _run_agent(ctx, AGENT_REMOTE_SENSING, provider)
        assert "EV-SAT-POST-FAKE" not in result.agent_specific["image_ids"]

    def test_fallback_makes_no_visual_claims(self, ctx):
        provider = MockProvider(
            fail_category=ProviderErrorCategory.SERVICE_UNAVAILABLE)
        result = _run_agent(ctx, AGENT_REMOTE_SENSING, provider)
        assert result.status == AgentStatus.DEGRADED
        assert result.agent_specific.get("observations") == [], \
            "fallback must not fabricate visual observations"
        assert any("未执行 AI 目视解译" in n or "模型调用失败" in n
                   for n in result.agent_specific.get("quality_notes", []))


# ═══════════════════════════════════════════════════════════════════════════════
# Injection quarantine (guard infrastructure — mechanism test, no payloads)
# ═══════════════════════════════════════════════════════════════════════════════
class TestInjectionQuarantine:
    def test_flagged_evidence_never_enters_prompt(self, ctx, monkeypatch):
        agent = GlacierGeologyAgent(provider=MockProvider(
            response=_valid_response(
                AGENT_GLACIER_GEOLOGY,
                _allowed_ids(ctx, AGENT_GLACIER_GEOLOGY))))
        # Mechanism test: flag benign evidence items via the detector API
        # (no adversarial payload literals are reproduced here). Flagged
        # items must be excluded from the prompt and recorded.
        monkeypatch.setattr(
            agent._injection_detector, "detect",
            lambda text: ((True, "test-pattern") if "地形" in text
                          else (False, None)))
        result = agent.run(ctx)
        assert result.status == AgentStatus.COMPLETED
        assert result.quarantined_evidence_ids, \
            "flagged evidence must be recorded as quarantined"
        prompt = agent.provider.calls[0]["user_prompt"]
        system_prompt = agent.provider.calls[0]["system_prompt"]
        for qid in result.quarantined_evidence_ids:
            assert f"[{qid}]" not in prompt
            assert f"[{qid}]" not in system_prompt
        assert any("隔离" in lim for lim in result.limitations), \
            "quarantine must be transparent in limitations"


# ═══════════════════════════════════════════════════════════════════════════════
# 19 — no paid model call under ordinary pytest
# ═══════════════════════════════════════════════════════════════════════════════
class TestNoPaidCalls:
    def test_live_agent_module_is_opt_in_gated(self):
        import tests.test_deepseek_live_agents as live_mod
        marks = getattr(live_mod, "pytestmark", [])
        assert any(m.name == "skipif" for m in marks), \
            "live agent tests must be gated by RUN_LIVE_TESTS + API key"
        assert any(m.name == "live" for m in marks)

    def test_deepseek_provider_not_constructed_by_agents(self, ctx):
        """Agents only hold the injected ModelProvider abstraction; without
        injection no HTTP-capable provider is created."""
        agent = GlacierGeologyAgent()
        assert agent.provider is None
        result = agent.run(ctx)
        assert result.status == AgentStatus.DEGRADED  # safe offline degrade
