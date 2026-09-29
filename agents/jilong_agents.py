"""
MountainGuardian – Jilong competition agents (rule-based, demo-mode safe).

Four lightweight agents on top of the existing BaseAgent machinery:
  1. IntelligenceAgent  – pre-event environment briefing
  2. RiskAnalysisAgent  – frozen demo risk model re-computation (NO LLM)
  3. CheckerAgent       – scientific-integrity rule checks (NO LLM)
  4. WarningAgent       – Chinese risk advisory + mandatory disclaimer

Hard rule: none of these agents may read post_event_validation except
CheckerAgent, which receives it explicitly from the Coordinator.
"""

import logging
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from agents.base_agent import BaseAgent, AgentResponse
from tools.case_loader import PRE_EVENT_PHASES

logger = logging.getLogger(__name__)

DISCLAIMER = ("本结果为历史案例回放和科技比赛实验，不属于官方灾害预警，"
              "也不能证明系统提前预测出了8·26灾害。")


def _fields_map(case_data: list) -> dict:
    return {f["key"]: f for f in (case_data or [])}


# ══════════════════════════════════════════════════════════════════════════════
# 1. 情报员 Agent
# ══════════════════════════════════════════════════════════════════════════════
class IntelligenceAgent(BaseAgent):
    """Summarizes pre-event static/context/evidence factors only."""

    def __init__(self):
        super().__init__("情报员 Agent", use_flash=True)

    def _execute(self, context: dict) -> AgentResponse:
        fm = _fields_map(context.get("case_data"))
        if not fm:
            return AgentResponse(agent_name=self.agent_name, action="intelligence",
                                 success=False, error="case_data missing",
                                 recommendation="案例数据缺失，无法生成环境情报。")

        def v(key, default=""):
            return fm[key]["value"] if key in fm else default

        lines = [
            f"✓ 高海拔冰川/冰岩源区（源区海拔约{v('source_elevation_m')}m，存在高位悬冰川）",
            f"✓ 地形高差大、沟谷陡峭（{v('terrain_class')}，垂直高差约{v('vertical_drop_m')}m）",
            f"✓ 沟道存在松散物源（{v('loose_material_supply')}）",
            f"✓ 历史上发生过类似链式灾害（{v('prior_event_date')}：{v('prior_event_type')}）",
            f"✓ 季风与高降水背景（年均约{v('annual_precip_mm')}mm，雨季{v('rainy_season')}）",
            f"✓ 下游存在口岸与基础设施暴露（{v('location')}，口岸海拔约{v('port_elevation_m')}m）",
        ]
        missing_note = "⚠ 公开资料缺少灾前源区实时位移/微震等动态传感数据"

        return AgentResponse(
            agent_name=self.agent_name,
            action="environment_intelligence",
            success=True,
            content={"summary_lines": lines, "missing": [missing_note],
                     "factor_count": len(lines)},
            recommendation="环境情报摘要\n" + "\n".join(lines) + "\n" + missing_note,
            reason="仅使用灾前静态/背景/遥感元数据字段整理，未使用任何灾后验证信息。",
            data_sources=["S03", "S04", "S05"],
            confidence=0.85,
            risk_level="high",
            alternatives=["补充源区实时传感数据后复核", "结合更高分辨率DEM复核沟谷参数"],
        )


# ══════════════════════════════════════════════════════════════════════════════
# 2. 风险分析员 Agent
# ══════════════════════════════════════════════════════════════════════════════
class RiskAnalysisAgent(BaseAgent):
    """Re-computes the frozen demo risk model. No LLM, no probability claims."""

    def __init__(self):
        super().__init__("风险分析员 Agent", use_flash=True)

    def _execute(self, context: dict) -> AgentResponse:
        model = context.get("risk_model")
        if not model:
            return AgentResponse(agent_name=self.agent_name, action="risk_analysis",
                                 success=False, error="risk_model missing",
                                 recommendation="风险模型缺失。")
        factors = model.get("factors", [])
        contributions = []
        for f in factors:
            contrib = round(f["weight_pct"] * f["score_0_to_5"] / 5.0, 1)
            contributions.append({
                "id": f["id"], "name": f["name"],
                "weight_pct": f["weight_pct"], "score": f["score_0_to_5"],
                "contribution": contrib, "evidence": f["evidence"],
                "source_ids": f["source_ids"],
            })
        weight_sum = sum(f["weight_pct"] for f in factors)
        index = round(sum(c["contribution"] for c in contributions), 1)

        if index >= 75:
            level = "高风险背景"
        elif index >= 50:
            level = "中风险背景"
        else:
            level = "低风险背景"

        return AgentResponse(
            agent_name=self.agent_name,
            action="risk_index",
            success=True,
            content={
                "risk_index": index,
                "pack_stated_index": model.get("calculated_index_0_to_100"),
                "weight_sum": weight_sum,
                "risk_level_label": level,
                "contributions": contributions,
                "semantics": "基础易灾风险指数（0-100），不是灾害发生概率",
            },
            recommendation=f"基础易灾风险指数：{index:.0f} / 100（{level}）。该指数不是发生概率。",
            reason="按 Case Pack 冻结公式 Σ(权重×评分)/5 复算六个灾前因子，未使用灾后字段。",
            data_sources=["S03", "S04", "S05", "S01"],
            confidence=0.85,
            risk_level="high",
            alternatives=["引入源区实时监测数据后可做动态风险更新（本Demo未实现）"],
        )


# ══════════════════════════════════════════════════════════════════════════════
# 3. 检查员 Agent
# ══════════════════════════════════════════════════════════════════════════════
class CheckerAgent(BaseAgent):
    """Rule-only scientific-integrity checks. The only agent allowed to see
    post_event_validation (supplied by the Coordinator as context['post_event'])."""

    def __init__(self):
        super().__init__("检查员 Agent", use_flash=True)

    def _execute(self, context: dict) -> AgentResponse:
        checks = []
        prior = {r["agent"]: r for r in context.get("prior_results", [])}
        risk = prior.get("风险分析员 Agent", {}).get("content", {})
        case_data = context.get("case_data", [])
        post_event = context.get("post_event", [])

        # 1. leakage: any post_event phase inside Risk/Intelligence inputs
        leaked = [f["id"] for f in case_data if f.get("phase") not in PRE_EVENT_PHASES]
        checks.append(("Risk输入灾前/灾后隔离",
                       "PASS" if not leaked else f"FAIL:{leaked}",
                       "风险分析员输入全部为灾前phase字段" if not leaked else "发现灾后字段混入"))

        # 2. index range
        idx = risk.get("risk_index")
        ok = idx is not None and 0 <= idx <= 100
        checks.append(("风险指数0-100范围", "PASS" if ok else "FAIL", f"risk_index={idx}"))

        # 3. weights sum
        ws = risk.get("weight_sum")
        ok = ws == 100
        checks.append(("因子权重合计100", "PASS" if ok else "FAIL", f"权重合计={ws}"))

        # 4. at least two independent factors
        n = len(risk.get("contributions", []))
        ok = n >= 2
        checks.append(("至少两个独立风险因素", "PASS" if ok else "FAIL", f"因子数={n}"))

        # 5. index not presented as probability
        text = str(risk.get("semantics", "")) + str(prior.get("风险分析员 Agent", {}).get("recommendation", ""))
        ok = ("不是" in text or "非" in text) and "概率91" not in text.replace(" ", "")
        checks.append(("风险指数未被当作概率", "PASS" if ok else "FAIL",
                       "输出明确标注“不是灾害发生概率”"))

        # 6. missing pre-event dynamic sensor data must be declared
        missing_declared = any("传感" in u or "动态" in u for u in context.get("usage_limits", []))
        checks.append(("灾前动态监测数据缺口声明",
                       "PASS" if missing_declared else "FAIL",
                       "缺少灾前实时源区动态传感数据，因此无法对8·26事件的具体发生时刻进行可靠提前预测。"))

        failed = [c for c in checks if c[1].startswith("FAIL")]
        verdict = "FAIL" if failed else "PASS WITH LIMITATIONS"

        return AgentResponse(
            agent_name=self.agent_name,
            action="integrity_check",
            success=True,
            content={"checks": [{"name": n_, "status": s, "detail": d} for n_, s, d in checks],
                     "verdict": verdict,
                     "limitation": ("缺少灾前实时源区动态传感数据，因此无法对8·26事件的"
                                    "具体发生时刻进行可靠提前预测。"),
                     "post_event_fields_seen": len(post_event)},
            recommendation=f"检查结论：{verdict}。" + ("；".join(c[0] for c in failed) if failed else
                          "结构检查全部通过，但因缺少灾前动态前兆数据，结论带限制条件。"),
            reason="对风险输入隔离、指数范围、权重、因子数、概率表述与数据缺口做规则检查。",
            data_sources=["S06", "S07"],
            confidence=0.9,
            risk_level="moderate",
            alternatives=["接入真实源区监测数据后可移除限制条件"],
        )


# ══════════════════════════════════════════════════════════════════════════════
# 4. 预警员 Agent
# ══════════════════════════════════════════════════════════════════════════════
class WarningAgent(BaseAgent):
    """Turns risk result + checker verdict into a plain-Chinese advisory."""

    def __init__(self):
        super().__init__("预警员 Agent", use_flash=True)

    def _execute(self, context: dict) -> AgentResponse:
        prior = {r["agent"]: r for r in context.get("prior_results", [])}
        risk = prior.get("风险分析员 Agent", {}).get("content", {})
        check = prior.get("检查员 Agent", {}).get("content", {})
        location = context.get("location", "西藏日喀则市吉隆县吉隆口岸区域")

        idx = risk.get("risk_index", 0)
        level = risk.get("risk_level_label", "高风险背景")
        reasons = [c["name"] for c in risk.get("contributions", [])]
        advice = ("加强冰川源区、沟道和河流水位监测，关注异常位移、震动和水位变化；"
                  "雨季期间保持对高位冰崩—碎屑流—泥石流链式灾害的警惕。")

        advisory = (
            f"AI风险提示\n地点：{location}\n"
            f"基础易灾风险指数：{idx:.0f} / 100\n风险背景：{level.replace('风险背景', '')}\n"
            "主要原因：\n" + "\n".join(f"• {r}" for r in reasons) + "\n"
            f"建议：{advice}"
        )

        return AgentResponse(
            agent_name=self.agent_name,
            action="risk_advisory",
            success=True,
            content={"advisory": advisory, "disclaimer": DISCLAIMER,
                     "checker_verdict": check.get("verdict", "N/A"),
                     "risk_index": idx, "risk_level_label": level,
                     "main_reasons": reasons},
            recommendation=advisory,
            reason="将风险指数、主要因子与检查结论转写为通俗中文提示，并附强制免责声明。",
            data_sources=["case.json 风险模型", "检查员结论"],
            confidence=0.85,
            risk_level="high",
            alternatives=["由专业部门发布正式预警（本系统不提供）"],
        )
