# 公司与发行定价研究

scripts/company_research.py 输入.json --out 新结果.json；--discover先定位招股书前30页关键词候选，可用maxPages=1至60。候选不是完整摘要，不把目录命中自动写成事实。默认研究卡不扫描全文件，只读身份页和指定摘录/表格页。

研究卡必填code、asOf；documents可提供PDF原文，financials可提供年度合并财务观测。documents项：id、issuer、title、path、sourceUrl（北交所/巨潮明确域名）、publishedAt、可选sha256、excerpts。前12页匹配发行人与标题，有代码另匹配标示，否则标代码关联由输入声明。未逐次联网验证PDF与URL一致，保留文件hash；披露日期由输入提供，不证明历史首次公开。

文本摘录包含id/topic/page/text，必须在指定页唯一匹配。topic：business、customers、fundraising、risks、inquiry、financial、valuation。输出原文摘录与来源，不把公司自己的表述当作已验证竞争优势。

table-cell摘录定位：kind=table-cell，tableIndex/rowIndex/column/labelColumn/labelRows（均0起）、headerRow/headerColumn/periodHeader、period（ISO年度末）、label/value/unit。程序匹配单元格值、完整跨行标签、年度表头及水平方向列对齐；当前只支持标签明确元或百分数的布局。无OCR、跨页复杂表格未全覆盖，不自动选数值列。

financials每项period、periodBasis=FY、scope=consolidated。本入口采用12月31日为年度末；半年或季度即使标为FY也会拒绝，不能用于年度发行PE，不支持其他财政年结日。标签与日期校验不代替原文完整期间及指标语义核对。revenue、netProfit（归母口径）、adjustedProfit（扣非归母）、cfo、rdExpense、customerTop5Pct、fundraisingTotal、workingCapitalUse均为观测对象：value/unit/evidenceIds。金额统一CNY，集中度pct。净利润字段语义由映射者确认，不能以利润表总净利润替代归母。table-cell证据逐项比对观测的值、单位和年度；没有证据标用户输入未核验。缺项不填零。计算连续年度收入/扣非增长、经营现金流/正归母利润、非经常损益占比、研发强度和募投补流占比；负或零分母留空，不强行显示异常比率。

发行定价：factsStore接第一批发行价；或price观测对象输入CNY/单股价格。postIssueShares单位shares，shareBasis明确before-greenshoe/full-greenshoe，不重复叠加绿鞋。valuationPeriod明确对应FY扣非合并归母净利润。发行市值=价格*股本；PE=市值/正扣非利润，非正利润留空。

peers输入code、pe观测对象（unit=multiple）、period、basis=adjusted-FY-consolidated、currency=CNY、valuationDate=asOf、comparabilityReason。日期/利润口径/币种不同剔除，不能混TTM与发行静态PE。至少3家才输出中位数及相对PE差异；可比理由是输入声明，统计比较不是合理价格、申购排名或收益预测。定价相同假设下profitStress=[{label,changePct}]仅测算扣非利润变动后的PE，不生成目标价。

真实世昌股份验收含2022至2024三年度12个财务单元格、业务/客户/募投风险/替代风险摘录及会计追溯调整说明。发行后股本尚为显式输入，问询原文及统一时点的真实同行池不足，研究卡保留缺项。历史年度按同一份招股书追溯数据计算，不拼接旧版本口径。当前版不自动下载任意招股书、全量提取全部附注或自动定性财务造假。
