"""
MountainGuardian v1.0 – Frontend package (G04A UI Foundation).

Geospatial Intelligence × AI Mission Control, built on Streamlit
(doc 05 §57: no React / Next / Vue migration).

Modules:
  theme        frozen design tokens + global CSS (doc 05 §39–§48)
  layout       frozen left navigation + global header (doc 05 §4–§7)
  components   reusable cards / chips / states (doc 05 §11–§14, §52–§55)
  viewmodels   read-only UI view models (doc 05 §59–§60) — UI never
               computes risk, never calls models, never writes snapshots
  map_view     2D folium map over frozen region config (doc 05 §10, §50)
  pages        Overview (full) + honest G04B placeholders

Entry point: `streamlit run mountainguardian_app.py` at the repo root.
"""

__version__ = "1.0.0-g04a"
