#!/usr/bin/env bash
# MountainGuardian v1.0 — Azure App Service Linux startup (Gate G05A).
#
# Frozen spec: doc 06 §45 (explicit Streamlit startup command) and §46
# (startup configuration must be version-controlled, not Portal-only).
# Production entry point is mountainguardian_app.py (G04B product entry).
#
# Port handling: Azure App Service injects the PORT environment variable
# into the runtime container (platform default 8000). We never hard-code
# a conflicting port — we honor $PORT with the platform default as fallback.
#
# CORS/XSRF flags: standard Streamlit-behind-Azure-reverse-proxy settings;
# the App Service frontend terminates TLS and forwards requests, and
# Streamlit's Origin/Host checks misfire behind that proxy. Health check
# path /_stcore/health is served by Streamlit itself (doc 06 §43).
set -euo pipefail

PORT="${PORT:-8000}"

# Persistent runtime area (doc 06 §36/§37): /home survives redeploys.
# MOUNTAINGUARDIAN_RUNTIME_DIR is provided via Azure App Settings in
# production; the mkdir keeps first-boot safe even before settings load.
RUNTIME_DIR="${MOUNTAINGUARDIAN_RUNTIME_DIR:-/home/data}"
mkdir -p "${RUNTIME_DIR}"

exec python -m streamlit run mountainguardian_app.py \
  --server.address=0.0.0.0 \
  --server.headless=true \
  --server.port="${PORT}" \
  --server.enableCORS=false \
  --server.enableXsrfProtection=false \
  --browser.gatherUsageStats=false
