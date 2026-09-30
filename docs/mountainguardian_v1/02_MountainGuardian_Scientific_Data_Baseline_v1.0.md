# MountainGuardian Scientific & Data Baseline v1.0
## 山河守望者 v1.0 科学与数据基线（冻结版）

**文档状态：** FROZEN / 已冻结  
**上位依据：**
- `00_MountainGuardian_Project_Foundation_v1.0.md`
- `01_MountainGuardian_Product_Requirements_v1.0.md`

**核心案例数据依据：**
- `data/cases/jilong_20260826/case.json`
- `data/cases/jilong_20260826/sources.md`
- `data/cases/jilong_20260826/README_for_Claude_Code.md`

**目标产品版本：** MountainGuardian v1.0  
**文档目的：** 冻结项目的科学问题、历史案例事实边界、数据分类与来源规则、风险指标含义、Historical Replay 数据隔离原则、Risk Watch 数据最低要求、遥感使用边界、验证方法与不确定性表达。  

---

# 1. 科学问题定义

MountainGuardian v1.0 不以“精准预测某一次灾害发生的确切时间和概率”为科学目标。

项目真正研究的问题是：

> **能否通过多源环境数据与多智能体 AI 协同，对高山峡谷地区的灾害基础易发性、当前风险状态及短期风险趋势进行结构化识别、解释和复核？**

具体包括三层问题：

## 1.1 基础易发性

某个区域是否长期具有较高灾害易发条件，例如：

- 高海拔冰冻圈环境；
- 巨大高差；
- 狭窄沟谷；
- 松散物源；
- 历史链式灾害复发性；
- 下游设施暴露。

## 1.2 当前风险状态

在既有易灾背景上，近期环境条件是否正在增加风险，例如：

- 连续降水；
- 极端天气；
- 气温异常；
- 积雪 / 融水变化；
- 土壤或地表湿度变化；
- 水文变化；
- 新遥感异常。

## 1.3 短期风险展望

基于未来 7 天天气与当前环境状态，对风险方向进行判断：

- 上升；
- 稳定；
- 下降。

v1.0 不输出未经统计校准的“未来 7 天灾害发生概率”。

---

# 2. 吉隆历史案例科学基线

MountainGuardian 当前核心历史验证案例为：

> **2026 年西藏吉隆口岸“8·26”冰岩崩—碎屑流—泥石流灾害。**

## 2.1 当前数据包支持的官方灾害链

Jilong Case Pack 当前采用的灾害机理表述为：

> **高位冰岩 / 冰川崩塌 → 高速碎屑流沿陡峭沟道下泄 → 裹挟冰碛物与松散岩土体 → 汇入东林藏布 → 演变为泥石流 → 冲击吉隆口岸及下游设施。**

该案例不应被简化表述为：

> “强降雨直接导致泥石流。”

降雨、季风和气候背景可以作为环境背景因素，但当前 Case Pack 的核心灾害链强调：

- 高位冰冻圈源区；
- 高差和沟谷；
- 松散物源；
- 链式放大过程。

## 2.2 当前 Case Pack 中的重要事实基线

以下内容可作为项目事实底座：

- 案例地点：西藏日喀则市吉隆县吉隆口岸及相关上游区域；
- 事件日期：2026-08-26；
- 源区为高海拔冰冻圈 / 高位冰岩环境；
- 源区海拔约 5200 米量级；
- 吉隆口岸海拔约 1800 米量级；
- 区域属于极高山—深切峡谷环境；
- 上游存在冰碛物及松散物源；
- 下游存在口岸、道路及基础设施暴露；
- 2025 年同一区域曾发生链式山洪泥石流相关灾害；
- 官方灾后调查与遥感资料确认了源区—沟道—下游口岸的链式灾害路径。

任何超出 Case Pack 当前字段与来源支持的细节，不得直接写入产品事实层。

---

# 3. Historical Replay 的科学目标

Historical Replay 不承担“证明 AI 能提前预测灾害”的任务。

其科学目标是：

> **验证在严格排除灾后信息的情况下，系统能否利用灾前可获得的信息识别出该区域已经存在的高基础风险条件。**

Historical Replay 的正确问题是：

> “灾害发生前，这个区域是否已经存在足够多的高风险证据？”

而不是：

> “系统是否知道 8 月 26 日一定会发生灾害？”

---

# 4. 数据阶段分类

Historical Replay 的所有数据必须按 `phase` 分类。

当前冻结的主要类别如下。

## 4.1 `pre_event_static`

灾害发生前长期已经存在的静态环境信息。

例如：

- 高程；
- 地形；
- 坡度；
- 沟谷；
- 冰川 / 冰冻圈背景；
- 松散物源；
- 下游设施暴露。

允许提供给：

- Glacier / Geology Agent；
- Weather / Hydrology Agent（如相关）；
- Remote Sensing Agent；
- Risk Synthesizer。

---

## 4.2 `derived_pre_event_static`

由灾前静态数据推导出的确定性特征。

例如：

- 高差；
- 地形组合特征；
- 易灾背景指数。

必须能够说明推导方法。

允许进入风险分析。

---

## 4.3 `pre_event_context`

灾前已经存在、但主要作为环境背景的信息。

例如：

- 季节；
- 雨季背景；
- 区域气候环境。

可以用于解释风险，但不能自动被包装为直接触发因素。

---

## 4.4 `pre_event_evidence`

灾害发生前已经获取到的证据。

例如：

- 灾前卫星影像；
- 灾前公开监测资料；
- 灾前历史事件记录。

允许提供给专业 Agent。

---

## 4.5 `post_event_validation`

灾害发生后才确认的信息。

例如：

- 实际灾害路径；
- 实际运动距离；
- 实际传播时间；
- 灾后卫星变化；
- 灾后调查确认的源区；
- 实际灾害规模。

**绝对禁止进入灾前风险分析。**

只能供：

- Critic / Reviewer；
- Historical Replay 结果验证；
- Evidence Center 的 Post-event 部分。

---

## 4.6 `context_only`

只允许作为背景展示，不进入风险评分。

例如：

- ENSO / 厄尔尼诺背景；
- 宏观气候讨论；
- 与具体事件因果关系未确认的信息。

---

## 4.7 `missing_input`

公开资料中未获得、但科学上重要的数据。

例如：

- 灾前实时源区位移；
- 微震；
- 实时冰裂活动；
- 高频源区监测数据。

这些缺失不能被 AI 自行补全。

系统必须明确显示：

> **Data unavailable / 未获得公开灾前动态监测数据。**

---

# 5. Data Leakage 红线

Historical Replay 的首要科学完整性原则是：

> **任何灾后才知道的信息，不得进入灾前分析过程。**

## 5.1 Risk Agent 禁止读取

Risk / Intelligence 类 Agent 禁止读取：

- `post_event_validation`
- 灾后事件结果
- 实际灾害发生时间
- 实际运动路径
- 实际灾害规模
- 灾后影像观察结果

## 5.2 Critic / Reviewer 可以读取

Critic / Reviewer 可以在风险结果已经生成之后读取：

- post-event evidence；
- 官方调查结果；
- 灾后影像；

用于判断：

> “系统在不知道结果时识别出的风险条件，与实际灾害调查结果是否具有对应关系？”

## 5.3 技术实现优先级

数据隔离必须由代码实现，不依赖 Prompt 自觉。

优先规则：

1. loader 按 `phase` 分区；
2. Coordinator 按 Agent 类型裁剪 context；
3. Risk Agent 输入 schema 不包含 post-event；
4. 自动化测试验证无泄漏；
5. Critic 最后检查。

---

# 6. 风险指标体系

MountainGuardian 必须严格区分四类概念。

## 6.1 Risk Index

Risk Index 是基于确定性规则或模型计算得到的指数。

例如：

> 91 / 100

含义：

> **基础易灾风险指数较高。**

它不是：

> “91% 的灾害发生概率”。

## 6.2 Risk Level

风险等级用于方便解释 Risk Index。

v1.0 建议统一：

- LOW
- MODERATE
- ELEVATED
- HIGH

具体阈值在 AI Agent Architecture / Risk Watch Design 中冻结。

## 6.3 Risk Trend

Risk Trend 表示：

> 当前 Risk Index 与历史快照相比的方向变化。

例如：

- ↑ Rising
- → Stable
- ↓ Falling

它不是长期气候预测。

## 6.4 Probability

只有在满足以下条件时才能使用“发生概率”：

- 存在足够历史样本；
- 有明确统计模型；
- 有训练 / 验证集；
- 有概率校准；
- 能说明误差和置信区间。

MountainGuardian v1.0 不满足这些条件，因此：

> **v1.0 禁止输出灾害发生概率。**

---

# 7. 吉隆 Demo 基础风险模型

当前 Jilong Case Pack 冻结的 Demo Risk Model 包含 6 个因子：

1. 高海拔冰冻圈源区；
2. 巨大高差与狭窄沟谷；
3. 沟道松散物源；
4. 历史链式灾害复发性；
5. 季风与高降水背景；
6. 下游暴露与口岸设施。

权重合计：

> **100%**

当前 Case Pack 复算结果：

> **Baseline Risk Index = 91 / 100**

该指数用于 Historical Replay。

必须显示：

> **Baseline Susceptibility / 基础易灾风险指数**

不能显示为：

> “预测准确率”
> “发生概率”
> “AI 预测 91%”

---

# 8. 风险模型与 LLM 的职责边界

## 8.1 Deterministic Engine

负责：

- Risk Index；
- 权重；
- 因子贡献；
- 阈值；
- Trend 数值计算。

必须：

- 可复现；
- 可测试；
- 相同输入得到相同结果。

## 8.2 LLM / Agent

负责：

- 理解证据；
- 比较不同数据；
- 解释风险因素；
- 总结变化；
- 识别冲突；
- 表达不确定性；
- 生成结构化说明。

LLM 不负责：

- 随意生成 Risk Index；
- 自创概率；
- 修改原始数据；
- 覆盖确定性计算结果。

---

# 9. Risk Watch 数据基线

Risk Watch 的目标不是一次性接入所有可能的数据，而是建立一个：

> **少量稳定核心数据 + 可选增强证据**

的结构。

---

# 10. Risk Watch Required Data

v1.0 优先保证以下数据能够稳定取得。

## 10.1 Weather

至少包括：

- 当前温度；
- 最近温度变化；
- 过去 7 天累计降水；
- 过去 7 天最大日降水；
- 未来 7 天天气预报；
- 未来 7 天累计预计降水；
- 极端天气提示（如可得）。

## 10.2 Static Terrain

静态基线：

- 海拔；
- 高差；
- 坡度；
- 沟谷 / 河谷特征。

不需要每次扫描重新下载。

## 10.3 Glacier / Cryosphere Baseline

静态 / 低频更新：

- 冰川 / 冰冻圈存在情况；
- 源区海拔；
- 高位冰岩环境；
- 已知冰湖或冰川地貌信息。

## 10.4 Historical Baseline

包括：

- 历史灾害；
- 已知链式灾害；
- Historical Replay 基础风险因子。

---

# 11. Optional Evidence

以下数据属于增强项。

## 11.1 Soil / Surface Moisture

有可靠公开数据则加入。

没有则：

> Missing / Not available

不能用模型猜测。

## 11.2 Hydrology

包括：

- 河流水位；
- 流量；
- 水位变化。

只有稳定数据源存在时启用。

v1.0 不应因水文数据不可获得而阻塞 Risk Watch。

## 11.3 Satellite

如果存在新的、质量可接受的遥感影像：

- 下载；
- 保存 metadata；
- 交 Remote Sensing Agent。

若：

- 没有新过境；
- 云量太大；
- 图像不可访问；

则：

> Remote sensing evidence unavailable for this scan.

Risk Watch 仍继续。

## 11.4 ENSO

可以作为：

- 气候背景；
- 季节环境变量。

不能作为：

> “本周泥石流风险上升的直接证据”

除非存在针对该区域的明确科学依据。

## 11.5 Glacier Dynamic Monitoring

如未来能够获得：

- 位移；
- 裂缝变化；
- 微震；
- 冰崩异常；
- 冰湖面积变化；

可升级为高价值动态输入。

v1.0 不将其作为必需数据。

---

# 12. Risk Watch Snapshot

每次 Run Risk Scan 必须产生一个结构化 Snapshot。

至少记录：

- scan_id
- region_id
- timestamp
- weather_observations
- weather_forecast
- static_baseline_version
- optional_evidence
- missing_sources
- data_quality
- agent_outputs
- risk_index
- risk_level
- critic_result

Snapshot 必须可追溯。

---

# 13. Historical Trend

Historical Trend 只基于已经真实执行过的 Snapshot。

例如：

| Date | Risk Index | Risk Level |
|---|---:|---|
| 2026-10-01 | 48 | MODERATE |
| 2026-10-08 | 53 | MODERATE |
| 2026-10-15 | 61 | ELEVATED |

不得为了让图表好看而预先编造未来扫描记录。

如当前只有一个 Snapshot：

> 页面应明确显示“历史数据不足，趋势将在后续扫描后形成”。

---

# 14. 7-Day Outlook

7-Day Outlook 主要依据：

- 当前风险基线；
- 未来 7 天天气预报；
- 当前环境状态；
- 专业 Agent 解释。

输出必须使用：

- risk direction；
- risk band；
- major drivers；
- confidence；
- missing evidence。

推荐：

> “未来 7 天风险展望：ELEVATED，主要受未来连续降水影响。”

不推荐：

> “未来 7 天泥石流概率 72%。”

---

# 15. 遥感数据原则

## 15.1 Historical Replay

可以使用：

- 灾前 Sentinel-2；
- 灾后 Sentinel-2；
- 官方灾害路径图；
- 官方冰川分布图；
- 现场灾前 / 灾后图。

必须标记：

- Pre-event
- Post-event
- Official reference

## 15.2 Risk Watch

Satellite 是 Optional Evidence。

只有在本次扫描存在：

- 新影像；
- 有效日期；
- 可接受质量；

时进入 Remote Sensing Agent。

## 15.3 Vision LLM

v1.0 可以让 Vision LLM 辅助观察：

- 河谷 / 冰雪覆盖变化；
- 可见地表变化；
- 图像明显异常。

但必须标记：

> **AI visual observation / AI 视觉观察**

不能直接升级为：

> “遥感科学判定”

除非有确定算法或官方证据支持。

---

# 16. 数据来源等级

Evidence 建议按来源可信度分层。

## Tier A — 官方 / 一手权威

例如：

- 中国地质调查局；
- 中国地质科学院；
- 国家航天 / 遥感官方机构；
- 官方气象机构；
- Copernicus / Sentinel 官方数据平台。

优先作为事实依据。

## Tier B — 权威科研 / 数据平台

例如：

- ERA5；
- 国际科学数据平台；
- 学术论文；
- 可信研究机构。

可用于分析。

## Tier C — 新闻 / 二次报道

用于：

- 背景；
- 事件叙事补充。

关键科学结论不能只依赖 Tier C。

## Tier D — AI / 自动推断

属于：

- Derived insight
- AI observation
- Model interpretation

必须与原始数据分开显示。

---

# 17. Evidence Provenance

每一个进入 Agent 推理的重要 Evidence Item 至少应包含：

- evidence_id；
- evidence_type；
- source_name；
- source_url / source_reference；
- observation_time；
- acquisition_time；
- phase；
- confidence / quality；
- raw_value / observation；
- derived_or_raw；
- used_by_agents。

任何无法追溯来源的重要数字不进入正式风险分析。

---

# 18. 数据质量

每个数据源应尽可能有质量标记。

例如：

- GOOD
- LIMITED
- STALE
- MISSING

常见限制：

- Satellite cloud cover；
- API unavailable；
- Temporal resolution too low；
- Geographic resolution too coarse；
- Historical only；
- No real-time sensor.

模型必须能看到这些限制。

---

# 19. Missing Data 原则

缺失不是错误，也不能隐藏。

系统必须允许：

> “数据不足”

成为正式输出。

例如：

> “本次扫描没有可用的新卫星影像，因此 Remote Sensing Agent 未提供动态遥感证据。”

比让 Agent 猜一个结论更正确。

Optional Evidence 缺失不得导致整次扫描失败。

Required Data 缺失时：

- 降级；
- 明确提示；
- 必要时不给出完整 Current Risk。

---

# 20. 不确定性表达

所有 AI 风险输出必须允许表达：

- Evidence Coverage；
- Agent Confidence；
- Data Quality；
- Missing Evidence；
- Agent Disagreement。

Confidence 不等于：

> “灾害发生概率”。

Confidence 表示：

> 当前结论在给定数据与分析条件下的模型 / 系统信心程度。

---

# 21. Agent Disagreement

如果三个专业 Agent 给出明显不同结论：

系统不能简单平均后隐藏冲突。

应向 Risk Synthesizer 和 Critic 暴露：

- 谁认为风险高；
- 谁认为风险低；
- 各自依据；
- 数据质量；
- 冲突原因。

Critic 负责输出：

> Agreement / Partial Agreement / Significant Disagreement

---

# 22. Historical Replay 验证指标

v1.0 不要求计算传统机器学习意义上的准确率。

可以验证：

## 22.1 Risk Factor Recall

实际灾后调查确认的关键风险因素中，有多少已经被灾前分析识别。

## 22.2 Evidence Alignment

AI 灾前分析所引用证据，与官方灾后调查之间是否存在对应。

## 22.3 Scientific Restraint

系统是否：

- 没有使用灾后数据；
- 没有声称知道具体发生时间；
- 没有把 Risk Index 写成 Probability；
- 正确表达缺失数据。

## 22.4 Explainability

最终风险结论是否能够追溯到：

> Source → Evidence → Agent → Risk Driver → Conclusion

---

# 23. Risk Watch 验证指标

Risk Watch v1.0 重点验证：

1. 数据采集是否成功；
2. Snapshot 是否保存；
3. Required Data 是否完整；
4. Optional Evidence 缺失是否可降级；
5. Agent 是否使用正确数据；
6. Risk Index 是否确定性可复现；
7. 7-Day Outlook 是否基于真实天气预报；
8. Historical Trend 是否只使用真实历史 Snapshot；
9. Critic 是否能指出数据限制；
10. 整个分析是否可追溯。

---

# 24. ENSO 科学边界

MountainGuardian 最初研究动机包含对厄尔尼诺与极端灾害的关注。

但 v1.0 必须保持以下边界：

> **ENSO 是大尺度气候背景，不等同于某次具体泥石流灾害的直接原因。**

在吉隆 Historical Replay 中：

- ENSO 不进入 91/100 风险指数；
- 不作为 8·26 具体事件直接因果证据。

在 Risk Watch 中：

- 可作为环境背景；
- 可辅助解释季节气候条件；
- 不自动提高短期 Risk Index。

---

# 25. Case Pack 版本治理

吉隆案例运行时 Single Source of Truth：

`data/cases/jilong_20260826/case.json`

原则：

- JSON 为程序主输入；
- CSV / XLSX 用于人工核对；
- DOCX 用于研究材料；
- sources.md 用于来源追溯；
- satellite/ 用于证据展示。

Case Pack 更新必须：

1. 更新 `pack_version`；
2. 保留 source_id；
3. 说明新增 / 删除字段；
4. 重新运行 leakage test；
5. 重新验证 Risk Index；
6. Git commit 留痕。

---

# 26. Risk Watch 数据版本治理

每次扫描不可覆盖上一轮数据。

应保存：

> Snapshot history

同一个数据源发生更新时，应至少记录：

- source；
- observation time；
- retrieval time；
- value；
- version / request metadata。

---

# 27. 禁止事项

Scientific / Data 层明确禁止：

- 灾后数据泄漏；
- AI 猜测缺失传感器数据；
- 把 Risk Index 叫 Probability；
- 为趋势图伪造历史 Snapshot；
- 为演示伪造未来天气；
- 用 AI 图像冒充卫星图；
- 用非吉隆区域数据冒充吉隆；
- 把新闻二次报道当唯一科学事实；
- 把 ENSO 直接写成具体灾害原因；
- 把 LLM 生成数字覆盖 Deterministic Engine；
- 隐藏关键数据缺失。

---

# 28. v1.0 数据最小可行集

为控制开发复杂度，Risk Watch v1.0 最低只要求：

### Static
- location
- terrain
- elevation / relief
- glacier / cryosphere baseline
- historical hazard baseline

### Dynamic Required
- recent temperature
- past 7-day precipitation
- next 7-day weather / precipitation forecast

### Optional
- soil moisture
- hydrology
- satellite
- ENSO
- glacier dynamic monitoring

即使 Optional 全部缺失，只要 Required 数据满足最低质量要求，系统仍可完成一个“有限证据条件下”的扫描，并由 Critic 明确指出限制。

---

# 29. 科学层 v1.0 验收标准

本文件对应的科学与数据能力只有在以下条件全部满足时才算完成：

1. Jilong Historical Replay 严格无 post-event leakage；
2. 91/100 基础易灾风险指数可确定性复算；
3. Risk Index 与 Probability 在所有页面中严格区分；
4. ENSO 不被错误写成吉隆事件直接原因；
5. Risk Watch 至少使用真实近期天气数据；
6. 7-Day Outlook 来自真实未来天气数据；
7. Historical Trend 只使用真实 Snapshot；
8. Optional Evidence 缺失可降级；
9. Satellite 的 pre/post/current 标签明确；
10. AI 视觉观察与科学事实区分；
11. 所有关键 Evidence 可追溯；
12. Critic 能看到 Data Quality 和 Missing Data；
13. 不确定性被展示；
14. 不伪造数据；
15. 数据更新有版本与 Git 记录。

---

# 30. 与后续文档关系

本文件冻结科学与数据边界。

后续：

- `03_MountainGuardian_AI_Agent_Architecture_v1.0.md`  
  必须按照本文的数据权限、Risk Index 与 LLM 边界设计 Agent。

- `04_MountainGuardian_Risk_Watch_Design_v1.0.md`  
  必须按照本文 Required / Optional 数据体系设计采集和 Snapshot。

- `05_MountainGuardian_UI_UX_Design_Spec_v1.0.md`  
  必须正确展示 Risk / Probability / Confidence / Missing Data。

- `06_MountainGuardian_Engineering_Deployment_Spec_v1.0.md`  
  必须实现 provenance、snapshot、日志与数据隔离。

---

# 31. 一句话科学基线

> **MountainGuardian v1.0 不是一个声称能够精准预测泥石流发生时间和概率的系统，而是一套通过真实多源数据、确定性风险计算与多智能体 AI 协同，对高山峡谷地区的基础易灾性、当前风险状态和 7 天风险趋势进行可解释、可追溯研判的研究型智能系统。**
