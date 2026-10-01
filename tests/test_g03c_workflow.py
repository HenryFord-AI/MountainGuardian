"""
MountainGuardian G03C – Risk Watch end-to-end workflow tests (mock only).

Gate G03C §17 required coverage:
   Workflow:            1 successful complete run     2 G03A data invocation
                        3 snapshot created            4 G03B invoked
                        5 agents invoked              6 synthesizer invoked
                        7 critic invoked              8 final result schema
                        9 run_id consistency
   Deterministic boundary:
                       10 agents cannot change score 11 synthesizer cannot
                       12 critic cannot
   Failure:            13 weather failure            14 agent failure
                       15 DeepSeek unavailable       16 synthesizer failure
                       17 critic failure
   Security:           19 no probability wording     20 no secret leakage
   Battle plan §17:    first scan / second scan trend / partial point
                       failure / snapshot persistence / run idempotency /
                       BACKFILL labeling / trend only real snapshots.

(18 no Case Pack loading, 21 security_manager untouched and 23 Historical
Replay 91 regression live in tests/test_g03c_isolation.py; 22 is the full
pytest regression run itself.)

All tests are OFFLINE: fake collectors over real G03A contracts, cached
synthetic climatology, temporary SQLite stores, scripted providers, and a
module-wide socket guard.
"""

from __future__ import annotations

import dataclasses
import json
import socket
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.critic import _PROBABILITY_PATTERNS
from agents.riskwatch_critic import RiskWatchCritic
from agents.riskwatch_synthesizer import RiskWatchSynthesizer
from orchestration.context_builder import MODE_RISK_WATCH
from orchestration.risk_watch_adapter import risk_watch_adapter
from orchestration.risk_watch_orchestrator import (
    OPTIONAL_EVIDENCE_SOURCES,
    RiskScanError,
    RiskWatchRunResult,
    build_risk_watch_context,
    compute_data_quality,
    run_risk_scan,
)
from riskwatch.engine.formulas import (
    STATUS_COMPLETED,
    STATUS_COMPLETED_WITH_LIMITATIONS,
    STATUS_FAILED,
)
from riskwatch.snapshot_store import SnapshotStore
from schemas.agent_outputs import AgentStatus
from schemas.synthesis import (
    CriticReviewResult,
    IssueSeverity,
    SynthesisResult,
)
from tests.g03b_helpers import FIXED_RETRIEVAL_TIME, flat_weather
from tests.g03c_helpers import (
    FIXED_CENTER,
    FakeCollector,
    ScriptedProvider,
    agent_payload,
    critic_payload,
    expected_engine_result,
    failing_collector,
    fixed_clock,
    fully_scripted_provider,
    make_runtime,
    make_test_region,
    partial_collector,
    synthesis_payload,
)


# ─── network guard: no test may touch the network (no paid calls) ────────────
@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def _guard(*args, **kwargs):
        raise AssertionError(
            "network access attempted in G03C mock suite — ordinary pytest "
            "must never call a live provider or weather API")
    monkeypatch.setattr(socket, "socket", _guard)
    monkeypatch.setattr(socket, "create_connection", _guard)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)


@pytest.fixture()
def env(tmp_path, monkeypatch):
    """Isolated scan environment: region + runtime (climatology) + db."""
    region = make_test_region(tmp_path)
    runtime = make_runtime(tmp_path)
    db_path = tmp_path / "scan.db"
    monkeypatch.delenv("MOUNTAINGUARDIAN_DB_PATH", raising=False)
    monkeypatch.delenv("MOUNTAINGUARDIAN_RUNTIME_DIR", raising=False)
    return {"tmp": tmp_path, "region": region, "runtime": runtime,
            "db": db_path, "regions_dir": tmp_path / "regions"}


def scan(env, *, collector=None, provider=None, run_id=None, **kwargs):
    """One offline scan over the standard fixtures."""
    collector = collector or FakeCollector(flat_weather(FIXED_CENTER))
    return run_risk_scan(
        env["region"].region_id,
        provider=provider,
        regions_dir=env["regions_dir"],
        runtime_dir=env["runtime"],
        db_path=env["db"],
        collector=collector,
        clock=fixed_clock(),
        run_id=run_id,
        generate_climatology=False,
        **kwargs)


# ═══ 1-9: workflow ═══════════════════════════════════════════════════════════
class TestWorkflowSuccess:
    def test_01_successful_complete_run(self, env):
        expected = expected_engine_result(env["region"], run_id="g03c-ok")
        provider = fully_scripted_provider(expected)
        result = scan(env, provider=provider, run_id="g03c-ok")

        assert isinstance(result, RiskWatchRunResult)
        assert result.status == STATUS_COMPLETED
        assert result.risk_index == pytest.approx(expected.C)
        assert result.risk_level == expected.current_risk_level
        assert result.outlook_7d_index == pytest.approx(expected.O7)
        # agents: glacier + weather completed by the scripted model;
        # remote sensing SKIPPED (no authorized imagery pipeline in G03C —
        # a valid formal output per doc 04 §23, not a failure)
        summary = result.ai_layer["agent_status_summary"]
        assert summary["glacier_geology"] == AgentStatus.COMPLETED.value
        assert summary["weather_hydrology"] == AgentStatus.COMPLETED.value
        assert summary["remote_sensing"] == AgentStatus.SKIPPED.value
        assert result.synthesis_status == "COMPLETED"
        assert result.synthesis.is_model_output is True
        assert result.critic_status in {v.value for v in CriticReviewResult}
        # full state machine walked (doc 04 §29)
        stages = [s[0] for s in result.stage_trace]
        assert stages[0] == "CREATED" and stages[-1] == "COMPLETED"
        assert "SNAPSHOT_SAVED" in stages and "ENGINE_COMPLETED" in stages
        # DeepSeek call accounting: 2 agents + synthesis + critic
        # (remote sensing short-circuits BEFORE any provider call)
        assert result.provenance["provider"]["generation_calls"] == 4
        # no Risk Watch data-integrity issue on a clean scan
        assert not [i for i in result.critic.issues
                    if i.check_id.startswith("RW_")]

    def test_02_g03a_data_invocation(self, env):
        collector = FakeCollector(flat_weather(FIXED_CENTER))
        result = scan(env, provider=None, collector=collector)
        # the G03A collector was invoked exactly once for this region
        assert collector.calls == [env["region"].region_id]
        prov = result.provenance["weather"]
        assert prov["status"] == "OK"
        assert prov["retrieval_time"] == FIXED_RETRIEVAL_TIME
        assert prov["endpoint"].startswith("https://api.open-meteo.com")
        # weather provenance persisted in the data snapshot
        with SnapshotStore(env["db"]) as store:
            row = store.get(result.data_snapshot_id)
        wp = row["payload"]["weather_provenance"]
        assert set(wp) == {"source_zone", "port_zone"}
        assert wp["source_zone"]["provider"] == "Open-Meteo"
        assert wp["source_zone"]["retrieval_time"]

    def test_03_snapshot_created_new_never_overwritten(self, env):
        first = scan(env, provider=None, run_id="g03c-s1")
        with SnapshotStore(env["db"]) as store:
            assert store.count() == 2          # data + result
            data_row = store.get(first.data_snapshot_id)
            data_payload_before = json.dumps(data_row["payload"],
                                             sort_keys=True)
        second = scan(env, provider=None, run_id="g03c-s2")
        with SnapshotStore(env["db"]) as store:
            assert store.count() == 4          # every scan → NEW snapshots
            # first data snapshot untouched (insert-only store)
            data_row_after = store.get(first.data_snapshot_id)
            assert json.dumps(data_row_after["payload"],
                              sort_keys=True) == data_payload_before
        assert first.data_snapshot_id != second.data_snapshot_id
        assert first.result_snapshot_id != second.result_snapshot_id
        assert first.data_snapshot_id and first.result_snapshot_id

    def test_04_g03b_engine_invoked_not_duplicated(self, env):
        # the workflow's deterministic result must be BYTE-IDENTICAL to a
        # direct G03B computation over the same inputs — proof the engine
        # was called, never reimplemented
        expected = expected_engine_result(env["region"], run_id="g03c-eng")
        result = scan(env, provider=None, run_id="g03c-eng")
        assert result.deterministic_result.to_json() == expected.to_json()
        assert result.deterministic_result.algorithm_version == \
            expected.algorithm_version

    def test_05_agents_invoked(self, env):
        expected = expected_engine_result(env["region"], run_id="g03c-ag")
        provider = fully_scripted_provider(expected)
        result = scan(env, provider=provider, run_id="g03c-ag")
        assert set(result.agent_results) == {
            "glacier_geology", "weather_hydrology", "remote_sensing"}
        kinds = [c["kind"] for c in provider.calls]
        assert "agent:glacier_geology" in kinds
        assert "agent:weather_hydrology" in kinds
        assert "agent:remote_sensing" not in kinds  # SKIPPED pre-provider
        # agent prompts carry the Risk Watch mode and evidence package
        gg_call = next(c for c in provider.calls
                       if c["kind"] == "agent:glacier_geology")
        assert "risk_watch" in gg_call["user_prompt"]
        assert "RW-STATIC-B" in gg_call["user_prompt"]
        for res in result.agent_results.values():
            assert res.run_id == "g03c-ag"
            assert res.input_evidence_ids  # saw the evidence package

    def test_06_synthesizer_invoked(self, env):
        expected = expected_engine_result(env["region"], run_id="g03c-sy")
        provider = fully_scripted_provider(expected)
        result = scan(env, provider=provider, run_id="g03c-sy")
        synth_call = next(c for c in provider.calls
                          if c["kind"] == "synthesis")
        assert "Risk Watch" in synth_call["system_prompt"]
        assert f"{expected.C:.2f}" in synth_call["user_prompt"] or \
            str(round(expected.C, 2)) in synth_call["user_prompt"]
        assert result.synthesis.deterministic_risk_index == \
            pytest.approx(expected.C)
        assert result.synthesis.risk_level == expected.current_risk_level
        # §12: the synthesis must state the index is NOT a probability —
        # appended by the runtime regardless of model wording
        assert any("不是灾害发生概率" in l
                   for l in result.synthesis.limitations)

    def test_07_critic_invoked(self, env):
        expected = expected_engine_result(env["region"], run_id="g03c-cr")
        provider = fully_scripted_provider(expected)
        result = scan(env, provider=provider, run_id="g03c-cr")
        assert any(c["kind"] == "critic" for c in provider.calls)
        verdict = result.critic
        assert verdict.review_result in {v.value for v in CriticReviewResult}
        # integrity attestation: the critic never touched the index
        assert verdict.risk_index_before == pytest.approx(expected.C)
        assert verdict.risk_index_after == pytest.approx(expected.C)

    def test_08_final_result_schema(self, env):
        result = scan(env, provider=None, run_id="g03c-schema")
        d = result.to_dict()
        # gate G03C §14 required schema
        for key in ("run_id", "region_id", "created_time",
                    "deterministic_result", "agent_results", "synthesis",
                    "critic", "critic_status", "limitations", "provenance"):
            assert key in d, key
        det = d["deterministic_result"]
        for key in ("B", "R", "F", "D", "C", "O7", "current_risk_level"):
            assert key in det, key
        # fully JSON-serializable
        payload = json.loads(result.to_json())
        assert payload["run_id"] == "g03c-schema"
        # persisted result snapshot carries the G03B trend-compat keys
        with SnapshotStore(env["db"]) as store:
            row = store.get(result.result_snapshot_id)
        top = row["payload"]
        assert top["snapshot_kind"] == "risk_watch_result"
        assert top["current_risk_index"] == pytest.approx(result.risk_index)
        assert "point_recent_percentiles" in top
        assert "point_forecast_percentiles" in top
        assert row["status"] == result.status
        assert row["run_id"] == result.run_id
        assert row["is_invalid"] == 0

    def test_09_run_id_consistency(self, env):
        provider = fully_scripted_provider(
            expected_engine_result(env["region"], run_id="g03c-rid"))
        result = scan(env, provider=provider, run_id="g03c-rid")
        rid = result.run_id
        assert rid == "g03c-rid"
        assert result.deterministic_result.run_id == rid
        assert all(r.run_id == rid for r in result.agent_results.values())
        assert result.synthesis.run_id == rid
        assert result.critic.run_id == rid
        assert all(c["run_id"] == rid for c in provider.calls)
        with SnapshotStore(env["db"]) as store:
            rows = store.list_snapshots()
        assert rows and all(r["run_id"] == rid for r in rows)
        assert result.data_quality["weather_status"] == "OK"


# ═══ 10-12: deterministic boundary (Layer 2 never changes Layer 1) ═══════════
class TestDeterministicBoundary:
    def test_10_agents_cannot_change_risk_score(self, env):
        expected = expected_engine_result(env["region"], run_id="g03c-b10")
        hostile = ScriptedProvider(
            agent_responses={
                "glacier_geology": agent_payload(
                    "glacier_geology", risk_signal="LOW", confidence=1.0),
                "weather_hydrology": agent_payload(
                    "weather_hydrology", risk_signal="LOW", confidence=1.0),
            },
            default_agent=None,
            synthesis_response=synthesis_payload(
                expected.C, expected.current_risk_level),
            critic_response=critic_payload())
        # hostile agents claim LOW risk in their narratives
        hostile.agent_responses["glacier_geology"]["key_findings"] = [
            "风险指数已降为 10，区域安全"]
        result = scan(env, provider=hostile, run_id="g03c-b10")
        # deterministic layer is untouched
        assert result.risk_index == pytest.approx(expected.C)
        assert result.risk_level == expected.current_risk_level
        assert result.deterministic_result.to_json() == expected.to_json()
        assert result.synthesis.deterministic_risk_index == \
            pytest.approx(expected.C)

    def test_11_synthesizer_cannot_change_risk_score(self, env):
        expected = expected_engine_result(env["region"], run_id="g03c-b11")
        tampered = synthesis_payload(expected.C, expected.current_risk_level)
        tampered["risk_index"] = min(expected.C + 10.0, 100.0)  # altered!
        provider = ScriptedProvider(
            agent_responses={
                "glacier_geology": agent_payload("glacier_geology"),
                "weather_hydrology": agent_payload("weather_hydrology")},
            synthesis_response=tampered,
            critic_response=critic_payload())
        result = scan(env, provider=provider, run_id="g03c-b11")
        # the altered index is REJECTED by the validator; the runtime
        # re-imposes the deterministic value; model output is not accepted
        assert result.risk_index == pytest.approx(expected.C)
        assert result.synthesis.deterministic_risk_index == \
            pytest.approx(expected.C)
        assert result.synthesis.is_model_output is False
        assert result.deterministic_result.to_json() == expected.to_json()

    def test_12_critic_cannot_change_risk_score(self, env):
        expected = expected_engine_result(env["region"], run_id="g03c-b12")
        provider = fully_scripted_provider(expected)
        provider.critic_response = critic_payload(
            review_result=CriticReviewResult.BLOCKED.value)
        result = scan(env, provider=provider, run_id="g03c-b12")
        # even a BLOCKED verdict leaves Layer 1 byte-identical
        assert result.critic_status == CriticReviewResult.BLOCKED.value
        assert result.risk_index == pytest.approx(expected.C)
        assert result.deterministic_result.to_json() == expected.to_json()
        assert result.critic.risk_index_before == \
            result.critic.risk_index_after == pytest.approx(expected.C)

    def test_adapter_is_immutable(self, env):
        expected = expected_engine_result(env["region"])
        adapter = risk_watch_adapter(expected)
        with pytest.raises(dataclasses.FrozenInstanceError):
            adapter.risk_index = 0.0
        with pytest.raises(dataclasses.FrozenInstanceError):
            adapter.risk_level = "LOW"

    def test_adapter_refuses_failed_result(self, env):
        result = scan(env, collector=failing_collector(), provider=None)
        assert result.deterministic_result.status == STATUS_FAILED
        from orchestration.risk_watch_adapter import RiskWatchAdapterError
        with pytest.raises(RiskWatchAdapterError):
            risk_watch_adapter(result.deterministic_result)


# ═══ 13-17: failure handling (gate §15) ══════════════════════════════════════
class TestFailureHandling:
    def test_13_weather_failure_no_fabricated_risk(self, env):
        result = scan(env, collector=failing_collector(), provider=None,
                      run_id="g03c-f13")
        det = result.deterministic_result
        assert det.status == STATUS_FAILED
        assert result.status == STATUS_FAILED
        # NO official index — nothing fabricated, zero-filled or carried over
        assert result.risk_index is None
        assert det.C is None and det.D is None and det.O7 is None
        assert result.risk_level is None
        # static baseline B remains independently reportable
        assert det.B == pytest.approx(92.222)
        # AI layer skipped entirely — no explanation invented
        assert result.ai_layer["status"] == "SKIPPED_NO_DETERMINISTIC_RESULT"
        assert result.agent_results == {}
        assert result.synthesis is None
        assert result.critic is None
        assert result.critic_status == "UNAVAILABLE_NO_DETERMINISTIC_RESULT"
        assert any("no official Current Risk Index" in l.lower()
                   or "不允许" in l or "unavailable" in l.lower()
                   for l in result.limitations)
        # both snapshots persisted for audit — failure is recorded, not hidden
        with SnapshotStore(env["db"]) as store:
            data_row = store.get(result.data_snapshot_id)
            res_row = store.get(result.result_snapshot_id)
        assert data_row["status"] == "DATA_FAILED"
        assert res_row["status"] == STATUS_FAILED
        assert res_row["payload"]["current_risk_index"] is None
        # a FAILED scan never becomes trend history
        assert result.historical_trend.status == "NO_HISTORY"

    def test_14_agent_failure_isolated(self, env):
        expected = expected_engine_result(env["region"], run_id="g03c-f14")
        provider = fully_scripted_provider(expected)

        class CrashAgent:
            agent_name = "glacier_geology"

            def run(self, context):
                raise RuntimeError("simulated catastrophic agent crash")

        from agents.remote_sensing_agent import RemoteSensingAgent
        from agents.weather_hydrology_agent import WeatherHydrologyAgent
        result = scan(
            env, provider=provider, run_id="g03c-f14",
            agents=[CrashAgent(),
                    WeatherHydrologyAgent(provider=provider),
                    RemoteSensingAgent(provider=provider)])
        # crashed agent is FAILED but the scan continues on Layer 1
        assert result.agent_results["glacier_geology"].status == \
            AgentStatus.FAILED
        assert result.agent_results["weather_hydrology"].status == \
            AgentStatus.COMPLETED
        assert result.risk_index == pytest.approx(expected.C)
        assert result.status == STATUS_COMPLETED_WITH_LIMITATIONS
        assert any("glacier_geology FAILED" in l
                   for l in result.limitations)

    def test_15_deepseek_unavailable_fallback_labeled(self, env):
        expected = expected_engine_result(env["region"], run_id="g03c-f15")
        result = scan(env, provider=None, run_id="g03c-f15")  # NO provider
        # deterministic layer fully available
        assert result.risk_index == pytest.approx(expected.C)
        assert result.status == STATUS_COMPLETED_WITH_LIMITATIONS
        # AI layer degraded with honest labels — never disguised as model
        assert result.synthesis_status == "FALLBACK"
        assert result.synthesis.fallback_used is True
        assert result.synthesis.is_model_output is False
        assert result.synthesis.deterministic_risk_index == \
            pytest.approx(expected.C)
        for name, res in result.agent_results.items():
            if res.status in (AgentStatus.COMPLETED, AgentStatus.DEGRADED):
                assert res.is_model_output is False
        assert any("fallback" in l.lower() or "回退" in l
                   for l in result.limitations)
        assert result.provenance["provider"]["generation_calls"] == 0
        # critic verdict still produced by the programmatic checks
        assert result.critic_status in {v.value for v in CriticReviewResult}
        assert result.critic.fallback_used is False  # no provider → offline

    def test_15b_deepseek_provider_error_fallback(self, env, monkeypatch):
        # a provider that fails every call (e.g. DeepSeek outage)
        expected = expected_engine_result(env["region"], run_id="g03c-f15b")
        provider = ScriptedProvider(
            fail_kinds={"agent:glacier_geology", "agent:weather_hydrology",
                        "agent:remote_sensing", "synthesis", "critic"})
        result = scan(env, provider=provider, run_id="g03c-f15b")
        assert result.risk_index == pytest.approx(expected.C)
        assert result.agent_results["glacier_geology"].fallback_used is True
        assert result.synthesis.fallback_used is True
        assert result.synthesis.is_model_output is False
        assert result.status == STATUS_COMPLETED_WITH_LIMITATIONS
        # deterministic result byte-identical despite total model outage
        assert result.deterministic_result.to_json() == expected.to_json()

    def test_16_synthesizer_failure_returns_deterministic_only(self, env):
        class ExplodingSynthesizer:
            def run(self, *args, **kwargs):
                raise RuntimeError("synthesizer internal failure")

        result = scan(env, provider=None, synthesizer=ExplodingSynthesizer(),
                      run_id="g03c-f16")
        # deterministic result returned; NO fake explanation
        assert result.synthesis is None
        assert result.synthesis_status == "UNAVAILABLE"
        assert result.critic is None
        assert result.critic_status == "UNAVAILABLE_NO_SYNTHESIS"
        assert result.risk_index is not None
        assert any("Synthesizer failure" in l
                   for l in result.limitations)
        assert result.status == STATUS_COMPLETED_WITH_LIMITATIONS
        # still persisted
        with SnapshotStore(env["db"]) as store:
            row = store.get(result.result_snapshot_id)
        assert row["payload"]["synthesis"] is None

    def test_17_critic_failure_disclosed(self, env):
        class ExplodingCritic:
            def run(self, *args, **kwargs):
                raise RuntimeError("critic internal failure")

        result = scan(env, provider=None, critic=ExplodingCritic(),
                      run_id="g03c-f17")
        assert result.critic is None
        assert result.critic_status == "UNAVAILABLE"
        assert any("Critic failure" in l and "not hidden" in l
                   for l in result.limitations)
        # everything upstream remains valid and persisted
        assert result.synthesis is not None
        assert result.risk_index is not None
        assert result.status == STATUS_COMPLETED_WITH_LIMITATIONS

    def test_snapshot_store_failure_aborts_fail_safe(self, env):
        class BrokenStore(SnapshotStore):
            def insert_snapshot(self, *args, **kwargs):
                raise RuntimeError("simulated db failure")

        broken = BrokenStore(env["db"])
        with pytest.raises(RiskScanError):
            scan(env, provider=None, store=broken)
        broken.close()

    def test_invalid_scan_mode_rejected(self, env):
        with pytest.raises(RiskScanError):
            scan(env, provider=None, scan_mode="PRETEND_LIVE")


# ═══ 19-20: security ═════════════════════════════════════════════════════════
class TestSecurity:
    def _narrative_texts(self, result: RiskWatchRunResult) -> list:
        texts = list(result.limitations)
        if result.synthesis is not None:
            s = result.synthesis
            texts += [s.summary, s.risk_explanation, *s.top_drivers,
                      *s.limitations, *s.missing_data, *s.disagreements]
        for res in result.agent_results.values():
            texts += [str(f) for f in res.key_findings]
            texts += [str(f) for f in res.limitations]
        if result.critic is not None:
            texts += [str(x) for x in result.critic.scientific_limitations]
        return [t for t in texts if t]

    def test_19_no_probability_wording(self, env):
        expected = expected_engine_result(env["region"], run_id="g03c-s19")
        for kwargs in ({"provider": None},
                       {"provider": fully_scripted_provider(expected)}):
            result = scan(env, run_id="g03c-s19", **kwargs)
            for text in self._narrative_texts(result):
                for pattern in _PROBABILITY_PATTERNS:
                    assert not pattern.search(text), \
                        f"probability wording {pattern!r} in {text[:80]!r}"
            # the required semantics statement is present
            assert result.synthesis is not None
            assert any("不是灾害发生概率" in l
                       for l in result.synthesis.limitations)

    def test_20_no_secret_leakage(self, env, monkeypatch):
        secret = "sk-TESTKEY-9f3d2a1c-do-not-leak"
        monkeypatch.setenv("DEEPSEEK_API_KEY", secret)
        # 'auto' resolves the REAL DeepSeekProvider; the socket guard makes
        # every HTTP attempt fail — the chain must sanitize, never echo
        result = scan(env, provider="auto", run_id="g03c-s20")
        blob = result.to_json()
        assert secret not in blob
        with SnapshotStore(env["db"]) as store:
            for row in store.list_snapshots():
                assert secret not in json.dumps(row, ensure_ascii=False,
                                                default=str)
        # and the scan still degraded honestly to fallbacks
        assert result.synthesis.fallback_used is True
        assert result.risk_index is not None


# ═══ battle plan §17: first scan / trend / partial / idempotency ═════════════
class TestScanLifecycle:
    def test_first_scan_has_no_history(self, env):
        result = scan(env, provider=None, run_id="g03c-first")
        det = result.deterministic_result
        assert det.risk_direction == "NO_HISTORY"
        assert det.previous_C is None and det.delta_C is None
        assert det.what_changed["status"] == "NO_HISTORY"
        assert result.historical_trend.status == "INSUFFICIENT_HISTORY"
        assert len(result.historical_trend.entries) == 1

    def test_second_scan_trend_and_what_changed(self, env):
        first = scan(env, provider=None, run_id="g03c-t1")
        second = scan(env, provider=None, run_id="g03c-t2")
        det = second.deterministic_result
        assert det.previous_C == pytest.approx(first.risk_index)
        assert det.delta_C == pytest.approx(0.0)
        assert det.risk_direction == "STABLE"
        assert det.what_changed["status"] == "COMPARISON_AVAILABLE"
        assert det.what_changed["previous_snapshot_id"] == \
            first.result_snapshot_id
        trend = second.historical_trend
        assert trend.status == "SIMPLE_COMPARISON"
        assert [e.snapshot_id for e in trend.entries] == \
            [first.result_snapshot_id, second.result_snapshot_id]

    def test_partial_point_failure_completed_with_limitations(self, env):
        result = scan(env, collector=partial_collector(), provider=None,
                      run_id="g03c-partial")
        det = result.deterministic_result
        assert det.status == STATUS_COMPLETED_WITH_LIMITATIONS
        assert result.status == STATUS_COMPLETED_WITH_LIMITATIONS
        # aggregation used ONLY the successful point — nothing zero-filled
        assert det.R is not None and det.F is not None
        assert det.recent_aggregation.driver_point_id == "source_zone"
        excluded = {m["point_id"] for m in det.missing_data}
        assert excluded == {"port_zone"}
        # offline synthesizer fallback discloses the gap
        joined = " ".join(result.synthesis.missing_data
                          + result.synthesis.limitations)
        assert "port_zone" in joined

    def test_run_idempotency_and_append_only(self, env):
        a = scan(env, provider=None, run_id="g03c-idem-a")
        b = scan(env, provider=None, run_id="g03c-idem-b")
        # same deterministic inputs → same official numbers
        assert a.risk_index == pytest.approx(b.risk_index)
        assert a.deterministic_result.B == b.deterministic_result.B
        assert a.deterministic_result.R == b.deterministic_result.R
        # but every scan is a NEW audited record — never a rewrite
        assert a.run_id != b.run_id
        assert a.result_snapshot_id != b.result_snapshot_id
        with SnapshotStore(env["db"]) as store:
            assert store.count() == 4

    def test_data_snapshots_never_enter_trend(self, env):
        scan(env, provider=None, run_id="g03c-tr")
        from riskwatch.engine.trend import query_historical_trend
        with SnapshotStore(env["db"]) as store:
            rows = store.list_snapshots()
            assert len(rows) == 2
            data_rows = [r for r in rows if r["status"].startswith("DATA_")]
            assert len(data_rows) == 1
            trend = query_historical_trend(store, "test_region")
        # only the RESULT snapshot is trend-eligible, never the data row
        assert [e.snapshot_id for e in trend.entries] == \
            [r["snapshot_id"] for r in rows
             if not r["status"].startswith("DATA_")]

    def test_backfill_labeling_and_exclusion(self, env):
        bf = scan(env, provider=None, run_id="g03c-bf",
                  scan_mode="BACKFILL")
        with SnapshotStore(env["db"]) as store:
            rows = {r["snapshot_id"]: r for r in store.list_snapshots()}
        assert rows[bf.result_snapshot_id]["scan_mode"] == "BACKFILL"
        # the next LIVE scan does NOT silently consume backfill history
        live = scan(env, provider=None, run_id="g03c-live2")
        assert live.deterministic_result.previous_C is None
        assert live.deterministic_result.risk_direction == "NO_HISTORY"
        trend_entries = live.historical_trend.entries
        assert all(e.scan_mode == "LIVE" for e in trend_entries)


# ═══ evidence package + data quality (steps 3 & 6 units) ═════════════════════
class TestEvidencePackage:
    def _context(self, env):
        region = env["region"]
        weather_map = flat_weather(FIXED_CENTER)
        collector = FakeCollector(weather_map)
        weather = collector.collect_region(region)
        from tests.g03b_helpers import flat_climatologies
        climatologies = flat_climatologies()
        watch = expected_engine_result(region, weather_map)
        dq = compute_data_quality(region, weather, climatologies)
        ctx = build_risk_watch_context(
            region, weather, climatologies, watch, dq,
            "g03c-ctx", FIXED_RETRIEVAL_TIME)
        return ctx, watch

    def test_context_is_risk_watch_mode_and_case_pack_free(self, env):
        ctx, _ = self._context(env)
        assert ctx.mode == MODE_RISK_WATCH
        ctx.assert_no_post_event()
        ids = {i.evidence_id for i in ctx.allowed_evidence}
        # no Case-Pack derived evidence ids anywhere
        assert not any(i.startswith(("EV-", "DF-")) for i in ids)
        assert {"RW-STATIC-B", "RW-ENGINE-C", "RW-ENGINE-O7",
                "RW-POINTS"} <= ids

    def test_required_and_optional_coverage_kept_separate(self, env):
        from tests.g03b_helpers import flat_climatologies
        region = env["region"]
        weather = FakeCollector(
            flat_weather(FIXED_CENTER)).collect_region(region)
        dq = compute_data_quality(region, weather, flat_climatologies())
        # doc 04 §42: required and optional coverage are NEVER blended
        assert dq["required_coverage"]["total"] == 2
        assert dq["required_coverage"]["ok"] == 2
        assert dq["required_coverage"]["failed"] == []
        assert dq["optional_coverage"]["available"] == 0
        assert len(dq["optional_coverage"]["missing"]) == \
            len(OPTIONAL_EVIDENCE_SOURCES)
        assert dq["satellite_pipeline_available"] is False

    def test_missing_sources_are_explicit_items(self, env):
        ctx, _ = self._context(env)
        missing_ids = {i.evidence_id for i in ctx.missing_sources}
        assert {"RW-OPT-SATELLITE", "RW-OPT-HYDRO", "RW-OPT-SOIL",
                "RW-OPT-ENSO"} == missing_ids
        for item in ctx.missing_sources:
            assert item.quality == "MISSING"
            assert item.phase == "missing_input"


# ═══ doc 04 §43 critic data-integrity checks (unit level) ════════════════════
class TestRiskWatchCriticChecks:
    def _scan_record(self, env, watch=None, weather=None):
        from orchestration.risk_watch_adapter import RiskWatchScanRecord
        from tests.g03b_helpers import flat_climatologies
        region = env["region"]
        weather = weather or FakeCollector(
            flat_weather(FIXED_CENTER)).collect_region(region)
        watch = watch or expected_engine_result(region)
        dq = compute_data_quality(
            region, weather, flat_climatologies())
        return RiskWatchScanRecord(
            region=region, weather=weather,
            climatologies=flat_climatologies(),
            watch_result=watch, data_quality=dq)

    def _synthesis(self, watch) -> SynthesisResult:
        # mirrors what the real synthesizer runtime produces: missing_data
        # includes the declared optional-source gaps (doc 04 §43 check 9)
        optional_missing = [
            f"{summary}（该数据源当前不可用）"
            for _eid, summary, _agents in OPTIONAL_EVIDENCE_SOURCES]
        return SynthesisResult(
            run_id="g03c-critic-unit",
            deterministic_risk_index=watch.C,
            risk_level=watch.current_risk_level,
            summary=f"当前风险指数 C={watch.C:.2f}，不是灾害发生概率。",
            risk_explanation="静态背景与降水百分位共同驱动，非概率表述。",
            top_drivers=["静态易灾背景"],
            evidence_coverage=0.7,
            missing_data=["源区实时动态监测数据（未获得公开数据）"]
            + optional_missing,
            limitations=["网格化模型天气非现场实测。",
                         "remote_sensing SKIPPED：无可用授权影像。"],
            evidence_ids=["RW-ENGINE-C"])

    def _run_critic(self, scan_record, synthesis, agent_results=None):
        from orchestration.risk_watch_adapter import risk_watch_adapter
        critic = RiskWatchCritic(provider=None, scan=scan_record)
        ctx_agent_results = agent_results or {}
        adapter = risk_watch_adapter(scan_record.watch_result)
        return critic.run(synthesis, adapter, ctx_agent_results,
                          _MinimalContext())

    def test_clean_scan_produces_no_rw_issues(self, env):
        watch = expected_engine_result(env["region"])
        record = self._scan_record(env, watch=watch)
        verdict = self._run_critic(record, self._synthesis(watch))
        rw_issues = [i for i in verdict.issues
                     if i.check_id.startswith("RW_")]
        assert rw_issues == []

    def test_tampered_C_is_caught_as_critical(self, env):
        watch = expected_engine_result(env["region"])
        tampered = dataclasses.replace(watch, C=watch.C + 5.0)
        record = self._scan_record(env, watch=tampered)
        verdict = self._run_critic(record, self._synthesis(watch))
        rw = [i for i in verdict.issues
              if i.check_id == "RW_FORMULA_INTEGRITY"]
        assert rw and any(i.severity == IssueSeverity.CRITICAL.value
                          for i in rw)
        assert verdict.review_result == CriticReviewResult.BLOCKED.value

    def test_tampered_percentile_is_caught(self, env):
        watch = expected_engine_result(env["region"])
        agg = watch.recent_aggregation
        bad_point = dataclasses.replace(
            agg.point_percentiles[0], percentile=1.234)
        bad_agg = dataclasses.replace(
            agg, point_percentiles=(bad_point,) +
            tuple(agg.point_percentiles[1:]))
        tampered = dataclasses.replace(watch, recent_aggregation=bad_agg)
        record = self._scan_record(env, watch=tampered)
        verdict = self._run_critic(record, self._synthesis(watch))
        assert any(i.check_id == "RW_FORMULA_INTEGRITY"
                   and "percentile" in i.message
                   for i in verdict.issues)

    def test_stale_weather_must_be_disclosed(self, env):
        watch = expected_engine_result(env["region"])
        record = self._scan_record(env, watch=watch)
        synthesis = self._synthesis(watch)
        synthesis.limitations = ["与数据质量无关的限制。"]
        # force a STALE point in the scan record
        for pw in record.weather.points.values():
            pw.quality = "STALE"
        verdict = self._run_critic(record, synthesis)
        assert any(i.check_id == "RW_DATA_INTEGRITY"
                   and "fresh" in i.message.lower()
                   for i in verdict.issues)

    def test_overconclusion_phrases_flagged(self, env):
        watch = expected_engine_result(env["region"])
        record = self._scan_record(env, watch=watch)
        synthesis = self._synthesis(watch)
        # NOTE: the shared _negated() heuristic (frozen G02B) treats a "未"
        # within 12 chars before the phrase as a negation context, so the
        # assertive sentence must not carry negation characters nearby.
        synthesis.summary = "source zone 即将发生泥石流，请紧急撤离。"
        verdict = self._run_critic(record, synthesis)
        assert any(i.check_id == "RW_OVERCLAIM" for i in verdict.issues)

    def test_no_scan_record_is_disclosed_not_fatal(self, env):
        watch = expected_engine_result(env["region"])
        critic = RiskWatchCritic(provider=None, scan=None)
        verdict = critic.run(
            self._synthesis(watch), risk_watch_adapter(watch), {},
            _MinimalContext())
        assert any(i.check_id == "RW_DATA_INTEGRITY"
                   and i.severity == IssueSeverity.INFO.value
                   for i in verdict.issues)


class _MinimalContext:
    """Duck-typed AnalysisContext stand-in for critic unit tests."""

    mode = MODE_RISK_WATCH
    run_id = "g03c-critic-unit"
    missing_sources = []
    scientific_constraints = []
    case_metadata = {}
    allowed_evidence = []
    context_only_evidence = []
    pre_event_imagery = []

    def evidence_by_id(self):
        return {}

    def assert_no_post_event(self):
        return None


# ═══ synthesizer specialization units ════════════════════════════════════════
class TestRiskWatchSynthesizerUnits:
    def test_fallback_payload_speaks_risk_watch(self, env):
        watch = expected_engine_result(env["region"], run_id="g03c-syn-fb")
        synth = RiskWatchSynthesizer(provider=None)
        result = scan(env, provider=None, run_id="g03c-syn-fb")
        fb = result.synthesis
        assert fb.fallback_used is True
        text = fb.summary + fb.risk_explanation
        # Risk Watch vocabulary — never the replay six-factor model
        assert "[规则回退]" in text
        assert f"{watch.C:.2f}" in text.replace(
            f"{round(watch.C, 2)}", f"{watch.C:.2f}") or \
            str(round(watch.C, 2)) in text
        assert "六因子" not in text
        assert "不是灾害发生概率" in text

    def test_prompt_never_mentions_historical_replay(self, env):
        expected = expected_engine_result(env["region"], run_id="g03c-p")
        provider = fully_scripted_provider(expected)
        scan(env, provider=provider, run_id="g03c-p")
        synth_call = next(c for c in provider.calls
                          if c["kind"] == "synthesis")
        critic_call = next(c for c in provider.calls
                           if c["kind"] == "critic")
        for call in (synth_call, critic_call):
            assert "Historical Replay" not in call["system_prompt"]
            assert "Stage A" not in call["system_prompt"]
            assert "risk_watch" in call["user_prompt"]
