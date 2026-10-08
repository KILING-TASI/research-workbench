# 公司经营、相对估值与DCF情景

只有用户提供或同意情景假设时计算。公开历史事实与未来假设分开；不从历史增长率自动生成未来预测。公司财务事实可来自[公司财报流程](company-report-workflow.md)，本入口不替代原文核验。

## 输入和调用

所有数值用 `{ "value":0.1,"basis":"assumption","note":"折现率10%情景假设" }` 表达。basis可为source-statement、calculation、assumption；前两类另需sourceUrl、locator、publishedAt，发布日期不能晚于asOf。计算值的定位要写明原始字段和公式。来源等级不会因为进入模型而升级。

各模式共同输入：identity（至少name，可附market/code）、asOf、currency、unit。金额统一单位；例如使用亿元时，所有收入、债务、现金必须是亿元。可附sourceFiles列表，每项path与sha256，运行时核对来源文件未变化。AI准备结构化输入，不让用户填写技术表单。

来源陈述可增加numericBinding：`{"path":"已登记JSON路径","pointer":"/tables/balance/rows/0/raw/ACCOUNTS_RECE","scale":0.00000001}`。pointer遵循JSON Pointer路径（斜杠用~1、波浪号用~0）；scale为正数，明确原始金额转为模型金额的缩放。逐字段核对不一致或字段缺失时停止，不能静默换字段。该功能仅核对JSON底稿数值，不能证明期间、币种、合并范围或公告原文正确；这些仍需财报原文核验。假设不能绑定成历史事实。

```text
python scripts/company_scenarios.py dcf dcf-input.json --out-dir new-dcf
python scripts/company_scenarios.py relative peers-input.json --out-dir new-peers
python scripts/company_scenarios.py forecast forecast-input.json --out-dir new-forecast
```

每次输出新目录内的result.json、自然语言Markdown和HTML，保留完整输入及代码哈希，不覆盖旧结果。

## DCF

需要连续第1至N年的cashFlows（每项year及上述数值结构，1至30年），终值参数terminalGrowth，桥接项netDebt。FCFF与WACC匹配；输入股权现金流时不能套用本模式。

建议明确声明cashFlowType为FCFF（年度条目也可声明）；声明FCFE或其他类型时拒绝计算。旧输入未声明时沿用FCFF模型约定，并在报告中提示尚需确认编制口径，不把默认约定解释成已经核验。

折现参数二选一：discountRate；或wacc的equityCost、debtCost、taxRate、equityWeight。权重是声明的市场价值权重，不自动以账面权益替代。WACC=权益权重×权益成本+债务权重×债务成本×(1-税率)。所有率使用小数，9%填0.09。

年末折现、恒定资本成本。最后一年FCFF必须为正，永续增长率低于折现率；不成立时拒绝终值计算。输出企业折现值、股权桥接值、终值占比和折现率±1百分点/增长率±0.5百分点敏感性。无效敏感性组合单独标记。

可选shares为数值条目，且unitScale必须与金额单位一致：亿元对应亿股，百万元对应百万股。每股情景值不是目标价。netDebt须由研究者明确桥接口径；少数股权、非经营资产、受限现金、期权和稀释未提供时不会自动补齐。

## 相对估值

companies为2至50家公司。每项code、name、valuationDate、financialPeriod、definition（如FY2025合并口径），marketCap、netProfit、equity、revenue；可选netDebt与EBITDA。全部币种/单位一致，日期/期间/口径一致才计算。指定公司的currency/unit如与全局不同会拒绝。

输出PE/PB/PS/EV-EBITDA和有效样本中位数。缺失字段可填null；对应倍数留空，特别是未取得市值时不推算市值。负利润、负净资产或非正EBITDA使相应倍数留空。模型不证明输入池可比，不把低倍数解释成低估，未取到市值不能用估计值冒充实时估值。

## 三表联动经营情景

普通非金融公司简化模型；不是完整会计科目预测，也不自动产生盈利一致预期。

opening必须提供revenue、cash、receivables、inventory、fixedAssets、otherAssets、payables、debt、otherLiabilities、equity。期初资产负债关系必须平衡；其他科目需要明确分类，不自动填数。

years为连续1至5年（year=1开始），每年给出revenueGrowth、grossMargin、opexRate、taxRate、depreciationRate、capexRate、DSO、DIO、DPO、interestRate、netBorrowing、payoutRate数值条目。

毛利及费用率不含折旧；折旧按期初固定资产，资本开支按收入，新增资产当年折旧未计。应收按收入、存货及应付按不含折旧成本，以365日换算。其他资产负债保持固定，利息按年均债务，税前亏损不计所得税，不自动模拟亏损抵扣。

每年联动利润表、现金流、资产负债表和FCFF，保留三表差额。期末模型现金为负时显示融资缺口，停止后续年，不自动补借款。受限资金、少数股权、并购、减值、递延税和现金利息需扩展模型另算；账面货币资金不能直接认定可用现金。

## 最小可运行DCF示例

```json
{"identity":{"name":"恒定现金流验收示例"},"asOf":"2026-10-05","currency":"CNY","unit":"元","discountRate":{"value":0.1,"basis":"assumption","note":"折现率10%"},"terminalGrowth":{"value":0,"basis":"assumption","note":"零增长"},"netDebt":{"value":0,"basis":"assumption","note":"无净债务"},"cashFlows":[{"year":1,"value":100,"basis":"assumption","note":"年度FCFF100"},{"year":2,"value":100,"basis":"assumption","note":"年度FCFF100"}]}
```

企业折现值为1000元，等于100/10%的恒定永续结果，用于公式验收，不是真实公司估值。京东方实际验收使用2025年公开三表锚定期初值，未来参数明确为验收假设；不能把该验收报告当作公司预测。

方法依据：[NYU Stern FCFF估值说明](https://pages.stern.nyu.edu/~adamodar/New_Home_Page/lectures/val.html)。

DCF自然语言报告直接展示九组折现率与增长率敏感性、企业值和股权值；无效组合显示未计算。提供股数时展示每股情景值，不称目标价。股权桥接值为负时说明模型企业值不足覆盖净债务，不解释为负股票交易价格。

三表情景报告展开利润、现金流与资产负债联动表，分别列EBIT、利息与税、三类现金流与FCFF、资产负债合计及权益。负现金属于尚未解决的融资缺口情景，不视为可执行经营计划。

报告单列历史与归并输入依据：逐项说明来源陈述或计算归并、披露日期、来源链接及JSON字段绑定情况。假设数量与来源输入数量分别显示，JSON匹配不升级为公告原文核验。无历史来源的纯假设情景明确标示。

当JSON字段路径经过带有 period/publishedAt 的财务底稿行时，同时校验两日期不晚于asOf，且输入publishedAt必须与底稿行一致。可选observationPeriod须与底稿行报告期一致；核对结果保留boundPeriod/boundPublishedAt。没有行日期元数据的普通JSON不推断期间。以上仍是渠道底稿校验，不证明公告真实首次披露时刻。

三表经营情景适用性检查：可声明companyType=nonfinancial/bank/insurance/securities/financial。明确金融类别或登记底稿ORG_TYPE包含银行、保险、证券、金融时拒绝普通企业forecast，不生成结果。未登记或通用类别只表示未检测到明确金融分类，不证明模型已全面适用；结果modelScopeReview保留这一边界。此检查不阻止金融公司原始三表查询或有据的财务比较。

报告先交付有范围的情景判断：DCF敏感性差额不是置信区间；三表区分模型现金缺口与现实偿债能力，后续未计算年度不当零；倍数按各自有效样本数解释中位数，不据低倍数认定低估。模型说明并不代替研究者对现金流、可比性、股权桥接与融资条件的核验。

forecast可提供`debtScope`：`components`为非空列表，每项name及标准value/basis/note来源结构，与opening.debt同单位；可给`excluded`文字列表。构成不得重名或与排除项同名，非负合计须等于opening.debt，否则拒绝。正文显式列出纳入及排除范围；未登记时明确范围未核，不推定完整。合计一致不证明全部有息负债、到期本息或利息适用性；不要为了合计自动填未披露项目。
