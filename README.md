# MountainGuardian / 山河守望者

**面向高山峡谷灾害场景的多智能体灾害风险情报平台。**
**A multi-agent disaster-risk intelligence platform for high-mountain and deeply incised valley environments.**

**Live Demo / 在线演示:** <https://mountainguardian.cn>

---

## 项目简介

MountainGuardian（山河守望者）是一个研究原型系统，面向高山峡谷灾害场景
（冰岩崩—碎屑流—泥石流灾害链），整合多源科学证据、专业 AI 智能体、确定性风险
计算、证据溯源与评审复核（Critic），为灾害风险研究与态势理解提供可审计的
情报支持。

系统不预测灾害是否发生，也不发布告警：它把"当前区域处于何种风险状态、
依据是什么、缺什么证据"以可复核的方式呈现出来。所有缺失证据均被显式声明，
从不伪造或静默丢弃。

## 核心能力

产品由四个入口组成：

- **总览** — 区域主地图、当前风险状态、智能体协作流、风险趋势与证据/数据覆盖。
- **历史验证** — 对冻结历史案例（2026 年西藏吉隆口岸"8·26"灾害）的灾前分析、
  灾后验证与完整性审计。
- **风险监测** — 基于最新观测与预报执行区域风险扫描，给出当前风险指数与
  未来 7 天风险展望及其驱动因素分解。
- **情报中心** — 智能体工作区、证据中心（溯源与相位标签）、审计与安全控制视图。

## 多智能体架构

冻结的智能体 DAG（非自治递归网络）：

1. **Glacier & Geology Agent（冰川地质智能体）** — 地形、冰冻圈、历史链式灾害、
   下游暴露等静态易灾证据分析。
2. **Weather & Hydrology Agent（气象水文智能体）** — 观测/预报降水窗口、
   气候态百分位等动态触发证据分析。
3. **Remote Sensing Agent（遥感解译智能体）** — 可用影像存在时的卫星证据解译；
   无可用新影像时显式 SKIPPED。
4. **Risk Synthesizer（风险综合智能体）** — 汇聚专业智能体证据与确定性引擎
   输出，生成结构化风险叙述。
5. **Critic（评审智能体）** — 检查科学边界、证据支撑与过度表述风险；
   评审只读，不得改写确定性风险结果。

专业智能体负责采集与分析证据，Synthesizer 负责综合，Critic 负责复核。

## 两种验证路径

- **Historical Replay（历史验证）** — 灾前分析在灾后验证开始之前冻结；
  灾后证据仅用于验证，永不进入灾前分析。
- **Risk Watch（风险监测）** — 实时观测与预报证据输入确定性风险状态引擎，
  输出当前风险指数 C 与 7 天展望指数 O7 及其分解。

## 科学边界

- 风险指数（B/R/F/D/C/O7）是确定性引擎输出的**启发式风险状态指标**，
  **不是灾害发生概率**，也不是官方预警等级。
- MountainGuardian 是**研究原型**，不是官方灾害预警系统；不使用官方预警术语，
  不进行任何形式的告警发布。
- 不可用的证据被**显式声明**（缺失项、回退项、跳过项），从不伪造或静默丢弃。
- Historical Replay 严格分离灾前分析与灾后验证；灾前结果冻结后不可被灾后阶段修改。
- 确定性风险结果**不可被 LLM 智能体改写**：Synthesizer 与 Critic 只能解释与复核，
  评审前后指数保持一致。

## 技术栈

- Python 3.12
- Streamlit（UI 与服务）
- SQLite（持久化快照与证据）
- DeepSeek（`deepseek-flash`，AI 解释层；缺失时显式回退）
- Open-Meteo（观测与预报天气数据）
- Azure App Service on Linux（单实例托管）
- GitHub Actions（CI/CD）

## 快速开始

```bash
git clone <repository-url>
cd MountainGuardian

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

# AI 解释层所需密钥（自行提供，切勿提交真实密钥）
export DEEPSEEK_API_KEY=your_key_here    # Windows: set DEEPSEEK_API_KEY=your_key_here

python -m streamlit run mountainguardian_app.py
```

运行测试：

```bash
python -m pytest
```

未设置 `DEEPSEEK_API_KEY` 时系统仍可运行：确定性风险结果保持有效，
AI 解释层以带标注的回退模式披露运行。

## 配置说明

配置通过环境变量提供：

- `DEEPSEEK_API_KEY` — DeepSeek API 密钥（仅环境变量，调用时读取）。
- `DEEPSEEK_MODEL` — 模型 ID，默认 `deepseek-flash`。
- `MOUNTAINGUARDIAN_DB_PATH` — SQLite 数据库路径（生产为 `/home/data/mountainguardian.db`）。
- `MOUNTAINGUARDIAN_RUNTIME_DIR` — 运行时目录（气候态缓存等）。

示例（仅占位符）：

```
DEEPSEEK_API_KEY=your_key_here
```

仓库中的 `.env.example` 为上游遗留模板，MountainGuardian v1.0 运行时不依赖该文件。

## 安全与可审计性

- **提示词注入防护** — 不可信证据文本与指令通道隔离，注入样本被阻断。
- **证据溯源** — 每条证据携带 Evidence ID、来源、观测时间、相位（灾前/灾后）
  与质量字段；界面仅展示结构化输出与审计字段。
- **输出结构校验** — 模型输出经 schema 校验，失败进入修复或显式回退路径，
  回退从不伪装为模型输出。
- **灾后信息泄漏防护** — Critic 对每次运行执行灾后泄漏检查（POST_EVENT_LEAKAGE）。
- **外部操作已禁用** — 智能体无工具、无外部写入面（设计上禁用）。
- **密钥分离** — 密钥仅存在于环境变量/托管配置中；仓库与界面不包含任何密钥。

## 上游项目 / 致谢

MountainGuardian 起源于开源项目 **RescueMind AI**
（<https://github.com/BALADURGAG24/rescuemind-multi-agent>，MIT License，
Copyright (c) 2026 BALADURGA G）。项目初始提交包含其代码副本（部分文件逐字相同），
v1.0 的产品代码在其后各工程阶段重写与扩展。按 MIT 要求，上游版权与许可声明
保留于 `LICENSE`，详见 `THIRD_PARTY_NOTICES.md`。

## 许可证

MIT License — 见 [LICENSE](LICENSE)。
Copyright (c) 2026 BALADURGA G（上游 RescueMind AI）；
Copyright (c) 2026 MountainGuardian contributors。

---

## Overview

MountainGuardian (山河守望者) is a research prototype for high-mountain,
deeply incised valley hazard settings (ice-rock avalanche – debris flow –
mudflow chains). It integrates multi-source scientific evidence, professional
AI agents, a deterministic risk-state engine, evidence provenance and Critic
review to support disaster-risk research and situational understanding.

The system does not predict whether a disaster will occur and issues no
alerts: it presents, in an auditable way, which risk state a region currently
occupies, on which evidence, and which evidence is missing. Missing evidence
is always disclosed, never fabricated or silently dropped.

## Key Capabilities

- **Overview** — regional base map, current risk state, agent collaboration
  flow, risk trend and evidence/data coverage.
- **Historical Replay** — pre-event analysis, post-event validation and
  integrity audit over a frozen historical case (Gyirong port, Tibet,
  2026-08-26 event).
- **Risk Watch** — on-demand regional risk scans over the latest observations
  and forecasts, with current risk index, 7-day outlook and driver
  decomposition.
- **Intelligence Center** — agent workspace, evidence center (provenance and
  phase tags), audit & safety-control views.

## Multi-Agent Architecture

A frozen agent DAG (not an autonomous recursive network):

1. **Glacier & Geology Agent** — static susceptibility evidence (terrain,
   cryosphere, historical chain events, downstream exposure).
2. **Weather & Hydrology Agent** — dynamic trigger evidence (observed and
   forecast precipitation windows, climatological percentiles).
3. **Remote Sensing Agent** — satellite evidence interpretation when usable
   imagery exists; explicitly SKIPPED otherwise.
4. **Risk Synthesizer** — integrates professional-agent evidence and
   deterministic engine output into structured risk narratives.
5. **Critic** — reviews scientific boundaries, evidence support and
   overclaim risk; review-only, never rewrites deterministic results.

Specialist agents gather and analyze evidence, the Synthesizer integrates,
and the Critic checks.

## Historical Replay & Risk Watch

- **Historical Replay** — pre-event analysis is frozen before post-event
  validation begins; post-event evidence is validation-only and never enters
  the pre-event analysis.
- **Risk Watch** — live observation and forecast evidence feeds the
  deterministic risk-state engine, producing the current risk index C and the
  7-day outlook index O7 with their decompositions.

## Scientific Boundaries

- The risk indices (B/R/F/D/C/O7) are deterministic, heuristic **risk-state
  indicators** — **not event probabilities** and not official warning levels.
- MountainGuardian is a **research prototype**, not an official
  disaster-warning system; it uses no official alert terminology and performs
  no warning dispatch of any kind.
- Unavailable evidence is **explicitly disclosed** (missing, fallback,
  skipped) — never fabricated or silently dropped.
- Historical Replay strictly separates pre-event analysis from post-event
  validation; frozen pre-event results cannot be modified afterwards.
- Deterministic risk results **cannot be rewritten by LLM agents**: the
  Synthesizer and Critic may only explain and review; indices are identical
  before and after review.

## Technology Stack

- Python 3.12
- Streamlit (UI and serving)
- SQLite (persisted snapshots and evidence)
- DeepSeek (`deepseek-flash`) for the AI explanation layer, with disclosed
  fallback when unavailable
- Open-Meteo (observed and forecast weather)
- Azure App Service on Linux (single instance)
- GitHub Actions (CI/CD)

## Quick Start

```bash
git clone <repository-url>
cd MountainGuardian

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Provide your own key for the AI explanation layer (never commit real keys)
export DEEPSEEK_API_KEY=your_key_here    # Windows: set DEEPSEEK_API_KEY=your_key_here

python -m streamlit run mountainguardian_app.py
```

Run the test suite:

```bash
python -m pytest
```

Without `DEEPSEEK_API_KEY` the system still runs: deterministic risk results
remain valid and the AI explanation layer operates in a disclosed, labelled
fallback mode.

## Configuration

Configuration is provided via environment variables:

- `DEEPSEEK_API_KEY` — DeepSeek API key (environment only, read at call time).
- `DEEPSEEK_MODEL` — model id, default `deepseek-flash`.
- `MOUNTAINGUARDIAN_DB_PATH` — SQLite database path
  (`/home/data/mountainguardian.db` in production).
- `MOUNTAINGUARDIAN_RUNTIME_DIR` — runtime directory (climatology caches etc.).

Placeholder example only:

```
DEEPSEEK_API_KEY=your_key_here
```

The `.env.example` file in the repository is a legacy upstream template; the
MountainGuardian v1.0 runtime does not depend on it.

## Safety & Auditability

- **Prompt-injection safeguards** — untrusted evidence text is isolated from
  instruction channels; injection samples are blocked.
- **Evidence provenance** — every evidence item carries an Evidence ID,
  source, observation time, phase (pre-event/post-event) and quality fields;
  the UI shows structured outputs and audit fields only.
- **Output schema validation** — model output is schema-validated; failures
  enter repair or explicit fallback paths, and fallbacks never masquerade as
  model output.
- **Post-event leakage protection** — the Critic runs a post-event leakage
  check (POST_EVENT_LEAKAGE) on every run.
- **External actions disabled** — agents have no tools and no external write
  surface (disabled by design).
- **Secret separation** — keys live only in environment variables / hosting
  configuration; the repository and the UI contain no secrets.

## Upstream / Acknowledgements

MountainGuardian originates from the open-source project **RescueMind AI**
(<https://github.com/BALADURGAG24/rescuemind-multi-agent>, MIT License,
Copyright (c) 2026 BALADURGA G). The project's first commit contained copies
of its code (several files byte-identical); the v1.0 product code was
rewritten and extended during subsequent engineering stages. Per the MIT
License, the upstream copyright and permission notices are retained in
`LICENSE`; see `THIRD_PARTY_NOTICES.md`.

## License

MIT License — see [LICENSE](LICENSE).
Copyright (c) 2026 BALADURGA G (upstream RescueMind AI);
Copyright (c) 2026 MountainGuardian contributors.
