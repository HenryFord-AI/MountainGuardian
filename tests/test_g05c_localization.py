"""G05C – Competition Chinese Localization audit.

Gate G05C (doc 08 addendum): the competition-facing UI is Chinese-first.
A Chinese judge must be able to understand and operate the complete
product without understanding English.

What this suite enforces:
  * the frozen four-entry navigation uses the approved Chinese labels
    (总览 / 历史验证 / 风险监测 / 情报中心) and no bilingual title pattern;
  * the primary CTA is 执行风险扫描 — "Run Risk Scan" is not retained;
  * common English UI labels (Overview, Current Risk, Data Coverage, …)
    no longer appear as visible product labels on ANY of the four pages;
  * every remaining Latin token in the rendered pages is an EXPLICIT
    technical-allowlist item (brands, model/provider IDs, run/evidence
    identifiers, frozen enum values embedded in backend prose, units) —
    this is NOT a blanket "ban A-Z" test;
  * status / risk-level / quality presentation mappings are complete,
    match the gate-approved wording, and never produce statutory
    official-warning terminology;
  * the presentation layer is mapping-only: frozen backend identifiers
    (scan-stage names, enums, agent keys) are untouched, and the new
    display module is pure data with no backend imports;
  * the mandatory Chinese disclaimers (风险指数不是事件发生概率 /
    研究性风险评估，非官方灾害告警) render on the risk pages, and no
    prohibited claim language is introduced by localization.

Rendering uses streamlit.testing.v1.AppTest over a TEMP snapshot db
seeded with one schema-shaped scan whose model-text fields are Chinese —
mirroring the verified real persisted production output (DeepSeek live
runs persist Chinese findings; deterministic fallbacks are Chinese).
"""

from __future__ import annotations

import ast
import html as html_lib
import os
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from frontend import display, layout, theme  # noqa: E402
from frontend.components import RISK_INDEX_NOTE  # noqa: E402
from riskwatch.snapshot_store import SnapshotStore  # noqa: E402

FRONTEND_DIR = REPO_ROOT / "frontend"
APP_ENTRY = REPO_ROOT / "mountainguardian_app.py"

UI_SOURCES = sorted(
    p for p in FRONTEND_DIR.rglob("*.py") if "__pycache__" not in p.parts
) + [APP_ENTRY]


# ─── seeded app fixture (Chinese model-text fields, real frozen labels) ──────

def _cn_payload(risk_index=89.54, outlook=82.0):
    """Schema-shaped Risk Watch result with Chinese model-generated text.

    Mirrors verified production behavior: persisted DeepSeek outputs and
    deterministic fallbacks are Chinese. Driver labels use the EXACT
    frozen English strings from region.json / drivers.py so the
    presentation mapping is exercised.
    """
    return {
        "run_id": "rw-g05c-test",
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
                "fallback_used": False, "skip_reason": None,
                # production-shaped citations of frozen config values —
                # the display layer must render them as Chinese label：value
                "key_findings": [
                    "地形-地质条件：区域被判定为“极高山区—深切峡谷”"
                    "（terrain_class=Extremely high mountain - deeply "
                    "incised gorge），源区约5200 m",
                    "物源条件：沟道内存在丰富的松散冰碛物与岩屑"
                    "（loose_material_supply=Abundant loose moraine and "
                    "rock debris）",
                    "冰冻圈背景：源区为冰川发育区"
                    "（glacierized_source_zone=True）",
                ],
                "missing_data": [], "limitations": ["无实时传感器（测试夹具）"],
            }, "audit": {"provider_status": "CONNECTED",
                         "model_id": "deepseek-flash", "latency_ms": 1200,
                         "quarantined_evidence_ids": []}},
            "weather_hydrology": {"output": {
                "status": "DEGRADED", "confidence": 0.35,
                "evidence_ids": ["RW-POINTS"],
                "fallback_used": False, "skip_reason": None,
                "key_findings": ["近期降水偏高（测试夹具）"],
                "missing_data": ["实时水文数据"], "limitations": [],
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
            "explanation_confidence": 0.65, "fallback_used": False,
            "evidence_coverage": 0.65,
            "summary": "确定性引擎综合摘要（测试夹具）",
            "limitations": ["综合局限（测试夹具）"],
        }, "audit": {"provider_status": "CONNECTED",
                     "model_id": "deepseek-flash", "latency_ms": 700}},
        "critic": {"verdict": {
            "review_result": "PASS_WITH_LIMITATIONS", "severity": "INFO",
            "fallback_used": False,
            "scientific_limitations": ["无实时源区传感器（测试夹具）"],
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
                {"label": "Recent 7-day precipitation percentile "
                          "(conservative regional maximum)",
                 "contribution_points_rounded": 6.2,
                 "driver_type": "DYNAMIC"},
            ],
            "outlook_drivers": [
                {"label": "Forecast 7-day precipitation percentile "
                          "(conservative regional maximum)",
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
        "limitations": ["测试局限"],
        "status": "COMPLETED",
    }


@pytest.fixture(scope="module")
def at_cn(tmp_path_factory):
    """AppTest over a TEMP db seeded with one Chinese-text valid scan."""
    db = tmp_path_factory.mktemp("mg-g05c") / "mountainguardian.db"
    store = SnapshotStore(db)
    store.insert_snapshot(
        run_id="rw-g05c-test", region_id="jilong_port", status="COMPLETED",
        payload=_cn_payload(), created_at="2026-10-01T10:55:12+00:00",
        scan_mode="LIVE",
    )
    store.close()
    os.environ["MOUNTAINGUARDIAN_DB_PATH"] = str(db)
    try:
        from streamlit.testing.v1 import AppTest

        app = AppTest.from_file(str(APP_ENTRY), default_timeout=120)
        app.run()
        yield app
    finally:
        os.environ.pop("MOUNTAINGUARDIAN_DB_PATH", None)


def _page_texts(app) -> list:
    """All user-visible strings AppTest exposes for the current page."""
    texts = [str(m.value) for m in app.markdown]
    for attr in ("caption", "error", "warning", "info", "success"):
        for el in getattr(app, attr, []) or []:
            texts.append(str(getattr(el, "value", "")))
    for b in app.button:
        texts.append(str(b.label))
    for t in getattr(app, "tabs", []) or []:
        texts.append(str(getattr(t, "label", "")))
    for r in getattr(app, "radio", []) or []:
        texts.extend(str(o) for o in r.options)
    for s in getattr(app, "selectbox", []) or []:
        texts.extend(str(o) for o in s.options)
    for e in getattr(app, "expander", []) or []:
        label = getattr(e, "label", None)
        if label:
            texts.append(str(label))
    return texts


_TAG_RE = re.compile(r"<[^>]+>")
_STYLE_BLOCK_RE = re.compile(r"<(style|script)\b[^>]*>.*?</\1\s*>",
                             re.S | re.I)


def _plain_visible(texts: list) -> str:
    """Strip injected CSS/JS blocks, HTML markup and entities →
    the plain text a judge would actually read."""
    joined = "\n".join(texts)
    joined = _STYLE_BLOCK_RE.sub(" ", joined)
    joined = _TAG_RE.sub(" ", joined)
    return html_lib.unescape(joined)


# ─── Explicit technical allowlist (gate G05C §8; doc 08 §4) ──────────────────
#
# Brands, machine/provenance identifiers, frozen enum values embedded in
# backend prose, and measurement units. Anything else in Latin letters on a
# rendered page is a localization defect.

ALLOWED_PHRASE_PATTERNS = (
    r"MountainGuardian",
    r"DeepSeek",
    r"deepseek-flash",
    r"Open-Meteo",
    r"Sentinel-2",
    r"Baseline Susceptibility Index",   # frozen backend semantics string
    r"NOAA El Ni[oñ]o Index Dashboard",
    r"WMO El Ni[oñ]o/La Ni[nñ]a Update \(August 2026\)",
    r"El Ni[oñ]o",
    r"La Ni[nñ]a",
    r"UTC",
    r"ENSO",
    r"DAG",
    r"https?://\S+",
    # code-module provenance references (audit trail, e.g. safety controls)
    r"(?:[a-z_]+/)+[a-z_]+\.py",
    # dataset / legacy persisted provenance tokens (frozen backend values)
    r"ERA5[\-–]?Land",
    r"context-only",
    r"sentinel-2",
    r"stac",
    r"enso",
    r"region\.json",   # frozen config filename (technical identifier)
    # run-id / replay identifiers
    r"rw-[0-9A-Za-z\-]+",
    r"rws-[0-9A-Za-z\-]+",
    r"g04b-ui-replay",
    # ── frozen backend strings (agents/ orchestration/ Case Pack) ──────
    # These embedded English fragments originate in frozen backend zones
    # that G05C must NOT modify; they are technical terms / source-data
    # citations inside otherwise-Chinese deterministic output, never UI
    # labels authored by the frontend. Disclosed in the Gate Report.
    r"Historical Replay 无实时预报数据",   # weather-agent fallback limitation
    r"El Niño firmly established",        # NOAA source-data citation
    r"Risk Index、专业 Agent 输出",        # frozen Stage-B attestation
)

# Single Latin words allowed verbatim: brands, measurement/data units from
# frozen Case Pack field values, and frozen enum/product terms embedded in
# backend prose. NOT a general English allowance — the banned-label test
# separately forbids every English UI label the frontend authors.
ALLOWED_WORDS = {
    "AI", "mm", "HIGH", "LOW", "MODERATE", "ELEVATED",
    "True", "False", "None", "Ni",
    # units / data-type suffixes from frozen Case Pack field values
    "km", "km2", "m", "cm", "ms", "min", "mins", "months", "month",
    "year", "years", "degC", "anomaly", "bool", "count", "index", "scene",
    # frozen product/science terms embedded in backend prose
    "Risk", "Index", "Agent", "Susceptibility", "Baseline",
    "Historical", "Replay", "Data", "Limited", "El", "firmly", "established",
    # frozen Case Pack / persisted data values (field values, dataset and
    # location identifiers inside otherwise-Chinese model findings)
    "Jilong", "InSAR", "Abundant", "era5", "preferred", "ERA5", "Land",
    "Case", "Pack",
}

_WORD_RE = re.compile(r"[A-Za-z]{2,}[A-Za-z0-9_\-]*")


def _is_identifier_token(token: str) -> bool:
    """Machine identifiers pass through untranslated by design:
    snake_case ids, SCREAMING_CASE enums, hyphenated uppercase evidence
    ids (RW-STATIC-TERRAIN, EV-SAT-POST-01)."""
    if "_" in token:
        return True
    stripped = token.replace("-", "")
    if stripped and stripped.isupper():
        return True
    return False


def _blank_allowed_phrases(text: str) -> str:
    for pat in ALLOWED_PHRASE_PATTERNS:
        text = re.sub(pat, " ", text)
    return text


def _unknown_latin_tokens(plain: str) -> set:
    text = _blank_allowed_phrases(plain)
    unknown = set()
    for m in _WORD_RE.finditer(text):
        tok = m.group(0)
        if tok in ALLOWED_WORDS:
            continue
        if _is_identifier_token(tok):
            continue
        unknown.add(tok)
    return unknown


# ─── Banned visible English UI labels (gate G05C audit list) ─────────────────

BANNED_VISIBLE_LABELS = (
    "Overview", "Historical Replay", "Risk Watch", "Intelligence Center",
    "Current Risk", "7-Day Outlook", "Data Coverage", "Scan Progress",
    "Historical Trend", "Agent Workspace", "Evidence Center",
    "Audit & Safety", "Model Runtime", "Run Risk Scan",
    "Completed", "Degraded", "Skipped", "Needs Revision",
    "Key Findings", "Evidence Used", "Missing Data", "Limitations",
    "Confidence", "Top Drivers", "Post-event Validation",
    "Scientific Limitations", "What Changed", "Required", "Optional",
    "Last Scan", "Last Updated", "Main Map", "Agent Collaboration",
    "Quick Entries", "Evidence",
)

PROHIBITED_CLAIMS = (
    "蓝色预警", "黄色预警", "橙色预警", "红色预警",
    "官方预警", "实时预警中心", "成功预测", "精准预测",
    "91%", "发生概率 91",
)

_PAGES = ("总览", "历史验证", "风险监测", "情报中心")


def _render_page(app, label: str) -> str:
    app.sidebar.radio[0].set_value(label).run()
    assert not app.exception, (label, [e.value for e in app.exception])
    return _plain_visible(_page_texts(app))


# ═══ Navigation / CTA / shared constants ═════════════════════════════════════

class TestFrozenChineseNavigation:
    def test_nav_labels_are_chinese_only(self):
        assert layout.NAV_LABELS == ("总览", "历史验证", "风险监测", "情报中心")

    def test_page_titles_are_chinese_only(self):
        assert layout.PAGE_TITLES == {
            "overview": "总览",
            "historical_replay": "历史验证",
            "risk_watch": "风险监测",
            "intelligence_center": "情报中心",
        }

    def test_no_bilingual_title_pattern_in_sources(self):
        pattern = re.compile(r"[一-鿿]+\s*[·/|]\s*(Overview|Risk Watch|"
                             r"Historical Replay|Intelligence Center|"
                             r"Current Risk)")
        for path in UI_SOURCES:
            text = path.read_text(encoding="utf-8")
            assert not pattern.search(text), path.name

    def test_primary_cta_is_chinese(self):
        from frontend.pages.risk_watch import CTA_LABEL
        assert CTA_LABEL == "执行风险扫描"

    def test_risk_index_note_is_chinese_disclaimer(self):
        assert RISK_INDEX_NOTE == "风险指数不是事件发生概率"

    def test_intel_tabs_are_chinese(self):
        src = (FRONTEND_DIR / "pages" / "intelligence_center.py").read_text(
            encoding="utf-8")
        assert '["智能体工作区", "证据中心", "审计与安全"]' in src


# ═══ Presentation mappings (gate-approved wording, enums untouched) ══════════

class TestDisplayMappings:
    def test_risk_bands_map_to_approved_labels(self):
        assert display.RISK_LEVEL_LABELS == {
            "LOW": "低", "MODERATE": "中等", "ELEVATED": "较高", "HIGH": "高",
        }
        # frozen backend enum vocabulary is untouched
        assert set(theme.RISK_LEVEL_COLORS) == {
            "LOW", "MODERATE", "ELEVATED", "HIGH"}

    def test_required_status_mappings_present(self):
        required = {
            "CONNECTED": "已连接", "FALLBACK": "回退模式",
            "COMPLETED": "已完成", "COMPLETED_WITH_LIMITATIONS": "已完成，但存在局限",
            "DEGRADED": "降级", "SKIPPED": "已跳过", "PENDING": "待处理",
            "NEEDS_REVISION": "需要修订", "PASS": "通过",
            "PASS_WITH_LIMITATIONS": "通过，但存在局限", "WARNING": "警告",
            "FAILED": "失败", "OFFLINE": "离线",
        }
        for key, zh in required.items():
            assert display.status_label(key) == zh, key

    def test_quality_mappings_present(self):
        required = {"GOOD": "良好", "LIMITED": "有限", "STALE": "已过期",
                    "MISSING": "缺失", "AVAILABLE": "可用",
                    "UNAVAILABLE": "不可用"}
        for key, zh in required.items():
            assert display.quality_label(key) == zh, key

    def test_unknown_values_pass_through_never_invented(self):
        assert display.status_label("SOMETHING_NEW") == "SOMETHING_NEW"
        assert display.risk_label("SOMETHING_NEW") == "SOMETHING_NEW"

    def test_frozen_backend_limitation_message_mapped_for_display(self):
        # doc 04 §36 failure-path string — backend value untouched, the
        # display mapping produces the approved Chinese equivalent
        frozen = ("Scan incomplete — required weather data unavailable: no "
                  "official Current Risk Index / 7-Day Outlook was produced "
                  "(doc 04 §36). Static baseline B remains independently "
                  "reportable; the AI interpretation layer was skipped.")
        zh = display.limitation_label(frozen)
        assert zh.startswith("扫描未完成")
        assert "缺少必需的天气数据" in zh
        # Chinese model limitations pass through unchanged
        assert display.limitation_label("无实时传感器") == "无实时传感器"

    def test_no_mapping_produces_official_warning_terms(self):
        tables = (display.STATUS_LABELS, display.RISK_LEVEL_LABELS,
                  display.QUALITY_LABELS, display.DIRECTION_LABELS,
                  display.AGREEMENT_LABELS, display.SCAN_MODE_LABELS,
                  display.PHASE_LABELS, display.EVIDENCE_TYPE_LABELS,
                  display.SKIP_REASON_LABELS, display.CRITIC_CHECK_LABELS,
                  display.SAFETY_CONTROL_LABELS, display.DRIVER_LABELS_ZH,
                  display.POINT_NAME_LABELS_ZH, display.AGENT_ID_LABELS)
        for table in tables:
            for value in table.values():
                for banned in ("预警", "概率", "成功预测", "精准预测"):
                    assert banned not in str(value) or "误用" in str(value), \
                        (value, banned)

    def test_agent_visible_names_are_chinese(self):
        from frontend.viewmodels import (AGENT_DISPLAY_NAMES, CRITIC_DISPLAY,
                                         SYNTHESIZER_DISPLAY)
        expected_zh = {
            "glacier_geology": "冰川地质智能体",
            "weather_hydrology": "气象水文智能体",
            "remote_sensing": "遥感解译智能体",
        }
        for key, zh in expected_zh.items():
            assert AGENT_DISPLAY_NAMES[key][1] == zh
            assert display.agent_id_label(key) == zh
        assert SYNTHESIZER_DISPLAY[1] == "风险综合智能体"
        assert CRITIC_DISPLAY[1] == "评审智能体"

    def test_display_module_is_pure_data_no_backend_imports(self):
        src = (FRONTEND_DIR / "display.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert node.module == "__future__", node.module
            elif isinstance(node, ast.Import):
                pytest.fail(f"display.py must not import {node.names}")

    def test_frozen_scan_stage_identifiers_untouched(self):
        from frontend.viewmodels import SCAN_STEP_STAGES
        assert tuple(s[3] for s in SCAN_STEP_STAGES) == (
            "NORMALIZED", "VALIDATED", "SNAPSHOT_SAVED",
            "AGENTS_COMPLETED", "SYNTHESIZED", "REVIEWED",
        )
        # visible step labels follow the gate terminology
        assert tuple(s[1] for s in SCAN_STEP_STAGES) == (
            "数据采集", "数据标准化", "保存快照",
            "智能体分析", "风险综合", "评审复核",
        )


# ═══ G05C remediation: judge-facing prose polish ════════════════════════════
#
# Commander visual acceptance required (1) no visible Stage A / Stage B
# engineering terminology in judge-facing prose and (2) long English
# region-config field=value citations rendered as Chinese label：value.
# Underlying identifiers, logic, config values and tests stay frozen.

class TestRemediationProsePolish:
    @pytest.fixture()
    def pages(self, at_cn):
        return {label: _render_page(at_cn, label) for label in _PAGES}

    def test_stage_identifiers_absent_from_judge_prose(self, pages):
        for label, body in pages.items():
            assert "Stage" not in body, label

    def test_replay_prose_uses_chinese_stage_wording(self, pages):
        replay = pages["历史验证"]
        assert "灾前阶段输入证据" in replay
        assert "灾前分析与灾后验证严格分离" in replay
        assert "灾前分析（灾前阶段冻结结果）" in replay
        assert "灾前阶段结果未修改" in replay
        assert "灾前阶段不可能知道的信息" in replay
        # the frozen Stage-B attestation (rendered inside an expander, so
        # asserted through the display mapping over the real VM string)
        from frontend.replay_viewmodels import build_historical_replay_viewmodel
        vm = build_historical_replay_viewmodel()
        mapped = display.narrative_label(vm.stage_b_statement)
        assert "Stage" not in mapped
        assert "灾后验证阶段仅执行" in mapped
        assert "灾后验证阶段未修改且不可修改灾前阶段" in mapped
        for note in vm.stage_b_findings:
            assert "Stage" not in display.narrative_label(note)

    def test_config_value_citations_render_chinese(self, pages):
        intel = pages["情报中心"]
        for zh in ("地形类型：极高山区—深切峡谷",
                   "松散物源：丰富的冰碛物与岩屑",
                   "冰川化源区：是"):
            assert zh in intel, zh
        for raw in ("terrain_class=", "loose_material_supply=",
                    "glacierized_source_zone="):
            assert raw not in intel, raw
            assert raw not in pages["历史验证"], raw

    def test_narrative_label_mappings(self):
        assert display.narrative_label(
            "（terrain_class=Extremely high mountain - deeply incised "
            "gorge）") == "（地形类型：极高山区—深切峡谷）"
        assert display.narrative_label(
            "loose_material_supply=Abundant loose moraine and rock debris"
        ) == "松散物源：丰富的冰碛物与岩屑"
        assert display.narrative_label(
            "loose_material_supply=Abundant") == "松散物源：丰富"
        assert display.narrative_label(
            "glacierized_source_zone=True") == "冰川化源区：是"
        assert display.narrative_label(
            "Stage B 仅执行灾后回顾性验证") == "灾后验证阶段仅执行灾后回顾性验证"
        assert display.narrative_label(
            "（Stage A / Stage B 分离）") == "（灾前分析与灾后验证严格分离）"
        # unknown narrative passes through untouched
        assert display.narrative_label("无实时传感器") == "无实时传感器"

    def test_frozen_identifiers_and_logic_untouched(self):
        # orchestration identifiers keep their frozen English values
        from orchestration.replay_orchestrator import run_stage_a, run_stage_b
        from frontend.replay_viewmodels import build_historical_replay_viewmodel
        vm = build_historical_replay_viewmodel()
        assert vm.stage_a_unchanged is True
        assert run_stage_a is not None and run_stage_b is not None
        # raw config values are still the frozen English strings
        from riskwatch.region import load_region
        cfg = load_region("jilong_port").data
        assert cfg["static_terrain_baseline"]["terrain_class"].startswith(
            "Extremely high mountain")
        assert cfg["cryosphere_baseline"]["glacierized_source_zone"] is True


# ═══ Rendered four-page language audit (allowlist-based) ═════════════════════

class TestRenderedChineseAudit:
    @pytest.fixture()
    def pages(self, at_cn):
        rendered = {}
        for label in _PAGES:
            rendered[label] = _render_page(at_cn, label)
        return rendered

    def test_no_banned_english_ui_labels(self, pages):
        for label, body in pages.items():
            # allowlisted frozen-backend phrases are blanked first — every
            # remaining occurrence of a banned label is a frontend defect
            scan_body = _blank_allowed_phrases(body)
            for banned in BANNED_VISIBLE_LABELS:
                assert banned not in scan_body, (label, banned)

    def test_only_allowlisted_latin_tokens_remain(self, pages):
        for label, body in pages.items():
            unknown = _unknown_latin_tokens(body)
            assert not unknown, (label, sorted(unknown))

    def test_no_prohibited_claim_language(self, pages):
        for label, body in pages.items():
            for banned in PROHIBITED_CLAIMS:
                assert banned not in body, (label, banned)

    def test_required_chinese_disclaimers_present(self, pages):
        assert "风险指数不是事件发生概率" in pages["总览"]
        assert "风险指数不是事件发生概率" in pages["风险监测"]
        assert "展望指数不是事件发生概率" in pages["风险监测"]
        assert "不是事件发生概率" in pages["历史验证"]
        assert "非官方灾害告警" in pages["风险监测"]

    def test_navigation_and_cta_rendered_chinese(self, at_cn, pages):
        assert list(at_cn.sidebar.radio[0].options) == list(_PAGES)
        at_cn.sidebar.radio[0].set_value("风险监测").run()
        labels = [b.label for b in at_cn.button]
        assert any("执行风险扫描" in x for x in labels), labels

    def test_risk_result_chinese_semantics_preserved(self, pages):
        replay = pages["历史验证"]
        # the deterministic 91/100 HIGH result, Chinese-labeled
        assert "91" in replay
        assert "基线易感性指数" in replay
        assert "高" in replay
        watch = pages["风险监测"]
        assert "89.5" in watch
        assert "当前风险" in watch
        assert "未来7天风险展望" in watch
        assert "历史风险趋势" in watch
        assert "扫描进度" in watch
        assert "数据覆盖" in watch
        assert "风险变化" in watch

    def test_frozen_driver_labels_display_in_chinese(self, pages):
        watch = pages["风险监测"]
        assert "巨大高差与狭窄沟谷" in watch
        assert "近7天降水百分位" in watch
        assert "未来7天预报降水百分位" in watch

    def test_statuses_and_labels_visible_in_chinese(self, pages):
        watch = pages["风险监测"]
        for expected in ("已完成", "已连接", "运行编号", "执行耗时",
                         "数据采集", "评审复核", "实时"):
            assert expected in watch, expected
        intel = pages["情报中心"]
        for expected in ("智能体工作区", "证据中心", "审计与安全",
                         "冰川地质智能体", "气象水文智能体", "遥感解译智能体",
                         "风险综合智能体", "评审智能体",
                         "提示词注入防护", "数据泄漏防护",
                         "灾后信息泄漏防护", "输出结构校验",
                         "外部操作已禁用", "置信度", "关键发现",
                         "模型运行状态"):
            assert expected in intel, expected
        replay = pages["历史验证"]
        for expected in ("灾前阶段", "事件发生", "灾后验证", "灾前证据",
                         "多智能体分析", "风险评估结果", "主要风险驱动因素",
                         "科学局限", "评审智能体"):
            assert expected in replay, expected
        overview = pages["总览"]
        for expected in ("主地图", "当前风险", "智能体协作", "证据",
                         "数据覆盖", "快速入口", "最近扫描"):
            assert expected in overview, expected

    def test_research_prototype_label_chinese(self, at_cn):
        sidebar = "\n".join(
            str(m.value) for m in at_cn.sidebar.markdown)
        assert "研究原型" in sidebar


# ═══ Source-level audit: user-facing literals are Chinese ════════════════════

class TestSourceLevelAudit:
    _ST_LITERAL_CALLS = {"button", "expander", "error", "caption", "status"}
    _CJK_RE = re.compile(r"[一-鿿]")

    def test_interactive_widget_labels_contain_chinese(self):
        """Every literal first-arg passed to st.button / st.expander /
        st.error / st.caption / st.status contains Chinese and none of the
        banned English labels (variable args are covered by the rendered
        audit)."""
        for path in UI_SOURCES:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                if not (isinstance(func, ast.Attribute)
                        and isinstance(func.value, ast.Name)
                        and func.value.id == "st"
                        and func.attr in self._ST_LITERAL_CALLS):
                    continue
                if not node.args:
                    continue
                arg = node.args[0]
                literal = None
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    literal = arg.value
                elif isinstance(arg, ast.JoinedStr):
                    literal = "".join(
                        v.value for v in arg.values
                        if isinstance(v, ast.Constant)
                        and isinstance(v.value, str)
                    )
                if literal is None:
                    continue
                assert self._CJK_RE.search(literal), (path.name, literal)
                for banned in BANNED_VISIBLE_LABELS:
                    assert banned not in literal, (path.name, literal, banned)

    def test_no_forbidden_claims_in_ui_sources(self):
        text = "\n".join(
            p.read_text(encoding="utf-8") for p in UI_SOURCES)
        for banned in PROHIBITED_CLAIMS:
            assert banned not in text, banned
        assert "预警" not in text

    def test_probability_term_only_negated_in_ui_sources(self):
        text = "\n".join(
            p.read_text(encoding="utf-8") for p in UI_SOURCES)
        for m in re.finditer("发生概率", text):
            ctx = text[max(0, m.start() - 8):m.start()]
            assert "不是" in ctx or "非" in ctx, \
                text[max(0, m.start() - 20):m.end() + 10]
