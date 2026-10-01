"""
MountainGuardian G04A – Overview page.

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
from frontend.map_view import build_overview_map
from frontend.viewmodels import OverviewViewModel

MAP_HEIGHT = 560


def _render_map(vm: OverviewViewModel) -> None:
    st.markdown(card_title("Main Map", accent="◈") + "", unsafe_allow_html=True)
    map_html = build_overview_map(vm.monitoring_points, height=MAP_HEIGHT)
    if map_html is None:
        st.markdown(
            empty_state("No monitoring points available for this region."),
            unsafe_allow_html=True,
        )
        return
    # The frame styling lives inside the folium HTML (iframe) — Streamlit
    # markdown cannot wrap a component in a shared div.
    st_components.html(map_html, height=MAP_HEIGHT + 12, scrolling=False)
    st.markdown(
        '<div class="mg-map-caption">Monitoring region: '
        f"{esc(vm.region_name)} · representative monitoring coordinates with "
        "documented uncertainty (region config, frozen). 2D view — no 3D GIS, "
        "no spatial re-analysis in the UI.</div>",
        unsafe_allow_html=True,
    )


def _render_current_risk(vm: OverviewViewModel) -> None:
    st.markdown(card_title("Current Risk", accent="●"), unsafe_allow_html=True)
    if vm.fallback_mode:
        st.markdown(
            '<div class="mg-fallback">AI Runtime · Fallback Mode</div>',
            unsafe_allow_html=True,
        )
        st.caption(
            "Deterministic Risk Index remains valid; AI explanation layers "
            "ran on rule-based fallbacks (never disguised as model output)."
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
    with st.expander("Top Risk Drivers (engine contributions)", expanded=False):
        st.markdown(drivers_html(vm.top_drivers), unsafe_allow_html=True)
        st.markdown(
            '<div class="mg-metric-note">Contribution points are deterministic '
            "engine output (doc 04). Static drivers come from the frozen "
            "regional susceptibility baseline.</div>",
            unsafe_allow_html=True,
        )


def _render_agents(vm: OverviewViewModel) -> None:
    st.markdown(
        card_title("Agent Collaboration", accent="✦"), unsafe_allow_html=True
    )
    if not vm.agents:
        st.markdown(
            empty_state(
                "Agent run states appear here after the first completed "
                "Risk Watch scan."
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
        '<div class="mg-metric-note">Professional agents → Risk Synthesizer → '
        "Critic review. Status, confidence and evidence counts only — full "
        "structured outputs live in the Intelligence Center.</div>",
        unsafe_allow_html=True,
    )


def _render_trend(vm: OverviewViewModel) -> None:
    st.markdown(
        card_title("Risk Trend · Recent Scan", accent="◫"), unsafe_allow_html=True
    )
    if not vm.has_result:
        st.markdown(
            empty_state("No scan history yet — trend starts after the first scan."),
            unsafe_allow_html=True,
        )
        return

    if vm.trend_status in ("NO_HISTORY", "INSUFFICIENT_HISTORY"):
        st.markdown(
            empty_state(
                "Historical trend will appear after more scans. "
                "History is never fabricated or pre-filled."
            ),
            unsafe_allow_html=True,
        )
    for tp in vm.trend_points:
        level_color = theme.risk_color(tp.risk_level)
        when = tp.created_at.replace("T", " ")[:16]
        badge = f' <span style="font-size:10px;color:{theme.TEXT_DIM};">[{esc(tp.scan_mode)}]</span>'
        st.markdown(
            f'<div class="mg-trend-row">'
            f'<span class="mg-trend-k">{esc(when)} UTC{badge}</span>'
            f'<span><b style="color:{level_color};">{tp.risk_index_rounded:.2f}</b>'
            f' &nbsp;{chip(tp.risk_level, level_color, small=True)}</span></div>',
            unsafe_allow_html=True,
        )

    st.markdown(
        f'<div class="mg-metric-note">Last scan: <b>{esc(vm.last_scan_status or "—")}</b>'
        f' · mode {esc(vm.last_scan_mode or "—")} · run {esc((vm.run_id or "—")[:34])}</div>',
        unsafe_allow_html=True,
    )


def _render_evidence(vm: OverviewViewModel) -> None:
    st.markdown(
        card_title("Evidence · Data Coverage", accent="▤"), unsafe_allow_html=True
    )
    cov = vm.coverage
    if not vm.has_result:
        st.markdown(
            empty_state("Evidence coverage appears after the first completed scan."),
            unsafe_allow_html=True,
        )
        return

    req = f"{cov.required_ok} / {cov.required_total}" if cov.required_ok is not None else "—"
    opt = (
        f"{cov.optional_available} / {cov.optional_total}"
        if cov.optional_available is not None else "—"
    )
    st.markdown(
        f'<div class="mg-trend-row"><span class="mg-trend-k">Required data</span>'
        f'<span><b>{esc(req)}</b></span></div>'
        f'<div class="mg-trend-row"><span class="mg-trend-k">Optional data</span>'
        f'<span><b>{esc(opt)}</b></span></div>',
        unsafe_allow_html=True,
    )

    if cov.point_quality:
        chips = " ".join(
            chip(f"{pid}: {q}", theme.GREEN if q == "FRESH" else theme.ORANGE, small=True)
            for pid, q in sorted(cov.point_quality.items())
        )
        st.markdown(f'<div style="margin-top:8px;">{chips}</div>', unsafe_allow_html=True)

    if cov.satellite_pipeline_available is False:
        st.markdown(
            empty_state("No usable new satellite imagery for this scan. "
                        "Optional source — scan validity unaffected."),
            unsafe_allow_html=True,
        )
    if cov.optional_missing:
        st.markdown(
            '<div class="mg-metric-note">Missing optional sources: '
            + esc(", ".join(str(x) for x in cov.optional_missing))
            + "</div>",
            unsafe_allow_html=True,
        )

    with st.expander("Evidence IDs used in this scan", expanded=False):
        any_ev = False
        for card in vm.agents:
            if card.evidence_ids:
                any_ev = True
                st.markdown(
                    f'<div style="font-size:11.5px;color:{theme.TEXT_DIM};'
                    f'margin:6px 0 3px 0;">{esc(card.name_en)}</div>'
                    + evidence_chips_html(card.evidence_ids),
                    unsafe_allow_html=True,
                )
        if not any_ev:
            st.markdown(empty_state("No evidence records in this scan."),
                        unsafe_allow_html=True)
        st.markdown(
            '<div class="mg-metric-note">Only evidence actually recorded by the '
            "Risk Watch run is listed — the UI never invents evidence.</div>",
            unsafe_allow_html=True,
        )


def _render_quick_entries() -> None:
    st.markdown(card_title("Quick Entries", accent="➤"), unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(
            '<div class="mg-entry-title">Historical Replay</div>'
            '<div class="mg-entry-desc">Research validation on the frozen '
            "2026-08-26 Jilong case — pre-event evidence only.</div>",
            unsafe_allow_html=True,
        )
        st.button("Enter Historical Replay →", use_container_width=True,
                  key="mg_quick_replay",
                  on_click=layout.navigate_to, args=("historical_replay",))
    with c2:
        st.markdown(
            '<div class="mg-entry-title">Risk Watch</div>'
            '<div class="mg-entry-desc">Run a live risk scan on the current '
            "monitoring region and inspect what changed.</div>",
            unsafe_allow_html=True,
        )
        st.button("Enter Risk Watch →", use_container_width=True,
                  key="mg_quick_watch",
                  on_click=layout.navigate_to, args=("risk_watch",))


def render(vm: OverviewViewModel) -> None:
    """Render the full Overview page inside bordered panels."""
    if vm.limitations:
        with st.expander(
            f"Scientific limitations recorded in the latest scan ({len(vm.limitations)})",
            expanded=False,
        ):
            for note in vm.limitations:
                st.markdown(f"- {esc(str(note))}", unsafe_allow_html=False)

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
