"""
MountainGuardian v1.0 – Risk Synthesizer & Critic output contracts (G02B).

Frozen design references:
  - 03_MountainGuardian_AI_Agent_Architecture_v1.0.md §14 (Risk Synthesizer
    inputs/duties/prohibitions/output structure), §15 (Critic review
    dimensions and output; allowed results PASS / PASS_WITH_LIMITATIONS /
    NEEDS_REVISION / BLOCKED), §18 (Agent Agreement taxonomy), §19–20
    (structured output + validation), §22 (fallback never masquerades as
    model output)
  - 02_MountainGuardian_Scientific_Data_Baseline_v1.0.md §6.1/§6.4 (Risk
    Index is not probability; v1.0 forbids event-probability output), §8.2
    (LLM explains, never overrides the deterministic number)

Hard rules encoded here:
  * the authoritative Risk Index in a SynthesisResult is ALWAYS the value
    carried from the deterministic engine — model output can never set it;
  * explanation_confidence is confidence in the analysis under available
    evidence, never a disaster probability;
  * the Critic verdict taxonomy is frozen; the Critic may reject or flag
    narrative claims but can never change the Risk Index.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Callable, Optional

SYNTHESIS_SCHEMA_VERSION = "v1"
CRITIC_SCHEMA_VERSION = "v1"


# ─── Frozen enums ──────────────────────────────────────────────────────────────
class AgentAgreement(str, Enum):
    """doc 03 §18 — computed deterministically by the Synthesizer runtime."""

    AGREEMENT = "AGREEMENT"
    PARTIAL_AGREEMENT = "PARTIAL_AGREEMENT"
    SIGNIFICANT_DISAGREEMENT = "SIGNIFICANT_DISAGREEMENT"


class CriticReviewResult(str, Enum):
    """doc 03 §15.2 — frozen verdict taxonomy, preserved exactly."""

    PASS = "PASS"
    PASS_WITH_LIMITATIONS = "PASS_WITH_LIMITATIONS"
    NEEDS_REVISION = "NEEDS_REVISION"
    BLOCKED = "BLOCKED"


class IssueSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


#: Frozen Critic check dimensions (G02B spec §11 / doc 03 §15.1)
CRITIC_CHECK_IDS = (
    "EVIDENCE_SUPPORT",
    "POST_EVENT_LEAKAGE",
    "CAUSAL_OVERCLAIM",
    "PROBABILITY_MISUSE",
    "MISSING_DATA_HONESTY",
    "AGENT_DISAGREEMENT",
    "SATELLITE_OVERCLAIM",
    "EVIDENCE_ID_INTEGRITY",
    "SCORE_INTEGRITY",
    "FALLBACK_LABELING",
)

_AGREEMENT_VALUES = [a.value for a in AgentAgreement]
_REVIEW_VALUES = [r.value for r in CriticReviewResult]


# ─── Synthesizer output schema (schema-first, doc 03 §19) ─────────────────────
SYNTHESIS_OUTPUT_SCHEMA = {
    "type": "object",
    "required": [
        "risk_index", "risk_level", "summary", "risk_explanation",
        "top_drivers", "agent_agreement", "disagreements",
        "evidence_coverage", "missing_data", "limitations",
        "explanation_confidence", "evidence_ids",
    ],
    "properties": {
        # The model must ECHO the deterministic index/level verbatim; the
        # runtime independently enforces them and rejects any deviation.
        "risk_index": {"type": "number", "minimum": 0, "maximum": 100},
        "risk_level": {"type": "string",
                       "enum": ["LOW", "MODERATE", "ELEVATED", "HIGH"]},
        "summary": {"type": "string"},
        "risk_explanation": {"type": "string"},
        "top_drivers": {"type": "array", "items": {"type": "string"}},
        "agent_agreement": {"type": "string", "enum": _AGREEMENT_VALUES},
        "disagreements": {"type": "array", "items": {"type": "string"}},
        "evidence_coverage": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "missing_data": {"type": "array", "items": {"type": "string"}},
        "limitations": {"type": "array", "items": {"type": "string"}},
        "explanation_confidence": {"type": "number",
                                   "minimum": 0.0, "maximum": 1.0},
        "evidence_ids": {"type": "array", "items": {"type": "string"}},
    },
}

CRITIC_OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["review_result", "issues", "scientific_limitations",
                 "required_corrections"],
    "properties": {
        "review_result": {"type": "string", "enum": _REVIEW_VALUES},
        "issues": {"type": "array", "items": {"type": "string"}},
        "scientific_limitations": {"type": "array",
                                   "items": {"type": "string"}},
        "required_corrections": {"type": "array",
                                 "items": {"type": "string"}},
    },
}


def make_synthesis_validator(expected_index: float, expected_level: str,
                             allowed_evidence_ids: frozenset,
                             ) -> Callable[[dict], list]:
    """Scientific-constraint validator for Synthesizer model output.

    Enforces BEFORE acceptance (doc 03 §20):
      * risk_index equals the deterministic engine value (the model may
        echo it, never alter it — doc 03 §14.3);
      * risk_level equals the deterministic band;
      * every cited evidence_id was authorized (unknown/hallucinated IDs
        are rejected);
      * explanation_confidence within [0, 1];
      * narrative fields non-empty.
    """
    allowed = set(allowed_evidence_ids)

    def validate(data: dict) -> list:
        errors: list = []
        idx = data.get("risk_index")
        if (isinstance(idx, bool) or not isinstance(idx, (int, float))
                or abs(float(idx) - float(expected_index)) > 0.05):
            errors.append(
                f"risk_index must equal the deterministic engine value "
                f"{expected_index} — the model may not change it")
        if data.get("risk_level") != expected_level:
            errors.append(
                f"risk_level must equal '{expected_level}' (deterministic)")
        conf = data.get("explanation_confidence")
        if (isinstance(conf, bool) or not isinstance(conf, (int, float))
                or not (0.0 <= float(conf) <= 1.0)):
            errors.append("explanation_confidence must be a number in [0, 1]")
        ids = data.get("evidence_ids")
        if not isinstance(ids, list):
            errors.append("evidence_ids must be a list")
        else:
            unknown = [str(i) for i in ids if str(i) not in allowed]
            if unknown:
                errors.append(
                    f"unknown or unauthorized evidence ids: {unknown[:10]}")
        for key in ("summary", "risk_explanation"):
            if not str(data.get(key) or "").strip():
                errors.append(f"{key} must be a non-empty string")
        drivers = data.get("top_drivers")
        if not isinstance(drivers, list) or not drivers:
            errors.append("top_drivers must be a non-empty list")
        if data.get("agent_agreement") not in _AGREEMENT_VALUES:
            errors.append("agent_agreement must be a frozen enum value")
        return errors

    return validate


def make_critic_validator() -> Callable[[dict], list]:
    """Validator for Critic model output: frozen enum + list shapes."""

    def validate(data: dict) -> list:
        errors: list = []
        if data.get("review_result") not in _REVIEW_VALUES:
            errors.append("review_result must be one of "
                          f"{_REVIEW_VALUES}")
        for key in ("issues", "scientific_limitations",
                    "required_corrections"):
            if not isinstance(data.get(key), list):
                errors.append(f"{key} must be a list of strings")
        return errors

    return validate


# ─── Result dataclasses ────────────────────────────────────────────────────────
@dataclass
class SynthesisResult:
    """Structured Risk Synthesizer output (doc 03 §14.4 + G02B §9).

    `deterministic_risk_index` / `risk_level` are copied from the immutable
    engine result by the runtime — they are NEVER taken from model data.
    """

    run_id: str
    deterministic_risk_index: float
    risk_level: str
    summary: str = ""
    risk_explanation: str = ""
    top_drivers: list = field(default_factory=list)
    agent_agreement: str = AgentAgreement.PARTIAL_AGREEMENT.value
    disagreements: list = field(default_factory=list)
    evidence_coverage: float = 0.0
    missing_data: list = field(default_factory=list)
    limitations: list = field(default_factory=list)
    explanation_confidence: float = 0.0
    evidence_ids: list = field(default_factory=list)
    agent_status_summary: dict = field(default_factory=dict)

    # runtime / provider state
    is_model_output: bool = False
    fallback_used: bool = False
    provider_status: str = ""
    provider: str = ""
    model_id: str = ""
    request_id: str = ""
    error_category: Optional[str] = None
    error_message: Optional[str] = None

    # audit metadata
    prompt_id: str = "risk_synthesizer_v1"
    prompt_version: str = "v1"
    schema_version: str = SYNTHESIS_SCHEMA_VERSION
    input_evidence_ids: list = field(default_factory=list)
    quarantined_texts: int = 0
    latency_ms: int = 0
    token_usage: dict = field(default_factory=dict)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "deterministic_risk_index": self.deterministic_risk_index,
            "risk_level": self.risk_level,
            "summary": self.summary,
            "risk_explanation": self.risk_explanation,
            "top_drivers": list(self.top_drivers),
            "agent_agreement": self.agent_agreement,
            "disagreements": list(self.disagreements),
            "evidence_coverage": self.evidence_coverage,
            "missing_data": list(self.missing_data),
            "limitations": list(self.limitations),
            "explanation_confidence": self.explanation_confidence,
            "evidence_ids": list(self.evidence_ids),
            "agent_status_summary": dict(self.agent_status_summary),
            "is_model_output": self.is_model_output,
            "fallback_used": self.fallback_used,
            "provider_status": self.provider_status,
        }

    def to_audit_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "component": "risk_synthesizer",
            "prompt_id": self.prompt_id,
            "prompt_version": self.prompt_version,
            "schema_version": self.schema_version,
            "model_id": self.model_id,
            "provider": self.provider,
            "request_id": self.request_id,
            "provider_status": self.provider_status,
            "is_model_output": self.is_model_output,
            "fallback_used": self.fallback_used,
            "error_category": self.error_category,
            "error_message": self.error_message,
            "deterministic_risk_index": self.deterministic_risk_index,
            "input_evidence_ids": list(self.input_evidence_ids),
            "quarantined_texts": self.quarantined_texts,
            "latency_ms": self.latency_ms,
            "token_usage": dict(self.token_usage),
            "timestamp": self.timestamp,
        }


@dataclass(frozen=True)
class CriticIssue:
    """One programmatic or model-review finding (immutable)."""

    check_id: str
    severity: str            # IssueSeverity value
    message: str
    origin: str = "programmatic"   # or "model_review"

    def to_dict(self) -> dict:
        return {"check_id": self.check_id, "severity": self.severity,
                "message": self.message, "origin": self.origin}


@dataclass
class CriticVerdictResult:
    """Structured Critic verdict (doc 03 §15.2). The Critic never changes
    the Risk Index — this object does not even carry one."""

    run_id: str
    review_result: str = CriticReviewResult.PASS.value
    severity: str = IssueSeverity.INFO.value
    issues: list = field(default_factory=list)              # CriticIssue
    scientific_limitations: list = field(default_factory=list)
    required_corrections: list = field(default_factory=list)
    programmatic_check_status: dict = field(default_factory=dict)
    risk_index_before: Optional[float] = None   # integrity attestation only
    risk_index_after: Optional[float] = None

    # runtime / provider state (narrative review call)
    is_model_output: bool = False
    fallback_used: bool = False
    provider_status: str = ""
    provider: str = ""
    model_id: str = ""
    request_id: str = ""
    error_category: Optional[str] = None
    error_message: Optional[str] = None

    # audit metadata
    prompt_id: str = "critic_v1"
    prompt_version: str = "v1"
    schema_version: str = CRITIC_SCHEMA_VERSION
    latency_ms: int = 0
    token_usage: dict = field(default_factory=dict)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "review_result": self.review_result,
            "severity": self.severity,
            "issues": [i.to_dict() for i in self.issues],
            "scientific_limitations": list(self.scientific_limitations),
            "required_corrections": list(self.required_corrections),
            "programmatic_check_status": dict(self.programmatic_check_status),
            "risk_index_before": self.risk_index_before,
            "risk_index_after": self.risk_index_after,
            "is_model_output": self.is_model_output,
            "fallback_used": self.fallback_used,
            "provider_status": self.provider_status,
        }

    def to_audit_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "component": "critic",
            "prompt_id": self.prompt_id,
            "prompt_version": self.prompt_version,
            "schema_version": self.schema_version,
            "model_id": self.model_id,
            "provider": self.provider,
            "request_id": self.request_id,
            "provider_status": self.provider_status,
            "is_model_output": self.is_model_output,
            "fallback_used": self.fallback_used,
            "error_category": self.error_category,
            "error_message": self.error_message,
            "review_result": self.review_result,
            "latency_ms": self.latency_ms,
            "token_usage": dict(self.token_usage),
            "timestamp": self.timestamp,
        }
