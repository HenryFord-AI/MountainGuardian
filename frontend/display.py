"""
MountainGuardian G05C – Centralized Chinese presentation mappings.

Competition localization (doc 08 addendum): the visible product language is
Chinese. This module is PRESENTATION-ONLY — it maps frozen backend enum
values / machine labels to their approved Chinese display strings and
never alters any underlying value, enum, formula or data source.

Rules enforced here (gate G05C / doc 05 §61–§63 / doc 08 §4–§6):
  * runtime enum values (status, risk level, quality, phase) stay as-is in
    the backend; only their display is localized;
  * technical identifiers and brands (MountainGuardian, DeepSeek,
    deepseek-flash, Open-Meteo, Sentinel-2, Run/Evidence IDs, UTC …) are
    never translated — unknown values pass through unchanged;
  * risk bands keep the frozen four-band semantics (LOW/MODERATE/
    ELEVATED/HIGH → 低/中等/较高/高); statutory government alert-level
    terminology is never produced;
  * every mapping is an exact-match lookup with passthrough fallback, so a
    new backend value degrades to showing its raw identifier, never to a
    wrong translation.
"""

from __future__ import annotations

# ─── Runtime / agent / critic status display (doc 05 §14, gate G05C) ────────
STATUS_LABELS = {
    "CONNECTED": "已连接",
    "FALLBACK": "回退模式",
    "COMPLETED": "已完成",
    "COMPLETED_WITH_LIMITATIONS": "已完成，但存在局限",
    "DEGRADED": "降级",
    "SKIPPED": "已跳过",
    "PENDING": "待处理",
    "RUNNING": "运行中",
    "NEEDS_REVISION": "需要修订",
    "PASS": "通过",
    "PASS_WITH_LIMITATIONS": "通过，但存在局限",
    "BLOCKED": "已拦截",
    "WARNING": "警告",
    "CRITICAL": "严重",
    "INFO": "提示",
    "FAILED": "失败",
    "FAILURE": "失败",
    "OFFLINE": "离线",
    "UNKNOWN": "未知",
    "UNAVAILABLE": "不可用",
    "EXECUTED": "已执行",
    # data availability states (doc 02 §18 / doc 04 §34) — same display
    # vocabulary as quality labels; coverage rows use these verbatim
    "AVAILABLE": "可用",
    "NOT USED": "未使用",
    "STALE": "已过期",
    "LIMITED": "有限",
    "MISSING": "缺失",
    "FRESH": "新鲜",
    "OK": "正常",
    # system state (nav footer / header chip)
    "ONLINE": "在线",
    "NO DATA": "无数据",
    # safety-control states (display only; guard logic untouched)
    "ACTIVE": "已启用",
    "ENFORCED": "已启用",
    "FLAGGED": "发现问题",
    "DISABLED BY DESIGN": "设计上禁用",
}

# ─── Frozen four risk bands — labels only (doc 04 §16, doc 08 §5) ───────────
RISK_LEVEL_LABELS = {
    "LOW": "低",
    "MODERATE": "中等",
    "ELEVATED": "较高",
    "HIGH": "高",
}

# ─── Data-quality / availability display (doc 02 §18, doc 04 §34) ───────────
QUALITY_LABELS = {
    "GOOD": "良好",
    "LIMITED": "有限",
    "STALE": "已过期",
    "MISSING": "缺失",
    "FRESH": "新鲜",
    "AVAILABLE": "可用",
    "UNAVAILABLE": "不可用",
    "NOT USED": "未使用",
    "OK": "正常",
}

# ─── Trend / comparison direction display (doc 02 §6.3, doc 04 §18) ─────────
DIRECTION_LABELS = {
    "RISING": "上升",
    "FALLING": "下降",
    "STABLE": "平稳",
    "NO_HISTORY": "暂无历史",
    "UP": "上升",
    "DOWN": "下降",
    "UNCHANGED": "持平",
    "NOT_COMPARABLE": "不可比较",
}

# ─── Agent agreement display (doc 03 §18) ────────────────────────────────────
AGREEMENT_LABELS = {
    "AGREEMENT": "一致",
    "PARTIAL_AGREEMENT": "部分一致",
    "SIGNIFICANT_DISAGREEMENT": "显著分歧",
}

# ─── Scan mode display ───────────────────────────────────────────────────────
SCAN_MODE_LABELS = {
    "LIVE": "实时",
    "HISTORICAL": "历史",
    "TEST": "测试",
}

# ─── Evidence phase display (frozen phase tags → Chinese) ───────────────────
PHASE_LABELS = {
    "PRE-EVENT": "灾前阶段",
    "EVENT": "事件发生",
    "POST-EVENT": "灾后验证",
    "CONTEXT": "仅作背景",
    "PRE_EVENT_STATIC": "灾前阶段",
    "DERIVED_PRE_EVENT_STATIC": "灾前阶段",
    "PRE_EVENT_CONTEXT": "灾前阶段",
    "PRE_EVENT_EVIDENCE": "灾前阶段",
    "POST_EVENT_VALIDATION": "灾后验证",
    "CONTEXT_ONLY": "仅作背景",
    "MISSING_INPUT": "缺失输入",
    "DESIGN_INPUT": "设计输入",
    "METADATA": "元数据",
    "SAFETY_BOUNDARY": "安全边界说明",
    "SCIENTIFIC_BOUNDARY": "科学边界说明",
}

# ─── Evidence type display (frozen type identifiers → Chinese) ──────────────
EVIDENCE_TYPE_LABELS = {
    "terrain": "地形",
    "geology": "地质",
    "cryosphere": "冰冻圈",
    "historical_event": "历史事件",
    "weather_context": "气象背景",
    "climate_context": "气候背景",
    "rs_image": "遥感影像",
    "rs_metadata": "遥感元数据",
    "hydrology_static": "静态水文",
}

# ─── Raw / derived display ───────────────────────────────────────────────────
RAW_DERIVED_LABELS = {
    "raw": "原始数据",
    "derived": "推导数据",
}

# ─── Agent skip reasons (doc 03 §12.2, doc 04 §23) ───────────────────────────
SKIP_REASON_LABELS = {
    "SKIPPED_NO_USABLE_IMAGERY": "已跳过：无可用影像",
    "SKIPPED_NO_NEW_IMAGERY": "已跳过：无新影像",
    "SKIPPED_LOW_QUALITY_IMAGERY": "已跳过：影像质量过低",
}

# ─── Critic programmatic check display (schemas.synthesis CRITIC_CHECK_IDS) ──
CRITIC_CHECK_LABELS = {
    "EVIDENCE_SUPPORT": "证据支撑",
    "POST_EVENT_LEAKAGE": "灾后信息泄漏",
    "CAUSAL_OVERCLAIM": "因果过度推断",
    "PROBABILITY_MISUSE": "概率表述误用",
    "MISSING_DATA_HONESTY": "缺失数据如实声明",
    "AGENT_DISAGREEMENT": "智能体分歧",
    "SATELLITE_OVERCLAIM": "卫星结论过度推断",
    "EVIDENCE_ID_INTEGRITY": "证据编号完整性",
    "SCORE_INTEGRITY": "分数完整性",
    "FALLBACK_LABELING": "回退标注完整性",
}

# ─── Frozen safety-control display labels (logic / IDs unchanged) ───────────
SAFETY_CONTROL_LABELS = {
    "Prompt Injection Guard": "提示词注入防护",
    "Data Leakage Guard": "数据泄漏防护",
    "Post-event Leakage Guard": "灾后信息泄漏防护",
    "Output Schema Validation": "输出结构校验",
    "External Actions Disabled": "外部操作已禁用",
}

# ─── Frozen deterministic driver labels (region.json / drivers.py) ──────────
# Exact-match display mapping of the frozen STATIC factor names and the two
# dynamic precipitation driver labels. Backend values stay English-frozen;
# unknown labels pass through unchanged (never invent a translation).
DRIVER_LABELS_ZH = {
    "High-altitude cryosphere source zone": "高海拔冰冻圈源区",
    "Huge vertical drop and narrow gorge": "巨大高差与狭窄沟谷",
    "Loose channel material supply": "沟道松散物源供给",
    "Historical chained-hazard recurrence": "历史链式灾害复发性",
    "Downstream exposure and port facilities": "下游暴露与口岸设施",
    "Monsoon and high-precipitation background": "季风与高降水背景",
    "Recent 7-day precipitation percentile (conservative regional maximum)":
        "近7天降水百分位（区域保守最大值）",
    "Forecast 7-day precipitation percentile (conservative regional maximum)":
        "未来7天预报降水百分位（区域保守最大值）",
}

# ─── Frozen monitoring-point display names (region.json) ─────────────────────
POINT_NAME_LABELS_ZH = {
    "Source Zone (high-altitude cryosphere / source-zone environment)":
        "源区（高海拔冰冻圈 / 源区环境）",
    "Port Zone (Jilong Port / downstream exposure zone)":
        "口岸区（吉隆口岸 / 下游暴露区）",
}
POINT_ID_LABELS_ZH = {
    "source_zone": "源区",
    "port_zone": "口岸区",
}

# ─── Optional-source keys in stored data-quality payloads (doc 04 §19) ──────
OPTIONAL_SOURCE_KEY_LABELS = {
    "satellite": "卫星影像",
    "hydrology": "水文",
    "soil": "土壤湿度",
    "enso": "ENSO 气候背景",
    "in_situ": "实地观测",
}

# ─── Agent IDs → visible Chinese names (class names / IDs unchanged) ────────
AGENT_ID_LABELS = {
    "glacier_geology": "冰川地质智能体",
    "weather_hydrology": "气象水文智能体",
    "remote_sensing": "遥感解译智能体",
    "synthesizer": "风险综合智能体",
    "risk_synthesizer": "风险综合智能体",
    "critic": "评审智能体",
}

# ─── Frozen backend limitation message (doc 04 §36 failure path) ────────────
# The orchestrator appends this frozen English string to the snapshot
# limitations when required weather data is unavailable. The backend value
# is untouched; only its display is mapped to the approved Chinese text.
_LIMITATION_PREFIX_ZH = (
    ("Scan incomplete — required weather data unavailable",
     "扫描未完成 — 缺少必需的天气数据：本轮未产生正式当前风险指数 / "
     "未来7天风险展望（文档 04 §36）。静态基线 B 仍可独立报告；"
     "AI 解释层已跳过。"),
)


def limitation_label(text) -> str:
    """Chinese display of frozen backend limitation messages (exact-prefix
    mapping; unknown texts pass through unchanged — model limitations are
    already Chinese)."""
    value = str(text or "")
    for prefix, zh in _LIMITATION_PREFIX_ZH:
        if value.startswith(prefix):
            return zh
    return value


# ─── Lookup helpers (exact match, passthrough fallback) ──────────────────────

def _lookup(table: dict, value, default=None):
    if value is None:
        return default if default is not None else "—"
    key = str(value)
    if key in table:
        return table[key]
    upper = key.upper()
    if upper in table:
        return table[upper]
    return default if default is not None else key


def status_label(value) -> str:
    """Chinese display of a frozen runtime status / verdict value."""
    return _lookup(STATUS_LABELS, value)


def risk_label(level) -> str:
    """Chinese display of a frozen risk band (低/中等/较高/高)."""
    return _lookup(RISK_LEVEL_LABELS, level)


def quality_label(value) -> str:
    """Chinese display of a frozen data-quality / availability value."""
    return _lookup(QUALITY_LABELS, value)


def direction_label(value) -> str:
    return _lookup(DIRECTION_LABELS, value)


def agreement_label(value) -> str:
    return _lookup(AGREEMENT_LABELS, value)


def scan_mode_label(value) -> str:
    return _lookup(SCAN_MODE_LABELS, value)


def phase_label(value) -> str:
    return _lookup(PHASE_LABELS, str(value or "").replace("_", " ").upper()
                   .replace(" ", "_"))


def evidence_type_label(value) -> str:
    return _lookup(EVIDENCE_TYPE_LABELS, value)


def raw_derived_label(value) -> str:
    return _lookup(RAW_DERIVED_LABELS, value)


def skip_reason_label(value) -> str:
    return _lookup(SKIP_REASON_LABELS, value)


def critic_check_label(check_id) -> str:
    return _lookup(CRITIC_CHECK_LABELS, check_id)


def safety_control_label(name) -> str:
    return _lookup(SAFETY_CONTROL_LABELS, name)


def driver_label(label) -> str:
    """Chinese display of a frozen deterministic driver label."""
    return _lookup(DRIVER_LABELS_ZH, label)


def point_name_label(name) -> str:
    return _lookup(POINT_NAME_LABELS_ZH, name)


def point_id_label(point_id) -> str:
    return _lookup(POINT_ID_LABELS_ZH, point_id)


def optional_source_key_label(key) -> str:
    return _lookup(OPTIONAL_SOURCE_KEY_LABELS, str(key or "").lower())


def agent_id_label(agent_id) -> str:
    return _lookup(AGENT_ID_LABELS, agent_id)
