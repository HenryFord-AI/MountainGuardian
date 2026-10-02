# MountainGuardian G05C Localization Addendum v1.0
## 山河守望者 v1.0 G05C 比赛中文本地化增补（冻结版）

**文档状态：** FROZEN / 已冻结  
**文档性质：** Battle Plan 增补（Addendum）— 不重写、不重新编号 00–07 冻结文档  
**Commander：** ChatGPT  
**Engineering Executor：** Claude Code  
**目标仓库：** `D:\HenryFord-AI\MountainGuardian`  
**目标版本：** MountainGuardian v1.0  
**Commander 批准时间：** 2026-10-02（G05C Gate 指令下达）

**上位冻结依据：**
- `00_MountainGuardian_Project_Foundation_v1.0.md`
- `01_MountainGuardian_Product_Requirements_v1.0.md`
- `02_MountainGuardian_Scientific_Data_Baseline_v1.0.md`
- `03_MountainGuardian_AI_Agent_Architecture_v1.0.md`
- `04_MountainGuardian_Risk_Watch_Design_v1.0.md`
- `05_MountainGuardian_UI_UX_Design_Spec_v1.0.md`
- `06_MountainGuardian_Engineering_Deployment_Spec_v1.0.md`
- `07_MountainGuardian_Battle_Plan_v1.0.md`

---

# 1. Gate 序列修订

在 G05B 与 G06 之间插入一个窄范围、Commander 批准的比赛交付 Gate：

```text
G05B — Custom Domain & HTTPS（已关闭）
↓
G05C — Competition Chinese Localization（比赛中文本地化）
↓
G06 — Release Candidate（发布候选 / 比赛冻结）
```

**修订理由：**
G06 比赛冻结之前，Commander 确认当前生产界面（https://mountainguardian.cn）
仍保留大量英文用户可见文本。比赛评审场景为上海 / 中国评审上下文，
比赛交付产品应做到：

> 中国评委在不理解英文的情况下，也能够完整理解并操作 MountainGuardian 产品。

因此插入 G05C，将公开比赛界面转为中文优先（Chinese-first）。

# 2. G05C 范围（Scope）

**G05C 是纯表现层（presentation-layer-only）本地化 Gate：**

- 仅修改用户可见 UI 文本的展示语言与展示映射；
- 允许新增小型共享展示映射模块（状态 / 风险等级 / 质量 / 智能体显示名）；
- 允许因中文文本长度所需的有界 CSS / 布局微调；
- 允许修改范围：`frontend/`、`mountainguardian_app.py`、`tests/`、
  `docs/mountainguardian_v1/`。

**G05C 明确不做（Explicitly out of scope）：**

- 无新产品功能（no new product feature）；
- 无科学变更（no scientific change）；
- 无 Risk 公式变更（no Risk formula change）；
- 无 Agent 架构变更（no Agent architecture change）；
- 无数据源扩展（no data-source expansion）；
- 无数据库 Schema 变更（no database schema change）；
- 无部署架构变更（no deployment architecture change）；
- 无 DNS 变更（no DNS change）；
- 无 TLS / 证书变更；
- G06 仍然是最终的 Release Candidate / Competition Freeze Gate。

以下目录在 G05C 中要求零语义变更：

```text
agents/  providers/  riskwatch/  orchestration/  security/
database schema  Case Pack 科学数据  Azure 基础设施  DNS  TLS  GitHub 部署架构
```

# 3. 中文优先原则

v1.0 比赛发布界面语言为中文。

**明确不实现：**

- 语言选择器（language selector）；
- i18n 框架；
- locale 自动检测；
- 浏览器语言切换；
- 双语产品模式。

界面不再使用“当前风险 · Current Risk”“风险监测 / Risk Watch”式双语标题。
可见导航固定为：

```text
总览
历史验证
风险监测
情报中心
```

说明：doc 05 §61 关键名词表使用“智能中心 / Intelligence Center”。
G05C Commander 指令明确比赛可见导航使用“情报中心”。
“情报中心”与“智能中心”指向同一冻结页面（Intelligence Center），
本增补以 Commander G05C 指令为准，页面功能、结构、Tab 组成不变。

品牌规则：

- 正式产品品牌 `MountainGuardian` 与 `山河守望者` 可并列出现
  （MountainGuardian 为品牌名，不翻译）；
- 不翻译、不修改正式域名与产品品牌。

# 4. 技术标识符允许清单（Technical Identifier Allowlist）

以下机器 / 溯源 / 品牌标识符保持英文原样，用于可审计性与溯源，
不属于“未翻译的界面文本”：

```text
MountainGuardian  DeepSeek  deepseek-flash  Open-Meteo  Sentinel-2
Run ID 值  Evidence ID 值（如 RW-STATIC-TERRAIN、EV-SAT-POST-*、
rw-20261002T…、g04b-ui-replay）
model ID  provider ID  数据库 / 运行标识符
UTC  URL  HTTP / HTTPS  Azure  GitHub
机器枚举原值（后端持久化值不变，仅展示层映射为中文）
```

展示层对状态、风险等级、数据质量、相位等枚举做中文展示映射；
底层 enum / 运行时值一律不改。

# 5. 冻结术语与展示映射（G05C 比赛版）

风险等级（仅翻译标签，四档冻结语义与后端枚举不变）：

```text
LOW → 低   MODERATE → 中等   ELEVATED → 较高   HIGH → 高
```

禁止使用官方预警术语：蓝色预警 / 黄色预警 / 橙色预警 / 红色预警。

主要界面术语：

```text
Current Risk → 当前风险          7-Day Outlook → 未来7天风险展望
Data Coverage → 数据覆盖          Scan Progress → 扫描进度
What Changed → 风险变化           Historical Trend → 历史风险趋势
Risk Index → 风险指数             Risk Level → 风险等级
Main Risk Drivers → 主要风险驱动因素
Pre-event Evidence → 灾前证据     Multi-Agent Analysis → 多智能体分析
Risk Result → 风险评估结果
Baseline Susceptibility Index → 基线易感性指数
Not event probability → 不是事件发生概率
Post-event Validation → 灾后验证  Scientific Limitations → 科学局限
Agent Workspace → 智能体工作区    Evidence Center → 证据中心
Audit & Safety → 审计与安全       Model Runtime → 模型运行状态
Evidence Coverage → 证据覆盖      Key Findings → 关键发现
Evidence Used → 使用证据          Missing Data → 缺失数据
Limitations → 局限                Execution Time → 执行耗时
Confidence → 置信度               Evidence Count → 证据数量
Run Risk Scan（主 CTA）→ 执行风险扫描
```

智能体可见名称（类名 / ID / prompt_id 不变）：

```text
冰川地质智能体  气象水文智能体  遥感解译智能体  风险综合智能体  评审智能体
```

安全控制可见标签（控制逻辑与 ID 不变）：

```text
Prompt Injection Guard → 提示词注入防护
Data Leakage Guard → 数据泄漏防护
Post-event Leakage Guard → 灾后信息泄漏防护
Output Schema Validation → 输出结构校验
External Actions Disabled → 外部操作已禁用
```

# 6. 科学语言边界（继承全部冻结禁令）

G05C 本地化不得引入任何被禁止的表述，包括其中文等价形式：

```text
AI成功预测了吉隆灾害   91%发生概率   未来7天泥石流概率72%
官方预警   实时预警中心   红色预警   精准预测
```

必须保持等价表述：

```text
风险指数不是事件发生概率。
研究原型。
非官方灾害告警（不是官方灾害预警的等价表述）。
```

历史验证页 91 / 100 高 的确定性结果不变；
仍必须清晰标注“基线易感性指数”“不是事件发生概率”；
Stage A / Stage B 分离不变；不得将结果重新解释为概率。

# 7. 模型输出语言检查规则

实施前必须先检查真实 / 持久化模型输出语言：

- 若模型生成内容（findings、synthesis、critic）已为中文：后端保持不动；
- 若存在持续英文的用户可见模型生成内容：不得静默修改 Agent Prompt，
  必须报告 `LANGUAGE_OUTPUT_BLOCKER`（角色、字段、英文示例、
  表现层无法安全解决的原因）并停止该项修改，等待 Commander 批准。

G05C 实施时检查结果：真实持久化 DeepSeek 运行输出
（key_findings、synthesis summary、critic scientific_limitations）
均为中文；确定性回退输出为中文（`[规则回退]` 前缀）。
未触发 LANGUAGE_OUTPUT_BLOCKER。

# 8. G05C 验收标准

工程验收：

1. 四个页面全部本地化；导航、按钮、Tab、状态、风险等级、数据质量、
   安全控制、局限 / 免责文本全部中文；
2. 技术标识符允许清单保持英文原样；
3. 本地化语言审计测试通过（含显式技术允许清单，不采用“禁止所有
   A–Z”式测试）；
4. 全量 pytest 通过；`pip check` 通过；
5. 无后端 / 科学变更；
6. PR 合并；main 回归通过；GitHub Actions 部署通过；
7. https://mountainguardian.cn 生产验证通过；
8. 四张生产页面视觉证据可供 Commander 审查。

最终关闭（CLOSED）额外要求：

> Commander Chinese Visual Acceptance PASS。

在 Commander 视觉验收之前，G05C 最高报告状态为：

```text
PASS — READY_FOR_COMMANDER_CHINESE_VISUAL_ACCEPTANCE
```

# 9. 缺陷修复规则

若 Commander 视觉验收发现本地化缺陷：
在同一 G05C 会话内使用有界 G05C remediation 分支修复；
G05C 最终关闭之前不启动 G06。

（本增补完）
