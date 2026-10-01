"""
MountainGuardian G04A – Global layout: left navigation + top header.

Frozen information architecture (doc 05 §4–§7):
  four fixed main entries, fixed left navigation, restrained global
  header with page name / region on the left and Model Runtime,
  Last Scan, Data Sources, Active Agents on the right.

Navigation is frozen at G04A; only Overview is fully implemented
(remaining pages render an honest "not yet implemented" state — they
are delivered in G04B and must never fake content).
"""

from __future__ import annotations

from typing import Optional

import streamlit as st

from frontend import theme
from frontend.components import chip, esc, stat_block

# Frozen v1.0 navigation (doc 05 §4). Order is part of the freeze.
NAV_PAGES = (
    ("overview", "总览 · Overview"),
    ("historical_replay", "历史验证 · Historical Replay"),
    ("risk_watch", "风险监测 · Risk Watch"),
    ("intelligence_center", "智能中心 · Intelligence Center"),
)
NAV_KEYS = tuple(key for key, _ in NAV_PAGES)
NAV_LABELS = tuple(label for _, label in NAV_PAGES)

PAGE_TITLES = {
    "overview": ("Overview", "总览"),
    "historical_replay": ("Historical Replay", "历史验证 / Research Validation"),
    "risk_watch": ("Risk Watch", "风险监测"),
    "intelligence_center": ("Intelligence Center", "智能中心"),
}

_NAV_STATE_KEY = "mg_nav_page"

# Small inline SVG mark (Lucide-style line icon — no emoji icons, doc 05 §47).
_LOGO_SVG = (
    '<svg width="26" height="26" viewBox="0 0 24 24" fill="none" '
    'stroke="#37D7E8" stroke-width="1.6" stroke-linecap="round" '
    'stroke-linejoin="round" style="vertical-align:middle;margin-right:9px;">'
    '<path d="m8 3 4 8 5-5 5 15H2L8 3z"/></svg>'
)


def _system_chip_color(state: str) -> str:
    return {
        "ONLINE": theme.GREEN,
        "DEGRADED": theme.ORANGE,
        "NO DATA": theme.TEXT_DIM,
    }.get(state, theme.TEXT_DIM)


def render_sidebar(system_state: str = "NO DATA") -> str:
    """Render logo + frozen navigation + footer status. Returns page key."""
    with st.sidebar:
        st.markdown(
            f"""
<div class="mg-logo">
  <div>{_LOGO_SVG}<span class="mg-logo-title">山河守望者</span></div>
  <div style="margin-left:35px;" class="mg-logo-sub">MountainGuardian</div>
  <div class="mg-logo-rule"></div>
</div>""",
            unsafe_allow_html=True,
        )

        labels = list(NAV_LABELS)
        current = st.session_state.get(_NAV_STATE_KEY, NAV_LABELS[0])
        if current not in labels:
            current = labels[0]
        choice = st.radio(
            "Navigation",
            labels,
            index=labels.index(current),
            label_visibility="collapsed",
            key="mg_nav_radio",
        )
        st.session_state[_NAV_STATE_KEY] = choice
        page_key = NAV_KEYS[labels.index(choice)]

        color = _system_chip_color(system_state)
        st.markdown(
            f"""
<div class="mg-nav-foot">
  Research Prototype · v1.0<br/>
  <span style="color:{color};font-weight:700;">● System {esc(system_state.title())}</span>
</div>""",
            unsafe_allow_html=True,
        )
    return page_key


def navigate_to(page_key: str) -> None:
    """Programmatic navigation (used by Overview quick entries).

    Must run as a button `on_click` callback — widget state cannot be
    modified after the radio has been instantiated during a script run.
    """
    for (key, label) in NAV_PAGES:
        if key == page_key:
            st.session_state[_NAV_STATE_KEY] = label
            st.session_state["mg_nav_radio"] = label
            return


def render_header(
    page_key: str,
    region_label: str = "",
    model_runtime: str = "UNKNOWN",
    last_scan: str = "",
    data_sources: Optional[int] = None,
    agents_txt: str = "—",
    system_state: str = "NO DATA",
) -> None:
    """Global top header (doc 05 §7): page + region left, runtime stats right."""
    title_en, title_zh = PAGE_TITLES.get(page_key, (page_key, ""))

    runtime_color = {
        "CONNECTED": theme.GREEN,
        "FALLBACK": theme.ORANGE,
        "DEGRADED": theme.ORANGE,
        "OFFLINE": theme.RED,
    }.get(model_runtime, theme.TEXT_DIM)
    state_color = _system_chip_color(system_state)

    last_scan_txt = (
        last_scan.replace("T", " ")[:16] + " UTC" if last_scan else "—"
    )
    stats = (
        stat_block("Model Runtime", model_runtime.title(), runtime_color)
        + stat_block("Last Scan", last_scan_txt)
        + stat_block("Data Sources", str(data_sources) if data_sources is not None else "—")
        + stat_block("Agents", agents_txt)
    )
    st.markdown(
        f"""
<div class="mg-header">
  <div>
    <div class="mg-header-title">{esc(title_en)}
      <span style="font-size:13px;color:{theme.TEXT_DIM};font-weight:500;margin-left:10px;">
      {esc(title_zh)}</span>
      &nbsp;{chip(system_state, state_color, small=True)}
    </div>
    <div class="mg-header-region">⛰ {esc(region_label)} · 2D Geospatial Intelligence Console</div>
  </div>
  <div class="mg-header-stats">{stats}</div>
</div>""",
        unsafe_allow_html=True,
    )
