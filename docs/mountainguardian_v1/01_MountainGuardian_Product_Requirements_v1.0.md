# MountainGuardian Product Requirements v1.0
## 山河守望者 v1.0 产品需求文档（冻结版）

**文档状态：** FROZEN / 已冻结  
**上位依据：** `00_MountainGuardian_Project_Foundation_v1.0.md`  
**目标产品版本：** MountainGuardian v1.0  
**文档目的：** 冻结 v1.0 的产品范围、用户路径、功能模块、输入输出、交互方式、优先级与验收标准。  
**非本文件范围：** 不在本文中冻结具体 Prompt、模型调用细节、数据库表结构、Azure 部署脚本和代码实现方式。

---

# 1. 产品定义

MountainGuardian（山河守望者）是一套面向高山峡谷地区的多智能体 AI 灾害风险监测与分析平台。

v1.0 围绕两种核心业务模式：

1. **Historical Replay — 历史验证**
2. **Risk Watch — 风险监测**

产品统一遵循：

> **DATA → AGENTS → EVIDENCE → RISK → REVIEW**

最终用户不需要理解底层代码，也不需要直接操作模型 API。用户通过地图、数据卡片、Agent 协同视图、风险结果和证据中心理解：

- 系统正在分析哪里；
- 系统使用了什么数据；
- 哪些 AI Agent 参与；
- 各 Agent 得出了什么结论；
- 风险指数和风险等级是什么；
- 结论依据是什么；
- 存在哪些限制和不确定性；
- 历史案例与当前监测如何相互验证。

---

# 2. v1.0 产品目标

v1.0 必须实现以下五个目标：

## 2.1 从规则 Demo 升级为真实 AI 系统

至少接入一个真实大模型 Provider，使专业 Agent 的分析结果来自真实模型调用，而不是仅由固定文案生成。

## 2.2 保留可复现的确定性风险引擎

风险指数必须由确定性算法计算，不能完全依赖 LLM 主观判断。

## 2.3 建立两种互补验证方式

- Historical Replay：证明系统能在严格数据边界下分析真实历史灾害。
- Risk Watch：证明系统能处理最新数据并形成持续风险监测结果。

## 2.4 建立专业产品体验

UI 应达到商业级 AI/GIS 原型产品水平，能够清楚展示：

- 区域
- 数据
- Agent
- 风险
- 证据
- 审查

## 2.5 支持在线访问

最终应部署到 Azure，评审老师可以通过公开 URL 浏览并触发主要演示流程。

---

# 3. 目标用户

v1.0 主要服务三类用户。

## 3.1 评审 / 演示用户

典型用户：

- 科技比赛评委；
- 学校科技老师；
- 指导教师；
- 参观者。

核心需求：

- 迅速理解项目在做什么；
- 一眼看到多智能体协作；
- 能实际点击并看到分析结果；
- 能确认数据和证据来源；
- 能理解历史验证和实时监测之间的关系。

## 3.2 项目研究用户

典型用户：

- 项目完成人；
- 指导者；
- 后续开发者。

核心需求：

- 查看历史案例输入；
- 查看 Agent 分析；
- 检查模型结果；
- 查看 Risk Watch 快照；
- 查看证据、日志与安全信息。

## 3.3 系统维护用户

典型用户：

- 项目开发与部署维护者。

核心需求：

- 知道模型是否正常；
- 知道最近扫描是否成功；
- 知道数据源是否缺失；
- 知道 Agent 是否异常；
- 能查看日志和审计信息。

v1.0 不设计复杂用户权限系统，以上三类用户共享同一个只读/演示型产品入口。

---

# 4. 信息架构

v1.0 冻结为四个主产品入口：

1. **Overview**
2. **Historical Replay**
3. **Risk Watch**
4. **Intelligence Center**

其中 Intelligence Center 内含：

- Agent Workspace
- Evidence Center
- Audit & Safety

---

# 5. Overview — 总览

## 5.1 页面目标

Overview 是用户进入 MountainGuardian 后的第一屏。

必须在 10 秒内让用户理解：

- 当前监测区域在哪里；
- 当前风险状态是什么；
- 系统最近什么时候运行；
- 有哪些数据源；
- 有哪些 Agent；
- Historical Replay 和 Risk Watch 都存在。

## 5.2 必须展示

### A. 产品与系统状态

显示：

- MountainGuardian / 山河守望者
- 当前监测区域
- 系统状态
- 最近扫描时间
- 数据源数量
- 活跃 Agent 数量
- 模型运行状态

### B. 主地图

使用 2D 卫星 / 地形地图。

必须至少支持：

- 吉隆口岸位置；
- 高山 / 冰川源区；
- 关键沟道 / 路径；
- 下游暴露区域；
- 核心监测点或风险标记。

不要求复杂 GIS 编辑能力。

### C. 当前风险状态

展示：

- Risk Index
- Risk Level
- Risk Trend
- Confidence / Evidence Coverage

必须明确 Risk Index 不是灾害发生概率。

### D. Agent 协作概览

展示：

- Glacier / Geology Agent
- Weather / Hydrology Agent
- Remote Sensing Agent
- Risk Synthesizer
- Critic / Reviewer

页面重点展示“协作关系”，不是长篇日志。

### E. 快速入口

提供：

- Historical Replay
- Run Risk Scan
- Intelligence Center

三个主要入口。

---

# 6. Historical Replay — 历史验证

## 6.1 页面目标

以 2026 年吉隆口岸“8·26”案例为核心，展示：

> **如果系统只使用灾前可以获得的信息，它能识别出哪些基础风险？**

必须同时展示灾前分析和灾后验证，但两者数据必须严格隔离。

## 6.2 案例基础信息

显示：

- 案例名称；
- 地点；
- 日期；
- 灾害类型；
- 数据来源数量；
- Historical Replay / Research Validation 标记。

## 6.3 灾前数据区

展示系统真正允许输入 Agent 的灾前数据，包括：

- 冰川 / 冰冻圈背景；
- 地形与高差；
- 沟道与松散物源；
- 季节 / 气候背景；
- 历史灾害记录；
- 灾前遥感影像；
- 其他允许的 pre-event evidence。

## 6.4 多 Agent 分析区

必须依次或并行展示：

### Glacier / Geology Agent
输出：
- 关键发现；
- 支撑证据；
- 置信度；
- 数据缺口。

### Weather / Hydrology Agent
输出：
- 关键发现；
- 支撑证据；
- 置信度；
- 数据缺口。

### Remote Sensing Agent
在存在可用遥感图像时输出：
- 可观察特征；
- 影像日期；
- 影像质量；
- 不确定性。

若没有适用影像，应显示：
- No usable new imagery / 本轮无可用新影像

而不是生成虚假结果。

### Risk Synthesizer
输出：
- 综合风险结论；
- Risk Index；
- Risk Level；
- Top Risk Drivers；
- Agent 之间是否一致。

### Critic / Reviewer
输出：
- 证据是否充分；
- 是否存在 data leakage；
- 是否存在过度因果推断；
- 哪些信息缺失；
- 结论可以说到什么程度；
- Review Result。

## 6.5 灾后验证区

灾后信息只能在风险结论生成后出现。

展示：

- 灾害路径；
- 灾后 Sentinel-2；
- 官方调查图件；
- 事件实际情况；
- 与系统灾前识别结果的对应关系。

严禁表述：

> “系统成功提前预测了 8·26 灾害。”

推荐表述：

> “历史回放显示，系统能够识别出灾前已经存在的多项高风险条件。”

## 6.6 Historical Replay 输出

最终应形成一页可阅读的综合结果：

- Risk Index
- Risk Level
- Top Drivers
- Agent Summary
- Critic Result
- Scientific Limitations
- Pre-event Evidence
- Post-event Validation

---

# 7. Risk Watch — 风险监测

## 7.1 页面目标

Risk Watch 用于展示 MountainGuardian 不仅可以回放历史案例，还能处理最新数据并持续生成区域风险快照。

v1.0 使用：

> **On-demand Risk Scan**

用户点击按钮触发一次真实扫描。

## 7.2 核心操作

页面必须有一个明确主要按钮：

> **Run Risk Scan / 立即执行风险扫描**

点击后启动：

> Collect → Normalize → Store → Compare → Agents → Risk → Review

页面应显示扫描进度。

## 7.3 Required Data

优先保证稳定获取：

- 当前 / 近期气温；
- 过去 7 天降水；
- 未来 7 天天气预报；
- 静态地形基础数据；
- 静态冰川 / 冰冻圈基础信息；
- 历史风险基线。

## 7.4 Optional Evidence

可选：

- 土壤 / 地表湿度；
- 河流水位；
- 最新卫星影像；
- ENSO；
- 冰川动态观测。

规则：

> 可选证据缺失不得导致整次 Risk Scan 失败。

## 7.5 扫描状态

扫描过程中至少显示：

1. 数据采集；
2. 数据标准化；
3. 与上次快照比较；
4. 专业 Agent 分析；
5. Risk Synthesizer；
6. Critic Review；
7. 完成。

用户应能判断失败发生在哪一步。

## 7.6 Risk Watch v1.0 输出

只输出：

### Current Risk
- Risk Index
- Risk Level
- 更新时间

### 7-Day Outlook
展示：
- 风险方向
- 主要气象驱动
- 需要关注的时间窗口
- 不确定性

不得表述为“7天内灾害发生概率”。

### Historical Trend
展示最近历史扫描的 Risk Index / Risk Level 变化。

可使用折线图：

- Scan Date
- Risk Index
- Risk Level

### What Changed
自动总结与上一次扫描相比：

- 哪些指标上升；
- 哪些下降；
- 哪些无明显变化；
- 哪些数据缺失。

### Main Risk Drivers
展示 3–5 个最重要风险因素。

### Data Quality / Coverage
展示：
- 本轮数据覆盖；
- 缺失数据；
- 是否有最新卫星图；
- 是否存在低质量证据。

---

# 8. Intelligence Center — 智能中心

Intelligence Center 是三个管理 / 解释型能力的统一入口。

---

# 9. Agent Workspace

## 9.1 页面目标

让用户直观看到：

> “Multi-Agent”是真实系统结构，而不是宣传词。

## 9.2 每个 Agent 卡片

必须至少显示：

- Agent 名称；
- 当前状态；
- 使用模型；
- 输入类型；
- 本轮关键输出；
- Confidence；
- 执行时间；
- Evidence Count。

## 9.3 Agent 协作关系

可视化：

> 专业 Agent → Risk Synthesizer → Critic / Reviewer

v1.0 不展示复杂递归 Agent 网络。

## 9.4 详细结果

允许用户展开某个 Agent，查看：

- 输入摘要；
- 结构化输出；
- 引用证据；
- 模型解释；
- 数据缺口；
- 原始 JSON（可选，面向开发者）。

---

# 10. Evidence Center

## 10.1 页面目标

所有重要 AI 结论都应该能追溯到证据。

## 10.2 证据分类

至少支持：

- Satellite
- Weather
- Terrain
- Glacier / Cryosphere
- Historical Events
- Hydrology（如果有）

## 10.3 每个 Evidence Item

显示：

- Evidence ID；
- 类型；
- 来源机构；
- 日期；
- 原始 URL 或来源说明；
- Pre-event / Post-event / Current；
- 使用该证据的 Agent；
- 简要观察；
- 数据质量。

## 10.4 卫星图

支持：

- 灾前 / 灾后影像；
- 官方图件；
- 图像 caption；
- 日期；
- 云量 / 质量限制。

v1.0 不需要复杂图像标注编辑器。

---

# 11. Audit & Safety

## 11.1 页面目标

展示 AI 系统是“受控、可追踪、可解释”的。

## 11.2 Model Runtime

显示：

- Provider；
- Model Name；
- Connected / Fallback；
- 最近调用状态；
- 失败次数（如有）。

## 11.3 Safety Controls

显示：

- Prompt Injection Guard；
- Data Leakage Guard；
- Post-event Leakage Guard；
- Output Schema Validation；
- External Actions Disabled。

## 11.4 Audit Log

记录：

- 扫描 ID；
- Agent；
- 时间；
- 模型调用；
- 输入类型；
- 输出状态；
- 异常；
- Risk Result。

不要求在 v1.0 中实现复杂审计搜索系统。

---

# 12. 产品交互流程

## 12.1 首次打开

用户进入 Overview：

1. 看地图；
2. 看当前风险；
3. 看 Agent 网络；
4. 看到 Historical Replay 和 Risk Watch 两个入口。

## 12.2 历史案例演示

用户进入 Historical Replay：

1. 查看吉隆案例；
2. 查看灾前数据；
3. 触发或查看 Agent 分析；
4. 查看 Risk Synthesizer；
5. 查看 Critic；
6. 查看灾后验证；
7. 查看结论与科学限制。

## 12.3 当前风险扫描

用户进入 Risk Watch：

1. 点击 Run Risk Scan；
2. 查看数据采集进度；
3. 查看多 Agent 分析；
4. 查看 Current Risk；
5. 查看 7-Day Outlook；
6. 查看 Historical Trend；
7. 查看本轮数据质量与证据。

---

# 13. 数据与模型展示原则

## 13.1 真实数据与模拟数据

主产品界面不得把模拟数据伪装成真实数据。

如未来为测试保留模拟数据，必须明确：

> Synthetic / Test Data

## 13.2 Model Output

模型输出不能直接以长段原始文本占据主界面。

必须转化为：

- Summary
- Findings
- Evidence
- Confidence
- Limitations

## 13.3 Risk Score

Risk Index 必须：

- 可复现；
- 可解释；
- 与公式或规则引擎对应；
- 与“概率”严格区分。

---

# 14. UI 级别的产品原则

v1.0 UI 以：

> **Geospatial Intelligence × AI Mission Control**

为冻结方向。

具体视觉规范将在：

`05_MountainGuardian_UI_UX_Design_Spec_v1.0.md`

中定义。

本 PRD 只冻结：

- 地图必须是主要视觉工作面之一；
- Multi-Agent 协作必须成为主视觉亮点；
- Risk Result 必须清晰突出；
- Evidence 必须易于追踪；
- 长文本不得成为主要信息表达方式；
- 免责声明应低干扰但真实存在。

---

# 15. 非功能需求

## 15.1 性能

演示环境下：

- 首页应可正常快速打开；
- Risk Scan 运行过程中必须有进度反馈；
- 单个模型失败不得导致整个页面崩溃；
- 可选数据源失败不得导致整个扫描失败。

## 15.2 稳定性

- Historical Replay 必须支持 deterministic fallback；
- 模型不可用时必须能够显示明确降级状态；
- 主页面不得因一张卫星图下载失败而崩溃。

## 15.3 可追溯性

每次风险分析应至少有：

- scan_id / run_id；
- timestamp；
- data sources；
- model status；
- agent outputs；
- risk result；
- critic result。

## 15.4 在线访问

v1.0 必须可通过 Azure 公开 URL 浏览。

不要求用户登录。

## 15.5 移动端

v1.0 以桌面浏览器为主。

移动端只要求页面不完全不可用，不做独立移动端适配工程。

---

# 16. 功能优先级

## P0 — v1.0 必须完成

- Overview
- Historical Replay
- Run Risk Scan
- Current Risk
- 7-Day Outlook
- Historical Trend
- Risk Watch Snapshot 创建与持久化
- 3 Professional Agents
- Risk Synthesizer
- Critic / Reviewer
- DeepSeek V4.1 Flash 真模型接入
- Deterministic Risk Engine
- Evidence Provenance
- Data Leakage Guard
- Azure Online Deployment
- 商业级 UI 主框架

## P1 — 有时间则完成

- Remote Sensing Vision 实际调用
- 更多 Risk Watch 数据源
- 更丰富 Evidence Center
- 更详细 Audit Log
- Risk Scan 快照浏览 / 管理增强界面
- 地图更多辅助图层

## P2 — v1.1 / Future

- GPT-6 Sol 第二模型 Reviewer
- 自动周扫描
- Azure Key Vault
- 复杂实时水文数据
- 冰川动态传感数据
- 更多区域 / 更多历史案例
- 30 天未来预测
- 季节风险预测
- 3D GIS
- 云数据库
- 生产级预警发布

---

# 17. 明确不属于 v1.0 的产品需求

v1.0 不要求：

- 对全国进行实时监测；
- 用户自定义任意地图区域；
- 完整 GIS 编辑工具；
- 多用户账号；
- 复杂 RBAC；
- 真实短信 / 邮件预警；
- 自动联系救援部门；
- 精确预测灾害发生时间；
- 灾害发生概率；
- 30 天未来风险；
- 季节风险；
- 多模型自动路由；
- 自研遥感模型；
- 自治 Agent 自行创建新 Agent；
- 复杂工作流编排 UI。

---

# 18. v1.0 产品验收场景

最终演示至少通过以下三个场景。

## Scenario A — Overview

用户打开公开 URL：

- 页面正常；
- 地图显示；
- 当前风险显示；
- Agent 状态显示；
- Historical Replay / Risk Watch 入口明确。

## Scenario B — Historical Replay

用户打开吉隆案例：

- 灾前信息与灾后验证分离；
- 3 个专业 Agent 有分析结果；
- Risk Index 能复现；
- Critic 能指出限制；
- 不产生 data leakage；
- Evidence 可查看。

## Scenario C — Risk Watch

用户点击 Run Risk Scan：

- 至少一组最新真实数据被获取；
- 形成 snapshot；
- Agent 真正调用模型；
- 输出 Current Risk；
- 输出 7-Day Outlook；
- Historical Trend 更新；
- 数据缺失有明确提示；
- 结果和模型调用可在 Audit 中追踪。

---

# 19. 产品成功标准

MountainGuardian v1.0 被认为产品层面完成，需要同时满足：

1. 用户可以不看说明书理解产品核心价值；
2. Historical Replay 和 Risk Watch 均可运行；
3. 多智能体协作在界面中真实可见；
4. 真实数据和真实模型均进入系统；
5. 风险结论有证据；
6. Critic 能表达限制；
7. 产品没有夸大预测能力；
8. 界面达到专业 AI / Geospatial 原型产品水平；
9. 在线 URL 可被评审访问；
10. 所有 P0 功能完成。

---

# 20. 与后续文档的关系

本 PRD 冻结“做什么”，不冻结“具体怎么实现”。

后续文件分别负责：

- `02_MountainGuardian_Scientific_Data_Baseline_v1.0.md`  
  冻结科学问题、数据与风险表达边界。

- `03_MountainGuardian_AI_Agent_Architecture_v1.0.md`  
  冻结模型与 Agent 具体工作方式。

- `04_MountainGuardian_Risk_Watch_Design_v1.0.md`  
  冻结 Risk Watch 数据采集、快照与风险计算流程。

- `05_MountainGuardian_UI_UX_Design_Spec_v1.0.md`  
  冻结具体视觉、组件和页面布局。

- `06_MountainGuardian_Engineering_Deployment_Spec_v1.0.md`  
  冻结代码、Git、Secret、Azure 与测试工程规范。

---

# 21. 一句话产品验收定义

> **MountainGuardian v1.0 应让用户通过一个专业的地理空间 AI 界面，真实运行历史案例验证和当前风险扫描，看到多个专业 AI Agent 如何基于真实证据形成风险判断、接受独立复核，并最终得到可解释、可追溯的当前风险与 7 天展望。**
