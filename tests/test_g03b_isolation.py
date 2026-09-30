"""G03B – structural isolation and no-AI/no-network enforcement.

Proves the deterministic engine's boundaries by inspecting code, not by
trusting comments:
  * no network stack, no provider/agent/orchestration/tools/security imports;
  * no Historical Replay Case Pack path or post-event strings;
  * no clock reads inside the engine (pure calculation functions);
  * the smoke tool makes no live weather request;
  * Historical Replay 91 regression remains intact alongside G03B.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

ENGINE_DIR = REPO_ROOT / "riskwatch" / "engine"
ENGINE_MODULES = sorted(ENGINE_DIR.rglob("*.py"))

FORBIDDEN_IMPORT_ROOTS = {
    "requests", "urllib", "urllib3", "socket", "http", "httpx", "aiohttp",
    "websockets", "tools", "agents", "orchestration", "providers", "security",
    "streamlit", "deepseek", "openai", "anthropic",
}

FORBIDDEN_STRINGS = (
    "data/cases",
    "case.json",
    "case_loader",
    "https://",
    "http://",
    "api.open-meteo",
    "archive-api",
    "deepseek",
    "DeepSeek",
)

CLOCK_STRINGS = (".now(", "utcnow", "time.time(", "time.monotonic(")

ALLOWED_RISKWATCH_IMPORTS = {
    "riskwatch.region",
    "riskwatch.weather",
    "riskwatch.climatology",
    "riskwatch.snapshot_store",
    "riskwatch.cache",
    "riskwatch.engine",
    "riskwatch.engine.formulas",
    "riskwatch.engine.static_baseline",
    "riskwatch.engine.core",
    "riskwatch.engine.drivers",
    "riskwatch.engine.comparison",
    "riskwatch.engine.trend",
}


def _trees():
    assert ENGINE_MODULES, "engine subpackage must exist"
    for path in ENGINE_MODULES:
        yield path, ast.parse(path.read_text(encoding="utf-8"))


class TestEngineImports:
    def test_no_network_or_ai_or_forbidden_imports(self):
        for path, tree in _trees():
            for node in ast.walk(tree):
                modules = []
                if isinstance(node, ast.ImportFrom):
                    modules = [node.module or ""]
                elif isinstance(node, ast.Import):
                    modules = [a.name for a in node.names]
                for mod in modules:
                    root = mod.split(".")[0]
                    assert root not in FORBIDDEN_IMPORT_ROOTS, (path, mod)
                    if root == "riskwatch":
                        assert mod in ALLOWED_RISKWATCH_IMPORTS, (path, mod)

    def test_no_forbidden_strings(self):
        for path in ENGINE_MODULES:
            text = path.read_text(encoding="utf-8")
            for needle in FORBIDDEN_STRINGS:
                assert needle not in text, (path.name, needle)

    def test_no_clock_reads_in_pure_engine(self):
        for path in ENGINE_MODULES:
            text = path.read_text(encoding="utf-8")
            for needle in CLOCK_STRINGS:
                assert needle not in text, (path.name, needle)

    def test_engine_never_opens_sockets_at_import_time(self):
        import socket

        original = socket.create_connection

        def deny(*args, **kwargs):
            raise AssertionError("engine import must not open sockets")

        socket.create_connection = deny
        try:
            import importlib

            import riskwatch.engine as pkg

            importlib.reload(pkg)
        finally:
            socket.create_connection = original


class TestSmokeToolIsOffline:
    def test_smoke_makes_no_live_request(self):
        text = (REPO_ROOT / "tools" / "g03b_smoke.py").read_text(encoding="utf-8")
        assert "WeatherCollector(" not in text
        assert "HistoricalWeatherClient(" not in text
        assert "default_http_get" not in text
        assert "import requests" not in text
        assert "--no-db" in text  # read-only db stance is explicit

    def test_smoke_never_writes_snapshots(self):
        text = (REPO_ROOT / "tools" / "g03b_smoke.py").read_text(encoding="utf-8")
        assert "insert_snapshot" not in text
        assert "mark_invalid" not in text


class TestTopLevelFoundationUnchanged:
    def test_g03a_modules_still_have_no_risk_formula(self):
        # The frozen G03A isolation contract is enforced by
        # tests/test_g03a_isolation.py; this guards the package layout
        # assumption it relies on (engine lives in the subpackage only).
        top_level = sorted((REPO_ROOT / "riskwatch").glob("*.py"))
        names = {p.name for p in top_level}
        assert names == {
            "__init__.py", "cache.py", "climatology.py", "region.py",
            "snapshot_store.py", "weather.py",
        }


class TestHistoricalReplayRegression:
    def test_historical_replay_index_remains_91(self):
        from orchestration.risk_engine import compute_historical_risk

        result = compute_historical_risk(run_id="g03b-isolation-check")
        assert result.risk_index == 91.0
        assert result.risk_level == "HIGH"

    def test_engine_does_not_reuse_historical_index(self):
        from riskwatch.engine import compute_static_baseline
        from riskwatch.region import load_region

        baseline = compute_static_baseline(load_region())
        assert baseline.value != 91.0
        assert baseline.value_rounded != 91.0


class TestNoProviderDependency:
    def test_computation_succeeds_without_api_key(self, monkeypatch, tmp_path):
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        from datetime import date

        from riskwatch.engine import compute_risk_watch
        from tests.g03b_helpers import (
            flat_climatologies,
            flat_weather,
            write_region,
        )

        region = write_region(tmp_path)
        result = compute_risk_watch(
            region, flat_weather(date(2026, 8, 15)),
            flat_climatologies(months=(8,)), run_id="no-ai")
        assert result.C is not None
        assert result.status.startswith("COMPLETED")
