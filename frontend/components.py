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


def flow_arrow_right() -> str:
    """Horizontal DAG connector (Intelligence Center, doc 03 §2)."""
    return '<div class="mg-dag-arrow">→</div>'


# ─── G04B shared product-page components ────────────────────────────────────

# Single-quote font list for SVG style attributes (double quotes delimit them).
_SVG_FONT = "'Inter','Microsoft YaHei','PingFang SC','Noto Sans SC',Arial,sans-serif"


def ring_gauge_html(
    value: Optional[float],
    color: str,
    size: int = 128,
    stroke: int = 9,
) -> str:
    """Restrained donut ring around the dominant number (doc 05 §49).

    Pure presentation of an already-computed backend value; the number
    always stays the primary visual, the ring is auxiliary.
    """
    if value is None:
        return ""
    clamped = max(0.0, min(100.0, float(value)))
    r = (size - stroke) / 2.0
    circ = 2 * 3.141592653589793 * r
    filled = circ * clamped / 100.0
    big = size // 4
    small = max(9, size // 11)
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" '
        f'role="img" aria-label="index {clamped:.1f} of 100">'
        f'<circle cx="{size/2}" cy="{size/2}" r="{r}" fill="none" '
        f'stroke="rgba(120,160,200,0.16)" stroke-width="{stroke}"/>'
        f'<circle cx="{size/2}" cy="{size/2}" r="{r}" fill="none" '
        f'stroke="{color}" stroke-width="{stroke}" stroke-linecap="round" '
        f'stroke-dasharray="{filled:.1f} {circ - filled:.1f}" '
        f'transform="rotate(-90 {size/2} {size/2})"/>'
        f'<text x="50%" y="47%" text-anchor="middle" fill="{color}" '
        f'style="font:750 {big}px {_SVG_FONT};">{clamped:g}</text>'
        f'<text x="50%" y="66%" text-anchor="middle" fill="{theme.TEXT_DIM}" '
        f'style="font:600 {small}px {_SVG_FONT};">'
        f'/ 100</text></svg>'
    )


def kv_row(key: str, value: str, color: Optional[str] = None) -> str:
    style = f' style="color:{color};font-weight:650;"' if color else ""
    return (
        f'<div class="mg-kv"><span class="mg-kv-k">{esc(key)}</span>'
        f'<span{style}>{esc(value)}</span></div>'
    )


def timeline_html(stages: tuple) -> str:
    """PRE-EVENT / EVENT / POST-EVENT separation strip (doc 05 §17).

    stages: (label_en, label_zh, when_txt, color, note) tuples in order.
    """
    parts = []
    for i, (label_en, label_zh, when, color, note) in enumerate(stages):
        if i:
            parts.append('<div class="mg-stage-join">→</div>')
        parts.append(
            f'<div class="mg-stage" style="border-color:{color}44;">'
            f'<div class="mg-stage-k" style="color:{color};">{esc(label_en)}</div>'
            f'<div class="mg-stage-v">{esc(when)}</div>'
            f'<div class="mg-stage-n">{esc(label_zh)}{(" · " + esc(note)) if note else ""}</div>'
            f'</div>'
        )
    return f'<div class="mg-timeline">{"".join(parts)}</div>'


def evidence_row_html(
    evidence_id: str,
    type_label: str,
    source: str,
    observed: str,
    phase: str,
    quality: str,
    note: str = "",
) -> str:
    """One provenance row (doc 05 §18/§35): id, source, date, phase, quality."""
    phase_color = {
        "PRE-EVENT": theme.CYAN,
        "EVENT": theme.ORANGE,
        "POST-EVENT": theme.PURPLE,
    }.get(phase.upper(), theme.TEXT_DIM)
    qual_color = {
        "GOOD": theme.GREEN, "LIMITED": theme.ORANGE,
        "STALE": theme.ORANGE, "MISSING": theme.RED,
    }.get(quality.upper(), theme.TEXT_DIM)
    note_html = f'<div class="mg-ev-meta">{esc(note)}</div>' if note else ""
    return (
        f'<div class="mg-ev-row"><div>'
        f'<span class="mg-ev-id">{esc(evidence_id)}</span> '
        f'<b>{esc(type_label)}</b>'
        f'<div class="mg-ev-meta">{esc(source)} · {esc(observed)}</div>'
        f'{note_html}'
        f'</div><div style="text-align:right;white-space:nowrap;">'
        f'{chip(phase, phase_color, small=True)} '
        f'{chip(quality or "—", qual_color, small=True)}</div></div>'
    )


def coverage_row_html(
    label: str,
    status: str,
    color: str,
    quality: str = "",
    note: str = "",
) -> str:
    """Data-coverage source row (doc 05 §31) — honest availability states."""
    qual_color = {
        "GOOD": theme.GREEN, "LIMITED": theme.ORANGE,
        "STALE": theme.ORANGE, "MISSING": theme.RED,
    }.get(quality.upper(), theme.TEXT_DIM)
    qual = f' {chip(quality, qual_color, small=True)}' if quality else ""
    note_html = f'<div class="mg-ev-meta">{esc(note)}</div>' if note else ""
    return (
        f'<div class="mg-ev-row"><div><b>{esc(label)}</b>'
        f'{note_html}</div>'
        f'<div style="text-align:right;white-space:nowrap;">'
        f'<span style="color:{color};font-weight:650;">{esc(status)}</span>{qual}'
        f'</div></div>'
    )


def scan_steps_html(steps: tuple) -> str:
    """Six-step workflow lifecycle (doc 05 §26), real stage timestamps only.

    steps: (num, label_zh, label_en, state, ts_txt); state ∈ DONE/PENDING/FAILED.
    """
    colors = {"DONE": theme.GREEN, "PENDING": theme.TEXT_DIM,
              "FAILED": theme.RED, "RUNNING": theme.CYAN}
    parts = []
    for i, (num, zh, en, state, ts_txt) in enumerate(steps):
        if i:
            parts.append('<div class="mg-step-join">→</div>')
        color = colors.get(state, theme.TEXT_DIM)
        mark = {"DONE": "✓", "FAILED": "✕", "RUNNING": "●"}.get(state, str(num))
        parts.append(
            f'<div class="mg-step">'
            f'<div class="mg-step-n" style="color:{color};border-color:{color}66;'
            f'background:{color}12;">{mark}</div>'
            f'<div class="mg-step-zh">{esc(zh)}</div>'
            f'<div class="mg-step-en">{esc(en)}</div>'
            f'<div class="mg-step-ts">{esc(ts_txt)}</div></div>'
        )
    return f'<div class="mg-steps">{"".join(parts)}</div>'


def critic_panel_html(
    review_result: str,
    severity: str,
    issues: tuple,
    limitations: tuple,
    corrections: tuple = (),
    checks: tuple = (),
    attestation: str = "",
) -> str:
    """Structured Critic card (doc 05 §21): verdict, issues, limitations.

    issues: (check_id, severity, message) tuples; checks: (check_id, ok)
    tuples of the frozen programmatic review dimensions. No prose walls.
    """
    color = theme.critic_color(review_result)
    rows = []
    for check_id, ok in checks:
        mark, mcolor = ("✓", theme.GREEN) if ok else ("!", theme.ORANGE)
        rows.append(
            f'<div class="mg-issue-row"><span style="color:{mcolor};'
            f'font-weight:700;">{mark}</span> {esc(check_id.replace("_", " ").title())}'
            f'</div>'
        )
    for check_id, sev, message in issues:
        sev_color = {"CRITICAL": theme.RED, "WARNING": theme.ORANGE}.get(
            sev, theme.TEXT_DIM)
        rows.append(
            f'<div class="mg-issue-row"><span style="color:{sev_color};'
            f'font-weight:700;">!</span> [{esc(sev)}] {esc(message)}'
            f' <span class="mg-ev-meta">({esc(check_id)})</span></div>'
        )
    for note in limitations:
        rows.append(
            f'<div class="mg-issue-row"><span style="color:{theme.TEXT_DIM};'
            f'font-weight:700;">·</span> {esc(note)}</div>'
        )
    for note in corrections:
        rows.append(
            f'<div class="mg-issue-row"><span style="color:{theme.ORANGE};'
            f'font-weight:700;">→</span> {esc(note)}</div>'
        )
    body = "".join(rows) or empty_state("No critic records in this run.")
    att = (
        f'<div class="mg-metric-note">{esc(attestation)}</div>' if attestation else ""
    )
    return (
        f'<div class="mg-critic-panel">'
        f'<div style="display:flex;justify-content:space-between;'
        f'align-items:center;gap:8px;margin-bottom:8px;">'
        f'<span style="font-weight:750;color:{color};letter-spacing:0.06em;">'
        f'{esc(review_result.replace("_", " "))}</span>'
        f'{chip(("severity " + severity) if severity else "review", color, small=True)}'
        f'</div>{body}{att}</div>'
    )


def safety_rows_html(rows: tuple) -> str:
    """Descriptive safety-control indicators (doc 03 §外围 Guard, doc 06 §76).

    rows: (name, state, color, detail). Read-only by construction — the UI
    exposes no control that can disable any guard.
    """
    parts = []
    for name, state, color, detail in rows:
        parts.append(
            f'<div class="mg-ev-row"><div><b>{esc(name)}</b>'
            f'<div class="mg-ev-meta">{esc(detail)}</div></div>'
            f'<div style="white-space:nowrap;">{chip(state, color, small=True)}'
            f'</div></div>'
        )
    return "".join(parts)


def table_html(headers: tuple, rows: tuple) -> str:
    """Compact dark table (audit log / provenance, doc 05 §37)."""
    if not rows:
        return empty_state("No records available.")
    head = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = []
    for row in rows:
        cells = "".join(f"<td>{esc(c)}</td>" for c in row)
        body.append(f"<tr>{cells}</tr>")
    return (
        f'<table class="mg-table"><thead><tr>{head}</tr></thead>'
        f'<tbody>{"".join(body)}</tbody></table>'
    )


# ─── Evidence chips ──────────────────────────────────────────────────────────

def evidence_chips_html(evidence_ids) -> str:
    if not evidence_ids:
        return ""
    return "".join(
        f'<span class="mg-evidence-chip">{esc(e)}</span>' for e in evidence_ids
    )
