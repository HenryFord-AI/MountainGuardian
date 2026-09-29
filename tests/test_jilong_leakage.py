"""
MountainGuardian – Jilong demo scientific-integrity tests.

The single most important property: post_event_validation data must NEVER
reach the Risk agent, while the Checker agent must receive it.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.case_loader import load_case, build_demo_context, PRE_EVENT_PHASES
from agents.coordinator_agent import CoordinatorAgent
from agents.jilong_agents import RiskAnalysisAgent


@pytest.fixture(scope="module")
def case():
    return load_case()


@pytest.fixture(scope="module")
def ctx(case):
    return build_demo_context(case)


class TestCaseLoader:
    def test_phase_partition_disjoint(self, case):
        assert case["pre_event"] and case["post_event"]
        assert all(f["phase"] in PRE_EVENT_PHASES for f in case["pre_event"])
        assert all(f["phase"] == "post_event_validation" for f in case["post_event"])
        assert not ({f["key"] for f in case["pre_event"]} &
                    {f["key"] for f in case["post_event"]})

    def test_p1_conflict_neutralized(self, case):
        """Case Pack P-1: C009/C040 carry 'Intelligence' in agent_use despite
        post_event phase. The loader must place them by phase, not agent_use."""
        pre_keys = {f["key"] for f in case["pre_event"]}
        assert "source_area" not in pre_keys
        assert "official_satellite_scene_count" not in pre_keys


class TestDataLeakage:
    def test_risk_sub_context_has_no_post_event(self, ctx):
        coord = CoordinatorAgent()
        sub = coord._build_sub_context(ctx, "risk")
        assert "post_event" not in sub
        assert all(f["phase"] in PRE_EVENT_PHASES for f in sub["case_data"])

    def test_intelligence_sub_context_has_no_post_event(self, ctx):
        coord = CoordinatorAgent()
        sub = coord._build_sub_context(ctx, "intelligence")
        assert "post_event" not in sub

    def test_checker_receives_post_event(self, ctx):
        coord = CoordinatorAgent()
        sub = coord._build_sub_context(ctx, "checker")
        assert sub["post_event"], "Checker must see post_event for validation"

    def test_full_pipeline_no_leakage_in_risk_input(self, ctx):
        """End-to-end: run the real pipeline and re-verify what the Risk agent
        could have seen via its sub-context construction path."""
        coord = CoordinatorAgent()
        result = coord.run(ctx)
        assert result.success is True
        risk_sub = coord._build_sub_context(ctx, "risk")
        assert "post_event" not in risk_sub
        consulted = result.content["agents_consulted"]
        assert "风险分析员 Agent" in consulted
        assert "检查员 Agent" in consulted


class TestRiskModel:
    def test_risk_index_is_91(self, case):
        agent = RiskAnalysisAgent()
        res = agent.run({"risk_model": case["risk_model"], "case_data": case["pre_event"]})
        assert res.success is True
        assert res.content["risk_index"] == 91.0
        assert res.content["risk_index"] == res.content["pack_stated_index"]

    def test_weights_sum_to_100(self, case):
        agent = RiskAnalysisAgent()
        res = agent.run({"risk_model": case["risk_model"]})
        assert res.content["weight_sum"] == 100

    def test_six_factors_explained(self, case):
        agent = RiskAnalysisAgent()
        res = agent.run({"risk_model": case["risk_model"]})
        assert len(res.content["contributions"]) == 6
        assert all(c["evidence"] and c["source_ids"] for c in res.content["contributions"])


class TestChecker:
    def test_verdict_pass_with_limitations(self, ctx):
        coord = CoordinatorAgent()
        result = coord.run(ctx)
        by = {r["agent"]: r for r in result.content["agent_results"]}
        check = by["检查员 Agent"]["content"]
        assert check["verdict"] == "PASS WITH LIMITATIONS"
        assert all(c["status"] == "PASS" for c in check["checks"])
        assert "无法对8·26事件的具体发生时刻进行可靠提前预测" in check["limitation"]

    def test_disclaimer_present(self, ctx):
        coord = CoordinatorAgent()
        result = coord.run(ctx)
        by = {r["agent"]: r for r in result.content["agent_results"]}
        assert "不属于官方灾害预警" in by["预警员 Agent"]["content"]["disclaimer"]
