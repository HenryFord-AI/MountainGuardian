"""
MountainGuardian G02A – AnalysisContext tests (Layer 1/2).

Covers: context construction, run identity, programmatic phase filtering
(post-event evidence physically excluded), minimum-necessary-context per
agent, context_only isolation, explicit missing-data representation, and
frozen scientific constraints.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from orchestration.context_builder import (
    MODE_HISTORICAL_REPLAY,
    MODE_RISK_WATCH,
    AnalysisContext,
    PhaseSafetyError,
    agent_evidence_view,
    build_analysis_context,
)
from schemas.evidence import (
    AGENT_GLACIER_GEOLOGY,
    AGENT_REMOTE_SENSING,
    AGENT_WEATHER_HYDROLOGY,
    POST_EVENT_PHASES,
    PRE_EVENT_RISK_PHASES,
    EvidenceItem,
)
from tools.case_loader import load_case


@pytest.fixture(scope="module")
def ctx():
    return build_analysis_context()


def _post_event_ids():
    case = load_case()
    return {f["id"] for f in case["raw"]["data_fields"]
            if f["phase"] in POST_EVENT_PHASES}


class TestConstruction:
    def test_run_id_unique_per_context(self):
        a = build_analysis_context()
        b = build_analysis_context()
        assert a.run_id and b.run_id and a.run_id != b.run_id

    def test_explicit_run_id_threaded(self):
        ctx = build_analysis_context(run_id="run-test-1")
        assert ctx.run_id == "run-test-1"

    def test_mode_and_region(self, ctx):
        assert ctx.mode == MODE_HISTORICAL_REPLAY
        assert ctx.region_id.upper() == "JILONG_20260826"
        assert ctx.case_metadata["case_name"]
        assert ctx.case_metadata["event_date"] == "2026-08-26"

    def test_risk_watch_mode_not_in_scope(self):
        with pytest.raises(NotImplementedError):
            build_analysis_context(mode=MODE_RISK_WATCH)
        with pytest.raises(ValueError):
            build_analysis_context(mode="unknown_mode")

    def test_context_self_check_passes(self, ctx):
        ctx.assert_no_post_event()  # must not raise


class TestProgrammaticPhaseFiltering:
    def test_no_post_event_evidence_in_context(self, ctx):
        banned = _post_event_ids()
        all_ids = set(ctx.evidence_by_id())
        assert not (all_ids & banned), \
            "post-event evidence must never enter the AnalysisContext"
        for item in ctx.evidence_by_id().values():
            assert item.phase not in POST_EVENT_PHASES

    def test_allowed_evidence_is_pre_event_only(self, ctx):
        assert ctx.allowed_evidence
        for item in ctx.allowed_evidence:
            assert item.phase in PRE_EVENT_RISK_PHASES

    def test_post_event_satellite_scene_excluded(self, ctx):
        ids = set(ctx.evidence_by_id())
        assert not any(i.startswith("EV-SAT-POST") for i in ids)
        assert any(i.startswith("EV-SAT-PRE") for i in ids)

    def test_tampered_context_raises_on_view(self, ctx):
        """Even if a caller tampers with the context, the per-agent view
        builder must refuse post-event evidence (defense in depth)."""
        trojan = EvidenceItem(
            evidence_id="C-TROJAN", evidence_type="terrain",
            phase="post_event_validation", summary="tampered",
            allowed_agents=(AGENT_GLACIER_GEOLOGY,))
        tampered = AnalysisContext(
            run_id=ctx.run_id, mode=ctx.mode, region_id=ctx.region_id,
            analysis_time=ctx.analysis_time,
            case_metadata=ctx.case_metadata,
            allowed_evidence=list(ctx.allowed_evidence) + [trojan],
            context_only_evidence=list(ctx.context_only_evidence),
            missing_sources=list(ctx.missing_sources),
            scientific_constraints=list(ctx.scientific_constraints),
            pre_event_imagery=list(ctx.pre_event_imagery))
        with pytest.raises(PhaseSafetyError):
            agent_evidence_view(tampered, AGENT_GLACIER_GEOLOGY)


class TestMinimumNecessaryContext:
    def test_views_are_smaller_than_full_pool(self, ctx):
        from schemas.evidence import build_evidence_pool
        from tools.case_loader import load_case
        pool_size = len(build_evidence_pool(load_case()))
        for agent in (AGENT_GLACIER_GEOLOGY, AGENT_WEATHER_HYDROLOGY,
                      AGENT_REMOTE_SENSING):
            view = agent_evidence_view(ctx, agent)
            assert 0 < len(view.all_items()) < pool_size

    def test_glacier_view_has_no_weather_or_climate_evidence(self, ctx):
        view = agent_evidence_view(ctx, AGENT_GLACIER_GEOLOGY)
        types = {i.evidence_type for i in view.evidence}
        assert "weather_context" not in types
        assert "climate_context" not in types
        assert view.background_evidence == []

    def test_weather_view_has_no_geology_specifics(self, ctx):
        view = agent_evidence_view(ctx, AGENT_WEATHER_HYDROLOGY)
        types = {i.evidence_type for i in view.evidence}
        assert "cryosphere" not in types
        assert "terrain" not in types
        assert "loose_material" not in types

    def test_context_only_goes_to_weather_agent_only(self, ctx):
        w = agent_evidence_view(ctx, AGENT_WEATHER_HYDROLOGY)
        g = agent_evidence_view(ctx, AGENT_GLACIER_GEOLOGY)
        r = agent_evidence_view(ctx, AGENT_REMOTE_SENSING)
        assert w.background_evidence, "ENSO background belongs to weather"
        for i in w.background_evidence:
            assert i.is_context_only()
        assert all(not i.is_context_only() for i in g.all_items())
        assert all(not i.is_context_only() for i in r.all_items())

    def test_imagery_only_in_remote_sensing_view(self, ctx):
        r = agent_evidence_view(ctx, AGENT_REMOTE_SENSING)
        g = agent_evidence_view(ctx, AGENT_GLACIER_GEOLOGY)
        assert r.pre_event_imagery and len(r.pre_event_imagery) == 1
        assert g.pre_event_imagery == []

    def test_unknown_agent_rejected(self, ctx):
        with pytest.raises(ValueError):
            agent_evidence_view(ctx, "risk_synthesizer")


class TestMissingDataAndConstraints:
    def test_missing_sources_explicit(self, ctx):
        assert ctx.missing_sources, \
            "missing data must be represented explicitly, never hidden"
        keys = " ".join(m.summary for m in ctx.missing_sources)
        assert "传感" in keys or "监测" in keys

    def test_missing_sources_reach_every_agent_view(self, ctx):
        for agent in (AGENT_GLACIER_GEOLOGY, AGENT_WEATHER_HYDROLOGY,
                      AGENT_REMOTE_SENSING):
            view = agent_evidence_view(ctx, agent)
            assert view.missing_sources

    def test_scientific_constraints_frozen(self, ctx):
        joined = " ".join(ctx.scientific_constraints)
        assert "不是灾害发生概率" in joined
        assert "不得补造缺失数据" in joined
        assert "ENSO" in joined
        assert "post-event" in joined or "灾后" in joined

    def test_case_pack_boundaries_included_as_constraints(self, ctx):
        joined = " ".join(ctx.scientific_constraints)
        # enso_direct_causality (C043) and case_use_boundary (C044) values
        assert "因果" in joined
        assert "演示" in joined or "预警" in joined
