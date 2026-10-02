"""
MountainGuardian G04B – Historical Replay / 历史验证 page.

Frozen positioning (doc 05 §15–§22, gate G04B §9): Research Validation —
"If MountainGuardian only uses information available before the event,
what pre-existing risk conditions can the multi-agent system identify?"

Page structure (doc 05 §16):
  A. Case header            B. 灾前阶段 / 事件发生 / 灾后验证 timeline
  C. Pre-event evidence     D. Multi-Agent analysis (3 agents → Synthesizer
                             → Critic)
  E. Baseline Susceptibility result   F. Critic card
  G. Post-event validation  H. Scientific limitations

Scientific boundaries enforced here:
  * pre-event evidence panel renders ONLY Stage-A authorized evidence;
    post-event evidence appears ONLY in the validation section;
  * the 91/100 HIGH value is consumed from the deterministic engine result
    and always labeled 基线易感性指数 — 不是事件发生概率; never recomputed,
    never a percentage, never accuracy;
  * no chain of thought, no prompts, no hidden reasoning — structured
    findings and evidence ids only.

G05C (doc 08): visible page language is Chinese; Evidence IDs, Run ID and
brand/technical identifiers stay verbatim per the frozen allowlist.
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
    evidence_row_html,
    flow_arrow,
    kv_row,
    ring_gauge_html,
    scientific_note,
    timeline_html,
)
from frontend.display import (
    agreement_label,
    narrative_label,
    risk_label,
    status_label,
)
from frontend.replay_viewmodels import (
    EVIDENCE_CATEGORIES,
    HistoricalReplayViewModel,
    build_historical_replay_viewmodel,
)

_STAGE_COLORS = {"CYAN": theme.CYAN, "ORANGE": theme.ORANGE,
                 "PURPLE": theme.PURPLE}


def _render_case_header(vm: HistoricalReplayViewModel) -> None:
    st.markdown(
        f'<div style="display:flex;justify-content:space-between;'
        f'align-items:flex-start;gap:16px;flex-wrap:wrap;">'
        f'<div><div style="font-size:20px;font-weight:750;">'
        f'{esc(vm.case_name)}</div>'
        f'<div style="font-size:12.5px;color:{theme.TEXT_DIM};margin-top:4px;">'
        f'{esc(vm.location)} · 事件日期 {esc(vm.event_date)} · 案例编号 '
        f'{esc(vm.case_id)}</div></div>'
        f'<div>{chip("研究验证", theme.PURPLE)} '
        f'{chip("历史验证", theme.CYAN, small=True)}</div></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        timeline_html(tuple(
            (en, zh, when, _STAGE_COLORS.get(color_key, theme.TEXT_DIM), note)
            for en, zh, when, color_key, note in vm.timeline
        )),
        unsafe_allow_html=True,
    )
    st.markdown(
        scientific_note(
            "灾前分析仅使用事件发生前可获得的公开数据；灾后资料只用于验证，"
            "从不进入灾前分析（灾前分析与灾后验证严格分离）。"
        ),
        unsafe_allow_html=True,
    )


def _render_pre_event_evidence(vm: HistoricalReplayViewModel) -> None:
    st.markdown(
        card_title("灾前证据", accent="▤")
        + f'<div class="mg-metric-note">灾前阶段输入证据 · '
        f'{len(vm.pre_event_evidence)} 条 · 仅灾前相位</div>',
        unsafe_allow_html=True,
    )
    if not vm.pre_event_evidence:
        st.markdown(empty_state("案例包中未记录灾前证据。"),
                    unsafe_allow_html=True)
        return
    for label_en, label_zh, types in EVIDENCE_CATEGORIES:
        items = [e for e in vm.pre_event_evidence if e.type_label in types]
        if not items:
            continue
        st.markdown(
            f'<div style="margin:10px 0 2px 0;font-size:11px;font-weight:700;'
            f'letter-spacing:0.12em;color:{theme.CYAN};">'
            f'{esc(label_zh)}（{len(items)}）</div>',
            unsafe_allow_html=True,
        )
        for e in items:
            st.markdown(
                evidence_row_html(
                    e.evidence_id, e.type_label, e.source, e.observed,
                    e.phase, e.quality,
                    note=(e.summary[:90] + "…") if len(e.summary) > 90 else e.summary,
                ),
                unsafe_allow_html=True,
            )
    st.markdown(
        '<div class="mg-metric-note">证据编号与相位来自冻结案例包；'
        "灾后相位证据不在本面板显示。</div>",
        unsafe_allow_html=True,
    )


def _agent_block(agent) -> str:
    color = (theme.critic_color(agent.status) if agent.key == "critic"
             else theme.agent_status_color(agent.status))
    conf = (f"{agent.confidence:.2f}"
            if isinstance(agent.confidence, (int, float)) else "—")
    fallback = (' <span style="color:%s;font-size:10px;font-weight:700;">'
                '回退</span>' % theme.ORANGE) if agent.fallback_used else ""
    findings = "".join(
        f'<div class="mg-issue-row">• {esc(narrative_label(f))}</div>'
        for f in agent.findings[:5]
    ) or empty_state("无结构化关键发现记录。")
    missing = ""
    if agent.missing_data:
        missing = (
            '<div class="mg-metric-note">缺失数据：'
            + esc("；".join(agent.missing_data[:3])) + "</div>"
        )
    limits = ""
    if agent.limitations:
        limits = (
            '<div class="mg-metric-note">局限：'
            + esc("；".join(agent.limitations[:2])) + "</div>"
        )
    return (
        f'<div class="mg-agent-card{" mg-agent-ai" if agent.is_ai_layer else ""}">'
        f'<span class="mg-agent-name">{esc(agent.name_zh)}</span>{fallback}'
        f'<div class="mg-agent-meta"><span style="color:{color};font-weight:700;">'
        f'● {esc(status_label(agent.status))}</span><br/>'
        f'置信度 <b>{esc(conf)}</b> · {len(agent.evidence_ids)} 条证据</div>'
        f'<div style="margin-top:8px;">{findings}</div>'
        f'<div style="margin-top:6px;">{evidence_chips_html(agent.evidence_ids)}</div>'
        f"{missing}{limits}</div>"
    )


def _render_agents(vm: HistoricalReplayViewModel) -> None:
    st.markdown(
        card_title("多智能体分析", accent="✦")
        + '<div class="mg-metric-note">仅基于灾前数据 · 三个专业智能体 → '
        "风险综合智能体 → 评审智能体（冻结 DAG，非自治网络）</div>",
        unsafe_allow_html=True,
    )
    cols = st.columns(3)
    for col, agent in zip(cols, vm.agents):
        col.markdown(_agent_block(agent), unsafe_allow_html=True)
    st.markdown(flow_arrow(), unsafe_allow_html=True)
    if vm.synthesizer is not None:
        st.markdown(_agent_block(vm.synthesizer), unsafe_allow_html=True)
        if vm.synthesis_summary:
            st.markdown(
                f'<div class="mg-metric-note">综合结论：{esc(narrative_label(vm.synthesis_summary)[:220])}'
                f' · 智能体一致性：{esc(agreement_label(vm.synthesis_agreement))}</div>',
                unsafe_allow_html=True,
            )
    st.markdown(flow_arrow(), unsafe_allow_html=True)
    if vm.critic is not None:
        st.markdown(
            critic_panel_html(
                vm.critic.review_result, vm.critic.severity,
                vm.critic.issues[:4], vm.critic.scientific_limitations[:4],
                attestation=(
                    "评审智能体不修改风险指数：评审前 "
                    f"{vm.critic.risk_index_before} / 评审后 "
                    f"{vm.critic.risk_index_after}"
                ),
            ),
            unsafe_allow_html=True,
        )
    else:
        st.markdown(empty_state("本回放运行无评审记录。"),
                    unsafe_allow_html=True)
    st.markdown(
        '<div class="mg-metric-note">仅展示结构化结论与证据编号 — '
        "不展示思维链、内部推理或系统提示词。</div>",
        unsafe_allow_html=True,
    )


def _render_risk_result(vm: HistoricalReplayViewModel) -> None:
    st.markdown(
        card_title("风险评估结果", accent="◉")
        + '<div class="mg-metric-note">灾前分析（灾前阶段冻结结果）</div>',
        unsafe_allow_html=True,
    )
    color = theme.risk_color(vm.risk_level)
    st.markdown(
        f'<div class="mg-ring-row">{ring_gauge_html(vm.risk_index, color)}'
        f'<div>{chip(risk_label(vm.risk_level) if vm.risk_level else "未知", color)}'
        f'<div style="margin-top:10px;font-size:12px;font-weight:700;">'
        f'基线易感性指数</div>'
        f'<div class="mg-metric-note" style="color:{theme.ORANGE};">'
        f'⚠ 不是事件发生概率</div></div></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        card_title("主要风险驱动因素"),
        unsafe_allow_html=True,
    )
    for i, (name, contribution) in enumerate(vm.top_drivers, start=1):
        st.markdown(
            f'<div class="mg-trend-row"><span><span style="color:'
            f'{theme.TEXT_DIM};">{i:02d}</span> {esc(name)}</span>'
            f'<b>+{contribution:.1f}</b></div>',
            unsafe_allow_html=True,
        )
    with st.expander("确定性因素贡献（R1–R6）", expanded=False):
        for fid, name, weight, score, contribution in vm.factors:
            st.markdown(
                kv_row(f"{fid} {name}",
                       f"权重 {weight:g}% · 评分 {score:g}/5 · +{contribution:.1f}"),
                unsafe_allow_html=True,
            )
        st.markdown(
            scientific_note(vm.semantics),
            unsafe_allow_html=True,
        )


def _render_post_event(vm: HistoricalReplayViewModel) -> None:
    st.markdown(
        card_title("灾后验证", accent="✓")
        + '<div class="mg-metric-note">不用于分析，仅用于验证 — 将灾前识别的'
        "风险因素与灾后遥感、官方调查结果进行方向性对比。</div>",
        unsafe_allow_html=True,
    )
    left, mid, right = st.columns(3, gap="medium")
    with left:
        st.markdown(card_title("灾后影像"),
                    unsafe_allow_html=True)
        for label, value in vm.post_satellite:
            st.markdown(kv_row(label, value), unsafe_allow_html=True)
        post_ids = [e.evidence_id for e in vm.post_event_evidence
                    if e.evidence_id.startswith("EV-SAT-POST")]
        st.markdown(evidence_chips_html(post_ids) or empty_state("无灾后影像证据。"),
                    unsafe_allow_html=True)
    with mid:
        st.markdown(card_title("官方调查"),
                    unsafe_allow_html=True)
        for label, value in vm.post_event_facts:
            shown = (value[:60] + "…") if len(value) > 60 else value
            st.markdown(kv_row(label, shown), unsafe_allow_html=True)
    with right:
        st.markdown(card_title("阶段完整性"),
                    unsafe_allow_html=True,
        )
        st.markdown(
            kv_row("灾前阶段结果未修改",
                   "是" if vm.stage_a_unchanged else "否",
                   theme.GREEN if vm.stage_a_unchanged else theme.RED),
            unsafe_allow_html=True,
        )
        st.markdown(
            kv_row("方向性验证结论", str(len(vm.stage_b_findings))),
            unsafe_allow_html=True,
        )
        st.markdown(
            kv_row("灾后证据编号数", str(len(vm.stage_b_post_event_ids))),
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="mg-metric-note">灾后验证仅做方向性对比，不产生对齐分数、'
            "不修改灾前阶段结果。</div>",
            unsafe_allow_html=True,
        )
    with st.expander("方向性验证结论（灾前因素 对比 灾后调查）",
                     expanded=False):
        for note in vm.stage_b_findings:
            st.markdown(f"- {esc(narrative_label(note))}")
        st.markdown(
            scientific_note(narrative_label(vm.stage_b_statement)),
        )
    with st.expander("灾前阶段不可能知道的信息（冻结不可知集）",
                     expanded=False):
        for note in vm.stage_b_could_not_know:
            st.markdown(f"- {esc(narrative_label(note))}")


def _render_limitations(vm: HistoricalReplayViewModel) -> None:
    st.markdown(card_title("科学局限", accent="!"),
                unsafe_allow_html=True)
    for note in vm.limitations:
        st.markdown(
            f'<div class="mg-issue-row"><span style="color:{theme.ORANGE};'
            f'font-weight:700;">!</span> {esc(note)}</div>',
            unsafe_allow_html=True,
        )
    st.markdown(
        scientific_note(
            "历史验证 / 研究验证：评估在事件发生前可获得的信息能否识别"
            "已存在的基础风险；不宣称能够精确预测事件发生时间。"
        ),
        unsafe_allow_html=True,
    )


def render() -> None:
    """Render the Historical Replay page (builds its read-only view model)."""
    try:
        vm = build_historical_replay_viewmodel()
    except Exception as exc:  # honest degraded state, never fake content
        with st.container(border=True):
            st.error(
                "历史验证视图模型无法组装。页面不显示任何数据，"
                "而不是显示伪造数值。"
            )
            st.caption(f"详情：{type(exc).__name__}: {exc}")
        return

    if vm.fallback_mode:
        st.markdown(
            '<div class="mg-fallback">AI 运行时 · 回退模式</div>',
            unsafe_allow_html=True,
        )
        st.caption(
            "确定性基线易感性指数仍然有效；AI 解释层使用了基于规则的"
            f"确定性回退（模型服务离线，运行编号 {vm.run_id}）— "
            "绝不伪装为模型输出。"
        )

    with st.container(border=True):
        _render_case_header(vm)

    left, mid, right = st.columns([1.15, 1.5, 0.95], gap="medium")
    with left:
        with st.container(border=True):
            _render_pre_event_evidence(vm)
    with mid:
        with st.container(border=True):
            _render_agents(vm)
    with right:
        with st.container(border=True):
            _render_risk_result(vm)

    with st.container(border=True):
        _render_post_event(vm)

    with st.container(border=True):
        _render_limitations(vm)

    st.markdown(
        f'<div class="mg-metric-note">回放运行编号 {esc(vm.run_id)} · 冻结时间 '
        f'{esc(vm.frozen_at)} · 模型运行状态 {esc(status_label(vm.model_runtime))}</div>',
        unsafe_allow_html=True,
    )
