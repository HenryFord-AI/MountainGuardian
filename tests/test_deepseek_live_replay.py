"""
MountainGuardian G02B – opt-in LIVE Historical Replay end-to-end smoke.

Engineering Spec §27: real-API tests MUST be explicit/opt-in. This module
runs ONLY when BOTH:

    RUN_LIVE_TESTS=1
    DEEPSEEK_API_KEY present in the process environment
        (delivered via the authorized Bitwarden path:
         bws run --project-id <MG_PROJECT_ID> -- python -m pytest ...)

Ordinary `pytest` skips this module entirely – no key required, no cost.

Proves the full bounded chain with the REAL model:

    pre-event AnalysisContext
    → 3 professional agents (GG / WH text, RS multimodal-or-skip)
    → deterministic Historical Risk Engine (91/100, no LLM)
    → Risk Synthesizer (explains, cannot alter the index)
    → Critic (programmatic checks + bounded model review)
    → Stage-A freeze (immutable, digest-sealed)
    → Stage-B post-event validation (deterministic, zero provider calls)

Paid-call accounting: a counting requests.Session records EVERY
/chat/completions HTTP attempt; the exact number is printed in the test
output and must stay within the bounded budget. Secrets are never printed;
assertions check presence/absence only.
"""

import json
import os
import sys
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

from orchestration.replay_orchestrator import run_historical_replay
from providers import DeepSeekProvider
from schemas.agent_outputs import AgentStatus
from schemas.synthesis import CriticReviewResult

_LIVE_ENABLED = os.environ.get("RUN_LIVE_TESTS", "") == "1"
_KEY_PRESENT = bool(os.environ.get("DEEPSEEK_API_KEY", ""))

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        not (_LIVE_ENABLED and _KEY_PRESENT),
        reason="live DeepSeek replay tests disabled "
               "(requires RUN_LIVE_TESTS=1 and DEEPSEEK_API_KEY via "
               "authorized secret chain)"),
]

#: bounded budget: GG + WH + RS + Synthesizer + Critic = 5 nominal calls;
#: each may consume at most (1 + max_retries) * (1 + max_schema_repairs)
#: HTTP attempts, but a healthy run must stay far below that.
_MAX_CHAT_ATTEMPTS = 10


class CountingSession(requests.Session):
    """Counts every chat-completions HTTP attempt (paid generation calls)."""

    def __init__(self):
        super().__init__()
        self.chat_attempts = 0
        self.attempt_log = []

    def post(self, url, *args, **kwargs):
        if "/chat/completions" in str(url):
            self.chat_attempts += 1
            self.attempt_log.append(str(url))
        return super().post(url, *args, **kwargs)


class TestLiveHistoricalReplay:
    def test_full_replay_with_real_deepseek(self):
        session = CountingSession()
        provider = DeepSeekProvider(session=session)
        replay = run_historical_replay(provider=provider,
                                       run_id="g02b-live-replay")

        # ── deterministic score integrity across the whole DAG ──
        assert replay.stage_a.risk_index == 91.0
        assert replay.stage_a.risk_level == "HIGH"
        assert replay.stage_b.risk_index_before == 91.0
        assert replay.stage_b.risk_index_after == 91.0
        assert replay.stage_b.stage_a_unchanged is True
        assert replay.stage_a.verify_integrity()

        payload = replay.stage_a.to_dict()
        statuses = payload["agent_status_summary"]
        syn = payload["synthesis"]["output"]
        critic = payload["critic"]["verdict"]

        # ── bounded paid-call accounting (EXACT count reported FIRST,
        #    even when assertions below fail) ──
        attempts = session.chat_attempts
        print(f"\n[G02B-LIVE] paid /chat/completions HTTP attempts: "
              f"{attempts} (budget <= {_MAX_CHAT_ATTEMPTS})")
        print(f"[G02B-LIVE] agent statuses: {statuses}")
        print(f"[G02B-LIVE] synthesis: model={syn['is_model_output']} "
              f"fallback={syn['fallback_used']}")
        print(f"[G02B-LIVE] critic verdict: {critic['review_result']} "
              f"(model_review={critic['is_model_output']}, "
              f"fallback={critic['fallback_used']})")
        print(f"[G02B-LIVE] synthesis summary: {syn['summary'][:300]}")
        print(f"[G02B-LIVE] coverage={syn['evidence_coverage']} "
              f"agreement={syn['agent_agreement']}")

        # ── professional agents ──
        assert statuses["glacier_geology"] in (
            AgentStatus.COMPLETED.value, AgentStatus.DEGRADED.value), statuses
        assert statuses["weather_hydrology"] in (
            AgentStatus.COMPLETED.value, AgentStatus.DEGRADED.value), statuses
        # RS may legitimately COMPLETE, DEGRADE (no multimodal support), or
        # SKIP (no usable authorized imagery) — but must be honestly labeled
        assert statuses["remote_sensing"] in (
            AgentStatus.COMPLETED.value, AgentStatus.DEGRADED.value,
            AgentStatus.SKIPPED.value), statuses

        # ── synthesizer ──
        assert syn["deterministic_risk_index"] == 91.0
        assert syn["is_model_output"] is True, \
            f"live synthesis fell back: {payload['synthesis']['audit']}"
        assert syn["fallback_used"] is False
        assert syn["top_drivers"]
        assert syn["summary"] and syn["risk_explanation"]
        assert 0.0 <= syn["explanation_confidence"] <= 1.0

        # ── critic ──
        assert critic["review_result"] in {
            r.value for r in CriticReviewResult}
        assert critic["risk_index_before"] == 91.0
        assert critic["risk_index_after"] == 91.0
        assert critic["review_result"] != CriticReviewResult.BLOCKED.value, \
            json.dumps(critic["issues"], ensure_ascii=False)
        # the CRITICAL programmatic dimensions must be clean on the
        # canonical live path (NEEDS_REVISION from stricter model review
        # is legitimate; structural integrity violations are not)
        for dimension in ("POST_EVENT_LEAKAGE", "SCORE_INTEGRITY",
                          "EVIDENCE_ID_INTEGRITY", "FALLBACK_LABELING"):
            assert dimension not in critic["programmatic_check_status"], \
                f"{dimension} flagged on live run: " + json.dumps(
                    critic["issues"], ensure_ascii=False)

        # ── Stage B validation ──
        assert replay.stage_b.directional_findings
        assert replay.stage_b.stage_a_could_not_know

        assert attempts <= _MAX_CHAT_ATTEMPTS, \
            f"paid call budget exceeded: {attempts} attempts"

        # ── secret hygiene ──
        audit_blob = json.dumps(payload, default=str, ensure_ascii=False)
        key = os.environ.get("DEEPSEEK_API_KEY", "")
        assert key and key not in audit_blob
        assert "Authorization" not in audit_blob
        assert "Bearer" not in audit_blob
