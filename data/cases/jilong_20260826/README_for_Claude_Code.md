# README for Claude Code — Jilong Case Pack v0.1

## 目标
把本数据包作为 MountainGuardian 的唯一案例事实底座。不要再使用原 RescueMind 的印度 Demo 数据作为比赛主流程。

## 建议读取顺序
1. `Jilong_Case_Data_v0.1.json`：程序主输入。
2. `Jilong_Case_Data_v0.1.xlsx`：人工核对与来源追踪。
3. `Jilong_Case_Sources_v0.1.md`：来源链接。
4. `satellite_images/`：若为空，运行 `download_satellite_images.py` 获取公开/官方参考图。

## 最重要的工程规则
- `phase=pre_event_static / pre_event_context / pre_event_evidence` 才可以进入“历史回放的灾前分析”。
- `phase=post_event_validation` 只能用于结果验证，绝不能喂给风险Agent后再声称“预测”。
- `context_only`（特别是ENSO）只用于页面背景说明，不进入风险评分。
- `missing_input` 必须由 Checker Agent 明确显示缺失，不允许编造。
- 风险输出统一称 `risk_index` 或“风险指数”，不要称“发生概率”。
- 当前演示参考指数约为 **91/100**，它是规则化演示分，不是经过统计验证的科学概率。
- 页面必须显示：`历史案例回放 / 科普实验用途，不用于真实灾害预警决策`。

## 5个Agent的数据职责

### 1. 情报员 Agent
读取灾前静态/背景/遥感元数据，整理风险因素和缺失项。

### 2. 风险分析员 Agent
使用 JSON 的 `demo_risk_model.factors` 计算基础易灾风险指数。第一版不要训练模型，不要加入灾后字段。

### 3. 检查员 Agent
至少执行：
- 灾前/灾后字段隔离；
- 来源ID存在性检查；
- 风险分数0-100检查；
- ENSO因果禁写检查；
- 缺少源区实时传感数据提示。

### 4. 预警员 Agent
只生成“风险提示/建议”，不要生成政府正式预警。说明主要风险因素和数据不足。

### 5. 安全员 Agent
不允许真实外发邮件/短信；不允许把模拟传感器信号写成真实历史观测；保留审计日志。

## 卫星图像
程序本地如没有图像文件，可以运行：

```bash
python download_satellite_images.py
```

网络下载失败时，Demo可以只展示图像URL、获取时间、分辨率和判读说明，不应伪造本地图像。

## 一个推荐的演示结论
“吉隆口岸具有高海拔冰冻圈、巨大高差、狭窄沟谷、丰富松散物源和历史链式灾害等多重高风险条件。历史数据可以帮助AI识别该区域为高基础易灾区；但公开资料中缺少灾前源区实时位移、微震等动态前兆，因此本Demo不能声称提前准确预测了8·26灾害的具体发生时刻。”
