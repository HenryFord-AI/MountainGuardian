"""
MountainGuardian G03A – Region configuration loader.

Loads the independent Risk Watch Source of Truth:

    data/regions/<region_id>/region.json

This module must NEVER read the Historical Replay Case Pack: that separation
is a structural anti-leakage control (frozen design doc 04 §3), enforced by
tests/test_g03a_isolation.py.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REGIONS_DIR = Path(__file__).resolve().parent.parent / "data" / "regions"
DEFAULT_REGION_ID = "jilong_port"

REQUIRED_TOP_LEVEL_KEYS = (
    "schema_version",
    "config_version",
    "region_id",
    "region_name",
    "monitoring_points",
    "static_terrain_baseline",
    "cryosphere_baseline",
    "historical_hazard_baseline",
    "static_susceptibility_inputs",
    "source_references",
    "provenance",
    "scientific_limitations",
)

REQUIRED_POINT_KEYS = (
    "point_id",
    "name",
    "latitude",
    "longitude",
    "coordinate_provenance",
)


class RegionConfigError(ValueError):
    """region.json is missing, malformed or violates the frozen schema."""


@dataclass(frozen=True)
class MonitoringPoint:
    point_id: str
    name: str
    latitude: float
    longitude: float
    elevation_m: float | None
    coordinate_provenance: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def coordinate_type(self) -> str:
        return str(self.coordinate_provenance.get("type", "unknown"))


@dataclass(frozen=True)
class RegionConfig:
    region_id: str
    data: dict[str, Any]
    path: Path

    @property
    def schema_version(self) -> str:
        return str(self.data["schema_version"])

    @property
    def config_version(self) -> str:
        return str(self.data["config_version"])

    @property
    def scoring_config_version(self) -> str:
        return str(
            self.data["static_susceptibility_inputs"]["scoring_config_version"]
        )

    @property
    def monitoring_points(self) -> list[MonitoringPoint]:
        return [
            MonitoringPoint(
                point_id=p["point_id"],
                name=p["name"],
                latitude=float(p["latitude"]),
                longitude=float(p["longitude"]),
                elevation_m=(
                    float(p["elevation_m"]) if p.get("elevation_m") is not None else None
                ),
                coordinate_provenance=dict(p.get("coordinate_provenance", {})),
                raw=dict(p),
            )
            for p in self.data["monitoring_points"]
        ]

    def point(self, point_id: str) -> MonitoringPoint:
        for p in self.monitoring_points:
            if p.point_id == point_id:
                return p
        raise RegionConfigError(f"unknown monitoring point: {point_id}")

    @property
    def climatology_baseline(self) -> tuple[str, str]:
        base = self.data["weather_data_policy"]["climatology_baseline"]
        return str(base["start"]), str(base["end"])


def _validate(data: dict[str, Any], path: Path) -> None:
    if not isinstance(data, dict):
        raise RegionConfigError(f"{path}: region config must be a JSON object")
    for key in REQUIRED_TOP_LEVEL_KEYS:
        if key not in data:
            raise RegionConfigError(f"{path}: missing required key '{key}'")

    points = data["monitoring_points"]
    if not isinstance(points, list) or len(points) < 2:
        raise RegionConfigError(
            f"{path}: v1.0 requires at least two monitoring points"
        )
    seen: set[str] = set()
    for p in points:
        for key in REQUIRED_POINT_KEYS:
            if key not in p:
                raise RegionConfigError(
                    f"{path}: monitoring point missing required key '{key}'"
                )
        if p["point_id"] in seen:
            raise RegionConfigError(f"{path}: duplicate point_id {p['point_id']}")
        seen.add(p["point_id"])

        prov = p["coordinate_provenance"]
        if not isinstance(prov, dict) or not prov:
            raise RegionConfigError(
                f"{path}: point {p['point_id']} has no coordinate provenance"
            )
        # No invented coordinates: every point must say where its coordinate
        # comes from, what it means and whether it is exact or representative.
        has_anchor = "anchor" in prov
        has_reference = "reference" in prov
        if not (has_anchor or has_reference):
            raise RegionConfigError(
                f"{path}: point {p['point_id']} provenance lacks source reference"
            )
        if not has_reference and "method" not in prov:
            raise RegionConfigError(
                f"{path}: point {p['point_id']} derived coordinate lacks method"
            )
        if "meaning" not in prov:
            raise RegionConfigError(
                f"{path}: point {p['point_id']} provenance lacks meaning"
            )
        if "exact" not in prov:
            raise RegionConfigError(
                f"{path}: point {p['point_id']} provenance must classify the "
                "coordinate as exact or representative"
            )
        lat, lon = p["latitude"], p["longitude"]
        if not (-90.0 <= float(lat) <= 90.0 and -180.0 <= float(lon) <= 180.0):
            raise RegionConfigError(f"{path}: point {p['point_id']} coords out of range")

    factors = data["static_susceptibility_inputs"]["factors"]
    if not isinstance(factors, list) or not factors:
        raise RegionConfigError(f"{path}: static susceptibility factors missing")
    total = sum(float(f["normalized_weight_pct"]) for f in factors)
    if abs(total - 100.0) > 0.05:
        raise RegionConfigError(
            f"{path}: normalized static weights must sum to 100 (got {total})"
        )


def load_region(region_id: str = DEFAULT_REGION_ID, regions_dir: Path | None = None) -> RegionConfig:
    base = Path(regions_dir) if regions_dir is not None else REGIONS_DIR
    path = base / region_id / "region.json"
    if not path.is_file():
        raise RegionConfigError(f"region config not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RegionConfigError(f"{path}: invalid JSON: {exc}") from exc
    _validate(data, path)
    if data["region_id"] != region_id:
        raise RegionConfigError(
            f"{path}: region_id '{data['region_id']}' does not match directory '{region_id}'"
        )
    return RegionConfig(region_id=region_id, data=data, path=path)
