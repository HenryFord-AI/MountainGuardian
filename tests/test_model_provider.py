"""
MountainGuardian G01 – DeepSeekProvider unit tests (mock only).

Ordinary `pytest` MUST NOT require DEEPSEEK_API_KEY and MUST NOT perform any
real network call (Engineering Spec §26–27). Every test here runs against a
fake HTTP session, and an autouse fixture blocks socket access module-wide.

Covers G01 required test areas 1–20 (see Gate instruction §8).
"""

import json
import socket
import sys
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

from providers import (
    DeepSeekProvider,
    ModelProvider,
    ModelRequest,
    ModelResult,
    ProviderErrorCategory,
    ProviderHealth,
    ProviderStatus,
    validate_json_schema,
)

FAKE_KEY = "sk-UNITTEST-FAKE-KEY-DO-NOT-LEAK-9f3a7c"


# ─── Network lockdown: no test in this module may touch the network ───────────
@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def _guard(*args, **kwargs):
        raise AssertionError("real network access attempted during unit tests")

    monkeypatch.setattr(socket, "socket", _guard)
    monkeypatch.setattr(socket, "create_connection", _guard)
    # Ordinary pytest must not depend on a real key (Gate §7)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)
    monkeypatch.delenv("DEEPSEEK_BASE_URL", raising=False)
    # Keep bounded-retry sleeps instant
    monkeypatch.setattr("providers.deepseek_provider.time.sleep",
                        lambda *_: None)


# ─── Fake HTTP session ────────────────────────────────────────────────────────
class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=None):
        self.status_code = status_code
        self._payload = payload
        self.text = text if text is not None else json.dumps(payload or {})

    def json(self):
        if self._payload is None:
            raise ValueError("no json payload")
        return self._payload


def chat_payload(content: str, usage=None, response_id="chatcmpl-test-1"):
    return {
        "id": response_id,
        "choices": [{"message": {"role": "assistant", "content": content}}],
        "usage": usage or {"prompt_tokens": 11, "completion_tokens": 7,
                           "total_tokens": 18},
    }


class FakeSession:
    """Programmable stand-in for requests.Session."""

    def __init__(self, script):
        # script: list of FakeResponse | Exception | callable(url, kwargs)
        self.script = list(script)
        self.calls = []

    def _next(self, method, url, kwargs):
        self.calls.append({"method": method, "url": url, **kwargs})
        if not self.script:
            raise AssertionError("FakeSession ran out of scripted responses")
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        if callable(item):
            return item(url, kwargs)
        return item

    def post(self, url, **kwargs):
        return self._next("post", url, kwargs)

    def get(self, url, **kwargs):
        return self._next("get", url, kwargs)


def make_provider(script, monkeypatch=None, **kwargs):
    if monkeypatch is not None:
        monkeypatch.setenv("DEEPSEEK_API_KEY", FAKE_KEY)
    return DeepSeekProvider(session=FakeSession(script), **kwargs)


SIMPLE_SCHEMA = {
    "type": "object",
    "required": ["answer", "confidence"],
    "properties": {
        "answer": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
}
VALID_JSON = json.dumps({"answer": "pong", "confidence": 0.9})


# ══════════════════════════════════════════════════════════════════════════════
# 1 & 2. Provider construction / config / default model ID
# ══════════════════════════════════════════════════════════════════════════════
class TestConstruction:
    def test_defaults(self):
        p = DeepSeekProvider()
        assert p.model_id == "deepseek-flash"          # area 2
        assert p.base_url == "https://api.deepseek.com"
        assert p.max_retries == 2
        assert p.max_schema_repairs == 1
        assert p.timeout > 0
        assert isinstance(p, ModelProvider)

    def test_env_overrides(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_MODEL", "custom-model")
        monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://example.invalid/v1/")
        p = DeepSeekProvider()
        assert p.model_id == "custom-model"
        assert p.base_url == "https://example.invalid/v1"  # trailing slash trimmed

    def test_key_read_from_environ_only_at_call_time(self, monkeypatch):
        p = DeepSeekProvider(session=FakeSession([]))
        monkeypatch.setenv("DEEPSEEK_API_KEY", FAKE_KEY)
        assert p._api_key() == FAKE_KEY
        monkeypatch.delenv("DEEPSEEK_API_KEY")
        assert p._api_key() == ""
        # the object itself never stores the secret
        assert FAKE_KEY not in repr(p)
        assert FAKE_KEY not in json.dumps(p.__dict__, default=str)

    def test_capabilities_declared(self):
        caps = DeepSeekProvider.capabilities
        assert caps["structured_output"] is True
        assert caps["multimodal"] is True                # area 12


# ══════════════════════════════════════════════════════════════════════════════
# 3, 4, 5. Valid structured response / JSON parsing / schema validation
# ══════════════════════════════════════════════════════════════════════════════
class TestStructuredGeneration:
    def test_valid_json_response(self, monkeypatch):                       # 3
        p = make_provider([FakeResponse(payload=chat_payload(VALID_JSON))],
                          monkeypatch)
        res = p.generate_structured(ModelRequest(
            system_prompt="You are a test.", user_prompt="ping",
            schema=SIMPLE_SCHEMA, run_id="run-1"))
        assert res.success is True
        assert res.data == {"answer": "pong", "confidence": 0.9}
        assert res.status == ProviderStatus.CONNECTED
        assert res.fallback_used is False
        assert res.error_category is None
        assert res.retry_count == 0 and res.repair_count == 0

    def test_request_payload_shape(self, monkeypatch):
        session = FakeSession([FakeResponse(payload=chat_payload(VALID_JSON))])
        p = DeepSeekProvider(session=session)
        monkeypatch.setenv("DEEPSEEK_API_KEY", FAKE_KEY)
        p.generate_structured(ModelRequest(
            system_prompt="sys", user_prompt="usr", schema=SIMPLE_SCHEMA,
            temperature=0.1, max_tokens=256))
        call = session.calls[0]
        assert call["url"] == "https://api.deepseek.com/chat/completions"
        body = call["json"]
        assert body["model"] == "deepseek-flash"
        assert body["response_format"] == {"type": "json_object"}
        assert body["temperature"] == 0.1 and body["max_tokens"] == 256
        assert call["timeout"] == p.timeout
        assert "json" in body["messages"][0]["content"].lower()

    def test_markdown_fenced_json_is_parsed(self, monkeypatch):            # 4
        fenced = f"```json\n{VALID_JSON}\n```"
        p = make_provider([FakeResponse(payload=chat_payload(fenced))],
                          monkeypatch)
        res = p.generate_structured(ModelRequest(
            user_prompt="ping", schema=SIMPLE_SCHEMA))
        assert res.success is True
        assert res.data["answer"] == "pong"

    def test_json_with_surrounding_prose_is_parsed(self, monkeypatch):     # 4
        noisy = f"Here is the result:\n{VALID_JSON}\nHope that helps."
        p = make_provider([FakeResponse(payload=chat_payload(noisy))],
                          monkeypatch)
        res = p.generate_structured(ModelRequest(user_prompt="ping",
                                                 schema=SIMPLE_SCHEMA))
        assert res.success is True

    def test_schema_validation_passes_and_fails(self):                     # 5
        assert validate_json_schema({"answer": "x", "confidence": 0.5},
                                    SIMPLE_SCHEMA) == []
        errs = validate_json_schema({"answer": "x"}, SIMPLE_SCHEMA)
        assert any("confidence" in e for e in errs)
        errs = validate_json_schema({"answer": "x", "confidence": 5},
                                    SIMPLE_SCHEMA)
        assert any("maximum" in e for e in errs)
        errs = validate_json_schema({"answer": 1, "confidence": 0.5},
                                    SIMPLE_SCHEMA)
        assert any("type" in e for e in errs)

    def test_scientific_output_validator_hook(self, monkeypatch):          # 5
        def hook(data):
            return ["risk_index out of scientific range"] \
                if data.get("confidence", 0) > 0.95 else []

        good = json.dumps({"answer": "ok", "confidence": 0.9})
        p = make_provider([FakeResponse(payload=chat_payload(good))],
                          monkeypatch)
        res = p.generate_structured(ModelRequest(
            user_prompt="ping", schema=SIMPLE_SCHEMA, output_validator=hook))
        assert res.success is True

        bad = json.dumps({"answer": "ok", "confidence": 0.99})
        p = make_provider(
            [FakeResponse(payload=chat_payload(bad)),
             FakeResponse(payload=chat_payload(bad))], monkeypatch)
        res = p.generate_structured(ModelRequest(
            user_prompt="ping", schema=SIMPLE_SCHEMA, output_validator=hook,
            fallback_data={"answer": "fallback", "confidence": 0.0}))
        assert res.success is False
        assert res.error_category == ProviderErrorCategory.SCHEMA_ERROR
        assert "scientific range" in res.error_message
        assert res.repair_count == 1
        assert res.fallback_used is True


# ══════════════════════════════════════════════════════════════════════════════
# 6, 7, 8. Invalid JSON / one bounded repair / repair failure → fallback
# ══════════════════════════════════════════════════════════════════════════════
class TestRepairPolicy:
    def test_invalid_json_then_repair_succeeds(self, monkeypatch):         # 6+7
        p = make_provider(
            [FakeResponse(payload=chat_payload("not json at all")),
             FakeResponse(payload=chat_payload(VALID_JSON))], monkeypatch)
        res = p.generate_structured(ModelRequest(
            user_prompt="ping", schema=SIMPLE_SCHEMA))
        assert res.success is True
        assert res.repair_count == 1                    # exactly one repair
        assert res.status == ProviderStatus.DEGRADED    # success but impaired

    def test_repair_request_contains_errors_and_original(self, monkeypatch):
        session = FakeSession(
            [FakeResponse(payload=chat_payload('{"answer": 42}')),
             FakeResponse(payload=chat_payload(VALID_JSON))])
        p = DeepSeekProvider(session=session)
        monkeypatch.setenv("DEEPSEEK_API_KEY", FAKE_KEY)
        res = p.generate_structured(ModelRequest(
            user_prompt="ping", schema=SIMPLE_SCHEMA))
        assert res.success is True
        repair_body = session.calls[1]["json"]
        msgs = repair_body["messages"]
        assert msgs[-2]["role"] == "assistant"
        assert msgs[-1]["role"] == "user"
        assert "validation" in msgs[-1]["content"].lower()

    def test_repair_failure_falls_back(self, monkeypatch):                 # 8
        p = make_provider(
            [FakeResponse(payload=chat_payload("garbage one")),
             FakeResponse(payload=chat_payload("garbage two"))],
            monkeypatch)
        fallback = {"answer": "deterministic", "confidence": 0.0}
        res = p.generate_structured(ModelRequest(
            user_prompt="ping", schema=SIMPLE_SCHEMA, fallback_data=fallback))
        assert res.success is False
        assert res.repair_count == 1                    # never more than one
        assert res.fallback_used is True
        assert res.data == fallback
        assert res.status == ProviderStatus.FALLBACK_ACTIVE
        assert res.error_category == ProviderErrorCategory.INVALID_RESPONSE

    def test_schema_failure_after_repair_falls_back(self, monkeypatch):    # 8
        bad = json.dumps({"answer": "x"})              # missing confidence
        p = make_provider(
            [FakeResponse(payload=chat_payload(bad)),
             FakeResponse(payload=chat_payload(bad))], monkeypatch)
        res = p.generate_structured(ModelRequest(
            user_prompt="ping", schema=SIMPLE_SCHEMA,
            fallback_data={"answer": "fb", "confidence": 0.0}))
        assert res.success is False
        assert res.repair_count == 1
        assert res.error_category == ProviderErrorCategory.SCHEMA_ERROR
        assert res.fallback_used is True

    def test_attempt_budget_is_hard_capped(self, monkeypatch):             # 15
        # Always-invalid output: total attempts must equal
        # (1 + max_retries) * (1 + max_schema_repairs) at most.
        script = [FakeResponse(payload=chat_payload("junk"))] * 10
        session = FakeSession(script)
        p = DeepSeekProvider(session=session)
        monkeypatch.setenv("DEEPSEEK_API_KEY", FAKE_KEY)
        res = p.generate_structured(ModelRequest(
            user_prompt="ping", schema=SIMPLE_SCHEMA,
            fallback_data={"answer": "fb", "confidence": 0.0}))
        assert res.success is False
        assert len(session.calls) <= (1 + p.max_retries) * (1 + p.max_schema_repairs)
        assert res.repair_count <= 1


# ══════════════════════════════════════════════════════════════════════════════
# 9–14. Error classification
# ══════════════════════════════════════════════════════════════════════════════
class TestErrorClassification:
    def test_auth_error_401(self, monkeypatch):                            # 9
        p = make_provider(
            [FakeResponse(status_code=401,
                          payload={"error": {"message": "invalid api key"}})],
            monkeypatch)
        res = p.generate_structured(ModelRequest(user_prompt="ping",
                                                 schema=SIMPLE_SCHEMA))
        assert res.success is False
        assert res.error_category == ProviderErrorCategory.AUTH_ERROR
        assert res.retry_count == 0                # auth errors never retried
        assert res.status == ProviderStatus.OFFLINE
        assert res.http_status == 401

    def test_missing_key_degrades_safely(self, monkeypatch):               # 9/12-runtime
        p = DeepSeekProvider(session=FakeSession([]))   # no key in env
        res = p.generate_structured(ModelRequest(
            user_prompt="ping", schema=SIMPLE_SCHEMA,
            fallback_data={"answer": "fb", "confidence": 0.0}))
        assert res.success is False
        assert res.fallback_used is True
        assert res.error_category == ProviderErrorCategory.AUTH_ERROR
        assert "DEEPSEEK_API_KEY" in res.error_message
        assert p.health_check().status == ProviderStatus.OFFLINE

    def test_timeout(self, monkeypatch):                                   # 10
        p = make_provider(
            [requests.exceptions.Timeout("read timed out"),
             requests.exceptions.Timeout("read timed out"),
             requests.exceptions.Timeout("read timed out")], monkeypatch)
        res = p.generate_structured(ModelRequest(
            user_prompt="ping", schema=SIMPLE_SCHEMA,
            fallback_data={"answer": "fb", "confidence": 0.0}))
        assert res.success is False
        assert res.error_category == ProviderErrorCategory.TIMEOUT
        assert res.retry_count == 2                # bounded retries happened
        assert res.status == ProviderStatus.FALLBACK_ACTIVE

    def test_rate_limit_429(self, monkeypatch):                            # 11
        p = make_provider(
            [FakeResponse(status_code=429,
                          payload={"error": {"message": "too many requests"}})] * 3,
            monkeypatch)
        res = p.generate_structured(ModelRequest(user_prompt="ping",
                                                 schema=SIMPLE_SCHEMA))
        assert res.error_category == ProviderErrorCategory.RATE_LIMIT
        assert res.retry_count == 2
        assert res.http_status == 429

    def test_service_unavailable_5xx(self, monkeypatch):                   # 12
        p = make_provider(
            [FakeResponse(status_code=503,
                          payload={"error": {"message": "overloaded"}})] * 3,
            monkeypatch)
        res = p.generate_structured(ModelRequest(user_prompt="ping",
                                                 schema=SIMPLE_SCHEMA))
        assert res.error_category == ProviderErrorCategory.SERVICE_UNAVAILABLE
        assert res.retry_count == 2

    def test_connection_error_is_service_unavailable(self, monkeypatch):
        p = make_provider(
            [requests.exceptions.ConnectionError("dns failure")] * 3,
            monkeypatch)
        res = p.generate_structured(ModelRequest(user_prompt="ping",
                                                 schema=SIMPLE_SCHEMA))
        assert res.error_category == ProviderErrorCategory.SERVICE_UNAVAILABLE

    def test_invalid_provider_response(self, monkeypatch):                 # 13
        # 200 but body has no choices
        p = make_provider([FakeResponse(payload={"id": "x"})] * 3,
                          monkeypatch)
        res = p.generate_structured(ModelRequest(user_prompt="ping",
                                                 schema=SIMPLE_SCHEMA))
        assert res.success is False
        assert res.error_category == ProviderErrorCategory.INVALID_RESPONSE

    def test_empty_content_is_invalid_response(self, monkeypatch):         # 13
        p = make_provider(
            [FakeResponse(payload=chat_payload("   "))] * 3, monkeypatch)
        res = p.generate_structured(ModelRequest(user_prompt="ping",
                                                 schema=SIMPLE_SCHEMA))
        assert res.error_category == ProviderErrorCategory.INVALID_RESPONSE

    def test_non_json_http_body(self, monkeypatch):                        # 13
        p = make_provider(
            [FakeResponse(status_code=200, payload=None,
                          text="<html>gateway</html>")] * 3, monkeypatch)
        res = p.generate_structured(ModelRequest(user_prompt="ping",
                                                 schema=SIMPLE_SCHEMA))
        assert res.error_category == ProviderErrorCategory.INVALID_RESPONSE

    def test_unknown_provider_error(self, monkeypatch):                    # 14
        p = make_provider(
            [requests.exceptions.RequestException("odd failure")],
            monkeypatch)
        res = p.generate_structured(ModelRequest(user_prompt="ping",
                                                 schema=SIMPLE_SCHEMA))
        assert res.success is False
        assert res.error_category == ProviderErrorCategory.UNKNOWN_PROVIDER_ERROR
        assert res.retry_count == 0                # not retryable

    def test_http_400_is_invalid_response_not_retried(self, monkeypatch):
        p = make_provider(
            [FakeResponse(status_code=400,
                          payload={"error": {"message": "bad request"}})],
            monkeypatch)
        res = p.generate_structured(ModelRequest(user_prompt="ping",
                                                 schema=SIMPLE_SCHEMA))
        assert res.error_category == ProviderErrorCategory.INVALID_RESPONSE
        assert res.retry_count == 0


# ══════════════════════════════════════════════════════════════════════════════
# 15. Bounded retry count
# ══════════════════════════════════════════════════════════════════════════════
class TestBoundedRetry:
    def test_retry_then_success(self, monkeypatch):
        session = FakeSession(
            [requests.exceptions.Timeout("t1"),
             FakeResponse(payload=chat_payload(VALID_JSON))])
        p = DeepSeekProvider(session=session)
        monkeypatch.setenv("DEEPSEEK_API_KEY", FAKE_KEY)
        res = p.generate_structured(ModelRequest(user_prompt="ping",
                                                 schema=SIMPLE_SCHEMA))
        assert res.success is True
        assert res.retry_count == 1
        assert res.status == ProviderStatus.DEGRADED
        assert len(session.calls) == 2

    def test_max_retries_respected(self, monkeypatch):
        session = FakeSession([FakeResponse(status_code=500, payload={})] * 9)
        p = DeepSeekProvider(session=session, max_retries=1)
        monkeypatch.setenv("DEEPSEEK_API_KEY", FAKE_KEY)
        res = p.generate_structured(ModelRequest(user_prompt="ping",
                                                 schema=SIMPLE_SCHEMA))
        assert res.success is False
        assert res.retry_count == 1
        assert len(session.calls) == 2             # 1 initial + 1 retry only

    def test_no_retry_on_auth(self, monkeypatch):
        session = FakeSession(
            [FakeResponse(status_code=401, payload={"error": {"message": "x"}})])
        p = DeepSeekProvider(session=session)
        monkeypatch.setenv("DEEPSEEK_API_KEY", FAKE_KEY)
        p.generate_structured(ModelRequest(user_prompt="ping",
                                           schema=SIMPLE_SCHEMA))
        assert len(session.calls) == 1


# ══════════════════════════════════════════════════════════════════════════════
# 16. Provider health states
# ══════════════════════════════════════════════════════════════════════════════
class TestHealthStates:
    def test_connected(self, monkeypatch):
        p = make_provider(
            [FakeResponse(payload={"data": [{"id": "deepseek-flash"},
                                            {"id": "deepseek-chat"}]})],
            monkeypatch)
        h = p.health_check()
        assert isinstance(h, ProviderHealth)
        assert h.status == ProviderStatus.CONNECTED
        assert h.model_id == "deepseek-flash"
        assert h.latency_ms >= 0

    def test_model_not_listed_is_degraded(self, monkeypatch):
        p = make_provider(
            [FakeResponse(payload={"data": [{"id": "deepseek-chat"}]})],
            monkeypatch)
        assert p.health_check().status == ProviderStatus.DEGRADED

    def test_rate_limited_is_degraded(self, monkeypatch):
        p = make_provider([FakeResponse(status_code=429, payload={})],
                          monkeypatch)
        assert p.health_check().status == ProviderStatus.DEGRADED

    def test_unreachable_is_offline(self, monkeypatch):
        p = make_provider([requests.exceptions.ConnectionError("down")],
                          monkeypatch)
        assert p.health_check().status == ProviderStatus.OFFLINE

    def test_auth_rejected_is_offline(self, monkeypatch):
        p = make_provider([FakeResponse(status_code=401, payload={})],
                          monkeypatch)
        assert p.health_check().status == ProviderStatus.OFFLINE

    def test_missing_key_is_offline_without_http(self):
        p = DeepSeekProvider(session=FakeSession([]))  # no key in env
        h = p.health_check()
        assert h.status == ProviderStatus.OFFLINE
        assert "DEEPSEEK_API_KEY" in h.detail
        assert p._session.calls == []

    def test_health_is_cached(self, monkeypatch):
        session = FakeSession(
            [FakeResponse(payload={"data": [{"id": "deepseek-flash"}]})] * 2)
        p = DeepSeekProvider(session=session)
        monkeypatch.setenv("DEEPSEEK_API_KEY", FAKE_KEY)
        p.health_check()
        p.health_check()
        assert len(session.calls) == 1             # refresh must not re-probe
        p.health_check(force=True)
        assert len(session.calls) == 2

    def test_fallback_active_state_exposed(self, monkeypatch):
        p = make_provider([FakeResponse(status_code=503, payload={})] * 3,
                          monkeypatch)
        res = p.generate_structured(ModelRequest(
            user_prompt="ping", schema=SIMPLE_SCHEMA,
            fallback_data={"answer": "fb", "confidence": 0.0}))
        assert res.status == ProviderStatus.FALLBACK_ACTIVE


# ══════════════════════════════════════════════════════════════════════════════
# 17. Deterministic fallback semantics
# ══════════════════════════════════════════════════════════════════════════════
class TestDeterministicFallback:
    def test_fallback_never_masquerades_as_real_output(self, monkeypatch):
        fallback = {"answer": "rule-based-fallback", "confidence": 0.0}
        p = make_provider([FakeResponse(status_code=401, payload={})],
                          monkeypatch)
        res = p.generate_structured(ModelRequest(
            user_prompt="ping", schema=SIMPLE_SCHEMA,
            fallback_data=fallback))
        assert res.success is False                # explicitly NOT success
        assert res.fallback_used is True
        assert res.data == fallback                # payload preserved verbatim
        assert res.status == ProviderStatus.FALLBACK_ACTIVE
        assert res.error_category is not None      # failure explicitly recorded
        audit = res.to_audit_dict()
        assert audit["fallback_used"] is True and audit["success"] is False

    def test_no_fallback_data_yields_none_data(self, monkeypatch):
        p = make_provider([FakeResponse(status_code=401, payload={})],
                          monkeypatch)
        res = p.generate_structured(ModelRequest(user_prompt="ping",
                                                 schema=SIMPLE_SCHEMA))
        assert res.success is False and res.data is None
        assert res.fallback_used is False


# ══════════════════════════════════════════════════════════════════════════════
# 18. No secret leakage
# ══════════════════════════════════════════════════════════════════════════════
class TestNoSecretLeakage:
    def test_key_never_appears_in_errors_audit_or_logs(self, monkeypatch,
                                                       caplog):
        monkeypatch.setenv("DEEPSEEK_API_KEY", FAKE_KEY)
        # A pathological error body that echoes the key back
        leaky_body = {"error": {"message": f"invalid key {FAKE_KEY}"}}
        session = FakeSession([FakeResponse(status_code=401,
                                            payload=leaky_body)])
        p = DeepSeekProvider(session=session)
        with caplog.at_level("DEBUG"):
            res = p.generate_structured(ModelRequest(
                user_prompt="ping", schema=SIMPLE_SCHEMA,
                fallback_data={"answer": "fb", "confidence": 0.0}))
        assert res.success is False

        dumped = json.dumps(res.to_audit_dict(), default=str) + res.error_message
        assert FAKE_KEY not in dumped
        assert FAKE_KEY not in repr(p)
        assert FAKE_KEY not in caplog.text
        assert "[REDACTED]" in res.error_message   # scrubbing actually ran

    def test_auth_header_sent_but_never_surfaced(self, monkeypatch):
        session = FakeSession([FakeResponse(payload=chat_payload(VALID_JSON))])
        p = DeepSeekProvider(session=session)
        monkeypatch.setenv("DEEPSEEK_API_KEY", FAKE_KEY)
        res = p.generate_structured(ModelRequest(user_prompt="ping",
                                                 schema=SIMPLE_SCHEMA))
        assert res.success is True
        sent = session.calls[0]["headers"]["Authorization"]
        assert sent == f"Bearer {FAKE_KEY}"        # header used for the call
        assert FAKE_KEY not in json.dumps(res.to_audit_dict(), default=str)
        assert "Authorization" not in json.dumps(res.to_audit_dict())

    def test_exception_messages_sanitized(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", FAKE_KEY)
        p = DeepSeekProvider(session=FakeSession([]))
        msg = p._sanitize(f"weird echo of {FAKE_KEY} in transport text")
        assert FAKE_KEY not in msg


# ══════════════════════════════════════════════════════════════════════════════
# 19. Audit metadata
# ══════════════════════════════════════════════════════════════════════════════
class TestAuditMetadata:
    def test_success_audit_fields(self, monkeypatch):
        usage = {"prompt_tokens": 21, "completion_tokens": 9,
                 "total_tokens": 30}
        p = make_provider(
            [FakeResponse(payload=chat_payload(VALID_JSON, usage=usage,
                                               response_id="chatcmpl-abc123"))],
            monkeypatch)
        res = p.generate_structured(ModelRequest(
            user_prompt="ping", schema=SIMPLE_SCHEMA, run_id="run-42"))
        assert res.success is True
        assert res.provider == "deepseek"
        assert res.model_id == "deepseek-flash"
        assert res.request_id
        assert res.run_id == "run-42"
        assert res.provider_response_id == "chatcmpl-abc123"
        assert res.latency_ms >= 0
        assert res.token_usage == usage
        assert res.http_status == 200
        audit = res.to_audit_dict()
        for key in ("provider", "model_id", "request_id", "run_id",
                    "success", "status", "fallback_used", "error_category",
                    "latency_ms", "retry_count", "repair_count",
                    "token_usage"):
            assert key in audit
        assert audit["status"] == "CONNECTED"

    def test_token_usage_accumulates_across_retry_and_repair(self,
                                                             monkeypatch):
        u = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        p = make_provider(
            [requests.exceptions.Timeout("t"),
             FakeResponse(payload=chat_payload("bad", usage=u)),
             FakeResponse(payload=chat_payload(VALID_JSON, usage=u))],
            monkeypatch)
        res = p.generate_structured(ModelRequest(user_prompt="ping",
                                                 schema=SIMPLE_SCHEMA))
        assert res.success is True
        assert res.retry_count == 1 and res.repair_count == 1
        assert res.token_usage["total_tokens"] == 30

    def test_failure_audit_records_category_and_counts(self, monkeypatch):
        p = make_provider(
            [FakeResponse(status_code=429, payload={})] * 3, monkeypatch)
        res = p.generate_structured(ModelRequest(user_prompt="ping",
                                                 schema=SIMPLE_SCHEMA))
        audit = res.to_audit_dict()
        assert audit["error_category"] == "RATE_LIMIT"
        assert audit["retry_count"] == 2
        assert audit["http_status"] == 429


# ══════════════════════════════════════════════════════════════════════════════
# 20. No live API call during ordinary pytest (+ multimodal interface)
# ══════════════════════════════════════════════════════════════════════════════
class TestNoLiveCallsAndMultimodal:
    def test_module_never_opens_socket(self):
        # The autouse no_network fixture already guarantees this for every
        # test above; assert the guard itself is active.
        with pytest.raises(AssertionError):
            socket.socket()

    def test_full_generation_without_key_makes_no_http_call(self):
        session = FakeSession([])
        p = DeepSeekProvider(session=session)
        res = p.generate_structured(ModelRequest(
            user_prompt="ping", schema=SIMPLE_SCHEMA,
            fallback_data={"answer": "fb", "confidence": 0.0}))
        assert session.calls == []
        assert res.success is False and res.fallback_used is True

    def test_multimodal_message_shape_url(self, monkeypatch):
        session = FakeSession([FakeResponse(payload=chat_payload(VALID_JSON))])
        p = DeepSeekProvider(session=session)
        monkeypatch.setenv("DEEPSEEK_API_KEY", FAKE_KEY)
        res = p.generate_multimodal(
            ModelRequest(user_prompt="Describe this glacier.",
                         schema=SIMPLE_SCHEMA),
            images=["https://example.invalid/scene.png"])
        assert res.success is True
        content = session.calls[0]["json"]["messages"][1]["content"]
        assert content[0]["type"] == "text"
        assert content[1]["type"] == "image_url"
        assert content[1]["image_url"]["url"] == "https://example.invalid/scene.png"

    def test_multimodal_message_shape_bytes_and_path(self, monkeypatch,
                                                     tmp_path):
        img = tmp_path / "scene.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\nfakedata")
        session = FakeSession([FakeResponse(payload=chat_payload(VALID_JSON))])
        p = DeepSeekProvider(session=session)
        monkeypatch.setenv("DEEPSEEK_API_KEY", FAKE_KEY)
        res = p.generate_multimodal(
            ModelRequest(user_prompt="q", schema=SIMPLE_SCHEMA),
            images=[b"\xff\xd8jpegbytes", str(img)])
        assert res.success is True
        content = session.calls[0]["json"]["messages"][1]["content"]
        assert content[1]["image_url"]["url"].startswith(
            "data:image/jpeg;base64,")
        assert content[2]["image_url"]["url"].startswith(
            "data:image/png;base64,")

    def test_multimodal_without_key_falls_back(self):
        p = DeepSeekProvider(session=FakeSession([]))
        res = p.generate_multimodal(
            ModelRequest(user_prompt="q", schema=SIMPLE_SCHEMA,
                         fallback_data={"answer": "fb", "confidence": 0.0}),
            images=["https://example.invalid/x.png"])
        assert res.success is False and res.fallback_used is True
        assert res.status == ProviderStatus.FALLBACK_ACTIVE
