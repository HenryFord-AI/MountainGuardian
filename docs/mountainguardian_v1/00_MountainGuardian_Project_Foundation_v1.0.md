# MountainGuardian Project Foundation v1.0
## 山河守望者项目基础总纲（冻结版）

**文档状态：** FROZEN / 已冻结  
**项目名称：** 山河守望者（MountainGuardian）  
**产品定位：** Multi-Agent Disaster Risk Intelligence Platform  
**当前版本基线：** Jilong Demo v0.1  
**目标版本：** MountainGuardian v1.0  
**适用范围：** 产品设计、科学数据、AI Agent 架构、Risk Watch、UI/UX、工程部署、Battle Plan  
**治理原则：** 本文为 MountainGuardian v1.0 的上位依据。后续下游文档如与本文发生原则性冲突，应先修改并重新冻结本文，再修改下游文档。

---

## 1. 项目背景与参赛定位

MountainGuardian（山河守望者）源于对高山峡谷地区洪水、泥石流及相关链式灾害的关注。项目希望探索：在真实自然灾害场景中，是否可以利用多智能体人工智能，将气象、水文、地形、冰川、遥感和历史灾害等多源数据组织起来，形成一套可解释、可追溯、可持续迭代的灾害风险分析与监测方法。

项目当前面向 2026 年“雏鹰杯”红领巾科创小能手主要项目中的“人工智能”类别。目标不是制作一段静态展示视频，也不是仅完成一篇灾害科普报告，而是形成一个真实可运行、可交互、可展示智能分析流程的 AI 系统原型。

MountainGuardian v1.0 以“可真实运行、可解释、可验证、可上线”为核心，而不是追求生产级政府灾害预警系统的完整能力。

---

## 2. 核心问题

MountainGuardian 研究和解决的核心问题是：

> **如何让多个具有不同专业职责的 AI Agent，像一个小型灾害风险研究团队一样，持续整合多源环境与遥感数据，对高山峡谷地区的灾害风险进行识别、解释、复核和趋势研判？**

项目重点研究：

1. 多源数据能否被自动组织并转化为结构化风险证据；
2. 不同专业 Agent 能否从不同角度形成独立分析；
3. 多 Agent 结果能否被综合成可解释的风险结论；
4. 系统能否通过独立 Critic / Reviewer 对结论进行复核并表达不确定性；
5. 系统能否随着周期性数据更新形成当前风险、短期展望和历史趋势；
6. 整个过程能否做到来源可追溯、行为可审计、边界可控制。

项目不以“准确预测某次灾害一定会在某时某地发生”为目标。

---

## 3. 产品愿景

MountainGuardian 的产品愿景是：

> **面向高山峡谷地区的多智能体 AI 灾害风险监测与分析平台。**

系统围绕两种互补业务模式工作。

### 3.1 Historical Replay — 历史验证

通过真实历史灾害案例，验证系统能否在严格区分“灾前可获得信息”和“灾后验证信息”的前提下，识别出灾害发生前已经存在的风险条件。

当前核心历史案例为：

**2026 年西藏吉隆口岸“8·26”冰岩崩—碎屑流—泥石流灾害。**

历史验证模式的目的不是宣称“系统提前预测出了 8·26 灾害”，而是回答：

> **如果只给系统灾前能够获得的地形、冰川、环境、历史灾害和遥感等信息，多智能体系统能够识别出哪些基础风险？**

### 3.2 Risk Watch — 风险监测

面向一个持续关注的区域，周期性采集最新数据，形成风险快照，并与历史快照比较。

v1.0 Risk Watch 只保留三个核心结果：

- **Current Risk**：当前风险状态；
- **7-Day Outlook**：未来 7 天短期风险展望；
- **Historical Trend**：过去一段时间的风险变化趋势。

v1.0 不实现 30 天未来风险预测和 2027 年夏季季节风险预测。

当前比赛 / 展示版本采用：

> **On-demand Risk Scan（手动触发真实扫描）**

用户点击“立即扫描”，系统完成一次数据采集、标准化、入库、比较、多 Agent 分析、复核和风险输出。

架构保持 **Scheduler-ready**，未来可在 Azure 上升级为周期性自动扫描。

---

## 4. 当前技术与产品基线

MountainGuardian 不是从零开发，而是在 GitHub 开源项目：

`BALADURGAG24/rescuemind-multi-agent`

基础上进行二次开发。

原项目 RescueMind AI 提供可复用能力：

- Python + Streamlit Web 应用；
- BaseAgent 抽象框架；
- Coordinator 调度机制；
- SQLite 日志与审计记录；
- AgentResponse 与可解释性卡片；
- Demo Mode 降级机制；
- 输入安全检查框架。

MountainGuardian 已完成第一阶段改造，并形成可运行的 **Jilong Demo v0.1**：

- Jilong Case Pack 已完成；
- 数据包已区分灾前数据与灾后验证数据；
- 历史案例页面可运行；
- 风险指数规则引擎可复算；
- 多 Agent 流程可运行；
- 数据泄漏专项测试已建立；
- 卫星与官方图件已经接入；
- Streamlit 系统本地运行成功；
- 自动化测试全部通过。

当前 v0.1 仍以规则化 Agent 为主，尚未完成真实大模型接入、Risk Watch、商业级 UI 和 Azure 部署。

---

## 5. MountainGuardian v1.0 目标形态

v1.0 不再只是“历史案例 Demo”，而应成为一个完整的 AI 风险分析原型产品。

### 5.1 四个主产品入口

为控制开发复杂度并提升产品聚焦度，v1.0 将原六页结构收缩为四个主入口：

1. **Overview**  
   地图、当前风险、最近扫描、Agent 状态和趋势总览。

2. **Historical Replay**  
   吉隆“8·26”案例的灾前证据、多智能体分析与灾后验证。

3. **Risk Watch**  
   执行真实数据扫描，输出当前风险、7-Day Outlook 与 Historical Trend。

4. **Intelligence Center**  
   内含三个子 Tab：
   - Agent Workspace
   - Evidence Center
   - Audit & Safety

这样保留所有核心功能，但减少独立页面数量和前端重复开发。

### 5.2 产品主线

MountainGuardian 的核心产品逻辑统一为：

> **DATA → AGENTS → EVIDENCE → RISK → REVIEW**

其中：

- DATA：多源数据；
- AGENTS：多个专业 AI Agent；
- EVIDENCE：可追溯证据；
- RISK：风险指数、等级和趋势；
- REVIEW：独立复核与不确定性表达。

---

## 6. AI 系统原则

MountainGuardian 不把大模型当作万能答案生成器，而采用：

> **确定性计算 + AI 推理**

的混合架构。

### 6.1 v1.0 Agent 架构

v1.0 固定采用：

- **Glacier / Geology Agent**
- **Weather / Hydrology Agent**
- **Remote Sensing Agent**
- **Risk Synthesizer**
- **Critic / Reviewer**

工作流固定为：

> **三个专业 Agent 并行分析 → Risk Synthesizer 综合 → Critic / Reviewer 复核**

v1.0 不实现复杂递归 Agent 对话，也不允许 Agent 自由互相调用形成不可控工作流。

### 6.2 模型策略

v1.0 只接入 **一个真实大模型 Provider**。

当前冻结方向：

> **DeepSeek V4.1 Flash 作为 v1.0 主模型。**

Critic / Reviewer 在 v1.0 中也使用同一模型，但采用独立 Prompt 和角色约束。

GPT-6 Sol 等第二模型作为 v1.1 / Future Enhancement，不属于 v1.0 必做范围。

### 6.3 模型与规则边界

必须长期坚持：

> **LLM 负责理解、解释、比较、推理与总结；确定性算法负责可复现的风险指数计算。**

大模型不得：

- 自行编造风险指数；
- 将风险指数包装成发生概率；
- 自行修改原始证据；
- 将灾后数据偷偷用于灾前分析。

### 6.4 Safety 不是一个独立“思考型 Agent”

v1.0 不单独实现复杂 Safety Agent。

安全能力通过系统级 Guard 实现：

- Prompt Injection Guard；
- Tool Permission Guard；
- Data Leakage Guard；
- Post-event Leakage Guard；
- Output Schema Validation；
- Audit Logging；
- External Action Disabled。

---

## 7. 科学与数据原则

### 7.1 真实性优先

所有关键事实、图像和数值必须能够追溯到真实来源。

不得：

- 用 AI 生成图像冒充卫星影像；
- 用其他地区数据冒充吉隆数据；
- 将模拟数据标记为真实观测；
- 将灾后信息用于模拟灾前预测；
- 将不确定判断包装成确定事实。

### 7.2 Historical Replay 必须防止 Data Leakage

历史案例数据至少区分：

- `pre_event_static`
- `pre_event_context`
- `pre_event_evidence`
- `post_event_validation`
- `context_only`

Risk / Intelligence 类 Agent 只能读取灾前允许字段。

灾后验证信息只能用于 Critic / Reviewer 和结果验证。

### 7.3 风险表达

系统必须严格区分：

- **Risk Index**：规则或模型计算的风险指数；
- **Risk Level**：Low / Moderate / Elevated / High；
- **Risk Trend**：风险相对历史快照的变化趋势；
- **Probability**：只有经过统计建模、训练和校准后才能使用。

在没有概率模型的情况下，禁止把 91/100 写成“91% 发生概率”。

### 7.4 ENSO / 厄尔尼诺

ENSO 可以作为气候背景和 Risk Watch 的环境输入之一，但不作为吉隆“8·26”具体灾害的直接因果证据。

---

## 8. Risk Watch 原则

Risk Watch 是 MountainGuardian 从“案例演示”迈向“真实监测产品”的核心能力。

### 8.1 Collect Data ≠ Call LLM

天气 API、遥感元数据、地形数据、历史数据、数据库读取等应优先通过普通程序完成。

只有在：

> **Collect → Normalize → Store → Compare**

之后，才进入：

> **Agents → Risk → Review**

AI 不承担本可由普通代码稳定完成的数据采集工作。

### 8.2 必选数据与可选数据

v1.0 Risk Watch 每次扫描的核心数据尽量控制为：

**Required / 优先保证稳定获取：**

- 当前与近期气温；
- 过去 7 天降水；
- 未来 7 天天气预报；
- 静态地形与冰川基础数据；
- 历史风险基线。

**Optional Evidence / 有则增强：**

- 土壤 / 地表湿度；
- 河流水位；
- 新卫星影像；
- ENSO；
- 冰川动态观测。

某个可选数据源缺失时，不应导致整个 Risk Watch 扫描失败。

### 8.3 v1.0 输出

Risk Watch v1.0 只输出：

- 当前风险；
- 未来 7 天风险展望；
- 最近历史风险趋势；
- 主要风险驱动因素；
- 数据缺失与不确定性。

### 8.4 遥感原则

Remote Sensing Agent 在 Historical Replay 中可充分使用现有灾前/灾后影像。

在 Risk Watch 中：

> **只有存在新的、可用质量的遥感影像时才调用遥感分析。**

不得要求“每周扫描必须有最新卫星影像”。

v1.0 不自研遥感变化检测模型，优先利用 Vision LLM 作为辅助观察工具。

---

## 9. UI / 产品体验原则

MountainGuardian v1.0 采用：

> **Geospatial Intelligence × AI Mission Control**

视觉方向。

核心工作面为：

> **2D 地理空间 / 卫星地形地图 + 风险叠加 + Agent 状态 + 风险结论**

v1.0 不实现复杂 3D GIS、不实现重型多图层 GIS 编辑器。

地图只需稳定展示：

- 监测区域；
- 冰川 / 源区；
- 关键路径；
- 下游暴露区域；
- 核心监测点；
- 风险标记。

UI 目标：

- 专业；
- 商业级；
- 高级；
- 科技感；
- AI 感；
- 可信；
- 数据驱动。

避免：

- 科技海报风；
- 游戏化赛博朋克；
- 大量霓虹装饰；
- 幼儿化或“学生作品感”；
- 过度免责声明占据主视觉。

科学边界与免责声明必须保留，但应以：

- Historical Replay
- Research Validation
- Research Prototype
- 页面底部科学声明

等方式低干扰呈现。

---

## 10. 开源、AI Coding 与原创边界

MountainGuardian 明确采用开源软件和 AI Coding 作为开发方法的一部分。

项目必须如实说明：

1. 基础代码来源于 MIT License 开源项目 RescueMind AI；
2. MountainGuardian 对其进行了新的问题定义、数据体系、风险模型、Agent 架构、数据泄漏防护、安全设计、Risk Watch、UI 和部署改造；
3. 原项目版权和 License 必须保留；
4. 不能将原项目已有 Agent 框架宣称为完全自主从零开发；
5. 可以并应当记录 AI Coding 工具、开发 Harness 和所使用模型；
6. AI Coding 是实现方法，不替代项目本人对问题、设计、测试、结果与科学边界的理解。

项目创新主要体现为：

> **如何利用多智能体 AI 与真实多源数据，构建面向高山峡谷灾害风险的可解释分析与监测系统。**

---

## 11. 明确不做的事情

为控制范围并提高投入产出比，v1.0 明确不做：

- 全国所有灾害实时预测；
- 精确预测某次灾害发生日期和分钟；
- 没有统计依据的灾害发生概率；
- 30 天未来风险预测；
- 2027 夏季季节风险预测；
- 第二大模型 Provider；
- 复杂递归 Agent 自主协作；
- 生产级政府预警发布；
- 邮件 / 短信真实预警发送；
- 自研遥感基础模型；
- 复杂遥感自动变化检测算法；
- 每周强制获取新卫星影像；
- 复杂 3D GIS；
- 重型多图层地理信息系统；
- PostgreSQL / 云数据库迁移；
- 复杂 RBAC 权限系统；
- 无边界自治 Agent；
- 为展示效果编造数据。

以上可作为 v1.1 或未来研究方向，但不进入当前 Battle Plan 的 v1.0 必做范围。

---

## 12. 工程与治理原则

后续开发采用阶段化治理。

每个 Gate 遵循：

> **Branch → Implement → Test → Review → Commit → Push → PR → Merge**

原则：

- `main` 始终保持可运行；
- 每个 Gate 有 Entry Condition；
- 每个 Gate 有 Acceptance Criteria；
- 每个 Gate 必须有测试；
- 每个 Gate 完成后形成 GitHub 可追踪版本；
- 禁止未经授权的大范围重构；
- 禁止 API Key / Secret 进入 Git。

---

## 13. Azure 与部署原则

v1.0 的目标是：

> **评审老师能够通过公开 URL 访问和试用 MountainGuardian。**

部署优先采用轻量方案：

- Azure App Service；
- GitHub Actions 自动部署；
- HTTPS；
- Health Check；
- App Service 环境变量 / Secrets。

v1.0 不强制使用 Azure Key Vault + Managed Identity。

只要满足：

> **Secret 不进入代码仓库，线上配置可安全管理**

即可。

Azure Key Vault 作为 v1.1 安全增强项。

数据库 v1.0 继续使用 SQLite；不进行 PostgreSQL 或其他云数据库迁移。

---

## 14. v1.0 成功标准

### 产品

- Historical Replay 与 Risk Watch 两种模式均可运行；
- 4 个主产品入口完整；
- UI 达到专业商业软件原型水平；
- 地理空间界面体现 Geospatial Intelligence；
- 评委可通过在线 URL 独立访问。

### AI

- DeepSeek V4.1 Flash 已真实接入；
- 三个专业 Agent 使用结构化输入 / 输出；
- Risk Synthesizer 能整合专业 Agent 与规则风险引擎；
- Critic / Reviewer 能独立复核结论；
- 大模型不可用时有可靠 fallback；
- Agent 不使用复杂递归工作流。

### Risk Watch

- Run Risk Scan 可真实执行；
- 能采集并保存至少一组真实最新数据；
- 能与历史快照比较；
- 输出 Current Risk；
- 输出 7-Day Outlook；
- 输出 Historical Trend；
- 可选数据源缺失不会导致系统整体失败。

### 数据与科学

- Jilong Case Pack 完整可追溯；
- Historical Replay 无 post-event data leakage；
- 风险指数与概率严格区分；
- 历史验证结论不夸大；
- 不确定性明确表达；
- 模型结论可追溯到具体证据。

### 安全

- Prompt Injection Guard；
- Data Leakage Guard；
- Post-event Leakage Guard；
- Output Schema Validation；
- 外部真实发送默认禁用；
- 模型与 Agent 行为有日志记录。

### 工程

- 自动化测试通过；
- GitHub Branch / PR / Merge 流程完整；
- Azure App Service 成功部署；
- GitHub Actions 可自动部署；
- Secret 不进入 Git；
- 在线 Health Check 正常；
- SQLite 能支持当前展示负载。

---

## 15. 后续文档关系

本 Foundation 是以下文档的上位依据：

1. `01_MountainGuardian_Product_Requirements_v1.0.md`
2. `02_MountainGuardian_Scientific_Data_Baseline_v1.0.md`
3. `03_MountainGuardian_AI_Agent_Architecture_v1.0.md`
4. `04_MountainGuardian_Risk_Watch_Design_v1.0.md`
5. `05_MountainGuardian_UI_UX_Design_Spec_v1.0.md`
6. `06_MountainGuardian_Engineering_Deployment_Spec_v1.0.md`
7. `07_MountainGuardian_Battle_Plan_v1.0.md`

如果后续文档与本 Foundation 原则冲突：

> **先修改 Foundation 并重新冻结，再修改下游文档。**

---

## 16. 当前阶段

当前状态：

> **Jilong Demo v0.1 — PASS**

Foundation v1.0 冻结后，依次完成：

> Product Requirements  
> → Scientific/Data Baseline  
> → AI Agent Architecture  
> → Risk Watch Design  
> → UI/UX Design  
> → Engineering/Deployment Spec  
> → Battle Plan

在 Battle Plan 冻结前，不启动 MountainGuardian v1.0 大规模代码改造。

---

## 17. 一句话项目定义

> **MountainGuardian（山河守望者）是一套面向高山峡谷地区的多智能体 AI 灾害风险监测与分析平台，通过融合冰川地质、气象水文、遥感和历史灾害等多源证据，让多个专业 AI Agent 协同分析、相互复核，并形成可解释、可追溯的当前风险判断、短期风险展望与历史趋势。**
