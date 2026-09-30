# MountainGuardian Battle Plan v1.0
## 山河守望者 v1.0 Claude Code 执行作战计划（冻结版）

**文档状态：** FROZEN / 已冻结  
**Commander：** ChatGPT  
**Engineering Executor：** Claude Code  
**目标仓库：** `D:\HenryFord-AI\MountainGuardian`  
**目标版本：** MountainGuardian v1.0  
**已购买正式域名：** `mountainguardian.cn`  

**上位冻结依据：**
- `00_MountainGuardian_Project_Foundation_v1.0.md`
- `01_MountainGuardian_Product_Requirements_v1.0.md`
- `02_MountainGuardian_Scientific_Data_Baseline_v1.0.md`
- `03_MountainGuardian_AI_Agent_Architecture_v1.0.md`
- `04_MountainGuardian_Risk_Watch_Design_v1.0.md`
- `05_MountainGuardian_UI_UX_Design_Spec_v1.0.md`
- `06_MountainGuardian_Engineering_Deployment_Spec_v1.0.md`

**视觉参考：**
- `docs/mountainguardian_v1/assets/ui_reference_geospatial_intelligence.png`

---

# 1. Battle Plan 目的

本文不再讨论 MountainGuardian“应该做什么”。

00–06 已经冻结：

- 产品范围；
- 科学边界；
- 数据规则；
- AI / Agent 架构；
- Risk Watch 公式；
- UI/UX 方向；
- 工程与部署原则。

本文只回答：

> **Claude Code 应该按什么顺序、在哪个 branch / worktree、以什么边界、通过哪些测试，把 MountainGuardian v1.0 一步一步实现出来。**

---

# 2. 两角色执行模型

项目开发阶段只保留两个实时角色。

## ChatGPT — Commander / Design Authority

负责：

- 维护冻结设计；
- 决定 Gate 顺序；
- 根据 Battle Plan 生成每个 Gate 的一键复制 Claude Code Prompt；
- 在启动 Prompt 中补充当时真实的 HEAD、模型名称等动态信息；
- 阅读 Claude Code Execution Report；
- 判定 PASS / REMEDIATION / BLOCKED；
- 只有当前 Gate CLOSED 后才发下一 Gate Prompt。

ChatGPT 不直接：

- 改仓库代码；
- 创建 branch；
- 建 worktree；
- 跑测试；
- commit；
- push；
- merge；
- deploy。

## Claude Code — Sole Engineering Executor

Claude Code 负责完整执行链：

> Entry Check → Worktree → Implementation → Test → Runtime Verification → Commit → Push → PR → Merge → Main Regression → Worktree Cleanup → Gate Report

不再设置独立 Developer / Tester / Merger / Deployment Operator。

---

# 3. Gate 状态

统一使用：

```text
NOT_STARTED
IN_PROGRESS
REMEDIATION
PASS
BLOCKED
CLOSED
```

含义：

- `PASS`：功能与测试通过，但 cleanup / Commander review 可能尚未完成；
- `CLOSED`：已经 merge main、main regression PASS、worktree cleanup 完成，并被 Commander 接受。

只有 `CLOSED` 后才能进入下一 Gate。

---

# 4. 每个 Gate 的 Claude Code Conversation Contract

默认：

> **每个 Gate 新开一个 Claude Code Conversation。**

同一 Gate 的：

- 开发；
- 测试；
- commit；
- push；
- PR；
- merge；
- main regression；
- worktree cleanup；

都在同一个 Conversation 中完成。

跨 Gate 不延续旧 Conversation，除非 Commander 明确要求。

---

# 5. Commander 每次必须提供的启动元数据

每次实际启动 Gate 时，ChatGPT 必须提供一个完整的一键复制 Prompt，并在最前面写明：

```text
Conversation Name:
Tool / Role:
New Conversation or Continue:
Model:
Thinking Level:
Permission / Bypass Setting:

Main Repository:
Conversation Start Repository:
Base Branch:
Feature Branch:
Worktree:
Active Working Directory:
Current Main HEAD:

Current Gate:
Gate Objective:
Entry Condition:
Allowed Scope:
Prohibited Scope:
Required Tests:
Live Verification:
Git Actions:
Merge Requirement:
Worktree Cleanup Requirement:
Exit Condition:
```

Battle Plan 中的 HEAD、具体 Claude 模型名称等属于：

> **Launch-time Dynamic Fields**

不得现在写死。

---

# 6. Claude Code 模型与思考强度原则

默认：

```text
Model:
当前 Claude Code 客户端中可用的最强稳定 coding model

Thinking Level:
High
```

以下 Gate 可以使用 Medium：

- G00 Governance Bootstrap；
- 非复杂文档 / Git 清理。

涉及以下内容必须 High：

- Provider；
- Agent；
- leakage；
- deterministic risk；
- Risk Watch；
- UI architecture；
- Azure deployment；
- release regression。

真正启动 Gate 时，Commander 应根据当时 Claude Code UI 中实际可用模型填写具体模型名称。

---

# 7. Permission 原则

默认：

```text
Standard / Normal permissions
```

不默认启用 unrestricted bypass。

如 Gate 需要：

- GitHub PR / merge；
- Azure CLI；
- 网络 live test；

这些属于该 Gate 明确授权范围，但不等于允许 Claude Code 无边界操作系统或其他仓库。

---

# 8. Worktree 总规则

Main Repository：

```text
D:\HenryFord-AI\MountainGuardian
```

所有 Gate worktree：

```text
D:\HenryFord-AI\MountainGuardian\.worktrees\
```

一个 Gate 一个 worktree。

Gate merge 后：

```text
remove worktree
→ prune
→ delete merged local feature branch
→ confirm main clean
```

默认同时只保留一个 active Gate worktree。

## Gate Conversation 的工作目录规则

每个新 Gate 的 Claude Code Conversation：

```text
Start:
D:\HenryFord-AI\MountainGuardian
branch = main
```

先完成只读 Entry Check，并由 Claude Code 创建：

```text
feature branch
+
D:\HenryFord-AI\MountainGuardian\.worktrees\<gate-worktree>
```

worktree 创建后，同一个 Conversation 的 Active Working Directory 切换为该 worktree。

实际实现、测试、commit、push 必须发生在 worktree。

主仓库 `main` 只允许用于：

```text
Entry Check / Bootstrap
Merge
Main Regression
Worktree Cleanup
```

这样无需用户手工提前创建 worktree，也不需要为同一个 Gate 再开第二个 Claude Code Conversation。

---

# 9. G00 特殊 Bootstrap 规则

第一次创建内部 `.worktrees/` 时存在 bootstrap 问题：

> `.worktrees/` 还没有进入 tracked `.gitignore`。

因此 G00 允许在 main 仓库的本地 `.git/info/exclude` 中先临时加入：

```text
.worktrees/
```

该文件不是 Git tracked content。

然后：

```text
create G00 worktree
→ 在 G00 branch 中正式修改 tracked .gitignore
→ merge main
```

G00 完成后，后续 Gate 不再需要该特殊处理。

---

# 10. Gate 总览

| Gate | Conversation | Branch | Worktree | Thinking | 核心产物 |
|---|---|---|---|---|---|
| G00 | MG-v1 G00 — Governance Baseline | `chore/v1-governance-baseline` | `.worktrees/g00-governance` | Medium | 冻结文档、UI reference、worktree治理、baseline |
| G01 | MG-v1 G01 — Model Provider | `feature/model-provider` | `.worktrees/g01-model-provider` | High | DeepSeek Provider + structured model runtime |
| G02A | MG-v1 G02A — Professional Agents | `feature/agent-professionals` | `.worktrees/g02a-professional-agents` | High | 3专业Agent + Schema +受控Context |
| G02B | MG-v1 G02B — Synthesis & Critic | `feature/agent-synthesis-critic` | `.worktrees/g02b-synthesis-critic` | High | Risk Synthesizer + Critic + Historical Replay Stage A/B |
| G03A | MG-v1 G03A — Risk Watch Data | `feature/risk-watch-data` | `.worktrees/g03a-risk-watch-data` | High | region config + weather + climatology + snapshots |
| G03B | MG-v1 G03B — Risk Watch Engine | `feature/risk-watch-engine` | `.worktrees/g03b-risk-watch-engine` | High | B/R/F/D/C/O7 + trend + What Changed |
| G03C | MG-v1 G03C — Risk Watch Workflow | `feature/risk-watch-workflow` | `.worktrees/g03c-risk-watch-workflow` | High | End-to-end Run Risk Scan |
| G03O | MG-v1 G03O — Satellite Optional | `feature/risk-watch-satellite` | `.worktrees/g03o-satellite` | High | Optional STAC discovery + RS Agent live vision |
| G04A | MG-v1 G04A — UI Foundation | `feature/ui-foundation` | `.worktrees/g04a-ui-foundation` | High | Design system + nav + map + Overview |
| G04B | MG-v1 G04B — Product Pages | `feature/ui-product-pages` | `.worktrees/g04b-ui-product-pages` | High | Historical Replay + Risk Watch + Intelligence Center |
| G05A | MG-v1 G05A — Azure Core Deployment | `feature/azure-core-deploy` | `.worktrees/g05a-azure-core` | High | CI/CD + App Service + azurewebsites URL |
| G05B | MG-v1 G05B — Custom Domain & HTTPS | `feature/custom-domain` | `.worktrees/g05b-custom-domain` | High | 品牌域名 + HTTPS |
| G06 | MG-v1 G06 — Release Candidate | `release/v1.0-rc` | `.worktrees/g06-release` | High | full regression + rc + final tag |

`G03O` 为：

> **Optional Enhancement Gate**

只有 G03C CLOSED 且时间允许时执行。

如果跳过，不影响 v1.0 P0 完成。

---

# 11. G00 — Governance Baseline

## Conversation

```text
MG-v1 G00 — Governance Baseline
```

## New Conversation

Yes.

## Thinking

Medium.

## Branch

```text
chore/v1-governance-baseline
```

## Conversation Start Repository

```text
D:\HenryFord-AI\MountainGuardian
```

Start branch:

```text
main
```

Claude Code first performs Entry Check and creates the dedicated G00 worktree.

## Worktree / Active Working Directory

After bootstrap:

```text
D:\HenryFord-AI\MountainGuardian\.worktrees\g00-governance
```

All tracked G00 changes must be made in this worktree.

## Objective

建立 v1.0 正式工程治理基线，不修改产品功能。

## Entry Conditions

用户已经把以下内容放入主仓库：

- 00–07 当前版本文档；
- `assets/ui_reference_geospatial_intelligence.png`；
- 所有文件名和路径符合冻结规范。

主仓库：

- branch = main；
- working tree 状态已确认；
- origin 可访问。

## Bootstrap

如 `.worktrees/` 尚未 tracked ignore：

在 main 本地：

```text
.git/info/exclude
```

临时增加：

```text
.worktrees/
```

然后创建 G00 worktree。

## Allowed Scope

- `docs/mountainguardian_v1/`
- `.gitignore`
- 与文档组织有关的 README / index（如有必要）
- 不改变运行代码。

## Required Work

1. 验证 00–07 文件齐全；
2. 验证 UI reference asset 路径；
3. `.gitignore` 加：
   ```text
   .worktrees/
   ```
4. 检查 Secret / `.env` ignore；
5. 记录当前 baseline HEAD；
6. 安装现有 requirements；
7. `pip check`；
8. full pytest；
9. Streamlit baseline health smoke；
10. Historical Replay baseline smoke；
11. Commit / push / PR / merge；
12. main regression；
13. worktree cleanup。

## Prohibited

- Agent 重构；
- Provider 接入；
- Risk Watch 实现；
- UI 重构；
- dependency upgrade。

## Acceptance

- 00–07 + reference image 在 main；
- `.worktrees/` tracked ignore；
- baseline tests = 0 failed；
- Streamlit = healthy；
- Historical Replay still PASS；
- main clean；
- G00 worktree removed。

---

# 12. G01 — Real Model Provider

## Conversation

```text
MG-v1 G01 — Model Provider
```

## New Conversation

Yes.

## Thinking

High.

## Branch

```text
feature/model-provider
```

## Worktree

```text
D:\HenryFord-AI\MountainGuardian\.worktrees\g01-model-provider
```

## Objective

接入真实 DeepSeek 模型，同时不改变现有 Historical Replay 科学逻辑。

## Core Deliverables

- `ModelProvider` abstraction；
- `DeepSeekProvider`；
- `deepseek-flash` 配置；
- structured generation；
- multimodal capability interface；
- provider health state；
- error classification；
- bounded retry；
- one bounded schema repair；
- deterministic fallback；
- audit fields；
- mock provider tests；
- opt-in live test。

## Secret Contract

Local live test：

```text
BWS_ACCESS_TOKEN
→ Bitwarden Secrets Manager
→ bws run
→ DEEPSEEK_API_KEY
```

Claude Code：

- 只检查环境变量存在；
- 不显示 Secret；
- 不请求用户粘贴 Secret；
- 不写入文件 / log / report。

## Required Tests

- provider unit tests；
- mocked structured output；
- invalid JSON；
- schema repair；
- auth error；
- timeout；
- 429；
- 5xx；
- fallback；
- no Secret leak；
- existing regression suite。

## Live Verification

显式 opt-in：

- actual DeepSeek request；
- model ID accepted；
- structured response parse PASS；
- latency logged；
- Secret not printed。

## Prohibited

- 重写 Agent workflow；
- 第二 Provider；
- GPT reviewer；
- Risk Watch；
- UI redesign。

## Acceptance

- real DeepSeek call PASS；
- mock CI path PASS；
- fallback PASS；
- full pytest 0 failed；
- Historical Replay unchanged；
- PR merged；
- main regression PASS；
- worktree removed。

---

# 13. G02A — Professional Agent Core

## Conversation

```text
MG-v1 G02A — Professional Agents
```

## Branch

```text
feature/agent-professionals
```

## Worktree

```text
.worktrees/g02a-professional-agents
```

## Objective

把 v0.1 规则型 Agent 升级为三个职责明确的专业 Agent，并建立统一结构化输入输出。

## Deliverables

- EvidenceItem Schema；
- AnalysisContext；
- Glacier / Geology Agent；
- Weather / Hydrology Agent；
- Remote Sensing Agent；
- status enum；
- confidence；
- missing data；
- Evidence ID referencing；
- minimum necessary context；
- Historical Replay pre-event context filter；
- mock + real Provider adapter wiring。

## Remote Sensing Rule

Historical Replay：

- pre-event imagery only during risk analysis。

无图：

```text
SKIPPED
```

不伪造结果。

## Tests

- Schema；
- context filtering；
- evidence permissions；
- post-event blocked；
- independent professional outputs；
- Agent failure isolation；
- Remote Sensing SKIP；
- fallback；
- full regression。

## Prohibited

- Risk Synthesizer redesign；
- Critic redesign；
- Risk Watch；
- UI redesign。

## Acceptance

3 专业 Agent：

- independent；
- structured；
- evidence-linked；
- phase-safe；
- mock test PASS；
- live DeepSeek smoke PASS；
- full regression PASS；
- merge + cleanup。

---

# 14. G02B — Risk Synthesizer & Critic

## Conversation

```text
MG-v1 G02B — Synthesis & Critic
```

## Branch

```text
feature/agent-synthesis-critic
```

## Worktree

```text
.worktrees/g02b-synthesis-critic
```

## Objective

完成 v1.0 多智能体闭环。

## Deliverables

### Deterministic Historical Risk

- 保持 Case Pack 91/100 可复算；
- LLM 不修改分数。

### Risk Synthesizer

输入：

- professional Agent outputs；
- deterministic Risk Engine；
- evidence coverage；
- data quality；
- missing data。

输出：

- risk explanation；
- top drivers；
- agent agreement；
- limitations。

### Critic

检查：

- evidence；
- leakage；
- causal overclaim；
- probability misuse；
- missing data；
- disagreement；
- satellite overclaim。

### Historical Replay Two-stage Freeze

```text
Stage A
Pre-event analysis
→ Synthesizer
→ Critic
→ Freeze Result

Stage B
Load post-event evidence
→ Validation only
```

Stage B 不得回写 Stage A Risk Index。

## Tests

- 91/100 regression；
- Stage A no leakage；
- Stage B cannot alter Stage A；
- prohibited probability claim；
- agreement/disagreement；
- Critic verdict enums；
- model failure；
- schema repair；
- full pytest。

## Runtime Acceptance

完整 Historical Replay：

> Real model → professional agents → deterministic risk → synthesizer → critic → post-event validation

PASS。

## Exit

merge → main regression → remove worktree。

---

# 15. G03A — Risk Watch Data Foundation

## Conversation

```text
MG-v1 G03A — Risk Watch Data
```

## Branch

```text
feature/risk-watch-data
```

## Worktree

```text
.worktrees/g03a-risk-watch-data
```

## Objective

先把 Risk Watch 的真实数据底座做稳，不调用完整 Agent 流程。

## Deliverables

### Region Config

```text
data/regions/jilong_port/region.json
```

包含：

- region metadata；
- Source Zone；
- Port Zone；
- static terrain；
- cryosphere baseline；
- historical hazard baseline；
- scoring config version；
- provenance。

### Weather Collector

Open-Meteo / frozen source：

- past 7 days；
- future 7 days；
- temperature；
- precipitation；
- metadata；
- timeout；
- retry；
- cache。

### Climatology

1991–2020：

- historical weather；
- monthly 7-day precipitation percentile baseline；
- local cache；
- reproducibility。

### Snapshot Schema

- immutable new records；
- run_id；
- source metadata；
- missing data；
- quality。

## Tests

- mock weather；
- normalization；
- 2 monitoring points；
- partial point failure；
- all point failure；
- cache；
- climatology percentile；
- snapshot create；
- no overwrite；
- provenance；
- no post-event data path。

## Live Test

真实 Open-Meteo request。

## Prohibited

- risk formula UI；
- final Risk Watch orchestration；
- UI redesign；
- satellite optional gate。

---

# 16. G03B — Risk Watch Deterministic Engine

## Conversation

```text
MG-v1 G03B — Risk Watch Engine
```

## Branch

```text
feature/risk-watch-engine
```

## Worktree

```text
.worktrees/g03b-risk-watch-engine
```

## Objective

实现 04 冻结文档中的透明、可复现动态风险算法。

## Required Formula

```text
B = Regional Static Susceptibility Baseline

R = Recent 7-Day Precipitation Percentile
F = Forecast 7-Day Precipitation Percentile

D = 0.60 × R + 0.40 × F

C = 0.70 × B + 0.30 × D

O7 = 0.70 × B + 0.30 × F
```

Risk Level：

```text
0–39     LOW
40–59    MODERATE
60–79    ELEVATED
80–100   HIGH
```

Risk Direction：

```text
ΔC >= +5       RISING
-5 < ΔC < +5   STABLE
ΔC <= -5       FALLING
first scan     NO_HISTORY
```

## Deliverables

- Static Baseline calculation；
- B/R/F/D/C/O7；
- risk bands；
- direction；
- historical trend query；
- What Changed deterministic comparison；
- top driver contribution objects。

## Tests

必须完整覆盖：

- normal；
- boundaries；
- first scan；
- missing Required；
- optional missing；
- repeated input；
- determinism；
- trend；
- no probability；
- no LLM dependency。

## Acceptance

相同输入：

> always same result。

公式与 04 文档逐项一致。

---

# 17. G03C — Risk Watch End-to-End Workflow

## Conversation

```text
MG-v1 G03C — Risk Watch Workflow
```

## Branch

```text
feature/risk-watch-workflow
```

## Worktree

```text
.worktrees/g03c-risk-watch-workflow
```

## Objective

把 G03A + G03B 与 G02 Agent 闭合成真正的：

> `run_risk_scan(region_id)`

## Workflow

```text
Collect
→ Normalize
→ Validate
→ Store Snapshot
→ Compare
→ Professional Agents
→ Deterministic Engine
→ Synthesizer
→ Critic
→ Persist Result
```

## Requirements

- 核心 scan 函数不依赖 Streamlit session；
- UI rerun 不自动触发；
- Required weather failure = incomplete；
- Optional evidence missing = continue；
- DeepSeek failure = deterministic + fallback；
- run_id 全链；
- audit；
- historical trend only real snapshots。

## Minimal UI

只允许增加：

> 功能性 minimal Risk Watch trigger / debug view

不做最终视觉重构。

最终 UI 留到 G04。

## Tests

- successful scan；
- first scan；
- second scan trend；
- model failure；
- required weather failure；
- partial point failure；
- snapshot persistence；
- run idempotency；
- full regression。

## Live Acceptance

至少完成 1 次真实：

> Open-Meteo + DeepSeek Risk Scan

并持久化 Snapshot。

---

# 18. G03O — Optional Satellite Enhancement

**Gate Type：Optional**

执行条件：

- G03C CLOSED；
- 核心 Risk Watch 稳定；
- 进度允许。

## Conversation

```text
MG-v1 G03O — Satellite Optional
```

## Objective

增加 Risk Watch 的卫星增强证据，但绝不让它成为核心依赖。

## Deliverables

- Copernicus STAC discovery；
- `sentinel-2-l2a`；
- acquisition metadata；
- cloud cover；
- quality bands；
- optional preview / asset；
- Remote Sensing Agent vision path；
- explicit AI Visual Observation。

## Skip Rules

```text
No new scene
→ SKIPPED_NO_NEW_IMAGERY

Cloud > threshold
→ SKIPPED_LOW_QUALITY_IMAGERY
```

Risk Watch 必须继续。

## Acceptance

Satellite 成功或 SKIP：

> 都不会改变核心 C / O7 公式，也不会阻塞 scan。

---

# 19. G04A — UI Foundation & Overview

## Conversation

```text
MG-v1 G04A — UI Foundation
```

## Branch

```text
feature/ui-foundation
```

## Worktree

```text
.worktrees/g04a-ui-foundation
```

## Objective

按照选定第二套效果图和 05 UI Spec，建立正式商业级界面基础。

## Mandatory Reference

```text
docs/mountainguardian_v1/assets/ui_reference_geospatial_intelligence.png
```

参考：

- visual language；
- map-first layout；
- color；
- density；
- agent spatial relationship。

不复制：

- 示例数字；
- 未冻结功能；
- 3D GIS。

## Deliverables

- global dark design system；
- left navigation；
- top header；
- reusable cards；
- status chips；
- typography；
- 2D geospatial map；
- Overview；
- Current Risk card；
- Agent Collaboration；
- quick entries；
- loading / empty / error / fallback states。

## Technical Rule

继续 Streamlit。

不迁 React / Next。

## Tests / Review

- existing tests；
- Streamlit startup；
- key page load；
- visual screenshot；
- 1280 / 1440 layout smoke；
- no fake data；
- no science language regression。

---

# 20. G04B — Historical Replay, Risk Watch & Intelligence Center

## Conversation

```text
MG-v1 G04B — Product Pages
```

## Branch

```text
feature/ui-product-pages
```

## Worktree

```text
.worktrees/g04b-ui-product-pages
```

## Objective

完成 05 UI Spec 中剩余正式产品页面。

## Deliverables

### Historical Replay

- Pre / Event / Post timeline；
- Evidence；
- Agent reasoning；
- 91/100 Baseline Susceptibility；
- Critic；
- Post-event Validation。

### Risk Watch

- Run Risk Scan CTA；
- progress；
- Current Risk；
- 7-Day Outlook；
- Historical Trend；
- What Changed；
- Data Coverage。

### Intelligence Center

Tabs：

- Agent Workspace；
- Evidence Center；
- Audit & Safety。

## UI Prohibitions

- 大红科普 banner；
- probability misuse；
- fake future trend；
- fake satellite；
- official warning terminology；
- 3D GIS。

## Acceptance

05 文档 69 节全部 UI acceptance 条目逐项核对。

并保存 05 文档建议的 10 张验收截图。

---

# 21. G05A — Azure Core Deployment

## Conversation

```text
MG-v1 G05A — Azure Core Deployment
```

## Branch

```text
feature/azure-core-deploy
```

## Worktree

```text
.worktrees/g05a-azure-core
```

## Objective

让 MountainGuardian 在 Azure App Service Linux 上稳定公开运行。

## Entry

- G04B CLOSED；
- local full regression PASS；
- production candidate code on main。

## Deliverables

- Azure App Service Linux；
- Python 3.12；
- single instance；
- startup command；
- `/home/data` runtime；
- SQLite persistence；
- App Settings；
- `DEEPSEEK_API_KEY` production secret；
- GitHub Actions CI/CD；
- health check；
- default HTTPS URL。

## Local vs Azure Secrets

Local：

```text
Bitwarden → bws run → DEEPSEEK_API_KEY
```

Azure：

```text
App Service Settings → DEEPSEEK_API_KEY
```

GitHub Actions：

> no DeepSeek key。

## CI/CD

```text
checkout
→ python setup
→ install
→ pip check
→ pytest
→ deploy
→ smoke check
```

## Production Acceptance

- `https://<app>.azurewebsites.net` = 200；
- `/_stcore/health` = 200；
- Overview；
- Historical Replay；
- Risk Watch；
- SQLite persistence；
- DeepSeek live；
- Open-Meteo live；
- Audit no Secret；
- redeploy does not wipe runtime DB。

## Prohibited

- PostgreSQL；
- Docker；
- Key Vault；
- multi-instance；
- custom domain in this Gate。

---

# 22. G05B — Custom Domain & HTTPS

## Conversation

```text
MG-v1 G05B — Custom Domain & HTTPS
```

## Branch

```text
feature/custom-domain
```

## Worktree

```text
.worktrees/g05b-custom-domain
```

## Objective

把已经稳定的 Azure App 映射到 MountainGuardian 已购买正式品牌域名：

```text
mountainguardian.cn
```

最终比赛展示主入口目标：

```text
https://mountainguardian.cn
```

如 Azure / DNS 实施阶段发现根域名绑定存在额外限制，可保留：

```text
https://www.mountainguardian.cn
```

作为兼容入口，但主品牌域名仍为：

```text
mountainguardian.cn
```

## Entry

- G05A CLOSED；
- `mountainguardian.cn` 已购买；
- 用户可以管理该域名 DNS。

## Work

- read Azure current verification values；
- 为 `mountainguardian.cn` 配置所需 DNS A / CNAME / TXT；
- 如使用 `www.mountainguardian.cn`，同步配置对应 CNAME / verification；
- Azure custom domain verification；
- App Service managed TLS；
- HTTPS only；
- final branded URL；
- keep `azurewebsites.net` fallback。

## Acceptance

- `mountainguardian.cn` DNS resolves；
- Azure ownership verification PASS；
- HTTPS certificate active；
- `https://mountainguardian.cn` = 200；
- `https://mountainguardian.cn/_stcore/health` = 200；
- Overview / Historical Replay / Risk Watch PASS；
- HTTP redirects HTTPS；
- Azure default `azurewebsites.net` URL remains available as fallback；
- 如配置 `www.mountainguardian.cn`，其跳转或访问行为明确且可验证。

## Rule

Custom Domain 失败：

> 不回滚 G05A Core Deployment。

记录为独立 remediation。

---

# 23. G06 — Release Candidate & Competition Freeze

## Conversation

```text
MG-v1 G06 — Release Candidate
```

## Branch

```text
release/v1.0-rc
```

## Worktree

```text
.worktrees/g06-release
```

## Objective

不再增加功能，只做完整验证、必要 blocker fix、证据固化和 release。

## Full Regression

### Code

- pip check；
- full pytest；
- leakage tests；
- risk formula；
- provider fallback；
- snapshots；
- UI smoke。

### Historical Replay

完整走一遍。

### Risk Watch

真实 Run Risk Scan 一次。

### Azure

- default `azurewebsites.net` URL；
- `https://mountainguardian.cn`；
- health；
- persistence；
- DeepSeek；
- Open-Meteo。

### Secret Audit

确认 repo 不含：

- DeepSeek key；
- BWS token；
- Azure secret；
- `.env`。

### UX

保存最终 10 张产品截图。

## Release Candidate

建议：

```text
v1.0-rc1
```

若发现 blocker：

```text
fix within release branch
→ tests
→ rc2
```

不增加 feature。

## Final Release

通过后：

```text
mountainguardian-v1.0
```

Git tag。

## Competition Freeze

Tag 后：

> 只接受 blocker fix。

比赛报告、视频、截图、在线系统应对应同一 release。

---

# 24. 每个 Gate 的统一 Entry Checklist

Claude Code 必须先从主仓库 `main` 报告：

```text
Main Repository
Conversation Start Repository
Main Branch
Main HEAD
Working Tree Status
git worktree list
Planned Feature Branch
Planned Worktree Path
Python Version
Git Version
pytest baseline
```

Entry Check 通过后，Claude Code 自己创建 feature branch + worktree，并报告：

```text
Created Feature Branch
Created Worktree
Active Working Directory
```

并读取：

> 当前 Gate 真正相关的 00–07 文档章节。

不得在 Entry Check 未完成时直接改代码。

---

# 25. 每个 Gate 的统一 Prohibitions

所有 Gate 默认禁止：

- 修改不相关模块；
- 改动冻结科学事实；
- 修改已冻结公式；
- 添加 v1.1 功能；
- 删除测试逃避失败；
- 把 mock 结果伪装 live；
- 写 Secret；
- force delete worktree；
- force push main；
- squash 掉必要的科学数据版本历史；
- 在 main 直接开发。

---

# 26. 每个 Gate 的统一 Test Rule

至少：

```text
Gate-specific tests
+
full existing regression
```

Gate 最后：

```text
0 failed
```

如有：

```text
skipped
```

必须说明为何合理。

Live test 与 unit tests 分开报告。

---

# 27. 每个 Gate 的统一 Git Closure

Claude Code 在功能 PASS 后必须继续完成：

```text
commit
push
PR
merge
update main
main critical regression
remove worktree
prune
delete merged local branch
verify main clean
```

不能把：

> “代码写完了”

当成 Gate 完成。

---

# 28. 每个 Gate 的统一 Claude Code Execution Report

报告模板：

```text
# MountainGuardian Gate Execution Report

## A. Gate
## B. Verdict
PASS / PASS WITH LIMITATIONS / BLOCKED / FAIL

## C. Entry State
- main HEAD
- branch
- worktree
- clean status

## D. Implemented Scope

## E. Files Changed

## F. Tests
- command
- result
- pass/fail/skip

## G. Live Verification

## H. Scientific / Security Checks

## I. Git Actions
- commit
- push
- PR
- merge commit

## J. Main Regression

## K. Worktree Cleanup

## L. Known Limitations

## M. Exit State
- main HEAD
- main clean
- worktree list
```

Report 中不得包含 Secret。

---

# 29. Commander Review Rule

用户把 Claude Code Report 发回 ChatGPT 后：

ChatGPT 必须判定：

```text
ACCEPT
REMEDIATE
BLOCKED
```

### ACCEPT

Gate CLOSED，可以生成下一个 Gate Prompt。

### REMEDIATE

继续当前 Claude Code Conversation。

Commander 给：

> bounded remediation prompt。

不创建下一 Gate。

### BLOCKED

停止执行链，分析 blocker。

如果 blocker 说明冻结设计不可实现：

> 修改对应 00–06 文档并重新冻结，再更新 Battle Plan。

---

# 30. Battle Plan 的减法原则

执行过程中不得“顺手加入”：

- 第二模型；
- GPT Reviewer；
- Vector DB；
- RAG 平台；
- MCP 重构；
- DeepSeek Harness；
- 30 天预测；
- 季节预测；
- 自动周扫描；
- PostgreSQL；
- Docker；
- 3D GIS；
- 用户账户；
- 真实预警发送。

这些不是“以后顺便做”，而是：

> **明确不属于 v1.0 Battle Plan。**

---

# 31. Recommended Critical Path

如果时间紧，严格优先：

```text
G00
↓
G01
↓
G02A
↓
G02B
↓
G03A
↓
G03B
↓
G03C
↓
G04A
↓
G04B
↓
G05A
↓
G06
```

可跳过：

```text
G03O Satellite Optional
G05B Custom Domain
```

其中 G05B 已对应已购买域名 `mountainguardian.cn`，属于最终比赛展示的推荐完成项。

---

# 32. Definition of v1.0 Complete

MountainGuardian v1.0 只有同时满足以下条件才算完成：

## Historical

- real model；
- 3 professional Agents；
- deterministic 91/100；
- Synthesizer；
- Critic；
- no leakage；
- post-event validation。

## Risk Watch

- real weather；
- climatology；
- Snapshot；
- deterministic B/R/F/D/C/O7；
- Current Risk；
- 7-Day Outlook；
- Historical Trend；
- real model explanation；
- Critic。

## UI

- selected Geospatial Intelligence direction；
- 4 main entries；
- 2D map；
- agent collaboration；
- evidence；
- audit；
- fallback states。

## Engineering

- full tests；
- clean Git history；
- dedicated worktrees；
- all worktrees cleaned；
- Azure online；
- `https://mountainguardian.cn` 作为正式品牌入口；
- Azure default URL 保留为 fallback；
- Secret safe；
- release tag。

---

# 33. Battle Plan Freeze Rule

本文冻结后：

> 不再在执行过程中随意重新安排 Gate 或扩大范围。

允许修改 Battle Plan 的情况：

1. 实际代码结构出现不可预见 blocker；
2. 官方 API / Azure 平台发生重大变化；
3. 冻结设计被证明存在科学或工程错误；
4. Commander 明确决定做 scope reduction。

修改时：

> Battle Plan 升版并重新冻结。

---

# 34. 正式品牌域名冻结

MountainGuardian v1.0 已购买并冻结正式品牌域名：

```text
mountainguardian.cn
```

目标生产入口：

```text
https://mountainguardian.cn
```

Azure 默认：

```text
https://<app-name>.azurewebsites.net
```

继续作为：

> **Core Deployment 验收地址与生产备用入口。**

域名本身已确定，不在后续 Gate 中重新选择品牌域名。

---

# 35. 下一步启动规则

Battle Plan v1.0 冻结并放入：

```text
docs/mountainguardian_v1/
```

后：

1. 用户确认 00–07 和 UI Reference 均已保存到 Repository；
2. 用户把冻结文档上传到 Project Sources；
3. ChatGPT Commander 生成：
   > **G00 — Governance Baseline**
   的完整一键复制 Claude Code 启动提示词；
4. 新开 Claude Code Conversation：
   > `MG-v1 G00 — Governance Baseline`
5. 从此严格按 Gate 执行。

---

# 36. 一句话 Battle Plan

> **MountainGuardian v1.0 按“治理基线 → 真实模型 → 专业 Agent → 综合与复核 → Risk Watch 数据 → 确定性风险引擎 → Risk Watch 全流程 → UI → Azure → Release”的 Gate 顺序推进；每个 Gate 均在独立 feature branch 与 repo 内 `.worktrees/` 工作区完成，由 Claude Code 独立承担开发、测试、commit、push、PR、merge、main regression 和 worktree cleanup，并由 ChatGPT Commander 审核后才能进入下一 Gate。**
