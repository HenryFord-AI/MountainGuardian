"""
MountainGuardian G03C – Risk Watch → G02B contract adapter.

The G02B Risk Synthesizer and Critic consume a deterministic engine result
through a small structural contract (run_id / risk_index / risk_level /
semantics / pack_stated_index / top_drivers(n)). Historical Replay supplies
``HistoricalRiskResult``; Risk Watch supplies the G03B
``riskwatch.engine.RiskWatchResult``.

This module adapts ONE to the OTHER without touching either frozen layer:

  * no formula is reimplemented here — every number is read from the
    immutable G03B result (doc 04 §39: the LLM layer never decides C/O7);
  * ``pack_stated_index`` maps to the SAME authoritative C: in Risk Watch
    the deterministic engine output *is* the official stated value, so the
    Critic's integrity check degenerates to "C equals the official C";
  * the adapter is only ever constructed when the engine produced an
    official Current Risk Index (C is not None). A FAILED deterministic
    result never reaches the AI interpretation layer, so no narrative can
    ever be built on a fabricated index.

``RiskWatchScanRecord`` bundles the deterministic truth layer inputs
(region config, weather result, climatology references, engine result,
data quality) for the Risk Watch Critic's doc 04 §43 programmatic checks.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional

from riskwatch.climatology import ClimatologyReference
from riskwatch.engine.core import RiskWatchResult
from riskwatch.engine.formulas import RISK_INDEX_SEMANTICS, round_display
from riskwatch.region import RegionConfig
from riskwatch.weather import RegionWeatherResult

MODEL_NAME = "risk-watch-engine-v1.0 (G03B deterministic)"
MODEL_TYPE = "deterministic_formula_engine"


class RiskWatchAdapterError(ValueError):
    """The adapter requires a deterministic result with an official C."""


@dataclass(frozen=True)
class RiskWatchEngineAdapter:
    """Structural stand-in for HistoricalRiskResult over a RiskWatchResult.

    Carries ONLY references/values derived from the immutable engine result.
    Mutable narrative layers receive this object read-only; nothing here can
    write back into the deterministic layer.
    """

    watch_result: RiskWatchResult

    # ── fields consumed by the G02B synthesizer / critic contracts ──
    run_id: str
    risk_index: float            # Current Risk Index C (authoritative)
    risk_level: str              # frozen prototype band of C
    pack_stated_index: float     # == C: the engine output IS the official value
    semantics: str = RISK_INDEX_SEMANTICS
    model_name: str = MODEL_NAME
    model_type: str = MODEL_TYPE
    interpretation: str = ""
    factors: tuple = ()          # driver decomposition lives in watch_result

    def __post_init__(self) -> None:
        if self.watch_result.C is None or self.watch_result.current_risk_level is None:
            raise RiskWatchAdapterError(
                "adapter requires an official deterministic Current Risk "
                "Index; a FAILED engine result must never reach the AI "
                "interpretation layer")
        if abs(self.risk_index - self.watch_result.C) > 1e-12:
            raise RiskWatchAdapterError("adapter risk_index must equal engine C")

    # ── deterministic driver view (never recomputed here) ──
    def top_drivers(self, n: int = 3) -> list:
        out = []
        for d in self.watch_result.top_drivers[:n]:
            out.append(
                f"{d.label}（{d.driver_type}，贡献 {d.contribution_points:.2f} "
                f"指数点 = 系数 {d.weight_or_coefficient:.2f} × 原值 "
                f"{d.raw_value:.1f}）"
            )
        return out

    @property
    def outlook_7d_index(self) -> Optional[float]:
        return self.watch_result.O7

    @property
    def outlook_7d_level(self) -> Optional[str]:
        return self.watch_result.outlook_7d_level


def risk_watch_adapter(watch_result: RiskWatchResult) -> RiskWatchEngineAdapter:
    """Build the adapter for a COMPLETED (official) deterministic result."""
    if watch_result.C is None or watch_result.current_risk_level is None:
        raise RiskWatchAdapterError(
            "adapter requires an official deterministic Current Risk Index; "
            "a FAILED engine result must never reach the AI interpretation "
            "layer")
    interpretation = (
        f"Current Risk Index C={round_display(watch_result.C)} 位于原型风险带 "
        f"{watch_result.current_risk_level}；7-Day Outlook O7="
        f"{round_display(watch_result.O7)}（{watch_result.outlook_7d_level}）；"
        f"风险方向 {watch_result.risk_direction}。数值全部由确定性引擎计算，"
        f"AI 层只解释、不修改。"
    )
    return RiskWatchEngineAdapter(
        watch_result=watch_result,
        run_id=watch_result.run_id,
        risk_index=float(watch_result.C),
        risk_level=str(watch_result.current_risk_level),
        pack_stated_index=float(watch_result.C),
        interpretation=interpretation,
    )


@dataclass(frozen=True)
class RiskWatchScanRecord:
    """Deterministic truth-layer bundle for the Risk Watch Critic.

    Everything the doc 04 §43 programmatic checks need to verify data
    integrity, recomputability and provenance — read-only.
    """

    region: RegionConfig
    weather: RegionWeatherResult
    climatologies: Mapping[str, Optional[ClimatologyReference]]
    watch_result: RiskWatchResult
    data_quality: dict

    def to_dict(self) -> dict[str, Any]:
        return {
            "region_id": self.region.region_id,
            "region_config_version": self.region.config_version,
            "weather_status": self.weather.status,
            "weather_retrieval_time": self.weather.retrieval_time,
            "data_quality": dict(self.data_quality),
        }
