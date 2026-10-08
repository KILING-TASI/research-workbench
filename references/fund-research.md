# 基金研究调用规范

聊天直接接收基金代码、候选池或持仓，不依赖工作台。参数不足时只询问影响结果的必要信息。默认输出风险摘要、共同口径对比表、指标解释、事件来源与缺失信息；技术参数与执行过程不写入用户回答。

## 分析与比较

`node scripts/fund_research.js compare 输入.json 新结果.json`

输入沿用 research_analytics.js 的历史总收益结构：asOf、frequency(daily/monthly)、currency、riskFreeAnnualPct、assets（code/currency/basis=total-return/sourceUrl/history[{date,value}]）。可选start/end。全部输入先检查乱序、重复、非正净值、未来日期，再取共同观察日；不足四期阻止，不填充缺失。月频仍须连续，日频共同观察不证明交易日完整。默认等权仅用于复用统计引擎，不作为配置建议。

输出单基金风险指标及通俗解释、输入池内中位数和逐指标高低比较、相关矩阵及裁剪明细。池内中位数不是全市场同类中位数。只有明确同风格、同份额及样本范围时才使用“同类”，不得将不同风格两基金池命名为同类。年化波动较低不等于更优，比较仅描述该指标。

可传reference（相同历史结构，role=declared-benchmark或comparison-reference；前者需definition定义）；并入共同日期后调用benchmarkStudy。不提供合成基准、不把同伴基金叫合同基准。多个指数/同类池分别比较，不能混成单一参照。

events可列code/id/title/publishedAt/sourceUrl/status(confirmed/unverified)。事件含义来自原文核对；元数据线索仍未核实，不推断因果或价格方向。

## A/C成本临界区间与定投

`node scripts/fund_research.js feeStudy 输入.json 新结果.json`

输入asOf、basis=constant-gross-nav-cost-scenario、classes两类、lots[{date,amount}]、horizonDays(1—7300)，可选showDays。每类id/sourceUrl/observedAt/managementPct/custodyPct/salesServicePct/subscriptionPct/redemption[{minDays,ratePct}]；赎回阶梯从0日起、严格递增。费率全为百分数，不是小数比例。输入限为外扣比例申购费；金额分档或固定费用先单独计算，不转换成未经说明的统一费率。

每笔投入分别计算外扣申购金额、运作费近似计提与持有天数对应赎回费。输出所选天数成本、各类费用分解、较低费用类别变化日期；是费用优势，不是产品买入建议。多笔投入支持定投成本情景，新投入按自身持有年龄收费。当前不使用真实净值，避免再次扣减已包含在净值里的管理、托管和销售服务费；真实历史投资者收益仍调用fundInvestorStudy，只扣投资者另付费用。

不保证唯一临界点，费率阶梯可出现多次切换。无交点不能称某类永久更优；现行费率不代表过去及未来费率，历史版本有效期需另核。

## 自选事件检查

`node scripts/fund_research.js monitor 输入.json 新结果.json`

输入asOf、watchlist代码数组、events、可选上轮seen。事件字段同上；输出新增/更改事件、seen。保存seen后再用于下轮，标的退出时间窗口不删除历史标记。当前从输入事件执行差异检查；资料由原文/已接入采集流程准备，不代表自动取得全部基金公告，不常驻、不发送通知。持续跟踪须用户明确提出并配置调度。

传闻不得标为确认离职。份额赎回与基金规模下降分开，规模下降可能来自净值变化；规模低于5000万仅作为核查合同清盘条件的线索，不直接断言将清盘。百亿规模也不直接断言能力下降。

## 其他需求复用路径

- 条件/负向筛选：先确定风格池、观察区间、指标定义与缺失处理；风格漂移百分比须定义距离算法，不默认20%为统一标准。缺字段保留未判定，不误当通过。保存模板不等于启用持续监控。
- 持仓/个人组合：holdingsStudy、holdingsChange与research_extensions.py；组合可混合股票、ETF、基金与债券，穿透不完整部分显示未知。定期报告快照不能证明真实交易、持有周期或已实现损益。
- 情景与调整前后比较：portfolio_stress.py、portfolio_models.py及rebalance；分别保存原方案、假设替换与费用，不输出交易指令。一次压力损益不叫最大回撤；回本所需涨幅可算，未来回本时间不能预测。
- 经理历史与归因：需逐产品任期、共管关系、有效基准及因子序列；公开披露不足时不宣称完整履历。Brinson需期间行业权重及收益，净值回归不能证明纯个人能力。
- 原文/合同核对：verify_original.py及报告解析；同口径同日字段方可比较。更正保留版本，关键词摘要不替代规则适用性核查。

费用、监控和筛选输出仍需注明来源、统计时间、历史与假设边界。研究事实与推论以文字标签区分，不只靠颜色。
