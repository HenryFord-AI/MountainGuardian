# MountainGuardian v1.0 — Release Manifest (RELEASE_MANIFEST_v1.0.md)

Authoritative release record for Gate G06 (Release Candidate & Competition Freeze).
Status: **FINAL — v1.0 competition release under Competition Freeze** (see §17).

## 1. Product & release purpose

- Product: **MountainGuardian / 山河守望者** — research prototype for regional
  ice-rock avalanche – debris-flow – mudflow risk-state assessment, Tibet Gyirong
  (吉隆) port region.
- Release purpose: **v1.0 competition release**. No new product feature, scientific
  fact, Risk formula, Agent architecture, provider behavior, database architecture,
  DNS topology or TLS architecture was introduced in G06. G06 performed validation,
  evidence capture and release only.

## 2. Release commit & date

- Code baseline (all validated code): `e60bc155ca8c28eb52c9a8d7043f04dcef79f0ec`
  (merge of PR #16, `main`), deployed to production by GitHub Actions
  `MountainGuardian CI/CD` run 37079545024 (success, 2026-10-02T23:51:48Z).
- Release branch: `release/v1.0-rc` (branched from `main` @ e60bc15).
- RC1 tag: `mountainguardian-v1.0-rc1` → release-branch HEAD that adds this manifest
  (exact commit recorded in the G06 RC1 Validation Report and tag object).
- Final tag (post Commander acceptance, post merge): `mountainguardian-v1.0` → final
  accepted `main` merge commit.
- Release date (RC1 evidence capture): **2026-10-03 (UTC)**.

## 3. Production URLs & runtime stack

| Role | URL |
|---|---|
| Primary brand domain | https://mountainguardian.cn |
| Compatibility hostname | https://www.mountainguardian.cn |
| Azure fallback | https://mountainguardian-v1.azurewebsites.net |
| Health endpoint | https://mountainguardian.cn/_stcore/health → `200 ok` |

Runtime stack: Azure App Service on Linux, plan `asp-mountainguardian-v1` SKU **B1
single instance**, region eastasia, `PYTHON|3.12`, startup `bash startup.sh`
(`streamlit run` headless), SQLite at `/home/data/mountainguardian.db`
(`MOUNTAINGUARDIAN_DB_PATH`), model provider DeepSeek `deepseek-flash`,
weather provider Open-Meteo (ECMWF IFS forecast / ERA5 reanalysis).
TLS: App Service Managed Certificates (GeoTrust TLS RSA CA G1), SNI-bound,
`httpsOnly=true` platform-enforced; DNS: A `@` → 13.75.34.162, CNAME `www`,
`asuid`/`asuid.www` TXT verification records retained (managed-cert auto-renewal
depends on this topology — do not insert CDN/intermediate CNAME).

## 4. Test results (full regression)

- `pip check`: **No broken requirements found** (main checkout and release worktree).
- `pytest`: **694 passed, 10 skipped, 0 failed** (identical on `main` @ e60bc15 and
  on `release/v1.0-rc`). No test was deleted or weakened in G06.
- Skipped (all opt-in live-network tests, by design):
  - 4× `test_deepseek_live*` — require `RUN_LIVE_TESTS=1` + DEEPSEEK_API_KEY via the
    authorized secret chain (never enabled in CI to avoid key exposure).
  - 5× `test_g03a_live_openmeteo` — opt-in live Open-Meteo (`RUN_LIVE_TESTS=1`).
  - 1× `test_g03c_live_scan` — requires materialized cached G03A climatology
    references in the runtime dir (live test never re-downloads 30 y of archive).
- Per-area targeted runs (release worktree): prompt-injection/output-schema/critic
  guards 101 passed; leakage guards (`test_jilong_leakage`) 11 passed; deterministic
  formula suite 135 passed; provider fallback 50 passed; snapshot persistence 17
  passed; Historical Replay Stage A/B integrity 56 passed; Chinese localization 32
  passed; UI smoke 72 passed; deployment 33 passed; professional agents / external
  actions 113 passed.
- Named guard tests verified present and green: `test_prompt_injection_blocked`,
  `test_blocked_before_provider_invocation`, `test_full_pipeline_no_leakage_in_risk_input`,
  `test_post_event_leakage_detected`, `test_post_event_outcome_value_leakage_detected`,
  `test_post_event_evidence_id_cited_blocks`, `test_20_no_secret_leakage`,
  `test_schema_validation_passes_and_fails`, `test_schema_violation_falls_back`,
  `test_hallucinated_evidence_id_blocks`, `test_no_control_can_disable_safety_guards`,
  `test_audit_safety_renders_safety_state`, `test_fallback_never_masquerades_as_real_output`,
  `test_forecast_side_failure_blocks_official_C_and_O7`.

## 5. Scientific boundary summary (frozen, verified unchanged)

Frozen formulas (`riskwatch/engine/formulas.py`, doc 04 §13–§18;
`FORMULA_VERSION = risk-watch-formulas-v1.0-frozen-doc04`):

```
B = regional static susceptibility baseline (static config, 5 factors)
R = recent 7-day precipitation percentile (regional conservative max)
F = forecast 7-day precipitation percentile (regional conservative max)
D = 0.60·R + 0.40·F
C = 0.70·B + 0.30·D
O7 = 0.70·B + 0.30·F
Bands: LOW 0–39 | MODERATE 40–59 | ELEVATED 60–79 | HIGH 80–100 (prototype bands)
Direction: ΔC ≥ +5 RISING | −5 < ΔC < +5 STABLE | ΔC ≤ −5 FALLING | first scan NO_HISTORY
```

- Source audit: weights/bands/direction thresholds match the frozen spec exactly;
  classification always uses unrounded values; `git log` shows `formulas.py` last
  changed in the original engine commit `bbf39c8` and the frozen case pack
  `data/cases/jilong_20260826/case.json` last changed in `325a72b` — **no drift**.
- Arithmetic verified against live production values (run …66526014):
  D = 0.60·99.1398 + 0.40·80.3226 = 91.61292 ✓;
  C = 0.70·92.222 + 0.30·91.61292 = 92.039276 ✓;
  O7 = 0.70·92.222 + 0.30·80.3226 = 88.65218 ✓.
- Semantics: B/R/F/D/C/O7 are deterministic heuristic risk-state indicators, **not
  event probabilities**, not official warning levels. UI shows localized band labels
  低 / 中等 / 较高 / 高 over unchanged backend bands.

## 6. Historical Replay validation (complete)

- Case identity (frozen): 2026 年西藏吉隆口岸"8·26"冰岩崩—碎屑流—泥石流灾害,
  event date 2026-08-26, case pack `JILONG_20260826`.
- Production UI (历史验证) verified 2026-10-03: timeline 灾前阶段 2026-08-24 →
  事件发生 2026-08-26 → 灾后验证 2026-08-27; 灾前证据 panel (21 条 · 仅灾前相位);
  multi-Agent analysis (3 professional agents → synthesizer → critic, frozen DAG);
  **91 / 100**, band **HIGH / 高**; explicit labels **基线易感性指数** and
  **⚠ 不是事件发生概率**; wording 灾前分析仅使用事件发生前可获得的公开数据;
  灾后验证: 不用于分析，仅用于验证; integrity line 灾前阶段结果未修改 present.
- No post-event leakage: leakage suite green; Stage B cannot mutate Stage A
  (`test_g03b_isolation`, `test_g03c_isolation`, replay assertions
  `risk_index_before == risk_index_after == 91.0`); production Critic cross-check for
  the live run reads 评审前 92.039276 / 评审后 92.039276 — 评审智能体从不修改确定性风险指数.
- 91 is the frozen historical Baseline Susceptibility Index; it is **not** a 91%
  probability and the UI never renders "91%".

## 7. Final production Risk Watch run(s)

One legitimate final scan was executed through the real production UI
(风险监测 → 执行风险扫描, headless Edge automation, 2026-10-03):

- **Intentional G06 scan**: `rw-20261003T013047039394Z-66526014`
  started 2026-10-03T01:30:47Z, completed 01:31:51Z, mode LIVE,
  status COMPLETED_WITH_LIMITATIONS, is_invalid=0.
- **Duplicate scan** `rw-20261003T015704847835Z-41b386e7` (01:57:04Z → 01:58:16Z):
  triggered unintentionally by the G06 screenshot-capture automation clicking the
  real CTA during a navigation retry. Disclosed here in full; engine outputs are
  byte-identical to the intentional run (same frozen inputs); direction chip differs
  only because its predecessor is the 01:31 run (STABLE +0.00 vs RISING +6.50).
  No historical row was modified, deleted or re-ordered; both runs appended
  immutable snapshots (DATA_OK + final) as designed.

Recorded values (identical for both runs, from production SQLite payload):

| Field | Value |
|---|---|
| B (static baseline susceptibility) | 92.22 (full precision 92.222) |
| R (recent 7-day percentile) | 99.14 (99.1398) |
| F (forecast 7-day percentile) | 80.32 (80.3226) |
| D | 91.61 (91.61292) |
| C (current risk index) | 92.04 (92.039276) |
| O7 (7-day outlook index) | 88.65 (88.65218) |
| Band | HIGH → 高 |
| Direction | RISING +6.50 (…66526014) / STABLE +0.00 (…41b386e7) |
| Required data coverage | 2 / 2 (Open-Meteo source zone + port zone) |
| Optional evidence | 0 / 4 (declared missing, never silent) |
| Glacier & Geology Agent | COMPLETED — real model output (deepseek-flash) |
| Weather & Hydrology Agent | DEGRADED — disclosed deterministic rule fallback (DeepSeek call timed out ≈30 s; fallback never masquerades) |
| Remote Sensing Agent | SKIPPED (SKIPPED_NO_USABLE_IMAGERY — valid formal output, accepted limitation) |
| Risk Synthesizer | COMPLETED — real model output (deepseek-flash) |
| Critic | model output, verdict NEEDS_REVISION (8 disclosed warnings; deterministic numbers unaffected; index unchanged) |
| DeepSeek | 模型服务状态 已连接 (CONNECTED), model deepseek-flash |
| Open-Meteo | AVAILABLE (ecmwf_ifs forecast; observations OK) |
| Disclosed limitations | 7 per run (4× climatology_model_fallback era5_land→era5 precipitation; remote-sensing skip; weather-agent rule fallback; critic NEEDS_REVISION) |

Persistence: verified twice — (a) UI reload shows the run as 最近扫描 and in
历史风险趋势; (b) read-only SQLite query through the Kudu ARM proxy against
`/home/data/mountainguardian.db` returns both runs with schema
`risk_watch_snapshot_v1`, config `g03b-2026-10-01.1`, `is_invalid=0`.

## 8. Security / secret audit

- Tracked content (156 files) scanned with redacted pattern reporting
  (DeepSeek-style `sk-…`, Alibaba `LTAI…`, private-key blocks, publish-profile
  passwords, assigned-secret literals, JWTs, GitHub PATs, Azure AccountKey,
  AWS-style keys, Bearer tokens): **0 real credentials**. All hits triaged as
  benign: `risk-watch-*` version strings (substring false positives), unit-test
  fixtures `sk-TEST…` / `sk-UNIT…`, and `.env.example` placeholders only.
- Live page DOM (all four pages + three intel tabs + both compat hosts): no
  `sk-…`, JWT, LTAI, private-key or PAT material.
- Production DEEPSEEK_API_KEY lives only in App Settings (rotated 2026-10-02 after
  the one-time exposure; old key revoked). `bws secret get/list` never run un-piped.
- Safety controls surfaced and tested: 提示词注入防护 已启用, 数据泄漏防护 已启用,
  灾后信息泄漏防护 通过, 输出结构校验 通过, 外部操作已禁用 (设计上禁用).

## 9. G05A deployment-authentication exception (approved)

The frozen deployment spec (doc 06 §54) preferred the Azure Web App Publish Profile.
During G05A that route was operationally unusable in the real deployment
environment (the hosting organization's Azure tenant: ARM credential APIs redacted, SCM basic-auth 401,
`az webapp deployment github-actions add` Not Found). The Commander approved a
**narrow exception limited to deployment authentication**: GitHub Actions uses
Azure OIDC federation (AAD app `mountainguardian-gh-deploy`, SP scoped Website
Contributor on `rg-mountainguardian-v1` only; repo stores client/tenant/subscription
ids as GitHub *variables*, zero secrets). Publish Profile remains a supported Azure
method elsewhere — the exception is environmental, not a platform deprecation.
G06 does **not** revert OIDC to Publish Profile and does **not** expand IAM scope.

## 10. G05C Chinese localization status

- Production UI is Chinese-first on all four pages: 总览 / 历史验证 / 风险监测 /
  情报中心 (sidebar verified on root, www and Azure fallback hosts).
- Required strings present: 执行风险扫描 (CTA), 当前风险, 未来7天风险展望, 数据覆盖,
  基线易感性指数, 不是事件发生概率, 灾前证据, 灾后验证, 外部操作已禁用,
  band labels 低/中等/较高/高; mandatory disclaimers rendered
  (风险指数不是事件发生概率 / 展望指数不是事件发生概率 / 研究性风险评估，非官方灾害告警).
- Language audit (G05C methodology, allowlist of technical identifiers): 0 unknown
  Latin tokens on 总览/历史验证/情报中心 tabs; 0 banned English UI labels
  (no Overview / Historical Replay / Risk Watch nav / Run Risk Scan regressions).
  Documented cosmetic notes (not blockers): the Critic's machine-generated audit
  narrative contains a few English technical tokens ("Risk Watch", "Case Pack",
  "conf/optional") inside Chinese disclosure sentences; the negation disclaimer
  "不等同官方预警等级" contains the substring 官方预警 (it is a prohibition, not a claim).
- No language selector, no i18n framework — presentation mapping stays in
  `frontend/display.py` (pure dicts), backend enums untouched.

## 11. Screenshot evidence index (10 primary, real production captures)

All captured from https://mountainguardian.cn (except #10 chrome proof) with
headless/headed Microsoft Edge via Playwright, viewport 1440×900, on release commit
baseline e60bc15 (production-deployed). Stored outside the repository at
`D:\HenryFord-AI\mg-g06-release-evidence\`. No mocks, no image generation.
Long pages (06–09) captured as expanded/stitched real viewport strips; #10 is a
Win32 PrintWindow capture of a real headed Edge window (address bar + TLS padlock).

| # | File | URL | Page / section | Capture (UTC) | Purpose |
|---|---|---|---|---|---|
| 01 | 01_overview_main.png | https://mountainguardian.cn | 总览 — brand, 主地图, 当前风险, system-state header | 2026-10-03 02:07:07 | Primary overview proof |
| 02 | 02_overview_lower.png | https://mountainguardian.cn | 总览 — 智能体协作 / 风险趋势 / 证据·数据覆盖 / 快速入口 | 02:07:08 | Lower overview sections |
| 03 | 03_historical_replay_main.png | https://mountainguardian.cn | 历史验证 — timeline, 灾前证据, multi-Agent analysis, 91/100, 基线易感性指数, 不是事件发生概率 | 02:07:13 | Historical Replay core proof |
| 04 | 04_historical_replay_validation.png | https://mountainguardian.cn | 历史验证 — 灾后验证, critic/review, scientific limitations, pre/post integrity | 02:07:14 | Validation & integrity proof |
| 05 | 05_risk_watch_main.png | https://mountainguardian.cn | 风险监测 — 执行风险扫描 CTA, 当前风险, 未来7天风险展望, 数据覆盖 | 02:07:19 | Risk Watch main state |
| 06 | 06_risk_watch_detail.png | https://mountainguardian.cn | 风险监测 — 扫描进度, 风险变化, 历史风险趋势, 驱动因素/证据, 评审复核 | 02:01:21 | Full Risk Watch detail |
| 07 | 07_intelligence_agent_workspace.png | https://mountainguardian.cn | 情报中心 · 智能体工作区 — 3 professional agents → 风险综合智能体 → 评审智能体, agent detail | 02:16:14 | Agent workspace proof |
| 08 | 08_intelligence_evidence_center.png | https://mountainguardian.cn | 情报中心 · 证据中心 — category tabs, evidence IDs, provenance, phase tags | 02:16:23 | Evidence/provenance proof |
| 09 | 09_intelligence_audit_safety.png | https://mountainguardian.cn | 情报中心 · 审计与安全 — model runtime, safety controls, audit trail, full critic review | 02:02:25 | Audit & safety proof |
| 10 | 10_production_brand_proof.png | https://mountainguardian.cn (headed Edge window) | Browser chrome: tab title 山河守望者 · MountainGuardian, address bar with TLS padlock + https://mountainguardian.cn, live UI | 02:10:13 | Brand-domain + TLS proof |

Supplementary captures (not primary): `_extra_riskwatch_pre_scan.png`,
`_extra_scan_progress.png`, `_extra_riskwatch_after_reload.png`,
`_extra_historical_full.png`, `compat_www.png`, `compat_mountainguardian-v1.png`,
plus text dumps (`riskwatch_*_body.txt`, `intel_*.txt`) and result JSONs.

## 12. Known limitations (true in the final system)

1. Remote Sensing Agent SKIPPED when no fresh usable Sentinel-2 imagery exists
   (SKIPPED_NO_USABLE_IMAGERY) — accepted, disclosed, never fabricated.
2. Optional evidence not numerically connected in v1.0: live hydrology/water level,
   soil moisture, ENSO background; Sentinel-2 optional pipeline not in the formula.
   Declared 0/4 on every scan; missing items never silently dropped.
3. Precipitation climatology uses a disclosed single-model fallback
   (era5_land → era5 on the same Open-Meteo endpoint; ERA5-Land exposes no
   precipitation variable in the current API).
4. B1 single-instance hosting; App Service cold start on idle; SQLite
   single-instance storage at /home/data/mountainguardian.db.
5. On-demand scans only — no scheduler, no background scanning, no alerting service.
6. Research prototype — not an official warning system; C/O7 are heuristic
   risk-state indicators, not event probabilities; no official alert terminology
   (no 蓝/黄/橙/红预警); no production warning dispatch.
7. No user authentication / RBAC (public read-only prototype).
8. In the two final runs the Weather & Hydrology Agent hit a transient DeepSeek
   latency timeout and used the disclosed deterministic rule fallback; DeepSeek
   service state remained CONNECTED with real model output in the other LLM roles.
9. Critic verdict NEEDS_REVISION on the final runs (narrative-layer warnings,
   e.g. undisclosed derivation of driver contributions) — disclosed in-product;
   deterministic indices unaffected and unchanged by the Critic.
10. Minor cosmetic localization notes in Critic narrative text (see §10).

## 13. Rollback references

- Deployment: GitHub Actions workflow `.github/workflows/azure-deploy.yml`
  (`workflow_dispatch` or push to `main`); redeploy any prior `main` commit to roll
  back the app. Deployment history visible in GitHub Actions run list.
- Data: risk snapshots are immutable; invalidation only via `is_invalid` +
  `correction_note` per frozen snapshot semantics — no row rewriting.
- DNS/TLS: no changes made in G06; managed-certificate topology untouched.

## 14. RC / final tag information

- RC tag: `mountainguardian-v1.0-rc1` (release branch HEAD incl. this manifest).
- Final tag: `mountainguardian-v1.0`, annotated "MountainGuardian v1.0 competition
  release", pointing at the final accepted `main` merge commit — created only after
  Commander RC acceptance, PR merge, post-merge regression, CI/CD success,
  post-merge production verification and a clean main checkout.
- Competition Freeze begins when the final tag is pushed: only genuine
  release-blocker fixes permitted afterwards; competition report, screenshots,
  demo video and the online system must correspond to this same release.

## 15. Recommended live-demo path

总览 → 历史验证 → 风险监测 → 执行风险扫描 (≈60–70 s live) → 情报中心.
Demo notes: the scan shows real stage progress; Remote Sensing may show 已跳过 and
the Weather & Hydrology Agent may show a disclosed fallback badge — both are honest
system states to narrate, not defects; never present C/O7 as probabilities.

## 16. RC2 release-packaging amendment (documentation only)

- RC1 engineering validation: **PASS** (Commander review 2026-10-03). The RC1 tag
  `mountainguardian-v1.0-rc1` remains **immutable** (not moved, not overwritten).
- Bounded amendment on `release/v1.0-rc` (tag `mountainguardian-v1.0-rc2`):
  release packaging only — bilingual README replacement, root LICENSE restated as
  MIT with retained upstream notice, new `THIRD_PARTY_NOTICES.md`, and this
  manifest section. **No application code, frontend, agents, prompts, formulas,
  scientific data, providers, SQLite, Azure, DNS, TLS, deployment auth or
  production environment change**; no redeployment is required or triggered by
  this amendment (documentation files are not part of the deployed app surface
  beyond repo content, and CI/CD deploys the same application code).
- Upstream/license audit: MountainGuardian derives from **RescueMind AI**
  (https://github.com/BALADURGAG24/rescuemind-multi-agent), **MIT License**,
  Copyright (c) 2026 BALADURGA G. Proven by byte-identical git blob SHAs between
  the first commit (4623fbb) and upstream (LICENSE, agents/base_agent.py,
  mcp/mcp_servers.py). MIT→MIT is compatible; the upstream copyright and
  permission notices are retained in `LICENSE` (both copyright lines) and
  `THIRD_PARTY_NOTICES.md`. Final license state: **MIT**.
- Competition-facing identity remains anonymous: README/LICENSE/notices contain no
  participant name, school, class, district, parent or teacher information, no
  competition branding; repository visibility remains **Private** (public release
  to be considered separately after competition review).
- Screenshot provenance: the 10 primary screenshots were captured against
  application code baseline e60bc15 and remain valid — this amendment does not
  alter production application code or UI, so no recapture was performed and none
  is required; the screenshots are unaltered.

## 17. Final release record (post-merge finalization)

- **Commander RC2 acceptance:** 2026-10-03 — RC2 approved for final release;
  final visual review of the 10 primary production screenshots PASS.
  RC1 (`mountainguardian-v1.0-rc1` → 0f894de) and RC2
  (`mountainguardian-v1.0-rc2` → f84dffd) tags remain immutable.
- **Release PR:** #17 (`release/v1.0-rc` → `main`), merged with merge commit
  **c645ba80d1d914f237002d33643c0bbc9ebaeec9**; `main == origin/main` at that commit.
- **Final regression on merged main:** `pip check` clean;
  `pytest` **694 passed, 10 skipped, 0 failed** (skips = documented opt-in
  live-network tests).
- **CI/CD:** GitHub Actions `MountainGuardian CI/CD` run **37094792840**
  (head c645ba8) — **success**, deployed to Azure App Service via the approved
  G05A OIDC deployment-authentication exception (Publish Profile not restored).
- **Post-merge production verification (read-only, no new scan):**
  https://mountainguardian.cn 200; /_stcore/health 200 ok;
  https://www.mountainguardian.cn 200 with valid TLS;
  https://mountainguardian-v1.azurewebsites.net 200. Four entrances smoked
  (总览/历史验证/风险监测/情报中心): Chinese-first nav intact, no traceback, no
  broken route, no horizontal overflow, zero identity hits, zero secret material
  in DOM; Historical Replay disclaimers intact (91/100 = 基线易感性指数,
  不是事件发生概率, no "91%"); accepted Risk Watch runs still persisted and
  visible; Open-Meteo 可用; DeepSeek 已连接 (deepseek-flash); safety controls
  (外部操作已禁用 etc.) intact.
- **Final release tag:** `mountainguardian-v1.0`, annotated
  "MountainGuardian v1.0 competition release", pointing at the main merge commit
  of this finalization change — i.e. the exact commit containing this finalized
  manifest (self-identified by tag name; the exact hash is recorded in the G06
  Final Release & Competition Freeze Report and verifiable via
  `git rev-list -n1 mountainguardian-v1.0`). Release code baseline: e60bc15
  (application code); release metadata lineage: RC1 0f894de → RC2 f84dffd →
  release merge c645ba8 → finalization merge (tagged).
- **Competition Freeze:** in force from the push of `mountainguardian-v1.0`.
  Only genuine release-blocker fixes permitted thereafter; the online system,
  the 10 primary screenshots, the competition report and any demo video
  correspond to this frozen release.
- **Anonymity & visibility:** competition-facing presentation remains anonymous
  (no participant/school/class/district/parent/teacher identity, no competition
  branding); GitHub repository remains **PRIVATE** during competition review;
  public open-source publication and creator attribution deferred to a separate
  post-competition decision.

— End of manifest. No secrets, credentials or sensitive values are contained herein.
