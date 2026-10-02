"""
MountainGuardian G04B – Risk Watch / 风险监测 page.

Frozen positioning (doc 05 §23–§31, gate G04B §10): On-demand Regional
Risk Scan — the operational product page of the completed G03C workflow.

  * ONE primary CTA: 执行风险扫描 (G05C Chinese-first label of the frozen
    Run Risk Scan action), wired to the existing orchestration entry
    run_risk_scan("jilong_port") — the page never re-implements
    collectors, formulas, agents, synthesizer or critic;
  * repeated clicks are blocked while a scan is running (session flag +
    disabled button);
  * Current Risk / 7-Day Outlook / Data Coverage / Scan Progress /
    What Changed / Historical Trend / Drivers / Evidence all read the
    persisted snapshot through RiskWatchViewModel — B/R/F/D/C/O7 are
    displayed as stored, never recomputed;
  * degraded / fallback / failed states are disclosed, never beautified;
  * the historical trend shows only real snapshots; with a single valid
    snapshot it shows the frozen honest empty state.

G05C (doc 08): visible page language is Chinese; Run ID values, stage
identifiers and brand/technical names stay verbatim per the allowlist.
"""

from __future__ import annotations

import streamlit as st

from frontend import components, theme
from frontend.components import (
    card_title,
    chip,
    coverage_row_html,
    drivers_html,
    empty_state,
    esc,
    kv_row,
    ring_gauge_html,
    scan_steps_html,
    scientific_note,
    table_html,
    trend_line,
)
from frontend.display import (
    direction_label,
    driver_label,
    point_id_label,
    risk_label,
    scan_mode_label,
    status_label,
)
from frontend.viewmodels import RiskWatchViewModel, build_risk_watch_viewmodel

# The single sanctioned orchestration entry point (gate G04B §10.1).
from orchestration.risk_watch_orchestrator import run_risk_scan

RUN_FLAG = "mg_rw_running"
CTA_LABEL = "执行风险扫描"

_CHANGE_MARKS = {
    "UP": ("↑", theme.RED),
    "DOWN": ("↓", theme.GREEN),
    "UNCHANGED": ("→", theme.CYAN),
    "NOT_COMPARABLE": ("·", theme.TEXT_DIM),
}


def _render_header(vm: RiskWatchViewModel) -> None:
    left, right = st.columns([2.4, 1], gap="medium")
    with left:
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:10px;'
            f'flex-wrap:wrap;"><span style="font-size:20px;font-weight:750;">'
            f'{esc(vm.region_label)}</span>'
            f'{chip("区域风险扫描", theme.CYAN)}</div>'
            f'<div class="mg-metric-note" style="margin-top:6px;">基于最新数据'
            "执行区域风险扫描，评估当前风险与未来 7 天风险背景。手动执行 · "
            "不提供实时告警 · 不表示灾害发生可能性。</div>",
            unsafe_allow_html=True,
        )
    with right:
        running = bool(st.session_state.get(RUN_FLAG, False))
        label = "扫描执行中…" if running else CTA_LABEL
        if st.button(label, type="primary", use_container_width=True,
                     disabled=running, key="mg_rw_run_cta",
                     help="调用既有风险扫描编排入口；运行中不可重复点击。"):
            _execute_scan()


def _execute_scan() -> None:
    """Run the frozen G03C workflow once; honest status on every outcome."""
    st.session_state[RUN_FLAG] = True
    try:
        with st.status(
            "风险扫描执行中 — 数据采集 → 数据标准化 → 保存快照 → "
            "智能体分析 → 风险综合 → 评审复核",
            expanded=True,
        ) as box:
            st.caption(
                "工作流各阶段在 G03C 编排器服务端执行；运行完成后，"
                "持久化的阶段轨迹显示在下方。不模拟任何中间耗时。"
            )
            result = run_risk_scan("jilong_port")
        st.session_state["mg_rw_last_status"] = str(result.status)
        box.update(
            label=f"扫描结束 — {status_label(result.status)}",
            state="complete" if str(result.status).startswith("COMPLETED")
            else "error",
        )
    except Exception as exc:
        st.session_state["mg_rw_last_status"] = "FAILED"
        st.session_state["mg_rw_last_error"] = f"{type(exc).__name__}: {exc}"
        st.error(
            "风险扫描以故障安全方式中止。未伪造任何风险数值；"
            "既有持久化结果仍然有效。"
        )
        st.caption(f"详情：{type(exc).__name__}: {exc}")
    finally:
        st.session_state[RUN_FLAG] = False
    st.rerun()


def _render_current_risk(vm: RiskWatchViewModel) -> None:
    st.markdown(card_title("当前风险", accent="●"),
                unsafe_allow_html=True)
    if not vm.has_result:
        st.markdown(
            empty_state(
                "尚无风险扫描结果。完成第一次风险扫描后，当前风险指数"
                "将显示在此处（不会伪造数值）。"
            ),
            unsafe_allow_html=True,
        )
        return
    color = theme.risk_color(vm.risk_level)
    st.markdown(
        f'<div class="mg-ring-row">{ring_gauge_html(vm.risk_index_rounded, color)}'
        f'<div>{chip(risk_label(vm.risk_level) if vm.risk_level else "未知", color)}'
        f'<div style="margin-top:8px;">{trend_line(vm.risk_direction, vm.trend_delta)}</div>'
        f'</div></div>',
        unsafe_allow_html=True,
    )
    st.markdown(kv_row("最近扫描", (vm.last_updated or "—").replace("T", " ")[:16] + " UTC"),
                unsafe_allow_html=True)
    cov = vm.coverage
    req = f"{cov.required_ok} / {cov.required_total}" if cov.required_ok is not None else "—"
    st.markdown(kv_row("必需数据覆盖", req), unsafe_allow_html=True)
    st.markdown(kv_row("扫描状态", status_label(vm.last_scan_status) if vm.last_scan_status else "—",
                       theme.GREEN if vm.last_scan_status == "COMPLETED"
                       else theme.ORANGE), unsafe_allow_html=True)
    st.markdown(
        scientific_note("风险指数不是事件发生概率。风险指数表示区域易发生"
                        "灾害的基础风险水平。"),
        unsafe_allow_html=True,
    )


def _render_outlook(vm: RiskWatchViewModel) -> None:
    st.markdown(card_title("未来7天风险展望", accent="◔"),
                unsafe_allow_html=True)
    if not vm.has_result or vm.outlook_index_rounded is None:
        st.markdown(empty_state("未来7天风险展望将在完成一次扫描后显示。"),
                    unsafe_allow_html=True)
        return
    color = theme.risk_color(vm.outlook_level)
    change_rows = []
    for pid, direction, delta in vm.outlook_change:
        mark, mcolor = _CHANGE_MARKS.get(
            direction.replace("CHANGE_", ""), ("·", theme.TEXT_DIM))
        delta_txt = f" {delta:+.1f} mm" if isinstance(delta, (int, float)) else ""
        change_rows.append(
            f'<div class="mg-kv"><span class="mg-kv-k">预报降水变化 Δ '
            f'{esc(point_id_label(pid))}</span>'
            f'<span style="color:{mcolor};font-weight:650;">{mark}{esc(delta_txt)} '
            f'{esc(direction_label(direction.replace("CHANGE_", "")))}</span></div>'
        )
    driver_row = (
        kv_row("主要驱动因素", driver_label(str(vm.outlook_drivers[0][0])))
        if vm.outlook_drivers else ""
    )
    st.markdown(
        f'<div class="mg-ring-row">{ring_gauge_html(vm.outlook_index_rounded, color)}'
        f'<div>{chip(risk_label(vm.outlook_level) if vm.outlook_level else "未知", color)}'
        f'<div style="margin-top:8px;">{"".join(change_rows)}</div>'
        f'</div></div>{driver_row}',
        unsafe_allow_html=True,
    )
    st.markdown(
        scientific_note("展望指数不是事件发生概率。展望指数表示在当前天气"
                        "预报情景下的区域风险背景。"),
        unsafe_allow_html=True,
    )


def _render_coverage(vm: RiskWatchViewModel) -> None:
    st.markdown(card_title("数据覆盖", accent="▤"),
                unsafe_allow_html=True)
    if not vm.has_result:
        st.markdown(empty_state("数据覆盖将在完成一次扫描后显示。"),
                    unsafe_allow_html=True)
        return
    cov = vm.coverage
    req = f"{cov.required_ok} / {cov.required_total}" if cov.required_ok is not None else "—"
    opt = (f"{cov.optional_available} / {cov.optional_total}"
           if cov.optional_available is not None else "—")
    st.markdown(
        f'<div style="display:flex;gap:18px;margin-bottom:8px;">'
        f'<div><div class="mg-metric" style="font-size:26px;color:{theme.CYAN};">{esc(req)}</div>'
        f'<div class="mg-metric-note">必需数据</div></div>'
        f'<div><div class="mg-metric" style="font-size:26px;color:{theme.TEXT_DIM};">{esc(opt)}</div>'
        f'<div class="mg-metric-note">可选证据</div></div></div>',
        unsafe_allow_html=True,
    )
    for row in vm.source_rows:
        color = {
            "AVAILABLE": theme.GREEN, "LIMITED": theme.ORANGE,
            "STALE": theme.ORANGE, "MISSING": theme.TEXT_DIM,
            "NOT USED": theme.TEXT_DIM,
        }.get(row.status, theme.TEXT_DIM)
        st.markdown(
            coverage_row_html(row.label, row.status, color,
                              quality=row.quality, note=row.note),
            unsafe_allow_html=True,
        )
    st.markdown(
        '<div class="mg-metric-note">可选证据缺失不会自动导致扫描失败；'
        "缺失项被显式声明，从不静默丢弃（文档 04 §19/§42）。</div>",
        unsafe_allow_html=True,
    )


def _render_scan_progress(vm: RiskWatchViewModel) -> None:
    st.markdown(
        card_title("扫描进度", accent="➔")
        + '<div class="mg-metric-note">数据采集 → 数据标准化 → 保存快照 → '
        "智能体分析 → 风险综合 → 评审复核（来自持久化阶段轨迹的真实时间戳）</div>",
        unsafe_allow_html=True,
    )
    if not vm.has_result:
        st.markdown(empty_state("尚未执行扫描 — 工作流步骤将在第一次"
                                "持久化运行后显示。"),
                    unsafe_allow_html=True)
        return
    st.markdown(
        scan_steps_html(tuple(
            (s.num, s.label_zh, s.label_en, s.state, s.ts) for s in vm.scan_steps
        )),
        unsafe_allow_html=True,
    )
    status_color = {
        "COMPLETED": theme.GREEN,
        "COMPLETED_WITH_LIMITATIONS": theme.ORANGE,
        "FAILED": theme.RED,
    }.get(vm.last_scan_status, theme.TEXT_DIM)
    st.markdown(
        f'<div style="margin-top:10px;">'
        + kv_row("扫描状态", status_label(vm.last_scan_status) if vm.last_scan_status else "—", status_color)
        + kv_row("运行编号", vm.run_id or "—")
        + kv_row("模式", scan_mode_label(vm.last_scan_mode) if vm.last_scan_mode else "—")
        + kv_row("执行耗时", f"{vm.scan_duration_s} 秒"
                 if vm.scan_duration_s is not None else "—")
        + kv_row("模型运行状态", status_label(vm.model_runtime),
                 theme.GREEN if vm.model_runtime == "CONNECTED" else theme.ORANGE)
        + "</div>",
        unsafe_allow_html=True,
    )
    if vm.fallback_mode or vm.last_scan_status == "COMPLETED_WITH_LIMITATIONS":
        st.markdown(
            '<div class="mg-fallback">已完成，但存在局限 / 回退模式</div>',
            unsafe_allow_html=True,
        )
        st.caption(
            "降级运行状态按原样披露：确定性结果仍然有效，"
            "AI 解释层部分运行或使用了回退。"
        )


def _render_what_changed(vm: RiskWatchViewModel) -> None:
    st.markdown(card_title("风险变化", accent="⇄"),
                unsafe_allow_html=True)
    if not vm.has_result:
        st.markdown(empty_state("对比结果将在第二次有效扫描后显示。"),
                    unsafe_allow_html=True)
        return
    wc = vm.what_changed or {}
    if vm.what_changed_status != "COMPARISON_AVAILABLE":
        st.markdown(
            f'<div style="border:1px solid {theme.ORANGE}55;background:'
            f'rgba(255,180,84,0.07);border-radius:9px;padding:12px 14px;">'
            f'<div style="font-weight:700;color:{theme.ORANGE};">'
            f'暂无历史比较基线</div>'
            f'<div class="mg-metric-note">当前仅有 1 次有效扫描结果。完成下一次'
            "风险扫描后，将显示本轮与上一轮的变化。历史比较从不伪造。</div></div>",
            unsafe_allow_html=True,
        )
        return
    cur = wc.get("current_risk") or {}
    mark, mcolor = _CHANGE_MARKS.get(
        str(cur.get("direction", "")).replace("CHANGE_", ""), ("·", theme.TEXT_DIM))
    delta = cur.get("delta")
    st.markdown(
        kv_row("风险指数（与上一轮相比）",
               f"{mark} {delta:+.2f}" if isinstance(delta, (int, float)) else "—",
               mcolor),
        unsafe_allow_html=True,
    )
    for section, label in (("recent_precipitation", "近期降水"),
                           ("forecast_precipitation", "预报降水")):
        for pid, cmp_ in sorted((wc.get(section) or {}).items()):
            if not isinstance(cmp_, dict):
                continue
            m2, c2 = _CHANGE_MARKS.get(
                str(cmp_.get("direction", "")).replace("CHANGE_", ""),
                ("·", theme.TEXT_DIM))
            d2 = cmp_.get("delta")
            st.markdown(
                kv_row(f"{label} · {point_id_label(pid)}",
                       f"{m2} {d2:+.1f} mm" if isinstance(d2, (int, float)) else "—",
                       c2),
                unsafe_allow_html=True,
            )
    missing = wc.get("missing_data") or {}
    if missing.get("newly_missing") or missing.get("newly_available"):
        st.markdown(
            kv_row("新增缺失", "、".join(missing.get("newly_missing") or ()) or "—"),
            unsafe_allow_html=True,
        )
        st.markdown(
            kv_row("新增可用", "、".join(missing.get("newly_available") or ()) or "—"),
            unsafe_allow_html=True,
        )
    st.markdown(
        '<div class="mg-metric-note">数字比较由冻结引擎生成（比较模块）；'
        "界面只读展示。</div>",
        unsafe_allow_html=True,
    )


def _render_trend(vm: RiskWatchViewModel) -> None:
    st.markdown(card_title("历史风险趋势", accent="◫"),
                unsafe_allow_html=True)
    if not vm.trend_points:
        st.markdown(empty_state("历史数据不足，完成更多扫描后将形成趋势。"),
                    unsafe_allow_html=True)
        return
    if vm.trend_status in ("NO_HISTORY", "INSUFFICIENT_HISTORY"):
        st.markdown(
            empty_state("历史数据不足，完成更多扫描后将形成趋势。"
                        "趋势从不伪造，也不预填未来数据点。"),
            unsafe_allow_html=True,
        )
    for tp in vm.trend_points:
        level_color = theme.risk_color(tp.risk_level)
        when = tp.created_at.replace("T", " ")[:16]
        badge = (f' <span style="font-size:10px;color:{theme.TEXT_DIM};">'
                 f'[{esc(scan_mode_label(tp.scan_mode))}]</span>')
        st.markdown(
            f'<div class="mg-trend-row"><span class="mg-trend-k">{esc(when)}'
            f' UTC{badge}</span><span><b style="color:{level_color};">'
            f'{tp.risk_index_rounded:.2f}</b> &nbsp;'
            f'{chip(risk_label(tp.risk_level), level_color, small=True)}</span></div>',
            unsafe_allow_html=True,
        )
    st.markdown(
        '<div class="mg-metric-note">趋势点仅来自真实、有效、已持久化的风险'
        "监测快照；不插值、不预测、不补点。</div>",
        unsafe_allow_html=True,
    )


def _render_drivers_evidence(vm: RiskWatchViewModel) -> None:
    st.markdown(card_title("主要风险驱动因素", accent="≡"),
                unsafe_allow_html=True)
    st.markdown(drivers_html(vm.top_drivers), unsafe_allow_html=True)
    if vm.outlook_drivers:
        st.markdown(
            '<div class="mg-metric-note" style="margin-top:8px;">'
            "未来7天展望驱动因素（O7 分解，冻结引擎）：</div>",
            unsafe_allow_html=True,
        )
        st.markdown(drivers_html(vm.outlook_drivers), unsafe_allow_html=True)
    st.markdown(card_title("本轮证据详情", accent="▤"),
                unsafe_allow_html=True)
    any_ev = False
    for card in vm.agents:
        if card.evidence_ids:
            any_ev = True
            st.markdown(
                f'<div class="mg-ev-meta" style="margin:6px 0 2px 0;">'
                f'{esc(card.name_zh)}</div>'
                + components.evidence_chips_html(card.evidence_ids),
                unsafe_allow_html=True,
            )
    if not any_ev:
        st.markdown(empty_state("本轮扫描无证据记录。"),
                    unsafe_allow_html=True)
    if vm.critic_result:
        st.markdown(
            card_title("评审复核", accent="◆"),
            unsafe_allow_html=True,
        )
        st.markdown(
            kv_row("评审结果", status_label(vm.critic_result),
                   theme.critic_color(vm.critic_result)),
            unsafe_allow_html=True,
        )
        if vm.critic_severity:
            st.markdown(kv_row("严重性", status_label(vm.critic_severity)),
                        unsafe_allow_html=True)
        for note in vm.critic_limitations[:3]:
            st.markdown(
                f'<div class="mg-issue-row"><span style="color:{theme.ORANGE};'
                f'font-weight:700;">!</span> {esc(note)}</div>',
                unsafe_allow_html=True,
            )
    if vm.limitations:
        from frontend.display import limitation_label

        with st.expander(f"本轮扫描局限（{len(vm.limitations)}）", expanded=False):
            for note in vm.limitations:
                st.markdown(f"- {esc(limitation_label(str(note)))}")


def render() -> None:
    """Render the Risk Watch page (read-only VM + single sanctioned CTA)."""
    try:
        vm = build_risk_watch_viewmodel()
    except Exception as exc:
        with st.container(border=True):
            st.error(
                "无法从快照存储读取风险监测视图模型。页面不显示任何数据，"
                "而不是显示伪造数值。"
            )
            st.caption(f"详情：{type(exc).__name__}: {exc}")
        return

    with st.container(border=True):
        _render_header(vm)

    if st.session_state.get("mg_rw_last_status"):
        last = str(st.session_state["mg_rw_last_status"])
        color = theme.GREEN if last.startswith("COMPLETED") else theme.RED
        st.caption(f"最近扫描请求状态：{status_label(last)}")
        st.markdown(chip(status_label(last), color, small=True), unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3, gap="medium")
    with c1:
        with st.container(border=True):
            _render_current_risk(vm)
    with c2:
        with st.container(border=True):
            _render_outlook(vm)
    with c3:
        with st.container(border=True):
            _render_coverage(vm)

    with st.container(border=True):
        _render_scan_progress(vm)

    left, right = st.columns([1.4, 1], gap="medium")
    with left:
        with st.container(border=True):
            _render_what_changed(vm)
    with right:
        with st.container(border=True):
            st.markdown(card_title("风险驱动因素与证据", accent="≡"),
                        unsafe_allow_html=True)
            _render_drivers_evidence(vm)

    bottom_l, bottom_r = st.columns([1.2, 1], gap="medium")
    with bottom_l:
        with st.container(border=True):
            _render_trend(vm)
    with bottom_r:
        with st.container(border=True):
            st.markdown(card_title("扫描事实", accent="ⓘ"),
                        unsafe_allow_html=True)
            st.markdown(
                table_html(
                    ("字段", "值"),
                    (
                        ("监测区域", vm.region_label),
                        ("运行编号", vm.run_id or "—"),
                        ("生成时间", (vm.last_updated or "—").replace("T", " ")[:19]),
                        ("状态", status_label(vm.last_scan_status) if vm.last_scan_status else "—"),
                        ("模式", scan_mode_label(vm.last_scan_mode) if vm.last_scan_mode else "—"),
                    ),
                ),
                unsafe_allow_html=True,
            )
            st.markdown(
                scientific_note(
                    "研究性风险评估，非官方灾害告警。"
                ),
                unsafe_allow_html=True,
            )
