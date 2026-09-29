"""
MountainGuardian – Case Pack Loader
Single Source of Truth: data/cases/<case_id>/case.json

Phase is the highest-authority rule (Case Pack issue P-1): agent_mapping input
ranges are NOT trusted. Only fields whose own phase is pre-event may reach the
Intelligence / Risk agents; post_event_validation goes to the Checker only.
"""

import json
from pathlib import Path

CASES_DIR = Path(__file__).resolve().parent.parent / "data" / "cases"
DEFAULT_CASE_ID = "jilong_20260826"

# The only phases allowed into pre-event analysis (Intelligence / Risk agents)
PRE_EVENT_PHASES = {
    "pre_event_static",
    "derived_pre_event_static",
    "pre_event_context",
    "pre_event_evidence",
}
POST_EVENT_PHASES = {"post_event_validation"}
# Background-only: page display, never scored, never causal claims
CONTEXT_ONLY_PHASES = {"context_only"}
# Boundaries / gaps: Checker + Safety consumption
BOUNDARY_PHASES = {"missing_input", "scientific_boundary", "safety_boundary", "design_input"}


def load_case(case_id: str = DEFAULT_CASE_ID) -> dict:
    """Read case.json and split it by phase into strictly separated buckets."""
    path = CASES_DIR / case_id / "case.json"
    data = json.loads(path.read_text(encoding="utf-8"))

    fields = data["data_fields"]
    by_key = {f["key"]: f for f in fields}

    def value(key, default=""):
        f = by_key.get(key)
        return f["value"] if f else default

    meta = {
        "case_id": value("case_id", case_id),
        "case_name": value("case_name"),
        "event_date": value("event_date"),
        "location": value("location"),
        "lat": value("port_lat"),
        "lon": value("port_lon"),
        "pack_version": data.get("pack_version", ""),
    }

    return {
        "meta": meta,
        "pre_event": [f for f in fields if f["phase"] in PRE_EVENT_PHASES],
        "post_event": [f for f in fields if f["phase"] in POST_EVENT_PHASES],
        "context_only": [f for f in fields if f["phase"] in CONTEXT_ONLY_PHASES],
        "boundaries": [f for f in fields if f["phase"] in BOUNDARY_PHASES],
        "metadata_fields": [f for f in fields if f["phase"] == "metadata"],
        "risk_model": data["demo_risk_model"],
        "sources": data["sources"],
        "usage_limits": [
            f["name_zh"] + "：" + str(f["value"]) + "（" + f.get("notes", "") + "）"
            for f in fields if f["phase"] in BOUNDARY_PHASES
        ],
        "disclaimer": value(
            "case_use_boundary",
            "历史案例回放与风险识别演示，不用于真实灾害预警决策",
        ),
        "satellite": data.get("satellite", {}),
        "raw": data,
    }


def build_demo_context(case: dict = None) -> dict:
    """Context handed to CoordinatorAgent for the competition demo run.

    post_event data travels ONLY as 'case_post'; Coordinator._build_sub_context
    decides per agent type whether it may be seen (Checker only).
    """
    case = case or load_case()
    meta = case["meta"]
    return {
        "query": f"请对{meta['case_name']}进行历史案例回放式多智能体风险分析",
        "location": meta["location"],
        "lat": meta["lat"],
        "lon": meta["lon"],
        "disaster_type": "debris_flow",
        "case_id": meta["case_id"],
        "case_pre": case["pre_event"],
        "case_post": case["post_event"],
        "risk_model": case["risk_model"],
        "data_sources": [f"{s['id']} {s['authority']}" for s in case["sources"]],
        "usage_limits": case["usage_limits"],
        "is_historical_demo": True,
        "force_agents": ["intelligence", "risk", "checker", "warning"],
    }
