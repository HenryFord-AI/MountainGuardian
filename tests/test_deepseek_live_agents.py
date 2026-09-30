"""
MountainGuardian G02A – opt-in LIVE professional-agent smoke test (Layer 3).

Engineering Spec §27: real-API tests MUST be explicit/opt-in. This module
runs ONLY when BOTH:

    RUN_LIVE_TESTS=1
    DEEPSEEK_API_KEY present in the process environment
        (delivered via the authorized Bitwarden path:
         bws run --project-id <MG_PROJECT_ID> -- python -m pytest ...)

Ordinary `pytest` skips this module entirely – no key required, no cost.

Infrastructure smoke, NOT a scientific-truth evaluation: it proves the chain

    GlacierGeologyAgent → ModelProvider → DeepSeekProvider
        → deepseek-flash → validated structured result

with exactly ONE paid model call. Secrets are never printed; assertions
check presence/absence only.
"""

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.glacier_geology_agent import GlacierGeologyAgent
from orchestration.context_builder import (
    agent_evidence_view,
    build_analysis_context,
)
from providers import DeepSeekProvider
from schemas.agent_outputs import AgentStatus, RiskSignal

_LIVE_ENABLED = os.environ.get("RUN_LIVE_TESTS", "") == "1"
_KEY_PRESENT = bool(os.environ.get("DEEPSEEK_API_KEY", ""))

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        not (_LIVE_ENABLED and _KEY_PRESENT),
        reason="live DeepSeek agent tests disabled "
               "(requires RUN_LIVE_TESTS=1 and DEEPSEEK_API_KEY via "
               "authorized secret chain)"),
]


class TestProfessionalAgentLive:
    def test_glacier_geology_agent_through_real_deepseek(self):
        """ONE paid call through the full professional-agent chain."""
        context = build_analysis_context(run_id="g02a-live-smoke")
        provider = DeepSeekProvider()
        agent = GlacierGeologyAgent(provider=provider)

        result = agent.run(context)

        assert result.status == AgentStatus.COMPLETED, (
            f"live agent run failed: status={result.status.value} "
            f"error_category={result.error_category} "
            f"error_message={result.error_message}")
        assert result.is_model_output is True
        assert result.fallback_used is False, \
            "fallback must not be reported as real model output"
        assert result.provider == "deepseek"
        assert result.model_id == "deepseek-flash"
        assert result.run_id == "g02a-live-smoke"
        assert result.request_id
        assert result.latency_ms > 0
        assert result.token_usage.get("total_tokens", 0) > 0

        # structured scientific output
        assert result.risk_signal in {s.value for s in RiskSignal}
        assert 0.0 <= result.confidence <= 1.0
        assert result.key_findings

        # evidence discipline: only authorized IDs cited
        allowed = agent_evidence_view(
            context, agent.agent_name).allowed_evidence_ids()
        assert set(result.evidence_ids) <= allowed
        assert result.evidence_ids, "findings must reference evidence"

        # audit record serializes cleanly and contains no secret material
        audit = json.dumps(result.to_audit_dict(), default=str)
        assert os.environ["DEEPSEEK_API_KEY"] not in audit
        assert "Authorization" not in audit
        assert "Bearer" not in audit
