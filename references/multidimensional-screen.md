# 多维条件筛选与ETF持仓反查

对指定候选池进行证据绑定筛选，不自带全市场七维数据。自然语言请求先准备候选和已有指标，再组织参数运行：
```text
python scripts/multidimensional_screen.py INPUT.json --out NEW.json
```
输入asOf、scope、candidates、conditions；每候选code/kind/market/name用于明确身份。同代码跨市场不合并。

fields字段支持fundType、inceptionYears、rating、riskLevel、returnPct、maximumDrawdownPct、annualVolatilityPct、Sharpe、dcaReturnPct、aumCNY、turnoverPct、netFlowCNY、valuationPercentile、valueExposure、growthExposure、sizeExposure。每字段value/observedAt/sourceUrl/basis，金额须说明币种，区间统计附window。评级和风险分级的basis需含供应商及标准；数字风险等级不得跨供应商直接比较。因子暴露需已有实算来源，不能依据名称猜测。

tags包含theme/industry/style，各自value为标签列表，加observedAt/sourceUrl/basis。basis区分产品名称、指数主题、实际持仓行业等。holdings为value列表(code/market/weightPct)、complete、observedAt/sourceUrl/basis=actual-fund-holdings。指数成分不能冒充实际持仓；局部表未出现某股标未知，不推断未持有。

conditions三种格式：
```json
[{"kind":"metric","field":"maximumDrawdownPct","op":"lt","value":25,"window":"2023-01-01/2025-12-31"},{"kind":"tag","dimension":"theme","value":"红利","basis":"verified-index-theme"},{"kind":"holding","code":"600519","market":"SSE","minimumWeightPct":1}]
```
数值用百分点（25表示25%）；op=lt/le/gt/ge/eq，多条件同时满足，区间拆上下限。可在规则指定basis/window；未匹配时不是满足条件。可选rank={field:aumCNY,direction:desc,sameIndexOnly:true}，同指数要求候选填写已核验trackingIndex。排序按日期、口径、窗口、单位分组；缺排序值不进入排序，不填零。

输出selected/excluded/unknown、逐条判定、条件覆盖、分组排名。自然语言报告先写候选范围和实际覆盖，再说明通过、失败、资料不足；不能声称全市场优选或未来表现。资金流不能用成交额代替；定投表现须带方案口径；成立年限需由已核验成立日期计算。此入口不自动取得主题、评级、流向、估值或因子数据库。


## 单位核验

收益、回撤、波动、定投收益、换手与估值分位要求 `unit=pct`（20表示20%）；规模、净流入要求 `CNY`；夏普要求 `ratio`；成立年限要求 `years`。指标单位缺失或不符标为资料不足，不静默将比例/百分点、元/万元或外币换算。条件可指定unit，但须符合上述字段规范；其他字段可按已有定义指定规则单位。数值条件不接受字符串、布尔值或非有限数。排序指标单位错误不进入排名，并在 `rankingGaps` 中说明。评分及排序仍仅针对指定输入池，不代表全市场排名。


资金流筛选条件必须指定 `basis` 与 `window`。未指定、口径不同或统计区间不同均标为未知，避免把真实结算现金流、供应商估算、份额变化估值代理混在一起比较。


入口同时输出JSON、Markdown和HTML研究简报：逐条件可判定覆盖、对象状态、缺口原因、独立排序组与资料来源。覆盖数不是七维齐备率或置信度；同指数排序开启时缺少trackingIndex的对象不进入排序，明确记录缺口，不能把所有未知指数合并成同组。输出已有时拒绝覆盖三种文件。

单个候选的日期越界、来源缺失或证据格式错误按条件列为不可核验，保留候选及原因，不中断其他候选；覆盖分母仍为全部输入。无效的筛选规则或重复候选仍拒绝运行。
