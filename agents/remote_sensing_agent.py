"""
MountainGuardian v1.0 – Remote Sensing Agent (G02A).

Frozen design references:
  - 03_MountainGuardian_AI_Agent_Architecture_v1.0.md §12 (Historical
    Replay: pre-event imagery only; no usable imagery → SKIPPED, never
    fabricated; §12.3 AI Visual Observation must be distinguished from
    official/algorithmic conclusions; §12.4 output structure)
  - 02_MountainGuardian_Scientific_Data_Baseline_v1.0.md §15.1 (pre-event
    Sentinel-2 as baseline; post-event scenes are validation only)

Hard rules implemented here:
  * Historical Replay risk analysis may ONLY use authorized pre-event
    imagery (phase pre_event_evidence AND observation date strictly before
    the public event date).
  * Post-event imagery can never be substituted — it is excluded by the
    context builder, re-excluded by the agent view, and re-checked here
    before any provider call.
  * No usable authorized image → status SKIPPED
    (skip_reason SKIPPED_NO_USABLE_IMAGERY). No visual observations are
    ever fabricated.
  * AI visual observations are marked as Tier-D AI interpretation, never
    presented as official remote-sensing conclusions.
"""

from __future__ import annotations

import logging
from pathlib import Path

from agents.professional_base import ProfessionalAgent
from orchestration.context_builder import AgentEvidenceView
from schemas.agent_outputs import AgentRunResult, AgentStatus, RiskSignal
from schemas.evidence import AGENT_REMOTE_SENSING, PRE_EVENT_RISK_PHASES

logger = logging.getLogger(__name__)

SKIP_NO_USABLE_IMAGERY = "SKIPPED_NO_USABLE_IMAGERY"

_AI_OBSERVATION_NOTE = (
    "observations 为 AI 目视观察（Tier D，模型解译），不是官方或算法化"
    "遥感结论，仅作辅助参考。")


def _date_part(text: str) -> str:
    """'2026-08-24 05:11' / '2026-08-24T05:11' → '2026-08-24' ('' if none)."""
    s = str(text or "").strip()
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return s[:10]
    return ""


class RemoteSensingAgent(ProfessionalAgent):
    agent_name = AGENT_REMOTE_SENSING
    prompt_id = "remote_sensing_v1"
    prompt_version = "v1"
    uses_imagery = True

    role_description = (
        "你是 MountainGuardian 系统的遥感专业分析员（Remote Sensing "
        "Agent），只负责基于授权灾前遥感影像与遥感元数据的专业分析。")
    task_description = (
        "本轮唯一任务（Historical Replay）：仅基于下方授权的灾前影像与"
        "遥感元数据，描述灾前环境基线（冰川源区、沟谷、地形背景）的目视"
        "特征与影像质量限制。你的目视观察是 AI Visual Observation，"
        "必须与官方/算法遥感结论明确区分。不得推断灾害发生后的地表变化。")
    forbidden_claims = (
        "不得使用或推测灾后影像、灾后地表变化、实际灾害路径。",
        "不得在无影像时虚构任何目视观察。",
        "不得把 AI 目视观察表述为官方遥感解译结论。",
        "不得给出灾害发生概率或具体发生时间。",
        "不得计算或修改最终 Risk Index。",
    )
    extra_scientific_constraints = (
        "灾前影像只作为环境/河谷基线；灾后变化只能由后续 Validation 阶段处理。",
        "云量、分辨率等质量限制必须写入 quality_notes。",
    )

    # ─── usable-imagery discipline ─────────────────────────────────────────
    def _usable_pre_event_imagery(self, view: AgentEvidenceView) -> list:
        """Return only imagery that is provably pre-event and loadable.

        Conservative on ambiguity: a missing phase, a missing/unparsable
        observation date, or a date not strictly before the public event
        date all disqualify an image. Post-event imagery is never eligible,
        so it can never be substituted into pre-event analysis.
        """
        event_date = _date_part(view.case_metadata.get("event_date"))
        usable = []
        for item in view.pre_event_imagery:
            if item.phase not in PRE_EVENT_RISK_PHASES:
                logger.warning("[remote_sensing] %s rejected: phase %s",
                               item.evidence_id, item.phase)
                continue
            obs_date = _date_part(item.observation_time)
            if not obs_date or (event_date and obs_date >= event_date):
                logger.warning("[remote_sensing] %s rejected: observation "
                               "date %r not provably before event %r",
                               item.evidence_id, obs_date, event_date)
                continue
            ref = str(item.media_ref or "")
            if not ref:
                continue
            if not ref.startswith(("http://", "https://", "data:")) \
                    and not Path(ref).is_file():
                logger.warning("[remote_sensing] %s rejected: media_ref "
                               "not available locally", item.evidence_id)
                continue
            usable.append(item)
        return usable

    # ─── pre-provider short-circuit: SKIPPED, never fabricated ─────────────
    def _pre_provider_hook(self, view: AgentEvidenceView):
        # per-run state, recomputed every run (agents are used sequentially;
        # no cross-run leakage of imagery selections)
        self._usable_imagery = []
        usable = self._usable_pre_event_imagery(view)
        if not usable:
            return self._skipped(
                view, SKIP_NO_USABLE_IMAGERY,
                missing_data=["无可用授权灾前影像（或影像不满足灾前日期/"
                              "质量/可获取性检查）"])
        # stash for the request phase (single bounded call, no state leaking
        # across runs: recomputed every run)
        self._usable_imagery = usable
        return None

    def _images_for_request(self, view: AgentEvidenceView) -> list:
        return [str(i.media_ref) for i in
                getattr(self, "_usable_imagery", [])]

    def _extra_prompt_data_sections(self, view: AgentEvidenceView) -> list:
        usable = getattr(self, "_usable_imagery", [])
        sections = []
        if usable:
            sections.append(("授权灾前影像（随本请求提交，pre-event only）",
                             usable))
        rs_meta = [e for e in view.evidence
                   if e.evidence_type == "remote_sensing_metadata"]
        if rs_meta:
            sections.append(("遥感元数据", rs_meta))
        return sections

    # ─── deterministic fallback: metadata only, NEVER visual claims ────────
    def _deterministic_fallback(self, view: AgentEvidenceView) -> dict:
        usable = getattr(self, "_usable_imagery", [])
        findings = []
        cited = []
        notes = []
        for item in usable:
            findings.append(
                f"[规则回退] 存在授权灾前影像 {item.value}"
                f"（{item.observation_time}），可作为环境基线。")
            cited.append(item.evidence_id)
            if item.limitations:
                notes.append(item.limitations)
        notes.append("模型调用失败，未执行 AI 目视解译；"
                     "本结果不包含任何视觉观察。")
        return {
            "agent": self.agent_name,
            "status": "DEGRADED",
            "risk_signal": RiskSignal.DATA_LIMITED.value,
            "confidence": 0.2,
            "key_findings": findings or ["[规则回退] 无可用授权灾前影像。"],
            "evidence_ids": cited,
            "image_ids": [i.evidence_id for i in usable],
            "observations": [],
            "quality_notes": notes,
            "missing_data": ["AI 目视解译结果（模型不可用）"],
            "limitations": [
                "确定性规则回退：仅确认灾前影像元数据存在，"
                "未产生任何视觉观察，不得当作遥感解译结论。",
            ],
        }

    # ─── post-processing: AI-observation labeling + image id discipline ────
    def _post_process(self, result: AgentRunResult,
                      view: AgentEvidenceView) -> AgentRunResult:
        if result.status in (AgentStatus.SKIPPED, AgentStatus.FAILED):
            return result
        usable_ids = {i.evidence_id for i in
                      getattr(self, "_usable_imagery", [])}
        image_ids = list(result.agent_specific.get("image_ids") or [])
        unauthorized = [i for i in image_ids if i not in usable_ids]
        if unauthorized:
            result.agent_specific["image_ids"] = [
                i for i in image_ids if i in usable_ids]
            result.limitations = list(result.limitations) + [
                f"模型引用了未授权 image_ids {unauthorized[:5]}，已移除。"]
        if result.is_model_output:
            result.limitations = list(result.limitations) + [_AI_OBSERVATION_NOTE]
        return result
