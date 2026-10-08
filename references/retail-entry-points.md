# 三个日常研究入口

用户只需提出问题；AI准备参数并复用本会话已确认的持仓、窗口与资金用途，不要求用户填JSON。工作台不是前置条件。

## 我的持仓有什么问题

先确认代码或资产编号、市值、币种和日期。仅有截图时注明识别结果，名称歧义先确认。已有来源和历史序列时按[组合诊断](holdings-portfolio.md)分析重叠、行业、相关性与风险；资金用途检查按[investment-intent.md](investment-intent.md)。缺资金安排、阈值或历史资料就列缺口，不默认替用户设限。

交付顺序：已知问题 → 涉及金额与占比 → 依据 → 未穿透或缺资料部分 → 下一步核实。没有发现已提供约束失败，不称组合健康或风险低。

## 这条消息对我的持仓有什么影响

先用[事件规范](event-research.md)取得目录线索，按[原文核验](original-verification.md)阅读适用原文。消息标题、转载和观点不是已核实事实。分别说明事实、收入/现金流/信用/治理影响路径、关联持仓与未知范围。

直接资产编号可关联；有时效依据的直接发行人关系可关联股票、债券与转债。行业、基金底层、控制链需另有资料，不从名称猜测。影响金额、有效条件和状态只从原文或明确声明提取，当前整合入口不自动判定利好利空、因果或价格变化。

## 我之前看好的逻辑，现在还成立吗

已有首次档案时读取[假设复盘](buy-side-thesis.md)，核对新材料、反证条件及证据适用性。没有首次记录时只能重建用户回忆并注明不是事前冻结，不伪造当时依据。复盘分别列支持、反驳、尚未验证及所据材料，保留首次判断。

## 统一报告入口

`python scripts/retail_research.py INPUT.json --out-dir NEW_DIR`

三个入口复用已有计算，输出HTML、Markdown、JSON和输入副本；不自动完成全市场采集，也不提供工作台新页面或后台更新。上游资料需按上述规范取得；报告目录须为新目录。

- `{"entry":"holdings","input":...}`：input为investment_intent.py原始参数，重新执行约束检查，报告前置失败和缺口。完整历史重叠等分析仍走原组合入口，不冒充此处已完成。
- `{"entry":"logic","snapshot":...,"input":...}`：snapshot为首次freeze完整结果，input为review输入；调用已有摘要验证和复盘逻辑，不能只传旧报告文本。
- `{"entry":"news","input":{"asOf":"2026-10-05","currency":"CNY","holdings":[{"assetId":"stock:example","assetClass":"stock","currency":"CNY","marketValue":100}],"event":{"entityId":"stock:example","title":"教学消息","source":"教学来源","publishedAt":"2026-10-01","acquiredAt":"2026-10-02"}}}`：教学参数不代表真实标的。event可附locator、effectiveAt、适用及撤回字段和impactPath；impactPath只是待验证解释。input可附issuerRelations，按已有直接发行人规范验证。

错误处理：主体不明先确认；日期晚于截止日不采用；原文引句未匹配列待核对；混币种先核验换算；缺首次档案不伪造；目录或下载失败保留成功资料与缺口。当前没有跨来源自动事实认证，报告应标明声明、原文定位和未知范围。
