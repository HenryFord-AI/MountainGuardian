"""
MountainGuardian G04B – Intelligence Center / 情报中心 page.

Frozen purpose (doc 05 §32–§37, gate G04B §11): AI system observability,
explainability, evidence provenance, audit & safety. NOT a chatbot — no
chat input, no autonomous-network visuals.

Tabs (default: Agent Workspace):
  1. Agent Workspace — the frozen DAG: three professional agents →
     Risk Synthesizer → Critic, plus per-agent structured detail;
  2. Evidence Center — category tabs over real EvidenceItem provenance,
     honest empty states where a category has no evidence;
  3. Audit & Safety — model runtime, descriptive safety-control states,
     a lightweight recent audit log, and the richer Critic view.

Never shown: chain of thought, hidden reasoning, system prompts, provider
secrets. Never offered: a control that disables any safety guard.
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
    latency = f"{agent.latency_ms} ms" if agent.latency_ms is not None else "—"
    fallback = (' <span style="color:%s;font-size:10px;font-weight:700;">'
                'FALLBACK</span>' % theme.ORANGE) if agent.fallback_used else ""
    model = ('model-output' if agent.is_model_output else 'deterministic fallback')
    return (
        f'<div class="mg-agent-card{" mg-agent-ai" if agent.is_ai_layer else ""}">'
        f'<span class="mg-agent-name">{esc(agent.name_en)}</span>{fallback}'
        f'<div class="mg-agent-zh">{esc(agent.name_zh)}</div>'
        f'<div class="mg-agent-meta">'
        f'<span style="color:{color};font-weight:700;">● '
        f'{esc(agent.status.replace("_", " ").title())}</span><br/>'
        f'Model {esc(agent.model_id)}<br/>'
        f'Confidence <b>{esc(conf)}</b> · {len(agent.evidence_ids)} evidence<br/>'
        f'Latency {esc(latency)} · {esc(model)}</div></div>'
    )


def _render_workspace(vm: IntelligenceViewModel) -> None:
    st.markdown(
        card_title("Multi-Agent Workflow · 多智能体分析工作流", accent="✦")
        + '<div class="mg-metric-note">三个专业智能体并行分析 → 风险综合智能体 → '
        "质检复核智能体（冻结 DAG，非自治递归网络）</div>",
        unsafe_allow_html=True,
    )
    if not vm.has_run:
        st.markdown(
            empty_state(
                "尚无运行记录。完成一次 Risk Scan 或 Historical Replay 后，"
                "Agent 工作区将显示真实运行状态。"
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

    st.markdown(card_title("Agent Detail · 智能体详情", accent="›"),
                unsafe_allow_html=True)
    options = [a.name_en for a in vm.agents]
    choice = st.selectbox(
        "Select agent", options, index=0, label_visibility="collapsed",
        key="mg_ic_agent_select",
    )
    agent = next(a for a in vm.agents if a.name_en == choice)
    left, right = st.columns([1.3, 1], gap="medium")
    with left:
        findings = "".join(
            f'<div class="mg-issue-row">• {esc(f)}</div>' for f in agent.findings[:6]
        ) or empty_state("No structured findings recorded for this agent.")
        st.markdown(
            f'<div class="mg-panel-alt">{card_title("Key Findings · 关键发现")}'
            f'{findings}</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="mg-panel-alt" style="margin-top:10px;">'
            f'{card_title("Evidence Used · 使用证据")}'
            f'{evidence_chips_html(agent.evidence_ids) or empty_state("No evidence ids recorded.")}'
            f'</div>',
            unsafe_allow_html=True,
        )
    with right:
        st.markdown(
            f'<div class="mg-panel-alt">{card_title("Input / Gaps · 输入与缺口")}'
            + kv_row("Status", agent.status)
            + kv_row("Provider status", agent.provider_status)
            + kv_row("Model", agent.model_id)
            + kv_row("Input summary",
                     f"{len(agent.evidence_ids)} authorized evidence ids")
            + (
                '<div class="mg-metric-note">Missing data: '
                + esc("; ".join(agent.missing_data[:4])) + "</div>"
                if agent.missing_data else ""
            )
            + (
                '<div class="mg-metric-note">Limitations: '
                + esc("; ".join(agent.limitations[:3])) + "</div>"
                if agent.limitations else ""
            )
            + (
                '<div class="mg-metric-note" style="color:%s;">Quarantined by '
                "injection guard: %s</div>" % (theme.ORANGE,
                                               esc(", ".join(agent.quarantined)))
                if agent.quarantined else ""
            )
            + "</div>",
            unsafe_allow_html=True,
        )
    st.markdown(
        '<div class="mg-metric-note">仅展示结构化输出、Evidence IDs 与审计字段 — '
        "不展示 chain of thought、系统提示词或私有推理痕迹。</div>",
        unsafe_allow_html=True,
    )


def _render_evidence_center(vm: IntelligenceViewModel) -> None:
    st.markdown(
        card_title("Evidence Center · 证据中心", accent="▤")
        + '<div class="mg-metric-note">Evidence 溯源是核心产品能力：来源、观测时间、'
        "相位、质量与使用方智能体均可追溯。</div>",
        unsafe_allow_html=True,
    )
    labels = [f"{en} · {zh}" for en, zh, _ in vm.evidence_categories]
    tabs = st.tabs(labels)
    for tab, (label_en, label_zh, items) in zip(tabs, vm.evidence_categories):
        with tab:
            if not items:
                st.markdown(
                    empty_state(
                        f"{label_en}：当前 Case Pack / 运行中无该类别证据。"
                        " Optional source — absence is shown, never hidden."
                    ),
                    unsafe_allow_html=True,
                )
                continue
            for e in items:
                used = ", ".join(e.used_by) if e.used_by else "none (validation only)"
                st.markdown(
                    components.evidence_row_html(
                        e.evidence_id, e.evidence_type, e.source, e.observed,
                        e.phase.replace("_", " ").upper(), e.quality,
                        note=f"{e.source_reference} · {e.raw_or_derived} · used by: {used}",
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
        st.markdown(card_title("Model Runtime · 模型运行状态", accent="◈"),
                    unsafe_allow_html=True)
        runtime_color = {
            "CONNECTED": theme.GREEN, "FALLBACK": theme.ORANGE,
            "DEGRADED": theme.ORANGE, "OFFLINE": theme.RED,
        }.get(vm.model_runtime, theme.TEXT_DIM)
        st.markdown(
            kv_row("Runtime", vm.model_runtime, runtime_color)
            + kv_row("Run ID", vm.run_id or "—")
            + kv_row("Created", (vm.created_at or "—").replace("T", " ")[:19])
            + kv_row("Scan status", vm.scan_status or "—")
            + kv_row("Duration",
                     f"{vm.duration_s} s" if vm.duration_s is not None else "—"),
            unsafe_allow_html=True,
        )
        if vm.fallback_mode:
            st.markdown('<div class="mg-fallback">AI Runtime · Fallback Mode</div>',
                        unsafe_allow_html=True)
            st.caption(
                "Deterministic results remain authoritative; AI explanation "
                "layers ran on labeled deterministic fallbacks."
            )
    with c2:
        st.markdown(card_title("Safety Controls · 安全控制", accent="▣"),
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
            "安全保护的控件（doc 06 §76–§77）。</div>",
            unsafe_allow_html=True,
        )

    st.markdown(card_title("Audit Log · 最近审计", accent="≣"),
                unsafe_allow_html=True)
    st.markdown(
        table_html(
            ("Time", "Run ID", "Agent / Stage", "Model", "Status", "Latency",
             "Fallback"),
            vm.audit_rows,
        ),
        unsafe_allow_html=True,
    )
    with st.expander("Run history (persisted snapshots)", expanded=False):
        st.markdown(
            table_html(
                ("Run ID", "Created (UTC)", "Status", "Mode"),
                vm.run_history,
            ),
            unsafe_allow_html=True,
        )

    st.markdown(card_title("Critic Review · 质检复核（完整视图）", accent="◆"),
                unsafe_allow_html=True)
    if vm.critic is None:
        st.markdown(empty_state("No critic record in the latest run."),
                    unsafe_allow_html=True)
    else:
        st.markdown(
            critic_panel_html(
                vm.critic.review_result, vm.critic.severity,
                vm.critic.issues, vm.critic.scientific_limitations,
                corrections=vm.critic.required_corrections,
                checks=vm.critic.programmatic_checks,
                attestation=(
                    "Risk Index attestation: before "
                    f"{vm.critic.risk_index_before} / after "
                    f"{vm.critic.risk_index_after} — the Critic never modifies "
                    "the deterministic index."
                ),
            ),
            unsafe_allow_html=True,
        )
    st.markdown(
        scientific_note(
            "Intelligence Center 用于解释系统如何工作：可观测性、可解释性、"
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
                "Intelligence Center view model could not be assembled. "
                "The page shows no data rather than fabricated values."
            )
            st.caption(f"Detail: {type(exc).__name__}: {exc}")
        return

    st.markdown(
        f'<div style="display:flex;justify-content:space-between;'
        f'align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:6px;">'
        f'<div style="font-size:16px;font-weight:750;">AI 系统可解释性与审计中心'
        f'</div><div>{chip(vm.run_id or "no run yet", theme.CYAN, small=True)} '
        f'{chip(vm.model_runtime, theme.GREEN if vm.model_runtime == "CONNECTED" else theme.ORANGE, small=True)}'
        f'</div></div>',
        unsafe_allow_html=True,
    )

    tab_ws, tab_ev, tab_audit = st.tabs(
        ["Agent Workspace · 智能体工作区",
         "Evidence Center · 证据中心",
         "Audit & Safety · 审计与安全"]
    )
    with tab_ws:
        _render_workspace(vm)
    with tab_ev:
        _render_evidence_center(vm)
    with tab_audit:
        _render_audit_safety(vm)
