"""G03C – structural isolation, anti-leakage and no-duplication enforcement.

Gate G03C §17 security block + §7:
  18. no post-event Case Pack loading anywhere in the Risk Watch workflow;
  21. security/security_manager.py is NOT modified (frozen guard infra);
  23. Historical Replay regression: the frozen index remains 91;
  §7. no algorithm duplication: the workflow calls the G03B engine and never
      reimplements B / R / F percentile / D / C / O7 (no
      riskwatch_final_formula.py or equivalent exists);
  §16. no UI modification: the workflow never imports Streamlit/frontend.

Boundaries are proven by inspecting code and by runtime instrumentation —
not by trusting comments (same discipline as test_g03a/g03b_isolation.py).
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import socket
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

G03C_MODULES = (
    REPO_ROOT / "orchestration" / "risk_watch_orchestrator.py",
    REPO_ROOT / "orchestration" / "risk_watch_adapter.py",
    REPO_ROOT / "agents" / "riskwatch_synthesizer.py",
    REPO_ROOT / "agents" / "riskwatch_critic.py",
)

FORBIDDEN_IMPORT_ROOTS = {
    "streamlit", "frontend", "components",
}
FORBIDDEN_IMPORT_MODULES = {
    "tools.case_loader", "tools",
}
FORBIDDEN_STRINGS = (
    "data/cases", "case.json", "load_case", "build_evidence_pool",
    "post_event_validation", "jilong_20250708",
)
#: frozen formula weights must never be re-typed in G03C code — the engine
#: is CALLED (gate §7). Multiplication by a frozen weight constant is the
#: duplication signature used by the G03A/G03B isolation suites.
FORMULA_DUPLICATION_RE = re.compile(r"0\.(60|40|70|30)\s*\*")
FORBIDDEN_FUNCTION_DEFS = {
    "compute_C", "compute_D", "compute_O7", "compute_B",
    "compute_static_baseline", "percentile_of", "classify_band",
}

#: sha256 of security/security_manager.py at the G03C entry state
#: (main @ ee2f837). The file is model-context-sensitive: the test only
#: ever hashes it, never reads it into any prompt or model context.
SECURITY_MANAGER_SHA256 = (
    "42916dbb35533a49688982722ae7009a8a9262d61cc1f11565c08c8ba76be450"
)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def _guard(*args, **kwargs):
        raise AssertionError("network access attempted in isolation suite")
    monkeypatch.setattr(socket, "socket", _guard)
    monkeypatch.setattr(socket, "create_connection", _guard)


def _trees():
    for path in G03C_MODULES:
        assert path.is_file(), f"missing G03C module {path}"
        yield path, ast.parse(path.read_text(encoding="utf-8"))


# ═══ 18: no post-event Case Pack loading ═════════════════════════════════════
class TestNoCasePackLoading:
    def test_no_case_pack_imports_or_paths_in_g03c_code(self):
        for path, tree in _trees():
            for node in ast.walk(tree):
                modules = []
                if isinstance(node, ast.ImportFrom):
                    modules = [node.module or ""]
                elif isinstance(node, ast.Import):
                    modules = [a.name for a in node.names]
                for mod in modules:
                    assert mod not in FORBIDDEN_IMPORT_MODULES, (path, mod)
            text = path.read_text(encoding="utf-8")
            for needle in FORBIDDEN_STRINGS:
                assert needle not in text, (path.name, needle)

    def test_case_loader_never_runs_during_a_full_scan(
            self, tmp_path, monkeypatch):
        """Runtime proof: a bomb-patched load_case must never be reached."""
        import tools.case_loader as case_loader

        calls = []

        def bomb(*args, **kwargs):
            calls.append("load_case")
            raise AssertionError(
                "Historical Replay Case Pack loaded during Risk Watch scan")

        monkeypatch.setattr(case_loader, "load_case", bomb)

        from tests.g03c_helpers import (
            FIXED_CENTER, FakeCollector, fixed_clock, make_runtime,
            make_test_region)
        from orchestration.risk_watch_orchestrator import run_risk_scan
        from tests.g03b_helpers import flat_weather

        region = make_test_region(tmp_path)
        runtime = make_runtime(tmp_path)
        result = run_risk_scan(
            region.region_id,
            provider=None,
            regions_dir=tmp_path / "regions",
            runtime_dir=runtime,
            db_path=tmp_path / "scan.db",
            collector=FakeCollector(flat_weather(FIXED_CENTER)),
            clock=fixed_clock(),
            generate_climatology=False,
            run_id="g03c-leak-bomb")
        assert result.risk_index is not None
        assert calls == []

        # the persisted audit trail contains no Case Pack material either
        from riskwatch.snapshot_store import SnapshotStore
        with SnapshotStore(tmp_path / "scan.db") as store:
            for row in store.list_snapshots():
                blob = json.dumps(row, ensure_ascii=False, default=str)
                assert "data/cases" not in blob
                assert "post_event_validation" not in blob
                assert "EV-SAT-POST" not in blob

    def test_critic_post_event_markers_never_touch_case_pack(self):
        from agents.riskwatch_critic import RiskWatchCritic

        critic = RiskWatchCritic(provider=None)
        ids, values, labels = critic._post_event_markers(None)
        assert (ids, values, labels) == (frozenset(), frozenset(), frozenset())

    def test_context_evidence_ids_are_risk_watch_native(self, tmp_path):
        """Every evidence id in a Risk Watch context is RW-* — none comes
        from the Case Pack pool (DF-*/EV-* namespaces)."""
        from tests.g03c_helpers import (
            FIXED_CENTER, FakeCollector, expected_engine_result,
            make_test_region)
        from tests.g03b_helpers import flat_climatologies, flat_weather
        from orchestration.risk_watch_orchestrator import (
            build_risk_watch_context, compute_data_quality)

        region = make_test_region(tmp_path)
        weather = FakeCollector(
            flat_weather(FIXED_CENTER)).collect_region(region)
        watch = expected_engine_result(region)
        dq = compute_data_quality(region, weather, flat_climatologies())
        ctx = build_risk_watch_context(
            region, weather, flat_climatologies(), watch, dq,
            "g03c-ids", "2026-08-15T06:00:00+00:00")
        all_ids = [i.evidence_id for i in
                   (ctx.allowed_evidence + ctx.missing_sources
                    + ctx.context_only_evidence + ctx.pre_event_imagery)]
        assert all_ids
        assert all(i.startswith("RW-") for i in all_ids)


# ═══ 21: security_manager.py untouched ═══════════════════════════════════════
class TestSecurityManagerUntouched:
    def test_security_manager_hash_unchanged(self):
        path = REPO_ROOT / "security" / "security_manager.py"
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest == SECURITY_MANAGER_SHA256, (
            "security/security_manager.py was modified during G03C — the "
            "frozen prompt-injection guard must never be weakened")

    def test_security_manager_not_in_git_diff(self):
        import subprocess

        out = subprocess.run(
            ["git", "status", "--porcelain", "--",
             "security/security_manager.py"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=60)
        assert out.returncode == 0
        assert out.stdout.strip() == "", (
            f"security_manager.py shows up as changed: {out.stdout!r}")


# ═══ 23 + §7: regression and no-duplication ══════════════════════════════════
class TestRegressionAndNoDuplication:
    def test_23_historical_replay_index_remains_91(self):
        from orchestration.risk_engine import compute_historical_risk

        result = compute_historical_risk(run_id="g03c-isolation-check")
        assert result.risk_index == 91.0
        assert result.risk_level == "HIGH"

    def test_no_duplicate_formula_module_exists(self):
        forbidden_names = {
            "riskwatch_final_formula.py", "final_formula.py",
            "risk_formula_final.py", "g03c_formula.py",
            "riskwatch_formula.py",
        }
        for path in REPO_ROOT.rglob("*.py"):
            rel = path.relative_to(REPO_ROOT)
            if any(part in (".git", "venv", ".worktrees", "__pycache__")
                   for part in rel.parts):
                continue
            assert path.name not in forbidden_names, rel

    def test_g03c_code_never_reimplements_engine_formulas(self):
        for path, tree in _trees():
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    assert node.name not in FORBIDDEN_FUNCTION_DEFS, (
                        path.name, node.name)
            code = path.read_text(encoding="utf-8")
            # strip docstrings/comments before scanning for frozen weights
            stripped = _strip_docstrings(tree, code)
            match = FORMULA_DUPLICATION_RE.search(stripped)
            assert match is None, (
                f"{path.name}: frozen formula weight literal "
                f"{match.group(0)!r} found — G03C must CALL the G03B engine, "
                "never duplicate its formulas")

    def test_engine_is_imported_and_called(self):
        text = (REPO_ROOT / "orchestration" /
                "risk_watch_orchestrator.py").read_text(encoding="utf-8")
        assert "from riskwatch.engine.core import" in text
        assert "compute_risk_watch(" in text
        # frozen recompute-verification in the critic calls G03B functions
        critic_text = (REPO_ROOT / "agents" /
                       "riskwatch_critic.py").read_text(encoding="utf-8")
        assert "from riskwatch.engine.formulas import" in critic_text
        assert "compute_C(" in critic_text and "compute_O7(" in critic_text

    def test_no_ui_dependency(self):
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

    def test_scan_function_has_no_streamlit_session_dependency(self):
        source = (REPO_ROOT / "orchestration" /
                  "risk_watch_orchestrator.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        code = _strip_docstrings(tree, source)
        # docstrings may name the boundary; executable code must not
        assert "streamlit" not in code.lower()
        assert "session_state" not in code


def _strip_docstrings(tree: ast.AST, source: str) -> str:
    """Remove docstring nodes and full-line comments for literal scans."""
    doc_spans = []
    nodes = [tree] + [n for n in ast.walk(tree)
                      if isinstance(n, (ast.ClassDef, ast.FunctionDef,
                                        ast.AsyncFunctionDef, ast.Module))]
    for target in nodes:
        body = getattr(target, "body", [])
        if (body and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)):
            doc_spans.append((body[0].lineno, body[0].end_lineno))
    lines = source.splitlines()
    out = []
    for i, line in enumerate(lines, start=1):
        if any(a <= i <= b for a, b in doc_spans):
            continue
        if line.lstrip().startswith("#"):
            continue
        out.append(line)
    return "\n".join(out)


# ═══ G03A/G03B packages stay frozen (layout guards) ══════════════════════════
class TestFrozenLayersUntouched:
    def test_g03a_top_level_layout_unchanged(self):
        names = {p.name for p in (REPO_ROOT / "riskwatch").glob("*.py")}
        assert names == {
            "__init__.py", "cache.py", "climatology.py", "region.py",
            "snapshot_store.py", "weather.py",
        }

    def test_g03b_engine_layout_unchanged(self):
        names = {p.name
                 for p in (REPO_ROOT / "riskwatch" / "engine").glob("*.py")}
        assert names == {
            "__init__.py", "comparison.py", "core.py", "drivers.py",
            "formulas.py", "static_baseline.py", "trend.py",
        }

    def test_g03c_needs_no_api_key_for_deterministic_core(
            self, tmp_path, monkeypatch):
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        from orchestration.risk_watch_orchestrator import run_risk_scan
        from tests.g03b_helpers import flat_weather
        from tests.g03c_helpers import (
            FIXED_CENTER, FakeCollector, fixed_clock, make_runtime,
            make_test_region)

        region = make_test_region(tmp_path)
        result = run_risk_scan(
            region.region_id, provider=None,
            regions_dir=tmp_path / "regions",
            runtime_dir=make_runtime(tmp_path),
            db_path=tmp_path / "scan.db",
            collector=FakeCollector(flat_weather(FIXED_CENTER)),
            clock=fixed_clock(), generate_climatology=False,
            run_id="g03c-nokey")
        assert result.risk_index is not None
        assert result.risk_level in {"LOW", "MODERATE", "ELEVATED", "HIGH"}
