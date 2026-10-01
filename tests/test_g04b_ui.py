"""G04B – Product Pages: Historical Replay / Risk Watch / Intelligence Center.

Structural discipline follows the G03A/G03B/G03C/G04A suites: boundaries are
enforced by reading source (AST / text) and by driving the real Streamlit
app through streamlit.testing.v1.AppTest — never by trusting comments.

Frozen rules verified here (doc 04/05, gate G04B):
  * Historical Replay separates PRE-EVENT / EVENT / POST-EVENT visibly and
    post-event evidence never appears among Stage-A inputs;
  * the deterministic Historical Replay index (91/100 HIGH) is CONSUMED from
    the backend engine result, labeled Baseline Susceptibility Index and
    always annotated "not event probability";
  * Risk Watch exposes ONE primary CTA wired to the existing G03C entry
    run_risk_scan("jilong_port"); repeated clicks are blocked while running;
  * Current Risk / 7-Day Outlook / Data Coverage / Scan Progress /
    What Changed / Historical Trend read persisted snapshots only — no
    fabricated trend, no invented comparison, honest degraded states;
  * Intelligence Center renders the frozen 3 → Synthesizer → Critic DAG,
    evidence provenance and audit/safety states; no secrets, no chain of
    thought, no control that can disable a safety guard;
  * the four approved visual reference assets are tracked in the repo.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from frontend import theme  # noqa: E402
from frontend.viewmodels import build_risk_watch_viewmodel  # noqa: E402
from riskwatch.snapshot_store import SnapshotStore  # noqa: E402

FRONTEND_DIR = REPO_ROOT / "frontend"
APP_ENTRY = REPO_ROOT / "mountainguardian_app.py"
ASSETS_DIR = REPO_ROOT / "docs" / "mountainguardian_v1" / "assets"

APPROVED_VISUAL_REFERENCES = (
    "ui_reference_overview_v1.0.png",
    "ui_reference_historical_replay_v1.0.png",
    "ui_reference_risk_watch_v1.0.png",
    "ui_reference_intelligence_center_v1.0.png",
)


def _page_source(name: str) -> str:
    return (FRONTEND_DIR / "pages" / name).read_text(encoding="utf-8")


def _body(at) -> str:
    return " ".join(str(m.value) for m in at.markdown)


@pytest.fixture(scope="module")
def at():
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(str(APP_ENTRY), default_timeout=120)
    app.run()
    return app


# ─── schema-shaped Risk Watch result payload (fixture only) ──────────────────

def _rw_payload(risk_index=89.54, outlook=82.0, *, fallback=False,
                status="COMPLETED"):
    return {
        "run_id": "rw-g04b-test",
        "region_id": "jilong_port",
        "current_risk_index": risk_index,
        "current_risk_level": "HIGH",
        "outlook_7d_index": outlook,
        "outlook_7d_level": "HIGH",
        "risk_direction": "STABLE",
        "agent_results": {
            "glacier_geology": {"output": {
                "status": "COMPLETED", "confidence": 0.74,
                "evidence_ids": ["RW-STATIC-TERRAIN", "RW-STATIC-CRYO"],
                "fallback_used": fallback, "skip_reason": None,
                "key_findings": ["static susceptibility high"],
                "missing_data": [], "limitations": ["no real-time sensors"],
            }, "audit": {"provider_status": "CONNECTED",
                         "model_id": "deepseek-flash", "latency_ms": 1200,
                         "quarantined_evidence_ids": []}},
            "weather_hydrology": {"output": {
                "status": "DEGRADED", "confidence": 0.35,
                "evidence_ids": ["RW-POINTS"],
                "fallback_used": fallback, "skip_reason": None,
                "key_findings": [], "missing_data": [], "limitations": [],
            }, "audit": {"provider_status": "CONNECTED",
                         "model_id": "deepseek-flash", "latency_ms": 900,
                         "quarantined_evidence_ids": []}},
            "remote_sensing": {"output": {
                "status": "SKIPPED", "confidence": 0.0, "evidence_ids": [],
                "fallback_used": False,
                "skip_reason": "SKIPPED_NO_USABLE_IMAGERY",
                "key_findings": [], "missing_data": [], "limitations": [],
            }, "audit": {"provider_status": "CONNECTED",
                         "model_id": "deepseek-flash", "latency_ms": 0,
                         "quarantined_evidence_ids": []}},
        },
        "ai_layer": {"status": "EXECUTED", "synthesis_status": "COMPLETED",
                     "critic_status": "PASS_WITH_LIMITATIONS"},
        "synthesis": {"output": {
            "evidence_ids": ["RW-STATIC-B", "RW-ENGINE-C"],
            "explanation_confidence": 0.65, "fallback_used": fallback,
            "evidence_coverage": 0.65, "summary": "deterministic summary",
            "limitations": ["synthesis limitation"],
        }, "audit": {"provider_status": "CONNECTED",
                    "model_id": "deepseek-flash", "latency_ms": 700}},
        "critic": {"verdict": {
            "review_result": "PASS_WITH_LIMITATIONS", "severity": "WARNING",
            "fallback_used": fallback,
            "scientific_limitations": ["no real-time source-zone sensors"],
            "required_corrections": [],
            "programmatic_check_status": {},
            "risk_index_before": risk_index, "risk_index_after": risk_index,
        }, "audit": {"provider_status": "CONNECTED",
                    "model_id": "deepseek-flash", "latency_ms": 600}},
        "data_quality": {
            "required_coverage": {"ok": 2, "total": 2, "failed": []},
            "optional_coverage": {
                "available": 0, "total": 4,
                "missing": ["satellite", "hydrology", "soil", "enso"],
            },
            "point_quality": {"port_zone": "FRESH", "source_zone": "FRESH"},
            "satellite_pipeline_available": False,
            "weather_status": "OK",
        },
        "optional_evidence_availability": [],
        "deterministic_result": {
            "display": {"C": round(risk_index, 2), "O7": round(outlook, 2)},
            "top_drivers": [
                {"label": "Huge vertical drop and narrow gorge",
                 "contribution_points_rounded": 19.45,
                 "driver_type": "STATIC"},
            ],
            "outlook_drivers": [
                {"label": "Forecast precipitation above local baseline",
                 "contribution_points_rounded": 8.4,
                 "driver_type": "DYNAMIC"},
            ],
            "what_changed": {
                "status": "NO_HISTORY",
                "note": "No previous eligible Risk Watch result exists.",
            },
        },
        "stage_trace": [
            ["CONFIG_LOADED", "2026-10-01T10:54:00"],
            ["NORMALIZED", "2026-10-01T10:54:05"],
            ["VALIDATED", "2026-10-01T10:54:06"],
            ["SNAPSHOT_SAVED", "2026-10-01T10:54:07"],
            ["AGENTS_COMPLETED", "2026-10-01T10:55:01"],
            ["SYNTHESIZED", "2026-10-01T10:55:08"],
            ["REVIEWED", "2026-10-01T10:55:12"],
            ["COMPLETED", "2026-10-01T10:55:12"],
        ],
        "limitations": ["test limitation"],
        "status": status,
    }


@pytest.fixture()
def store_factory(tmp_path):
    def _make() -> SnapshotStore:
        return SnapshotStore(tmp_path / "mg-g04b.db")
    return _make


def _insert(store, payload, created_at="2026-10-01T10:55:12+00:00",
            status="COMPLETED"):
    return store.insert_snapshot(
        run_id=payload["run_id"], region_id="jilong_port", status=status,
        payload=payload, created_at=created_at, scan_mode="LIVE",
    )


@pytest.fixture(scope="module")
def at_seeded(tmp_path_factory):
    """AppTest over a TEMP snapshot db with one persisted valid scan.

    Redirects MOUNTAINGUARDIAN_DB_PATH so the real runtime database is never
    touched by tests; the seeded state exercises the "real persisted data"
    rendering paths of Risk Watch and Intelligence Center.
    """
    import os

    db = tmp_path_factory.mktemp("mg-seeded") / "mountainguardian.db"
    store = SnapshotStore(db)
    _insert(store, _rw_payload())
    store.close()
    os.environ["MOUNTAINGUARDIAN_DB_PATH"] = str(db)
    try:
        from streamlit.testing.v1 import AppTest

        app = AppTest.from_file(str(APP_ENTRY), default_timeout=120)
        app.run()
        yield app
    finally:
        os.environ.pop("MOUNTAINGUARDIAN_DB_PATH", None)


# ═══ Approved visual reference pack is tracked (gate G04B entry rule) ════════

class TestVisualReferencePack:
    def test_four_approved_assets_present(self):
        for name in APPROVED_VISUAL_REFERENCES:
            assert (ASSETS_DIR / name).is_file(), name

    def test_global_visual_reference_present(self):
        assert (ASSETS_DIR / "ui_reference_geospatial_intelligence.png").is_file()


# ═══ Historical Replay ═══════════════════════════════════════════════════════

class TestHistoricalReplay:
    @pytest.fixture()
    def page(self, at):
        at.sidebar.radio[0].set_value("历史验证 · Historical Replay").run()
        return at

    def test_page_renders_without_exception(self, page):
        assert not page.exception, [e.value for e in page.exception]

    def test_stage_separation_visible(self, page):
        body = _body(page)
        assert "PRE-EVENT" in body
        assert "EVENT" in body
        assert "POST-EVENT" in body
        assert "Post-event Validation" in body

    def test_baseline_susceptibility_not_probability(self, page):
        body = _body(page)
        assert "Baseline Susceptibility Index" in body
        assert "Not event probability" in body or "not event probability" in body
        assert "91" in body
        # forbidden probability / prediction marketing language never appears
        for banned in ("91%", "发生概率 91", "prediction accuracy",
                       "AI 成功预测", "successfully predicted"):
            assert banned not in body

    def test_critic_result_renders(self, page):
        body = _body(page)
        assert "PASS WITH LIMITATIONS" in body or "PASS_WITH_LIMITATIONS" in body

    def test_post_event_evidence_not_in_stage_a_panel(self, page):
        body = _body(page)
        head, _, validation = body.partition("Post-event Validation")
        assert validation, "validation section missing"
        assert "EV-SAT-POST" not in head
        assert "EV-SAT-POST" in validation

    def test_pre_event_evidence_panel_carries_pre_event_phase(self, page):
        body = _body(page)
        head, _, _ = body.partition("Post-event Validation")
        assert "PRE-EVENT" in head

    def test_no_chain_of_thought_or_prompts(self, page):
        body = _body(page).lower()
        for banned in ("chain of thought", "chain-of-thought",
                       "system prompt", "hidden reasoning"):
            assert banned not in body or "不展示" in _body(page)

    def test_viewmodel_consumes_engine_index_verbatim(self):
        from frontend.replay_viewmodels import build_historical_replay_viewmodel
        from orchestration.risk_engine import compute_historical_risk

        vm = build_historical_replay_viewmodel()
        risk = compute_historical_risk()
        assert vm.risk_index == risk.risk_index == 91.0
        assert vm.risk_level == "HIGH"
        assert vm.semantics == risk.semantics

    def test_viewmodel_stage_separation_structural(self):
        from frontend.replay_viewmodels import build_historical_replay_viewmodel

        vm = build_historical_replay_viewmodel()
        pre_ids = {e.evidence_id for e in vm.pre_event_evidence}
        post_ids = {e.evidence_id for e in vm.post_event_evidence}
        assert pre_ids and post_ids
        assert not (pre_ids & post_ids)
        assert all(e.phase == "PRE-EVENT" for e in vm.pre_event_evidence)
        assert all(e.phase == "POST-EVENT" for e in vm.post_event_evidence)
        # Stage B attestation: Stage A untouched, no alignment score invented
        assert vm.stage_a_unchanged is True
        assert vm.stage_b_findings


# ═══ Risk Watch ══════════════════════════════════════════════════════════════

class TestRiskWatch:
    @pytest.fixture()
    def page(self, at):
        at.sidebar.radio[0].set_value("风险监测 · Risk Watch").run()
        return at

    def test_page_renders_without_exception(self, page):
        assert not page.exception, [e.value for e in page.exception]

    def test_single_primary_cta_exists(self, page):
        labels = [b.label for b in page.button]
        cta = [x for x in labels if "Run Risk Scan" in x]
        assert cta, labels

    def test_cta_repeated_click_blocked_while_running(self, at):
        at.session_state["mg_rw_running"] = True
        at.run()
        try:
            cta = [b for b in at.button if "Run Risk Scan" in b.label
                   or "Running" in b.label]
            assert cta and all(b.disabled for b in cta)
        finally:
            at.session_state["mg_rw_running"] = False
            at.run()

    def test_cta_source_uses_existing_orchestration_entry(self):
        src = _page_source("risk_watch.py")
        assert "from orchestration.risk_watch_orchestrator import run_risk_scan" \
            in src
        tree = ast.parse(src)
        calls = [
            node.func.id for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == "run_risk_scan"
        ]
        assert calls == ["run_risk_scan"]

    def test_empty_store_shows_honest_empty_states(self, tmp_path):
        """Hermetic: pins an empty temp db — ambient runtime state (e.g. a
        previous gate's gitignored snapshots) must not affect this check."""
        import os

        from streamlit.testing.v1 import AppTest

        db = tmp_path / "empty-runtime.db"
        os.environ["MOUNTAINGUARDIAN_DB_PATH"] = str(db)
        try:
            app = AppTest.from_file(str(APP_ENTRY), default_timeout=120)
            app.run()
            app.sidebar.radio[0].set_value("风险监测 · Risk Watch").run()
            assert not app.exception, [e.value for e in app.exception]
            body = _body(app)
        finally:
            os.environ.pop("MOUNTAINGUARDIAN_DB_PATH", None)
        assert "尚无风险扫描结果" in body or "No scan has run yet" in body
        assert "历史数据不足" in body

    def test_viewmodel_reads_stored_values_verbatim(self, store_factory):
        store = store_factory()
        try:
            _insert(store, _rw_payload())
            vm = build_risk_watch_viewmodel(store=store)
        finally:
            store.close()
        assert vm.has_result is True
        assert vm.risk_index_rounded == 89.54
        assert vm.risk_level == "HIGH"
        assert vm.outlook_index_rounded == 82.0
        assert vm.outlook_level == "HIGH"
        assert vm.last_scan_status == "COMPLETED"
        assert vm.run_id == "rw-g04b-test"

    def test_scan_steps_from_persisted_trace_only(self, store_factory):
        store = store_factory()
        try:
            _insert(store, _rw_payload())
            vm = build_risk_watch_viewmodel(store=store)
        finally:
            store.close()
        done = [s.num for s in vm.scan_steps if s.state == "DONE"]
        assert done == [1, 2, 3, 4, 5, 6]
        assert vm.scan_steps[2].ts == "10:54:07"
        assert vm.scan_duration_s == pytest.approx(72.0, abs=0.5)

    def test_first_snapshot_what_changed_is_honest_empty(self, store_factory):
        store = store_factory()
        try:
            _insert(store, _rw_payload())
            vm = build_risk_watch_viewmodel(store=store)
        finally:
            store.close()
        assert vm.what_changed_status == "NO_HISTORY"

    def test_first_snapshot_trend_empty_state(self, store_factory):
        store = store_factory()
        try:
            _insert(store, _rw_payload())
            vm = build_risk_watch_viewmodel(store=store)
        finally:
            store.close()
        assert len(vm.trend_points) == 1
        assert vm.trend_status in ("NO_HISTORY", "INSUFFICIENT_HISTORY")

    def test_no_fabricated_trend_points(self, store_factory):
        store = store_factory()
        try:
            _insert(store, _rw_payload())
            _insert(store, _rw_payload(), created_at="2026-10-02T10:00:00+00:00")
            stored = store.count()
            vm = build_risk_watch_viewmodel(store=store)
        finally:
            store.close()
        # exactly the persisted valid snapshots — nothing interpolated
        assert stored == 2
        assert len(vm.trend_points) == stored

    def test_degraded_state_disclosed(self, store_factory):
        store = store_factory()
        try:
            _insert(store, _rw_payload(fallback=True),
                    status="COMPLETED_WITH_LIMITATIONS")
            vm = build_risk_watch_viewmodel(store=store)
        finally:
            store.close()
        assert vm.fallback_mode is True
        assert vm.model_runtime == "FALLBACK"
        assert vm.system_state == "DEGRADED"
        assert vm.last_scan_status == "COMPLETED_WITH_LIMITATIONS"

    def test_optional_missing_never_fails_scan(self, store_factory):
        store = store_factory()
        try:
            _insert(store, _rw_payload())
            vm = build_risk_watch_viewmodel(store=store)
        finally:
            store.close()
        optional = [r for r in vm.source_rows if not r.required]
        assert optional
        assert all(r.status == "MISSING" for r in optional)
        assert vm.last_scan_status == "COMPLETED"


class TestRiskWatchSeeded:
    """Risk Watch rendering over one real persisted snapshot."""

    @pytest.fixture()
    def page(self, at_seeded):
        at_seeded.sidebar.radio[0].set_value("风险监测 · Risk Watch").run()
        return at_seeded

    def test_current_risk_renders_stored_value(self, page):
        assert not page.exception, [e.value for e in page.exception]
        body = _body(page)
        assert "Current Risk" in body
        assert "89.5" in body
        assert "HIGH" in body
        assert "not event probability" in body or "Not event probability" in body

    def test_outlook_renders_stored_value(self, page):
        body = _body(page)
        assert "7-Day Outlook" in body
        assert "82" in body
        assert "Outlook Index — not event probability" in body

    def test_coverage_and_scan_state_render(self, page):
        body = _body(page)
        assert "Data Coverage" in body
        assert "Scan Progress" in body
        assert "COMPLETED" in body
        assert "rw-g04b-test" in body

    def test_what_changed_honest_empty_with_single_snapshot(self, page):
        body = _body(page)
        assert "暂无历史比较基线" in body

    def test_trend_honest_single_point_state(self, page):
        body = _body(page)
        assert "历史数据不足" in body


# ═══ Intelligence Center ═════════════════════════════════════════════════════

class TestIntelligenceCenter:
    @pytest.fixture()
    def page(self, at_seeded):
        at_seeded.sidebar.radio[0].set_value("智能中心 · Intelligence Center").run()
        return at_seeded

    def test_three_tabs_exist(self, page):
        assert not page.exception, [e.value for e in page.exception]
        labels = " | ".join(str(getattr(t, "label", "")) for t in page.tabs)
        for label in ("Agent Workspace", "Evidence Center", "Audit & Safety"):
            assert label in labels, labels

    def test_agent_workspace_shows_frozen_dag(self, page):
        body = _body(page)
        # "&" is HTML-escaped in rendered markup
        for name in ("Glacier &amp; Geology Agent",
                     "Weather &amp; Hydrology Agent",
                     "Remote Sensing Agent", "Risk Synthesizer",
                     "Critic · Reviewer"):
            assert name in body, name

    def test_evidence_center_renders_provenance(self, page):
        body = _body(page)
        # real Case Pack evidence ids with phase + quality metadata
        assert "EV-" in body
        assert "POST-EVENT" in body or "POST EVENT" in body

    def test_audit_safety_renders_safety_state(self, page):
        body = _body(page)
        for control in ("Prompt Injection Guard", "Data Leakage Guard",
                        "Post-event Leakage Guard", "Output Schema Validation",
                        "External Actions Disabled"):
            assert control in body

    def test_no_secrets_rendered(self, page):
        body = _body(page)
        for banned in ("DEEPSEEK_API_KEY", "sk-", "api_key=", "Bearer "):
            assert banned not in body

    def test_no_chain_of_thought_rendered(self, page):
        body = _body(page).lower()
        assert "chain of thought:" not in body
        assert "system prompt:" not in body

    def test_no_control_can_disable_safety_guards(self, page):
        # no checkbox / toggle / radio that could flip a guard exists
        assert len(page.checkbox) == 0
        assert len(page.toggle) == 0
        src = _page_source("intelligence_center.py")
        for forbidden in ("st.checkbox", "st.toggle", "st.switch"):
            assert forbidden not in src

    def test_viewmodel_safety_rows_from_real_run_signals(self, store_factory):
        from frontend.intel_viewmodels import build_intelligence_viewmodel

        store = store_factory()
        try:
            _insert(store, _rw_payload())
            vm = build_intelligence_viewmodel(store=store)
        finally:
            store.close()
        names = [r[0] for r in vm.safety_rows]
        assert names == [
            "Prompt Injection Guard", "Data Leakage Guard",
            "Post-event Leakage Guard", "Output Schema Validation",
            "External Actions Disabled",
        ]
        assert vm.has_run is True
        assert vm.audit_rows
        assert vm.evidence_categories


# ═══ Overview regression (G04A) ══════════════════════════════════════════════

class TestOverviewRegression:
    def test_overview_still_default_and_functional(self, at):
        at.sidebar.radio[0].set_value("总览 · Overview").run()
        assert not at.exception, [e.value for e in at.exception]
        body = _body(at)
        assert "Main Map" in body
        assert "Current Risk" in body
        assert "Agent Collaboration" in body


# ═══ Shared design-system consistency across the four pages ═════════════════

class TestDesignConsistency:
    def test_pages_reuse_global_components_not_page_css(self):
        for name in ("historical_replay.py", "risk_watch.py",
                     "intelligence_center.py"):
            src = _page_source(name)
            assert "st.markdown(f\"<style>" not in src
            assert "<style>" not in src

    def test_risk_note_constant_shared(self):
        from frontend.components import RISK_INDEX_NOTE

        assert RISK_INDEX_NOTE == "Risk Index — not event probability"
        assert theme.risk_color("HIGH") == theme.RED
        assert theme.agent_status_color("SKIPPED") != theme.RED
