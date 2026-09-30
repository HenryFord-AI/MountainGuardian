"""
MountainGuardian v1.0 – orchestration package.

G02A scope: the AnalysisContext builder (doc 03 §7, §25, §26; doc 02 §5.3).
Full Stage A/B workflow orchestration belongs to G02B and is deliberately
NOT implemented here.
"""

from orchestration.context_builder import (
    MODE_HISTORICAL_REPLAY,
    MODE_RISK_WATCH,
    AgentEvidenceView,
    AnalysisContext,
    agent_evidence_view,
    build_analysis_context,
)

__all__ = [
    "MODE_HISTORICAL_REPLAY",
    "MODE_RISK_WATCH",
    "AgentEvidenceView",
    "AnalysisContext",
    "agent_evidence_view",
    "build_analysis_context",
]
