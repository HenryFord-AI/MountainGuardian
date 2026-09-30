"""
MountainGuardian G03B – frozen v1.0 Risk Watch formula constants and pure
classifiers.

Everything in this module is deterministic, side-effect free and offline:
no clock, no network, no LLM, no mutable state.

Frozen definitions (doc 04 §13–§18, battle plan §16):

    B  = Regional Static Susceptibility Baseline   (static_baseline.py)
    R  = Recent 7-Day Precipitation Percentile     (regional conservative max)
    F  = Forecast 7-Day Precipitation Percentile   (regional conservative max)
    D  = 0.60 x R + 0.40 x F                       (Dynamic Trigger Index)
    C  = 0.70 x B + 0.30 x D                       (Current Risk Index)
    O7 = 0.70 x B + 0.30 x F                       (7-Day Outlook Index)

All indices are logically bounded to 0–100. None of them is a disaster
probability, an occurrence forecast or a statutory warning level.

The weight constants below are the ONLY authorized v1.0 formula weights.
Configuration must never silently override them; the explicit
``FORMULA_VERSION`` identifies the frozen set for auditability.
"""

from __future__ import annotations

import math

#: Explicit version of the whole deterministic engine (result objects carry it).
ALGORITHM_VERSION = "risk-watch-engine-v1.0"

#: Explicit version of the frozen formula constant set (doc 04 §13–§18).
FORMULA_VERSION = "risk-watch-formulas-v1.0-frozen-doc04"

# --- frozen formula weights (doc 04 §14/§15/§17) ---------------------------
# D = 0.60 x R + 0.40 x F
WEIGHT_RECENT_IN_D = 0.60
WEIGHT_FORECAST_IN_D = 0.40
# C = 0.70 x B + 0.30 x D
WEIGHT_STATIC_IN_C = 0.70
WEIGHT_DYNAMIC_IN_C = 0.30
# O7 = 0.70 x B + 0.30 x F
WEIGHT_STATIC_IN_O7 = 0.70
WEIGHT_FORECAST_IN_O7 = 0.30

# Exact decomposed contributions of the dynamic terms to C:
#   recent  -> 0.30 x 0.60 = 0.18 x R
#   forecast-> 0.30 x 0.40 = 0.12 x F
WEIGHT_RECENT_IN_C = WEIGHT_DYNAMIC_IN_C * WEIGHT_RECENT_IN_D
WEIGHT_FORECAST_IN_C = WEIGHT_DYNAMIC_IN_C * WEIGHT_FORECAST_IN_D

# --- logical index bounds ---------------------------------------------------
INDEX_MIN = 0.0
INDEX_MAX = 100.0
#: Tolerance used only to absorb float representation noise at the hard
#: bounds; values outside [INDEX_MIN - tol, INDEX_MAX + tol] are rejected.
BOUNDARY_TOLERANCE = 1e-9

# --- prototype risk bands (doc 04 §16) --------------------------------------
# Half-open intervals: 0 <= x < 40 LOW, 40 <= x < 60 MODERATE,
# 60 <= x < 80 ELEVATED, 80 <= x <= 100 HIGH.
# These are PROTOTYPE bands, never statutory Chinese warning-color terms.
BAND_LOW = "LOW"
BAND_MODERATE = "MODERATE"
BAND_ELEVATED = "ELEVATED"
BAND_HIGH = "HIGH"

# --- risk direction (doc 04 §18) ---------------------------------------------
DIRECTION_RISING = "RISING"
DIRECTION_STABLE = "STABLE"
DIRECTION_FALLING = "FALLING"
DIRECTION_NO_HISTORY = "NO_HISTORY"
#: Product readability threshold in index points; NOT statistical significance.
DIRECTION_THRESHOLD_POINTS = 5.0

# --- frozen result statuses (doc 04 §29/§36/§37) -----------------------------
STATUS_COMPLETED = "COMPLETED"
STATUS_COMPLETED_WITH_LIMITATIONS = "COMPLETED_WITH_LIMITATIONS"
STATUS_FAILED = "FAILED"
#: Snapshot statuses that count as valid official Risk Watch results.
VALID_RESULT_STATUSES = (STATUS_COMPLETED, STATUS_COMPLETED_WITH_LIMITATIONS)

# --- What Changed precipitation direction vocabulary -------------------------
CHANGE_UP = "UP"
CHANGE_DOWN = "DOWN"
CHANGE_UNCHANGED = "UNCHANGED"
CHANGE_NOT_COMPARABLE = "NOT_COMPARABLE"

# --- display rounding policy --------------------------------------------------
DISPLAY_DECIMALS = 2
ROUNDING_POLICY = (
    "All internal calculations use full IEEE-754 double precision; no "
    "intermediate value is rounded before subsequent calculations. "
    "Serialized/display values are rounded consistently to 2 decimal places; "
    "the raw unrounded values are preserved alongside them. Risk-band "
    "classification and all comparisons always use the unrounded values."
)

NUMERIC_METHOD = {
    "precision_policy": ROUNDING_POLICY,
    "display_rounding_decimals": DISPLAY_DECIMALS,
    "percentile_method": (
        "mean_rank (G03A riskwatch.climatology.percentile_of: "
        "100 * (below + 0.5 * equal) / n over the full stored monthly "
        "1991-2020 rolling 7-day distribution)"
    ),
    "climatology_month_assignment": (
        "window_end_month (frozen G03A methodology: a 7-day window belongs "
        "to the natural month of its END date; no second cross-month rule "
        "exists)"
    ),
    "regional_aggregation": (
        "conservative maximum percentile over successful eligible monitoring "
        "points (doc 04 §11); Source Zone and Port Zone are never averaged"
    ),
    "driver_point_tie_break": (
        "first point attaining the maximum in region.json monitoring_points "
        "order"
    ),
    "index_bounds": (INDEX_MIN, INDEX_MAX),
    "direction_threshold_points": DIRECTION_THRESHOLD_POINTS,
}

#: Frozen semantics statement — must accompany the indices everywhere.
RISK_INDEX_SEMANTICS = (
    "B/R/F/D/C/O7 are transparent, reproducible prototype heuristic risk "
    "indices (0-100) produced by a deterministic engine. The Current Risk "
    "Index C is a risk-state indicator: it is NOT a disaster occurrence "
    "probability, NOT an official warning level and NOT a prediction of event "
    "timing. O7 states which risk background the region may occupy IF the "
    "current 7-day forecast materializes; it is NOT a future disaster "
    "probability. Risk bands are prototype bands only."
)


class RiskFormulaError(ValueError):
    """A formula input/output violates the frozen 0–100 contract."""


def validate_index(value: float, name: str = "index") -> float:
    """Enforce the logical 0–100 bound on a numeric index.

    Rejects NaN/±inf and anything outside [0, 100] beyond float-noise
    tolerance; clamps representation noise at the hard bounds.
    """
    try:
        v = float(value)
    except (TypeError, ValueError) as exc:
        raise RiskFormulaError(f"{name}: non-numeric index value {value!r}") from exc
    if not math.isfinite(v):
        raise RiskFormulaError(f"{name}: non-finite index value {v!r}")
    if v < INDEX_MIN - BOUNDARY_TOLERANCE or v > INDEX_MAX + BOUNDARY_TOLERANCE:
        raise RiskFormulaError(
            f"{name}: value {v!r} outside frozen 0-100 bounds"
        )
    return min(max(v, INDEX_MIN), INDEX_MAX)


def classify_band(value: float, name: str = "index") -> str:
    """Map a full-precision 0–100 index onto the frozen prototype bands.

    Classification ALWAYS uses the actual calculated value, never a
    prematurely rounded display value.
    """
    v = validate_index(value, name)
    if v < 40.0:
        return BAND_LOW
    if v < 60.0:
        return BAND_MODERATE
    if v < 80.0:
        return BAND_ELEVATED
    return BAND_HIGH


def compute_D(R: float, F: float) -> float:
    """Frozen Dynamic Trigger Index: D = 0.60 x R + 0.40 x F."""
    r = validate_index(R, "R")
    f = validate_index(F, "F")
    return validate_index(WEIGHT_RECENT_IN_D * r + WEIGHT_FORECAST_IN_D * f, "D")


def compute_C(B: float, D: float) -> float:
    """Frozen Current Risk Index: C = 0.70 x B + 0.30 x D."""
    b = validate_index(B, "B")
    d = validate_index(D, "D")
    return validate_index(WEIGHT_STATIC_IN_C * b + WEIGHT_DYNAMIC_IN_C * d, "C")


def compute_O7(B: float, F: float) -> float:
    """Frozen 7-Day Outlook Index: O7 = 0.70 x B + 0.30 x F."""
    b = validate_index(B, "B")
    f = validate_index(F, "F")
    return validate_index(
        WEIGHT_STATIC_IN_O7 * b + WEIGHT_FORECAST_IN_O7 * f, "O7"
    )


def classify_direction(delta_c: float) -> str:
    """Frozen Risk Direction rule (doc 04 §18).

    delta >= +5 -> RISING; delta <= -5 -> FALLING; otherwise STABLE.
    Exactly +5 is RISING and exactly -5 is FALLING. This is a product
    readability threshold, not a statistical significance test.
    """
    try:
        d = float(delta_c)
    except (TypeError, ValueError) as exc:
        raise RiskFormulaError(f"delta_C: non-numeric value {delta_c!r}") from exc
    if not math.isfinite(d):
        raise RiskFormulaError(f"delta_C: non-finite value {d!r}")
    if d >= DIRECTION_THRESHOLD_POINTS:
        return DIRECTION_RISING
    if d <= -DIRECTION_THRESHOLD_POINTS:
        return DIRECTION_FALLING
    return DIRECTION_STABLE


def round_display(value: float | None, decimals: int = DISPLAY_DECIMALS) -> float | None:
    """Consistent display rounding; never used for classification."""
    if value is None:
        return None
    return round(float(value), decimals)
