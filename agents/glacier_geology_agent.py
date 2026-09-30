"""
MountainGuardian v1.0 – Glacier / Geology Agent (G02A).

Frozen design reference: 03_MountainGuardian_AI_Agent_Architecture_v1.0.md
§10 (职责 / 不负责 / 输出结构).

Scope: terrain & relief, cryosphere / source-zone context, channel and
loose-material (geological) susceptibility, historical geological /
chain-hazard context, downstream static exposure — using ONLY authorized
pre-event evidence.

Not responsible for: weather forecasts, computing the final Risk Index,
judging specific event timing, or reading post-event validation data.
"""

from __future__ import annotations

from agents.professional_base import ProfessionalAgent
from orchestration.context_builder import AgentEvidenceView
from schemas.agent_outputs import RiskSignal
from schemas.evidence import AGENT_GLACIER_GEOLOGY

#: evidence types this agent weighs as susceptibility factors
_FACTOR_TYPES = ("cryosphere", "terrain", "geology", "historical_event",
                 "downstream_exposure")


class GlacierGeologyAgent(ProfessionalAgent):
    agent_name = AGENT_GLACIER_GEOLOGY
    prompt_id = "glacier_geology_v1"
    prompt_version = "v1"

    role_description = (
        "你是 MountainGuardian 系统的冰川与地质专业分析员（Glacier / "
        "Geology Agent），只负责基于授权灾前证据的冰川、地形与地质易发性"
        "专业分析。")
    task_description = (
        "本轮唯一任务：基于下方授权证据，分析地形与高差、坡度与峡谷环境、"
        "冰川/冰冻圈背景、高位冰岩环境、沟道与松散物源、历史地质/链式灾害"
        "背景以及下游暴露的静态地理条件，给出专业风险条件判断"
        "（risk_signal 与 key_findings），并显式列出缺失数据与限制。")
    forbidden_claims = (
        "不得给出灾害发生概率或具体发生时间。",
        "不得计算、修改或复述最终 Risk Index（仅由确定性引擎计算）。",
        "不得使用、引用或推测任何灾后（post-event）验证信息。",
        "不得虚构不存在的监测数据、影像观察或文献结论。",
        "不得做出超出授权证据支撑范围的因果断言。",
    )
    extra_scientific_constraints = (
        "confidence 是对当前数据条件下专业判断的信心，不是事件概率。",
        "历史灾害记录只说明背景易发性，不证明未来事件必然发生。",
    )

    # ─── deterministic rule fallback (doc 03 §22.1) ────────────────────────
    def _deterministic_fallback(self, view: AgentEvidenceView) -> dict:
        findings = []
        drivers = []
        cited = []
        factor_types_present = set()
        for item in view.evidence:
            if item.evidence_type in _FACTOR_TYPES:
                factor_types_present.add(item.evidence_type)
                text = f"{item.summary}：{item.value}" \
                    + (f" {item.unit}" if item.unit else "")
                findings.append(f"[规则回退] {text}")
                cited.append(item.evidence_id)
                if item.evidence_type in ("cryosphere", "terrain", "geology"):
                    drivers.append(item.summary)

        n = len(factor_types_present)
        if n >= 4:
            signal = RiskSignal.HIGH.value
        elif n >= 2:
            signal = RiskSignal.ELEVATED.value
        elif n >= 1:
            signal = RiskSignal.MODERATE.value
        else:
            signal = RiskSignal.DATA_LIMITED.value

        missing = [f"{m.summary}（未获得公开数据）" for m in view.missing_sources]
        return {
            "agent": self.agent_name,
            "status": "DEGRADED",
            "risk_signal": signal,
            "confidence": 0.4,
            "key_findings": findings or ["[规则回退] 无授权灾前地质/冰川证据可用。"],
            "evidence_ids": cited,
            "risk_drivers": drivers,
            "missing_data": missing,
            "limitations": [
                "确定性规则回退：仅罗列授权证据中的静态易灾背景因子，"
                "不包含模型专业推理。",
                "灾前动态监测数据（位移/微震等）缺失，无法判断源区实时活动性。",
            ],
        }
