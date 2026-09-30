"""
MountainGuardian v1.0 – EvidenceItem (unified evidence structure).

Frozen design references:
  - 02_MountainGuardian_Scientific_Data_Baseline_v1.0.md §4 (phase taxonomy),
    §5 (leakage red line), §16 (source tiers), §17 (Evidence Provenance),
    §18 (data quality), §19 (Missing Data principle)
  - 03_MountainGuardian_AI_Agent_Architecture_v1.0.md §8 (Evidence object),
    §25 (safety boundaries are enforced in code, not prompts),
    §26 (minimum necessary context)

Hard rules implemented here:
  * Evidence is NEVER invented. Every EvidenceItem is derived from the
    Case Pack (data/cases/<case_id>/case.json) or from explicitly listed
    satellite scene metadata.
  * The phase taxonomy of the Case Pack is preserved verbatim. Phase is
    the highest-authority attribute (Case Pack issue P-1): `agent_use`
    hints inside the pack are NOT trusted for authorization.
  * post_event_validation evidence gets allowed_agents = () — no
    professional risk-analysis agent may ever receive it. Only future
    Critic / Validation stages (G02B) may consume it.
"""

from __future__ import annotations

import ast
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ─── Frozen phase taxonomy (mirrors tools/case_loader.py) ─────────────────────
#: Phases allowed into pre-event professional risk analysis (doc 02 §4.1–4.4)
PRE_EVENT_RISK_PHASES = frozenset({
    "pre_event_static",
    "derived_pre_event_static",
    "pre_event_context",
    "pre_event_evidence",
})

#: Absolutely forbidden in pre-event risk analysis (doc 02 §4.5, §5.1)
POST_EVENT_PHASES = frozenset({"post_event_validation"})

#: Background display only; never scored, never causal claims (doc 02 §4.6)
CONTEXT_ONLY_PHASES = frozenset({"context_only"})

#: Boundaries / gaps consumed as constraints or explicit missing data
#: (doc 02 §4.7, §19)
BOUNDARY_PHASES = frozenset({
    "missing_input",
    "scientific_boundary",
    "safety_boundary",
    "design_input",
})

METADATA_PHASES = frozenset({"metadata"})

# ─── Professional agent identifiers (doc 03 §9) ───────────────────────────────
AGENT_GLACIER_GEOLOGY = "glacier_geology"
AGENT_WEATHER_HYDROLOGY = "weather_hydrology"
AGENT_REMOTE_SENSING = "remote_sensing"

PROFESSIONAL_AGENTS = (
    AGENT_GLACIER_GEOLOGY,
    AGENT_WEATHER_HYDROLOGY,
    AGENT_REMOTE_SENSING,
)

# ─── Evidence types ────────────────────────────────────────────────────────────
TYPE_REGION = "region_metadata"
TYPE_TERRAIN = "terrain"
TYPE_CRYOSPHERE = "cryosphere"
TYPE_GEOLOGY = "geology"
TYPE_HISTORICAL_EVENT = "historical_event"
TYPE_EXPOSURE = "downstream_exposure"
TYPE_WEATHER_CONTEXT = "weather_context"
TYPE_CLIMATE_CONTEXT = "climate_context"
TYPE_HYDROLOGY_STATIC = "hydrology_static"
TYPE_RS_IMAGE = "remote_sensing_image"
TYPE_RS_METADATA = "remote_sensing_metadata"
TYPE_MISSING_INPUT = "missing_input"
TYPE_SCIENTIFIC_BOUNDARY = "scientific_boundary"
TYPE_SAFETY_BOUNDARY = "safety_boundary"

# ─── Data quality labels (doc 02 §18) ─────────────────────────────────────────
class EvidenceQuality(str, Enum):
    GOOD = "GOOD"
    LIMITED = "LIMITED"
    STALE = "STALE"
    MISSING = "MISSING"


#: Case Pack qualitative confidence → quality label
_QUALITY_FROM_CONFIDENCE = {
    "高": EvidenceQuality.GOOD,
    "中-高": EvidenceQuality.GOOD,
    "中": EvidenceQuality.LIMITED,
    "低": EvidenceQuality.LIMITED,
    "": EvidenceQuality.LIMITED,
}

# ─── Key → (evidence_type, allowed_agents) authorization table ────────────────
# Phase remains the highest authority; this table only decides WHICH
# pre-event evidence is relevant to which professional agent
# (minimum necessary context, doc 03 §26). agent_use strings inside the
# Case Pack are deliberately NOT used (Case Pack issue P-1).
_ALL_THREE = (AGENT_GLACIER_GEOLOGY, AGENT_WEATHER_HYDROLOGY, AGENT_REMOTE_SENSING)
_GG = (AGENT_GLACIER_GEOLOGY,)
_WH = (AGENT_WEATHER_HYDROLOGY,)
_RS = (AGENT_REMOTE_SENSING,)

_KEY_AUTHORIZATION = {
    # region / exposure
    "location": (TYPE_REGION, _ALL_THREE),
    "port_lat": (TYPE_REGION, _ALL_THREE),
    "port_lon": (TYPE_REGION, _ALL_THREE),
    "port_elevation_m": (TYPE_EXPOSURE, _GG),
    # cryosphere / source zone
    "glacierized_source_zone": (TYPE_CRYOSPHERE, _GG),
    "source_elevation_m": (TYPE_CRYOSPHERE, _GG),
    "upstream_glacial_lake_count": (TYPE_CRYOSPHERE, _GG),
    "upstream_glacial_lake_area_km2": (TYPE_CRYOSPHERE, _GG),
    # terrain / geology
    "terrain_class": (TYPE_TERRAIN, _GG),
    "vertical_drop_m": (TYPE_TERRAIN, _GG),
    "loose_material_supply": (TYPE_GEOLOGY, _GG),
    "tectonic_context": (TYPE_GEOLOGY, _GG),
    # historical geological / chain-hazard context
    "prior_event_date": (TYPE_HISTORICAL_EVENT, _GG),
    "prior_event_type": (TYPE_HISTORICAL_EVENT, _GG),
    "prior_event_impact": (TYPE_HISTORICAL_EVENT, _GG),
    # weather / climate context
    "annual_precip_mm": (TYPE_WEATHER_CONTEXT, _WH),
    "rainy_season": (TYPE_WEATHER_CONTEXT, _WH),
    "summer_precip_share_pct": (TYPE_WEATHER_CONTEXT, _WH),
    "enso_status_aug2026": (TYPE_CLIMATE_CONTEXT, _WH),
    "nino34_aug2026": (TYPE_CLIMATE_CONTEXT, _WH),
    "mei_v2_aug2026": (TYPE_CLIMATE_CONTEXT, _WH),
    # remote sensing metadata (pre-event scenes)
    "satellite_pre_datetime": (TYPE_RS_METADATA, _RS),
    "satellite_resolution_m": (TYPE_RS_METADATA, _RS),
}

#: Boundary-phase keys → evidence type
_BOUNDARY_TYPES = {
    "missing_input": TYPE_MISSING_INPUT,
    "scientific_boundary": TYPE_SCIENTIFIC_BOUNDARY,
    "safety_boundary": TYPE_SAFETY_BOUNDARY,
}


def _parse_source_ids(raw: Any) -> list:
    """Case Pack stores source_ids as a stringified list, e.g. \"['S01']\"."""
    if isinstance(raw, (list, tuple)):
        return [str(s) for s in raw]
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = ast.literal_eval(raw)
            if isinstance(parsed, (list, tuple)):
                return [str(s) for s in parsed]
        except (ValueError, SyntaxError):
            return [raw.strip()]
    return []


@dataclass(frozen=True)
class EvidenceItem:
    """Unified evidence structure (doc 03 §8, doc 02 §17).

    Immutable by design: once built from the Case Pack, evidence cannot be
    mutated by agents or model output.
    """

    evidence_id: str
    evidence_type: str
    phase: str
    summary: str
    value: Any = None
    unit: str = ""
    source_name: str = ""
    source_organization: str = ""
    source_reference: str = ""
    observation_time: str = ""
    quality: str = EvidenceQuality.LIMITED.value
    raw_or_derived: str = "raw"
    allowed_agents: tuple = ()
    limitations: str = ""
    media_ref: str = ""
    source_confidence: str = ""
    extra: dict = field(default_factory=dict)

    # ─── phase predicates ──────────────────────────────────────────────────
    def is_pre_event(self) -> bool:
        return self.phase in PRE_EVENT_RISK_PHASES

    def is_post_event(self) -> bool:
        return self.phase in POST_EVENT_PHASES

    def is_context_only(self) -> bool:
        return self.phase in CONTEXT_ONLY_PHASES

    def is_boundary(self) -> bool:
        return self.phase in BOUNDARY_PHASES

    def is_authorized_for(self, agent_name: str) -> bool:
        return agent_name in self.allowed_agents

    def to_dict(self) -> dict:
        return {
            "evidence_id": self.evidence_id,
            "evidence_type": self.evidence_type,
            "phase": self.phase,
            "summary": self.summary,
            "value": self.value,
            "unit": self.unit,
            "source_name": self.source_name,
            "source_organization": self.source_organization,
            "source_reference": self.source_reference,
            "observation_time": self.observation_time,
            "quality": self.quality,
            "raw_or_derived": self.raw_or_derived,
            "allowed_agents": list(self.allowed_agents),
            "limitations": self.limitations,
            "media_ref": self.media_ref,
        }

    def to_prompt_block(self, max_text: int = 300) -> str:
        """Compact, bounded serialization for prompt inclusion.

        Content is untrusted DATA — the base agent wraps the whole block in
        data markers; nothing here is an instruction to the model.
        """
        parts = [
            f"[{self.evidence_id}] type={self.evidence_type} "
            f"phase={self.phase} quality={self.quality}",
            f"  {str(self.summary)[:max_text]}",
        ]
        if self.value not in (None, ""):
            parts.append(f"  value={str(self.value)[:max_text]}"
                         + (f" {self.unit}" if self.unit else ""))
        if self.observation_time:
            parts.append(f"  observation_time={self.observation_time}")
        if self.source_name or self.source_organization:
            parts.append(f"  source={self.source_reference or '-'} "
                         f"{str(self.source_organization)[:80]} "
                         f"{str(self.source_name)[:120]}")
        if self.limitations:
            parts.append(f"  limitations={str(self.limitations)[:max_text]}")
        return "\n".join(parts)


def evidence_from_case_field(field_dict: dict,
                             sources_by_id: Optional[dict] = None) -> EvidenceItem:
    """Convert one Case Pack data_field into an EvidenceItem.

    Authorization logic:
      * pre-event phases → looked up in _KEY_AUTHORIZATION (unknown keys are
        authorized to NO agent — conservative default);
      * context_only     → only the Weather / Hydrology Agent, background use;
      * boundary phases  → all three agents may see the gap/constraint;
      * post_event_validation / metadata → allowed_agents = () always.
    """
    sources_by_id = sources_by_id or {}
    key = str(field_dict.get("key", ""))
    phase = str(field_dict.get("phase", ""))
    source_ids = _parse_source_ids(field_dict.get("source_ids"))
    src = sources_by_id.get(source_ids[0], {}) if source_ids else {}

    if phase in PRE_EVENT_RISK_PHASES:
        evidence_type, allowed = _KEY_AUTHORIZATION.get(key, ("", ()))
    elif phase in CONTEXT_ONLY_PHASES:
        evidence_type, allowed = _KEY_AUTHORIZATION.get(
            key, (TYPE_CLIMATE_CONTEXT, ()))
    elif phase in BOUNDARY_PHASES:
        evidence_type = _BOUNDARY_TYPES.get(phase, "boundary")
        allowed = _ALL_THREE if phase != "design_input" else ()
    else:  # post_event_validation, metadata, anything unknown
        evidence_type, allowed = ("", ())

    raw_or_derived = ("derived" if phase == "derived_pre_event_static"
                      else "raw")
    quality = (EvidenceQuality.MISSING.value if phase == "missing_input"
               else _QUALITY_FROM_CONFIDENCE.get(
                   str(field_dict.get("confidence", "")),
                   EvidenceQuality.LIMITED).value)

    return EvidenceItem(
        evidence_id=str(field_dict.get("id") or key),
        evidence_type=evidence_type or "unclassified",
        phase=phase,
        summary=str(field_dict.get("name_zh") or key),
        value=field_dict.get("value"),
        unit=str(field_dict.get("unit") or ""),
        source_name=str(src.get("name", "")),
        source_organization=str(src.get("authority", "")),
        source_reference=",".join(source_ids),
        observation_time="",  # static/background fields have no single time
        quality=quality,
        raw_or_derived=raw_or_derived,
        allowed_agents=allowed,
        limitations=str(field_dict.get("notes") or ""),
        source_confidence=str(field_dict.get("confidence") or ""),
    )


def satellite_evidence_items(satellite: dict,
                             sources_by_id: Optional[dict] = None,
                             local_image_dir: Optional[Path] = None,
                             ) -> list:
    """Build EvidenceItems for the Case Pack satellite section.

    The PRE scene becomes pre_event_evidence authorized for the Remote
    Sensing Agent. The POST scene is kept as post_event_validation with
    allowed_agents = () so that it can never enter risk analysis
    (doc 02 §15.1, doc 03 §12.1). Official reference images published
    after the event are likewise excluded from risk analysis.
    """
    satellite = satellite or {}
    items: list = []
    s2 = satellite.get("public_sentinel2") or {}
    limitations = str(s2.get("limitations") or "")
    org = "Copernicus Sentinel-2 / 公开专题（太空日报）"

    pre = s2.get("pre") or {}
    if pre:
        item_id = str(pre.get("item_id") or "pre_scene")
        media = ""
        if local_image_dir:
            candidates = sorted(Path(local_image_dir).glob("*pre*.jpg"))
            if candidates:
                media = str(candidates[0])
        media = media or str(pre.get("image_url") or "")
        items.append(EvidenceItem(
            evidence_id=f"EV-SAT-PRE-{item_id}",
            evidence_type=TYPE_RS_IMAGE,
            phase="pre_event_evidence",
            summary=f"灾前 Sentinel-2 影像 {item_id}（真彩色，10 m 级）",
            value=item_id,
            unit="",
            source_name="公开 Sentinel-2 灾前场景",
            source_organization=org,
            source_reference="S09",
            observation_time=str(pre.get("datetime_utc") or ""),
            quality=EvidenceQuality.LIMITED.value,
            raw_or_derived="raw",
            allowed_agents=_RS,
            limitations=limitations,
            media_ref=media,
            extra={"resolution_m": pre.get("resolution_m"),
                   "center": s2.get("center")},
        ))

    post = s2.get("post") or {}
    if post:
        item_id = str(post.get("item_id") or "post_scene")
        items.append(EvidenceItem(
            evidence_id=f"EV-SAT-POST-{item_id}",
            evidence_type=TYPE_RS_IMAGE,
            phase="post_event_validation",
            summary=f"灾后 Sentinel-2 影像 {item_id}（仅作验证，禁止进入灾前分析）",
            value=item_id,
            source_name="公开 Sentinel-2 灾后场景",
            source_organization=org,
            source_reference="S09",
            observation_time=str(post.get("datetime_utc") or ""),
            quality=EvidenceQuality.LIMITED.value,
            raw_or_derived="raw",
            allowed_agents=(),
            limitations=(f"灾后整景云量约{post.get('cloud_pct_approx', '?')}%；"
                         + limitations),
            media_ref=str(post.get("image_url") or ""),
        ))

    return items


def build_evidence_pool(case: dict) -> list:
    """Build the full EvidenceItem pool from a loaded Case Pack.

    `case` is the dict returned by tools.case_loader.load_case(). The pool
    contains items of every phase (including post-event, unauthorized) so
    that downstream Critic/Validation stages can use it later; the
    AnalysisContext builder is responsible for phase filtering. Nothing is
    invented here — items map 1:1 onto Case Pack fields.
    """
    raw = case.get("raw") or {}
    sources_by_id = {str(s.get("id")): s for s in (raw.get("sources") or [])}
    pool = [evidence_from_case_field(f, sources_by_id)
            for f in (raw.get("data_fields") or [])]

    # Locate the local satellite image directory. Case ids in the pack are
    # uppercase (JILONG_20260826) while the data directory is lowercase —
    # try candidates so this also works on case-sensitive file systems.
    case_ids = [str(raw.get("case_id") or ""),
                str(case.get("meta", {}).get("case_id") or "")]
    from tools.case_loader import DEFAULT_CASE_ID
    case_ids.append(DEFAULT_CASE_ID)
    cases_root = Path(__file__).resolve().parent.parent / "data" / "cases"
    satellite_dir = None
    for cid in case_ids:
        candidate = cases_root / cid / "satellite"
        if candidate.is_dir():
            satellite_dir = candidate
            break
    pool.extend(satellite_evidence_items(
        raw.get("satellite") or {},
        sources_by_id=sources_by_id,
        local_image_dir=satellite_dir,
    ))
    return pool
