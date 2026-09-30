"""
MountainGuardian G03A – Risk Watch snapshot persistence (SQLite).

Frozen rules (doc 06 §36/§38/§39, doc 04 §30/§31):
  * local default path data/runtime/mountainguardian.db, overridable via
    MOUNTAINGUARDIAN_DB_PATH (Azure: /home/data/mountainguardian.db);
  * idempotent schema initialization (CREATE TABLE IF NOT EXISTS);
  * NEW SCAN -> NEW SNAPSHOT: inserts only, never UPDATE/DELETE; a duplicate
    snapshot identity raises SnapshotExistsError instead of overwriting;
  * every snapshot carries run_id, region_id, timestamps, scan mode, status,
    schema/config versions and a provenance-bearing JSON payload (weather
    normalized data, quality, missing data, source metadata);
  * future Gates extend by adding nullable columns / payload keys, never by
    destructive migration. A correction model (is_invalid + correction_note)
    exists as nullable metadata only.
"""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "risk_watch_snapshot_v1"

SCAN_MODE_LIVE = "LIVE"
SCAN_MODE_BACKFILL = "BACKFILL"
ALLOWED_SCAN_MODES = (SCAN_MODE_LIVE, SCAN_MODE_BACKFILL)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS risk_watch_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id     TEXT NOT NULL UNIQUE,
    run_id          TEXT NOT NULL,
    region_id       TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    scan_mode       TEXT NOT NULL DEFAULT 'LIVE',
    status          TEXT NOT NULL,
    schema_version  TEXT NOT NULL,
    config_version  TEXT,
    is_invalid      INTEGER NOT NULL DEFAULT 0,
    correction_note TEXT,
    payload_json    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_risk_watch_snapshots_region_time
    ON risk_watch_snapshots (region_id, created_at);

CREATE INDEX IF NOT EXISTS idx_risk_watch_snapshots_run
    ON risk_watch_snapshots (run_id);
"""


class SnapshotStoreError(Exception):
    """Base snapshot persistence error."""


class SnapshotExistsError(SnapshotStoreError):
    """A snapshot with this identity already exists: overwrite refused."""


def default_db_path() -> Path:
    env = os.environ.get("MOUNTAINGUARDIAN_DB_PATH", "")
    if env:
        return Path(env)
    return (
        Path(__file__).resolve().parent.parent
        / "data"
        / "runtime"
        / "mountainguardian.db"
    )


def new_snapshot_id() -> str:
    return f"rws-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}-{uuid.uuid4().hex[:8]}"


class SnapshotStore:
    def __init__(self, db_path: Path | str | None = None):
        self.db_path = Path(db_path) if db_path is not None else default_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self.init_schema()

    # -- schema ------------------------------------------------------------
    def init_schema(self) -> None:
        self._conn.executescript(SCHEMA_SQL)
        self._conn.commit()

    # -- writes ------------------------------------------------------------
    def insert_snapshot(
        self,
        run_id: str,
        region_id: str,
        status: str,
        payload: dict[str, Any],
        created_at: str | None = None,
        scan_mode: str = SCAN_MODE_LIVE,
        config_version: str | None = None,
        snapshot_id: str | None = None,
    ) -> str:
        """Append a new immutable snapshot. Never overwrites an existing one."""
        if scan_mode not in ALLOWED_SCAN_MODES:
            raise SnapshotStoreError(
                f"scan_mode must be one of {ALLOWED_SCAN_MODES} "
                "(BACKFILL must be explicit, never disguised as LIVE)"
            )
        if not run_id:
            raise SnapshotStoreError("run_id is required")
        sid = snapshot_id or new_snapshot_id()
        created = created_at or datetime.now(timezone.utc).isoformat()
        try:
            self._conn.execute(
                """
                INSERT INTO risk_watch_snapshots (
                    snapshot_id, run_id, region_id, created_at, scan_mode,
                    status, schema_version, config_version, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sid,
                    run_id,
                    region_id,
                    created,
                    scan_mode,
                    status,
                    SCHEMA_VERSION,
                    config_version,
                    json.dumps(payload, ensure_ascii=False, sort_keys=True),
                ),
            )
            self._conn.commit()
        except sqlite3.IntegrityError as exc:
            self._conn.rollback()
            raise SnapshotExistsError(
                f"snapshot {sid} already exists; silent overwrite is forbidden"
            ) from exc
        return sid

    def mark_invalid(self, snapshot_id: str, note: str) -> None:
        """Frozen correction model: flag + note, never content mutation."""
        self._conn.execute(
            "UPDATE risk_watch_snapshots SET is_invalid = 1, correction_note = ? "
            "WHERE snapshot_id = ?",
            (note, snapshot_id),
        )
        self._conn.commit()

    # -- reads -------------------------------------------------------------
    def get(self, snapshot_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM risk_watch_snapshots WHERE snapshot_id = ?",
            (snapshot_id,),
        ).fetchone()
        return self._row_to_dict(row) if row else None

    def list_snapshots(self, region_id: str | None = None) -> list[dict[str, Any]]:
        if region_id is None:
            rows = self._conn.execute(
                "SELECT * FROM risk_watch_snapshots ORDER BY id"
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM risk_watch_snapshots WHERE region_id = ? ORDER BY id",
                (region_id,),
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def count(self) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) AS n FROM risk_watch_snapshots"
        ).fetchone()
        return int(row["n"])

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        data["payload"] = json.loads(data.pop("payload_json"))
        return data

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "SnapshotStore":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()
