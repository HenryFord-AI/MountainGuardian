"""
MountainGuardian G04A – Overview 2D geospatial map (folium).

Doc 05 §10 / §50: 2D satellite-terrain map as the main workspace.
No 3D, no drawing tools, no dynamic GIS analysis, no layer manager.

Data policy — existing data only, nothing invented:
  * monitoring points (coordinates, elevation, provenance, uncertainty)
    come from the frozen region config `data/regions/jilong_port/region.json`;
  * uncertainty rings are the documented coordinate_provenance
    uncertainty_km values, rendered as-is;
  * the source→port connector is explicitly labeled SCHEMATIC: it only
    indicates the documented hazard-path direction between the two
    representative monitoring points (region.json provenance: source area
    ≈10 km east of the port along the documented path). It is not surveyed
    geometry and says so in its tooltip.
"""

from __future__ import annotations

from typing import Optional, Sequence

import folium

from frontend import theme

# Dark satellite basemap (Esri World Imagery) — CSS-filtered to fit the
# deep-navy mission-control palette while preserving natural terrain.
_IMAGERY_TILES = (
    "https://server.arcgisonline.com/ArcGIS/rest/services/"
    "World_Imagery/MapServer/tile/{z}/{y}/{x}"
)
_IMAGERY_ATTR = (
    "Tiles © Esri — Source: Esri, Maxar, Earthstar Geographics, "
    "and the GIS User Community"
)

_DARKEN_CSS = """
<style>
html, body { background: #07111F; margin: 0; }
.leaflet-container {
    background: #07111F; font-family: inherit;
    border: 1px solid rgba(120,160,200,0.22); border-radius: 10px;
}
.leaflet-tile-pane { filter: brightness(0.52) contrast(1.12) saturate(0.72) hue-rotate(-10deg); }
.leaflet-control-zoom a {
    background: #101C2D !important; color: #DCE7F3 !important;
    border-color: rgba(120,160,200,0.25) !important;
}
.leaflet-tooltip.mg-tip {
    background: #101C2D; color: #DCE7F3; border: 1px solid rgba(120,160,200,0.35);
    border-radius: 8px; box-shadow: 0 4px 18px rgba(0,0,0,0.5); font-size: 11.5px;
    max-width: 300px; white-space: normal;
}
.leaflet-tooltip.mg-tip::before { display: none; }
.mg-legend {
    background: rgba(16,28,45,0.92); border: 1px solid rgba(120,160,200,0.25);
    border-radius: 8px; padding: 8px 11px; color: #DCE7F3; font-size: 11px;
    line-height: 1.8;
}
.mg-legend b { letter-spacing: 0.08em; font-size: 10px; color: #8799AD;
    text-transform: uppercase; }
</style>
"""

_LEGEND_HTML = """
<div class="mg-legend">
  <b>图例</b><br/>
  <span style="color:#37D7E8;">●</span> 监测点（代表性坐标）<br/>
  <span style="color:#37D7E8;">○</span> 坐标不确定性范围<br/>
  <span style="color:#FFB454;">┄</span> 灾害路径方向（示意图）
</div>
"""

_POINT_STYLE = {
    "source_zone": dict(color=theme.CYAN, label="源区 · 5200 m"),
    "port_zone": dict(color=theme.CYAN, label="吉隆口岸 · 1800 m"),
}


def _point_tooltip(point_id: str, name: str, elevation_m: Optional[float],
                   uncertainty_km: Optional[float]) -> str:
    from frontend.display import point_name_label

    elev = f"{elevation_m:.0f} m" if elevation_m is not None else "—"
    unc = (
        f"±{uncertainty_km:.0f} 公里（代表性坐标，非实测）"
        if uncertainty_km is not None else "代表性坐标"
    )
    return (
        f"<b>{point_name_label(name)}</b><br/>"
        f"海拔：{elev}<br/>"
        f"坐标：{unc}"
    )


def build_overview_map(
    monitoring_points: Sequence[tuple],
    height: int = 560,
) -> Optional[str]:
    """Return standalone map HTML for the Overview main workspace.

    `monitoring_points` rows: (point_id, name, lat, lon, elevation_m,
    uncertainty_km) — exactly the view-model shape from region.json.
    Returns None when there is nothing to render (empty state upstream).
    """
    pts = [p for p in monitoring_points if p[2] is not None and p[3] is not None]
    if not pts:
        return None

    lats = [float(p[2]) for p in pts]
    lons = [float(p[3]) for p in pts]
    center = ((min(lats) + max(lats)) / 2, (min(lons) + max(lons)) / 2)

    m = folium.Map(
        location=center,
        zoom_start=13,
        tiles=_IMAGERY_TILES,
        attr=_IMAGERY_ATTR,
        control_scale=True,
        prefer_canvas=True,
        world_copy_jump=False,
    )
    root = m.get_root()
    root.html.add_child(folium.Element(_DARKEN_CSS))
    root.html.add_child(folium.Element(
        '<div style="position:fixed;bottom:22px;left:22px;z-index:1000;">'
        + _LEGEND_HTML + "</div>"
    ))

    # ── schematic hazard-path connector (drawn first, under the markers) ──
    if len(pts) >= 2:
        src = next((p for p in pts if p[0] == "source_zone"), pts[0])
        dst = next((p for p in pts if p[0] == "port_zone"), pts[-1])
        folium.PolyLine(
            locations=[[float(src[2]), float(src[3])],
                       [float(dst[2]), float(dst[3])]],
            color=theme.ORANGE, weight=2.5, opacity=0.85, dash_array="7 7",
            tooltip=folium.Tooltip(
                "<b>已记录的灾害路径方向 — 示意图（非实测几何）</b><br/>"
                "两个代表性监测点之间的直线连接（源区位于口岸以东约 10 公里，"
                "沿已记录的冰崩 — 碎屑流路径）。仅为方向示意，非实测几何。",
                className="mg-tip", sticky=True,
            ),
        ).add_to(m)

    # ── monitoring points + documented uncertainty rings ─────────────────
    for point_id, name, lat, lon, elevation_m, uncertainty_km in pts:
        style = _POINT_STYLE.get(point_id, dict(color=theme.CYAN, label=str(name)))
        if uncertainty_km:
            folium.Circle(
                location=[float(lat), float(lon)],
                radius=float(uncertainty_km) * 1000.0,
                color=theme.CYAN, weight=1, opacity=0.45,
                fill=True, fill_color=theme.CYAN, fill_opacity=0.05,
                tooltip=folium.Tooltip(
                    f"坐标不确定性 ±{uncertainty_km:.0f} 公里"
                    f"（区域配置中已记录）",
                    className="mg-tip", sticky=True,
                ),
            ).add_to(m)
        folium.CircleMarker(
            location=[float(lat), float(lon)],
            radius=6,
            color=style["color"], weight=2, opacity=1.0,
            fill=True, fill_color=style["color"], fill_opacity=0.9,
            tooltip=folium.Tooltip(
                _point_tooltip(point_id, str(name), elevation_m, uncertainty_km),
                className="mg-tip", sticky=True,
            ),
        ).add_to(m)

    # fit the whole monitored region with comfortable padding
    pad = 0.03
    m.fit_bounds([
        [min(lats) - pad, min(lons) - pad * 1.6],
        [max(lats) + pad, max(lons) + pad * 1.6],
    ])
    return m._repr_html_()
