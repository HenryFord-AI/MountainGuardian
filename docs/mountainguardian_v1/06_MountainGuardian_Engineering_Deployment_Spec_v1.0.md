# MountainGuardian Engineering & Deployment Specification v1.0
## 山河守望者 v1.0 工程与部署规范（冻结版）

**文档状态：** FROZEN / 已冻结  
**上位依据：**
- `00_MountainGuardian_Project_Foundation_v1.0.md`
- `01_MountainGuardian_Product_Requirements_v1.0.md`
- `02_MountainGuardian_Scientific_Data_Baseline_v1.0.md`
- `03_MountainGuardian_AI_Agent_Architecture_v1.0.md`
- `04_MountainGuardian_Risk_Watch_Design_v1.0.md`
- `05_MountainGuardian_UI_UX_Design_Spec_v1.0.md`

**目标产品版本：** MountainGuardian v1.0  
**目标仓库：** `D:\HenryFord-AI\MountainGuardian`  
**目标部署平台：** Azure App Service on Linux  
**目标运行栈：** Python 3.12.x + Streamlit + SQLite  
**文档目的：** 冻结 v1.0 的工程治理、仓库结构、分支与 Git 流程、依赖管理、配置与 Secret、Provider 接入、测试体系、数据持久化、日志与审计、Health Check、GitHub Actions、Azure 部署、回滚与最终工程验收标准。  
**非本文件范围：** 不定义各阶段具体 Claude Code 执行 Prompt；具体实施顺序由 `07_MountainGuardian_Battle_Plan_v1.0.md` 冻结。

---

# 1. 工程目标

MountainGuardian v1.0 的工程实现必须同时满足：

1. `main` 始终可运行；
2. 每个开发 Gate 都可独立验证；
3. 真实模型和真实数据接入不破坏 deterministic fallback；
4. Secret 不进入 Git；
5. 数据、模型、Agent、Risk、Critic 全过程可追踪；
6. 本地与 Azure 尽量使用同一代码路径；
7. 在线版本可由评审通过公开 URL 访问；
8. 任何外部 API 或模型故障都不能导致系统伪造结果；
9. 不为了部署引入大规模技术栈迁移；
10. 工程复杂度服从比赛版本的投入产出比。

---

# 2. 技术栈冻结

v1.0 继续使用：

```text
Python 3.12.x
Streamlit
SQLite
pytest
requests / httpx（按现有代码最小变更选择）
Git
GitHub
GitHub Actions
Azure App Service Linux
```

v1.0 不迁移：

- React；
- Next.js；
- Vue；
- FastAPI 主站重写；
- Docker / Kubernetes；
- PostgreSQL；
- Redis；
- Vector Database；
- Terraform；
- Azure Key Vault；
- Azure Container Apps。

除非现有代码存在无法绕过的 blocker，否则 Battle Plan 不得引入上述迁移。

---

# 3. 当前仓库基线

Repository Root：

```text
D:\HenryFord-AI\MountainGuardian
```

当前系统已经具备：

- Streamlit 可运行；
- SQLite 可运行；
- Jilong Demo v0.1；
- BaseAgent / Coordinator；
- Case Loader；
- Jilong Agents；
- Historical Replay；
- 自动化测试；
- 数据泄漏专项测试。

Battle Plan 启动前必须重新确认：

```text
git status
git branch --show-current
git rev-parse HEAD
pytest
```

不在本文件冻结某一个 HEAD commit，因为 00–06 文档加入仓库后 HEAD 会继续变化。

---

# 4. v1.0 设计文档与 Worktree 目录

冻结：

```text
D:\HenryFord-AI\MountainGuardian\
├── .git/
├── .gitignore
├── .worktrees/
│   └── <current-gate-worktree>/
├── docs/
│   └── mountainguardian_v1/
│       ├── 00_MountainGuardian_Project_Foundation_v1.0.md
│       ├── 01_MountainGuardian_Product_Requirements_v1.0.md
│       ├── 02_MountainGuardian_Scientific_Data_Baseline_v1.0.md
│       ├── 03_MountainGuardian_AI_Agent_Architecture_v1.0.md
│       ├── 04_MountainGuardian_Risk_Watch_Design_v1.0.md
│       ├── 05_MountainGuardian_UI_UX_Design_Spec_v1.0.md
│       ├── 06_MountainGuardian_Engineering_Deployment_Spec_v1.0.md
│       ├── 07_MountainGuardian_Battle_Plan_v1.0.md
│       └── assets/
│           └── ui_reference_geospatial_intelligence.png
└── ...
```

Worktree 统一集中在：

```text
D:\HenryFord-AI\MountainGuardian\.worktrees\
```

`.gitignore` 必须包含：

```text
.worktrees/
```

原则：

> 所有临时开发 worktree 都集中在主项目目录内部的 `.worktrees/`，禁止在 `D:\HenryFord-AI\` 或其他目录到处创建零散 worktree。

`docs/mountainguardian_v1/` 中只保留当前有效冻结版本。

旧讨论稿不需要长期保留在仓库中，因为 Git 已经承担版本历史。

---

# 5. 数据目录职责

运行数据与设计文档分开。

```text
data/
├── cases/
│   └── jilong_20260826/
├── regions/
│   └── jilong_port/
└── runtime/
```

含义：

- `cases/`：Historical Replay 数据；
- `regions/`：Risk Watch 区域静态配置；
- `runtime/`：本地运行时产生的 Snapshot / SQLite / Cache（具体路径由配置决定）。

Historical Replay 与 Risk Watch 不得共用同一完整输入文件。

---

# 6. Git Branch + Worktree 原则

所有功能开发必须：

> **从最新且 clean 的 `main` 创建独立 feature branch，并为该 Gate 创建独立 dedicated worktree。**

主仓库固定为：

```text
D:\HenryFord-AI\MountainGuardian
```

主仓库职责：

> **只承担 `main` 基线、merge 后回归验证和 worktree 管理，不作为日常功能开发目录。**

每个 Gate 的开发目录固定放在：

```text
D:\HenryFord-AI\MountainGuardian\.worktrees\
```

命名建议：

```text
feature/model-provider
.worktrees/g01-model-provider

feature/agent-v2
.worktrees/g02-agent-v2

feature/risk-watch
.worktrees/g03-risk-watch

feature/ui-v2
.worktrees/g04-ui-v2

feature/azure-deploy
.worktrees/g05-azure-deploy
```

如 Battle Plan 进一步拆分 Gate，可继续使用：

```text
feature/risk-watch-weather
.worktrees/g03a-risk-watch-weather
```

不在一个长期巨型分支中完成整个 v1.0。

同一时间默认只保留：

> **1 个 active Gate worktree**

除非 ChatGPT Commander 明确批准并行 Gate。

---

# 7. 每个 Gate 的 Git + Worktree 流程

冻结流程：

```text
Main Repository Clean
↓
Update main
↓
Create Feature Branch
↓
Create Dedicated Worktree under .worktrees/
↓
Claude Code works only inside that worktree
↓
Implement bounded scope
↓
Run tests
↓
Runtime verification
↓
Review diff
↓
Commit
↓
Push
↓
Create / update PR
↓
Merge PR to main
↓
Update main repository
↓
Run critical regression on main
↓
Remove Gate worktree
↓
git worktree prune
↓
Verify .worktrees/ is clean
```

一个 Gate 未完成：

> **merge + main regression + worktree cleanup**

不得进入下一 Gate。

---

# 8. `main` 分支原则

`main` 必须始终：

- 可安装；
- 可测试；
- 可启动；
- Historical Replay 不被破坏；
- 无 Secret；
- 无未解决 blocker。

禁止：

- 直接在 `main` 进行大范围开发；
- 多个未验证 Gate 一次性 merge；
- 为赶进度跳过测试后继续开发。

---

# 9. Commit 原则

每个 Gate 至少一个明确 commit。

Commit message 示例：

```text
Add DeepSeek provider abstraction
Implement professional agent workflow
Add Risk Watch weather snapshots
Add Risk Watch deterministic engine
Redesign MountainGuardian UI
Add Azure App Service deployment
```

不使用：

```text
update
fix stuff
final
test
```

等无法追踪的提交说明。

---

# 10. PR 原则

每个 PR 至少包含：

- Scope；
- Changed files；
- Tests run；
- Runtime verification；
- Known limitations；
- Security / data leakage impact；
- Acceptance verdict。

Battle Plan 可以为 Claude Code 提供固定 PR 模板。

---

# 11. Working Tree 原则

每个新 Gate 启动时，主仓库：

```text
D:\HenryFord-AI\MountainGuardian
```

必须执行：

```text
git status
git branch --show-current
git worktree list
```

要求：

- 主仓库当前分支为 `main`；
- `main` working tree = clean；
- 不存在上一个 Gate 遗留的 active worktree；
- 如存在用户未提交文件，Claude Code 不得自行删除、覆盖或 stash，必须停在 Gate Entry Check。

---

# 11A. Worktree 生命周期

每个 Gate 必须遵循：

```text
Create → Use → Merge → Regression → Remove → Prune
```

建议创建方式：

```text
git worktree add .worktrees/gXX-<gate-name> -b feature/<branch-name> main
```

开发期间：

> Claude Code 的所有代码修改、测试、commit 都只能在该 Gate worktree 内完成。

禁止：

- 在主仓库 `main` 直接改功能代码；
- 在仓库外部建立散落 worktree；
- 一个 Gate merge 后继续保留无用途 worktree；
- Claude Code 自己决定长期保留 worktree。

---

# 11B. Worktree Cleanup 是 Gate Exit Condition

PR merge 后，Claude Code 必须从主仓库路径执行：

```text
git -C D:\HenryFord-AI\MountainGuardian pull --ff-only
git -C D:\HenryFord-AI\MountainGuardian worktree remove .worktrees/gXX-<gate-name>
git -C D:\HenryFord-AI\MountainGuardian worktree prune
git -C D:\HenryFord-AI\MountainGuardian worktree list
```

随后确认：

- 对应 worktree 已不存在；
- `.worktrees/` 中没有该 Gate 残留；
- `main` clean；
- main regression PASS。

只有这些条件满足，Gate 才正式 CLOSED。

如 worktree 中仍有未提交修改：

> **不得使用 `--force` 静默删除。**

Claude Code 必须先说明残留内容并停止 cleanup，等待 Commander 判断。

---

# 12. Python 版本

v1.0 本地当前基线：

> **Python 3.12.x**

Azure App Service 使用：

> **Python 3.12 Linux runtime**

保持本地 / CI / Azure 主版本一致。

不在 v1.0 开发中升级到新的 Python major/minor，除非部署平台出现明确 blocker。

---

# 13. Dependency Management

继续使用：

```text
requirements.txt
```

不迁移 Poetry / uv / Conda。

要求：

- 所有新增运行依赖进入 `requirements.txt`；
- 所有测试依赖明确可安装；
- 每个 Gate 运行 `pip check`；
- 避免为了一个小功能引入大型依赖包；
- 地图 / UI 组件优先选择维护稳定、依赖少的方案。

---

# 14. Dependency Upgrade 原则

v1.0 不进行“顺便全部升级”。

新增功能时：

> **Minimum Necessary Dependency Change**

只有：

- 安全问题；
- Python 3.12 不兼容；
- Azure blocker；
- 必需 API；

才升级已有核心依赖。

升级后必须跑完整 regression。

---

# 15. 配置分层

系统配置分为：

## A. Non-secret Configuration

可以进入 Git：

```text
model_id
base_url
timeouts
risk thresholds
cloud cover threshold
cache duration
region config path
db logical path
log level
```

## B. Secret Configuration

绝对不能进入 Git：

```text
DEEPSEEK_API_KEY
Azure deployment credential
future private API keys
```

---

# 16. 环境变量命名建议

建议统一：

```text
MOUNTAINGUARDIAN_ENV
DEEPSEEK_API_KEY
DEEPSEEK_BASE_URL
DEEPSEEK_MODEL
MOUNTAINGUARDIAN_DB_PATH
MOUNTAINGUARDIAN_RUNTIME_DIR
MOUNTAINGUARDIAN_LOG_LEVEL
```

默认：

```text
DEEPSEEK_MODEL=deepseek-flash
```

代码不得把 DeepSeek key 写入默认配置。

---

# 17. 本地 Secret 管理

MountainGuardian v1.0 正式采用：

> **Bitwarden Secrets Manager 作为本地开发 Secret Source of Truth。**

Windows 用户环境中允许长期保存：

```text
BWS_ACCESS_TOKEN
```

其用途仅为让 Bitwarden Secrets Manager CLI（`bws`）访问被授权的 Project / Secret。

DeepSeek 真正的模型访问密钥：

```text
DEEPSEEK_API_KEY
```

保存在 Bitwarden Secrets Manager 中，不作为 Windows 持久环境变量长期保存。

正式链路：

```text
Windows User Environment
└── BWS_ACCESS_TOKEN
        │
        ▼
Bitwarden Secrets Manager
└── MountainGuardian Project
        └── DEEPSEEK_API_KEY
                │
                ▼
             bws run
                │
                ▼
Current Claude Code / pytest live test / Streamlit process
└── DEEPSEEK_API_KEY
                │
                ▼
MountainGuardian
└── os.environ["DEEPSEEK_API_KEY"]
```

核心原则：

> **MountainGuardian 代码本身不直接集成 Bitwarden SDK，也不调用 Bitwarden API。应用只读取标准环境变量。**

推荐本地 live runtime 方式：

```text
bws run --project-id <MOUNTAINGUARDIAN_PROJECT_ID> -- <command>
```

例如：

```text
bws run --project-id <MOUNTAINGUARDIAN_PROJECT_ID> -- streamlit run app.py
```

如 Claude Code 从命令行启动，也可由同样方式启动，使其子进程继承 `DEEPSEEK_API_KEY`。

普通单元测试和 GitHub Actions CI：

> **不需要 `DEEPSEEK_API_KEY`，使用 mock / deterministic provider。**

只有显式 live integration test 才要求真实模型 Secret。

安全要求：

- `BWS_ACCESS_TOKEN` 和 `DEEPSEEK_API_KEY` 均不得进入 Git；
- 不得写入 `.py`；
- 不得写入 committed `.env`；
- 不得写入 SQLite；
- 不得写入日志；
- 不得写入 Gate Report；
- 不得写入截图；
- 不得粘贴到 Claude Code Conversation；
- 不得在 terminal 中 echo secret value；
- Claude Code 只允许检查环境变量是否存在，不得显示其内容。

Bitwarden Machine Account 应遵循：

> **Minimum Necessary Access**

即只授予 MountainGuardian 所需 Project / Secret 权限，不授予无关 Secret 访问权限。

---

# 18. `.env` 原则

v1.0 不依赖 `.env` 才能运行。

正式本地 Secret 注入优先级：

```text
Bitwarden Secrets Manager
→ bws run
→ process environment
```

如果开发者临时使用：

```text
.env
.env.local
```

必须加入 `.gitignore`，且不得作为正式开发流程依赖。

正式推荐：

> **process environment only**

---

# 19. Azure Secret 管理

Azure Production 不依赖 Bitwarden。

v1.0 使用：

> **Azure App Service Application Settings / Environment Variables**

保存：

```text
DEEPSEEK_API_KEY
DEEPSEEK_MODEL
other runtime secrets
```

因此本地与生产环境对应用代码保持完全一致的 Secret 接口：

```text
Local:
Bitwarden → bws run → DEEPSEEK_API_KEY

Azure:
App Service Settings → DEEPSEEK_API_KEY

Application:
os.environ["DEEPSEEK_API_KEY"]
```

Azure App Service Application Settings 在运行时作为环境变量提供给应用，并在平台侧静态加密。

v1.0 不强制：

- Azure Key Vault；
- Managed Identity。

Key Vault 作为 v1.1 安全增强。

---

# 20. GitHub Secret 边界

GitHub Actions Secret 只保存 CI/CD 必须的部署凭据，例如：

```text
AZURE_WEBAPP_PUBLISH_PROFILE
```

DeepSeek API Key 不需要复制到 GitHub Actions。

原因：

> CI 自动测试应默认使用 mock / deterministic provider，不应为了 unit tests 调用真实付费模型。

---

# 21. Provider 工程边界

真实大模型通过轻量 Provider abstraction。

逻辑：

```text
agents
  ↓
ModelProvider
  ↓
DeepSeekProvider
  ↓
DeepSeek API
```

Agent 不直接：

- 拼 URL；
- 管理 API Key；
- 自己实现 retry；
- 自己解析 HTTP error。

---

# 22. Provider Error Classification

至少区分：

```text
AUTH_ERROR
TIMEOUT
RATE_LIMIT
SERVICE_UNAVAILABLE
INVALID_RESPONSE
SCHEMA_ERROR
UNKNOWN_PROVIDER_ERROR
```

这些错误进入：

- Audit；
- Fallback；
- UI runtime state。

不能直接显示 raw Secret / response header。

---

# 23. HTTP Timeout

外部 API 必须设置显式 timeout。

包括：

- DeepSeek；
- Open-Meteo；
- Copernicus。

禁止无限等待。

具体 timeout 数值由 Battle Plan 实现并通过运行测试调整。

---

# 24. Retry 原则

只允许 bounded retry。

建议：

```text
network / 429 / 5xx:
max 1–2 retry

schema repair:
max 1 repair
```

禁止：

- 无限重试；
- Agent 无限 reflection；
- 页面卡死。

---

# 25. 外部 API 数据采集

Collector 与 Agent 分离。

Collector 负责：

```text
HTTP
parse
normalize
validate
cache
provenance
```

Agent 只读 Collector 输出。

LLM 不直接承担：

> 网络数据采集器。

---

# 26. Network Mocking

CI 测试默认不依赖外网。

测试方式：

```text
mock DeepSeek response
mock Open-Meteo response
mock Copernicus response
```

这样 GitHub Actions 不会因：

- 网络波动；
- API 限流；
- Token 成本；

随机失败。

---

# 27. Live Integration Test

真实 API 测试必须是：

> **explicit / opt-in**

例如：

```text
RUN_LIVE_TESTS=1
```

默认：

```text
pytest
```

不得调用真实付费模型。

Live tests 用于：

- 本地 Gate 验证；
- Azure smoke test；
- Provider 接入首次验证。

---

# 28. 测试分层

v1.0 至少有四层测试。

## Layer 1 — Unit

测试：

- schema；
- formula；
- phase filter；
- risk thresholds；
- data normalization；
- fallback。

## Layer 2 — Integration with Mock

测试：

- Coordinator；
- Agents；
- Provider adapter；
- Collector；
- Snapshot。

## Layer 3 — Live Smoke

测试：

- DeepSeek；
- Open-Meteo；
- optional Copernicus。

## Layer 4 — UI / Runtime Smoke

测试：

- Streamlit 启动；
- health endpoint；
- 页面关键流程；
- Run Risk Scan。

---

# 29. Regression Baseline

当前已有 pytest baseline 必须继续保持。

每个 Gate：

> **不能以新增测试通过为理由接受旧测试回归。**

最终要求：

```text
0 failed
```

如旧测试必须修改：

> PR 必须解释为什么测试语义需要变化。

---

# 30. Scientific Regression Tests

必须长期保留：

- post-event leakage；
- Risk Index ≠ Probability；
- 91/100 Historical Replay 复算；
- Stage B 不回写 Stage A；
- Optional satellite 缺失不阻塞；
- Required weather 缺失不伪造风险；
- Historical Trend 不读取未来数据。

---

# 31. Risk Watch Formula Tests

必须覆盖：

```text
B
R
F
D
C
O7
Risk Level
Risk Direction
```

至少测试：

- normal；
- boundary；
- missing；
- first snapshot；
- repeated snapshot。

公式值不能依赖 LLM。

---

# 32. Output Schema Tests

每个 Agent：

- valid JSON；
- invalid JSON；
- missing field；
- invalid enum；
- confidence > 1；
- unknown evidence ID；
- forbidden probability claim。

均应有测试。

---

# 33. Runtime Mode

建议统一：

```text
MOUNTAINGUARDIAN_ENV=local
MOUNTAINGUARDIAN_ENV=azure
```

不通过代码分支实现两套产品。

只有：

- path；
- secrets；
- deployment configuration；

不同。

---

# 34. SQLite 原则

v1.0 继续使用 SQLite。

原因：

- 当前用户并发极低；
- 数据量小；
- 已有 schema；
- 已有 audit；
- 迁移数据库投入产出比低。

不引入 PostgreSQL。

---

# 35. Azure SQLite 部署边界

v1.0 Azure App Service 固定：

> **单实例运行**

不横向 scale-out。

原因：

- SQLite 是本地文件数据库；
- 当前并发负载不需要多实例；
- 避免多实例文件锁与一致性复杂度。

---

# 36. SQLite 持久化路径

本地可以使用：

```text
data/runtime/mountainguardian.db
```

Azure 使用独立持久路径，例如：

```text
/home/data/mountainguardian.db
```

实际通过：

```text
MOUNTAINGUARDIAN_DB_PATH
```

配置。

数据库不得依赖代码部署目录中的相对位置来保证持久性。

---

# 37. Azure `/home` 使用原则

Azure App Service Linux 的 `/home` 用作持久化文件区域。

v1.0 可用于：

- SQLite；
- Risk Watch Snapshot；
- runtime cache；
- small generated metadata。

不使用：

- Azure Files mounted share 作为 SQLite 数据库位置；
- 临时容器目录保存需要长期存在的 Snapshot。

---

# 38. 数据初始化

Azure 首次部署：

如果数据库不存在：

> 自动初始化 schema。

如果存在：

> 不覆盖。

部署流程不得把一个空数据库文件覆盖已有运行数据库。

---

# 39. Snapshot 保存

Risk Watch Snapshot：

- 先写入 SQLite / runtime storage；
- 新 Snapshot 只新增；
- 不覆盖旧记录；
- 每条有 run_id；
- 数据版本可追溯。

可选：

> 同时保存小型 JSON snapshot 作为调试 evidence。

但 v1.0 不要求双写。

---

# 40. 数据备份

v1.0 不建设复杂备份平台。

最低要求：

- SQLite 位于持久目录；
- 重要比赛演示前手工下载一次数据库备份；
- Case Pack / region config 全部在 Git。

Risk Watch runtime Snapshot 丢失不影响 Historical Replay。

---

# 41. Logging

分两类。

## Application Log

输出：

- startup；
- collector error；
- provider error；
- scan lifecycle；
- deployment runtime error。

写 stdout / stderr，供 Azure Log Stream 查看。

## Audit Log

写入 SQLite：

- run_id；
- agent；
- model；
- evidence；
- status；
- fallback；
- latency；
- risk result。

---

# 42. Logging 禁止内容

日志不得记录：

- API key；
- Azure credential；
- 完整 Secret header；
- 用户 Bitwarden 内容；
- 敏感 Authorization header。

HTTP debug logging 默认关闭。

---

# 43. Health Check

Streamlit 官方提供：

```text
/_stcore/health
```

v1.0 Azure App Service Health Check 使用该 endpoint。

部署验收必须确认：

```text
GET /_stcore/health
HTTP 200
```

---

# 44. Health Check 的含义

Health Check 只判断：

> Web application process 是否正常服务。

不要求每次 Health Check：

- 调 DeepSeek；
- 调 Open-Meteo；
- 下载卫星；
- 查询所有外部 API。

否则会：

- 增加费用；
- 增加误报；
- 让健康检查依赖第三方。

外部 Provider 状态单独在 Audit & Safety 展示。

---

# 45. Streamlit Startup

Azure App Service 属于非 Flask / Django 的自定义 Python Web server 场景，因此需要显式 startup command。

必须满足：

```text
streamlit run app.py
--server.address=0.0.0.0
--server.headless=true
--server.port=<Azure-compatible port>
```

Battle Plan 部署 Gate 中必须在目标 App Service 上实际验证 startup command 和 port。

不依赖 App Service 对 Flask / Django 的自动检测。

---

# 46. Startup File

推荐把 startup command 版本化保存为：

```text
startup.sh
```

或：

```text
startup.txt
```

避免只在 Azure Portal 手工配置而仓库没有记录。

文件必须位于部署包可访问的位置。

---

# 47. Azure 部署形态

v1.0 使用：

> **Azure App Service — Linux Code Deployment**

不使用自定义 Docker Container。

理由：

- Python App Service 原生支持；
- 依赖简单；
- GitHub Actions 接入成熟；
- 降低比赛版运维工作量。

---

# 48. Azure Runtime

目标：

```text
Linux
Python 3.12
Single Instance
```

SKU 具体选择不在本文件冻结。

标准：

- 能稳定运行 Streamlit；
- 能访问外部 DeepSeek / Open-Meteo；
- 内存足够；
- 费用可接受。

Battle Plan 部署时根据用户当前 Azure Subscription 实际可用计划决定。

---

# 49. HTTPS

Azure Core Deployment 的第一验收地址：

```text
https://<app-name>.azurewebsites.net
```

必须通过 HTTPS 并独立满足核心运行验收。

MountainGuardian v1.0 最终比赛展示目标进一步升级为：

```text
https://<custom-domain>
```

但：

> **Custom Domain 不阻塞 Core Deployment。**

自定义域名和证书绑定在独立 Custom Domain Gate 中完成。

---

# 50. Authentication

比赛 v1.0：

> **不启用用户登录。**

原因：

- 评委需要直接打开；
- 产品不包含个人敏感数据；
- 无真实外部预警动作；
- 降低演示风险。

如果公开访问存在成本或滥用风险，可在后续增加简单保护，但不属于 P0。

---

# 50A. Custom Domain 定位

v1.0 最终展示计划使用：

> **自定义品牌域名 + HTTPS**

但 Custom Domain：

> **不是核心开发和 Azure Core Deployment 的前置依赖。**

正式部署流程分为：

```text
Stage A — Azure Core Deployment
→ https://<app-name>.azurewebsites.net
→ runtime / health / Historical Replay / Risk Watch PASS

Stage B — Custom Domain & HTTPS
→ bind custom domain
→ enable managed TLS certificate
→ verify branded HTTPS URL
```

因此：

> **即使 DNS / 域名绑定临时失败，也不得阻塞 Azure Core Deployment 的验收。**

---

# 50B. 域名准备原则

用户可以提前注册目标域名。

优先品牌方向：

```text
mountainguardian.<TLD>
```

例如：

```text
mountainguardian.ai
```

如根域名使用和 DNS 管理复杂度较高，比赛版可以优先绑定：

```text
app.mountainguardian.<TLD>
```

或：

```text
www.mountainguardian.<TLD>
```

域名注册商与 Azure Hosting 解耦。

只要求：

> **用户拥有该域名，并能管理 DNS records。**

---

# 50C. DNS 与 Azure 绑定原则

Custom Domain Gate 中，Claude Code / Azure Operator 根据 Azure Portal 当日提供的验证值配置。

常见：

## Subdomain

```text
CNAME
app → <app-name>.azurewebsites.net

TXT
asuid.app → <Azure verification ID>
```

## Root Domain

可能需要：

```text
A
@ → <Azure App Service IP>

TXT
asuid → <Azure verification ID>
```

具体 DNS record 以 Azure 当日 Portal / 官方文档返回为准，不在代码中硬编码。

---

# 50D. HTTPS

Custom Domain 验证通过后：

> 配置 Azure App Service Managed Certificate 或当前 Azure 推荐的等价托管 TLS 方案。

最终用户访问必须使用：

```text
https://<custom-domain>
```

HTTP 应自动重定向 HTTPS。

v1.0 不要求：

- 自定义商业证书；
- 自定义 CA；
- 自己维护证书续期流程。

---

# 50E. Custom Domain Gate 验收

至少检查：

1. DNS ownership verification PASS；
2. custom domain 绑定 PASS；
3. HTTPS certificate ACTIVE；
4. `https://<custom-domain>` = 200；
5. `/_stcore/health` 通过 custom domain = 200；
6. Overview 正常；
7. Historical Replay 正常；
8. Risk Watch 页面正常；
9. HTTP → HTTPS；
10. Azure 默认 `azurewebsites.net` URL 仍可作为备用访问地址。

---

# 51. GitHub Actions 目标

GitHub Actions 负责：

```text
Checkout
→ Setup Python
→ Install Dependencies
→ Run Tests
→ Package / Build
→ Deploy to Azure
→ Smoke Check
```

部署必须发生在测试通过之后。

---

# 52. CI 与 CD 分阶段

Azure Gate 完成前：

> GitHub Actions 可以先只运行 CI。

Azure Gate 完成后：

> `main` merge 触发 CI + deployment。

这样前四个开发 Gate 不会因为 Azure 尚未准备好而阻塞。

---

# 53. GitHub Actions Trigger

最终 v1.0 建议：

```text
on push to main
```

含义：

> PR merge 到 main 后，自动运行测试并部署。

如测试失败：

> 不部署。

---

# 54. GitHub Actions Authentication

v1.0 采用低复杂度方式：

> **Azure Web App Publish Profile**

存入 GitHub Actions Secret：

```text
AZURE_WEBAPP_PUBLISH_PROFILE
```

Future 可以升级为：

- OIDC；
- Service Principal。

v1.0 不为此增加额外 IAM 配置工作。

---

# 55. GitHub Actions Security

Workflow：

- 不 echo secrets；
- 不输出 publish profile；
- 不上传 `.env`；
- 不把 runtime DB 打包进 artifact；
- 不把 Bitwarden Secret 引入 CI；
- Actions 版本在实施时选择官方维护版本，并尽可能固定到稳定版本 / SHA。

---

# 56. Build Automation

Python App Service 部署必须确保：

```text
requirements.txt
```

位于项目根目录，使 Azure build 能安装依赖。

如果使用 App Service build automation：

```text
SCM_DO_BUILD_DURING_DEPLOYMENT=1
```

具体 workflow 在 Battle Plan Azure Gate 中实现和验证。

---

# 57. Deployment Artifact

部署内容应排除：

- `.venv/`
- local SQLite；
- local runtime cache；
- screenshots 临时输出；
- `.env`
- secrets；
- test artifacts；
- large reference DOCX / XLSX（如不需要运行）。

Historical Replay 所需：

```text
data/cases/jilong_20260826/
```

和：

```text
data/regions/jilong_port/
```

必须进入部署 artifact。

---

# 58. `.gitignore`

必须至少覆盖：

```text
.venv/
.env
.env.*
__pycache__/
.pytest_cache/
data/runtime/
*.db-journal
*.db-shm
*.db-wal
```

但必须注意：

> 不得误排除正式 Case Pack 与 region config。

---

# 59. UI Reference Asset

必须纳入 Git：

```text
docs/mountainguardian_v1/assets/ui_reference_geospatial_intelligence.png
```

该文件是设计参考，不要求部署到 production runtime。

如部署 artifact 需要减小，可以在打包步骤排除 `docs/`，但源码仓库必须保留。

---

# 60. Environment Configuration

Azure App Settings 至少：

```text
MOUNTAINGUARDIAN_ENV=azure
DEEPSEEK_API_KEY=<secret>
DEEPSEEK_MODEL=deepseek-flash
MOUNTAINGUARDIAN_DB_PATH=/home/data/mountainguardian.db
MOUNTAINGUARDIAN_RUNTIME_DIR=/home/data
MOUNTAINGUARDIAN_LOG_LEVEL=INFO
```

`DEEPSEEK_BASE_URL` 如保持官方默认，可由代码安全默认值提供。

---

# 61. Provider Connectivity

Azure 部署后必须执行：

> DeepSeek live smoke test

验证：

- DNS / outbound internet；
- TLS；
- Authentication；
- model id；
- structured response。

失败时：

> 应用仍可打开，并进入 Fallback Mode。

---

# 62. Weather Connectivity

Azure 部署后必须验证：

- Open-Meteo 请求成功；
- 吉隆监测点返回数据；
- timeout / retry 正常；
- cache 正常。

天气 Required Data 完全失败时：

> Risk Scan 不生成新正式 Current Risk Index。

---

# 63. Copernicus Connectivity

Satellite 属于 Optional。

Azure 部署后：

- 能搜索 STAC：PASS；
- 不能搜索 STAC：记录 limitation，但不阻塞 v1.0 发布。

不为 Optional Satellite 阻塞整个 Azure上线。

---

# 64. Azure Health Check

App Service 配置：

```text
/_stcore/health
```

Health Check 不做 Model / Weather live calls。

另外在产品 Audit 页面维护：

```text
Model Runtime
Weather Source
Satellite Source
```

这些属于业务依赖状态，与 App Service process health 分开。

---

# 65. Runtime Smoke Test

每次 production deployment 后最低检查：

1. HTTPS URL = 200；
2. `/_stcore/health` = 200；
3. Overview 打开；
4. Historical Replay 打开；
5. SQLite 可读写；
6. Risk Watch 页面打开；
7. 如果允许 live smoke：Run Risk Scan 一次；
8. Audit 不暴露 Secret。

---

# 66. Rollback 原则

任何 production deployment 后出现：

- 页面无法启动；
- Historical Replay broken；
- 数据库无法打开；
- 大范围测试失败；

必须：

> 回滚到上一个已知可用 Git commit / deployment。

不在 production 临时手工 patch 源代码。

修复流程：

```text
rollback
→ new feature/fix branch
→ test
→ PR
→ merge
→ deploy
```

---

# 67. Database Rollback

代码 rollback 不得：

> 自动删除或重建 production SQLite。

数据库 schema 变更必须向后兼容或具有显式 migration。

v1.0 尽量避免复杂 schema migration。

---

# 68. Migration 原则

如新增表：

> `CREATE TABLE IF NOT EXISTS`

优先。

如新增列：

- migration 可重复执行；
- 不破坏旧数据；
- 有测试。

不使用破坏性：

```text
DROP TABLE
DELETE ALL
```

作为自动部署步骤。

---

# 69. Deployment Gate

Azure Deployment 必须是 Battle Plan 的后期 Gate。

进入条件：

- Model Provider 完成；
- Agent v2 完成；
- Risk Watch 完成；
- UI v2 完成；
- full pytest PASS；
- local runtime PASS。

不边开发核心功能边调 Azure。

---

# 70. Observability

v1.0 不引入复杂 observability stack。

最低使用：

- Azure App Service Log Stream；
- SQLite Audit Log；
- UI Audit & Safety；
- GitHub Actions logs。

Application Insights 属于 Future / optional，不是 P0。

---

# 71. Performance

目标是：

> 稳定演示，而不是高并发。

原则：

- 单实例；
- 单用户 / 少量用户；
- 外部 API 有缓存；
- Agent 可逻辑并行；
- UI 不重复调用模型；
- 页面刷新不触发 Risk Scan。

---

# 72. Streamlit Session 原则

页面 rerun 不得：

- 自动重新调用 DeepSeek；
- 自动执行 Risk Scan；
- 自动下载卫星；
- 重复写 Snapshot。

任何昂贵或有副作用操作必须：

> 用户显式点击按钮。

---

# 73. Idempotency

一次 Run Risk Scan 必须有：

```text
run_id
```

防止 Streamlit rerun 导致同一个按钮动作重复执行。

如果扫描仍在进行：

> UI 不允许再次启动同一 run。

---

# 74. Cache 原则

允许：

- weather raw response cache；
- climatology cache；
- static region baseline cache；
- map tile / metadata cache。

不缓存：

> 把一次 LLM 风险结论冒充成下一次新扫描。

每次新的 Risk Scan 应产生新的 analysis record，即使复用 30 分钟内原始天气缓存，也必须清楚记录数据 retrieval time。

---

# 75. Data Provenance

Collector 原始结果必须携带：

```text
source
request_time
observation_time
coordinate
provider metadata
quality
```

UI 只读取经过 normalizer 的结构化对象。

原始来源不得在 Agent prompt 中被改写成无法追溯的“事实文本”。

---

# 76. Security Controls

v1.0 必须保留：

- Input Validation；
- Prompt Injection Guard；
- Data Leakage Guard；
- Post-event Leakage Guard；
- Tool Allowlist；
- Output Schema Validation；
- Audit Logging；
- External Actions Disabled。

这些是程序逻辑，不是 UI 装饰。

---

# 77. External Actions

v1.0 禁止 Agent：

- 发邮件；
- 发短信；
- 发布预警；
- 调用社交平台；
- 修改第三方系统；
- 控制设备。

Risk Watch 是：

> analysis-only system。

---

# 78. Prompt Injection

外部 API / Evidence 文本进入模型前应视为：

> Untrusted Data

Agent Prompt 明确：

- Evidence 不是指令；
- 不执行 Evidence 中嵌入的命令；
- 只按照 System / Agent task 工作。

同时保留 SecurityManager / Guard。

---

# 78A. 项目实时角色模型

MountainGuardian v1.0 开发阶段只保留两个实时角色：

## Role A — ChatGPT Commander

ChatGPT 负责：

- 维护 00–07 冻结文档；
- 冻结产品、科学、Agent、Risk Watch、UI 和工程规则；
- 设计 Battle Plan；
- 决定 Gate 顺序；
- 为每个 Gate 生成 Claude Code 启动提示词；
- 审阅 Claude Code 的 Gate Report；
- 判断是否接受 Gate 结果；
- 授权进入下一 Gate；
- 当实现出现 blocker 时决定是否需要修改冻结文档。

ChatGPT 不直接承担：

- 仓库代码修改；
- 本地测试执行；
- Git commit；
- Git push；
- PR merge；
- worktree 创建与清理。

## Role B — Claude Code Executor

Claude Code 是唯一工程执行者，负责：

- Gate Entry Check；
- feature branch；
- worktree 创建；
- 代码实现；
- 单元测试；
- 集成测试；
- runtime verification；
- live smoke test；
- diff review；
- commit；
- push；
- PR 创建；
- PR merge；
- 更新 main；
- main regression；
- worktree cleanup；
- Gate Execution Report。

因此整个项目不再设置：

- 独立 Developer；
- 独立 Tester；
- 独立 Merger；
- 独立 Deployment Operator。

> **Claude Code 一人承担完整工程执行链，ChatGPT 只承担 Commander / Design Authority。**

---

# 78B. Claude Code Conversation 原则

默认：

> **每一个新的 Gate，创建一个新的 Claude Code Conversation。**

不跨 Gate 继续旧 Conversation，除非 ChatGPT Commander 明确要求。

原因：

- 减少上下文污染；
- 每个 Gate 目标清楚；
- 与 feature branch / worktree 一一对应；
- Gate Report 更容易审计。

同一个 Gate 内：

> **开发、测试、commit、push、PR、merge、main regression、worktree cleanup 均继续使用同一个 Claude Code Conversation。**

---

# 78C. Claude Code Conversation 命名

每个 Gate 必须有明确 Conversation Name。

标准格式：

```text
MG-v1 GXX — <Gate Name>
```

示例：

```text
MG-v1 G01 — Model Provider
MG-v1 G02 — Agent Intelligence
MG-v1 G03 — Risk Watch
MG-v1 G04 — UI/UX Redesign
MG-v1 G05 — Azure Deployment
```

如果 Gate 拆为子 Gate：

```text
MG-v1 G03A — Risk Watch Weather
MG-v1 G03B — Risk Watch Engine
```

---

# 78D. Claude Code 模型与思考强度

每次 ChatGPT Commander 输出 Claude Code 启动提示词时，必须明确写出：

```text
Model:
Thinking Level:
```

默认规则：

```text
Model: 当前 Claude Code 客户端中可用的最强稳定 coding model
Thinking Level: High
```

对于简单机械修复，Commander 可以降为：

```text
Thinking Level: Medium
```

但涉及以下任务时必须使用 High：

- 架构修改；
- Agent 工作流；
- Risk Watch 公式；
- 数据权限；
- leakage；
- provider / fallback；
- Azure deployment；
- merge 前综合验证。

如果用户客户端展示具体模型名称，Commander 在当次 Gate Prompt 中直接填写具体选择，不留模糊项。

---

# 78E. 新 Claude Code 对话启动位置与 Worktree 切换

由于每个 Gate 的 dedicated worktree 由 Claude Code 自己创建，因此新 Gate 启动时 worktree 尚不存在。

每个 Gate 新 Conversation 固定采用两阶段工作目录：

## Phase 0 — Bootstrap / Entry Check

新 Claude Code Conversation 从主仓库打开：

```text
Conversation Start Repository:
D:\HenryFord-AI\MountainGuardian

Base Branch:
main
```

该阶段只允许：

- 读取冻结文档；
- `git status` / `git branch` / `git rev-parse` / `git worktree list`；
- 验证 `main` clean；
- 必要时完成 G00 的 `.git/info/exclude` bootstrap；
- 从最新 `main` 创建该 Gate 的 feature branch + dedicated worktree。

除上述 bootstrap 动作外：

> **不得在主仓库 `main` 修改产品代码或 Gate 实现文件。**

## Phase 1 — Active Gate Work

worktree 创建完成后，同一个 Claude Code Conversation 必须把实际工程工作切换到：

```text
Worktree:
D:\HenryFord-AI\MountainGuardian\.worktrees\gXX-<gate-name>

Active Working Directory:
D:\HenryFord-AI\MountainGuardian\.worktrees\gXX-<gate-name>
```

之后以下动作全部只能发生在该 worktree：

- implementation；
- tests；
- runtime verification；
- diff review；
- commit；
- push；
- PR preparation。

Claude Code 可以通过 `cd`、绝对路径或 `git -C <worktree>` 明确操作该 worktree，但必须在 Gate Report 中证明实际修改属于 feature branch / worktree，而不是 `main`。

## Phase 2 — Merge / Regression / Cleanup

PR 准备完成后，同一个 Conversation 可以回到主仓库执行：

- merge；
- update `main`；
- main regression；
- worktree remove；
- `git worktree prune`；
- merged local branch cleanup；
- final clean verification。

因此：

> **每个 Gate 仍然只使用一个 Claude Code Conversation；Conversation 可以从 `main` 启动，但 `main` 只承担 bootstrap、merge、regression 和 cleanup，不承担功能开发。**

---

# 78F. Claude Code 启动提示词强制元数据

ChatGPT Commander 每次输出可复制给 Claude Code 的 Gate Prompt 时，必须在最前面完整写明：

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

Current Gate:
Gate Objective:
Entry Condition:
Allowed Scope:
Prohibited Scope:
Required Tests:
Runtime Verification:
Git Actions:
Merge Requirement:
Worktree Cleanup Requirement:
Exit Condition:
```

不得省略：

- Conversation Name；
- 是否新开；
- Model；
- Thinking；
- Repository；
- Branch；
- Worktree；
- Permission / Bypass；
- Gate；
- 关键禁止事项。

---

# 78G. Permission / Bypass 默认规则

默认：

```text
Permission / Bypass Setting:
Normal / Standard permissions.
Do not enable broad bypass unless the Commander explicitly authorizes it for a bounded reason.
```

即：

- 不默认开启 unrestricted bypass；
- 不用“为了省事”跳过保护；
- 如某 Gate 确实需要特殊权限，ChatGPT Commander 必须在启动提示词中显式写出原因和边界。

---

# 79. Development with Claude Code

Claude Code 开发必须受 Battle Plan Gate 约束，并遵守第 78A–78G 节的双角色与 Conversation Contract。

每次新 Gate Prompt 必须包含：

- Conversation Name；
- Tool / Role；
- New Conversation or Continue；
- Model；
- Thinking Level；
- Permission / Bypass Setting；
- main repository；
- base branch；
- feature branch；
- Conversation Start Repository（固定主仓库 `main`）；
- dedicated worktree；
- Active Working Directory（worktree 创建后）；
- current HEAD；
- clean status；
- current Gate；
- allowed scope；
- prohibited scope；
- tests；
- acceptance criteria；
- commit / push / PR / merge requirement；
- main regression；
- worktree cleanup requirement。

不得只说：

> “把 MountainGuardian 做好。”

---

# 80. Claude Code 修改原则

Claude Code：

- 优先最小修改；
- 不擅自重构 unrelated modules；
- 不删除既有 tests；
- 不修改 Case Pack 科学事实；
- 不更改冻结公式；
- 不改变 UI Design Direction；
- 不添加 v1.1 功能；
- 不将 Secret 写入文件。

---

# 81. 每 Gate 验收证据

每 Gate 至少保留：

```text
branch
commit
tests
runtime result
changed files
acceptance verdict
known limitations
```

Battle Plan 将进一步规定输出模板。

---

# 82. Final Release Candidate

所有功能完成后：

建议形成：

```text
v1.0-rc1
```

完成：

- full regression；
- Azure smoke；
- Historical Replay；
- live Risk Watch；
- screenshot evidence；
- demo video preparation。

发现问题：

> fix branch → rc2

最终再：

```text
v1.0
```

tag。

---

# 83. Release Tag

正式比赛冻结版本建议 Git tag：

```text
mountainguardian-v1.0
```

Tag 创建前必须：

- clean tree；
- main latest；
- pytest PASS；
- Azure PASS；
- URL PASS。

---

# 84. Final Competition Freeze

比赛材料制作完成后：

核心代码只接受：

> blocker fix

不继续添加新功能。

保证：

- 演示视频；
- 报告截图；
- 在线系统；

三者对应同一个 release。

---

# 85. v1.0 明确不做的工程能力

- Dockerization；
- Kubernetes；
- PostgreSQL；
- Redis；
- Key Vault；
- Managed Identity；
- OIDC deployment；
- Multi-instance scaling；
- Blue/Green deployment；
- Staging slot；
- Terraform；
- Application Insights 深度集成；
- Sentry；
- CDN；

- User Authentication；
- RBAC；
- Background Scheduler；
- Message Queue；
- Microservices。

以上都可以未来增加，但不得进入 v1.0 Battle Plan P0。

---

# 86. Engineering Acceptance Criteria

v1.0 工程层只有在以下全部满足时才算完成：

1. 00–07 冻结文档在仓库中；
2. UI reference image 在指定路径；
3. main 可运行；
4. working tree clean；
5. Python 3.12 本地运行；
6. requirements 可安装；
7. `pip check` PASS；
8. full pytest 0 failed；
9. Historical Replay PASS；
10. leakage tests PASS；
11. DeepSeek live provider PASS；
12. provider failure fallback PASS；
13. Open-Meteo live PASS；
14. Risk Watch deterministic formula PASS；
15. Snapshot persistence PASS；
16. Optional satellite failure不阻塞；
17. SQLite 本地 PASS；
18. SQLite Azure persistent path PASS；
19. Streamlit Azure startup PASS；
20. `/_stcore/health` = 200；
21. GitHub Actions tests PASS；
22. GitHub Actions deployment PASS；
23. public HTTPS URL 可访问；
24. production Secret 不在 Git；
25. logs 不暴露 Secret；
26. Audit 可追踪 run_id；
27. App Service 单实例；
28. production runtime smoke PASS；
29. rollback procedure 已验证或至少有可执行步骤；
30. release tag 可创建；
31. `.worktrees/` 已加入 `.gitignore`；
32. 每个 Gate 使用 dedicated worktree；
33. 每个 Gate merge 后 worktree 已删除并 prune；
34. Gate 结束时 main clean；
35. Claude Code Conversation metadata 按 78F 完整记录；
36. Azure 默认 `azurewebsites.net` URL 可独立完成核心部署验收；
37. 最终比赛版 custom domain 已绑定或存在明确可执行绑定步骤；
38. custom domain HTTPS 已验证；
39. Bitwarden 本地 Secret 链路符合 `BWS_ACCESS_TOKEN → bws run → DEEPSEEK_API_KEY`；
40. GitHub Actions CI 不持有 DeepSeek API Key。

---

# 87. 官方平台验证快照（2026-09-30）

本工程规范在 2026-09-30 对当前官方平台资料进行了核对。

确认：

## Azure App Service Python

- Python Web App 使用 Linux App Service；
- 可配置自定义 startup command；
- App Settings 以环境变量形式提供给 Python 应用；
- Python deployment 可由 requirements.txt 自动安装依赖。

## Azure App Service Secrets

- Application Settings 在平台侧静态加密；
- Key Vault 可作为更高级 Secret 管理，但不是 v1.0 必须项。

## GitHub Actions

- Azure App Service 支持通过 GitHub Actions 部署 Python Web App；
- 可使用 Publish Profile 作为 deployment credential；
- workflow 可在部署前加入 pytest 等测试。

## Health Check

- Azure App Service 支持配置 customer health path；
- Streamlit 官方提供 `/_stcore/health`。

## Storage

- Azure App Service Linux `/home` 是持久化文件区域；
- v1.0 保持单实例并将 SQLite 放到 `/home/data`；
- 不将 SQLite 放在额外挂载的 Azure Files share。

---

# 88. 当前参考链接

实现 Gate 执行时应再次核对最新官方文档。

Azure Python App Service：

```text
https://learn.microsoft.com/azure/app-service/configure-language-python
```

Azure GitHub Actions：

```text
https://learn.microsoft.com/azure/app-service/deploy-github-actions
```

GitHub Python to Azure App Service：

```text
https://docs.github.com/actions/how-tos/deploy/deploy-to-third-party-platforms/python-to-azure-app-service
```

Azure App Settings：

```text
https://learn.microsoft.com/azure/app-service/configure-common
```

Streamlit health endpoint / deployment：

```text
https://docs.streamlit.io/deploy/tutorials/docker
```

---

# 89. 与 Battle Plan 的关系

本文只冻结：

> **工程规则与部署目标。**

下一份：

```text
07_MountainGuardian_Battle_Plan_v1.0.md
```

必须把 00–06 的冻结设计转化成：

```text
Gate
Entry Condition
Scope
Claude Code Prompt
Tests
Acceptance Criteria
Git Actions
Exit Condition
```

Battle Plan 不得重新讨论已经冻结的：

- 产品范围；
- 科学边界；
- Agent 架构；
- Risk Watch 公式；
- UI 视觉方向；
- 工程原则。

如果实施时发现真正 blocker：

> 先回到对应冻结文档修改并重新冻结，再修改 Battle Plan。

---

# 90. 一句话工程定义

> **MountainGuardian v1.0 采用最小而稳健的工程路线：在现有 Python + Streamlit + SQLite 代码库上按 Gate 逐步实现真实模型、多智能体、Risk Watch 和专业 UI，通过严格测试、独立 feature branch、PR/merge 和可追溯日志保持 main 始终可运行，最终以单实例 Azure App Service Linux + GitHub Actions 部署成可公开访问的比赛版在线系统。**
