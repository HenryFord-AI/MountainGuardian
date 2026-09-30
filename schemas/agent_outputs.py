"""
MountainGuardian v1.0 – professional agent output contracts.

Frozen design references:
  - 03_MountainGuardian_AI_Agent_Architecture_v1.0.md §10.3 / §11.3 / §12.4
    (per-agent output structures), §19 (structured output), §20 (validation
    pipeline), §28 (agent status enum), §29 (confidence semantics),
    §33 (audit logging), §34 (prompt versioning)
  - 02_MountainGuardian_Scientific_Data_Baseline_v1.0.md §6 (Risk Index ≠
    Probability), §19 (missing data is a valid formal output)

Confidence is the agent's confidence in its professional analysis under
current data conditions. It is NEVER an event probability.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

from schemas.evidence import (
    AGENT_GLACIER_GEOLOGY,
    AGENT_REMOTE_SENSING,
    AGENT_WEATHER_HYDROLOGY,
)

AGENT_OUTPUT_SCHEMA_VERSION = "v1"


# ─── Enums (doc 03 §28) ────────────────────────────────────────────────────────
class AgentStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    SKIPPED = "SKIPPED"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"


class RiskSignal(str, Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    ELEVATED = "ELEVATED"
    HIGH = "HIGH"
    DATA_LIMITED = "DATA_LIMITED"


#: Statuses a model may report about itself; SKIPPED/FAILED/PENDING/RUNNING
#: are produced by the runtime, never by the model.
_MODEL_STATUSES = ["COMPLETED", "DEGRADED"]

_RISK_SIGNAL_VALUES = [s.value for s in RiskSignal]


# ─── Output JSON schemas (schema-first, doc 03 §19) ────────────────────────────
def _base_properties(agent_name: str) -> dict:
    return {
        "agent": {"type": "string", "enum": [agent_name]},
        "status": {"type": "string", "enum": _MODEL_STATUSES},
        "risk_signal": {"type": "string", "enum": _RISK_SIGNAL_VALUES},
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "key_findings": {"type": "array", "items": {"type": "string"}},
        "evidence_ids": {"type": "array", "items": {"type": "string"}},
        "missing_data": {"type": "array", "items": {"type": "string"}},
        "limitations": {"type": "array", "items": {"type": "string"}},
    }


_BASE_REQUIRED = [
    "agent", "status", "risk_signal", "confidence",
    "key_findings", "evidence_ids", "missing_data", "limitations",
]

_SCHEMAS: dict = {
    AGENT_GLACIER_GEOLOGY: {
        "type": "object",
        "required": _BASE_REQUIRED + ["risk_drivers"],
        "properties": {
            **_base_properties(AGENT_GLACIER_GEOLOGY),
            "risk_drivers": {"type": "array", "items": {"type": "string"}},
        },
    },
    AGENT_WEATHER_HYDROLOGY: {
        "type": "object",
        "required": _BASE_REQUIRED + ["recent_conditions", "forecast_signals"],
        "properties": {
            **_base_properties(AGENT_WEATHER_HYDROLOGY),
            "recent_conditions": {"type": "array", "items": {"type": "string"}},
            "forecast_signals": {"type": "array", "items": {"type": "string"}},
        },
    },
    AGENT_REMOTE_SENSING: {
        "type": "object",
        "required": _BASE_REQUIRED + ["image_ids", "observations",
                                      "quality_notes"],
        "properties": {
            **_base_properties(AGENT_REMOTE_SENSING),
            "image_ids": {"type": "array", "items": {"type": "string"}},
            "observations": {"type": "array", "items": {"type": "string"}},
            "quality_notes": {"type": "array", "items": {"type": "string"}},
        },
    },
}


def output_schema_for(agent_name: str) -> dict:
    try:
        return _SCHEMAS[agent_name]
    except KeyError:
        raise ValueError(f"no output schema for agent {agent_name!r}") from None


# ─── Scientific / authorization output validation (doc 03 §20) ────────────────
def make_output_validator(agent_name: str,
                          allowed_evidence_ids: frozenset,
                          ) -> Callable[[dict], list]:
    """Build the scientific-constraint validator hook for ModelRequest.

    Enforces (in the provider pipeline, BEFORE any result is accepted):
      * agent identity matches;
      * confidence within [0, 1] (schema also enforces; belt and braces);
      * every cited evidence_id was actually authorized for this agent —
        unknown / hallucinated IDs are rejected;
      * key_findings non-empty (a formal 'no findings' still needs text);
      * status is a model-reportable status.
    """
    allowed = set(allowed_evidence_ids)

    def validate(data: dict) -> list:
        errors: list = []
        if data.get("agent") != agent_name:
            errors.append(f"agent field must be '{agent_name}'")
        status = data.get("status")
        if status not in _MODEL_STATUSES:
            errors.append(f"status {status!r} not model-reportable")
        conf = data.get("confidence")
        if (isinstance(conf, bool) or not isinstance(conf, (int, float))
                or not (0.0 <= float(conf) <= 1.0)):
            errors.append("confidence must be a number in [0, 1]")
        ids = data.get("evidence_ids")
        if not isinstance(ids, list):
            errors.append("evidence_ids must be a list")
        else:
            unknown = [str(i) for i in ids if str(i) not in allowed]
            if unknown:
                errors.append(
                    f"unknown or unauthorized evidence ids: {unknown[:10]}")
        findings = data.get("key_findings")
        if not isinstance(findings, list) or not findings:
            errors.append("key_findings must be a non-empty list")
        return errors

    return validate


# ─── Unified agent run result ──────────────────────────────────────────────────
@dataclass
class AgentRunResult:
    """Structured result of one professional agent run.

    Carries the model's scientific content (when the real model succeeded),
    the explicit runtime status, provider/fallback state, and audit metadata
    (doc 03 §33). `is_model_output` distinguishes real model analysis from
    deterministic fallback so the UI can never present fallback as AI output
    (doc 03 §22.1).
    """

    agent_name: str
    status: AgentStatus
    run_id: str = ""
    risk_signal: Optional[str] = None
    confidence: float = 0.0
    key_findings: list = field(default_factory=list)
    evidence_ids: list = field(default_factory=list)
    missing_data: list = field(default_factory=list)
    limitations: list = field(default_factory=list)
    agent_specific: dict = field(default_factory=dict)

    # runtime / provider state
    is_model_output: bool = False
    fallback_used: bool = False
    provider_status: str = ""
    provider: str = ""
    model_id: str = ""
    request_id: str = ""
    error_category: Optional[str] = None
    error_message: Optional[str] = None
    skip_reason: Optional[str] = None

    # audit metadata
    prompt_id: str = ""
    prompt_version: str = ""
    schema_version: str = AGENT_OUTPUT_SCHEMA_VERSION
    input_evidence_ids: list = field(default_factory=list)
    quarantined_evidence_ids: list = field(default_factory=list)
    latency_ms: int = 0
    token_usage: dict = field(default_factory=dict)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "agent": self.agent_name,
            "status": self.status.value,
            "risk_signal": self.risk_signal,
            "confidence": self.confidence,
            "key_findings": list(self.key_findings),
            "evidence_ids": list(self.evidence_ids),
            "missing_data": list(self.missing_data),
            "limitations": list(self.limitations),
            **{k: list(v) for k, v in self.agent_specific.items()},
            "is_model_output": self.is_model_output,
            "fallback_used": self.fallback_used,
            "provider_status": self.provider_status,
            "skip_reason": self.skip_reason,
            "run_id": self.run_id,
        }

    def to_audit_dict(self) -> dict:
        """Full audit record (doc 03 §33). Contains no secrets by
        construction — provider errors are already sanitized upstream."""
        return {
            "run_id": self.run_id,
            "agent_id": self.agent_name,
            "prompt_id": self.prompt_id,
            "prompt_version": self.prompt_version,
            "schema_version": self.schema_version,
            "model_id": self.model_id,
            "provider": self.provider,
            "request_id": self.request_id,
            "status": self.status.value,
            "provider_status": self.provider_status,
            "is_model_output": self.is_model_output,
            "fallback_used": self.fallback_used,
            "error_category": self.error_category,
            "error_message": self.error_message,
            "skip_reason": self.skip_reason,
            "input_evidence_ids": list(self.input_evidence_ids),
            "quarantined_evidence_ids": list(self.quarantined_evidence_ids),
            "latency_ms": self.latency_ms,
            "token_usage": dict(self.token_usage),
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_model_data(cls, agent_name: str, data: dict, *,
                        specific_keys: tuple = (), **kwargs) -> "AgentRunResult":
        """Build a result from validated model JSON (or fallback payload)."""
        specific = {k: list(data.get(k) or []) for k in specific_keys}
        risk_signal = data.get("risk_signal")
        if risk_signal not in _RISK_SIGNAL_VALUES:
            risk_signal = None
        return cls(
            agent_name=agent_name,
            risk_signal=risk_signal,
            confidence=float(data.get("confidence") or 0.0),
            key_findings=list(data.get("key_findings") or []),
            evidence_ids=[str(i) for i in (data.get("evidence_ids") or [])],
            missing_data=list(data.get("missing_data") or []),
            limitations=list(data.get("limitations") or []),
            agent_specific=specific,
            **kwargs,
        )


#: agent-specific extra fields per doc 03 §10.3 / §11.3 / §12.4
AGENT_SPECIFIC_KEYS = {
    AGENT_GLACIER_GEOLOGY: ("risk_drivers",),
    AGENT_WEATHER_HYDROLOGY: ("recent_conditions", "forecast_signals"),
    AGENT_REMOTE_SENSING: ("image_ids", "observations", "quality_notes"),
}
