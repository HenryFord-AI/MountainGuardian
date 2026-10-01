"""
MountainGuardian G04A – Reusable UI components.

Small HTML/CSS building blocks shared by all pages (doc 05 §57–§58:
make Streamlit look like a product through structured layout, CSS and
reusable card functions — no heavy frontend framework).

Every component is presentation-only: it receives already-assembled
view-model values and never touches the risk engine or data layer.

Frozen language rules enforced here (doc 05 §11, §62–§63):
  * Risk Index is always annotated "not event probability";
  * risk vocabulary is only LOW / MODERATE / ELEVATED / HIGH;
  * agent status vocabulary follows doc 05 §14 colors, SKIPPED ≠ FAILED.
"""

from __future__ import annotations

import html
from typing import Optional

from frontend import theme

# The mandatory scientific annotation next to every Risk Index display.
RISK_INDEX_NOTE = "Risk Index — not event probability"


def esc(value) -> str:
    return html.escape(str(value if value is not None else ""))


def chip(text: str, color: str, small: bool = False) -> str:
    cls = "mg-chip mg-chip-sm" if small else "mg-chip"
    return (
        f'<span class="{cls}" style="color:{color};border-color:{color}55;'
        f'background:{color}14;">{esc(text)}</span>'
    )


def dot(color: str) -> str:
    return f'<span class="mg-dot" style="background:{color};"></span>'


def card_title(text: str, accent: str = "") -> str:
    label = esc(text)
    if accent:
        label = f'<span class="mg-title-accent">{esc(accent)}</span> {label}'
    return f'<div class="mg-card-title">{label}</div>'


def empty_state(message: str) -> str:
    """Explicit empty state (doc 05 §53) — never leave a blank hole."""
    return f'<div class="mg-empty">◇ &nbsp;{esc(message)}</div>'


def scientific_note(text: str) -> str:
    return f'<div class="mg-sci-note">{esc(text)}</div>'


def stat_block(key: str, value: str, color: Optional[str] = None) -> str:
    style = f' style="color:{color}"' if color else ""
    return (
        f'<div class="mg-stat"><div class="mg-stat-k">{esc(key)}</div>'
        f'<div class="mg-stat-v"{style}>{esc(value)}</div></div>'
    )


# ─── Current Risk card (doc 05 §11) ──────────────────────────────────────────

_TREND_ARROWS = {
    "RISING": ("↑", theme.RED),
    "FALLING": ("↓", theme.GREEN),
    "STABLE": ("→", theme.CYAN),
}


def trend_line(direction: Optional[str], delta: Optional[float]) -> str:
    if not direction or direction == "NO_HISTORY":
        return (
            f'<div class="mg-trend-row"><span class="mg-trend-k">Trend</span>'
            f'<span style="color:{theme.TEXT_DIM};font-size:12px;">'
            f'no prior scan to compare</span></div>'
        )
    arrow, color = _TREND_ARROWS.get(direction, ("→", theme.TEXT_DIM))
    delta_txt = ""
    if delta is not None:
        delta_txt = f" {delta:+.2f}"
    label = direction.title()
    return (
        f'<div class="mg-trend-row"><span class="mg-trend-k">Trend</span>'
        f'<span style="color:{color};font-weight:700;">{arrow}{esc(delta_txt)} '
        f'{esc(label)}</span></div>'
    )


def risk_card_html(
    risk_index_rounded: Optional[float],
    risk_level: Optional[str],
    direction: Optional[str] = None,
    delta: Optional[float] = None,
    required: tuple = (None, None),
    optional: tuple = (None, None),
    last_updated: str = "",
) -> str:
    """The Overview main risk visual: big number + level + trend + coverage.

    Displays stored engine output only. The mandatory note
    "Risk Index — not event probability" is always rendered.
    """
    if risk_index_rounded is None:
        return empty_state(
            "No Risk Watch scan result yet. The Current Risk Index appears "
            "here after the first completed scan (Risk Watch page)."
        )
    color = theme.risk_color(risk_level)
    req_txt = (
        f"{required[0]} / {required[1]}"
        if required[0] is not None and required[1] is not None else "—"
    )
    opt_txt = (
        f"{optional[0]} / {optional[1]}"
        if optional[0] is not None and optional[1] is not None else "—"
    )
    updated = esc(last_updated.replace("T", " ")[:16] + " UTC") if last_updated else "—"
    return f"""
<div>
  <div style="display:flex;align-items:baseline;gap:12px;">
    <span class="mg-metric" style="color:{color};">{risk_index_rounded:.2f}</span>
    <span style="font-size:15px;color:{theme.TEXT_DIM};font-weight:600;">/ 100</span>
  </div>
  <div style="margin:8px 0 12px 0;">{chip(risk_level or "UNKNOWN", color)}</div>
  <div class="mg-trend-row"><span class="mg-trend-k">Evidence</span>
    <span>Required <b>{esc(req_txt)}</b> &nbsp;·&nbsp; Optional <b>{esc(opt_txt)}</b></span></div>
  {trend_line(direction, delta)}
  <div class="mg-trend-row"><span class="mg-trend-k">Last Updated</span>
    <span>{updated}</span></div>
  <div class="mg-metric-note">{esc(RISK_INDEX_NOTE)}</div>
</div>"""


def drivers_html(top_drivers: tuple) -> str:
    """Top risk drivers list (label + contribution points, engine-sourced)."""
    if not top_drivers:
        return empty_state("Driver contributions appear with the next completed scan.")
    rows = []
    for i, (label, points, dtype) in enumerate(top_drivers, start=1):
        pts = f"{points:.2f}" if isinstance(points, (int, float)) else "—"
        tag = "static" if str(dtype).upper() == "STATIC" else "dynamic"
        rows.append(
            f'<div class="mg-trend-row">'
            f'<span><span style="color:{theme.TEXT_DIM};">{i:02d}</span> '
            f'{esc(label)}</span>'
            f'<span style="white-space:nowrap;"><span style="color:{theme.TEXT_DIM};'
            f'font-size:11px;">{esc(tag)}</span> &nbsp;<b>+{esc(pts)}</b></span></div>'
        )
    return "".join(rows)


# ─── Agent collaboration (doc 05 §13–§14) ────────────────────────────────────

def agent_card_html(card) -> str:
    """One agent tile: name, status, confidence, evidence count — nothing
    else. Chain-of-thought / prompts / hidden reasoning are never shown."""
    if card.key == "critic":
        color = theme.critic_color(card.status)
    else:
        color = theme.agent_status_color(card.status)
    ai_cls = " mg-agent-ai" if card.is_ai_layer else ""
    conf = f"{card.confidence:.2f}" if isinstance(card.confidence, (int, float)) else "—"
    if card.evidence_count is None:
        ev_txt = "—"
    else:
        ev_txt = f"{card.evidence_count} evidence"
    status_txt = card.status.replace("_", " ").title()
    extra = (
        f'<div style="font-size:10.5px;color:{theme.TEXT_DIM};margin-top:4px;">'
        f'{esc(card.extra)}</div>' if card.extra else ""
    )
    fallback = (
        f' <span style="color:{theme.ORANGE};font-size:10px;font-weight:700;">'
        f'FALLBACK</span>' if card.fallback_used else ""
    )
    return f"""
<div class="mg-agent-card{ai_cls}">
  {dot(color)} <span class="mg-agent-name">{esc(card.name_en)}</span>{fallback}
  <div class="mg-agent-zh">{esc(card.name_zh)}</div>
  <div class="mg-agent-meta">
    <span style="color:{color};font-weight:700;">● {esc(status_txt)}</span><br/>
    Confidence <b>{esc(conf)}</b> · {esc(ev_txt)}
  </div>
  {extra}
</div>"""


def flow_arrow() -> str:
    return '<div class="mg-flow-arrow">↓</div>'


# ─── Evidence chips ──────────────────────────────────────────────────────────

def evidence_chips_html(evidence_ids) -> str:
    if not evidence_ids:
        return ""
    return "".join(
        f'<span class="mg-evidence-chip">{esc(e)}</span>' for e in evidence_ids
    )
