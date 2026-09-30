# MountainGuardian UI/UX Design Specification v1.0
## 山河守望者 v1.0 UI/UX 设计规范（冻结版）

**文档状态：** FROZEN / 已冻结  
**上位依据：**
- `00_MountainGuardian_Project_Foundation_v1.0.md`
- `01_MountainGuardian_Product_Requirements_v1.0.md`
- `02_MountainGuardian_Scientific_Data_Baseline_v1.0.md`
- `03_MountainGuardian_AI_Agent_Architecture_v1.0.md`
- `04_MountainGuardian_Risk_Watch_Design_v1.0.md`

**目标产品版本：** MountainGuardian v1.0  
**选定视觉方向：** 第二套效果图 —— **Geospatial Intelligence / 地理空间智能平台风格**  
**设计定位：** **Geospatial Intelligence × AI Mission Control**  
**文档目的：** 冻结 v1.0 的信息架构、页面布局、视觉体系、核心组件、交互规则、风险表达方式、地图呈现方式、多智能体协作呈现方式、证据与审计呈现方式以及 UI 级验收标准。  
**非本文件范围：** 不冻结底层 Python 类、数据库表、API 实现、Azure 部署脚本和 Claude Code Battle Plan。

---

# 0. Selected Visual Reference — 已选视觉参考

MountainGuardian v1.0 已正式选择此前三套 UI 概念方案中的：

> **第二套：Geospatial Intelligence / 地理空间智能平台风格**

作为 v1.0 的主要视觉方向参考。

项目仓库中的正式参考图路径冻结为：

```text
docs/mountainguardian_v1/assets/ui_reference_geospatial_intelligence.png
```

该参考图属于本 UI/UX Design Spec 的组成部分。

## 0.1 参考图冻结的内容

实现时应继承以下核心设计语言：

- 深色高端地理空间智能平台气质；
- 中央大地图 / 卫星地形作为主要工作面；
- 地图上叠加源区、关键路径、暴露区域和监测点；
- 多智能体节点围绕地图和分析流程组织；
- 右侧突出 Current Risk、Risk Trend、Top Drivers；
- 底部整合 Historical Replay、Evidence、Audit / Safety 等辅助信息；
- 深海军蓝为主背景；
- cyan / glacier blue 作为数据与地理空间主色；
- 少量橙红表达风险；
- 少量 AI purple 表达模型 / Agent；
- 商业级 Mission Control / Geospatial Intelligence 产品气质；
- 高信息密度，但保持明确层级和足够留白。

## 0.2 参考图不冻结的内容

参考图中的以下内容不得被 Claude Code 视为正式数据或正式功能定义：

- 示例 Risk Index；
- 示例百分比；
- 示例趋势；
- 示例日期；
- 示例 Data Source 数量；
- 示例 Agent 数量；
- 示例风险因素比例；
- 图中为视觉展示而出现、但未被 00–04 文档冻结的功能；
- 图中可能存在的 3D、复杂图层或重型 GIS 表现。

因此：

> **参考图冻结“视觉语言与版式方向”，不冻结其中的示例数据、科学结论或未确认功能。**

## 0.3 实现优先级规则

当参考图、本文文字规范与其他冻结文档之间发生差异时，优先级固定为：

```text
00 Project Foundation
↓
01 Product Requirements
↓
02 Scientific & Data Baseline
↓
03 AI & Agent Architecture
↓
04 Risk Watch Design
↓
05 UI/UX Design Spec
↓
Selected Visual Reference Image
```

即：

- **功能、数据、科学边界**：以 00–04 为准；
- **页面结构、视觉系统、交互表达**：以本文为准；
- **整体风格和版式气质**：参考选定效果图；
- **不得为了像参考图而实现超出 v1.0 范围的复杂功能。**

## 0.4 实现目标

Claude Code 的目标不是对参考图进行像素级复刻，而是：

> **在 Streamlit 技术栈和 v1.0 功能范围内，尽可能实现同一等级的 Geospatial Intelligence 视觉语言、空间结构和产品质感。**

---


# 1. 设计目标

MountainGuardian v1.0 的 UI 不应只是“把算法结果放到网页上”。

它必须让用户在第一眼就理解：

> **这是一个以地理空间为主工作面、以多智能体 AI 为分析核心、以证据和风险结果为输出的灾害风险智能平台。**

UI 必须同时做到：

1. **一眼知道系统在监测哪里**
2. **一眼知道当前风险是什么**
3. **一眼看到多个 Agent 正在协作**
4. **一眼知道结论来自哪些证据**
5. **一眼看出 Historical Replay 与 Risk Watch 是两种不同模式**
6. **保持科学克制，不把研究型风险判断包装成官方预警**

---

# 2. 视觉总方向

冻结视觉方向：

> **Geospatial Intelligence × AI Mission Control**

参考气质：

- 高端地理空间智能平台；
- AI 任务控制中心；
- 科研决策辅助系统；
- 商业级 SaaS 原型；
- 深色专业控制台。

避免：

- 学生作品感；
- 科技海报风；
- 游戏 UI；
- 赛博朋克霓虹堆叠；
- 大面积渐变；
- 过度动画；
- 复杂 3D GIS；
- 大段文字报告直接铺在页面上。

---

# 3. 核心视觉原则

## 3.1 地图优先

MountainGuardian 的核心工作面必须是：

> **2D 地理空间 / 卫星地形地图**

地图用于承载：

- 监测区域；
- 源区；
- 吉隆口岸；
- 关键沟道 / 路径；
- 暴露区域；
- 监测点；
- 风险标记；
- 当前扫描区域。

地图不是纯背景图。

---

## 3.2 数据优先于装饰

重要信息优先级：

> 风险结果 > 地图 > Agent 状态 > 证据 > 日志 > 装饰

任何视觉元素如果不能帮助用户：

- 理解风险；
- 理解数据；
- 理解 Agent；
- 理解证据；

都不应占据重要空间。

---

## 3.3 大数字 + 短文本

主页面避免长篇 AI 文本。

优先使用：

```text
72 / 100
ELEVATED

↑ +8
Risk Rising

Required Data
6 / 6

Agents
5 / 5
```

详细解释放入：

- Expand；
- Drawer；
- Tab；
- Detail Panel。

---

# 4. v1.0 信息架构

v1.0 固定为四个主入口：

```text
01 Overview
02 Historical Replay
03 Risk Watch
04 Intelligence Center
```

Intelligence Center 内含三个 Tab：

```text
Agent Workspace
Evidence Center
Audit & Safety
```

左侧主导航保持固定。

---

# 5. 全局页面框架

桌面端建议采用：

```text
┌──────────────────────────────────────────────────────────────┐
│ Top Header                                                   │
├────────────┬─────────────────────────────────────────────────┤
│            │                                                 │
│ Left       │                                                 │
│ Navigation │            Main Workspace                       │
│            │                                                 │
│            │                                                 │
├────────────┴─────────────────────────────────────────────────┤
│ Optional Footer / Scientific Note                            │
└──────────────────────────────────────────────────────────────┘
```

---

# 6. 左侧导航

建议宽度：

```text
220–260 px
```

包含：

### Logo 区

- 山河守望者
- MountainGuardian
- 小型山体 / 地形图标

### 主导航

- 总览 / Overview
- 历史验证 / Historical Replay
- 风险监测 / Risk Watch
- 智能中心 / Intelligence Center

### 底部状态

小型：

- Research Prototype
- v1.0
- System Online / Degraded

避免在左侧导航放大量说明文字。

---

# 7. 顶部 Header

全局 Header 建议包含：

左侧：

- 当前页面名称；
- 当前监测区域。

右侧：

- Model Runtime
- Last Scan
- Data Sources
- Active Agents

例如：

```text
西藏 · 吉隆口岸

● System Online
Last Scan: 10:32
Data Sources: 6
Agents: 5/5
```

Header 高度保持克制。

---

# 8. Overview 页面目标

Overview 必须在 10 秒内回答：

1. 监测哪里？
2. 风险多高？
3. 风险在升还是降？
4. 最近有没有扫描？
5. AI Agent 有没有正常运行？
6. 历史验证与当前监测从哪里进入？

---

# 9. Overview 页面结构

冻结为：

```text
┌───────────────────────────────────────────────────────┐
│ Header / System Status                                │
├───────────────────────────────────────┬───────────────┤
│                                       │               │
│                                       │ Current Risk  │
│            Main Map                   │               │
│                                       │ 72 / 100      │
│                                       │ ELEVATED      │
│                                       │               │
├───────────────────────┬───────────────┴───────────────┤
│ Agent Collaboration   │ Risk Trend / Recent Scan      │
├───────────────────────┼───────────────────────────────┤
│ Historical Replay     │ Evidence / Data Coverage      │
└───────────────────────┴───────────────────────────────┘
```

地图占据最大视觉面积。

---

# 10. Overview 主地图

## 10.1 地图类型

v1.0 使用：

> **2D Satellite / Terrain Map**

不做 3D。

## 10.2 必须显示

至少：

- 吉隆口岸位置；
- Source Zone；
- Port Zone；
- 关键沟道；
- 下游暴露区；
- Monitoring Points；
- 当前扫描区域。

## 10.3 地图图层

v1.0 只保留少量固定图层：

```text
Base Satellite / Terrain
Source Zone
Hazard Path
Exposure Area
Monitoring Points
```

不做复杂图层管理器。

## 10.4 地图交互

最低交互：

- hover / click marker；
- zoom；
- pan；
- marker tooltip；
- fit region。

不要求：

- 绘图；
- 编辑多边形；
- 动态 GIS 分析；
- 复杂空间查询。

---

# 11. Overview — Current Risk Card

右侧风险卡必须是主视觉之一。

结构：

```text
CURRENT RISK

72 / 100
ELEVATED

Trend
↑ +8

Evidence
Required 6/6
Optional 1/4

Last Updated
2026-09-30 10:32
```

必须包含小字：

> Risk Index — not event probability

避免：

> “72% 泥石流概率”

---

# 12. Risk Color System

统一颜色语义：

## LOW
绿色

## MODERATE
青绿 / 黄绿色

## ELEVATED
橙色

## HIGH
红色

但页面不得使用官方：

- 蓝色预警；
- 黄色预警；
- 橙色预警；
- 红色预警；

作为法定术语。

只使用：

```text
LOW
MODERATE
ELEVATED
HIGH
```

---

# 13. Agent Collaboration 组件

Overview 中展示简洁 Agent 网络：

```text
Glacier / Geology
          \
Weather / Hydrology → Risk Synthesizer → Critic
          /
Remote Sensing
```

## 每个 Agent 只显示：

- Name
- Status
- Confidence
- Evidence Count

例如：

```text
Glacier / Geology
● Completed
Confidence 0.86
5 Evidence
```

不在 Overview 展开完整推理文本。

---

# 14. Agent 状态颜色

统一：

```text
PENDING     灰
RUNNING     蓝 / 青
COMPLETED   绿
SKIPPED     灰蓝
DEGRADED    橙
FAILED      红
```

SKIPPED 不应视觉上像 FAILED。

---

# 15. Historical Replay 页面定位

页面主题：

> **Historical Replay / Research Validation**

核心问题：

> 如果只使用灾前数据，系统能够识别哪些风险？

页面不是“灾害故事展示页”，而是：

> **可验证的 AI 分析实验页**

---

# 16. Historical Replay 页面结构

建议：

```text
┌────────────────────────────────────────────────────┐
│ Case Header                                        │
├────────────────────────────────────────────────────┤
│ PRE-EVENT ───────── EVENT ───────── POST-EVENT     │
├──────────────┬──────────────────────┬───────────────┤
│ Evidence     │ Agent Reasoning      │ Risk Result   │
│              │                      │               │
├──────────────┴──────────────────────┴───────────────┤
│ Post-event Validation                              │
└────────────────────────────────────────────────────┘
```

---

# 17. Historical Replay 时间线

顶部固定显示三阶段：

```text
PRE-EVENT
2026-08-24

EVENT
2026-08-26

POST-EVENT
2026-08-27
```

重点：

- PRE-EVENT 为蓝 / 青；
- EVENT 为橙；
- POST-EVENT 为紫 / 灰；

避免用户误解灾后数据进入灾前分析。

---

# 18. Historical Replay Evidence Panel

左侧证据栏分组：

```text
Terrain
Glacier / Cryosphere
History
Weather Context
Satellite
```

每条 Evidence 显示：

- 类型；
- 来源；
- 日期；
- Phase；
- Quality。

例如：

```text
Sentinel-2
2026-08-24
PRE-EVENT
Quality: GOOD
```

---

# 19. Historical Replay Agent Reasoning

中间区域是多 Agent 展示主舞台。

Agent Card：

```text
Glacier / Geology Agent
Status: Completed
Confidence: 0.86

Key Findings
• 巨大高差
• 高位冰冻圈源区
• 狭窄沟谷
• 松散物源

Evidence
E-01 E-03 E-07
```

三个专业 Agent 先显示。

下方：

```text
Risk Synthesizer
↓
Critic / Reviewer
```

---

# 20. Historical Replay Risk Result

右侧突出：

```text
BASELINE SUSCEPTIBILITY

91 / 100
HIGH

Top Drivers
01 Huge Relief
02 Cryosphere Source Zone
03 Loose Materials
04 Historical Recurrence
```

必须有：

> Baseline Susceptibility Index  
> Not event probability

---

# 21. Critic Card

Critic 视觉上与其他 Agent 区分。

建议使用：

- 紫色 / 蓝紫；
- Shield 图标；
- “Review”标签。

显示：

```text
PASS WITH LIMITATIONS

✓ No post-event leakage
✓ Risk Index ≠ Probability
! No real-time source-zone sensors
! Exact timing cannot be predicted
```

Critic 不做大段文字。

---

# 22. Post-event Validation

页面底部显示：

- 灾后 Sentinel-2；
- 官方灾害路径；
- 调查确认源区；
- 实际灾害链。

文案：

> **Post-event Validation**

而不是：

> “AI prediction confirmed”

建议结果：

```text
Pre-event Risk Factors Identified
5 / 6 aligned with post-event investigation
```

如果该比例未来正式实现，必须来源于确定性比较，不由 LLM 随意产生。

---

# 23. Risk Watch 页面定位

页面主题：

> **Risk Watch / 当前风险监测**

核心交互只有一个：

> **Run Risk Scan**

必须让用户清楚看到一次扫描到底做了什么。

---

# 24. Risk Watch 页面结构

建议：

```text
┌────────────────────────────────────────────────────┐
│ Region / Last Scan / RUN RISK SCAN                 │
├─────────────────┬────────────────┬─────────────────┤
│ Current Risk    │ 7-Day Outlook  │ Data Coverage   │
├────────────────────────────────────────────────────┤
│ Scan Progress / What Changed                       │
├───────────────────────────┬────────────────────────┤
│ Historical Trend          │ Drivers / Evidence     │
└───────────────────────────┴────────────────────────┘
```

---

# 25. Run Risk Scan Button

作为页面唯一主 CTA：

```text
Run Risk Scan
立即执行风险扫描
```

按钮状态：

```text
READY
RUNNING
COMPLETED
COMPLETED WITH LIMITATIONS
FAILED
```

运行中不得允许用户连续重复点击。

---

# 26. Scan Progress

不用复杂动画。

使用明确步骤：

```text
1 Collect Data          ✓
2 Normalize             ✓
3 Save Snapshot         ✓
4 Agent Analysis        ●
5 Risk Synthesis        ○
6 Critic Review         ○
```

用户必须知道系统不是“黑箱等待”。

---

# 27. Current Risk Card

结构与 Overview 保持一致。

显示：

- Current Risk Index；
- Risk Level；
- Risk Direction；
- Last Scan；
- Required Coverage。

---

# 28. 7-Day Outlook Card

显示：

```text
7-DAY OUTLOOK

76 / 100
ELEVATED
↑ Rising

Main Driver
Forecast precipitation above local baseline
```

必须标注：

> Outlook Index — not event probability

---

# 29. Historical Trend

折线图只显示真实 Snapshot：

X：

```text
Scan Date
```

Y：

```text
Risk Index 0–100
```

如只有一条：

> 历史数据不足，完成更多扫描后将形成趋势。

不得放模拟未来曲线。

---

# 30. What Changed

使用简洁比较卡：

```text
Since Last Scan

Recent Rainfall     ↑
Forecast Rainfall   ↑
Risk Index          +6
Satellite           No new imagery
Hydrology           Not available
```

数字比较由代码生成。

LLM 只负责解释。

---

# 31. Data Coverage

建议显示：

```text
Required
6 / 6

Optional
1 / 4
```

并支持展开：

```text
Weather          Available
Terrain          Available
Cryosphere       Available
History          Available
Satellite        No new imagery
Hydrology        Missing optional
ENSO             Not used
```

---

# 32. Intelligence Center 页面定位

Intelligence Center 不作为用户第一入口。

用于：

> **解释系统如何工作。**

包含三个 Tab：

```text
Agent Workspace
Evidence Center
Audit & Safety
```

---

# 33. Agent Workspace

## 33.1 页面目标

证明：

> Multi-Agent 是真实架构，不是宣传词。

## 33.2 主布局

左 / 中：

Agent Cards

右：

Selected Agent Detail

## 33.3 Agent Card

至少显示：

```text
Agent Name
Model
Status
Confidence
Evidence Count
Latency
```

## 33.4 展开详情

显示：

- Input Summary
- Key Findings
- Evidence IDs
- Limitations
- Structured Output
- Prompt Version（开发模式可见）

默认不直接展示完整系统 Prompt。

---

# 34. Evidence Center

按类别 Tab：

```text
Satellite
Weather
Terrain
Cryosphere
Historical
Hydrology
```

若无 Hydrology：

> 显示 Empty / Optional Source

不是隐藏。

---

# 35. Evidence Card

结构统一：

```text
Evidence ID
Type
Source
Observation Date
Phase
Quality
Used By
```

下方：

> Observation / Summary

对图片：

- Thumbnail
- Full View
- Caption
- Cloud Cover
- Pre / Post / Current

---

# 36. Audit & Safety

页面目标：

> **展示系统是受控的。**

顶部状态卡：

```text
Model Runtime
Connected

Data Leakage Guard
Active

Output Schema
Valid

External Actions
Disabled
```

---

# 37. Audit Log

表格即可。

字段：

```text
Time
Run ID
Agent
Action
Status
Latency
Fallback
```

点击一行查看详情。

v1.0 不做复杂查询系统。

---

# 38. Scientific Disclaimer

不再使用首页大红框。

采用三级方式：

## Level 1 — 产品级

左侧底部：

> Research Prototype

## Level 2 — 页面级

Historical Replay：

> Historical Replay / Research Validation

Risk Watch：

> Research risk assessment — not an official disaster warning

## Level 3 — 关键数值旁

Risk Index 下：

> Not event probability

这样既专业，又保留科学边界。

---

# 39. 视觉 Design System

## 39.1 Background

主背景：

```text
#07111F
```

深海军蓝 / near black。

## 39.2 Primary Panel

```text
#101C2D
```

## 39.3 Secondary Panel

```text
#142338
```

## 39.4 Border

低对比蓝灰：

```text
rgba(120,160,200,0.15~0.25)
```

---

# 40. Accent Colors

## Glacier / Data Cyan

```text
#37D7E8
```

## AI Purple

```text
#8B7CFF
```

## Normal Green

```text
#42D392
```

## Elevated Orange

```text
#FFB454
```

## High Risk Red

```text
#FF5E6C
```

## Neutral Text

```text
#DCE7F3
```

## Secondary Text

```text
#8799AD
```

---

# 41. 色彩使用规则

颜色必须表达语义。

不要：

- 每张卡片一个颜色；
- 大面积紫色；
- 大面积高饱和 cyan；
- 彩虹渐变。

建议：

- 背景 80%
- 中性色 15%
- Accent 5%

---

# 42. Typography

优先系统字体：

中文：

```text
Microsoft YaHei
PingFang SC
Noto Sans SC
```

英文：

```text
Inter
Arial
Helvetica
```

不强制引入外部 Web Font。

---

# 43. Typography Scale

建议：

```text
Page Title          28–32 px
Section Title       18–22 px
Card Number         32–48 px
Card Title          14–16 px
Body                13–15 px
Metadata            11–12 px
```

避免超大海报式标题。

---

# 44. Spacing

建议 8pt grid：

```text
8
16
24
32
```

主要卡片 padding：

```text
16–20 px
```

卡片间距：

```text
12–16 px
```

---

# 45. Radius

建议：

```text
8–12 px
```

避免过度圆角。

---

# 46. Shadow / Glow

只允许很轻微：

- cyan border glow；
- active Agent glow；
- risk highlight。

不做：

- 霓虹灯边框；
- 大面积发光；
- cyberpunk effect。

---

# 47. 图标

优先：

- Lucide style
- Material Symbols style
- 简单线性图标

保持统一。

避免：

- emoji 作为正式图标；
- 复杂 3D icon；
- 风格混杂。

---

# 48. Chart Style

所有图表：

- 深色底；
- 细网格线；
- 单一主线；
- Highlight 当前点；
- Tooltip 简洁。

避免：

- 3D chart；
- 饼图堆叠；
- 过多颜色。

---

# 49. Risk Gauge

不建议复杂仪表盘。

优先：

```text
72 / 100
ELEVATED
```

辅以：

- 环形进度；
- 横条；
- 小型趋势箭头。

数字必须比图形重要。

---

# 50. 地图风格

建议：

- Dark satellite / terrain basemap；
- 保留自然地形；
- Overlay 控制透明度；
- 风险面不遮盖地图。

Source Zone：

> cyan / blue

Path：

> orange

Exposure：

> red / transparent

Monitoring Point：

> cyan pin

---

# 51. 动画

v1.0 只允许：

- Agent running pulse；
- Scan progress；
- chart transition；
- card loading skeleton。

不做：

- 地图飞行动画；
- 粒子效果；
- 背景动态云；
- 炫技过场。

---

# 52. Loading State

每个数据块必须有：

```text
Loading
Loaded
Unavailable
Error
```

避免一片空白。

---

# 53. Empty State

例如没有卫星图：

> No usable new satellite imagery for this scan.

没有历史趋势：

> Historical trend will appear after more scans.

没有 Hydrology：

> Optional hydrology source not connected.

Empty State 本身也是系统可信度的一部分。

---

# 54. Error State

Error 信息分层：

## User level

短句：

> Weather data unavailable.

## Detail

展开：

- source；
- timestamp；
- error code。

不直接把 Python traceback 放给普通用户。

---

# 55. Fallback Mode UI

模型失效时必须明显但不过度惊慌：

```text
AI Runtime
Fallback Mode
```

主结果继续显示：

- Deterministic Risk Index；
- Rule-based explanation。

但不得显示成：

> AI analysis completed normally

---

# 56. Responsive

v1.0 以：

> **Desktop-first**

为主。

推荐目标宽度：

```text
1440 px
```

最低：

```text
1280 px
```

移动端：

- 不做独立设计；
- 允许自然纵向堆叠；
- 保证文字可读；
- 地图不崩溃。

---

# 57. Streamlit 实现原则

v1.0 仍可基于 Streamlit 实现。

UI Design 不要求迁移：

- React；
- Next.js；
- Vue。

重点是：

> **通过结构化布局、CSS、组件和地图库，把 Streamlit 做得像产品。**

不为纯视觉原因重写前端技术栈。

---

# 58. 建议 UI 技术策略

可使用：

- Streamlit layout；
- CSS theme；
- Plotly / Altair charts；
- Folium / PyDeck / Streamlit map integration；
- reusable card functions；
- HTML/CSS 组件（适度）。

选择标准：

> **稳定 > 可维护 > 演示效果 > 技术炫耀**

---

# 59. 页面数据源原则

UI 不自己计算风险。

UI 只读取：

- View Model；
- Risk Result；
- Agent Output；
- Evidence；
- Audit。

禁止：

> 在 UI 层重新计算 Risk Index。

---

# 60. UI View Model

建议每页先形成统一：

```text
OverviewViewModel
HistoricalReplayViewModel
RiskWatchViewModel
IntelligenceViewModel
```

这样：

- 数据层；
- Agent 层；
- UI 层；

保持分离。

---

# 61. 关键名词统一

中文 / 英文建议固定：

```text
山河守望者 / MountainGuardian

总览 / Overview
历史验证 / Historical Replay
风险监测 / Risk Watch
智能中心 / Intelligence Center

冰川地质智能体 / Glacier & Geology Agent
气象水文智能体 / Weather & Hydrology Agent
遥感解译智能体 / Remote Sensing Agent
风险综合智能体 / Risk Synthesizer
评审智能体 / Critic / Reviewer

当前风险 / Current Risk
7天风险展望 / 7-Day Outlook
历史风险趋势 / Historical Trend

风险指数 / Risk Index
风险等级 / Risk Level
证据覆盖 / Evidence Coverage
```

---

# 62. 禁止 UI 表述

禁止：

```text
AI 成功预测了吉隆灾害
91% 发生概率
未来 7 天泥石流概率 72%
官方预警
实时预警中心
红色预警
精准预测
```

除非将来有真实科学依据或官方发布内容。

---

# 63. 推荐 UI 表述

推荐：

```text
Historical Replay
Research Validation
Baseline Susceptibility Index
Current Risk Index
7-Day Outlook
Risk Rising
Evidence Limited
PASS WITH LIMITATIONS
AI Visual Observation
Research Prototype
Not an official disaster warning
```

---

# 64. Overview 最终演示路径

评委打开 URL：

### Step 1
看到：

> 山河守望者 + 地图 + 当前风险

### Step 2
看到：

> 多 Agent 协作

### Step 3
进入：

> Historical Replay

### Step 4
看到：

> 91 / 100 + Critic + 灾后验证

### Step 5
进入：

> Risk Watch

### Step 6
点击：

> Run Risk Scan

### Step 7
看到：

> 真实数据 → Agent → Current Risk → 7-Day Outlook

### Step 8
进入：

> Intelligence Center

看到：

> Evidence + Audit + Safety

整个故事闭环。

---

# 65. 首页第一屏必须避免的信息

Overview 第一屏不要出现：

- 大段研究说明；
- 开源 License；
- 详细 Agent Prompt；
- 数据字段表；
- 完整来源列表；
- 技术栈说明；
- 比赛说明；
- 过长免责声明。

这些内容放到：

- Intelligence Center；
- About；
- Footer；
- Research Report。

---

# 66. 视觉 Reference 使用原则

正式视觉参考图：

```text
docs/mountainguardian_v1/assets/ui_reference_geospatial_intelligence.png
```

该图是 MountainGuardian v1.0 的：

> **Selected Visual Direction Reference**

实现时：

> 不要求像素级复刻，但不得偏离其核心视觉语言和页面层次。

Claude Code 应继承：

- 深色 Geospatial Intelligence 主工作面；
- 中央地图作为视觉核心；
- Source Zone / Path / Exposure / Monitoring Points 的地图叠加；
- Agent 节点与分析流程的空间关系；
- 右侧 Current Risk / Trend / Drivers；
- 底部 Historical Replay / Evidence / Audit 信息区；
- cyan + dark navy + limited orange/red + limited AI purple 的颜色体系；
- 高端商业控制台的整体气质。

但不得为了复刻参考图而：

- 引入复杂 3D GIS；
- 添加 00–04 未冻结的数据；
- 制造虚假实时信息；
- 增加不必要的复杂图层；
- 把示例数字当成真实系统输出。

实现应根据 Streamlit 的稳定性做合理简化。

---

# 67. v1.0 UI 明确不做

- 3D GIS；
- 地图编辑器；
- 图层自由配置；
- 用户上传 ShapeFile；
- 自定义任意监测区域；
- 大屏自适应控制中心；
- 手机专属版本；
- 动态粒子背景；
- AI Avatar；
- 聊天机器人主入口；
- 大型消息中心；
- 用户账号系统；
- 复杂 Dashboard Builder；
- 自定义主题系统；
- 重型前端框架迁移。

---

# 68. UI 开发优先级

## P0

- 左侧导航；
- Header；
- Overview；
- 2D Map；
- Current Risk；
- Agent Collaboration；
- Historical Replay；
- Risk Watch；
- Run Risk Scan；
- Historical Trend；
- Intelligence Center；
- Evidence Center；
- Audit & Safety；
- Fallback 状态；
- Scientific disclaimer。

## P1

- 更精细地图 Overlay；
- 图像弹窗；
- 更丰富 Tooltip；
- Agent 详情 Drawer；
- 更丰富 Audit detail；
- 更细致 Loading animation。

## P2

- 3D；
- 多区域；
- Mobile-first；
- Advanced map layers；
- User customization。

---

# 69. UI 验收标准

UI/UX 只有满足以下条件才算 v1.0 完成：

1. 四个主入口可稳定访问；
2. 左侧导航一致；
3. 地图是 Overview 主视觉；
4. Current Risk 在第一屏清晰可见；
5. Risk Index 与 Probability 区分；
6. 多 Agent 协作在视觉上清楚；
7. SKIPPED 与 FAILED 明确区分；
8. Historical Replay 有 Pre / Event / Post 时间线；
9. Post-event evidence 不与 pre-event 混淆；
10. 91/100 正确标记为 Baseline Susceptibility；
11. Critic 状态清楚；
12. Risk Watch 有唯一主 CTA：Run Risk Scan；
13. Scan Progress 清楚；
14. Current Risk / 7-Day Outlook / Historical Trend 均可见；
15. Historical Trend 不展示伪造未来数据；
16. Missing Optional Data 有明确 Empty State；
17. Intelligence Center 包含 3 个 Tab；
18. Evidence 能追踪来源与 Phase；
19. Audit 能显示 Model / Agent / Guard 状态；
20. Fallback Mode 有明确 UI；
21. 不出现官方预警式误导语言；
22. 不出现大红色科普警告框；
23. Desktop 1280–1440 px 下布局稳定；
24. Streamlit 仍保持可维护；
25. 选定的 Geospatial Intelligence 视觉方向得到体现。

---

# 70. 页面验收快照建议

UI 开发完成后至少保存以下截图作为项目证据：

1. Overview
2. Historical Replay — Agent Analysis
3. Historical Replay — Post-event Validation
4. Risk Watch — Before Scan
5. Risk Watch — Running
6. Risk Watch — Completed
7. Agent Workspace
8. Evidence Center
9. Audit & Safety
10. Fallback Mode

这些截图未来可用于：

- 比赛研究报告；
- 开发记录；
- 展示视频；
- GitHub README。

---

# 71. 一句话 UI 定义

> **MountainGuardian v1.0 的界面是一套以 2D 地理空间地图为核心工作面、以多智能体协作为主要视觉叙事、以风险结果和证据为核心信息输出的深色专业 AI 控制台；它应看起来像真实商业级 Geospatial Intelligence 产品，而不是科技海报或学生 Demo。**
