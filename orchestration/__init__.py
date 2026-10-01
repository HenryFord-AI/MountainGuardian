"""
MountainGuardian v1.0 – orchestration package.

G02A scope: the AnalysisContext builder (doc 03 §7, §25, §26; doc 02 §5.3).
G02B scope: the deterministic Historical Risk Engine and the explicit
Historical Replay Stage-A/Stage-B orchestration DAG (doc 03 §13, §16;
doc 07 §14).
G03C scope: the Risk Watch end-to-end workflow — run_risk_scan(region_id)
connects the G03A data foundation and the G03B deterministic engine with
the G02A professional agents and G02B synthesis/critic (doc 04 §29/§36-39,
doc 03 §36.2, doc 07 §17).
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
from orchestration.risk_watch_adapter import (
    RiskWatchEngineAdapter,
    RiskWatchScanRecord,
    risk_watch_adapter,
)
from orchestration.risk_watch_orchestrator import (
    CountingProvider,
    RiskScanError,
    RiskWatchRunResult,
    build_risk_watch_context,
    compute_data_quality,
    run_risk_scan,
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
    "RiskWatchEngineAdapter",
    "RiskWatchScanRecord",
    "risk_watch_adapter",
    "CountingProvider",
    "RiskScanError",
    "RiskWatchRunResult",
    "build_risk_watch_context",
    "compute_data_quality",
    "run_risk_scan",
]
