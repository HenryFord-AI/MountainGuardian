# MountainGuardian v1.0 — G05A Azure Deployment Runbook

**Gate:** G05A — Azure Core Deployment (frozen doc 06 §45–§67, doc 07 §21)
**Status:** living document for this Gate; update on any deployment-affecting change.
**Scope boundary:** Custom Domain (mountainguardian.cn) belongs to G05B and is NOT configured here.

---

## 1. Azure Architecture (frozen, minimal footprint)

```text
GitHub (main) ──push──▶ GitHub Actions
                          checkout → Python 3.12 → pip install
                          → pip check → pytest (must pass)
                          → zip runtime artifact
                          → azure/login@v2 (OIDC federated credential)
                          → azure/webapps-deploy (zip)
                          → smoke check ( /  and /_stcore/health )
                                     │
                                     ▼
                    Azure App Service — Linux Code Deployment
                    single instance, Python 3.12, Streamlit
                    /home/data (persistent) ── mountainguardian.db (SQLite)
```

One Resource Group / one App Service Plan / one Web App. No slots, no
autoscale, no container, no managed identity, no Key Vault (v1.0 frozen).

### 1.1 Documented G05A deviation — deployment credential

The frozen spec (doc 06 §54) mandates the Azure Web App Publish Profile in
`AZURE_WEBAPP_PUBLISH_PROFILE`. During G05A execution (2026-10) this method
was verified **unusable on the current Azure platform**:

- every ARM API (`publishxml`, `list-publishing-profiles`,
  `list-publishing-credentials`) returns `REDACTED` instead of the password;
- SCM (`*.scm.azurewebsites.net`) rejects basic-auth zipdeploy with HTTP 401
  even for freshly-set deployment-user credentials;
- Azure's own provisioning tool `az webapp deployment github-actions add`
  fails with `Not Found` when fetching the publish profile.

Commander-approved minimal replacement: **OIDC federated credentials**.
An AAD app registration (`mountainguardian-gh-deploy`) trusts ID tokens from
`https://token.actions.githubusercontent.com` for subjects
`repo:HenryFord-AI/MountainGuardian:ref:refs/heads/main` (and, temporarily,
the G05A feature branch). Its service principal holds **Website Contributor
on `rg-mountainguardian-v1` only** (least privilege). GitHub stores only the
three non-secret identifiers (`AZURE_CLIENT_ID`, `AZURE_TENANT_ID`,
`AZURE_SUBSCRIPTION_ID`) as repository **variables** (non-secret by nature;
no Azure password or client
secret exists anywhere. This stays inside the frozen architecture: no
Key Vault, no managed identity for the app runtime, no infrastructure change.

## 2. Resource Inventory

| Item | Value |
|---|---|
| Subscription | SchoolSub-026 (Xi'an Jiaotong-Liverpool University tenant) |
| Region | East Asia (`eastasia`) |
| Resource Group | `rg-mountainguardian-v1` |
| App Service Plan | `asp-mountainguardian-v1` |
| SKU | B1 (Basic, 1 vCore / 1.75 GB, single instance, no autoscale) |
| Web App | `mountainguardian-v1` |
| Runtime | Linux, `PYTHON|3.12` |
| Public URL | `https://mountainguardian-v1.azurewebsites.net` |
| Health path | `/_stcore/health` (Streamlit process health only) |

## 3. Startup Configuration (version-controlled)

Source of truth: repository root `startup.sh` (doc 06 §46 — never Portal-only).

- Entry point: `mountainguardian_app.py` (G04B production entry; the frozen
  spec's historical `app.py` reference predates the product rename).
- Port: Azure injects `PORT` (platform default 8000); `startup.sh` binds
  `--server.port=${PORT:-8000}`. Never hard-code a different port.
- Flags: `--server.address=0.0.0.0 --server.headless=true`, plus
  `--server.enableCORS=false --server.enableXsrfProtection=false` (standard
  Streamlit-behind-Azure-reverse-proxy settings) and
  `--browser.gatherUsageStats=false`.
- `startup.sh` also `mkdir -p "$MOUNTAINGUARDIAN_RUNTIME_DIR"` before launch
  (first-boot safety for `/home/data`).
- The Web App's `appCommandLine` is set to `bash startup.sh` so the startup
  path is reproducible from the repository:
  `az webapp config set -g rg-mountainguardian-v1 -n mountainguardian-v1 --generic-configurations '{"appCommandLine":"bash startup.sh"}'`

## 4. Application Settings (NAMES only — values never in Git)

Non-secret:

```text
MOUNTAINGUARDIAN_ENV=azure
DEEPSEEK_MODEL=deepseek-flash
MOUNTAINGUARDIAN_DB_PATH=/home/data/mountainguardian.db
MOUNTAINGUARDIAN_RUNTIME_DIR=/home/data
MOUNTAINGUARDIAN_LOG_LEVEL=INFO
SCM_DO_BUILD_DURING_DEPLOYMENT=1
```

Secret (value ONLY in Azure App Service configuration, set out-of-band):

```text
DEEPSEEK_API_KEY=<configured directly from Bitwarden via bws; never echoed>
```

Three-way separation (frozen doc 06 §17/§19/§20):

```text
LOCAL:            Bitwarden → bws run → DEEPSEEK_API_KEY
AZURE PRODUCTION: Azure App Service Settings → DEEPSEEK_API_KEY
GITHUB ACTIONS:   NO DeepSeek key (mock/deterministic tests only)
```

`DEEPSEEK_BASE_URL` uses the code default (`https://api.deepseek.com`).

## 5. Deployment Procedure

### 5.1 One-time provisioning (performed once in G05A)

```bash
az group create -n rg-mountainguardian-v1 -l eastasia
az appservice plan create -n asp-mountainguardian-v1 -g rg-mountainguardian-v1 \
  --sku B1 --is-linux -l eastasia
az webapp create -n mountainguardian-v1 -g rg-mountainguardian-v1 \
  --plan asp-mountainguardian-v1 --runtime "PYTHON|3.12"
# startup command, health check, https-only, app settings (see §3/§4/§6)
```

### 5.2 Steady state — GitHub Actions

- Workflow: `.github/workflows/azure-deploy.yml`
- Trigger: `push` to `main` (post-merge production deployment) and
  `workflow_dispatch` (manual). A temporary `push` trigger on
  `feature/azure-core-deploy` existed only for the initial safe validation
  of the G05A deployment path (validation runs executed 2026-10-02, final
  rerun succeeded end-to-end); it was removed in the last commit before
  merge. This note is the required documentation of that deviation.
- Tests always run first; deploy job has `needs: test` — failed tests block
  deployment.
- Auth: `azure/login@v2` with OIDC federated credentials; repository
  variables `AZURE_CLIENT_ID` / `AZURE_TENANT_ID` / `AZURE_SUBSCRIPTION_ID`
  (non-secret identifiers; see §1.1). The repository holds **zero GitHub
  secrets** (verified 2026-10-02); in particular no DeepSeek key.
- Artifact: tracked repository content zipped in CI, excluding `.git/`,
  `.github/`, `tests/`, `docs/`, `logs/`, venvs, `data/runtime/`, caches,
  `.env*`, `*.db*`, `*.publishsettings`, legacy Docker/cloudrun files.
  Required runtime content (app entry, `frontend/`, `agents/`,
  `orchestration/`, `riskwatch/`, `providers/`, `schemas/`, `tools/`,
  `config/`, `security/`, `requirements.txt`, `startup.sh`,
  `data/cases/jilong_20260826/`, `data/regions/jilong_port/`) is included
  and asserted in-workflow.
- Azure-side build: `SCM_DO_BUILD_DURING_DEPLOYMENT=1` makes Kudu/Oryx run
  `pip install -r requirements.txt` during deployment (doc 06 §56).
- Post-deploy smoke: workflow curls `/` and `/_stcore/health` until both
  return 200 (retry window ~10 min to absorb first-build time).

## 6. Health Check

- App Service health path: `/_stcore/health` (doc 06 §43–§44).
- Measures Streamlit process health ONLY — never DeepSeek / Open-Meteo /
  satellite. External provider state lives in the product's Audit & Safety.

## 7. SQLite Persistence Design

- DB: `/home/data/mountainguardian.db` via `MOUNTAINGUARDIAN_DB_PATH`.
- Runtime dir: `/home/data` via `MOUNTAINGUARDIAN_RUNTIME_DIR` (climatology
  cache and runtime artifacts).
- `/home` is the App Service persistent volume; redeploys replace
  `/home/site/wwwroot` (code) but do NOT wipe `/home/data`.
- `SnapshotStore` creates the parent directory on first boot and initializes
  the schema idempotently (`CREATE TABLE IF NOT EXISTS` semantics); existing
  DBs are never overwritten by deployment (doc 06 §38).
- Single instance only — no scale-out, therefore no SQLite file-lock issues.
- Never copy a local runtime DB into production; production state is created
  by production itself.

### 7.1 Persistence verification (G05A acceptance)

1. Deploy; confirm `/home/data/mountainguardian.db` created (Kudu console or
   a legitimate product write path).
2. Run one real Risk Watch scan → snapshot row persisted.
3. Record non-sensitive proof (snapshot id / run_id).
4. Redeploy the SAME candidate via GitHub Actions.
5. Confirm the same snapshot still exists.

## 8. Rollback Procedure

**Known-good reference:** Git commit recorded in the Gate report (final
merged `main` HEAD after G05A).

Steps (never patch production source via SSH as normal recovery — doc 06 §66):

1. Identify the last known-good commit on `main` (e.g. from Gate report or
   `git log`).
2. Redeploy it through the intended path:
   - Preferred: `git revert` the bad merge on a fix branch → PR → merge →
     automatic deploy; or
   - Manual rollback of the same known-good commit:
     `git checkout <good-commit> -- .` on a branch, push, run
     `workflow_dispatch` from that branch (or merge via PR to `main`).
3. Watch the workflow: tests must pass, then deploy, then smoke.
4. Verify health after rollback:
   - `https://mountainguardian-v1.azurewebsites.net/` = 200
   - `/_stcore/health` = 200
   - Open all four pages; Audit & Safety shows sane provider state.
5. **Production SQLite is preserved automatically**: rollback only replaces
   code under `/home/site/wwwroot`; `/home/data/mountainguardian.db` is
   untouched. NEVER delete/recreate the production DB during rollback.
   Schema is forward-compatible (idempotent init, no destructive migration).

## 9. Operational Notes

- Logs: Azure Portal → App Service → Log stream (stdout/stderr from
  Streamlit + startup). Application logs must never contain secrets.
- Cold start: after idle, first request may take ~10–20 s (B1, single
  instance). Health check pings keep the process supervised, not external
  APIs.
- Cost control: B1 single instance, no autoscale, no slots. If the Gate
  closes and the app is idle for long periods, do NOT downsize to F1/D1 —
  Streamlit websockets and CPU quota are not viable there.
- Backup (doc 06 §40): before important demos, download
  `/home/data/mountainguardian.db` via Kudu console (zip download of
  `/home/data`).

## 10. Troubleshooting Quick Reference

| Symptom | First checks |
|---|---|
| 502 / no health | Log stream: Oryx build failure? `requirements.txt` install errors? startup command = `bash startup.sh`? |
| App starts but port mismatch | Confirm `PORT` honored; `appCommandLine` correct |
| DB not persisting | Confirm `MOUNTAINGUARDIAN_DB_PATH=/home/data/...`; confirm single instance; confirm `/home/data` exists |
| DeepSeek fallback in production | App Settings: `DEEPSEEK_API_KEY` present (check name only), `DEEPSEEK_MODEL=deepseek-flash`; outbound connectivity via Log stream error classes (AUTH_ERROR/TIMEOUT/...) |
| Weather fails | Open-Meteo reachability from Azure; Risk Watch must NOT fabricate a new Current Risk Index without required weather |
