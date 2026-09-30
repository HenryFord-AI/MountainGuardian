# MountainGuardian AI & Agent Architecture v1.0
## 山河守望者 v1.0 AI 与多智能体架构设计（冻结版）

**文档状态：** FROZEN / 已冻结  
**上位依据：**
- `00_MountainGuardian_Project_Foundation_v1.0.md`
- `01_MountainGuardian_Product_Requirements_v1.0.md`
- `02_MountainGuardian_Scientific_Data_Baseline_v1.0.md`

**目标产品版本：** MountainGuardian v1.0  
**文档目的：** 冻结 v1.0 的模型接入方式、多智能体组成、固定工作流、各 Agent 职责、输入输出 Schema、确定性风险引擎边界、Critic 机制、Fallback、安全边界、日志与验收规则。  
**非本文件范围：** 不在本文中冻结 Risk Watch 的具体数据 API、UI 视觉细节、Azure 部署脚本、数据库完整表结构和 Claude Code Battle Plan。

---

# 1. 架构目标

MountainGuardian v1.0 的 AI 系统必须同时满足五个目标：

1. **真实 AI**  
   至少一个核心分析路径真实调用大模型，而不是用固定文案模拟。

2. **真实 Multi-Agent**  
   不同专业 Agent 有独立职责、独立输入、独立结构化输出。

3. **可复现 Risk**  
   Risk Index 由确定性 Risk Engine 计算，不由 LLM 自由生成。

4. **可复核**  
   Risk Synthesizer 的综合结论必须经过独立 Critic / Reviewer。

5. **可降级**  
   模型、遥感或可选数据不可用时，系统仍能以明确状态完成安全降级，而不是崩溃或伪造结果。

---

# 2. v1.0 总体架构

v1.0 冻结为固定 DAG（Directed Acyclic Graph）工作流：

```text
                       ┌─────────────────────┐
                       │   Data / Evidence   │
                       │   Allowed Context   │
                       └──────────┬──────────┘
                                  │
                    ┌─────────────┼─────────────┐
                    │             │             │
                    ▼             ▼             ▼
          Glacier / Geology   Weather /      Remote Sensing
               Agent          Hydrology Agent     Agent
                    │             │             │
                    └─────────────┼─────────────┘
                                  ▼
                       Deterministic Risk Engine
                                  │
                                  ▼
                         Risk Synthesizer
                                  │
                                  ▼
                         Critic / Reviewer
                                  │
                                  ▼
                         Final Risk Result
```

外围系统 Guard：

```text
Prompt Injection Guard
Data Leakage Guard
Post-event Leakage Guard
Output Schema Validation
Evidence Provenance
Audit Logging
External Actions Disabled
```

---

# 3. v1.0 不采用自治型 Agent Network

v1.0 明确不实现：

- Agent 自己创建新 Agent；
- Agent 自由选择下一位 Agent；
- 递归 Agent 对话；
- 无上限反思循环；
- 自由工具调用；
- Agent 自主向外部系统写入或发送消息。

原因：

- 难以测试；
- 难以审计；
- Token 成本不可控；
- 结果不稳定；
- 对本项目展示价值有限。

v1.0 的 Multi-Agent 价值来自：

> **专业分工 + 独立分析 + 结构化汇总 + 反向复核**

而不是复杂自治。

---

# 4. 模型策略

## 4.1 v1.0 主模型

产品名称：

> **DeepSeek-V4.1-Flash**

API 调用模型 ID：

> **`deepseek-flash`**

截至 2026-09-30，DeepSeek 官方 API 文档显示：

- `deepseek-flash` 对应最新 DeepSeek-V4.1-Flash；
- 支持原生多模态视觉理解；
- DeepSeek API 提供 OpenAI / Anthropic 兼容协议。

代码和配置中应使用：

```text
deepseek-flash
```

而不是把展示名称 `DeepSeek-V4.1-Flash` 直接当 API model id。

## 4.2 单模型原则

v1.0 只接入一个真实 Model Provider。

以下角色均可使用同一模型：

- Glacier / Geology Agent；
- Weather / Hydrology Agent；
- Remote Sensing Agent；
- Risk Synthesizer；
- Critic / Reviewer。

角色差异通过：

- 不同 System Prompt；
- 不同 Input Schema；
- 不同 Evidence 权限；
- 不同 Output Schema；
- 不同 temperature / reasoning 配置（如 Provider 支持）；

实现。

## 4.3 Future

第二模型 Reviewer、多模型投票、自动模型路由等全部属于 v1.1 / Future，不进入 v1.0 P0。

---

# 5. Provider Abstraction

虽然 v1.0 只使用一个模型 Provider，代码仍应通过轻量 Provider abstraction 接入。

建议逻辑接口：

```python
class ModelProvider:
    def generate_structured(self, request) -> ModelResult:
        ...

    def generate_multimodal(self, request, images) -> ModelResult:
        ...

    def health_check(self) -> ProviderHealth:
        ...
```

v1.0 实现：

```text
DeepSeekProvider
```

未来可增加：

```text
OpenAIProvider
OtherProvider
```

但不进入本轮实现范围。

目的不是做复杂框架，而是避免 Agent 代码直接绑定某个 SDK。

---

# 6. Provider 配置原则

Provider 配置至少包括：

- model_id；
- base_url；
- api_key reference；
- timeout；
- retry policy；
- max output tokens；
- multimodal capability；
- structured output capability；
- provider status。

Secret 不得写入：

- Python 文件；
- JSON 配置；
- Git；
- Prompt；
- Agent log。

具体 Secret 管理方式由 Engineering & Deployment Spec 冻结。

---

# 7. 核心运行上下文 AnalysisContext

所有 Agent 不直接读取整个数据库或整个 Case Pack。

Coordinator 为每次运行构造受控：

> **AnalysisContext**

建议核心字段：

```text
run_id
mode
region_id
analysis_time
allowed_evidence[]
static_baseline
dynamic_snapshot
weather_forecast
data_quality
missing_sources[]
risk_engine_inputs
previous_snapshot_summary
scientific_constraints
```

其中：

```text
mode = historical_replay | risk_watch
```

Historical Replay 与 Risk Watch 使用同一 Agent 框架，但 AnalysisContext 权限不同。

---

# 8. Evidence 对象

进入模型的重要证据必须使用统一 EvidenceItem。

建议字段：

```text
evidence_id
evidence_type
source_name
source_reference
observation_time
phase
quality
raw_or_derived
summary
value
unit
allowed_agents[]
```

Agent Prompt 应优先引用 `evidence_id`，而不是复制大量无来源文本。

Agent 输出中的关键结论必须能够回指 Evidence ID。

---

# 9. 三个专业 Agent

v1.0 只保留三个专业 Agent：

1. Glacier / Geology Agent
2. Weather / Hydrology Agent
3. Remote Sensing Agent

三个 Agent 在逻辑上相互独立。

默认工作方式：

> **可并行执行**

任何一个 Agent 不应读取另一个 Agent 的输出后再修改自己的专业判断。

这样能够保留真正的：

> Independent Expert Analysis

---

# 10. Glacier / Geology Agent

## 10.1 职责

负责分析：

- 高程与高差；
- 坡度和峡谷环境；
- 冰川 / 冰冻圈背景；
- 高位冰岩环境；
- 沟道；
- 松散物源；
- 历史地质 / 链式灾害信息；
- 下游暴露相关静态地理条件。

## 10.2 不负责

不负责：

- 天气预报；
- 自己计算最终 Risk Index；
- 判断具体灾害发生时间；
- 读取 post-event validation 后倒推灾前结论。

## 10.3 输出结构

建议：

```json
{
  "agent": "glacier_geology",
  "status": "COMPLETED",
  "risk_signal": "HIGH",
  "confidence": 0.86,
  "findings": [],
  "evidence_ids": [],
  "risk_drivers": [],
  "missing_data": [],
  "limitations": []
}
```

`confidence` 是对当前专业分析的信心，不是灾害发生概率。

---

# 11. Weather / Hydrology Agent

## 11.1 Historical Replay 职责

仅分析灾前允许的：

- 季节 / 雨季背景；
- 已存在的公开气象背景；
- 允许的水文背景信息。

如果历史实时气象数据不足：

> 明确输出 Data Limited。

不得用灾后天气信息补齐。

## 11.2 Risk Watch 职责

重点分析：

- 当前温度；
- 过去 7 天降水；
- 最大日降水；
- 未来 7 天天气；
- 未来累计降水；
- 可选土壤湿度；
- 可选水位 / 流量。

## 11.3 输出结构

建议：

```json
{
  "agent": "weather_hydrology",
  "status": "COMPLETED",
  "risk_signal": "ELEVATED",
  "confidence": 0.82,
  "recent_conditions": [],
  "forecast_signals": [],
  "evidence_ids": [],
  "missing_data": [],
  "limitations": []
}
```

---

# 12. Remote Sensing Agent

## 12.1 Historical Replay

可以分析：

- 灾前 Sentinel-2；
- pre-event 可使用图件。

风险分析阶段不得看到：

- 灾后 Sentinel-2；
- 实际灾害路径；
- 灾后调查标注。

风险结论完成后，可在 Validation 阶段查看 post-event evidence。

## 12.2 Risk Watch

只有满足以下条件才运行动态遥感分析：

- 存在新的遥感影像；
- 影像日期有效；
- 云量 / 质量达到最低条件；
- Evidence metadata 完整。

否则返回：

```text
SKIPPED_NO_USABLE_IMAGERY
```

而不是伪造遥感结果。

## 12.3 Vision LLM 定位

DeepSeek-V4.1-Flash 支持多模态，因此 v1.0 可以把可用影像提交给 Remote Sensing Agent 做：

> **AI Visual Observation**

输出必须与：

> Official / Algorithmic Remote-Sensing Conclusion

区分。

## 12.4 输出结构

建议：

```json
{
  "agent": "remote_sensing",
  "status": "COMPLETED | SKIPPED",
  "risk_signal": "MODERATE",
  "confidence": 0.74,
  "image_ids": [],
  "observations": [],
  "quality_notes": [],
  "evidence_ids": [],
  "limitations": []
}
```

---

# 13. Deterministic Risk Engine

Risk Engine 是系统中与 LLM 独立的确定性模块。

## 13.1 职责

负责：

- Risk Index；
- Risk Level 映射；
- 因子贡献；
- Snapshot 间变化；
- Historical Trend 数值；
- 必要的阈值判断。

## 13.2 Historical Replay

使用 Jilong Case Pack 冻结的 6 因子风险模型。

当前基线：

> **91 / 100**

同样输入必须始终复算得到同样结果。

## 13.3 Risk Watch

Risk Watch 的动态风险算法将在：

`04_MountainGuardian_Risk_Watch_Design_v1.0.md`

进一步冻结。

本文件只规定：

> Risk Synthesizer 不允许覆盖 Risk Engine 输出的数值。

---

# 14. Risk Synthesizer

Risk Synthesizer 是多 Agent 结果的综合者，不是新的风险计算器。

## 14.1 输入

输入包括：

- 3 个专业 Agent 的结构化结果；
- Deterministic Risk Engine 输出；
- Evidence Coverage；
- Missing Data；
- Data Quality；
- Previous Snapshot（Risk Watch 时）。

## 14.2 职责

负责：

- 汇总一致结论；
- 标出 Agent 冲突；
- 解释 Risk Index；
- 排序 Top Risk Drivers；
- 形成 Current Risk narrative；
- Risk Watch 时形成 7-Day Outlook；
- 明确主要不确定性。

## 14.3 禁止

Risk Synthesizer 不得：

- 修改 Risk Index；
- 自己重新创造权重；
- 输出概率；
- 隐藏 Agent 分歧；
- 补造缺失证据。

## 14.4 输出结构

建议：

```json
{
  "risk_index": 72,
  "risk_level": "ELEVATED",
  "risk_trend": "RISING",
  "top_drivers": [],
  "agent_agreement": "PARTIAL_AGREEMENT",
  "evidence_coverage": 0.78,
  "summary": "",
  "outlook_7d": "",
  "limitations": []
}
```

---

# 15. Critic / Reviewer

Critic 是 v1.0 最重要的可靠性机制之一。

它的任务不是再次生成一份漂亮结论，而是：

> **主动寻找当前结论为什么可能不成立。**

## 15.1 Review 维度

至少检查：

1. Evidence 是否充分；
2. Evidence 是否可追溯；
3. 是否存在 post-event leakage；
4. 是否存在因果过度推断；
5. Risk Index 是否被错误写成 Probability；
6. Missing Data 是否被隐藏；
7. Agent 是否明显冲突；
8. 结论是否超出数据支持范围；
9. 7-Day Outlook 是否真实依赖天气预报；
10. 遥感结论是否超出 AI visual observation 边界。

## 15.2 Critic 输出

建议：

```json
{
  "review_result": "PASS_WITH_LIMITATIONS",
  "severity": "LOW",
  "issues": [],
  "scientific_limitations": [],
  "required_corrections": [],
  "approved_claims": [],
  "prohibited_claims": []
}
```

允许结果：

- PASS
- PASS_WITH_LIMITATIONS
- NEEDS_REVISION
- BLOCKED

---

# 16. Historical Replay 的 Critic 与 Validation 分离

Historical Replay 中必须逻辑上分成两个步骤：

## Stage A — Scientific Review

Critic 只读取：

- 灾前允许数据；
- 专业 Agent 输出；
- Risk Engine；
- Synthesizer。

完成：

> 对“灾前风险分析本身”的复核。

## Stage B — Post-event Validation

只有 Stage A 完成后，系统才允许读取：

- `post_event_validation`
- 灾后 Sentinel-2；
- 官方路径；
- 实际事件结果。

Stage B 回答：

> 灾前已经识别的风险条件与灾后调查结果如何对应？

**Stage B 不允许回写或修改 Stage A 的 Risk Index。**

---

# 17. Risk Watch Critic

Risk Watch 没有 post-event validation 阶段。

Critic 重点检查：

- Required Data 完整性；
- Optional Evidence 缺失；
- 数据是否过期；
- 天气 forecast 时间窗口；
- Agent disagreement；
- Risk Index 是否可解释；
- 7-Day Outlook 是否夸大；
- 是否缺少足够动态证据。

---

# 18. Agent Agreement

专业 Agent 输出必须保留独立性。

Risk Synthesizer 计算 / 判断：

- AGREEMENT
- PARTIAL_AGREEMENT
- SIGNIFICANT_DISAGREEMENT

如 Significant Disagreement：

- 不允许隐藏；
- Risk Synthesizer 必须说明冲突；
- Critic 必须判断是否需要降低结论强度。

---

# 19. Structured Output

所有核心 Agent 必须使用结构化输出。

原则：

> **先 Schema，后 Prompt。**

不能让产品逻辑依赖模型自由生成的一段 Markdown。

最低要求：

- JSON 可解析；
- 字段可验证；
- enum 可约束；
- Evidence ID 可追溯；
- Confidence 范围可验证；
- Missing Data 必须显式字段。

---

# 20. Output Schema Validation

每个模型调用后：

```text
Model Output
   ↓
JSON Parse
   ↓
Schema Validation
   ↓
Scientific Constraint Validation
   ↓
Accept / Repair / Fallback
```

不得把无法解析或越界输出直接展示到主界面。

---

# 21. Repair Policy

模型第一次返回无效结构时：

允许：

> **一次 bounded repair**

即把 Schema error 返回模型，要求只修复结构。

不允许：

- 无限 retry；
- 无限 self-reflection；
- 无限 Agent 对话。

第二次仍失败：

> 进入 fallback。

---

# 22. Fallback 设计

v1.0 必须保留原 RescueMind / MountainGuardian 已有的 deterministic fallback 思路。

## 22.1 Provider Failure

如果 DeepSeek API：

- timeout；
- 401 / 403；
- rate limit；
- service unavailable；
- invalid response；

系统应：

1. 明确记录 Provider Error；
2. 不伪装成真实 AI 输出；
3. 使用 deterministic / rule fallback；
4. UI 显示：

> **Fallback Mode**

## 22.2 Agent Failure

单个专业 Agent 失败：

- 其他 Agent 继续；
- Synthesizer 获知该 Agent 缺失；
- Evidence Coverage 降低；
- Critic 明确指出。

## 22.3 Risk Engine Failure

Risk Engine 属于关键路径。

如果确定性 Risk Engine 无法运行：

> 不允许生成正式 Risk Index。

可以展示 Agent observations，但最终结果必须标记：

> **Risk calculation unavailable**

---

# 23. Model Health Check

系统至少支持：

```text
Provider Connected
Provider Degraded
Provider Offline
Fallback Active
```

Overview / Audit & Safety 应能显示当前 Model Runtime 状态。

Health Check 不应每次刷新页面都产生高额 Token 调用。

---

# 24. Prompt 架构原则

每个 Agent Prompt 至少包含：

## A. Role
明确专业角色。

## B. Task
本轮唯一任务。

## C. Allowed Data
明确允许读取什么。

## D. Forbidden Claims
明确不能说什么。

## E. Scientific Constraints
例如：

- Risk Index ≠ Probability；
- 不补造 Missing Data；
- 不把 ENSO 当具体因果；
- 不读取 post-event。

## F. Evidence Requirement
关键结论引用 Evidence ID。

## G. Output Schema
只返回规定结构。

---

# 25. Prompt 不承载安全边界

Prompt 中可以重复安全规则，但：

> **真正的数据隔离不能只靠 Prompt。**

例如 post-event leakage 必须通过：

- Data Loader；
- Context Builder；
- Agent Input Schema；

在模型调用之前完成。

Prompt 只是第二道防线。

---

# 26. Token 与上下文控制

v1.0 不把整个 Case Pack、全部日志或全部数据库塞给每个 Agent。

原则：

> **Minimum Necessary Context**

每个 Agent 只收到：

- 与本职责相关的 Evidence；
- 必要 static baseline；
- 本轮 dynamic snapshot；
- 科学约束。

目标：

- 降低 Token；
- 降低噪声；
- 降低 data leakage；
- 提高可解释性。

---

# 27. Parallel Execution

三个专业 Agent 在数据准备完成后允许并行执行：

```text
Glacier / Geology ─┐
Weather / Hydrology ├─→ Barrier → Risk Synthesizer
Remote Sensing ────┘
```

Remote Sensing 被 SKIPPED 时：

> Barrier 不等待不存在的视觉任务。

是否采用真正 Python async / thread 实现，由工程规范和现有代码结构决定；产品层只要求逻辑并行、职责独立。

---

# 28. Agent Status

统一状态枚举建议：

- PENDING
- RUNNING
- COMPLETED
- SKIPPED
- DEGRADED
- FAILED

UI 不应只显示“成功 / 失败”，应区分：

> SKIPPED because no usable data

与：

> FAILED because system error

---

# 29. Confidence

Agent Confidence 表示：

> Agent 对自己在当前数据条件下形成的专业判断的信心。

它不是：

- Risk Probability；
- Model Accuracy；
- Event Probability。

v1.0 Confidence 建议范围：

```text
0.00 – 1.00
```

Confidence 必须结合：

- Evidence Coverage；
- Data Quality；
- Missing Data；

解释。

---

# 30. Evidence Coverage

建议系统单独计算 / 汇总：

> **Evidence Coverage**

它表示本轮应有证据中实际可获得的覆盖程度。

例如：

```text
Required sources: 5
Available: 5
Optional sources: 4
Available: 1
```

Evidence Coverage 可以帮助解释为什么：

- Risk Index 较高；
- 但 Confidence 仍有限。

---

# 31. External Tool 权限

v1.0 Agent 默认只允许：

> **Read / Analyze**

不允许：

- 发邮件；
- 发短信；
- 发预警；
- 修改外部数据库；
- 控制设备；
- 上传公开社交平台；
- 触发真实救援动作。

数据采集器可以调用允许的公开 API，但数据采集器与 LLM Agent 逻辑分离。

---

# 32. Security Guard 与 Agent 分离

系统 Guard 属于基础设施，不属于 AI Agent。

至少包括：

```text
Input Validation
Prompt Injection Detection
Evidence Phase Filter
Tool Allowlist
Output Schema Validator
Audit Logger
```

UI 可以在 Audit & Safety 中展示这些 Guard 状态，但不需要创建一个“Safety Agent”。

---

# 33. Audit Logging

每次模型调用至少记录：

- run_id；
- agent_id；
- model_id；
- start_time；
- end_time；
- status；
- input evidence IDs；
- output schema version；
- fallback used；
- error type；
- token usage（API 提供时）；
- latency；
- prompt version。

默认不在普通 UI 展示完整 Prompt 内容。

---

# 34. Prompt Versioning

每个 Agent Prompt 建议拥有：

```text
prompt_id
prompt_version
```

例如：

```text
glacier_geology_v1
weather_hydrology_v1
remote_sensing_v1
risk_synthesizer_v1
critic_v1
```

后续 Prompt 修改可以审计。

---

# 35. Run ID

每次：

- Historical Replay 分析；
- Risk Watch 扫描；

必须生成唯一：

> **run_id**

所有：

- Evidence；
- Agent output；
- Risk result；
- Critic result；
- Log；

通过 run_id 关联。

---

# 36. 两种运行模式

## 36.1 Historical Replay

固定顺序：

```text
Load Case Pack
→ Phase Filter
→ Build Pre-event Context
→ Professional Agents
→ Deterministic Risk Engine
→ Risk Synthesizer
→ Critic Stage A
→ Freeze Pre-event Result
→ Load Post-event Validation
→ Validation Stage B
→ Final Historical Replay Report
```

关键要求：

> Post-event data 只能在 Pre-event Result 冻结之后加载。

## 36.2 Risk Watch

固定顺序：

```text
Collect Latest Data
→ Normalize
→ Store Snapshot
→ Compare Previous Snapshot
→ Build AnalysisContext
→ Professional Agents
→ Deterministic Risk Engine
→ Risk Synthesizer
→ Critic
→ Persist Final Result
```

---

# 37. 当前 RescueMind 代码的复用原则

优先复用已有：

- `BaseAgent`
- `CoordinatorAgent`
- `AgentResponse`
- SQLite logging
- SecurityManager
- Demo / fallback pattern

但不受原始 RescueMind 的“灾害响应 Agent 列表”限制。

v1.0 的 Agent 命名、职责和工作流以本文件为准。

---

# 38. 建议代码模块边界

不冻结具体文件名，但建议逻辑拆分：

```text
providers/
    base_provider
    deepseek_provider

agents/
    glacier_geology_agent
    weather_hydrology_agent
    remote_sensing_agent
    risk_synthesizer
    critic_agent

risk/
    deterministic_engine

schemas/
    evidence
    agent_outputs
    risk_result

orchestration/
    context_builder
    workflow

guards/
    leakage
    schema
    tool_permissions
```

Claude Code 可以结合现有仓库结构做最小侵入式实现。

---

# 39. v1.0 明确不做

AI / Agent 层不做：

- 第二 Model Provider；
- 多模型 voting；
- GPT-6 Reviewer；
- Agent 自主规划；
- 无限 ReAct；
- 无限 Reflection；
- Agent 创建 Agent；
- 复杂 Memory System；
- Vector Database；
- RAG 平台化建设；
- MCP Server 架构重构；
- DeepSeek Harness 迁移；
- 大规模知识图谱；
- 自研模型训练；
- 微调；
- Autonomous Tool Use；
- 真实外部预警动作。

这些不得进入 v1.0 Battle Plan，除非 Foundation 重新冻结。

---

# 40. AI 架构验收标准

AI & Agent Architecture 只有在以下条件全部满足时才算完成：

1. `deepseek-flash` 真实 API 调用成功；
2. API Key 不进入 Git；
3. Provider health check 可用；
4. 3 个专业 Agent 职责分离；
5. 三个专业 Agent 可独立执行；
6. 所有核心 Agent 使用结构化输出；
7. 输出经过 schema validation；
8. Agent 关键结论引用 Evidence ID；
9. Remote Sensing 无图时正确 SKIP；
10. Risk Index 只来自 Deterministic Engine；
11. Risk Synthesizer 不能修改 Risk Index；
12. Critic 能识别科学边界问题；
13. Historical Replay Stage A 无 post-event leakage；
14. Stage B 不能回写 Stage A Risk Index；
15. Risk Watch 可在 Optional Evidence 缺失时运行；
16. Provider failure 可降级到 fallback；
17. 单 Agent failure 不导致整个系统崩溃；
18. Risk Engine failure 时不伪造风险分数；
19. run_id 贯穿所有分析对象；
20. Agent / model / fallback / error 均有 audit log；
21. 不存在真实外部发送动作；
22. 自动化测试覆盖核心权限和 fallback。

---

# 41. 官方模型信息验证快照

本架构在 2026-09-30 对 DeepSeek 官方公开资料进行了实现前核对。

确认：

- 产品模型：DeepSeek-V4.1-Flash；
- API model id：`deepseek-flash`；
- 原生支持多模态视觉输入；
- 支持 OpenAI / Anthropic 兼容 API 方式。

正式实现时仍应以 DeepSeek 当日 `/models` 返回和官方文档为准。

参考来源：

- DeepSeek API Docs — Change Log，2026-09-10 DeepSeek-V4.1-Flash Release
- DeepSeek API Docs — First API Call
- DeepSeek API Docs — Lists Models

---

# 42. 与后续文档关系

本文件冻结：

> **AI 怎么思考、各 Agent 怎么分工、模型和确定性算法如何合作。**

下一份：

`04_MountainGuardian_Risk_Watch_Design_v1.0.md`

负责进一步冻结：

- 哪些真实数据源；
- 怎么采集；
- 怎么形成 Snapshot；
- Dynamic Risk Index 怎么计算；
- 7-Day Outlook 怎么形成；
- Historical Trend 怎么生成。

`05_MountainGuardian_UI_UX_Design_Spec_v1.0.md`

只负责：

> 如何把上述 AI 系统清晰、美观地呈现给用户。

`06_MountainGuardian_Engineering_Deployment_Spec_v1.0.md`

负责：

> Provider、Secret、Git、Testing、Azure 等工程实现规则。

---

# 43. 一句话 AI 架构定义

> **MountainGuardian v1.0 采用“固定编排的专业多智能体 + 确定性风险引擎 + 独立 Critic”的混合 AI 架构：三个专业 Agent 基于受控证据独立分析，确定性引擎计算可复现的 Risk Index，Risk Synthesizer 负责综合解释，Critic 负责主动寻找证据、逻辑与科学边界问题，并在模型或数据缺失时安全降级。**
