"""G05A — Azure core deployment tests (deployment-focused, hermetic).

Scope (gate G05A): verify the version-controlled deployment surface only —
startup script sanity, workflow structure (tests-before-deploy, no secrets),
artifact exclusion rules, and Azure environment path resolution for the
production runtime directory. No network, no Azure calls, no secrets.

Frozen references: doc 06 §36 (SQLite path), §43 (health endpoint),
§45–§46 (startup command / startup file), §51–§55 (GitHub Actions),
§57–§58 (artifact exclusions / .gitignore).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
STARTUP_SH = REPO_ROOT / "startup.sh"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "azure-deploy.yml"
GITIGNORE = REPO_ROOT / ".gitignore"
REQUIREMENTS = REPO_ROOT / "requirements.txt"


# ─── startup.sh sanity (doc 06 §45–§46) ──────────────────────────────────────


class TestStartupScript:
    def test_startup_script_exists_and_is_versioned(self):
        assert STARTUP_SH.is_file(), "startup.sh must exist at repository root"

    def test_startup_uses_production_entry_point(self):
        text = STARTUP_SH.read_text(encoding="utf-8")
        # Production entry is mountainguardian_app.py (G04B), NOT legacy app.py.
        assert "mountainguardian_app.py" in text
        assert not re.search(r"streamlit run app\.py\b", text)

    def test_startup_binds_all_interfaces_headless(self):
        text = STARTUP_SH.read_text(encoding="utf-8")
        assert "--server.address=0.0.0.0" in text
        assert "--server.headless=true" in text

    def test_startup_honors_azure_port_env_without_hardcoding(self):
        text = STARTUP_SH.read_text(encoding="utf-8")
        # Must use the Azure runtime-provided PORT with platform default 8000.
        assert "${PORT:-8000}" in text
        assert "--server.port=" in text
        # No hard port literal other than the documented platform default.
        ports = re.findall(r"--server\.port=(\d+)", text)
        assert not ports, "port must come from $PORT, not a literal"

    def test_startup_creates_runtime_dir(self):
        text = STARTUP_SH.read_text(encoding="utf-8")
        assert "MOUNTAINGUARDIAN_RUNTIME_DIR" in text
        assert "mkdir -p" in text

    def test_startup_contains_no_secrets(self):
        text = STARTUP_SH.read_text(encoding="utf-8").lower()
        assert "deepseek_api_key" not in text
        assert "sk-" not in text
        assert "publishsettings" not in text
        assert "publish-profile" not in text


# ─── GitHub Actions workflow structure (doc 06 §51–§55) ─────────────────────


class TestWorkflow:
    @pytest.fixture()
    def workflow_text(self) -> str:
        assert WORKFLOW.is_file(), "azure-deploy.yml must exist"
        return WORKFLOW.read_text(encoding="utf-8")

    def test_trigger_on_main_push(self, workflow_text):
        # main is always a push trigger; the temporary feature-branch trigger
        # for initial validation is documented and removed before merge.
        assert re.search(r"push:\s*\n\s*branches:\s*\[main", workflow_text)

    def test_tests_run_before_deploy(self, workflow_text):
        # Deploy job must declare needs: test so failures block deployment.
        assert re.search(r"needs:\s*test", workflow_text)
        # The test job runs pip check and pytest.
        assert "pip check" in workflow_text
        assert re.search(r"run:\s*pytest", workflow_text)

    def test_deploy_uses_oidc_federated_credentials(self, workflow_text):
        # Documented G05A deviation: Publish Profile retired by the Azure
        # platform; OIDC federated credentials approved by the Commander.
        # The three Azure identifiers are non-secret repository variables.
        assert "azure/login@v2" in workflow_text
        assert "vars.AZURE_CLIENT_ID" in workflow_text
        assert "vars.AZURE_TENANT_ID" in workflow_text
        assert "vars.AZURE_SUBSCRIPTION_ID" in workflow_text
        assert "id-token: write" in workflow_text
        assert "azure/webapps-deploy@v3" in workflow_text
        # No publish profile / password-based deployment credential remains.
        assert "AZURE_WEBAPP_PUBLISH_PROFILE" not in workflow_text
        assert "publish-profile" not in workflow_text

    def test_workflow_contains_no_deepseek_key(self, workflow_text):
        assert "DEEPSEEK_API_KEY" not in workflow_text

    def test_workflow_never_echoes_secrets(self, workflow_text):
        # No echo/print of any secrets context value.
        assert not re.search(r"(echo|print).*\$\{\{\s*secrets\.", workflow_text)

    def test_workflow_excludes_env_and_runtime_db(self, workflow_text):
        for pattern in ('-x ".env"', '-x ".env.*"', '-x "*.db"', '-x "data/runtime/*"'):
            assert pattern in workflow_text, f"package must exclude {pattern}"

    def test_workflow_includes_required_runtime_content(self, workflow_text):
        for required in (
            "mountainguardian_app.py",
            "startup.sh",
            "requirements.txt",
            "data/cases/jilong_20260826/case.json",
            "data/regions/jilong_port/region.json",
        ):
            assert required in workflow_text, f"package must include {required}"

    def test_workflow_has_smoke_check(self, workflow_text):
        assert "/_stcore/health" in workflow_text
        assert "azurewebsites.net" in workflow_text


# ─── .gitignore / artifact exclusion (doc 06 §57–§58) ────────────────────────


class TestGitignore:
    @pytest.fixture()
    def ignore_text(self) -> str:
        return GITIGNORE.read_text(encoding="utf-8")

    @pytest.mark.parametrize(
        "pattern",
        [
            ".env",
            ".env.*",
            "data/runtime/",
            ".venv/",
            ".worktrees/",
            ".pytest_cache/",
            "*.db-journal",
            "*.db-shm",
            "*.db-wal",
            "*.publishsettings",
        ],
    )
    def test_required_ignores_present(self, ignore_text, pattern):
        assert pattern in ignore_text

    def test_case_pack_and_region_config_not_ignored(self, ignore_text):
        # Guard against accidental exclusion of scientific runtime data.
        assert "data/cases" not in ignore_text.replace("data/cases/*/reference/", "")
        assert "data/regions" not in ignore_text

    def test_case_pack_and_region_config_tracked_in_git(self):
        import subprocess

        out = subprocess.run(
            ["git", "ls-files", "data/"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        assert "data/cases/jilong_20260826/case.json" in out
        assert "data/regions/jilong_port/region.json" in out


# ─── Azure environment path resolution (doc 06 §33/§36/§60) ──────────────────


class TestAzurePathResolution:
    def test_db_path_env_override(self, monkeypatch, tmp_path):
        from riskwatch.snapshot_store import default_db_path

        azure_path = str(tmp_path / "home" / "data" / "mountainguardian.db")
        monkeypatch.setenv("MOUNTAINGUARDIAN_DB_PATH", azure_path)
        assert str(default_db_path()) == azure_path

    def test_db_path_default_is_local_runtime(self, monkeypatch):
        from riskwatch.snapshot_store import default_db_path

        monkeypatch.delenv("MOUNTAINGUARDIAN_DB_PATH", raising=False)
        resolved = default_db_path()
        assert resolved == REPO_ROOT / "data" / "runtime" / "mountainguardian.db"

    def test_runtime_dir_env_override(self, monkeypatch, tmp_path):
        from riskwatch.climatology import runtime_dir

        monkeypatch.setenv("MOUNTAINGUARDIAN_RUNTIME_DIR", str(tmp_path))
        assert runtime_dir() == tmp_path

    def test_snapshot_store_creates_parent_dir(self, monkeypatch, tmp_path):
        # First-boot safety: store must create a missing /home/data equivalent.
        from riskwatch.snapshot_store import SnapshotStore

        target = tmp_path / "nested" / "runtime" / "mountainguardian.db"
        monkeypatch.setenv("MOUNTAINGUARDIAN_DB_PATH", str(target))
        store = SnapshotStore()
        try:
            assert target.is_file()
        finally:
            store.close() if hasattr(store, "close") else None


# ─── requirements.txt at repository root (doc 06 §13/§56) ────────────────────


class TestRequirements:
    def test_requirements_at_repo_root(self):
        assert REQUIREMENTS.is_file()

    def test_runtime_dependencies_declared(self):
        text = REQUIREMENTS.read_text(encoding="utf-8").lower()
        for dep in ("streamlit", "requests", "folium", "python-dotenv"):
            assert dep in text, f"production dependency {dep} missing"

    def test_no_secret_material_in_requirements(self):
        text = REQUIREMENTS.read_text(encoding="utf-8")
        assert "DEEPSEEK_API_KEY" not in text
        assert "sk-" not in text
