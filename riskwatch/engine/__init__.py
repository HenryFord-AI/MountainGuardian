"""
MountainGuardian G03B – Risk Watch deterministic engine (subpackage).

Transparent, deterministic and reproducible implementation of the frozen
doc 04 risk algorithm on top of the G03A data foundation:

    B   Regional Static Susceptibility Baseline (region.json static factors)
    R/F point precipitation percentiles -> conservative regional maxima
    D   = 0.60 x R + 0.40 x F
    C   = 0.70 x B + 0.30 x D
    O7  = 0.70 x B + 0.30 x F
    prototype risk bands, Risk Direction, Historical Trend query,
    What Changed comparison, traceable Top Risk Driver contributions.

Hard boundaries of this subpackage:
  * no network access of any kind (consumes cached/normalized G03A data);
  * no LLM / agent / provider imports — results are available with no
    DEEPSEEK_API_KEY and no model provider;
  * no Historical Replay Case Pack path;
  * no clock inside pure calculation functions;
  * no orchestration (run_risk_scan belongs to G03C) and no UI (G04).
"""

from riskwatch.engine.formulas import (
    ALGORITHM_VERSION,
    FORMULA_VERSION,
    NUMERIC_METHOD,
    RISK_INDEX_SEMANTICS,
    ROUNDING_POLICY,
    RiskFormulaError,
    classify_band,
    classify_direction,
    compute_C,
    compute_D,
    compute_O7,
    round_display,
    validate_index,
)
from riskwatch.engine.static_baseline import (
    DERIVED_SECTION_KEY,
    STATIC_BASELINE_ALGORITHM,
    StaticBaseline,
    StaticBaselineError,
    StaticBaselineValidationError,
    StaticFactorContribution,
    compute_static_baseline,
    derive_static_baseline_section,
    verify_stored_baseline,
)
from riskwatch.engine.core import (
    PointExclusion,
    PointPercentileResult,
    RegionalAggregation,
    RiskWatchInputError,
    RiskWatchResult,
    collect_point_percentile,
    compute_risk_watch,
)
from riskwatch.engine.drivers import (
    RiskDriverContribution,
    build_current_risk_drivers,
    build_outlook_drivers,
    contribution_sum,
    sort_drivers,
    sums_to_index,
)
from riskwatch.engine.comparison import (
    PreviousState,
    build_what_changed,
    load_previous_state,
    previous_state_from_snapshot,
)
from riskwatch.engine.trend import (
    HistoricalTrend,
    TrendEntry,
    query_historical_trend,
)

__all__ = [
    "ALGORITHM_VERSION",
    "FORMULA_VERSION",
    "NUMERIC_METHOD",
    "RISK_INDEX_SEMANTICS",
    "ROUNDING_POLICY",
    "RiskFormulaError",
    "classify_band",
    "classify_direction",
    "compute_C",
    "compute_D",
    "compute_O7",
    "round_display",
    "validate_index",
    "DERIVED_SECTION_KEY",
    "STATIC_BASELINE_ALGORITHM",
    "StaticBaseline",
    "StaticBaselineError",
    "StaticBaselineValidationError",
    "StaticFactorContribution",
    "compute_static_baseline",
    "derive_static_baseline_section",
    "verify_stored_baseline",
    "PointExclusion",
    "PointPercentileResult",
    "RegionalAggregation",
    "RiskWatchInputError",
    "RiskWatchResult",
    "collect_point_percentile",
    "compute_risk_watch",
    "RiskDriverContribution",
    "build_current_risk_drivers",
    "build_outlook_drivers",
    "contribution_sum",
    "sort_drivers",
    "sums_to_index",
    "PreviousState",
    "build_what_changed",
    "load_previous_state",
    "previous_state_from_snapshot",
    "HistoricalTrend",
    "TrendEntry",
    "query_historical_trend",
]
