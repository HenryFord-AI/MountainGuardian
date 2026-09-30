"""
MountainGuardian v1.0 – orchestration package.

G02A scope: the AnalysisContext builder (doc 03 §7, §25, §26; doc 02 §5.3).
G02B scope: the deterministic Historical Risk Engine and the explicit
Historical Replay Stage-A/Stage-B orchestration DAG (doc 03 §13, §16;
doc 07 §14).
"""

from orchestration.context_builder import (
    MODE_HISTORICAL_REPLAY,
    MODE_RISK_WATCH,
    AgentEvidenceView,
    AnalysisContext,
    agent_evidence_view,
    build_analysis_context,
)
from orchestration.replay_orchestrator import (
    FrozenStateError,
    HistoricalReplayResult,
    StageAFreeze,
    StageBValidationResult,
    build_stage_a_freeze,
    run_historical_replay,
    run_stage_a,
    run_stage_b,
)
from orchestration.risk_engine import (
    HistoricalRiskResult,
    RiskEngineError,
    compute_historical_risk,
    risk_level_for,
)

__all__ = [
    "MODE_HISTORICAL_REPLAY",
    "MODE_RISK_WATCH",
    "AgentEvidenceView",
    "AnalysisContext",
    "agent_evidence_view",
    "build_analysis_context",
    "FrozenStateError",
    "HistoricalReplayResult",
    "StageAFreeze",
    "StageBValidationResult",
    "build_stage_a_freeze",
    "run_historical_replay",
    "run_stage_a",
    "run_stage_b",
    "HistoricalRiskResult",
    "RiskEngineError",
    "compute_historical_risk",
    "risk_level_for",
]
