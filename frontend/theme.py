"""
MountainGuardian G04A – Global dark design system (theme tokens + CSS).

Frozen visual direction (doc 05 §2, §39–§48):
  Geospatial Intelligence × AI Mission Control — deep navy background,
  glacier/data cyan as primary accent, limited orange/red for risk,
  limited AI purple for model/agent semantics. No neon, no gaming UI,
  no large gradients, no decorative animation.

This module owns:
  * the frozen color tokens (doc 05 §39.1–§40);
  * risk level → color mapping (doc 05 §12);
  * agent status → color mapping (doc 05 §14);
  * typography / spacing / radius tokens (doc 05 §42–§45);
  * one `inject_css()` entry point used by the application shell.

UI never computes risk here — this file is pure presentation.
"""

from __future__ import annotations

# ─── Background & panels (doc 05 §39) ────────────────────────────────────────
BG = "#07111F"                # deep navy / near black
PANEL = "#101C2D"             # primary panel
PANEL_ALT = "#142338"         # secondary panel
BORDER = "rgba(120,160,200,0.18)"
BORDER_STRONG = "rgba(120,160,200,0.28)"

# ─── Accents (doc 05 §40) ────────────────────────────────────────────────────
CYAN = "#37D7E8"              # glacier / data cyan — primary accent
PURPLE = "#8B7CFF"            # AI purple — model / agent semantics
GREEN = "#42D392"             # normal / completed
ORANGE = "#FFB454"            # elevated / degraded
RED = "#FF5E6C"               # high risk / failed
TEXT = "#DCE7F3"              # neutral text
TEXT_DIM = "#8799AD"          # secondary text

# ─── Risk level colors (doc 05 §12) ──────────────────────────────────────────
# Only LOW / MODERATE / ELEVATED / HIGH may be used as risk terms.
# Statutory government warning-level terminology and colors are forbidden
# in this product (doc 05 §12/§62) — these bands are research vocabulary.
RISK_LEVEL_COLORS = {
    "LOW": GREEN,
    "MODERATE": "#A8CE3C",     # teal / yellow-green
    "ELEVATED": ORANGE,
    "HIGH": RED,
}

# ─── Agent status colors (doc 05 §14) ────────────────────────────────────────
# SKIPPED (gray-blue) must never look like FAILED (red).
AGENT_STATUS_COLORS = {
    "PENDING": "#6B7A8D",
    "RUNNING": CYAN,
    "COMPLETED": GREEN,
    "SKIPPED": "#5A7089",
    "DEGRADED": ORANGE,
    "FAILED": RED,
}

# Critic review results (doc 04/05 §21) — visually distinct, purple family.
CRITIC_RESULT_COLORS = {
    "PASS": GREEN,
    "PASS_WITH_LIMITATIONS": ORANGE,
    "NEEDS_REVISION": ORANGE,
    "FAIL": RED,
    "FAILED": RED,
    "UNAVAILABLE": "#6B7A8D",
}

# ─── Typography (doc 05 §42–§43) ─────────────────────────────────────────────
FONT_STACK = (
    '"Inter", "Microsoft YaHei", "PingFang SC", "Noto Sans SC", '
    "Arial, Helvetica, sans-serif"
)
FONT_MONO = '"Cascadia Mono", "JetBrains Mono", Consolas, monospace'

# ─── Geometry (doc 05 §44–§45) ───────────────────────────────────────────────
RADIUS = "10px"               # 8–12px
SPACING = (8, 16, 24, 32)     # 8pt grid


def risk_color(level: str | None) -> str:
    """Semantic color for a frozen risk level; unknown → dim gray."""
    return RISK_LEVEL_COLORS.get((level or "").upper(), TEXT_DIM)


def agent_status_color(status: str | None) -> str:
    return AGENT_STATUS_COLORS.get((status or "").upper(), TEXT_DIM)


def critic_color(result: str | None) -> str:
    return CRITIC_RESULT_COLORS.get((result or "").upper(), PURPLE)


# ─── Global CSS ──────────────────────────────────────────────────────────────
# Injected once by the app shell. Styles both native Streamlit containers and
# the .mg-* component classes used by frontend/components.py.
_CSS = f"""
/* ══ Streamlit chrome ══════════════════════════════════════════════════ */
html, body, [data-testid="stAppViewContainer"] {{
    background-color: {BG};
    color: {TEXT};
    font-family: {FONT_STACK};
}}
header[data-testid="stHeader"] {{ background: transparent; }}
#MainMenu, footer, [data-testid="stStatusWidget"] {{ visibility: hidden; }}
.block-container {{ padding-top: 0.6rem; padding-bottom: 1.5rem; max-width: 1600px; }}

/* ══ Sidebar / left navigation (doc 05 §6) ═════════════════════════════ */
section[data-testid="stSidebar"] {{
    background: linear-gradient(180deg, #0A1626 0%, {BG} 100%);
    border-right: 1px solid {BORDER};
}}
section[data-testid="stSidebar"] > div:first-child {{ padding-top: 0.5rem; }}
.mg-logo {{ padding: 10px 6px 4px 6px; }}
.mg-logo-title {{
    font-size: 19px; font-weight: 700; letter-spacing: 0.06em; color: {TEXT};
}}
.mg-logo-sub {{
    font-size: 11px; letter-spacing: 0.22em; color: {CYAN};
    text-transform: uppercase; margin-top: 2px; font-weight: 600;
}}
.mg-logo-rule {{
    height: 1px; background: {BORDER_STRONG}; margin: 14px 2px 10px 2px;
}}
/* nav radio → mission-control nav items */
section[data-testid="stSidebar"] [data-testid="stRadio"] > label {{ display: none; }}
section[data-testid="stSidebar"] label[data-baseweb="radio"] {{
    background: transparent; border: 1px solid transparent;
    border-radius: 8px; margin: 3px 0; padding: 7px 10px;
    width: 100%; transition: background 120ms ease;
}}
section[data-testid="stSidebar"] label[data-baseweb="radio"]:hover {{
    background: rgba(55,215,232,0.06);
}}
section[data-baseweb="radio"] > span:first-of-type {{ display: none; }} /* hide circle */
section[data-testid="stSidebar"] label[data-baseweb="radio"]:has(input:checked) {{
    background: rgba(55,215,232,0.10);
    border: 1px solid rgba(55,215,232,0.35);
    box-shadow: 0 0 10px rgba(55,215,232,0.10) inset;
}}
section[data-testid="stSidebar"] label[data-baseweb="radio"] div[data-testid="stMarkdownContainer"] p {{
    font-size: 13.5px; font-weight: 600; color: {TEXT_DIM}; letter-spacing: 0.02em;
}}
section[data-testid="stSidebar"] label[data-baseweb="radio"]:has(input:checked) div[data-testid="stMarkdownContainer"] p {{
    color: {TEXT};
}}
.mg-nav-foot {{
    position: relative; margin-top: 26px; padding: 10px 8px;
    border-top: 1px solid {BORDER};
    font-size: 11px; color: {TEXT_DIM}; line-height: 1.7; letter-spacing: 0.03em;
}}

/* ══ Panels / cards ════════════════════════════════════════════════════ */
div[data-testid="stVerticalBlockBorderWrapper"] {{
    background: {PANEL};
    border: 1px solid {BORDER} !important;
    border-radius: {RADIUS};
}}
.mg-panel {{
    background: {PANEL}; border: 1px solid {BORDER};
    border-radius: {RADIUS}; padding: 16px 18px;
}}
.mg-panel-alt {{
    background: {PANEL_ALT}; border: 1px solid {BORDER};
    border-radius: {RADIUS}; padding: 14px 16px;
}}
.mg-card-title {{
    font-size: 11.5px; font-weight: 700; letter-spacing: 0.18em;
    text-transform: uppercase; color: {TEXT_DIM}; margin-bottom: 10px;
}}
.mg-card-title .mg-title-accent {{ color: {CYAN}; }}

/* ══ Big numbers (doc 05 §3.3, §43) ════════════════════════════════════ */
.mg-metric {{
    font-size: 40px; font-weight: 750; line-height: 1.05;
    font-variant-numeric: tabular-nums; letter-spacing: -0.01em;
}}
.mg-metric-sub {{ font-size: 13px; color: {TEXT_DIM}; margin-top: 2px; }}
.mg-metric-note {{
    font-size: 11px; color: {TEXT_DIM}; margin-top: 8px;
    letter-spacing: 0.02em;
}}

/* ══ Chips / badges ════════════════════════════════════════════════════ */
.mg-chip {{
    display: inline-block; padding: 2.5px 9px; border-radius: 999px;
    font-size: 11px; font-weight: 700; letter-spacing: 0.10em;
    text-transform: uppercase; border: 1px solid;
}}
.mg-dot {{ display: inline-block; width: 8px; height: 8px; border-radius: 50%; }}
.mg-chip-sm {{ font-size: 10.5px; padding: 1.5px 8px; letter-spacing: 0.08em; }}

/* ══ Global header (doc 05 §7) ═════════════════════════════════════════ */
.mg-header {{
    display: flex; justify-content: space-between; align-items: center;
    gap: 16px; padding: 12px 4px 14px 4px; flex-wrap: wrap;
    border-bottom: 1px solid {BORDER}; margin-bottom: 16px;
}}
.mg-header-title {{ font-size: 21px; font-weight: 700; letter-spacing: 0.01em; }}
.mg-header-region {{ font-size: 12.5px; color: {TEXT_DIM}; margin-top: 3px; }}
.mg-header-stats {{ display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }}
.mg-stat {{
    background: {PANEL_ALT}; border: 1px solid {BORDER}; border-radius: 8px;
    padding: 6px 12px; min-width: 108px;
}}
.mg-stat-k {{
    font-size: 10px; letter-spacing: 0.14em; text-transform: uppercase;
    color: {TEXT_DIM}; font-weight: 600;
}}
.mg-stat-v {{ font-size: 13.5px; font-weight: 650; margin-top: 2px; color: {TEXT}; }}

/* ══ Agent collaboration flow (doc 05 §13) ═════════════════════════════ */
.mg-agent-card {{
    background: {PANEL_ALT}; border: 1px solid {BORDER}; border-radius: 9px;
    padding: 10px 12px; height: 100%;
}}
.mg-agent-card.mg-agent-ai {{ border-color: rgba(139,124,255,0.38); }}
.mg-agent-name {{ font-size: 12.5px; font-weight: 700; line-height: 1.3; }}
.mg-agent-zh {{ font-size: 11px; color: {TEXT_DIM}; margin-top: 1px; }}
.mg-agent-meta {{
    font-size: 11.5px; color: {TEXT_DIM}; margin-top: 7px; line-height: 1.75;
    font-variant-numeric: tabular-nums;
}}
.mg-flow-arrow {{
    text-align: center; color: {TEXT_DIM}; font-size: 15px; padding: 2px 0;
}}
.mg-evidence-chip {{
    display: inline-block; font-family: {FONT_MONO}; font-size: 10.5px;
    color: {CYAN}; background: rgba(55,215,232,0.07);
    border: 1px solid rgba(55,215,232,0.22); border-radius: 5px;
    padding: 1px 6px; margin: 2px 3px 2px 0;
}}

/* ══ States (doc 05 §52–§55) ═══════════════════════════════════════════ */
.mg-empty {{
    color: {TEXT_DIM}; font-size: 13px; padding: 14px 2px; line-height: 1.7;
}}
.mg-fallback {{
    display: inline-block; background: rgba(255,180,84,0.10);
    border: 1px solid rgba(255,180,84,0.45); color: {ORANGE};
    border-radius: 8px; padding: 6px 12px; font-size: 12px; font-weight: 700;
    letter-spacing: 0.08em; text-transform: uppercase;
}}
.mg-sci-note {{
    font-size: 11px; color: {TEXT_DIM}; letter-spacing: 0.02em;
    border-left: 2px solid rgba(55,215,232,0.4); padding: 2px 0 2px 10px;
    margin-top: 10px;
}}

/* ══ Trend list ════════════════════════════════════════════════════════ */
.mg-trend-row {{
    display: flex; justify-content: space-between; align-items: baseline;
    padding: 6px 0; border-bottom: 1px dashed {BORDER};
    font-size: 12.5px; font-variant-numeric: tabular-nums;
}}
.mg-trend-row:last-child {{ border-bottom: none; }}
.mg-trend-k {{ color: {TEXT_DIM}; }}

/* ══ Map ═══════════════════════════════════════════════════════════════ */
.mg-map-frame {{
    border: 1px solid {BORDER}; border-radius: {RADIUS}; overflow: hidden;
}}
.mg-map-caption {{ font-size: 11px; color: {TEXT_DIM}; margin-top: 6px; line-height: 1.6; }}

/* ══ Quick entry cards ═════════════════════════════════════════════════ */
.mg-entry-title {{ font-size: 14px; font-weight: 700; }}
.mg-entry-desc {{ font-size: 12px; color: {TEXT_DIM}; margin-top: 4px; line-height: 1.6; }}

/* ══ Generic markdown polish ═══════════════════════════════════════════ */
[data-testid="stMarkdownContainer"] p {{ line-height: 1.55; }}
section[data-testid="stSidebar"] .stButton button {{
    background: rgba(55,215,232,0.08); border: 1px solid rgba(55,215,232,0.35);
    color: {CYAN}; font-weight: 650; letter-spacing: 0.04em; border-radius: 8px;
}}
section[data-testid="stSidebar"] .stButton button:hover {{
    background: rgba(55,215,232,0.16); border-color: {CYAN};
}}
.stButton button {{ border-radius: 8px; }}
div[data-testid="stExpander"] details {{
    background: {PANEL_ALT}; border: 1px solid {BORDER}; border-radius: 8px;
}}
div[data-testid="stExpander"] summary {{ font-size: 12.5px; color: {TEXT_DIM}; }}
"""


def inject_css() -> None:
    """Inject the frozen MountainGuardian design system into the app."""
    import streamlit as st

    st.markdown(f"<style>{_CSS}</style>", unsafe_allow_html=True)
