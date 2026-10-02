"""
MountainGuardian G04A – Honest placeholder for unknown navigation entries.

The four main entries are frozen at G04A (doc 05 §4) and all four are
fully implemented since G04B — this placeholder only renders for an
unknown page key and must never fake content, fake data or fake scans.

G05C (doc 08): visible text is Chinese.
"""

from __future__ import annotations

import streamlit as st

from frontend.components import card_title, esc

_PAGE_NOTES = {
    "historical_replay": (
        "历史验证 / 研究验证",
        "基于冻结的 2026-08-26 吉隆案例，仅使用灾前证据进行回放："
        "灾前/事件/灾后时间线、智能体分析卡、基线易感性结果、"
        "评审复核与灾后验证。",
    ),
    "risk_watch": (
        "风险监测",
        "唯一主操作：执行风险扫描。实时扫描进度、当前风险、"
        "未来7天风险展望、历史风险趋势、风险变化与数据覆盖。",
    ),
    "intelligence_center": (
        "情报中心",
        "三个标签页：智能体工作区、证据中心、审计与安全 — "
        "完整溯源地解释多智能体系统如何工作。",
    ),
}


def render(page_key: str) -> None:
    title, note = _PAGE_NOTES.get(
        page_key, (page_key.replace("_", " ").title(), "")
    )
    with st.container(border=True):
        st.markdown(card_title("规划页面", accent="◇"), unsafe_allow_html=True)
        st.markdown(
            f'<div class="mg-entry-title" style="font-size:17px;">{esc(title)}</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="mg-empty" style="max-width:640px;">'
            "该导航入口在 v1.0 信息架构中冻结。本页面不模拟任何内容："
            "无伪造数据、无伪造扫描。</div>",
            unsafe_allow_html=True,
        )
        if note:
            st.caption(note)
