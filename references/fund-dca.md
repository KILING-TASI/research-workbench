# 历史定投回测与同基金多方案比较

根据用户基金代码、起止日期、金额或份额、周/月周期和分红方式准备原始单位净值及分红拆分事件，运行：

```text
python scripts/fund_dca.py INPUT.json --out NEW.json
```

输出JSON及自然语言Markdown。history为date/nav；sourceUrl为净值来源；asOf为资料截止日；start/end为计划起止日；events每项date、cashPerOldUnit、newUnitsPerOldUnit、sourceUrl，分红金额以拆分前旧份额为单位；无事件须明确列空数组。

必须声明eventCoverage=verified-complete或assumed-complete，附eventEvidence说明。官方事件未完整核验时只能用assumed-complete并显著说明，未知且不愿作完整性假设时不计算。数据须覆盖起止，不能静默缩短。

plans每项name、mode(amount/units)、value、frequency(weekly/monthly)、distribution(reinvest/cash)，可设subscriptionFeePct（默认0，即未模拟申购费）。金额为每期含申购费总支出；份额模式为每期净购入份额。缺少用户关键参数时询问，不让用户填JSON。

最小输入：
```json
{"code":"000001","asOf":"2025-02-28","start":"2025-01-31","end":"2025-02-28","sourceUrl":"https://example.org/nav","history":[{"date":"2025-01-31","nav":1},{"date":"2025-02-28","nav":1.1}],"events":[],"eventCoverage":"assumed-complete","eventEvidence":"仅为演示，假设无分红拆分","plans":[{"name":"每月100元","mode":"amount","value":100,"frequency":"monthly","distribution":"reinvest"}]}
```
输出总投入200、期末资产210、累计收益率5%、期数2，并有逐笔日期、净值、费用和份额；XIRR另算，不把5%叫年化收益。

## 对话与交付

示例：比较110022在2023-01-03至2025-12-31每月500元和每周125元定投。先取数、核对事件及窗口，输出方案汇总及逐期明细。方案投入不等时明确提示，不能仅按终值排名。现金分红与再投没有区别时说明区间事件情况，不编造差异。

非交易日顺延至下个已有净值日；无官方日历不保证没有缺日。固定月日采用原始日期锚点，月末不足日截到该月最后一天。区间末未执行的计划单列。按当日净值成交，不模拟真实确认延迟、舍入或申购限制。分红默认事件日理论再投，可显式提供再投日期；现金权益不等于可用现金。不支持智能估值定投、费率阶梯或赎回到手收益；定投累计资产曲线不直接计算真实账户最大回撤。不重复扣净值内运作费。历史结果不代表未来。


## 日期缺口检查

输出`valuationAgeDays`（期末估值距请求截止日的日历日数）及各方案`scheduleDelays`（计划日、执行日与顺延日数）。顺延不能自动证明为正常休市。可指定非负整数`maxScheduleDelayDays`、`maxValuationAgeDays`，超限拒算；未设置门槛仍逐项披露，不插值补净值。门槛是研究参数，非市场交易规则，节假日与真实净值缺口需另行核对。


## 事件证据与假设标识

事件清单必须显式给出，缺失不能等同于无事件。`eventEvidence`须为非空文字。`verified-complete`仅为输入者声明，结果标记`input-declared-not-independently-verified`；程序并未自动认证完整性。`assumed-complete`标记`explicit-completeness-assumption`，报告顶部明确假设口径。不得将后者改写为真实账户已核验收益。


## 分红再投日期

事件可提供`reinvestDate`（不早于事件日）。截至估值日已经到达的再投日期必须有净值，否则拒算；不得自动顺延补价。等待期间分红为无息权益，期末仍未到再投日时列入`pendingReinvestment`与期末现金权益，不伪造份额。未提供时继续采用事件日理论再投并披露假设。事件权益按该日投入前旧份额计算，源自输入事件模型，非真实登记日、到账日或份额确认认证。


## 分红方式适用性

事件可附`distributionPolicy`：cash-only（仅现金）、cash-or-reinvest（允许现金或红利再投）、unspecified（未登记）。前两种必须附`policyEvidence`原文依据文字，仍属输入声明而非程序认证。研究区间内有现金分红且明确cash-only时拒绝再投方案。现金红利到账后的二级市场买入不是产品红利再投资，不能复用为免交易成本再投。未登记分红方式时报告突出理论假设限制。
