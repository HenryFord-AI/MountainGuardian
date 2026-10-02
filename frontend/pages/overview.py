"""
MountainGuardian G04A – Overview page (总览).

The first screen must answer within seconds (doc 05 §8):
  1. Where is the system monitoring?      → main map (region + points)
  2. What is the current risk?            → Current Risk card
  3. What is the trend?                   → Risk Trend / Recent Scan card
  4. Are the Agents working?              → Agent Collaboration component
  5. What evidence supports the result?   → Evidence / Data Coverage card

Frozen layout (doc 05 §9): map-first, Current Risk on the right,
agent collaboration + trend below, quick entries + evidence at the
bottom. All values come from the read-only OverviewViewModel — this
page never computes risk, never calls models, never writes snapshots.

G05C (doc 08): visible page language is Chinese; technical identifiers
(Evidence IDs, Run ID, UTC, brand names) stay verbatim per the allowlist.
"""

from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as st_components

from frontend import layout, theme
from frontend.components import (
    agent_card_html,
    card_title,
    chip,
    drivers_html,
    empty_state,
    esc,
    evidence_chips_html,
    flow_arrow,
    risk_card_html,
)
from frontend.display import (
    point_id_label,
    quality_label,
    risk_label,
    scan_mode_label,
    status_label,
)
from frontend.map_view import build_overview_map
from frontend.viewmodels import OverviewViewModel

MAP_HEIGHT = 560


def _render_map(vm: OverviewViewModel) -> None:
    st.markdown(card_title("主地图", accent="◈") + "", unsafe_allow_html=True)
    map_html = build_overview_map(vm.monitoring_points, height=MAP_HEIGHT)
    if map_html is None:
        st.markdown(
            empty_state("该区域暂无可用监测点。"),
            unsafe_allow_html=True,
        )
        return
    # The frame styling lives inside the folium HTML (iframe) — Streamlit
    # markdown cannot wrap a component in a shared div.
    st_components.html(map_html, height=MAP_HEIGHT + 12, scrolling=False)
    st.markdown(
        '<div class="mg-map-caption">监测区域：'
        f"{esc(vm.region_name_zh or vm.region_name)} · "
        "代表性监测坐标（不确定性已记录，区域配置冻结）。"
        "二维视图 — 无三维 GIS，UI 不做空间再分析。</div>",
        unsafe_allow_html=True,
    )


def _render_current_risk(vm: OverviewViewModel) -> None:
    st.markdown(card_title("当前风险", accent="●"), unsafe_allow_html=True)
    if vm.fallback_mode:
        st.markdown(
            '<div class="mg-fallback">AI 运行时 · 回退模式</div>',
            unsafe_allow_html=True,
        )
        st.caption(
            "确定性风险指数仍然有效；AI 解释层使用了基于规则的回退"
            "（绝不伪装为模型输出）。"
        )
    cov = vm.coverage
    st.markdown(
        risk_card_html(
            vm.risk_index_rounded,
            vm.risk_level,
            direction=vm.risk_direction,
            delta=vm.trend_delta,
            required=(cov.required_ok, cov.required_total),
            optional=(cov.optional_available, cov.optional_total),
            last_updated=vm.last_updated or "",
        ),
        unsafe_allow_html=True,
    )
    with st.expander("主要风险驱动因素（引擎贡献分解）", expanded=False):
        st.markdown(drivers_html(vm.top_drivers), unsafe_allow_html=True)
        st.markdown(
            '<div class="mg-metric-note">贡献分值为确定性引擎输出（文档 04）。'
            "静态驱动因素来自冻结的区域易灾基线。</div>",
            unsafe_allow_html=True,
        )


def _render_agents(vm: OverviewViewModel) -> None:
    st.markdown(
        card_title("智能体协作", accent="✦"), unsafe_allow_html=True
    )
    if not vm.agents:
        st.markdown(
            empty_state(
                "智能体运行状态将在第一次完成风险扫描后显示在此处。"
            ),
            unsafe_allow_html=True,
        )
        return

    professionals = [a for a in vm.agents if not a.is_ai_layer]
    ai_layer = [a for a in vm.agents if a.is_ai_layer]

    cols = st.columns(len(professionals) if professionals else 1)
    for col, card in zip(cols, professionals):
        col.markdown(agent_card_html(card), unsafe_allow_html=True)

    st.markdown(flow_arrow(), unsafe_allow_html=True)

    if ai_layer:
        cols2 = st.columns(len(ai_layer))
        for col, card in zip(cols2, ai_layer):
            col.markdown(agent_card_html(card), unsafe_allow_html=True)

    st.markdown(
        '<div class="mg-metric-note">专业智能体 → 风险综合智能体 → '
        "评审智能体复核。此处仅显示状态、置信度与证据数量 — "
        "完整结构化输出见情报中心。</div>",
        unsafe_allow_html=True,
    )


def _render_trend(vm: OverviewViewModel) -> None:
    st.markdown(
        card_title("风险趋势 · 最近扫描", accent="◫"), unsafe_allow_html=True
    )
    if not vm.has_result:
        st.markdown(
            empty_state("尚无扫描历史 — 第一次扫描后开始形成趋势。"),
            unsafe_allow_html=True,
        )
        return

    if vm.trend_status in ("NO_HISTORY", "INSUFFICIENT_HISTORY"):
        st.markdown(
            empty_state(
                "历史数据不足，完成更多扫描后将形成趋势。"
                "历史从不伪造或预填。"
            ),
            unsafe_allow_html=True,
        )
    for tp in vm.trend_points:
        level_color = theme.risk_color(tp.risk_level)
        when = tp.created_at.replace("T", " ")[:16]
        badge = (f' <span style="font-size:10px;color:{theme.TEXT_DIM};">'
                 f'[{esc(scan_mode_label(tp.scan_mode))}]</span>')
        st.markdown(
            f'<div class="mg-trend-row">'
            f'<span class="mg-trend-k">{esc(when)} UTC{badge}</span>'
            f'<span><b style="color:{level_color};">{tp.risk_index_rounded:.2f}</b>'
            f' &nbsp;{chip(risk_label(tp.risk_level), level_color, small=True)}</span></div>',
            unsafe_allow_html=True,
        )

    st.markdown(
        f'<div class="mg-metric-note">最近扫描：<b>{esc(status_label(vm.last_scan_status) if vm.last_scan_status else "—")}</b>'
        f' · 模式 {esc(scan_mode_label(vm.last_scan_mode) if vm.last_scan_mode else "—")}'
        f' · 运行编号 {esc((vm.run_id or "—")[:34])}</div>',
        unsafe_allow_html=True,
    )


def _render_evidence(vm: OverviewViewModel) -> None:
    st.markdown(
        card_title("证据 · 数据覆盖", accent="▤"), unsafe_allow_html=True
    )
    cov = vm.coverage
    if not vm.has_result:
        st.markdown(
            empty_state("证据覆盖将在第一次完成扫描后显示。"),
            unsafe_allow_html=True,
        )
        return

    req = f"{cov.required_ok} / {cov.required_total}" if cov.required_ok is not None else "—"
    opt = (
        f"{cov.optional_available} / {cov.optional_total}"
        if cov.optional_available is not None else "—"
    )
    st.markdown(
        f'<div class="mg-trend-row"><span class="mg-trend-k">必需数据</span>'
        f'<span><b>{esc(req)}</b></span></div>'
        f'<div class="mg-trend-row"><span class="mg-trend-k">可选数据</span>'
        f'<span><b>{esc(opt)}</b></span></div>',
        unsafe_allow_html=True,
    )

    if cov.point_quality:
        chips = " ".join(
            chip(f"{point_id_label(pid)}: {quality_label(q)}",
                 theme.GREEN if q == "FRESH" else theme.ORANGE, small=True)
            for pid, q in sorted(cov.point_quality.items())
        )
        st.markdown(f'<div style="margin-top:8px;">{chips}</div>', unsafe_allow_html=True)

    if cov.satellite_pipeline_available is False:
        st.markdown(
            empty_state("本轮扫描无可用新卫星影像。"
                        "可选数据源 — 不影响扫描有效性。"),
            unsafe_allow_html=True,
        )
    if cov.optional_missing:
        from frontend.display import optional_source_key_label

        st.markdown(
            '<div class="mg-metric-note">缺失可选数据源：'
            + esc("、".join(optional_source_key_label(x)
                           for x in cov.optional_missing))
            + "</div>",
            unsafe_allow_html=True,
        )

    with st.expander("本轮扫描使用的证据编号", expanded=False):
        any_ev = False
        for card in vm.agents:
            if card.evidence_ids:
                any_ev = True
                st.markdown(
                    f'<div style="font-size:11.5px;color:{theme.TEXT_DIM};'
                    f'margin:6px 0 3px 0;">{esc(card.name_zh)}</div>'
                    + evidence_chips_html(card.evidence_ids),
                    unsafe_allow_html=True,
                )
        if not any_ev:
            st.markdown(empty_state("本轮扫描无证据记录。"),
                        unsafe_allow_html=True)
        st.markdown(
            '<div class="mg-metric-note">仅列出风险监测运行实际记录的证据 — '
            "UI 从不虚构证据。</div>",
            unsafe_allow_html=True,
        )


def _render_quick_entries() -> None:
    st.markdown(card_title("快速入口", accent="➤"), unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(
            '<div class="mg-entry-title">历史验证</div>'
            '<div class="mg-entry-desc">基于冻结的 2026-08-26 吉隆案例开展'
            "研究验证 — 仅使用灾前证据。</div>",
            unsafe_allow_html=True,
        )
        st.button("进入历史验证 →", use_container_width=True,
                  key="mg_quick_replay",
                  on_click=layout.navigate_to, args=("historical_replay",))
    with c2:
        st.markdown(
            '<div class="mg-entry-title">风险监测</div>'
            '<div class="mg-entry-desc">对当前监测区域执行实时风险扫描，'
            "并查看本轮变化。</div>",
            unsafe_allow_html=True,
        )
        st.button("进入风险监测 →", use_container_width=True,
                  key="mg_quick_watch",
                  on_click=layout.navigate_to, args=("risk_watch",))


def render(vm: OverviewViewModel) -> None:
    """Render the full Overview page inside bordered panels."""
    if vm.limitations:
        from frontend.display import limitation_label

        with st.expander(
            f"最近扫描记录的科学局限（{len(vm.limitations)}）",
            expanded=False,
        ):
            for note in vm.limitations:
                st.markdown(f"- {esc(limitation_label(str(note)))}",
                            unsafe_allow_html=False)

    row1_left, row1_right = st.columns([2.15, 1], gap="medium")
    with row1_left:
        with st.container(border=True):
            _render_map(vm)
    with row1_right:
        with st.container(border=True):
            _render_current_risk(vm)

    row2_left, row2_right = st.columns([1.55, 1], gap="medium")
    with row2_left:
        with st.container(border=True):
            _render_agents(vm)
    with row2_right:
        with st.container(border=True):
            _render_trend(vm)

    row3_left, row3_right = st.columns([1, 1.55], gap="medium")
    with row3_left:
        with st.container(border=True):
            _render_quick_entries()
    with row3_right:
        with st.container(border=True):
            _render_evidence(vm)
