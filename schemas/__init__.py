"""
MountainGuardian v1.0 – schemas package.

Frozen data contracts for evidence and agent outputs:
  - schemas/evidence.py        – EvidenceItem (doc 02 §16–19, doc 03 §8)
  - schemas/agent_outputs.py   – AgentStatus / RiskSignal / AgentRunResult
                                 and output JSON schemas (doc 03 §10.3,
                                 §11.3, §12.4, §19, §28, §29)
  - schemas/synthesis.py       – Synthesizer / Critic contracts (doc 03
                                 §14–16, §18; G02B)
"""

from schemas.evidence import (
    BOUNDARY_PHASES,
    CONTEXT_ONLY_PHASES,
    POST_EVENT_PHASES,
    PRE_EVENT_RISK_PHASES,
    EvidenceItem,
    EvidenceQuality,
    build_evidence_pool,
    evidence_from_case_field,
    satellite_evidence_items,
)
from schemas.agent_outputs import (
    AGENT_OUTPUT_SCHEMA_VERSION,
    AgentRunResult,
    AgentStatus,
    RiskSignal,
    make_output_validator,
    output_schema_for,
)
from schemas.synthesis import (
    SYNTHESIS_OUTPUT_SCHEMA,
    AgentAgreement,
    CriticIssue,
    CriticReviewResult,
    CriticVerdictResult,
    IssueSeverity,
    SynthesisResult,
    make_synthesis_validator,
)

__all__ = [
    "BOUNDARY_PHASES",
    "CONTEXT_ONLY_PHASES",
    "POST_EVENT_PHASES",
    "PRE_EVENT_RISK_PHASES",
    "EvidenceItem",
    "EvidenceQuality",
    "build_evidence_pool",
    "evidence_from_case_field",
    "satellite_evidence_items",
    "AGENT_OUTPUT_SCHEMA_VERSION",
    "AgentRunResult",
    "AgentStatus",
    "RiskSignal",
    "make_output_validator",
    "output_schema_for",
    "SYNTHESIS_OUTPUT_SCHEMA",
    "AgentAgreement",
    "CriticIssue",
    "CriticReviewResult",
    "CriticVerdictResult",
    "IssueSeverity",
    "SynthesisResult",
    "make_synthesis_validator",
]
