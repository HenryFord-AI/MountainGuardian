# MountainGuardian v1.0 — G05B Custom Domain & HTTPS Runbook

**Gate:** G05B — Custom Domain & HTTPS (frozen deployment stage; no product scope change)
**Status:** living document for this Gate; update on any domain/TLS-affecting change.
**Scope boundary:** G05A (Azure Core Deployment) is CLOSED and untouched. This Gate only
binds the frozen brand domain to the existing production Web App and enables managed TLS.

---

## 1. Domain Topology (direct DNS, frozen)

```text
mountainguardian.cn      ──A @──▶  Azure App Service inbound IP  ─┐
                                                                  ├──▶ Web App mountainguardian-v1
www.mountainguardian.cn  ──CNAME──▶ mountainguardian-v1.azurewebsites.net ─┘

Fallback (G05A, MUST remain live): https://mountainguardian-v1.azurewebsites.net
```

| Role | URL |
|---|---|
| Primary brand URL (public materials) | `https://mountainguardian.cn` |
| Secondary compatibility URL | `https://www.mountainguardian.cn` |
| Core Deployment fallback / emergency access | `https://mountainguardian-v1.azurewebsites.net` |

- No second Web App, no second App Service Plan, no Front Door / App Gateway /
  Traffic Manager / CDN / WAF / Cloudflare — both hostnames bind directly to the
  SAME existing site (required topology for App Service Managed Certificate
  issuance and auto-renewal).
- v1.0: no www→root canonical redirect middleware; both hostnames serve the same
  app directly. Public/competition material uses the root domain.
- HTTP→HTTPS enforcement is platform behavior (`httpsOnly=true`), never
  Streamlit-side redirect logic.

## 2. Registrar / DNS

| Item | Value |
|---|---|
| Domain | `mountainguardian.cn` |
| Registrar / DNS provider | Alibaba Cloud / HiChina (万网) |
| Authoritative nameservers | `dns13.hichina.com`, `dns14.hichina.com` |
| DNS execution method | **Manual** (Commander-entered in Alibaba Cloud console; no API/CLI credentials exist in the engineering environment, by design) |
| TTL | 600 s (HiChina zone default minimum at entry time; TTL choice is not a Gate blocker) |

### 2.1 G05B DNS records (the ONLY records touched)

| Type | Host | Value | Purpose |
|---|---|---|---|
| A | `@` | `13.75.34.162` | apex → current App Service inbound IP (see §3.1) |
| TXT | `asuid` | Azure Custom Domain Verification ID (recorded in Azure; verified 2026-10-02) | apex ownership validation |
| CNAME | `www` | `mountainguardian-v1.azurewebsites.net` | www → App Service |
| TXT | `asuid.www` | Azure Custom Domain Verification ID (same value) | www ownership validation |

Pre-change zone inventory (read-only, 2026-10-02): the zone contained **no**
A / AAAA / TXT / CAA / MX records at the apex and `www` did not exist — all four
records were pure additions. **No MX / SPF / DKIM / DMARC / NS or unrelated
records were created, modified or deleted.**

The `asuid` TXT records remain in place after issuance (App Service re-validates
ownership periodically); the A and CNAME records must NEVER be removed or
re-pointed elsewhere while the managed certificates are in use — direct DNS
topology is required for certificate auto-renewal.

### 2.2 Propagation verification (2026-10-02)

Direct UDP DNS from the engineering network is blocked; verification used
DNS-over-HTTPS against two independent public resolvers (AliDNS `dns.alidns.com`
and DNSPod `doh.pub`), both matching the authoritative HiChina zone:

- `mountainguardian.cn` A → `13.75.34.162` ✓ (both resolvers)
- `asuid.mountainguardian.cn` TXT → verification ID ✓
- `www.mountainguardian.cn` CNAME → `mountainguardian-v1.azurewebsites.net` → `13.75.34.162` ✓
- `asuid.www.mountainguardian.cn` TXT → verification ID ✓

## 3. Azure Resources (existing, unchanged)

| Item | Value |
|---|---|
| Subscription | SchoolSub-026 |
| Resource Group | `rg-mountainguardian-v1` |
| App Service Plan | `asp-mountainguardian-v1` (B1, single instance) |
| Web App | `mountainguardian-v1` (Linux, `PYTHON|3.12`) |
| Region | East Asia (`eastasia`) |
| Default hostname | `mountainguardian-v1.azurewebsites.net` (kept, fallback) |

### 3.1 Inbound IP note

For this Linux B1 stamp the ARM property `inboundIpAddress` returns empty;
`possibleInboundIpAddresses = 13.75.34.162, 20.189.104.112`. The authoritative
resolution of `mountainguardian-v1.azurewebsites.net` (`waws-prod-hk1-031`
stamp) returns `13.75.34.162`, which is the value used for the apex A record.
Values were read live from the actual Azure resource at Gate time — never
from memory.

If Azure ever migrates the app's stamp, the A record must be updated to the
new inbound IP (managed-certificate renewal tolerates brief drift, but HTTP
traffic would break). Re-read the live value with:

```bash
az rest --method GET --url "https://management.azure.com/subscriptions/<sub>/resourceGroups/rg-mountainguardian-v1/providers/Microsoft.Web/sites/mountainguardian-v1?api-version=2022-09-01" \
  --query "{inbound:properties.inboundIpAddress,possible:properties.possibleInboundIpAddresses}"
```

## 4. Custom-Domain Binding & Ownership Validation (2026-10-02)

Performed with the current Azure CLI (no Portal-only steps):

```bash
az webapp config hostname add --webapp-name mountainguardian-v1 \
  -g rg-mountainguardian-v1 --hostname www.mountainguardian.cn
az webapp config hostname add --webapp-name mountainguardian-v1 \
  -g rg-mountainguardian-v1 --hostname mountainguardian.cn
```

Result: BOTH hostnames returned `hostNameType: "Verified"` — Azure's own
ownership validation passed via the `asuid` TXT records (DNS resolution alone
was NOT treated as verification).

Site hostnames after binding: `mountainguardian.cn`,
`www.mountainguardian.cn`, `mountainguardian-v1.azurewebsites.net` (default
hostname NOT removed).

## 5. TLS — App Service Managed Certificates

Free App Service Managed Certificates (no commercial/paid/Key Vault/wildcard/
third-party certificate). Current CLI path (note: the older `--to-hostname`
flag no longer exists; `ssl show` is resource-group-level):

```bash
az webapp config ssl create -g rg-mountainguardian-v1 -n mountainguardian-v1 \
  --hostname mountainguardian.cn
az webapp config ssl create -g rg-mountainguardian-v1 -n mountainguardian-v1 \
  --hostname www.mountainguardian.cn
az webapp config ssl show -g rg-mountainguardian-v1 --certificate-name <hostname>
az webapp config ssl bind -g rg-mountainguardian-v1 -n mountainguardian-v1 \
  --certificate-thumbprint <thumbprint> --ssl-type SNI
```

| Hostname | Issuer | Valid | Thumbprint | SSL state |
|---|---|---|---|---|
| `mountainguardian.cn` | GeoTrust TLS RSA CA G1 (DigiCert) | 2026-10-02 → 2027-04-02 | `405097F57FAEBB68DA825B2A9FD89C2ECC31B7D0` | `SniEnabled` |
| `www.mountainguardian.cn` | GeoTrust TLS RSA CA G1 (DigiCert) | 2026-10-02 → 2027-04-02 | `4B31B6DF97C143EDA229882D87138A574E3ECD09` | `SniEnabled` |

- SNI binding on the multitenant stamp (normal for shared App Service).
- Managed Certificates auto-renew while the direct DNS topology (§2.1) stays
  intact — do NOT switch `www` to an intermediate CNAME or the apex to a CDN.
- The zone has **no CAA records**; issuance succeeded without any CAA change.
  If future issuance ever fails on CAA, identify the CURRENT Azure CA
  requirement from live Azure documentation before touching CAA — never
  broaden CAA casually.

## 6. HTTPS / Redirect Verification (2026-10-02)

| Check | Result |
|---|---|
| `https://mountainguardian.cn` | 200, TLS verify OK (valid chain, CN=mountainguardian.cn) |
| `https://mountainguardian.cn/_stcore/health` | 200 `ok` |
| `http://mountainguardian.cn` | 301 → `https://mountainguardian.cn/` (single hop, no loop) |
| `https://www.mountainguardian.cn` | 200, TLS verify OK (CN=www.mountainguardian.cn) |
| `https://www.mountainguardian.cn/_stcore/health` | 200 `ok` |
| `http://www.mountainguardian.cn` | 301 → `https://www.mountainguardian.cn/` (single hop, no loop) |
| `https://mountainguardian-v1.azurewebsites.net` (fallback) | 200 — default hostname intact |
| Web App `httpsOnly` | `true` (unchanged; platform-enforced) |
| `minTlsVersion` | 1.2 (unchanged) |

## 7. Product Smoke on Brand Domain (2026-10-02)

Method: headless Microsoft Edge (Playwright, local engineering tooling — not
committed to the repository) driving `https://mountainguardian.cn` as a real
browser client; screenshots + DOM probes stored in `D:\HenryFord-AI\mg-g05b-evidence\`.

Four-page smoke (root hostname `https://mountainguardian.cn`, one continuous
browser session — same binding, same app):

| Page | Result |
|---|---|
| Overview 总览 | PASS — 200; Leaflet map renders; persisted production state loads (LAST SCAN + historical trend rows from production SQLite); no traceback, no console errors |
| Historical Replay 历史验证 | PASS — PRE-EVENT / EVENT / POST-EVENT timeline renders; honest baseline labeling; no traceback |
| Risk Watch 风险监测 | PASS — page renders; primary CTA `立即执行风险扫描 · Run Risk Scan` present and functional (used for the live scan below); no traceback |
| Intelligence Center 智能中心 | PASS — Agent Workspace / Evidence Center / Audit sections render; MODEL RUNTIME `Connected`; no traceback |

Cross-cutting checks: no Host-header problem; no TLS warning (valid
certificate chain in a real browser); no redirect loop; **zero failed
sub-requests** (no 4xx/5xx assets); DOM probe found **no `sk-` secret
material** on any page. `www` hostname verified separately at HTTP level
(200 / health `ok` / single-hop 301) — same binding to the same app, so the
full four-page retest was not repeated there (Gate-allowed minimum: root +
health + Overview equivalent).

System chip reads `DEGRADED` — honest disclosure because the optional Remote
Sensing source is MISSING (no usable new satellite imagery); identical
frozen behavior to G05A, not a domain/TLS defect.

### 7.1 Brand-domain production Risk Watch scan (UI-triggered)

One legitimate scan executed by clicking the frozen CTA in the real browser
against `https://mountainguardian.cn` (full chain: custom domain → Streamlit
→ Open-Meteo → DeepSeek → deterministic engine → Agents → Synthesizer →
Critic → persistent SQLite). Runtime values — C/O7 are transparent
deterministic prototype heuristic state indicators, **not probabilities**:

| Field | Value |
|---|---|
| run_id | `rw-20261002T135255147418Z-d43b612a` (2026-10-02T13:52:50Z → 13:53:54Z) |
| Mode / Status | LIVE / `COMPLETED_WITH_LIMITATIONS` (6 limitations disclosed in UI) |
| C | **85.54** |
| O7 | **72.01** |
| direction | **STABLE** (Δ −1.42 vs previous scan, frozen ±5-point rule) |
| Providers | Open-Meteo `AVAILABLE GOOD` (Source Zone, Port Zone, climatology); DeepSeek `CONNECTED`, model `deepseek-flash` |
| Agents | Glacier & Geology **LIVE** model-output (16.4 s); Weather & Hydrology **LIVE** model-output (16.1 s); Remote Sensing **SKIPPED** deterministic-fallback (no imagery — frozen design) |
| Synthesizer | **LIVE** model-output (7.3 s) |
| Critic | **LIVE** model-output (17.7 s); verdict `NEEDS_REVISION` / severity `WARNING` (honest review output rendered as-is) |
| SQLite | new snapshot row persisted and re-rendered in Overview + Historical Trend without reload tricks |

Evidence (screenshots, DOM text dumps, probe scripts, result JSON):
`D:\HenryFord-AI\mg-g05b-evidence\` (outside the repository, like G05A).

## 8. Runtime Dependencies After Domain Binding

Verified from the brand-domain production application after binding (scan
`rw-20261002T135255147418Z-d43b612a`):

- **DeepSeek: CONNECTED / LIVE** — all four model roles (2 Agents,
  Synthesizer, Critic) returned real model output (`deepseek-flash`,
  latencies 7.3–17.7 s), no fallback in the model layer.
- **Open-Meteo: AVAILABLE** — `AVAILABLE GOOD` for Source Zone and Port Zone
  (recent + forecast + 1991–2020 climatology from `/home/data` cache).
- **SQLite: readable/writable under `/home/data`** — the production scan
  wrote its snapshot row to `/home/data/mountainguardian.db` and the app
  re-rendered it (Overview LAST SCAN + Risk Watch historical trend, alongside
  earlier persisted scans of the day).

No credentials were changed during G05B.

## 9. Rollback Procedure (G05B — must NOT disturb G05A)

Failure of the custom domain NEVER touches the production application:
`https://mountainguardian-v1.azurewebsites.net` remains the emergency path
throughout, and no G05B step modifies app code, SQLite, or the DeepSeek key.

Diagnose → correct DNS/binding → revalidate, in escalating order:

1. **TLS/hostname problem, binding sound:** re-check DNS values (§2.2) and
   certificate state (`az webapp config ssl show ...`); re-bind if needed.
2. **Broken hostname binding:** remove ONLY the affected binding —
   `az webapp config hostname delete -g rg-mountainguardian-v1 -n mountainguardian-v1 --hostname <bad-hostname>`
   — leaving the other hostname, the default hostname and the app untouched.
3. **Bad certificate:** `az webapp config ssl delete` (RG-level, by
   certificate name) for the affected hostname only, then re-create/re-bind.
4. **DNS regression:** correct the specific record in Alibaba Cloud console
   (never bulk-edit; never touch NS/MX).
5. **Absolute worst case:** delete both custom bindings + certificates; site
   continues serving on `*.azurewebsites.net` exactly as after G05A.

Forbidden during any G05B rollback: deleting the Web App, changing product
code, resetting `/home/data` SQLite, rotating credentials, rolling back G05A
architecture, disabling the default hostname.

## 10. Operational Notes

- Health path `/_stcore/health` measures Streamlit process health only (same
  as G05A) — provider state lives in the product's Audit & Safety.
- B1 single instance; cold start after idle ~10–20 s applies to all hostnames.
- If the domain ever needs to move to another App Service: add the new
  binding + certificate FIRST, then re-point DNS, then clean up — never the
  reverse order.
- Renewal: App Service Managed Certificates renew automatically ~around
  expiry (current validity ends 2027-04-02). Monitor via Azure Portal →
  TLS/SSL settings; no action needed while §2.1 topology holds.
