"""
MountainGuardian G04B – Historical Replay / 历史回放 page.

Frozen positioning (doc 05 §15–§22, gate G04B §9): Research Validation —
"If MountainGuardian only uses information available before the event,
what pre-existing risk conditions can the multi-agent system identify?"

Page structure (doc 05 §16):
  A. Case header            B. PRE-EVENT / EVENT / POST-EVENT timeline
  C. Pre-event evidence     D. Multi-Agent analysis (3 agents → Synthesizer
                             → Critic)
  E. Baseline Susceptibility result   F. Critic card
  G. Post-event validation  H. Scientific limitations

Scientific boundaries enforced here:
  * pre-event evidence panel renders ONLY Stage-A authorized evidence;
    post-event evidence appears ONLY in the validation section;
  * the 91/100 HIGH value is consumed from the deterministic engine result
    and always labeled "Baseline Susceptibility Index — not event probability";
    never recomputed, never a percentage, never accuracy;
  * no chain of thought, no prompts, no hidden reasoning — structured
    findings and evidence ids only.
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
from frontend.replay_viewmodels import (
    EVIDENCE_CATEGORIES,
    HistoricalReplayViewModel,
    build_historical_replay_viewmodel,
)

_STAGE_COLORS = {"CYAN": theme.CYAN, "ORANGE": theme.ORANGE,
                 "PURPLE": theme.PURPLE}

BASELINE_NOTE = "Baseline Susceptibility Index — Not event probability"


def _render_case_header(vm: HistoricalReplayViewModel) -> None:
    st.markdown(
        f'<div style="display:flex;justify-content:space-between;'
        f'align-items:flex-start;gap:16px;flex-wrap:wrap;">'
        f'<div><div style="font-size:20px;font-weight:750;">'
        f'{esc(vm.case_name)}</div>'
        f'<div style="font-size:12.5px;color:{theme.TEXT_DIM};margin-top:4px;">'
        f'{esc(vm.location)} · 事件日期 {esc(vm.event_date)} · Case '
        f'{esc(vm.case_id)}</div></div>'
        f'<div>{chip("Research Validation · 研究验证", theme.PURPLE)} '
        f'{chip("Historical Replay", theme.CYAN, small=True)}</div></div>',
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
            "从不进入灾前分析（Stage A / Stage B 分离）。"
        ),
        unsafe_allow_html=True,
    )


def _render_pre_event_evidence(vm: HistoricalReplayViewModel) -> None:
    st.markdown(
        card_title("Pre-event Evidence · 灾前证据", accent="▤")
        + f'<div class="mg-metric-note">Stage A 输入证据 · '
        f'{len(vm.pre_event_evidence)} 条 · 仅灾前相位</div>',
        unsafe_allow_html=True,
    )
    if not vm.pre_event_evidence:
        st.markdown(empty_state("No pre-event evidence recorded in the Case Pack."),
                    unsafe_allow_html=True)
        return
    for label_en, label_zh, types in EVIDENCE_CATEGORIES:
        items = [e for e in vm.pre_event_evidence if e.type_label in types]
        if not items:
            continue
        st.markdown(
            f'<div style="margin:10px 0 2px 0;font-size:11px;font-weight:700;'
            f'letter-spacing:0.12em;color:{theme.CYAN};text-transform:uppercase;">'
            f'{esc(label_en)} · {esc(label_zh)} ({len(items)})</div>',
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
        '<div class="mg-metric-note">Evidence IDs 与相位来自冻结 Case Pack；'
        "灾后相位证据不在本面板显示。</div>",
        unsafe_allow_html=True,
    )


def _agent_block(agent) -> str:
    color = (theme.critic_color(agent.status) if agent.key == "critic"
             else theme.agent_status_color(agent.status))
    conf = (f"{agent.confidence:.2f}"
            if isinstance(agent.confidence, (int, float)) else "—")
    fallback = (' <span style="color:%s;font-size:10px;font-weight:700;">'
                'FALLBACK</span>' % theme.ORANGE) if agent.fallback_used else ""
    findings = "".join(
        f'<div class="mg-issue-row">• {esc(f)}</div>' for f in agent.findings[:5]
    ) or empty_state("No structured findings recorded.")
    missing = ""
    if agent.missing_data:
        missing = (
            f'<div class="mg-metric-note">Missing data: '
            + esc("; ".join(agent.missing_data[:3])) + "</div>"
        )
    limits = ""
    if agent.limitations:
        limits = (
            f'<div class="mg-metric-note">Limitations: '
            + esc("; ".join(agent.limitations[:2])) + "</div>"
        )
    return (
        f'<div class="mg-agent-card{" mg-agent-ai" if agent.is_ai_layer else ""}">'
        f'<span class="mg-agent-name">{esc(agent.name_en)}</span>{fallback}'
        f'<div class="mg-agent-zh">{esc(agent.name_zh)}</div>'
        f'<div class="mg-agent-meta"><span style="color:{color};font-weight:700;">'
        f'● {esc(agent.status.replace("_", " ").title())}</span><br/>'
        f'Confidence <b>{esc(conf)}</b> · {len(agent.evidence_ids)} evidence</div>'
        f'<div style="margin-top:8px;">{findings}</div>'
        f'<div style="margin-top:6px;">{evidence_chips_html(agent.evidence_ids)}</div>'
        f"{missing}{limits}</div>"
    )


def _render_agents(vm: HistoricalReplayViewModel) -> None:
    st.markdown(
        card_title("Multi-Agent Analysis · 多智能体分析", accent="✦")
        + '<div class="mg-metric-note">仅基于灾前数据 · 三个专业智能体 → '
        "Risk Synthesizer → Critic（冻结 DAG，非自治网络）</div>",
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
                f'<div class="mg-metric-note">Synthesis: {esc(vm.synthesis_summary[:220])}'
                f' · agreement {esc(vm.synthesis_agreement)}</div>',
                unsafe_allow_html=True,
            )
    st.markdown(flow_arrow(), unsafe_allow_html=True)
    if vm.critic is not None:
        st.markdown(
            critic_panel_html(
                vm.critic.review_result, vm.critic.severity,
                vm.critic.issues[:4], vm.critic.scientific_limitations[:4],
                attestation=(
                    "Critic 不修改 Risk Index：before "
                    f"{vm.critic.risk_index_before} / after "
                    f"{vm.critic.risk_index_after}"
                ),
            ),
            unsafe_allow_html=True,
        )
    else:
        st.markdown(empty_state("No critic record in this replay run."),
                    unsafe_allow_html=True)
    st.markdown(
        '<div class="mg-metric-note">仅展示结构化结论与 Evidence IDs — '
        "不展示 chain of thought、内部推理或系统提示词。</div>",
        unsafe_allow_html=True,
    )


def _render_risk_result(vm: HistoricalReplayViewModel) -> None:
    st.markdown(
        card_title("Risk Result · 风险评估结果", accent="◉")
        + '<div class="mg-metric-note">灾前分析（Stage A 冻结结果）</div>',
        unsafe_allow_html=True,
    )
    color = theme.risk_color(vm.risk_level)
    st.markdown(
        f'<div class="mg-ring-row">{ring_gauge_html(vm.risk_index, color)}'
        f'<div>{chip(vm.risk_level or "UNKNOWN", color)}'
        f'<div style="margin-top:10px;font-size:12px;font-weight:700;">'
        f'基础易灾性指数</div>'
        f'<div class="mg-metric-note">Baseline Susceptibility Index</div>'
        f'<div class="mg-metric-note" style="color:{theme.ORANGE};">'
        f'⚠ Not event probability · 不是事件发生可能性</div></div></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        card_title("Top Drivers · 主要驱动因素"),
        unsafe_allow_html=True,
    )
    for i, (name, contribution) in enumerate(vm.top_drivers, start=1):
        st.markdown(
            f'<div class="mg-trend-row"><span><span style="color:'
            f'{theme.TEXT_DIM};">{i:02d}</span> {esc(name)}</span>'
            f'<b>+{contribution:.1f}</b></div>',
            unsafe_allow_html=True,
        )
    with st.expander("Deterministic factor contributions (R1–R6)", expanded=False):
        for fid, name, weight, score, contribution in vm.factors:
            st.markdown(
                kv_row(f"{fid} {name}",
                       f"weight {weight:g}% · score {score:g}/5 · +{contribution:.1f}"),
                unsafe_allow_html=True,
            )
        st.markdown(
            scientific_note(vm.semantics),
            unsafe_allow_html=True,
        )


def _render_post_event(vm: HistoricalReplayViewModel) -> None:
    st.markdown(
        card_title("Post-event Validation · 灾后验证", accent="✓")
        + '<div class="mg-metric-note">不用于分析，仅用于验证 — 将灾前识别的'
        "风险因素与灾后遥感、官方调查结果进行方向性对比。</div>",
        unsafe_allow_html=True,
    )
    left, mid, right = st.columns(3, gap="medium")
    with left:
        st.markdown(card_title("Post-event Imagery · 灾后影像"),
                    unsafe_allow_html=True)
        for label, value in vm.post_satellite:
            st.markdown(kv_row(label, value), unsafe_allow_html=True)
        post_ids = [e.evidence_id for e in vm.post_event_evidence
                    if e.evidence_id.startswith("EV-SAT-POST")]
        st.markdown(evidence_chips_html(post_ids) or empty_state("No post-event imagery evidence."),
                    unsafe_allow_html=True)
    with mid:
        st.markdown(card_title("Official Investigation · 官方调查"),
                    unsafe_allow_html=True)
        for label, value in vm.post_event_facts:
            shown = (value[:60] + "…") if len(value) > 60 else value
            st.markdown(kv_row(label, shown), unsafe_allow_html=True)
    with right:
        st.markdown(card_title("Stage B Integrity · 阶段完整性"),
                    unsafe_allow_html=True)
        st.markdown(
            kv_row("Stage A unchanged",
                   "YES" if vm.stage_a_unchanged else "NO",
                   theme.GREEN if vm.stage_a_unchanged else theme.RED),
            unsafe_allow_html=True,
        )
        st.markdown(
            kv_row("Directional findings", str(len(vm.stage_b_findings))),
            unsafe_allow_html=True,
        )
        st.markdown(
            kv_row("Post-event evidence ids", str(len(vm.stage_b_post_event_ids))),
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="mg-metric-note">Stage B 仅做方向性验证，不产生对齐分数、'
            "不修改 Stage A 结果。</div>",
            unsafe_allow_html=True,
        )
    with st.expander("Directional findings (pre-event factors vs post-event investigation)",
                     expanded=False):
        for note in vm.stage_b_findings:
            st.markdown(f"- {esc(note)}")
        st.markdown(
            scientific_note(vm.stage_b_statement),
        )
    with st.expander("What Stage A could NOT know (frozen unknowable set)",
                     expanded=False):
        for note in vm.stage_b_could_not_know:
            st.markdown(f"- {esc(note)}")


def _render_limitations(vm: HistoricalReplayViewModel) -> None:
    st.markdown(card_title("Scientific Limitations · 科学局限性", accent="!"),
                unsafe_allow_html=True)
    for note in vm.limitations:
        st.markdown(
            f'<div class="mg-issue-row"><span style="color:{theme.ORANGE};'
            f'font-weight:700;">!</span> {esc(note)}</div>',
            unsafe_allow_html=True,
        )
    st.markdown(
        scientific_note(
            "Historical Replay / Research Validation：评估在事件发生前可获得的"
            "信息能否识别已存在的基础风险；不宣称能够精确预测事件发生时间。"
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
                "Historical Replay view model could not be assembled. "
                "The page shows no data rather than fabricated values."
            )
            st.caption(f"Detail: {type(exc).__name__}: {exc}")
        return

    if vm.fallback_mode:
        st.markdown(
            '<div class="mg-fallback">AI Runtime · Fallback Mode</div>',
            unsafe_allow_html=True,
        )
        st.caption(
            "Deterministic Baseline Susceptibility Index remains valid; the "
            "AI explanation layers ran on rule-based deterministic fallbacks "
            f"(provider offline, run {vm.run_id}) — never disguised as model output."
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
        f'<div class="mg-metric-note">Replay run {esc(vm.run_id)} · frozen at '
        f'{esc(vm.frozen_at)} · model runtime {esc(vm.model_runtime)}</div>',
        unsafe_allow_html=True,
    )
