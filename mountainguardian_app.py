"""
山河守望者 · MountainGuardian v1.0 — Streamlit application entry (G04A).

Geospatial Intelligence × AI Mission Control UI foundation:
  * frozen four-entry left navigation (doc 05 §4);
  * global header with Model Runtime / Last Scan / Data Sources / Agents;
  * Overview page fully implemented (map-first, Current Risk, Agent
    Collaboration, Trend, Evidence Coverage, quick entries);
  * Historical Replay / Risk Watch / Intelligence Center render honest
    G04B placeholders — no faked content.

Run locally:
    streamlit run mountainguardian_app.py

Session rules (doc 06 §72): page reruns only re-read local structured
data (region config + SQLite snapshots). Nothing here calls DeepSeek,
runs a Risk Scan, downloads anything or writes to the snapshot store.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Repo root on sys.path so `frontend` and `riskwatch` import cleanly.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st

# ─── Page configuration (must be the first Streamlit call) ───────────────────
st.set_page_config(
    page_title="山河守望者 · MountainGuardian",
    page_icon="⛰️",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": None,
        "Report a bug": None,
        "About": (
            "山河守望者 MountainGuardian v1.0 — Research Prototype. "
            "Geospatial Intelligence × AI Mission Control. "
            "Research risk assessment — not an official disaster warning."
        ),
    },
)

from frontend import layout, theme                      # noqa: E402
from frontend.pages import coming_soon, overview        # noqa: E402
from frontend.viewmodels import build_overview_viewmodel  # noqa: E402

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("mountainguardian.ui")

theme.inject_css()

# ─── Read-only view model (safe on every rerun) ──────────────────────────────
try:
    vm = build_overview_viewmodel()
    vm_error = None
except Exception as exc:  # region/db unreadable → honest degraded UI, no fake data
    logger.exception("Overview view model failed to load")
    vm = None
    vm_error = exc

# ─── Shell: navigation + header ──────────────────────────────────────────────
system_state = vm.system_state if vm is not None else "NO DATA"
page_key = layout.render_sidebar(system_state=system_state)

if vm is not None:
    agents_txt = (
        f"{vm.agents_executed} / {vm.agents_total}" if vm.has_result else "—"
    )
    layout.render_header(
        page_key,
        region_label=vm.region_label,
        model_runtime=vm.model_runtime,
        last_scan=vm.last_updated or "",
        data_sources=vm.data_source_count,
        agents_txt=agents_txt,
        system_state=system_state,
    )
else:
    layout.render_header(page_key, system_state=system_state)

# ─── Page dispatch ────────────────────────────────────────────────────────────
if page_key == "overview":
    if vm is not None:
        overview.render(vm)
    else:
        with st.container(border=True):
            st.error(
                "Region configuration or snapshot database could not be read. "
                "The UI shows no data rather than fabricated values."
            )
            st.caption(f"Detail: {type(vm_error).__name__}: {vm_error}")
else:
    coming_soon.render(page_key)
