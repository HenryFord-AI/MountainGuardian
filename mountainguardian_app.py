"""
山河守望者 · MountainGuardian v1.0 — Streamlit application entry (G04B).

Geospatial Intelligence × AI Mission Control:
  * frozen four-entry left navigation (doc 05 §4);
  * global header with Model Runtime / Last Scan / Data Sources / Agents;
  * Overview (G04A), Historical Replay, Risk Watch and Intelligence Center
    (G04B) — all four product pages consume read-only view models over the
    frozen backend contracts; no page fabricates data.

Run locally:
    streamlit run mountainguardian_app.py

Session rules (doc 06 §72): page reruns only re-read local structured data
(region config + SQLite snapshots + frozen Case Pack). The single exception
is the Risk Watch page's explicit Run Risk Scan CTA, which calls the frozen
G03C orchestration entry point on user request (gate G04B §10.1).
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
            "山河守望者 MountainGuardian v1.0 — 研究原型。"
            "地理空间智能 × AI 任务控制台。"
            "研究性风险评估 — 非官方灾害告警。"
        ),
    },
)

from frontend import layout, theme                      # noqa: E402
from frontend.pages import (                            # noqa: E402
    coming_soon,
    historical_replay,
    intelligence_center,
    overview,
    risk_watch,
)
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
                "无法读取区域配置或快照数据库。"
                "界面不显示任何数据，而不是显示伪造数值。"
            )
            st.caption(f"详情：{type(vm_error).__name__}: {vm_error}")
elif page_key == "historical_replay":
    historical_replay.render()
elif page_key == "risk_watch":
    risk_watch.render()
elif page_key == "intelligence_center":
    intelligence_center.render()
else:
    coming_soon.render(page_key)
