# MountainGuardian Risk Watch Design v1.0
## 山河守望者 v1.0 Risk Watch 风险监测设计（冻结版）

**文档状态：** FROZEN / 已冻结  
**上位依据：**
- `00_MountainGuardian_Project_Foundation_v1.0.md`
- `01_MountainGuardian_Product_Requirements_v1.0.md`
- `02_MountainGuardian_Scientific_Data_Baseline_v1.0.md`
- `03_MountainGuardian_AI_Agent_Architecture_v1.0.md`

**目标产品版本：** MountainGuardian v1.0  
**文档目的：** 冻结 Risk Watch 的运行边界、区域配置、真实数据源、扫描流程、Snapshot 结构、动态风险算法、7-Day Outlook、Historical Trend、数据质量、降级机制、遥感可选流程以及 v1.0 验收标准。  
**非本文件范围：** 不冻结 UI 视觉细节、Azure 部署脚本、模型 Prompt 全文和 Claude Code Battle Plan。

---

# 1. Risk Watch 的产品定位

Risk Watch 用于证明 MountainGuardian 不仅能够回放历史灾害案例，还能够：

> **读取当前真实环境数据，形成新的风险快照，并持续比较区域风险状态的变化。**

v1.0 的 Risk Watch 是一个：

> **On-demand Regional Risk Scan / 手动触发区域风险扫描**

而不是生产级实时预警系统。

用户点击：

> **Run Risk Scan / 立即执行风险扫描**

系统完成：

```text
Collect
→ Normalize
→ Validate
→ Store Snapshot
→ Compare
→ Professional Agents
→ Deterministic Risk Engine
→ Risk Synthesizer
→ Critic
→ Persist Result
```

---

# 2. v1.0 核心输出

Risk Watch v1.0 只冻结三个主要风险结果：

## 2.1 Current Risk

当前风险状态，包括：

- Current Risk Index；
- Risk Level；
- 更新时间；
- 主要风险驱动因素；
- Evidence Coverage；
- Confidence / limitations。

## 2.2 7-Day Outlook

未来 7 天风险展望，包括：

- 未来 7 天风险方向；
- 7-Day Outlook Index / Band；
- 未来降水等主要天气驱动；
- 不确定性；
- 缺失证据。

## 2.3 Historical Trend

只使用已经真实执行过的 Risk Watch Snapshot，展示：

- 扫描日期；
- Current Risk Index；
- Risk Level；
- 变化方向。

v1.0 不实现：

- 30 天未来风险预测；
- 季节风险预测；
- 灾害发生概率；
- 精确灾害发生时间预测。

---

# 3. Historical Replay 与 Risk Watch 必须数据隔离

Historical Replay 与 Risk Watch 使用同一个 Agent 框架，但不使用同一个运行数据入口。

## 3.1 Historical Replay Source of Truth

继续使用：

```text
data/cases/jilong_20260826/case.json
```

该文件包含历史案例的 pre-event 与 post-event 数据，因此必须通过 phase filter 使用。

## 3.2 Risk Watch Region Source of Truth

v1.0 建议新建独立区域配置：

```text
data/regions/jilong_port/region.json
```

Risk Watch **不得直接把历史 Case Pack 整体作为实时扫描上下文**。

`region.json` 只保存允许用于持续监测的内容：

- region_id；
- region_name；
- monitoring points；
- static terrain baseline；
- static cryosphere baseline；
- historical hazard baseline；
- static susceptibility factors；
- source references；
- scoring configuration version。

这样可以从架构上降低 post-event leakage 风险。

---

# 4. Risk Watch 监测区域

v1.0 只监测：

> **西藏吉隆口岸及相关上游高山峡谷区域**

不支持用户在地图上任意选择全国区域。

原因：

- 数据和风险模型针对性更强；
- 避免泛化超出证据；
- 降低开发复杂度；
- 有利于形成可重复演示。

未来 v1.1 才考虑多区域配置。

---

# 5. Monitoring Points

山区天气空间差异较大，因此 v1.0 不建议仅用一个单点代表整个区域。

Risk Watch 应从 `region.json` 读取固定监测点。

最低建议：

## A. Source Zone

代表高海拔冰冻圈 / 源区环境。

## B. Port Zone

代表吉隆口岸及下游暴露区。

如 Case Pack 能可靠支持第三个中游位置，可增加：

## C. Mid-channel Zone

但第三点不是 v1.0 P0。

坐标必须来自项目已有可追溯资料或后续确认数据，本文不凭空填写坐标。

---

# 6. 数据源总体策略

Risk Watch v1.0 采用：

> **稳定核心数据 + 可选增强证据**

而不是追求“所有数据每次必须齐全”。

核心原则：

> **天气每次扫描必须可用；静态地形/冰川/历史数据本地缓存；卫星、水文等只作为可选增强。**

---

# 7. Required Data — 动态天气

v1.0 的主要实时动态数据为天气。

当前建议实现源：

> **Open-Meteo ECMWF Forecast API**

理由：

- 可按经纬度获取全球数据；
- 支持过去若干天与未来天气；
- 支持降水和温度等变量；
- 可按高度进行统计降尺度；
- 接入成本低；
- 适合作为比赛原型的稳定数据源。

v1.0 至少采集：

## Recent Conditions

- 过去 7 天每日降水；
- 过去 7 天累计降水；
- 过去 7 天最大单日降水；
- 过去 7 天温度范围。

## Forecast

- 未来 7 天每日预计降水；
- 未来 7 天累计预计降水；
- 未来 7 天温度范围；
- 未来极端天气提示（如数据字段支持）。

天气数据必须保存：

- requested coordinate；
- returned grid coordinate；
- elevation；
- observation / forecast time；
- retrieval time；
- provider / model metadata。

---

# 8. Historical Weather Baseline

为了避免直接用随意的毫米阈值判断“降水高不高”，v1.0 建立一个当地历史气候基线。

建议数据源：

> **Open-Meteo Historical Weather API / ERA5-Land**

基线时段冻结为：

> **1991-01-01 至 2020-12-31**

用途：

- 计算当地月尺度的 7 日累计降水分布；
- 为 Recent Precipitation 与 Forecast Precipitation 提供 percentile baseline。

历史基线：

- 只需初始化或低频更新；
- 不需要每次扫描重新下载；
- 应缓存到本地数据文件或数据库。

---

# 9. 为什么使用 Percentile

绝对降水量在高山区域具有明显地域和季节差异。

v1.0 不直接规定：

> “超过 X mm 就一定高风险”。

而使用：

> **该时间段的降水在当地历史分布中处于什么位置。**

例如：

- 50th percentile：接近常态；
- 75th percentile：明显偏高；
- 90th percentile：高；
- 95th percentile：很高。

Percentile 只是：

> **气象异常程度指标**

不是灾害发生概率。

---

# 10. 7-Day Precipitation Climatology

对每个 Monitoring Point：

1. 使用 1991–2020 历史日降水；
2. 计算连续 7 天累计降水；
3. 按对应自然月形成分布；
4. 保存月度 percentile reference。

例如：

```text
January:
P50
P75
P90
P95
P99

February:
...

September:
...
```

Risk Watch 运行时：

- 过去 7 天累计降水与当月历史分布比较；
- 未来 7 天累计预计降水与当月历史分布比较。

---

# 11. 多监测点聚合

每个 Monitoring Point 独立计算：

- recent_precip_percentile；
- forecast_precip_percentile。

v1.0 区域级气象触发信号采用：

> **各监测点中的较高值作为保守区域信号。**

原因：

- 高山峡谷风险可能由局部高值驱动；
- 简单平均可能稀释源区极端条件。

UI / Evidence Center 必须同时保留各点原始结果，使该保守聚合可解释。

---

# 12. Risk Watch Static Susceptibility Baseline

Historical Replay 的 `91/100` 是针对历史案例的：

> **Baseline Susceptibility Index**

其中包含历史案例特定的六因子结构。

Risk Watch 不直接把 Historical Replay 的 91 当作实时 Current Risk Index。

v1.0 应构建独立：

> **Regional Static Susceptibility Baseline（B）**

---

# 13. Static Baseline 的来源

为了避免重复设计一套完全新的权重，Risk Watch Static Baseline 从 Jilong Case Pack 已冻结模型中继承静态因子。

Historical Replay 六因子：

1. 高海拔冰冻圈源区；
2. 巨大高差与狭窄沟谷；
3. 沟道松散物源；
4. 历史链式灾害复发性；
5. 季风与高降水背景；
6. 下游暴露与口岸设施。

Risk Watch 的 Static Baseline：

> **去除第 5 项“季风与高降水背景”，防止与实时降水动态因子重复计算。**

剩余五项保持 Historical Replay 原相对权重关系，并重新归一化到 100%。

原权重：

```text
20 : 25 : 20 : 15 : 10
```

归一化后约为：

```text
22.22%
27.78%
22.22%
16.67%
11.11%
```

Risk Watch 实现时由确定性代码从 Case Pack 静态因子值重新计算：

> **B = Regional Static Susceptibility Baseline**

最终 B 数值必须在实现时由实际 Case Pack 字段确定并写入 `region.json`，本文不凭空预设具体分数。

---

# 14. Dynamic Trigger Index

v1.0 为控制科学边界和开发复杂度，动态数值评分只使用：

> **降水触发信号**

温度、土壤湿度、水文、遥感等进入 Agent 解释和 Confidence，但不直接改变 v1.0 数值 Risk Index。

定义：

```text
R = Recent 7-Day Precipitation Percentile
F = Forecast 7-Day Precipitation Percentile
```

区域级 Dynamic Trigger Index：

```text
D = 0.60 × R + 0.40 × F
```

其中：

- `R` 反映最近已经发生的水分输入；
- `F` 反映未来 7 天可能继续增加的气象压力。

D 范围：

```text
0 – 100
```

D 不是灾害概率。

---

# 15. Current Risk Index

v1.0 Current Risk Index 定义为：

```text
C = 0.70 × B + 0.30 × D
```

其中：

- `B` = Regional Static Susceptibility Baseline；
- `D` = Dynamic Trigger Index。

设计含义：

> **长期易灾背景是主体，近期气象触发用于调节当前风险状态。**

这是 MountainGuardian v1.0 的：

> **透明、可复现、研究原型型启发式风险指数**

不是经过大样本训练和概率校准的生产级灾害模型。

---

# 16. Current Risk Level

v1.0 统一使用：

```text
0–39     LOW
40–59    MODERATE
60–79    ELEVATED
80–100   HIGH
```

这些是：

> **Prototype Risk Bands / 原型风险分级**

不是法定灾害预警等级。

界面不得使用：

- 蓝色预警；
- 黄色预警；
- 橙色预警；
- 红色预警；

等可能与官方预警制度混淆的法定术语，除非明确引用官方已发布预警。

---

# 17. 7-Day Outlook Index

未来 7 天展望只使用：

- Static Baseline；
- Forecast Precipitation Percentile。

定义：

```text
O7 = 0.70 × B + 0.30 × F
```

输出：

- 7-Day Outlook Index；
- Risk Band；
- Direction；
- main weather driver；
- limitations。

它表示：

> **如果当前未来 7 天天气预报成立，区域风险背景可能处于何种水平。**

它不是未来 7 天灾害发生概率。

---

# 18. Risk Direction

与上一次有效 Snapshot 比较 Current Risk Index：

建议：

```text
ΔC >= +5       RISING
-5 < ΔC < +5   STABLE
ΔC <= -5       FALLING
```

如只有第一条 Snapshot：

```text
NO_HISTORY
```

该阈值属于产品可读性阈值，不代表科学显著性检验。

---

# 19. Optional Evidence 不改变 v1.0 数值公式

以下数据在 v1.0 中：

- 温度；
- 土壤湿度；
- 河流水位；
- Sentinel-2；
- ENSO；
- 冰川动态信息；

可以：

- 提高 / 降低 Agent Confidence；
- 形成 qualitative finding；
- 成为 Critic limitation；
- 成为 Top Evidence。

但：

> **不直接进入 C 或 O7 数值公式。**

这样保证：

- 每次扫描评分逻辑稳定；
- Optional 数据缺失不会改变算法定义；
- 不因为某周“有卫星图”、某周“没卫星图”而导致分数不可比较。

未来经过更多案例验证后，再考虑增加新的动态数值因子。

---

# 20. Temperature 的 v1.0 用法

温度属于 Required Weather Evidence，但不直接进入 v1 数值评分。

Weather / Hydrology Agent 可以使用：

- Source Zone 温度；
- Port Zone 温度；
- 升温 / 降温趋势；
- 0°C 上下变化；
- 与降水的组合关系；

解释冰雪融化、冻融环境等可能影响。

Critic 必须提醒：

> **没有直接冰川位移、裂缝或微震数据时，不能根据气温单独判断高位冰岩体即将失稳。**

---

# 21. Satellite Optional Pipeline

Risk Watch 每次扫描可以执行轻量：

> **Satellite Discovery**

而不是强制：

> Download + Process Satellite

推荐使用：

> **Copernicus Data Space Ecosystem STAC API**

目标 collection：

```text
sentinel-2-l2a
```

扫描逻辑：

```text
Search latest scene
→ Check acquisition date
→ Check cloud cover
→ Save metadata
→ If usable, optionally obtain preview / asset
→ Remote Sensing Agent
```

---

# 22. Satellite Quality Policy

建议 v1.0：

```text
Cloud Cover <= 30%      GOOD
30% < Cloud Cover <=60% LIMITED
Cloud Cover > 60%       SKIP for Risk Watch dynamic analysis
```

阈值应写入配置文件，而不是硬编码散落在 UI。

Historical Replay 已有的灾后影像即使云量较高，仍可以作为：

> **Post-event validation with explicit limitation**

但 Risk Watch 不要求使用低质量影像。

---

# 23. Remote Sensing Agent 在 Risk Watch 中的结果

如有可用新影像：

```text
COMPLETED
```

并输出：

- acquisition date；
- cloud cover；
- visual observations；
- confidence；
- limitations。

如无：

```text
SKIPPED_NO_NEW_IMAGERY
```

或：

```text
SKIPPED_LOW_QUALITY_IMAGERY
```

Risk Watch 主流程继续。

---

# 24. Optional Hydrology

v1.0 不把实时河流水位作为 P0。

如未来发现：

- 公开；
- 稳定；
- 区域匹配；
- 可自动访问；

的真实水文源，可作为 Optional Evidence 接入。

没有时：

```text
MISSING_OPTIONAL
```

不得用其他地区数据替代。

---

# 25. Soil Moisture

v1.0 可优先使用天气 / 再分析产品中可获得的土壤湿度作为辅助证据。

但由于：

- 高山地形复杂；
- 空间分辨率有限；
- 模型值并非现场传感器实测；

页面必须标记数据来源与分辨率限制。

不进入 v1.0 Current Risk Index 数值公式。

---

# 26. ENSO

ENSO 只作为：

> **Context-only climate background**

v1.0 Risk Watch 可以展示当前 ENSO 状态，但：

- 不进入 C；
- 不进入 O7；
- 不直接改变 Risk Level；
- 不作为本周风险升高的直接原因。

如实现成本影响 P0，可完全不接入 v1.0 Risk Watch。

---

# 27. Data Collection 与 LLM 分离

必须遵循：

> **Collect Data ≠ Call LLM**

数据采集由普通 Python / HTTP Client 完成。

Collector 输出结构化原始数据后才进入 Agent。

LLM 不负责：

- 浏览天气网站；
- 自己猜当前天气；
- 自己下载卫星；
- 自己判断 API endpoint；
- 修改原始 API 返回值。

---

# 28. Collector 架构

建议最小 Collector：

```text
WeatherCollector
StaticBaselineLoader
SatelliteDiscoveryCollector (Optional)
```

未来：

```text
HydrologyCollector
SoilMoistureCollector
ENSOCollector
```

但不要求 v1.0 P0 全部实现。

---

# 29. 一次 Risk Scan 的状态机

建议：

```text
CREATED
↓
COLLECTING
↓
NORMALIZING
↓
VALIDATING
↓
SNAPSHOT_SAVED
↓
ANALYZING
↓
SYNTHESIZING
↓
REVIEWING
↓
COMPLETED
```

允许：

```text
COMPLETED_WITH_LIMITATIONS
FAILED
```

UI 必须显示用户可理解的阶段，而不是只显示 Spinner。

---

# 30. Snapshot 原则

每次真实扫描必须生成唯一：

```text
scan_id / run_id
```

并形成不可覆盖的 Snapshot。

核心字段建议：

```json
{
  "scan_id": "",
  "region_id": "jilong_port",
  "scan_time": "",
  "data_version": "",
  "monitoring_points": [],
  "recent_weather": {},
  "forecast_weather": {},
  "static_baseline": {},
  "optional_evidence": [],
  "missing_sources": [],
  "data_quality": {},
  "recent_precip_percentile": null,
  "forecast_precip_percentile": null,
  "dynamic_trigger_index": null,
  "current_risk_index": null,
  "current_risk_level": "",
  "outlook_7d_index": null,
  "outlook_7d_level": "",
  "risk_direction": "",
  "agent_outputs": [],
  "critic_result": {}
}
```

---

# 31. Snapshot 不可覆盖

新扫描：

> **只能新增 Snapshot**

不能修改旧 Snapshot 来让趋势“更好看”。

允许：

- 标记 invalid；
- 增加 correction record；

不允许静默覆盖。

---

# 32. Historical Trend

Historical Trend 使用：

> **最近真实有效 Snapshot**

绘图。

如果只有：

### 1 条
显示：

> “历史数据不足，完成更多扫描后将形成趋势。”

### 2 条
允许显示简单变化。

### 3 条及以上
显示趋势折线图。

不得预填未来数据。

---

# 33. 首次演示的数据问题

项目第一次部署时可能没有足够多真实 Snapshot。

允许在开发 / 测试阶段：

> 手动执行若干次真实历史日期 replay scan

但这些必须明确标记：

```text
BACKFILL
```

并且数据来自相应历史日期的真实历史天气数据。

不得把 Backfill 标记成当日真实在线扫描。

如果 Battle Plan 时间不足：

> v1.0 可以仅从上线后开始积累 Snapshot。

---

# 34. Data Freshness

每个动态数据源必须记录：

- observation time；
- forecast initialization time（如可得）；
- retrieval time。

Weather 数据质量建议：

```text
FRESH
STALE
MISSING
```

具体 freshness 阈值在实现配置中统一定义。

---

# 35. API Cache

为了避免：

- 重复调用；
- 演示连续点击；
- 外部 API 临时限流；

v1.0 应支持短期缓存。

建议：

> 天气原始 API 响应缓存 30 分钟。

用户在 30 分钟内再次扫描：

- 可以复用同一原始天气数据；
- 但必须显示实际 retrieval time；
- 不得伪装成新数据。

具体缓存实现由工程规范决定。

---

# 36. Required Data Failure

如核心天气数据完全不可获得：

Risk Watch 不允许生成新的正式 Current Risk Index。

页面应显示：

> **Scan Incomplete — Required weather data unavailable**

仍可显示：

- Static Baseline；
- 上一次成功 Snapshot；
- 错误信息。

不得让 LLM 猜测天气。

---

# 37. Partial Point Failure

如 Source Zone 获取成功，但 Port Zone 获取失败：

允许：

> `COMPLETED_WITH_LIMITATIONS`

但：

- Evidence Coverage 下降；
- Critic 必须指出；
- 区域聚合只能基于成功点；
- UI 显示缺失点。

如果所有 Monitoring Point 均失败：

> Scan FAILED。

---

# 38. Model Failure

数据采集成功但 DeepSeek 失败时：

- Snapshot 仍保存；
- Deterministic Risk Engine 仍可运行；
- Current Risk Index 可以计算；
- Agent explanation 使用 fallback；
- UI 标记：

> **AI Analysis: Fallback Mode**

不得把 rule fallback 假装成模型结果。

---

# 39. Current Risk 与 Agent 关系

正确顺序：

```text
Data
→ Deterministic Features
→ B / R / F / D / C / O7
→ Professional Agents
→ Risk Synthesizer explains deterministic result
→ Critic reviews
```

或在工程上让专业 Agent 与 deterministic calculation 部分并行。

但原则必须是：

> **LLM 不决定 C 和 O7 的数字。**

---

# 40. Top Risk Drivers

Risk Watch Top Risk Drivers 可以来自两部分：

## Static Drivers

由 Static Baseline 因子贡献排序。

## Dynamic Drivers

由：

- recent precipitation percentile；
- forecast precipitation percentile；

贡献。

Risk Synthesizer 可以用自然语言解释，但排序基础必须可追溯。

---

# 41. What Changed

与上一次 Snapshot 比较至少生成：

- Recent precipitation ↑ / → / ↓
- Forecast precipitation ↑ / → / ↓
- Current Risk Index ↑ / → / ↓
- Optional evidence changes
- Newly missing / newly available data

What Changed 的数值比较由代码产生。

LLM 只负责总结。

---

# 42. Evidence Coverage

建议 Risk Watch 分开显示：

## Required Coverage

例如：

```text
Required: 6 / 6
```

## Optional Coverage

例如：

```text
Optional: 1 / 4
```

不要把二者简单混成一个看起来“很低”的百分比。

Critic 应优先关注：

> Required Coverage 是否完整。

---

# 43. Critic 的 Risk Watch 专项检查

每次 Scan 必须检查：

1. Weather 是否真实获取；
2. 数据时间是否新鲜；
3. Monitoring Point 是否完整；
4. Climatology baseline 是否正确版本；
5. Percentile 是否可复算；
6. Static Baseline 是否来自 region config；
7. Current Risk 是否按公式计算；
8. 7-Day Outlook 是否按公式计算；
9. Optional Evidence 缺失是否被隐藏；
10. Satellite 是否超出 visual observation 边界；
11. LLM 是否输出 Probability；
12. 是否出现“即将发生泥石流”等过度结论。

---

# 44. 对高山区域天气数据的科学限制

Open-Meteo / ECMWF / ERA5-Land 等属于网格化模型或再分析数据。

吉隆区域：

- 地形起伏巨大；
- 局地微气候复杂；
- 源区与口岸高差明显。

因此：

> **模型天气数据不能等同于现场自动站或源区传感器实测。**

系统必须把：

- grid resolution；
- elevation handling；
- lack of local sensor；

作为 Scientific Limitation。

---

# 45. Risk Watch 无法解决的核心缺口

v1.0 最重要的科学限制必须公开：

> **没有源区高频冰川位移、裂缝、微震、冰崩等实时监测数据。**

因此 MountainGuardian v1.0：

可以研判：

- 高基础易灾性；
- 气象压力；
- 风险状态变化；

不能可靠判断：

> “某个高位冰岩体将在未来几小时或几天内发生崩塌。”

这是 Critic 应主动表达的限制。

---

# 46. Scheduler-ready

虽然 v1.0 UI 只提供手动：

> Run Risk Scan

但核心扫描函数不得依赖 Streamlit 用户会话。

应支持类似：

```text
run_risk_scan(region_id)
```

未来可以由：

- Azure scheduler；
- GitHub Action；
- CLI；
- API endpoint；

调用。

v1.0 不需要真正启用后台自动调度。

---

# 47. Future Weekly Watch

未来自动模式建议：

```text
Weekly Trigger
→ Collect
→ Snapshot
→ Detect Material Change
→ If change significant: run AI analysis
→ Else: record No Significant Change
```

这是未来方向，不属于 v1.0 P0。

---

# 48. v1.0 P0 数据源冻结建议

## Required Operational

### Weather / Forecast
**Open-Meteo ECMWF Forecast API**

用途：

- 近期天气；
- 过去 7 天；
- 未来 7 天；
- 温度；
- 降水。

## Required Historical Baseline

### Open-Meteo Historical Weather API / ERA5-Land

用途：

- 1991–2020 climatology；
- 7-Day precipitation percentile baseline。

## Required Static

### Local MountainGuardian Region Baseline

来源：

- 已验证 Case Pack；
- 官方来源；
- `region.json`。

## Optional Satellite

### Copernicus Data Space Ecosystem STAC

collection：

```text
sentinel-2-l2a
```

用途：

- 最新场景发现；
- acquisition date；
- cloud cover；
- optional imagery evidence。

---

# 49. 为什么不把更多数据源列入 P0

v1.0 不把以下列为 Required：

- 实时水位；
- SMAP；
- ENSO；
- 冰川传感器；
- 多卫星融合；
- 雷达降水；
- 商业遥感。

原因：

> **增加一个数据源不仅是增加一个 API，还会增加认证、字段映射、质量控制、异常处理、测试、UI 和科学解释成本。**

这些能力对当前比赛演示的增益不足以抵消实现风险。

---

# 50. v1.0 Risk Watch 验收场景

## Scenario A — Successful Scan

用户点击 Run Risk Scan：

1. Weather Collector 成功；
2. 两个核心监测点有数据；
3. 过去 7 天和未来 7 天降水得到；
4. percentile 计算成功；
5. Snapshot 保存；
6. Current Risk Index 计算；
7. 3 个 Agent 中至少 Glacier / Geology 与 Weather / Hydrology 完成；
8. Remote Sensing 可完成或 SKIP；
9. Synthesizer 完成；
10. Critic 完成；
11. 页面显示 Current Risk / 7-Day Outlook / Historical Trend。

## Scenario B — No New Satellite

- Satellite Discovery 未找到合适影像；
- Remote Sensing = SKIPPED；
- Risk Watch 正常完成；
- UI 明确提示，不视为系统失败。

## Scenario C — Model Failure

- 天气获取成功；
- deterministic result 正常；
- DeepSeek 不可用；
- fallback 生效；
- UI 显示 Fallback Mode；
- Snapshot / Audit 完整。

## Scenario D — Required Weather Failure

- Weather API 不可用；
- 不生成伪造 Current Risk；
- 显示上次成功结果；
- 新 Scan 标记 FAILED / INCOMPLETE。

---

# 51. v1.0 Risk Watch 完成标准

Risk Watch 只有满足以下条件才算实现完成：

1. 有独立 `region.json`；
2. Risk Watch 不读取 Historical Replay post-event 数据；
3. 至少两个 Monitoring Point；
4. Open-Meteo 真实请求成功；
5. 过去 7 天数据可获取；
6. 未来 7 天数据可获取；
7. 1991–2020 climatology 可生成并缓存；
8. recent precipitation percentile 可复算；
9. forecast precipitation percentile 可复算；
10. Static Baseline 可复算；
11. D、C、O7 公式有自动化测试；
12. Risk Level 阈值有自动化测试；
13. 每次扫描生成新 Snapshot；
14. Snapshot 不静默覆盖；
15. Historical Trend 只用真实 Snapshot；
16. Optional Satellite 失败不阻塞；
17. Required Weather 失败时不生成伪造结果；
18. DeepSeek 失败时可 fallback；
19. Critic 能看到 data quality / missing data；
20. Current Risk / 7-Day Outlook 不输出 Probability；
21. 所有关键来源可追溯；
22. Run Risk Scan 可脱离 Streamlit UI 被独立调用。

---

# 52. 当前公开接口验证快照

本设计在 2026-09-30 对拟采用的数据接口进行了实现前核对。

确认：

## Open-Meteo

- ECMWF Forecast API 可按经纬度返回全球天气预报；
- 支持 temperature、precipitation 等变量；
- 支持 `past_days`；
- 历史天气 API 提供 ERA5 / ERA5-Land 等历史再分析数据；
- ERA5-Land 提供约 0.1° 级全球历史数据；
- Open-Meteo Elevation API 使用 Copernicus DEM GLO-90 90m 数据。

## Copernicus Data Space Ecosystem

- 当前 STAC endpoint 为：
  `https://stac.dataspace.copernicus.eu/v1/`
- 支持 `sentinel-2-l2a` collection；
- 支持按时间、空间和 `eo:cloud_cover` 搜索；
- 旧 STAC endpoint 已废弃。

正式开发时仍应再次以当日官方文档和实时 endpoint 为准。

---

# 53. 一句话 Risk Watch 定义

> **MountainGuardian Risk Watch v1.0 是一个面向吉隆口岸高山峡谷区域的按需风险扫描系统：它以稳定的静态易灾背景为基础，获取真实近期与未来天气，用当地历史气候分位数形成可复现的动态气象触发指数，再由专业 AI Agent 对证据进行解释、综合和复核；卫星、水文等数据作为可选增强，不影响核心扫描流程的稳定运行。**
