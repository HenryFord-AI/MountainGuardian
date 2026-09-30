"""
MountainGuardian G03B – deterministic "What Changed" comparison and previous
valid-result resolution.

Compares the current deterministic result against the previous ELIGIBLE
Risk Watch snapshot. No LLM summarization, no new scientific significance
thresholds: precipitation comparisons use plain deterministic
UP / UNCHANGED / DOWN; Risk Direction remains governed solely by the frozen
±5-point C rule (formulas.classify_direction).

Optional evidence comparison describes AVAILABILITY changes only — optional
values never change numeric risk (doc 04 §19).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from riskwatch.engine.formulas import (
    CHANGE_DOWN,
    CHANGE_NOT_COMPARABLE,
    CHANGE_UNCHANGED,
    CHANGE_UP,
    DIRECTION_NO_HISTORY,
    DIRECTION_THRESHOLD_POINTS,
    VALID_RESULT_STATUSES,
    classify_direction,
)
from riskwatch.snapshot_store import SCAN_MODE_BACKFILL


@dataclass(frozen=True)
class PreviousState:
    """Extracted comparable state of a previous valid Risk Watch snapshot."""

    snapshot_id: str
    created_at: str
    scan_mode: str
    current_C: Optional[float]
    recent_precip_by_point: dict = field(default_factory=dict)
    forecast_precip_by_point: dict = field(default_factory=dict)
    missing_point_ids: tuple = ()
    optional_evidence_ids: tuple = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "created_at": self.created_at,
            "scan_mode": self.scan_mode,
            "current_C": self.current_C,
            "recent_precip_by_point": dict(self.recent_precip_by_point),
            "forecast_precip_by_point": dict(self.forecast_precip_by_point),
            "missing_point_ids": list(self.missing_point_ids),
            "optional_evidence_ids": list(self.optional_evidence_ids),
        }


def _numeric(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _point_precip_map(payload: dict[str, Any], key: str) -> dict[str, Optional[float]]:
    out: dict[str, Optional[float]] = {}
    section = payload.get(key)
    if isinstance(section, dict):
        for pid, rec in section.items():
            if isinstance(rec, dict):
                out[str(pid)] = _numeric(rec.get("cumulative_precip_mm"))
    return out


def previous_state_from_snapshot(snapshot: dict[str, Any]) -> Optional[PreviousState]:
    """Extract PreviousState from a stored snapshot row, or None if ineligible.

    Eligibility (frozen): not flagged invalid, status is an official Risk
    Watch result status (COMPLETED / COMPLETED_WITH_LIMITATIONS) and the
    payload carries a numeric Current Risk Index. Data-only snapshots (e.g.
    G03A weather snapshots with status OK) are NOT eligible history.
    """
    if not isinstance(snapshot, dict):
        return None
    if int(snapshot.get("is_invalid", 0) or 0) != 0:
        return None
    status = str(snapshot.get("status", ""))
    if status not in VALID_RESULT_STATUSES:
        return None
    payload = snapshot.get("payload")
    if not isinstance(payload, dict):
        return None
    current_c = _numeric(payload.get("current_risk_index", payload.get("C")))
    if current_c is None:
        return None
    missing_ids: set[str] = set()
    for rec in payload.get("missing_data", []) or []:
        if isinstance(rec, dict) and rec.get("point_id"):
            missing_ids.add(str(rec["point_id"]))
    optional_ids = tuple(
        str(x) for x in (payload.get("optional_evidence_availability", []) or [])
    )
    return PreviousState(
        snapshot_id=str(snapshot.get("snapshot_id", "")),
        created_at=str(snapshot.get("created_at", "")),
        scan_mode=str(snapshot.get("scan_mode", "")),
        current_C=current_c,
        recent_precip_by_point=_point_precip_map(payload, "point_recent_percentiles"),
        forecast_precip_by_point=_point_precip_map(payload, "point_forecast_percentiles"),
        missing_point_ids=tuple(sorted(missing_ids)),
        optional_evidence_ids=optional_ids,
    )


def load_previous_state(
    store,
    region_id: str,
    include_backfill: bool = False,
) -> Optional[PreviousState]:
    """Most recent eligible previous result (read-only store access).

    BACKFILL snapshots are excluded by default so a backfilled record can
    never silently masquerade as live history; when included they stay
    explicitly labeled via PreviousState.scan_mode.
    """
    candidates: list[PreviousState] = []
    for row in store.list_snapshots(region_id):
        if not include_backfill and str(row.get("scan_mode", "")) == SCAN_MODE_BACKFILL:
            continue
        state = previous_state_from_snapshot(row)
        if state is not None:
            candidates.append(state)
    if not candidates:
        return None
    return candidates[-1]  # list_snapshots is append-only id order


def _compare_numeric(
    previous: Optional[float], current: Optional[float]
) -> dict[str, Any]:
    if previous is None or current is None:
        return {
            "previous": previous,
            "current": current,
            "delta": None,
            "direction": CHANGE_NOT_COMPARABLE,
        }
    delta = current - previous
    if delta > 0:
        direction = CHANGE_UP
    elif delta < 0:
        direction = CHANGE_DOWN
    else:
        direction = CHANGE_UNCHANGED
    return {
        "previous": previous,
        "current": current,
        "delta": delta,
        "direction": direction,
    }


def build_what_changed(
    current_C: Optional[float],
    current_recent_precip_by_point: dict[str, Optional[float]],
    current_forecast_precip_by_point: dict[str, Optional[float]],
    current_missing_point_ids,
    current_optional_evidence_ids,
    previous: Optional[PreviousState],
) -> dict[str, Any]:
    """Deterministic comparison against the previous eligible result."""
    current_missing = {str(p) for p in current_missing_point_ids}
    current_optional = {str(e) for e in current_optional_evidence_ids}
    if previous is None or previous.current_C is None:
        return {
            "status": DIRECTION_NO_HISTORY,
            "note": (
                "No previous eligible Risk Watch result exists; nothing to "
                "compare. History is never fabricated."
            ),
        }
    previous_missing = {str(p) for p in previous.missing_point_ids}
    previous_optional = {str(e) for e in previous.optional_evidence_ids}

    delta_c = None
    direction = CHANGE_NOT_COMPARABLE
    if current_C is not None:
        delta_c = current_C - previous.current_C
        direction = classify_direction(delta_c)

    precip_point_ids = sorted(
        set(previous.recent_precip_by_point) | set(current_recent_precip_by_point)
    )
    forecast_point_ids = sorted(
        set(previous.forecast_precip_by_point) | set(current_forecast_precip_by_point)
    )
    return {
        "status": "COMPARISON_AVAILABLE",
        "previous_snapshot_id": previous.snapshot_id,
        "previous_created_at": previous.created_at,
        "previous_scan_mode": previous.scan_mode,
        "current_risk": {
            "previous": previous.current_C,
            "current": current_C,
            "delta": delta_c,
            "direction": direction,
            "rule": "frozen +/-5 index-point Risk Direction rule",
            "threshold_points": DIRECTION_THRESHOLD_POINTS,
            "note": (
                "Product readability threshold, not statistical significance."
            ),
        },
        "recent_precipitation": {
            pid: _compare_numeric(
                previous.recent_precip_by_point.get(pid),
                current_recent_precip_by_point.get(pid),
            )
            for pid in precip_point_ids
        },
        "forecast_precipitation": {
            pid: _compare_numeric(
                previous.forecast_precip_by_point.get(pid),
                current_forecast_precip_by_point.get(pid),
            )
            for pid in forecast_point_ids
        },
        "missing_data": {
            "previous_missing": sorted(previous_missing),
            "current_missing": sorted(current_missing),
            "newly_missing": sorted(current_missing - previous_missing),
            "newly_available": sorted(previous_missing - current_missing),
        },
        "optional_evidence": {
            "previous_available": sorted(previous_optional),
            "current_available": sorted(current_optional),
            "added": sorted(current_optional - previous_optional),
            "removed": sorted(previous_optional - current_optional),
            "note": (
                "Availability changes only: optional evidence never modifies "
                "B/R/F/D/C/O7 numeric outputs (doc 04 §19)."
            ),
        },
    }
