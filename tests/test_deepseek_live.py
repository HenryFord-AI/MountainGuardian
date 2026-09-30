"""
MountainGuardian G01 – opt-in LIVE DeepSeek integration test (Layer 3 smoke).

Engineering Spec §27: real-API tests MUST be explicit/opt-in. This module
runs ONLY when BOTH:

    RUN_LIVE_TESTS=1
    DEEPSEEK_API_KEY present in the process environment
        (delivered via the authorized Bitwarden path:
         bws run --project-id <MG_PROJECT_ID> -- python -m pytest ...)

Ordinary `pytest` skips this module entirely – no key required, no cost.

The live prompt is deliberately tiny and harmless (provider-infrastructure
test, NOT a scientific-reasoning test). One paid call, no repeats.

Secrets are never printed: assertions check presence/absence only.
"""

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from providers import (
    DeepSeekProvider,
    ModelRequest,
    ProviderStatus,
)

_LIVE_ENABLED = os.environ.get("RUN_LIVE_TESTS", "") == "1"
_KEY_PRESENT = bool(os.environ.get("DEEPSEEK_API_KEY", ""))

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        not (_LIVE_ENABLED and _KEY_PRESENT),
        reason="live DeepSeek tests disabled "
               "(requires RUN_LIVE_TESTS=1 and DEEPSEEK_API_KEY via "
               "authorized secret chain)"),
]

PING_SCHEMA = {
    "type": "object",
    "required": ["ping", "ok"],
    "properties": {
        "ping": {"type": "string"},
        "ok": {"type": "boolean"},
    },
}


class TestDeepSeekLive:
    def test_live_health_check(self):
        provider = DeepSeekProvider()
        health = provider.health_check(force=True)
        assert health.status == ProviderStatus.CONNECTED, (
            f"health detail: {health.detail}")
        assert health.model_id == "deepseek-flash"

    def test_live_structured_generation(self):
        """One tiny real call proving: endpoint reachable, auth accepted,
        model id `deepseek-flash` accepted, structured response parses,
        schema validation passes, audit metadata + latency recorded,
        fallback NOT used, no secret exposed."""
        provider = DeepSeekProvider()
        request = ModelRequest(
            system_prompt="You are a connectivity test harness.",
            user_prompt=('Respond with JSON only: {"ping": "pong", '
                         '"ok": true}'),
            schema=PING_SCHEMA,
            max_tokens=64,
            temperature=0.0,
            run_id="g01-live-verification",
            fallback_data={"ping": "FALLBACK", "ok": False},
        )
        result = provider.generate_structured(request)

        assert result.success is True, (
            f"live call failed: {result.error_category} "
            f"{result.error_message}")
        assert result.fallback_used is False, \
            "fallback must not be reported as real model output"
        assert result.data == {"ping": "pong", "ok": True}
        assert result.model_id == "deepseek-flash"
        assert result.provider == "deepseek"
        assert result.latency_ms > 0
        assert result.request_id and result.run_id == "g01-live-verification"
        assert result.token_usage.get("total_tokens", 0) > 0
        assert result.status in (ProviderStatus.CONNECTED,
                                 ProviderStatus.DEGRADED)

        # Audit record serializes cleanly and contains no secret material
        audit = json.dumps(result.to_audit_dict(), default=str)
        assert os.environ["DEEPSEEK_API_KEY"] not in audit
        assert "Authorization" not in audit
        assert "Bearer" not in audit
