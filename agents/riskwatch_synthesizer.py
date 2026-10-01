"""
MountainGuardian G03C – Risk Watch Risk Synthesizer.

Thin specialization of the frozen G02B ``RiskSynthesizer``. EVERYTHING
structural is inherited unchanged:

  * one bounded provider call, schema + scientific output validation
    (the model must ECHO the deterministic C / band — deviation is rejected
    by ``make_synthesis_validator`` and re-imposed in code);
  * deterministic agreement / coverage / missing-data runtime computation;
  * explicit rule-based fallback (fallback_used=True, is_model_output=False)
    whenever the model is unavailable — never disguised as AI output;
  * injection quarantine on untrusted narrative text.

Only the Risk Watch narrative surface is specialized (doc 04 §39-§42,
gate G03C §12):

  * prompts speak B / R / F / D / C / O7 (G03B vocabulary), never the
    Historical Replay six-factor model;
  * the fallback payload is a deterministic Risk Watch summary;
  * every synthesis result carries the explicit statement that the Risk
    Index is NOT a probability, appended by the runtime (model-independent).

The synthesizer NEVER modifies C / O7 / Risk Level: it receives the
read-only ``RiskWatchEngineAdapter`` and its authoritative numbers are
copied from it, exactly as in G02B.
"""

from __future__ import annotations

from agents.risk_synthesizer import (
    _DATA_BLOCK_END,
    _DATA_BLOCK_START,
    RiskSynthesizer,
)
from orchestration.context_builder import AnalysisContext
from orchestration.risk_watch_adapter import RiskWatchEngineAdapter
from riskwatch.engine.formulas import round_display

#: Runtime-appended, model-independent semantics statement (gate G03C §12:
#: the synthesis MUST explicitly state the Risk Index is not a probability).
#: Wording keeps the deterministic C adjacent to the "Risk Index" label so
#: the Critic's SCORE_INTEGRITY narrative scan always sees the true value.
def _semantics_note(adapter: RiskWatchEngineAdapter) -> str:
    w = adapter.watch_result
    return (
        f"Risk Index C={round_display(w.C)}（{w.current_risk_level} 原型风险带）"
        f"与 7-Day Outlook O7={round_display(w.O7)} 是确定性风险状态指标，"
        f"不是灾害发生概率，不是官方预警等级，也不指示事件发生时刻。"
    )


class RiskWatchSynthesizer(RiskSynthesizer):
    """Explains the G03B deterministic Risk Watch result + agent outputs."""

    prompt_id = "risk_watch_synthesizer_v1"
    prompt_version = "v1"

    ROLE = ("你是 MountainGuardian 系统的风险综合员（Risk Synthesizer），"
            "负责把三个独立专业 Agent 的结构化结论与确定性 Risk Watch 引擎"
            "（B/R/F/D/C/O7）结果综合成一份可审计的当前风险解释。"
            "你不是风险计算器。")
    TASK = ("本轮唯一任务（Risk Watch 实时扫描）：基于下方提供的确定性 Risk "
            "Watch 引擎结果（静态基线 B、近期/预报降水百分位 R/F、动态触发"
            "指数 D、当前风险指数 C、7 天展望 O7、风险带与风险方向）与专业 "
            "Agent 输出，解释当前风险状态的成因，按可追溯贡献排序主要风险"
            "驱动因素，说明 Agent 之间的一致与分歧、证据覆盖、缺失数据与"
            "限制条件，并如实转述与上一次快照相比的变化（What Changed）。"
            "risk_index 必须原样照抄确定性引擎给出的 C 数值，risk_level 必须"
            "原样照抄 C 的风险带，不得修改、重算或重新解释为概率。")
    FORBIDDEN = RiskSynthesizer.FORBIDDEN + (
        "不得修改、重算或覆盖 B/R/F/D/O7 中的任何数值。",
        "不得把 7-Day Outlook（O7）表述为未来灾害必然发生或发生概率。",
        "不得声称系统能够预测具体灾害发生时刻（无源区实时监测数据）。",
        "不得把网格化模型天气表述为现场实测。",
    )

    # ─── Risk Watch prompt surface ─────────────────────────────────────────
    def _risk_watch_block(self, adapter: RiskWatchEngineAdapter) -> str:
        w = adapter.watch_result
        d = w.to_dict()
        disp = d["display"]
        lines = [
            "## 确定性 Risk Watch 引擎结果（权威数值，只能照抄，不得修改）",
            f"engine={d['algorithm_version']} status={d['status']}",
            f"B  静态易灾基线 = {disp['B']}（region.json 五因子推导，"
            f"config {d['provenance']['region_config_version']}）",
            f"R  近7天降水百分位（区域保守最大） = {disp['R']}"
            f"（驱动点 {d['R_driver_point']}）",
            f"F  未来7天预报降水百分位（区域保守最大） = {disp['F']}"
            f"（驱动点 {d['F_driver_point']}）",
            f"D  动态触发指数 = {disp['D']}（D = 0.60×R + 0.40×F，冻结公式）",
            f"C  当前风险指数 = {disp['C']}（C = 0.70×B + 0.30×D，冻结公式）",
            f"risk_level = {d['current_risk_level']}（原型风险带）",
            f"O7 7天展望指数 = {disp['O7']}（O7 = 0.70×B + 0.30×F，冻结公式）",
            f"outlook_7d_level = {d['outlook_7d_level']}",
            f"risk_direction = {d['risk_direction']}"
            f"（previous_C={d['previous_C']}, delta_C={d['delta_C']}，"
            f"±5 指数点冻结规则）",
            f"what_changed = {d['what_changed'].get('status', '')}",
            f"语义：{d['semantics']}",
            "主要驱动因素（贡献可追溯，合计等于 C）：",
        ]
        for drv in d["top_drivers"][:7]:
            lines.append(
                f"- {drv['label']}（{drv['driver_type']}）：贡献 "
                f"{drv['contribution_points_rounded']} 指数点 = 系数 "
                f"{drv['weight_or_coefficient']:.2f} × 原值 "
                f"{drv['raw_value']:.1f}"
                + (f"，监测点 {drv['monitoring_point_id']}"
                   if drv.get("monitoring_point_id") else "")
            )
        if d["limitations"]:
            lines.append("引擎限制条件（必须如实转述）：")
            lines.extend(f"- {l}" for l in d["limitations"][:10])
        return "\n".join(lines)

    def build_prompts(self, agent_results: dict,
                      risk_result: RiskWatchEngineAdapter,
                      context: AnalysisContext,
                      runtime: dict) -> tuple:
        """Return (system_prompt, user_prompt) — Risk Watch wording only."""
        constraints = list(getattr(context, "scientific_constraints", []))
        system_parts = [
            f"【角色】{self.ROLE}",
            f"【任务】{self.TASK}",
            "【禁止】" + "\n".join(f"- {c}" for c in self.FORBIDDEN),
            "【科学约束】" + "\n".join(f"- {c}" for c in constraints),
            "【证据要求】evidence_ids 只能引用下方专业 Agent 已引用或系统"
            "授权的 Evidence ID；不得虚构。",
            "【输出】只返回一个符合给定 JSON Schema 的 JSON 对象。"
            "explanation_confidence 是你对本次解释的信心（0-1），"
            "不是灾害发生概率。summary 或 risk_explanation 中必须明确说明"
            "风险指数不是灾害发生概率。输出必须简洁：summary ≤ 200 字，"
            "risk_explanation ≤ 500 字，top_drivers ≤ 5 条（每条 ≤ 60 字），"
            "数组每条 ≤ 100 字，evidence_ids ≤ 10 个。",
        ]
        system_prompt = "\n\n".join(system_parts)

        meta = context.case_metadata
        risk_block = self._risk_watch_block(risk_result)
        agent_blocks = "\n\n".join(
            self._agent_block(name, res)
            for name, res in sorted(agent_results.items()))
        runtime_block = (
            "## 运行时确定性统计（照抄进输出，不得改写）\n"
            f"agent_agreement={runtime['agreement']}\n"
            f"evidence_coverage={runtime['coverage']}\n"
            + ("分歧说明：\n" + "\n".join(
                f"- {x}" for x in runtime["disagreements"])
               if runtime["disagreements"] else "")
            + ("\n未参与投票的 Agent（缺席≠分歧，必须如实说明）：\n"
               + "\n".join(f"- {a}" for a in runtime["absent"])
               if runtime["absent"] else "")
            + "\n缺失数据（必须在 missing_data 中如实反映）：\n"
            + "\n".join(f"- {m[:200]}"
                        for m in runtime["missing_data"][:20]))

        user_prompt = (
            f"扫描：{meta.get('case_name', '')}\n"
            f"区域：{meta.get('location', '')}"
            f"（参考坐标 {meta.get('lat', '')}, {meta.get('lon', '')}）\n"
            f"分析模式：{context.mode}（Risk Watch 实时运行扫描，"
            f"无历史灾害 Case Pack 输入）\n"
            f"天气检索时间：{meta.get('retrieval_time', '')}\n\n"
            f"{_DATA_BLOCK_START}\n{risk_block}\n\n"
            f"## 专业 Agent 输出（相互独立，仅由你汇总）\n{agent_blocks}\n\n"
            f"{runtime_block}\n{_DATA_BLOCK_END}\n\n"
            "请输出规定的 JSON 对象：解释当前确定性风险指数 C 与 7 天展望 "
            "O7、按贡献排序 top_drivers、如实反映 agent_agreement / "
            "disagreements / evidence_coverage / missing_data / limitations，"
            "risk_index 与 risk_level 原样照抄 C 与其风险带，并明确说明"
            "风险指数不是灾害发生概率。")
        return system_prompt, user_prompt

    # ─── deterministic Risk Watch fallback (doc 03 §22.1, doc 04 §38) ──────
    def _fallback_payload(self, agent_results: dict,
                          risk_result: RiskWatchEngineAdapter,
                          runtime: dict) -> dict:
        w = risk_result.watch_result
        d = w.to_dict()
        disp = d["display"]
        cited: list = []
        for res in agent_results.values():
            for eid in res.evidence_ids:
                if eid not in cited:
                    cited.append(eid)
        explanation = (
            f"[规则回退] 确定性 Risk Watch 引擎结果：B={disp['B']}，"
            f"R={disp['R']}，F={disp['F']}，D={disp['D']}（D=0.60×R+0.40×F），"
            f"Current Risk Index C={disp['C']} / 100"
            f"（{w.current_risk_level} 原型风险带，C=0.70×B+0.30×D），"
            f"7-Day Outlook O7={disp['O7']}（{w.outlook_7d_level}，"
            f"O7=0.70×B+0.30×F），风险方向 {w.risk_direction}。"
            f"主要驱动：{'；'.join(risk_result.top_drivers(3))}。"
            f"该指数不是灾害发生概率。"
        )
        return {
            "risk_index": risk_result.risk_index,
            "risk_level": risk_result.risk_level,
            "summary": (f"[规则回退] 当前风险指数 C={disp['C']} / 100"
                        f"（{w.current_risk_level}），7 天展望 O7="
                        f"{disp['O7']}（{w.outlook_7d_level}）。模型综合不可用，"
                        "本结果为确定性规则汇总，不是 AI 分析。"
                        "风险指数不是灾害发生概率。"),
            "risk_explanation": explanation,
            "top_drivers": risk_result.top_drivers(3),
            "agent_agreement": runtime["agreement"],
            "disagreements": list(runtime["disagreements"]),
            "evidence_coverage": runtime["coverage"],
            "missing_data": list(runtime["missing_data"]),
            "limitations": [
                "确定性规则回退结果，不是模型综合输出（模型调用失败或不可用）。",
                "缺少源区实时动态监测数据（位移/微震等），无法判断具体发生时刻。",
            ] + list(runtime.get("absent", [])) + list(w.limitations)[:6],
            "explanation_confidence": 0.0,
            "evidence_ids": cited[:30],
        }

    # ─── runtime-appended semantics guarantee ───────────────────────────────
    def _result_from_payload(self, payload: dict, agent_results: dict,
                             risk_result: RiskWatchEngineAdapter,
                             runtime: dict, **kwargs):
        result = super()._result_from_payload(
            payload, agent_results, risk_result, runtime, **kwargs)
        note = _semantics_note(risk_result)
        if note not in result.limitations:
            result.limitations = list(result.limitations) + [note]
        return result

    # ─── Risk Watch missing-data wording (no replay-specific phrasing) ─────
    @staticmethod
    def collect_missing_data(agent_results: dict,
                             context: AnalysisContext) -> list:
        seen, out = set(), []
        for res in agent_results.values():
            for m in res.missing_data:
                if m not in seen:
                    seen.add(m)
                    out.append(m)
        for item in getattr(context, "missing_sources", []):
            text = f"{item.summary}（该数据源当前不可用）"
            if text not in seen:
                seen.add(text)
                out.append(text)
        return out
