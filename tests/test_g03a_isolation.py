"""G03A – structural anti-leakage and scope-boundary enforcement.

These tests prove separation by inspecting the code, not by trusting
comments:
  * the riskwatch package has no runtime path into the Historical Replay
    Case Pack (no case.json read, no tools.case_loader import);
  * no B / R / F / D / C / O7 risk formula and no risk bands live in G03A;
  * no agent / DeepSeek workflow is wired into the data foundation.
"""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

RISKWATCH_DIR = Path(__file__).parent.parent / "riskwatch"
MODULES = sorted(RISKWATCH_DIR.glob("*.py"))

FORBIDDEN_IMPORT_MODULES = {
    "tools.case_loader",
    "tools",
    "agents",
    "orchestration",
    "providers.deepseek_provider",
    "providers",
    "security.security_manager",
}

FORBIDDEN_NAME_RE = re.compile(
    r"(current_risk_index|dynamic_trigger_index|outlook_7d|risk_direction|"
    r"risk_level|GlacierGeologyAgent|WeatherHydrologyAgent|RemoteSensingAgent|"
    r"RiskSynthesizer|Critic|DeepSeek|deepseek)",
    re.IGNORECASE,
)

FORMULA_RE = re.compile(r"0\.(60|40|70|30)\s*\*")


def _module_trees():
    for path in MODULES:
        yield path, ast.parse(path.read_text(encoding="utf-8"))


def _docstring_nodes(tree):
    nodes = []
    targets = [tree] + [
        n for n in ast.walk(tree) if isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    for target in targets:
        body = getattr(target, "body", [])
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            nodes.append(body[0].value)
    return nodes


def _code_identifiers_and_strings(tree):
    """Names and string constants in executable code (docstrings excluded)."""
    doc_ids = {id(n) for n in _docstring_nodes(tree)}
    names, strings = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in doc_ids
        ):
            strings.add(node.value)
    return names, strings


class TestNoPostEventRuntimePath:
    def test_no_case_pack_imports_or_reads(self):
        forbidden_roots = {"tools", "agents", "orchestration", "providers", "security"}
        for path, tree in _module_trees():
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    mod = node.module or ""
                    assert mod.split(".")[0] not in forbidden_roots, path
                    assert "case_loader" not in mod, path
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        assert alias.name.split(".")[0] not in forbidden_roots, path
                        assert "case_loader" not in alias.name, path

    def test_no_case_path_string_in_executable_code(self):
        for path, tree in _module_trees():
            _, strings = _code_identifiers_and_strings(tree)
            for s in strings:
                assert "data/cases" not in s, (path, s)
                assert "case.json" not in s, (path, s)

    def test_region_loader_reads_only_region_files(self):
        region_src = (RISKWATCH_DIR / "region.py").read_text(encoding="utf-8")
        assert "regions" in region_src
        assert "data/cases" not in region_src
        assert "case_loader" not in region_src


class TestNoRiskFormula:
    def test_no_formula_constants_or_risk_outputs(self):
        for path, tree in _module_trees():
            names, strings = _code_identifiers_and_strings(tree)
            blob = " ".join(names) + " " + " ".join(strings)
            assert not FORMULA_RE.search(blob), path
            assert not FORBIDDEN_NAME_RE.search(blob), (path, blob[:200])

    def test_no_risk_band_words(self):
        for path in MODULES:
            text = path.read_text(encoding="utf-8")
            for band in ("LOW", "MODERATE", "ELEVATED", "HIGH"):
                # quality states FRESH/STALE/MISSING are allowed; bands are not
                assert not re.search(rf"\b{band}\b", text), (path, band)


class TestNoAgentWorkflow:
    def test_no_agent_or_provider_imports(self):
        for path, tree in _module_trees():
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    assert (node.module or "") not in FORBIDDEN_IMPORT_MODULES, path
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        assert alias.name not in FORBIDDEN_IMPORT_MODULES, path


class TestSnapshotPayloadHasNoRiskFields:
    def test_g03a_payload_contract_is_data_only(self):
        # The snapshot store must accept arbitrary payloads without adding
        # risk fields; G03A never writes current_risk_index etc.
        from riskwatch import snapshot_store

        src = Path(snapshot_store.__file__).read_text(encoding="utf-8")
        assert "current_risk_index" not in src
        assert "outlook" not in src
