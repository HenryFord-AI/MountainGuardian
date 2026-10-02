"""
MountainGuardian G04B – Intelligence Center / 情报中心 page.

Frozen purpose (doc 05 §32–§37, gate G04B §11): AI system observability,
explainability, evidence provenance, audit & safety. NOT a chatbot — no
chat input, no autonomous-network visuals.

Tabs (default: 智能体工作区):
  1. 智能体工作区 — the frozen DAG: three professional agents →
     Risk Synthesizer → Critic, plus per-agent structured detail;
  2. 证据中心 — category tabs over real EvidenceItem provenance,
     honest empty states where a category has no evidence;
  3. 审计与安全 — model runtime, descriptive safety-control states,
     a lightweight recent audit log, and the richer Critic view.

Never shown: chain of thought, hidden reasoning, system prompts, provider
secrets. Never offered: a control that disables any safety guard.

G05C (doc 08): visible page language is Chinese; Evidence IDs, Run IDs,
model IDs (deepseek-flash) and brand names stay verbatim per allowlist.
"""

from __future__ import annotations

import streamlit as st

from frontend import components, theme
from frontend.components import (
    card_title,
    chip,
    critic_panel_html,
    empty_state,
    esc,
    evidence_chips_html,
    flow_arrow_right,
    kv_row,
    safety_rows_html,
    scientific_note,
    table_html,
)
from frontend.display import (
    agent_id_label,
    narrative_label,
    raw_derived_label,
    scan_mode_label,
    status_label,
)
from frontend.intel_viewmodels import (
    IntelligenceViewModel,
    build_intelligence_viewmodel,
)

_STATE_COLORS = {
    "GREEN": theme.GREEN, "ORANGE": theme.ORANGE, "RED": theme.RED,
    "CYAN": theme.CYAN, "PURPLE": theme.PURPLE, "DIM": theme.TEXT_DIM,
}


def _agent_tile(agent) -> str:
    color = (theme.critic_color(agent.status) if agent.key == "critic"
             else theme.agent_status_color(agent.status))
    conf = (f"{agent.confidence:.2f}"
            if isinstance(agent.confidence, (int, float)) else "—")
    latency = f"{agent.latency_ms} 毫秒" if agent.latency_ms is not None else "—"
    fallback = (' <span style="color:%s;font-size:10px;font-weight:700;">'
                '回退</span>' % theme.ORANGE) if agent.fallback_used else ""
    model = '模型输出' if agent.is_model_output else '确定性回退'
    return (
        f'<div class="mg-agent-card{" mg-agent-ai" if agent.is_ai_layer else ""}">'
        f'<span class="mg-agent-name">{esc(agent.name_zh)}</span>{fallback}'
        f'<div class="mg-agent-meta">'
        f'<span style="color:{color};font-weight:700;">● '
        f'{esc(status_label(agent.status))}</span><br/>'
        f'模型 {esc(agent.model_id)}<br/>'
        f'置信度 <b>{esc(conf)}</b> · {len(agent.evidence_ids)} 条证据<br/>'
        f'执行耗时 {esc(latency)} · {esc(model)}</div></div>'
    )


def _render_workspace(vm: IntelligenceViewModel) -> None:
    st.markdown(
        card_title("多智能体分析工作流", accent="✦")
        + '<div class="mg-metric-note">三个专业智能体并行分析 → 风险综合智能体 → '
        "评审智能体（冻结 DAG，非自治递归网络）</div>",
        unsafe_allow_html=True,
    )
    if not vm.has_run:
        st.markdown(
            empty_state(
                "尚无运行记录。完成一次风险扫描或历史验证后，"
                "智能体工作区将显示真实运行状态。"
            ),
            unsafe_allow_html=True,
        )
        return
    professionals = [a for a in vm.agents if not a.is_ai_layer]
    ai_layer = [a for a in vm.agents if a.is_ai_layer]
    cols = st.columns([1, 1, 1, 0.35, 1.1, 0.35, 1.1])
    for i, agent in enumerate(professionals):
        with cols[i]:
            st.markdown(_agent_tile(agent), unsafe_allow_html=True)
    cols[3].markdown(flow_arrow_right(), unsafe_allow_html=True)
    synth = next((a for a in ai_layer if a.key == "synthesizer"), None)
    critic = next((a for a in ai_layer if a.key == "critic"), None)
    if synth is not None:
        with cols[4]:
            st.markdown(_agent_tile(synth), unsafe_allow_html=True)
    cols[5].markdown(flow_arrow_right(), unsafe_allow_html=True)
    if critic is not None:
        with cols[6]:
            st.markdown(_agent_tile(critic), unsafe_allow_html=True)

    st.markdown(card_title("智能体详情", accent="›"),
                unsafe_allow_html=True)
    options = [a.name_zh for a in vm.agents]
    choice = st.selectbox(
        "选择智能体", options, index=0, label_visibility="collapsed",
        key="mg_ic_agent_select",
    )
    agent = next(a for a in vm.agents if a.name_zh == choice)
    left, right = st.columns([1.3, 1], gap="medium")
    with left:
        findings = "".join(
            f'<div class="mg-issue-row">• {esc(narrative_label(f))}</div>'
            for f in agent.findings[:6]
        ) or empty_state("该智能体无结构化关键发现记录。")
        st.markdown(
            f'<div class="mg-panel-alt">{card_title("关键发现")}'
            f'{findings}</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="mg-panel-alt" style="margin-top:10px;">'
            f'{card_title("使用证据")}'
            f'{evidence_chips_html(agent.evidence_ids) or empty_state("无证据编号记录。")}'
            f'</div>',
            unsafe_allow_html=True,
        )
    with right:
        st.markdown(
            f'<div class="mg-panel-alt">{card_title("输入与缺口")}'
            + kv_row("状态", status_label(agent.status))
            + kv_row("模型服务状态", status_label(agent.provider_status))
            + kv_row("模型", agent.model_id)
            + kv_row("输入摘要", agent.input_summary or "—")
            + (
                '<div class="mg-metric-note">缺失数据：'
                + esc("；".join(narrative_label(x) for x in agent.missing_data[:4]))
                + "</div>"
                if agent.missing_data else ""
            )
            + (
                '<div class="mg-metric-note">局限：'
                + esc("；".join(narrative_label(x) for x in agent.limitations[:3]))
                + "</div>"
                if agent.limitations else ""
            )
            + (
                '<div class="mg-metric-note" style="color:%s;">'
                "提示词注入防护隔离证据：%s</div>" % (theme.ORANGE,
                                                       esc("、".join(agent.quarantined)))
                if agent.quarantined else ""
            )
            + "</div>",
            unsafe_allow_html=True,
        )
    st.markdown(
        '<div class="mg-metric-note">仅展示结构化输出、证据编号与审计字段 — '
        "不展示思维链、系统提示词或私有推理痕迹。</div>",
        unsafe_allow_html=True,
    )


def _render_evidence_center(vm: IntelligenceViewModel) -> None:
    st.markdown(
        card_title("证据中心", accent="▤")
        + '<div class="mg-metric-note">证据溯源是核心产品能力：来源、观测时间、'
        "相位、质量与使用方智能体均可追溯。</div>",
        unsafe_allow_html=True,
    )
    labels = [zh for _en, zh, _items in vm.evidence_categories]
    tabs = st.tabs(labels)
    for tab, (label_en, label_zh, items) in zip(tabs, vm.evidence_categories):
        with tab:
            if not items:
                st.markdown(
                    empty_state(
                        f"{label_zh}：当前案例包 / 运行中无该类别证据。"
                        "可选数据源 — 缺失会显式展示，绝不隐藏。"
                    ),
                    unsafe_allow_html=True,
                )
                continue
            for e in items:
                used = ("、".join(agent_id_label(u) for u in e.used_by)
                        if e.used_by else "无（仅用于验证）")
                st.markdown(
                    components.evidence_row_html(
                        e.evidence_id, e.evidence_type, e.source, e.observed,
                        e.phase, e.quality,
                        note=f"{e.source_reference} · "
                             f"{raw_derived_label(e.raw_or_derived)} · "
                             f"使用方：{used}",
                    ),
                    unsafe_allow_html=True,
                )
                if e.summary:
                    st.markdown(
                        f'<div class="mg-ev-meta" style="padding-left:2px;">'
                        f'{esc(e.summary[:160])}</div>',
                        unsafe_allow_html=True,
                    )


def _render_audit_safety(vm: IntelligenceViewModel) -> None:
    c1, c2 = st.columns(2, gap="medium")
    with c1:
        st.markdown(card_title("模型运行状态", accent="◈"),
                    unsafe_allow_html=True)
        runtime_color = {
            "CONNECTED": theme.GREEN, "FALLBACK": theme.ORANGE,
            "DEGRADED": theme.ORANGE, "OFFLINE": theme.RED,
        }.get(vm.model_runtime, theme.TEXT_DIM)
        st.markdown(
            kv_row("运行状态", status_label(vm.model_runtime), runtime_color)
            + kv_row("运行编号", vm.run_id or "—")
            + kv_row("生成时间", (vm.created_at or "—").replace("T", " ")[:19])
            + kv_row("扫描状态", status_label(vm.scan_status) if vm.scan_status else "—")
            + kv_row("执行耗时",
                     f"{vm.duration_s} 秒" if vm.duration_s is not None else "—"),
            unsafe_allow_html=True,
        )
        if vm.fallback_mode:
            st.markdown('<div class="mg-fallback">AI 运行时 · 回退模式</div>',
                        unsafe_allow_html=True)
            st.caption(
                "确定性结果仍然权威有效；AI 解释层使用了带标注的"
                "确定性回退。"
            )
    with c2:
        st.markdown(card_title("安全控制", accent="▣"),
                    unsafe_allow_html=True)
        st.markdown(
            safety_rows_html(tuple(
                (name, state, _STATE_COLORS.get(color_key, theme.TEXT_DIM), detail)
                for name, state, color_key, detail in vm.safety_rows
            )),
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="mg-metric-note">上述为只读状态指示：产品不提供任何可关闭'
            "安全保护的控件（文档 06 §76–§77）。</div>",
            unsafe_allow_html=True,
        )

    st.markdown(card_title("最近审计", accent="≣"),
                unsafe_allow_html=True)
    st.markdown(
        table_html(
            ("时间", "运行编号", "智能体 / 阶段", "模型", "状态", "执行耗时",
             "回退"),
            tuple(
                (ts, rid, agent_name, model, status_label(status), latency, fb)
                for ts, rid, agent_name, model, status, latency, fb
                in vm.audit_rows
            ),
        ),
        unsafe_allow_html=True,
    )
    with st.expander("运行历史（已持久化快照）", expanded=False):
        st.markdown(
            table_html(
                ("运行编号", "生成时间（UTC）", "状态", "模式"),
                tuple(
                    (rid, created, status_label(status), scan_mode_label(mode))
                    for rid, created, status, mode in vm.run_history
                ),
            ),
            unsafe_allow_html=True,
        )

    st.markdown(card_title("评审复核（完整视图）", accent="◆"),
                unsafe_allow_html=True)
    if vm.critic is None:
        st.markdown(empty_state("最近一次运行无评审记录。"),
                    unsafe_allow_html=True)
    else:
        st.markdown(
            critic_panel_html(
                vm.critic.review_result, vm.critic.severity,
                vm.critic.issues, vm.critic.scientific_limitations,
                corrections=vm.critic.required_corrections,
                checks=vm.critic.programmatic_checks,
                attestation=(
                    "风险指数核验：评审前 "
                    f"{vm.critic.risk_index_before} / 评审后 "
                    f"{vm.critic.risk_index_after} — 评审智能体从不修改"
                    "确定性风险指数。"
                ),
            ),
            unsafe_allow_html=True,
        )
    st.markdown(
        scientific_note(
            "情报中心用于解释系统如何工作：可观测性、可解释性、"
            "证据溯源与审计安全。非聊天机器人入口。"
        ),
        unsafe_allow_html=True,
    )


def render() -> None:
    """Render the Intelligence Center (three frozen tabs)."""
    try:
        vm = build_intelligence_viewmodel()
    except Exception as exc:
        with st.container(border=True):
            st.error(
                "情报中心视图模型无法组装。页面不显示任何数据，"
                "而不是显示伪造数值。"
            )
            st.caption(f"详情：{type(exc).__name__}: {exc}")
        return

    st.markdown(
        f'<div style="display:flex;justify-content:space-between;'
        f'align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:6px;">'
        f'<div style="font-size:16px;font-weight:750;">AI 系统可解释性与审计中心'
        f'</div><div>{chip(vm.run_id or "尚无运行", theme.CYAN, small=True)} '
        f'{chip(status_label(vm.model_runtime), theme.GREEN if vm.model_runtime == "CONNECTED" else theme.ORANGE, small=True)}'
        f'</div></div>',
        unsafe_allow_html=True,
    )

    tab_ws, tab_ev, tab_audit = st.tabs(
        ["智能体工作区", "证据中心", "审计与安全"]
    )
    with tab_ws:
        _render_workspace(vm)
    with tab_ev:
        _render_evidence_center(vm)
    with tab_audit:
        _render_audit_safety(vm)
