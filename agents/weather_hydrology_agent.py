"""
MountainGuardian v1.0 – Weather / Hydrology Agent (G02A).

Frozen design reference: 03_MountainGuardian_AI_Agent_Architecture_v1.0.md
§11 (Historical Replay 职责 / 输出结构).

Historical Replay scope: season / rainy-season background, existing public
meteorological background, and authorized hydrological background ONLY.
When historical real-time weather/hydrology data is insufficient the agent
must explicitly output Data Limited — it must NEVER backfill with
post-event weather information, and climate context (ENSO) may never be
packaged as direct event causation.

Risk Watch responsibilities (§11.2) are out of G02A scope.
"""

from __future__ import annotations

from agents.professional_base import ProfessionalAgent
from orchestration.context_builder import AgentEvidenceView
from schemas.agent_outputs import RiskSignal
from schemas.evidence import AGENT_WEATHER_HYDROLOGY

_CONTEXT_TYPES = ("weather_context", "climate_context")


class WeatherHydrologyAgent(ProfessionalAgent):
    agent_name = AGENT_WEATHER_HYDROLOGY
    prompt_id = "weather_hydrology_v1"
    prompt_version = "v1"

    role_description = (
        "你是 MountainGuardian 系统的气象与水文专业分析员（Weather / "
        "Hydrology Agent），只负责基于授权灾前证据的气象/气候背景与水文"
        "背景专业分析。")
    task_description = (
        "本轮唯一任务（Historical Replay）：基于下方授权证据，分析季节与"
        "雨季背景、已存在的公开气象/气候背景，以及可获得的水文背景信息；"
        "如果历史实时气象或水文数据不足，必须在 missing_data 中显式声明 "
        "Data Limited，并如实降低 confidence。输出专业背景判断，"
        "不下结论说某次天气过程必然触发了灾害。")
    forbidden_claims = (
        "不得给出灾害发生概率。",
        "不得把 ENSO / 厄尔尼诺等气候背景包装为本次具体事件的直接触发因果。",
        "不得用灾后天气信息补齐灾前分析。",
        "不得虚构实时气象观测、雷达、水文站数据。",
        "不得计算或修改最终 Risk Index。",
    )
    extra_scientific_constraints = (
        "雨季/降水背景只能提高易灾背景认识，不能作为具体事件的触发判定。",
        "水文数据缺失时，必须显式输出 Data Limited，而不是推测。",
    )

    # ─── deterministic rule fallback (doc 03 §22.1) ────────────────────────
    def _deterministic_fallback(self, view: AgentEvidenceView) -> dict:
        conditions = []
        cited = []
        has_weather_context = False
        for item in list(view.evidence) + list(view.background_evidence):
            if item.evidence_type in _CONTEXT_TYPES:
                text = f"{item.summary}：{item.value}" \
                    + (f" {item.unit}" if item.unit else "")
                tag = "（背景，非因果）" if item.is_context_only() else ""
                conditions.append(f"[规则回退] {text}{tag}")
                cited.append(item.evidence_id)
                if item.evidence_type == "weather_context":
                    has_weather_context = True

        signal = (RiskSignal.ELEVATED.value if has_weather_context
                  else RiskSignal.DATA_LIMITED.value)
        missing = [f"{m.summary}（未获得公开数据）" for m in view.missing_sources]
        if not any("水文" in m for m in missing):
            missing.append("灾前实时水文/水位观测数据（未获得公开数据，Data Limited）")
        return {
            "agent": self.agent_name,
            "status": "DEGRADED",
            "risk_signal": signal,
            "confidence": 0.35,
            "key_findings": conditions or [
                "[规则回退] 无授权灾前气象/水文证据可用，Data Limited。"],
            "evidence_ids": cited,
            "recent_conditions": conditions,
            "forecast_signals": [],
            "missing_data": missing,
            "limitations": [
                "确定性规则回退：仅罗列授权灾前气象/气候背景，"
                "不包含模型专业推理。",
                "气候背景（含 ENSO）不构成具体事件直接因果。",
                "Historical Replay 无实时预报数据，forecast_signals 为空。",
            ],
        }
