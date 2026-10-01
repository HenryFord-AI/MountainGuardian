"""
MountainGuardian G04A – Honest placeholder for frozen navigation entries.

The four main entries are frozen at G04A (doc 05 §4), but only Overview
is implemented in this Gate. Historical Replay, Risk Watch and
Intelligence Center are delivered in G04B. These pages must never fake
content, fake data or fake scans — they state exactly what is coming and
where the underlying capability already lives.
"""

from __future__ import annotations

import streamlit as st

from frontend.components import card_title, esc

_PAGE_NOTES = {
    "historical_replay": (
        "Historical Replay / Research Validation",
        "Replays the frozen 2026-08-26 Jilong case using pre-event evidence "
        "only: Pre/Event/Post timeline, agent reasoning cards, Baseline "
        "Susceptibility result, Critic review and post-event validation. "
        "The backend replay capability already exists — this page wires it "
        "into the product UI in Gate G04B.",
    ),
    "risk_watch": (
        "Risk Watch / 当前风险监测",
        "One primary action: Run Risk Scan. Live scan progress, Current "
        "Risk, 7-Day Outlook, Historical Trend, What Changed and Data "
        "Coverage. The end-to-end scan workflow already exists — this page "
        "exposes it in the product UI in Gate G04B.",
    ),
    "intelligence_center": (
        "Intelligence Center / 智能中心",
        "Three tabs: Agent Workspace, Evidence Center, Audit & Safety — "
        "explaining how the multi-agent system works with full provenance. "
        "Delivered in Gate G04B.",
    ),
}


def render(page_key: str) -> None:
    title, note = _PAGE_NOTES.get(
        page_key, (page_key.replace("_", " ").title(), "")
    )
    with st.container(border=True):
        st.markdown(card_title("Planned Page", accent="◇"), unsafe_allow_html=True)
        st.markdown(
            f'<div class="mg-entry-title" style="font-size:17px;">{esc(title)}</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="mg-empty" style="max-width:640px;">'
            "This navigation entry is frozen in the v1.0 information "
            "architecture. Its full UI implementation is scheduled in Gate "
            "G04B — UI Product Pages. Nothing on this page is simulated: "
            "no fake data, no fake scans.</div>",
            unsafe_allow_html=True,
        )
        if note:
            st.caption(note)
