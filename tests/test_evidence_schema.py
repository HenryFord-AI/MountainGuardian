"""
MountainGuardian G02A – EvidenceItem schema tests (Layer 1 unit).

Covers: EvidenceItem structure, Case Pack conversion fidelity (evidence is
never invented), phase preservation, quality mapping, source provenance,
satellite scene conversion (pre-event authorized / post-event excluded),
and agent authorization mapping.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from schemas.evidence import (
    AGENT_GLACIER_GEOLOGY,
    AGENT_REMOTE_SENSING,
    AGENT_WEATHER_HYDROLOGY,
    CONTEXT_ONLY_PHASES,
    POST_EVENT_PHASES,
    PRE_EVENT_RISK_PHASES,
    EvidenceItem,
    EvidenceQuality,
    build_evidence_pool,
    evidence_from_case_field,
    satellite_evidence_items,
)
from tools.case_loader import load_case


@pytest.fixture(scope="module")
def case():
    return load_case()


@pytest.fixture(scope="module")
def pool(case):
    return build_evidence_pool(case)


class TestEvidenceItemSchema:
    def test_required_logical_fields_exist(self):
        item = EvidenceItem(
            evidence_id="X1", evidence_type="terrain",
            phase="pre_event_static", summary="测试", value=1, unit="m",
            source_name="n", source_organization="org",
            source_reference="S01", observation_time="2026-01-01",
            quality=EvidenceQuality.GOOD.value, raw_or_derived="raw",
            allowed_agents=(AGENT_GLACIER_GEOLOGY,), limitations="lim",
            media_ref="ref")
        for attr in ("evidence_id", "evidence_type", "phase", "summary",
                     "value", "unit", "source_name", "source_organization",
                     "source_reference", "observation_time", "quality",
                     "raw_or_derived", "allowed_agents", "limitations",
                     "media_ref"):
            assert hasattr(item, attr)
        d = item.to_dict()
        assert d["evidence_id"] == "X1"
        assert d["allowed_agents"] == [AGENT_GLACIER_GEOLOGY]

    def test_immutable_by_design(self):
        item = EvidenceItem(evidence_id="X2", evidence_type="t",
                            phase="pre_event_static", summary="s")
        with pytest.raises(Exception):
            item.phase = "post_event_validation"

    def test_phase_predicates(self):
        pre = EvidenceItem(evidence_id="p", evidence_type="t",
                           phase="pre_event_static", summary="s")
        post = EvidenceItem(evidence_id="q", evidence_type="t",
                            phase="post_event_validation", summary="s")
        assert pre.is_pre_event() and not pre.is_post_event()
        assert post.is_post_event() and not post.is_pre_event()

    def test_quality_enum_values(self):
        assert {q.value for q in EvidenceQuality} == \
            {"GOOD", "LIMITED", "STALE", "MISSING"}


class TestCasePackConversion:
    def test_pool_covers_every_case_field(self, case, pool):
        field_ids = {f["id"] for f in case["raw"]["data_fields"]}
        pool_ids = {i.evidence_id for i in pool}
        assert field_ids <= pool_ids, "every case field must map 1:1"

    def test_no_evidence_invented(self, case, pool):
        field_ids = {f["id"] for f in case["raw"]["data_fields"]}
        for item in pool:
            assert (item.evidence_id in field_ids
                    or item.evidence_id.startswith("EV-SAT-")), \
                f"unexpected invented evidence {item.evidence_id}"

    def test_phase_preserved_verbatim(self, case, pool):
        by_id = {i.evidence_id: i for i in pool}
        for f in case["raw"]["data_fields"]:
            assert by_id[f["id"]].phase == f["phase"]

    def test_post_event_fields_never_authorized(self, case, pool):
        by_id = {i.evidence_id: i for i in pool}
        post_ids = [f["id"] for f in case["raw"]["data_fields"]
                    if f["phase"] in POST_EVENT_PHASES]
        assert post_ids, "case pack must contain post-event fields"
        for pid in post_ids:
            assert by_id[pid].allowed_agents == (), \
                "post-event evidence must authorize no professional agent"

    def test_metadata_fields_never_authorized(self, case, pool):
        by_id = {i.evidence_id: i for i in pool}
        for f in case["raw"]["data_fields"]:
            if f["phase"] == "metadata":
                assert by_id[f["id"]].allowed_agents == ()

    def test_source_provenance_resolved(self, case, pool):
        by_id = {i.evidence_id: i for i in pool}
        item = by_id["C010"]  # a glacier source-zone field with S-source
        assert item.source_reference, "source ids must be parsed"
        assert item.source_organization or item.source_name

    def test_quality_mapped_from_confidence(self, case, pool):
        by_id = {i.evidence_id: i for i in pool}
        for f in case["raw"]["data_fields"]:
            q = by_id[f["id"]].quality
            assert q in {x.value for x in EvidenceQuality}
        # missing_input fields must be quality MISSING (explicit gap)
        miss = [i for i in pool if i.phase == "missing_input"]
        assert miss and all(
            m.quality == EvidenceQuality.MISSING.value for m in miss)

    def test_derived_flag_for_derived_phase(self, pool):
        derived = [i for i in pool
                   if i.phase == "derived_pre_event_static"]
        assert derived and all(
            d.raw_or_derived == "derived" for d in derived)

    def test_agent_authorization_mapping(self, pool):
        by_id = {i.evidence_id: i for i in pool}
        # glacier/geology evidence
        for key_id in ("C010", "C013", "C014"):
            assert AGENT_GLACIER_GEOLOGY in by_id[key_id].allowed_agents
        # weather context evidence
        weather = [i for i in pool
                   if i.evidence_type == "weather_context"]
        assert weather and all(
            AGENT_WEATHER_HYDROLOGY in i.allowed_agents for i in weather)
        # context_only (ENSO) → weather agent only, never glacier/RS
        ctx_only = [i for i in pool if i.phase in CONTEXT_ONLY_PHASES]
        assert ctx_only
        for i in ctx_only:
            assert i.allowed_agents in ((), (AGENT_WEATHER_HYDROLOGY,))

    def test_unknown_pre_event_key_is_conservative(self):
        item = evidence_from_case_field(
            {"id": "C999", "key": "some_unknown_key", "name_zh": "未知",
             "value": 1, "phase": "pre_event_static", "confidence": "高",
             "source_ids": "[]"})
        assert item.allowed_agents == (), \
            "unknown keys must not be auto-authorized to any agent"


class TestSatelliteEvidence:
    def test_pre_scene_authorized_for_remote_sensing(self, case):
        items = satellite_evidence_items(case["raw"]["satellite"])
        pre = [i for i in items if i.phase == "pre_event_evidence"]
        assert len(pre) == 1
        assert AGENT_REMOTE_SENSING in pre[0].allowed_agents
        assert pre[0].observation_time.startswith("2026-08-24")
        assert pre[0].media_ref

    def test_post_scene_excluded_from_all_agents(self, case):
        items = satellite_evidence_items(case["raw"]["satellite"])
        post = [i for i in items if i.phase == "post_event_validation"]
        assert len(post) == 1
        assert post[0].allowed_agents == ()

    def test_pool_contains_both_satellite_scenes(self, pool):
        sat = [i for i in pool if i.evidence_id.startswith("EV-SAT-")]
        phases = {i.phase for i in sat}
        assert "pre_event_evidence" in phases
        assert "post_event_validation" in phases

    def test_pre_event_phase_set_is_frozen(self):
        assert PRE_EVENT_RISK_PHASES == {
            "pre_event_static", "derived_pre_event_static",
            "pre_event_context", "pre_event_evidence"}
