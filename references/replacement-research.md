# ETF持仓替换研究

围绕一个问题执行：是否值得把现有ETF换成指定候选。先确认是否仍符合使用者的目标敞口；不从短期涨幅倒推“更好”。金额、计划年限和券商费率须明确标注实际输入或示例假设。

## 执行

宿主 Python 执行 `scripts/replacement_research.py 输入.json --out 新结果.json`。此入口只依赖标准库，不依赖工作台。首次依据不可覆盖。将输入和结果保存；研究任务在 research-workbench 的 research_tasks.py 中创建，填判断、反方证据、失效条件与复查日。没有用户请求不建立自动化。

输入：asOf、positionValue、positionCurrency=CNY、holdingYears、current、candidate、costAssumptions。current/candidate 含 code、indexId、indexVariant、currency、replication，以及 identity、annualFeePct、quote、tracking、premium、liquidity。

每个证据字段均是对象：value、sourceUrl、locator、observedAt、availableAt、verification（official-reviewed 或 third-party-observed）。推荐额外保存 documentSha256、reviewedBy。核验状态是登记者声明；原文身份、摘录和金额仍须人工/Skill核对。不能凭URL域名或标题自动标官方。

- identity：用官方产品资料确认代码、指数代码/版本、交易币种、复制方法。同主题不同指数、价格指数与全收益基准不混排。
- annualFeePct：年费率百分数；核对当前生效日、管理/托管/销售服务与其他运营费用的覆盖。未核实项不补零，不称完整TER。
- quote.value：bid、ask；同日，报价不是研究日则交易前复核。单点价差只是代理，不是成交保证。
- tracking.value：basis=nav-total-return-minus-index-total-return，start、end、count、indexId、annualTrackingDifferencePct、trackingErrorPct；两产品同区间、同基准，至少120期。跟踪差为基金全收益减指数全收益，越高不必然可延续；误差为波动，不当收益。由可复核同口径历史计算，年度报告不同区间数字不能直接混用。
- premium.value：百分数，价格与净值须匹配时点；无法匹配则缺失，不能拿前日NAV判断盘中溢价。
- liquidity.value：averageAmount、count，至少20期；核对两产品共同日期、停牌及成交额单位。需要结合订单深度，不能用平均成交额证明大额可成交。

costAssumptions 含 sellCommissionPct、buyCommissionPct、sellMinimum、buyMinimum、sellSlippageBps、buySlippageBps、otherCashCosts。佣金按输入金额分别计费并考虑最低佣金；半价差代理各计一边，加输入滑点和其他成本。简化模型两边使用相同名义金额，未模拟整手余款与深度。假设为零不代表实际没有成本。

## 结论与复查

输出证据缺口、逐项成本、年度费率节约、仅按费率的回本年限、历史净跟踪差对照、反方理由和复查条件。任一关键缺口或候选跟踪更差时暂缓；费用相同/更高或持有期无法覆盖成本时不以省费用支持替换。全部满足也只进入人工复核，不给自动交易指令。

净值表现已扣费用，不把观察到的净跟踪优势与费用节约相加，也不把历史差当未来收益。成本回本是情景测算，不是策略有效性证明。

真实试跑510300→510310：交易所名单确认代码与CSI300产品名称；510310管理人页面核实管理费与托管费。指数版本/复制方式、510300官方费用、共同区间跟踪质量与当日折溢价仍缺；9月30日报价只能作历史成本示例。10万元、一年及佣金是示例，不能解释为使用者持仓。
