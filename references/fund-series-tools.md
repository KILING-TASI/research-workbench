# 净值质量、分红口径、多基准与快照对比

## 入口

在Skill根目录执行，AI组织输入，用户无需填写JSON：

```text
python scripts/fund_series_tools.py quality INPUT.json --out NEW.json
python scripts/fund_series_tools.py distributions INPUT.json --out NEW.json
python scripts/fund_series_tools.py benchmarks INPUT.json --out NEW.json
python scripts/fund_series_tools.py snapshot-diff INPUT.json --out NEW.json
```

新文件写入，已有输出拒绝覆盖。四项结果可保存在研究档案中；可通过综合报告supplementaryResults接入既有JSON、Markdown和HTML；AI需先核对结果主体/截止日。输入校验失败必须显示原因，不输出伪完整结果。

## 净值质量 quality

输入code/asOf/sourceUrl、history[{date,nav,accumulatedNav?,adjustmentFactor?}]。日期严格递增、净值为正。jumpThresholdPct默认10，flatRunObservations默认5，都是核查阈值，不是错数判定阈值。

可选calendar{start,end,dates,sourceUrl,applicabilityConfirmed}。需要符合基金投资市场、申赎/估值日安排的明确日历；只有applicabilityConfirmed=true才输出dateCoveragePct。没有日历不拿工作日猜交易日，不打综合质量分。输出缺日、日历外观测、跳变及连续不变线索。连续不变不能证明停牌。

事件记录完整时可核对累计净值与因子。累计净值采用单位净值加累计现金分红口径，只在无拆分且起点累计净值可得时检查；拆分后该项不适用。adjustmentFactor必须转换为本工具的“初始1份经红利再投后的单位数”定义，不能直接比较平台任意前/后复权因子。consistencyTolerance需按显示精度设置，默认1e-6。无字段不校验、不声称完整一致。

## 分红与拆分 distributions

history同上；events必须显式提供（确实核验无事件用空数组）。eventCoverage=verified-complete-for-window只有取得并核对完整事件来源后才设置，不能从缓存没有事件推断完整。未知则停止计算。

事件字段date/sourceUrl/cashPerOldUnit/newUnitsPerOldUnit，分别为每旧份现金、每旧份变成的新份额。现金与拆分数量至少明确提供一项；仅缺另一项时采用0或1，不能把未提供任何数量的事件当作无变化。同日现金与拆分合并一条事件；事件须在窗口起点之后且当日净值可得，否则拒绝，不插值。除息日再投是模型假设，未模拟实际到账时点、税费和交易费用。

输出reinvestValue与cashAccountValue（均初始本金归一为1），后者是基金市值加保留的无息现金，不是基金净值。分别计算收益与年化、回撤；现金分红按初始本金统计，不冒称当前股息率。factorVersion根据原始序列和事件生成哈希，输入及结果需共同保存。红利再投序列可映射为既有compare引擎的total-return输入；现金账户应单独说明口径，不与纯基金净值混称。

最小示例（合成数据，仅用于说明参数）：

```json
{"code":"example","asOf":"2026-01-04","sourceUrl":"https://example.org/nav","eventCoverage":"verified-complete-for-window","history":[{"date":"2026-01-01","nav":1},{"date":"2026-01-02","nav":0.9},{"date":"2026-01-03","nav":0.99},{"date":"2026-01-04","nav":1.08}],"events":[{"date":"2026-01-02","cashPerOldUnit":0.1,"sourceUrl":"https://example.org/dividend"}]}
```

运行distributions后，末期reinvestValue=1.20、cashAccountValue=1.18；总收益分别20%与18%。短窗口几何年化会很大，用户报告优先展示区间收益及期限，不能将短期年化当未来收益。不完整事件输入报错，先补证据或只输出质量线索。

## 多基准 benchmarks

输入asOf/currency/frequency（日daily、月monthly）/riskFreeAnnualPct，以及fund{code,currency,basis=total-return,sourceUrl,history[{date,value}]}和benchmarks数组。

每个基准name、components（同基金序列字段加weight）、rebalance=each-observation或buy-and-hold、contractBenchmarkStatus=verified-match/verified-different/unverified。非负权重合计1。合同状态由原文核对，不凭用户名称认定。支持一个或多个组件及多个基准；联合对齐共同日期，不回填缺日；月频必须逐月连续。

每观察期再平衡按加权周期收益连乘；买入持有按起点金额权重归一后的组件市值求和。报告明示基准来源、权重、再平衡、频率和合同一致性。输出累计超额百分点、年化跟踪误差、信息比率、Beta及Jensen Alpha。Jensen Alpha是周期超额收益回归截距乘年频数，不等于几何年化Alpha。零基准方差或零主动波动时对应指标留空。

市场指数序列仍需取数并核验；允许指定基金作为研究参照，但必须写“基金参照”，不能假称指数或合同基准。不自动分解打新、费用、转融通收益。

## 快照对比 snapshot-diff

before/after各含subjectCodes（顺序一致）、asOf（递增）、metrics（数值或null）、methodology（必须含returnBasis/frequency/window/classificationVersion）、sources、reportVersions。

窗口要说明固定日期还是滚动期限；classificationVersion不适用时明确填not-applicable，不能用空缺代替核验。口径字段变更时全部指标只并列，不输出可比差值；同口径也不将差异当能力归因。字段缺值不计算差异。输出口径变化、指标变化、两版来源和报告版本。保存原快照，不能改写旧结果。已有档案结果需由AI先整理成该明确结构，尚未自动转换所有旧档案类型。

## 证据与确定性披露

区分原文披露、确定性计算、假设估算、缺失与冲突。完整报告快照只证明报告日披露覆盖，不证明逐日真实持仓或精确业绩归因。数据覆盖率不是置信度、准确率或投资适配评分。置信区间必须有统计模型、样本与分布假设，不因标为估算就随意造区间。

每项结论注明依赖的数据、公式/处理口径、参数、来源日期及已知限制。报告缺失只阻断依赖该报告的持仓/归因，不能据此认定独立净值序列的回撤缺失。缺口清单必须说明具体影响。

版本对比检测的是数值、来源及口径变化，不能自动认定“真实经济变化”或因果；源文件、解析器和数据口径变化需分别记录。竞争差异以实际功能验收为依据，不宣称独家或竞品无法实现。

## 序列计算补充
日频基准比较可提供与quality相同结构的calendar及calendarMarket。共同观测区间内，适用日历缺日或日历适用性未确认时，年度跟踪误差、信息比率与年化Jensen指标留空；基金和基准同时漏掉同一天也会被检测。alignment.calendarCheck保留核查结果。累计区间收益与按实际期限计算的年化收益另行保留，不证明逐日完整。未提供日历时不声称日频完整性已核验；检查仅覆盖共同区间，不证明原始请求窗口完整或数据源正确。

事件完整性仅记录输入声明，不等于独立核验。极端短区间的年化计算超出数值范围时留空并解释原因。基准与基金日序列对齐丢失观测时，不输出年度跟踪误差、信息比率与年化 Jensen 指标。缺适用交易日历时，完整度留空。

跳变结果保留previousDate、date与calendarDayGap，说明相邻有效观测的起止和自然日跨度；不将跨休市区间称相邻自然日、不摊平涨跌幅。跨度不等于漏失估值日数量，仍需产品适用日历及事件核验。
