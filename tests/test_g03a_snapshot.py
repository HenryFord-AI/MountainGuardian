"""G03A – snapshot schema, append-only persistence, no silent overwrite."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from riskwatch.snapshot_store import (  # noqa: E402
    SCHEMA_VERSION,
    SnapshotExistsError,
    SnapshotStore,
    SnapshotStoreError,
    default_db_path,
)

PAYLOAD = {
    "region_id": "jilong_port",
    "monitoring_points": {
        "source_zone": {
            "quality": "FRESH",
            "recent": {"cumulative_precipitation_mm": 12.5},
            "missing": {"recent_missing_days": []},
            "provenance": {
                "provider": "Open-Meteo",
                "model_requested": "ecmwf_ifs",
                "retrieval_time": "2026-10-01T06:00:00+00:00",
                "requested_coordinate": {"latitude": 28.28, "longitude": 85.481},
                "returned_coordinate": {"latitude": 28.25, "longitude": 85.5},
            },
        }
    },
    "data_quality": {"source_zone": "FRESH"},
    "missing_sources": [],
}


@pytest.fixture()
def store(tmp_path):
    with SnapshotStore(tmp_path / "mountainguardian.db") as s:
        yield s


class TestSchema:
    def test_idempotent_initialization(self, tmp_path):
        path = tmp_path / "mg.db"
        SnapshotStore(path).close()
        SnapshotStore(path).close()  # second init must not fail or reset
        with SnapshotStore(path) as s:
            assert s.count() == 0

    def test_default_path_honors_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MOUNTAINGUARDIAN_DB_PATH", str(tmp_path / "custom.db"))
        assert default_db_path() == tmp_path / "custom.db"
        monkeypatch.delenv("MOUNTAINGUARDIAN_DB_PATH")
        assert default_db_path().name == "mountainguardian.db"
        assert "data" in default_db_path().parts and "runtime" in default_db_path().parts


class TestInsertAndRead:
    def test_insert_stores_run_id_provenance_quality_missing(self, store):
        sid = store.insert_snapshot(
            run_id="run-0001",
            region_id="jilong_port",
            status="OK",
            payload=PAYLOAD,
            created_at="2026-10-01T06:00:00+00:00",
        )
        row = store.get(sid)
        assert row["run_id"] == "run-0001"
        assert row["region_id"] == "jilong_port"
        assert row["status"] == "OK"
        assert row["scan_mode"] == "LIVE"
        assert row["schema_version"] == SCHEMA_VERSION
        assert row["payload"]["monitoring_points"]["source_zone"]["provenance"][
            "provider"
        ] == "Open-Meteo"
        assert row["payload"]["data_quality"] == {"source_zone": "FRESH"}
        assert row["payload"]["missing_sources"] == []

    def test_backfill_must_be_explicit(self, store):
        sid = store.insert_snapshot(
            run_id="run-bf", region_id="jilong_port", status="OK",
            payload=PAYLOAD, scan_mode="BACKFILL",
        )
        assert store.get(sid)["scan_mode"] == "BACKFILL"
        with pytest.raises(SnapshotStoreError):
            store.insert_snapshot(
                run_id="run-x", region_id="jilong_port", status="OK",
                payload=PAYLOAD, scan_mode="PRETEND-LIVE",
            )

    def test_run_id_required(self, store):
        with pytest.raises(SnapshotStoreError):
            store.insert_snapshot(
                run_id="", region_id="jilong_port", status="OK", payload=PAYLOAD
            )


class TestImmutability:
    def test_duplicate_identity_cannot_silently_overwrite(self, store):
        sid = store.insert_snapshot(
            run_id="run-0001", region_id="jilong_port", status="OK",
            payload=PAYLOAD, snapshot_id="fixed-id",
        )
        with pytest.raises(SnapshotExistsError):
            store.insert_snapshot(
                run_id="run-0002", region_id="jilong_port", status="OK",
                payload={"tampered": True}, snapshot_id="fixed-id",
            )
        row = store.get(sid)
        assert row["payload"] == PAYLOAD  # prior content unchanged
        assert row["run_id"] == "run-0001"
        assert store.count() == 1

    def test_new_scan_appends_new_snapshot(self, store):
        ids = [
            store.insert_snapshot(
                run_id=f"run-{i}", region_id="jilong_port", status="OK", payload=PAYLOAD
            )
            for i in range(3)
        ]
        assert len(set(ids)) == 3
        assert store.count() == 3
        listed = store.list_snapshots("jilong_port")
        assert [r["run_id"] for r in listed] == ["run-0", "run-1", "run-2"]

    def test_mark_invalid_does_not_mutate_payload(self, store):
        sid = store.insert_snapshot(
            run_id="run-1", region_id="jilong_port", status="PARTIAL", payload=PAYLOAD
        )
        store.mark_invalid(sid, "collector bug discovered")
        row = store.get(sid)
        assert row["is_invalid"] == 1
        assert row["correction_note"] == "collector bug discovered"
        assert row["payload"] == PAYLOAD


class TestRuntimeArtifactsIgnored:
    def test_gitignore_covers_runtime_db_and_cache(self):
        gitignore = (Path(__file__).parent.parent / ".gitignore").read_text(encoding="utf-8")
        assert "data/runtime/" in gitignore
        assert "*.db-wal" in gitignore

    def test_region_config_is_not_gitignored(self):
        import subprocess

        root = Path(__file__).parent.parent
        proc = subprocess.run(
            ["git", "check-ignore", "-q", "data/regions/jilong_port/region.json"],
            cwd=root,
        )
        assert proc.returncode == 1  # not ignored -> deployable/tracked
