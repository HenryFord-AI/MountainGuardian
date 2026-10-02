"""G04A – UI Foundation: theme, view models, components, isolation, smoke.

Structural discipline follows the G03A/G03B/G03C suites: boundaries are
enforced by reading source (AST / text), not by trusting comments.

Frozen rules verified here (doc 05, doc 06 §71–§75):
  * design tokens match the frozen UI spec colors;
  * risk vocabulary LOW/MODERATE/ELEVATED/HIGH only; SKIPPED ≠ FAILED;
  * 风险指数不是事件发生概率 (G05C disclaimer) is always rendered;
  * the UI layer never computes risk, never imports providers / agents /
    database / security, never writes snapshots;
  * G04B refinement: two narrow consume points are sanctioned (the Risk
    Watch CTA → G03C orchestration entry; the replay/intel view models →
    Case Pack loader + evidence schemas + deterministic replay engine);
    see ALLOWED_BACKEND_IMPORTS below;
  * view models read region.json + snapshot store only (read-only);
  * no fabricated data: missing results surface as explicit empty states;
  * the Streamlit app boots and the frozen 4-entry navigation renders.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

import sys

sys.path.insert(0, str(REPO_ROOT))

from frontend import components, theme  # noqa: E402
from frontend.viewmodels import build_overview_viewmodel  # noqa: E402
from riskwatch.region import load_region  # noqa: E402
from riskwatch.snapshot_store import SnapshotStore  # noqa: E402

FRONTEND_DIR = REPO_ROOT / "frontend"
APP_ENTRY = REPO_ROOT / "mountainguardian_app.py"

UI_SOURCES = sorted(
    p for p in FRONTEND_DIR.rglob("*.py") if "__pycache__" not in p.parts
) + [APP_ENTRY]


def _ui_source_text() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in UI_SOURCES)


def _trees():
    for path in UI_SOURCES:
        yield path, ast.parse(path.read_text(encoding="utf-8"))


# ─── Minimal, schema-shaped snapshot payload fixture ─────────────────────────
# Mirrors the real G03C result-snapshot payload keys. Test fixture only —
# the UI itself never sees synthetic data.

def _payload(risk_index=89.542496, risk_level="HIGH", *, fallback=False):
    return {
        "run_id": "rw-test",
        "region_id": "jilong_port",
        "current_risk_index": risk_index,
        "current_risk_level": risk_level,
        "agent_results": {
            "glacier_geology": {"output": {
                "status": "COMPLETED", "confidence": 0.74,
                "evidence_ids": ["RW-STATIC-TERRAIN", "RW-STATIC-CRYO"],
                "fallback_used": False, "skip_reason": None,
            }, "audit": {"provider_status": "CONNECTED"}},
            "weather_hydrology": {"output": {
                "status": "DEGRADED", "confidence": 0.35,
                "evidence_ids": ["RW-POINTS"],
                "fallback_used": False, "skip_reason": None,
            }, "audit": {"provider_status": "CONNECTED"}},
            "remote_sensing": {"output": {
                "status": "SKIPPED", "confidence": 0.0, "evidence_ids": [],
                "fallback_used": False, "skip_reason": "SKIPPED_NO_USABLE_IMAGERY",
            }, "audit": {"provider_status": "CONNECTED"}},
        },
        "ai_layer": {
            "status": "EXECUTED",
            "synthesis_status": "COMPLETED",
            "critic_status": "NEEDS_REVISION",
            "agent_status_summary": {
                "glacier_geology": "COMPLETED",
                "weather_hydrology": "DEGRADED",
                "remote_sensing": "SKIPPED",
            },
        },
        "synthesis": {
            "output": {
                "evidence_ids": ["RW-STATIC-B", "RW-ENGINE-C"],
                "explanation_confidence": 0.65,
                "fallback_used": fallback,
                "evidence_coverage": 0.65,
            },
            "audit": {"provider_status": "CONNECTED"},
        },
        "critic": {
            "verdict": {
                "review_result": "NEEDS_REVISION", "severity": "WARNING",
                "fallback_used": False,
            },
            "audit": {"provider_status": "CONNECTED"},
        },
        "data_quality": {
            "required_coverage": {"ok": 2, "total": 2, "failed": []},
            "optional_coverage": {
                "available": 0, "total": 4,
                "missing": ["satellite", "hydrology", "ensO", "in_situ"],
            },
            "point_quality": {"port_zone": "FRESH", "source_zone": "FRESH"},
            "satellite_pipeline_available": False,
            "weather_status": "OK",
        },
        "deterministic_result": {
            "display": {"C": round(risk_index, 2)},
            "top_drivers": [
                {"label": "Huge vertical drop and narrow gorge",
                 "contribution_points_rounded": 19.45, "driver_type": "STATIC"},
            ],
        },
        "limitations": ["test limitation"],
    }


@pytest.fixture()
def store_factory(tmp_path):
    def _make() -> SnapshotStore:
        return SnapshotStore(tmp_path / "mg-test.db")
    return _make


# ═══ Theme tokens match the frozen spec (doc 05 §39–§40, §12, §14) ══════════

class TestThemeTokens:
    def test_background_and_panel_colors(self):
        assert theme.BG == "#07111F"
        assert theme.PANEL == "#101C2D"
        assert theme.PANEL_ALT == "#142338"

    def test_accent_colors(self):
        assert theme.CYAN == "#37D7E8"
        assert theme.PURPLE == "#8B7CFF"
        assert theme.GREEN == "#42D392"
        assert theme.ORANGE == "#FFB454"
        assert theme.RED == "#FF5E6C"
        assert theme.TEXT == "#DCE7F3"
        assert theme.TEXT_DIM == "#8799AD"

    def test_risk_vocabulary_is_frozen(self):
        assert set(theme.RISK_LEVEL_COLORS) == {
            "LOW", "MODERATE", "ELEVATED", "HIGH"
        }

    def test_risk_semantic_colors(self):
        assert theme.risk_color("LOW") == theme.GREEN
        assert theme.risk_color("ELEVATED") == theme.ORANGE
        assert theme.risk_color("HIGH") == theme.RED

    def test_skipped_never_looks_like_failed(self):
        assert (
            theme.AGENT_STATUS_COLORS["SKIPPED"]
            != theme.AGENT_STATUS_COLORS["FAILED"]
        )
        assert theme.AGENT_STATUS_COLORS["FAILED"] == theme.RED
        assert theme.AGENT_STATUS_COLORS["COMPLETED"] == theme.GREEN

    def test_css_uses_frozen_background(self):
        css = theme._CSS
        assert theme.BG in css
        assert "mg-panel" in css and "mg-chip" in css and "mg-header" in css


# ═══ Components: scientific language guard (doc 05 §11, §62–§63) ═════════════

class TestComponents:
    def test_risk_card_always_annotates_not_probability(self):
        html = components.risk_card_html(89.54, "HIGH")
        assert "风险指数不是事件发生概率" in html
        assert "89.54" in html and "高" in html

    def test_risk_card_empty_state_when_no_result(self):
        html = components.risk_card_html(None, None)
        assert "事件发生概率" not in html
        assert "尚无风险扫描结果" in html

    def test_trend_line_no_history_is_honest(self):
        html = components.trend_line("NO_HISTORY", None)
        assert "暂无历史扫描可比较" in html

    def test_agent_card_shows_only_frozen_fields(self):
        from frontend.viewmodels import AgentCardVM
        card = AgentCardVM(
            key="glacier_geology", name_en="Glacier & Geology Agent",
            name_zh="冰川地质智能体", status="COMPLETED", confidence=0.74,
            evidence_count=9, evidence_ids=tuple(["E%d" % i for i in range(9)]),
        )
        html = components.agent_card_html(card)
        assert "0.74" in html and "9 条证据" in html
        assert "已完成" in html
        # G05C: the visible agent label is Chinese — the English display
        # name must not appear as the primary visible label
        assert "冰川地质智能体" in html
        assert "Glacier" not in html
        # never renders reasoning / prompts
        assert "prompt" not in html.lower()

    def test_sources_contain_no_forbidden_phrases(self):
        text = _ui_source_text()
        for phrase in ("预警", "成功预测", "精准预测",
                       "AI prediction confirmed", "official warning"):
            assert phrase not in text, phrase

    def test_probability_only_in_negated_disclaimer(self):
        """G05C: the frozen disclaimer wording 风险指数不是事件发生概率
        requires the term 发生概率 — it may ONLY appear negated (不是…).
        Percentage-probability claims stay forbidden (doc 05 §62)."""
        text = _ui_source_text()
        for m in re.finditer("发生概率", text):
            ctx = text[max(0, m.start() - 8):m.start()]
            assert "不是" in ctx or "非" in ctx, \
                text[max(0, m.start() - 20):m.end() + 10]
        assert "风险指数不是事件发生概率" in text
        assert not re.search(r"\d+(\.\d+)?\s*%[^。\n]{0,8}概率", text)


# ═══ View models: read-only assembly, no fabrication ═════════════════════════

class TestOverviewViewModel:
    def test_empty_store_yields_explicit_empty_state(self, store_factory):
        store = store_factory()
        vm = build_overview_viewmodel(store=store)
        assert vm.has_result is False
        assert vm.risk_index_rounded is None
        assert vm.agents == ()
        assert vm.trend_status == "NO_HISTORY"
        assert vm.system_state == "NO DATA"
        store.close()

    def test_data_only_snapshot_never_becomes_a_result(self, store_factory):
        store = store_factory()
        store.insert_snapshot(
            run_id="r1", region_id="jilong_port", status="DATA_OK",
            payload={"note": "data-only"},
        )
        vm = build_overview_viewmodel(store=store)
        assert vm.has_result is False
        store.close()

    def test_reads_stored_engine_values_verbatim(self, store_factory):
        store = store_factory()
        store.insert_snapshot(
            run_id="r1", region_id="jilong_port",
            status="COMPLETED_WITH_LIMITATIONS", payload=_payload(),
        )
        vm = build_overview_viewmodel(store=store)
        assert vm.has_result is True
        # display rounding of the STORED value — never a recomputation
        assert vm.risk_index_rounded == 89.54
        assert vm.risk_level == "HIGH"
        assert vm.last_scan_status == "COMPLETED_WITH_LIMITATIONS"
        assert vm.system_state == "DEGRADED"
        store.close()

    def test_invalidated_snapshot_is_ignored(self, store_factory):
        store = store_factory()
        store.insert_snapshot(
            run_id="r1", region_id="jilong_port", status="COMPLETED",
            payload=_payload(risk_index=50.0, risk_level="MODERATE"),
        )
        sid = store.insert_snapshot(
            run_id="r2", region_id="jilong_port", status="COMPLETED",
            payload=_payload(risk_index=60.0, risk_level="ELEVATED"),
        )
        store.mark_invalid(sid, "test correction")
        vm = build_overview_viewmodel(store=store)
        assert vm.risk_index_rounded == 50.0
        assert vm.risk_level == "MODERATE"
        store.close()

    def test_latest_valid_result_wins_and_trend_delta_from_engine(self, store_factory):
        store = store_factory()
        store.insert_snapshot(
            run_id="r1", region_id="jilong_port", status="COMPLETED",
            payload=_payload(risk_index=50.0, risk_level="MODERATE"),
        )
        store.insert_snapshot(
            run_id="r2", region_id="jilong_port", status="COMPLETED",
            payload=_payload(risk_index=60.0, risk_level="ELEVATED"),
        )
        vm = build_overview_viewmodel(store=store)
        assert vm.risk_index_rounded == 60.0
        assert vm.risk_direction == "RISING"
        assert vm.trend_delta == 10.0
        assert len(vm.trend_points) == 2
        store.close()

    def test_agent_cards_reflect_stored_statuses(self, store_factory):
        store = store_factory()
        store.insert_snapshot(
            run_id="r1", region_id="jilong_port",
            status="COMPLETED_WITH_LIMITATIONS", payload=_payload(),
        )
        vm = build_overview_viewmodel(store=store)
        by_key = {a.key: a for a in vm.agents}
        assert set(by_key) == {
            "glacier_geology", "weather_hydrology", "remote_sensing",
            "synthesizer", "critic",
        }
        assert by_key["glacier_geology"].status == "COMPLETED"
        assert by_key["glacier_geology"].confidence == 0.74
        assert by_key["glacier_geology"].evidence_count == 2
        assert by_key["weather_hydrology"].status == "DEGRADED"
        assert by_key["remote_sensing"].status == "SKIPPED"
        assert by_key["remote_sensing"].extra == "已跳过：无可用影像"
        assert by_key["synthesizer"].is_ai_layer is True
        assert by_key["synthesizer"].confidence == 0.65
        assert by_key["critic"].status == "NEEDS_REVISION"
        # 3 professional COMPLETED/DEGRADED + synthesizer + critic verdict
        assert vm.agents_executed == 4 and vm.agents_total == 5
        store.close()

    def test_fallback_mode_is_surfaced_never_disguised(self, store_factory):
        store = store_factory()
        store.insert_snapshot(
            run_id="r1", region_id="jilong_port", status="COMPLETED",
            payload=_payload(fallback=True),
        )
        vm = build_overview_viewmodel(store=store)
        assert vm.fallback_mode is True
        assert vm.model_runtime == "FALLBACK"
        store.close()

    def test_viewmodel_never_writes_to_store(self, store_factory):
        store = store_factory()
        store.insert_snapshot(
            run_id="r1", region_id="jilong_port", status="COMPLETED",
            payload=_payload(),
        )
        before = store.count()
        build_overview_viewmodel(store=store)
        build_overview_viewmodel(store=store)
        assert store.count() == before
        store.close()

    def test_real_region_config_two_documented_points(self, store_factory):
        store = store_factory()
        region = load_region("jilong_port")
        vm = build_overview_viewmodel(region=region, store=store)
        assert vm.region_id == "jilong_port"
        ids = [p[0] for p in vm.monitoring_points]
        assert ids == ["source_zone", "port_zone"]
        for row, point in zip(vm.monitoring_points, region.monitoring_points):
            assert row[2] == point.latitude and row[3] == point.longitude
        assert vm.data_source_count == len(region.data["source_references"])
        store.close()


# ═══ Map: existing data only, schematic honesty ══════════════════════════════

class TestMapView:
    def test_no_points_no_map(self):
        from frontend.map_view import build_overview_map
        assert build_overview_map([]) is None

    def test_map_html_from_real_region_points(self):
        from frontend.map_view import build_overview_map
        region = load_region("jilong_port")
        pts = tuple(
            (p.point_id, p.name, p.latitude, p.longitude, p.elevation_m,
             (p.coordinate_provenance or {}).get("uncertainty_km"))
            for p in region.monitoring_points
        )
        html = build_overview_map(pts)
        assert html is not None
        assert "leaflet" in html.lower()
        assert "Esri" in html
        # schematic connector must disclose that it is schematic (G05C Chinese)
        assert "示意图" in html
        assert "非实测几何" in html
        # 2D only — no 3D / terrain exaggeration libraries
        assert "Cesium" not in html and "three.js" not in html.lower()


# ═══ Structural isolation (same discipline as G03A/B/C suites) ═══════════════
#
# G04B refinement (gate G04B §10.1 / §9.2, documented — Overview rules unchanged):
# the UI layer still never imports providers / agents / database / security /
# network stacks anywhere. Two NARROW read/consume exceptions exist because the
# frozen product pages must wire existing backend entries instead of
# reimplementing them:
#   * frontend/pages/risk_watch.py may import the single G03C orchestration
#     entry (run_risk_scan) for the one sanctioned CTA;
#   * the two G04B read-only view-model modules may consume the frozen
#     Case Pack loader, evidence schemas and the deterministic replay
#     orchestrator/engine (read paths only — no writes, no formulas).
# Everything else — including all risk-formula functions and every snapshot
# write — remains forbidden in every UI source.

FORBIDDEN_IMPORT_ROOTS = {
    "providers", "agents", "database", "mcp", "security",
    "tools", "requests", "urllib", "httpx", "aiohttp", "socket", "openai",
}

# Per-file sanctioned backend roots (G04B). "orchestration" stays forbidden
# everywhere except these exact consume points.
ALLOWED_BACKEND_IMPORTS = {
    "frontend/pages/risk_watch.py": {"orchestration"},
    "frontend/replay_viewmodels.py": {"orchestration", "tools", "schemas"},
    "frontend/intel_viewmodels.py": {"tools", "schemas"},
}

# Modules the sanctioned orchestration imports may resolve to (no more).
ALLOWED_ORCHESTRATION_MODULES = {
    "orchestration.risk_watch_orchestrator",
    "orchestration.risk_engine",
    "orchestration.replay_orchestrator",
}


class TestUIIsolation:
    def test_no_forbidden_imports_in_ui_layer(self):
        for path, tree in _trees():
            rel = path.relative_to(REPO_ROOT).as_posix()
            allowed = ALLOWED_BACKEND_IMPORTS.get(rel, set())
            for node in ast.walk(tree):
                modules = []
                if isinstance(node, ast.ImportFrom):
                    modules = [node.module or ""]
                elif isinstance(node, ast.Import):
                    modules = [a.name for a in node.names]
                for mod in modules:
                    root = mod.split(".")[0]
                    if root == "orchestration":
                        assert mod in ALLOWED_ORCHESTRATION_MODULES, (path, mod)
                        assert "orchestration" in allowed, (path, mod)
                        continue
                    if root in FORBIDDEN_IMPORT_ROOTS:
                        assert root in allowed, (path, mod)

    def test_ui_never_triggers_scans_or_writes(self):
        for path in UI_SOURCES:
            rel = path.relative_to(REPO_ROOT).as_posix()
            text = path.read_text(encoding="utf-8")
            for forbidden in ("insert_snapshot", "mark_invalid",
                              "compute_risk_watch", "compute_C(", "compute_D(",
                              "compute_O7(", "derive_static_baseline"):
                assert forbidden not in text, (rel, forbidden)
            if rel != "frontend/pages/risk_watch.py":
                # the single sanctioned CTA lives in risk_watch.py only
                assert "run_risk_scan" not in text, rel

    def test_risk_watch_cta_is_the_single_orchestration_entry(self):
        src = (FRONTEND_DIR / "pages" / "risk_watch.py").read_text(encoding="utf-8")
        assert src.count("run_risk_scan(") >= 1
        # no direct collector / agent / synthesizer / critic invocation
        for forbidden in ("WeatherCollector", "run_professional_agents",
                          "RiskSynthesizer(", "Critic(", "compute_risk_watch"):
            assert forbidden not in src, forbidden

    def test_viewmodel_and_map_have_no_streamlit_dependency(self):
        for name in ("viewmodels.py", "map_view.py", "components.py",
                     "replay_viewmodels.py", "intel_viewmodels.py"):
            src = (FRONTEND_DIR / name).read_text(encoding="utf-8")
            assert "import streamlit" not in src, name

    def test_no_case_pack_access_from_ui(self):
        for path in UI_SOURCES:
            rel = path.relative_to(REPO_ROOT).as_posix()
            text = path.read_text(encoding="utf-8")
            assert "data/cases" not in text, rel
            if rel not in ("frontend/replay_viewmodels.py",
                           "frontend/intel_viewmodels.py"):
                assert "case_loader" not in text, rel

    def test_entry_point_is_new_file_legacy_app_untouched(self):
        assert APP_ENTRY.is_file()
        legacy = (REPO_ROOT / "app.py").read_text(encoding="utf-8")
        assert "RescueMind" in legacy  # legacy demo entry preserved as-is


# ═══ Runtime smoke: Streamlit app boots, frozen navigation renders ═══════════

class TestAppSmoke:
    @pytest.fixture()
    def at(self):
        from streamlit.testing.v1 import AppTest
        app = AppTest.from_file(str(APP_ENTRY), default_timeout=60)
        app.run()
        return app

    def test_app_runs_without_exception(self, at):
        assert not at.exception, [e.value for e in at.exception]

    def test_frozen_four_entry_navigation(self, at):
        radios = at.sidebar.radio
        assert len(radios) == 1
        assert radios[0].options == [
            "总览",
            "历史验证",
            "风险监测",
            "情报中心",
        ]

    def test_overview_is_default_page(self, at):
        assert at.sidebar.radio[0].value == "总览"
        body = " ".join(str(m.value) for m in at.markdown)
        assert "主地图" in body
        assert "当前风险" in body
        assert "智能体协作" in body

    def test_product_pages_render_after_g04b(self, at):
        """G04A placeholders were replaced by real G04B product pages.

        The frozen navigation still switches cleanly and no page raises;
        detailed per-page content assertions live in tests/test_g04b_ui.py.
        """
        for label, marker in (
            ("历史验证", "灾前证据"),
            ("风险监测", "数据覆盖"),
            ("情报中心", "证据中心"),
        ):
            at.sidebar.radio[0].set_value(label).run()
            assert not at.exception, [e.value for e in at.exception]
            body = " ".join(str(m.value) for m in at.markdown)
            assert marker in body, (label, marker)
