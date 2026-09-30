"""
MountainGuardian v1.0 – Model Provider abstraction.

Frozen design references:
  - 03_MountainGuardian_AI_Agent_Architecture_v1.0.md §5 (Provider Abstraction),
    §19–21 (Structured Output / Validation / Repair Policy),
    §22 (Fallback), §23 (Model Health Check)
  - 06_MountainGuardian_Engineering_Deployment_Spec_v1.0.md §21 (Provider
    engineering boundary), §22 (Provider Error Classification),
    §23 (HTTP Timeout), §24 (Bounded Retry)

This module defines the lightweight logical interface only:

    class ModelProvider:
        def generate_structured(self, request) -> ModelResult: ...
        def generate_multimodal(self, request, images) -> ModelResult: ...
        def health_check(self) -> ProviderHealth: ...

It is deliberately NOT a generic framework. v1.0 has exactly one real
provider implementation: DeepSeekProvider (providers/deepseek_provider.py).

Security contract: secrets (API keys, tokens, authorization headers) must
never appear in exceptions, log messages, or audit metadata produced here.
"""

from __future__ import annotations

import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

REDACTED = "[REDACTED]"


# ─── Provider runtime states (doc 03 §23) ─────────────────────────────────────
class ProviderStatus(str, Enum):
    """Model runtime states frozen by the architecture document.

    CONNECTED       – provider reachable, authenticated, working normally.
    DEGRADED        – provider usable but impaired (retries/repairs needed,
                      rate limited, model not listed, transient errors).
    OFFLINE         – provider unreachable, authentication failed, or no key.
    FALLBACK_ACTIVE – a generation failed and deterministic fallback was used.
    """

    CONNECTED = "CONNECTED"
    DEGRADED = "DEGRADED"
    OFFLINE = "OFFLINE"
    FALLBACK_ACTIVE = "FALLBACK_ACTIVE"


# ─── Provider error classification (doc 06 §22) ───────────────────────────────
class ProviderErrorCategory(str, Enum):
    AUTH_ERROR = "AUTH_ERROR"
    TIMEOUT = "TIMEOUT"
    RATE_LIMIT = "RATE_LIMIT"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    INVALID_RESPONSE = "INVALID_RESPONSE"
    SCHEMA_ERROR = "SCHEMA_ERROR"
    UNKNOWN_PROVIDER_ERROR = "UNKNOWN_PROVIDER_ERROR"


#: Categories eligible for bounded network retry (doc 06 §24).
RETRYABLE_CATEGORIES = frozenset({
    ProviderErrorCategory.TIMEOUT,
    ProviderErrorCategory.RATE_LIMIT,
    ProviderErrorCategory.SERVICE_UNAVAILABLE,
})

#: Categories that mean the provider itself is unreachable/unusable, mapped to
#: OFFLINE when a generation fails without fallback data.
OFFLINE_CATEGORIES = frozenset({
    ProviderErrorCategory.AUTH_ERROR,
    ProviderErrorCategory.TIMEOUT,
    ProviderErrorCategory.SERVICE_UNAVAILABLE,
})


class ProviderError(Exception):
    """Sanitized provider error. The message must never contain secrets,
    authorization headers, or raw response headers."""

    def __init__(
        self,
        category: ProviderErrorCategory,
        message: str,
        http_status: Optional[int] = None,
        retryable: bool = False,
    ):
        self.category = category
        self.http_status = http_status
        self.retryable = retryable
        super().__init__(message)


def sanitize_text(text: str, secrets: tuple = ()) -> str:
    """Remove any secret substring from text before it reaches logs/errors."""
    out = str(text)
    for secret in secrets:
        if secret:
            out = out.replace(secret, REDACTED)
    return out


# ─── Request / Result / Health dataclasses ────────────────────────────────────
@dataclass
class ModelRequest:
    """A single structured generation request.

    schema           – optional JSON-schema-like dict validated after parsing
                       (subset supported by validate_json_schema below).
    output_validator – optional scientific/output validation hook. Callable
                       receiving the parsed dict, returning a list of error
                       strings (empty/None = pass).
    fallback_data    – optional deterministic fallback payload. When the real
                       model call cannot safely complete, it is returned in
                       ModelResult.data with fallback_used=True and
                       success=False, so callers/UI can never mistake it for
                       real model output (doc 03 §22.1).
    run_id           – analysis run identifier threaded through for audit.
    """

    system_prompt: str = ""
    user_prompt: str = ""
    schema: Optional[dict] = None
    output_validator: Optional[Callable[[dict], Optional[list]]] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    run_id: Optional[str] = None
    request_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    fallback_data: Optional[dict] = None


@dataclass
class ModelResult:
    """Result of a provider generation call, with audit metadata (G01 §4.I)."""

    success: bool
    data: Optional[dict] = None
    raw_text: str = ""
    status: ProviderStatus = ProviderStatus.OFFLINE
    fallback_used: bool = False

    # Error information (always sanitized)
    error_category: Optional[ProviderErrorCategory] = None
    error_message: Optional[str] = None

    # Audit metadata
    provider: str = ""
    model_id: str = ""
    request_id: str = ""
    run_id: Optional[str] = None
    provider_response_id: Optional[str] = None
    latency_ms: int = 0
    retry_count: int = 0
    repair_count: int = 0
    http_status: Optional[int] = None
    token_usage: dict = field(default_factory=dict)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_audit_dict(self) -> dict:
        """Serializable audit record. Contains no secrets by construction."""
        return {
            "provider": self.provider,
            "model_id": self.model_id,
            "request_id": self.request_id,
            "run_id": self.run_id,
            "provider_response_id": self.provider_response_id,
            "success": self.success,
            "status": self.status.value,
            "fallback_used": self.fallback_used,
            "error_category": (self.error_category.value
                               if self.error_category else None),
            "error_message": self.error_message,
            "latency_ms": self.latency_ms,
            "retry_count": self.retry_count,
            "repair_count": self.repair_count,
            "http_status": self.http_status,
            "token_usage": dict(self.token_usage),
            "timestamp": self.timestamp,
        }


@dataclass
class ProviderHealth:
    """Health-check snapshot (doc 03 §23). Never raises; cheap to call."""

    status: ProviderStatus
    model_id: str = ""
    detail: str = ""
    latency_ms: int = 0
    checked_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "model_id": self.model_id,
            "detail": self.detail,
            "latency_ms": self.latency_ms,
            "checked_at": self.checked_at,
        }


# ─── Minimal JSON-schema-subset validation ────────────────────────────────────
_JSON_TYPES = {
    "object": dict,
    "array": list,
    "string": str,
    "boolean": bool,
    "null": type(None),
}


def validate_json_schema(data: Any, schema: Optional[dict],
                         path: str = "$") -> list:
    """Validate data against a small JSON-schema-like subset.

    Supported keywords: type (object/array/string/number/integer/boolean/
    null), required, properties, items, enum, minimum, maximum.

    Returns a list of human-readable error strings; empty list = valid.
    Deliberately minimal – no external dependency (G01 §5).
    """
    errors: list = []
    if not schema:
        return errors

    expected = schema.get("type")
    if expected:
        ok = False
        if expected == "number":
            ok = isinstance(data, (int, float)) and not isinstance(data, bool)
        elif expected == "integer":
            ok = isinstance(data, int) and not isinstance(data, bool)
        elif expected == "string":
            ok = isinstance(data, str)
        elif expected in _JSON_TYPES:
            py = _JSON_TYPES[expected]
            ok = isinstance(data, py) and not (
                expected != "boolean" and isinstance(data, bool)
                and py is not bool)
        if not ok:
            errors.append(f"{path}: expected type '{expected}', "
                          f"got {type(data).__name__}")
            return errors  # further checks on wrong type are noise

    if "enum" in schema and data not in schema["enum"]:
        errors.append(f"{path}: value {data!r} not in enum {schema['enum']}")

    if isinstance(data, (int, float)) and not isinstance(data, bool):
        if "minimum" in schema and data < schema["minimum"]:
            errors.append(f"{path}: {data} < minimum {schema['minimum']}")
        if "maximum" in schema and data > schema["maximum"]:
            errors.append(f"{path}: {data} > maximum {schema['maximum']}")

    if isinstance(data, dict):
        for req in schema.get("required", []):
            if req not in data:
                errors.append(f"{path}: missing required field '{req}'")
        props = schema.get("properties", {})
        for key, sub in props.items():
            if key in data:
                errors.extend(
                    validate_json_schema(data[key], sub, f"{path}.{key}"))

    if isinstance(data, list) and "items" in schema:
        for i, item in enumerate(data):
            errors.extend(
                validate_json_schema(item, schema["items"], f"{path}[{i}]"))

    return errors


# ─── Abstract provider ────────────────────────────────────────────────────────
class ModelProvider(ABC):
    """Lightweight provider interface (doc 03 §5).

    Agents talk to this interface only – never to an SDK, raw URLs, API keys,
    retries, or HTTP error parsing (doc 06 §21).
    """

    #: short provider identifier used in audit records
    provider_name: str = "abstract"
    #: API model id used at runtime (never a display name)
    model_id: str = ""

    @abstractmethod
    def generate_structured(self, request: ModelRequest) -> ModelResult:
        """Generate a JSON-structured response: parse → schema validation →
        scientific/output validation hook → accept / one bounded repair /
        deterministic fallback (doc 03 §20–22)."""

    @abstractmethod
    def generate_multimodal(self, request: ModelRequest,
                            images: Optional[list] = None) -> ModelResult:
        """Generate from text + image inputs. G01 establishes the capability
        interface only; the Remote Sensing workflow belongs to a later gate."""

    @abstractmethod
    def health_check(self) -> ProviderHealth:
        """Cheap provider health probe. Must not perform token-generating
        calls and must not run on every UI page refresh (doc 03 §23)."""


def extract_json_block(raw: str) -> str:
    """Best-effort extraction of a JSON object/array from model output:
    strips markdown code fences, then falls back to the outermost braces."""
    text = (raw or "").strip()
    if text.startswith("```"):
        first_nl = text.find("\n")
        if first_nl != -1:
            text = text[first_nl + 1:]
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
        text = text.strip()
    if text:
        return text
    return raw or ""


def find_outermost_json(text: str) -> Optional[str]:
    """Return the outermost {...} or [...] slice of text, if any."""
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        end = text.rfind(closer)
        if start != -1 and end > start:
            return text[start:end + 1]
    return None


def monotonic_ms(start: float) -> int:
    return int((time.monotonic() - start) * 1000)
