"""
MountainGuardian G03C – opt-in LIVE end-to-end Risk Watch scan (Layer 3).

Engineering Spec §27: real-API tests MUST be explicit/opt-in. This module
runs ONLY when BOTH:

    RUN_LIVE_TESTS=1
    DEEPSEEK_API_KEY present in the process environment
        (delivered via the authorized Bitwarden path:
        bws run --project-id <MG_PROJECT_ID> -- python -m pytest ...)

Ordinary `pytest` skips this module entirely — no key required, no cost.

ONE real end-to-end execution (gate G03C §18):

    real Open-Meteo forecast (2 point requests, 30-min raw cache)
  + cached G03A 1991-2020 climatology references (NEVER re-downloaded
    here — the module skips when they are absent)
  + real DeepSeek professional agents / synthesizer / critic (at most 5
    generation calls; Remote Sensing short-circuits SKIPPED before any
    provider call because v1.0 has no imagery pipeline)
  + real immutable snapshot persistence.

The live record required by the gate (DeepSeek call count, latency,
provider status, final Critic verdict) is printed with -s and asserted
below. Secrets are never printed.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from orchestration.risk_watch_orchestrator import run_risk_scan  # noqa: E402
from riskwatch.climatology import ClimatologyStore, runtime_dir  # noqa: E402
from riskwatch.region import load_region  # noqa: E402
from riskwatch.snapshot_store import SnapshotStore, default_db_path  # noqa: E402
from schemas.synthesis import CriticReviewResult  # noqa: E402

_LIVE_ENABLED = os.environ.get("RUN_LIVE_TESTS", "") == "1"
_KEY_PRESENT = bool(os.environ.get("DEEPSEEK_API_KEY", ""))

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        not (_LIVE_ENABLED and _KEY_PRESENT),
        reason="live G03C scan disabled (requires RUN_LIVE_TESTS=1 and "
               "DEEPSEEK_API_KEY via authorized secret chain)"),
]

MAX_EXPECTED_DEEPSEEK_CALLS = 5  # 2 agents + synthesis + critic (+0 RS)


def _climatology_ready() -> bool:
    region = load_region()
    store = ClimatologyStore(runtime_dir() / "climatology")
    return all(store.load(p.point_id) is not None
               for p in region.monitoring_points)


@pytest.mark.skipif(
    not _LIVE_ENABLED or not _climatology_ready(),
    reason="cached G03A climatology references not present in the runtime "
           "dir — materialize once via `python -m riskwatch.climatology` "
           "(the live test never re-downloads 30 years of archive data)")
class TestLiveRiskWatchScan:
    def test_full_real_scan_openmeteo_plus_deepseek(self):
        result = run_risk_scan("jilong_port")   # production defaults

        # ── deterministic layer produced an official result ──
        assert result.status in ("COMPLETED", "COMPLETED_WITH_LIMITATIONS")
        assert result.risk_index is not None
        assert 0.0 <= result.risk_index <= 100.0
        assert result.risk_level in {"LOW", "MODERATE", "ELEVATED", "HIGH"}
        det = result.deterministic_result
        assert det.B is not None and det.R is not None
        assert det.F is not None and det.D is not None
        assert det.O7 is not None

        # ── AI interpretation layer really ran on DeepSeek ──
        provider_audit = result.provenance["provider"]
        assert provider_audit["provider_name"] == "deepseek"
        calls = provider_audit["generation_calls"]
        assert 1 <= calls <= MAX_EXPECTED_DEEPSEEK_CALLS, provider_audit
        assert provider_audit["successful_calls"] >= 1

        # ── run_id chain and persistence ──
        assert result.run_id == det.run_id
        assert all(r.run_id == result.run_id
                   for r in result.agent_results.values())
        with SnapshotStore(default_db_path()) as store:
            data_row = store.get(result.data_snapshot_id)
            res_row = store.get(result.result_snapshot_id)
        assert data_row is not None and res_row is not None
        assert data_row["run_id"] == res_row["run_id"] == result.run_id
        assert res_row["status"] == result.status
        assert res_row["payload"]["current_risk_index"] == \
            pytest.approx(result.risk_index)

        # ── critic verdict is a frozen-taxonomy value; index attested ──
        assert result.critic_status in (
            {v.value for v in CriticReviewResult} | {"UNAVAILABLE"})
        if result.critic is not None:
            assert result.critic.risk_index_before == \
                result.critic.risk_index_after == \
                pytest.approx(result.risk_index)

        # ── no secret anywhere in the persisted audit trail ──
        secret = os.environ.get("DEEPSEEK_API_KEY", "")
        blob = json.dumps(res_row, ensure_ascii=False, default=str)
        assert secret and secret not in blob
        assert secret not in result.to_json()

        # ── gate §18 live record ──
        print("\n=== G03C LIVE VERIFICATION RECORD ===")
        print(f"run_id           : {result.run_id}")
        print(f"region           : {result.region_id}")
        print(f"status           : {result.status}")
        print(f"C / level        : {result.risk_index!r} "
              f"{result.risk_level}")
        print(f"O7 / level       : {result.outlook_7d_index!r} "
              f"{result.outlook_7d_level}")
        print(f"B / R / F / D    : {det.B!r} / {det.R!r} / {det.F!r} / "
              f"{det.D!r}")
        print(f"direction        : {det.risk_direction}")
        print(f"weather          : {result.data_quality['weather_status']} "
              f"retrieved {result.provenance['weather']['retrieval_time']}")
        print(f"point quality    : {result.data_quality['point_quality']}")
        print(f"deepseek calls   : {calls} "
              f"(successful {provider_audit['successful_calls']}, "
              f"total latency {provider_audit['total_latency_ms']} ms)")
        for c in provider_audit["calls"]:
            print(f"   call {c['request_id']}: success={c['success']} "
                  f"status={c['provider_status']} "
                  f"latency={c['latency_ms']}ms "
                  f"tokens={c['token_usage'].get('total_tokens', 0)}")
        print(f"agents           : "
              f"{result.ai_layer.get('agent_status_summary')}")
        print(f"synthesizer      : {result.synthesis_status} "
              f"(model_output="
              f"{result.synthesis.is_model_output if result.synthesis else None})")
        print(f"critic           : {result.critic_status}")
        print(f"snapshots        : data={result.data_snapshot_id} "
              f"result={result.result_snapshot_id}")
        print(f"trend            : {result.historical_trend.status} "
              f"({len(result.historical_trend.entries)} real entries)")
