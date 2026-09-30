"""
MountainGuardian G03B – deterministic Historical Trend query.

Read-only queries over the G03A append-only snapshot store (doc 04 §32/§33):
  * trend points come ONLY from real, valid, already-executed Risk Watch
    results — history is never fabricated and future values are never
    pre-filled;
  * invalid snapshots (is_invalid), failed scans and data-only snapshots
    without an official Current Risk Index never enter the valid trend;
  * BACKFILL snapshots remain explicitly labeled and are excluded by
    default (include_backfill=False) so they can never silently mix into a
    LIVE-only trend;
  * the snapshot store is never mutated here: no rewrite, no re-scoring, no
    payload history changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from riskwatch.engine.formulas import (
    DIRECTION_NO_HISTORY,
    VALID_RESULT_STATUSES,
    classify_band,
    classify_direction,
    round_display,
)
from riskwatch.snapshot_store import SCAN_MODE_BACKFILL

TREND_NO_HISTORY = "NO_HISTORY"
TREND_INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
TREND_SIMPLE_COMPARISON = "SIMPLE_COMPARISON"
TREND_AVAILABLE = "TREND_AVAILABLE"

TREND_POLICY = (
    "real valid snapshots only; no fabricated or pre-filled trend points; "
    "BACKFILL snapshots are explicitly labeled and excluded by default; "
    "invalid snapshots never enter the trend"
)


@dataclass(frozen=True)
class TrendEntry:
    snapshot_id: str
    created_at: str
    scan_mode: str
    status: str
    current_risk_index: float          # full precision, as stored
    current_risk_index_rounded: float
    risk_level: str                    # recomputed with the frozen bands
    risk_direction: str                # vs previous entry in the valid series

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "created_at": self.created_at,
            "scan_mode": self.scan_mode,
            "status": self.status,
            "current_risk_index": self.current_risk_index,
            "current_risk_index_rounded": self.current_risk_index_rounded,
            "risk_level": self.risk_level,
            "risk_direction": self.risk_direction,
        }


@dataclass(frozen=True)
class HistoricalTrend:
    region_id: str
    status: str
    include_backfill: bool
    entries: tuple                     # tuple[TrendEntry, ...] chronological
    policy: str = TREND_POLICY

    def to_dict(self) -> dict[str, Any]:
        return {
            "region_id": self.region_id,
            "status": self.status,
            "include_backfill": self.include_backfill,
            "entry_count": len(self.entries),
            "policy": self.policy,
            "entries": [e.to_dict() for e in self.entries],
        }


def _valid_risk_rows(store, region_id: str, include_backfill: bool) -> list[dict]:
    rows = []
    for row in store.list_snapshots(region_id):
        if int(row.get("is_invalid", 0) or 0) != 0:
            continue
        if str(row.get("status", "")) not in VALID_RESULT_STATUSES:
            continue
        if not include_backfill and str(row.get("scan_mode", "")) == SCAN_MODE_BACKFILL:
            continue
        payload = row.get("payload")
        if not isinstance(payload, dict):
            continue
        value = payload.get("current_risk_index", payload.get("C"))
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        rows.append(row)
    return rows


def query_historical_trend(
    store,
    region_id: str,
    include_backfill: bool = False,
    limit: Optional[int] = None,
) -> HistoricalTrend:
    """Deterministic trend query over real valid snapshots.

    1 valid snapshot -> INSUFFICIENT_HISTORY; 2 -> SIMPLE_COMPARISON;
    3+ -> TREND_AVAILABLE; none -> NO_HISTORY. Per-entry direction is
    computed against the previous entry of the same valid series with the
    frozen ±5 rule; the first entry is always NO_HISTORY.
    """
    rows = _valid_risk_rows(store, region_id, include_backfill)
    entries: list[TrendEntry] = []
    previous_c: Optional[float] = None
    for row in rows:
        payload = row["payload"]
        c = float(payload.get("current_risk_index", payload.get("C")))
        direction = (
            DIRECTION_NO_HISTORY if previous_c is None
            else classify_direction(c - previous_c)
        )
        entries.append(
            TrendEntry(
                snapshot_id=str(row.get("snapshot_id", "")),
                created_at=str(row.get("created_at", "")),
                scan_mode=str(row.get("scan_mode", "")),
                status=str(row.get("status", "")),
                current_risk_index=c,
                current_risk_index_rounded=round_display(c),
                risk_level=classify_band(c, "current_risk_index"),
                risk_direction=direction,
            )
        )
        previous_c = c

    count = len(entries)
    if count == 0:
        status = TREND_NO_HISTORY
    elif count == 1:
        status = TREND_INSUFFICIENT_HISTORY
    elif count == 2:
        status = TREND_SIMPLE_COMPARISON
    else:
        status = TREND_AVAILABLE

    if limit is not None and limit >= 0:
        entries = entries[-limit:] if limit else []

    return HistoricalTrend(
        region_id=region_id,
        status=status,
        include_backfill=include_backfill,
        entries=tuple(entries),
    )
