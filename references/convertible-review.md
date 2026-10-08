# 可转债基础诊断

用户问单只可转债“持有到期赚不赚、溢价怎么看、条款价格条件是否满足”时使用。AI整理参数，不要求用户填写JSON。它是现金流与条款观察，不是完整含权定价引擎。

## 已实现的交付

- 纯债现金流现值、税前到期收益率、转股价值与两种溢价率。
- 给定单一贴现收益率的修正久期、凸性和DV01。不是零息曲线或信用利差校准。
- 对已确认适用的退出现金流逐一测算，只称“已提供情景中的最低收益率”，不冒称完整YTW。
- 按交易日观察顺序做滚动窗口价格条件计数。每日使用当日有效转股价；旧观察退出窗口后才扣除。窗口不足标缺口，不推定已满足完整条款。
- 自然语言Markdown/HTML诊断与JSON计算底稿，可由研究结果检索找回。

## 调用与输入

```bash
python scripts/convertible_review.py references/examples/convertible-review-example.json --out-dir local-data/convertible-example
python scripts/start.py convertible --input references/examples/convertible-review-example.json --out-dir local-data/convertible-entry
python scripts/start.py convertible --continue-from local-data/convertible-entry --out-dir local-data/convertible-reused
```

输入包含currency（三字母币种）、source、fullPrice、faceValue、stockPrice、conversionPrice、discountYield和cashFlows。价格、面值与现金流金额必须同币种、同面值单位；fullPrice为含应计利息的全价，利率用小数。cashFlows每项为year（未来年数）和amount（正金额），包含全部剩余利息与本金，时间严格递增。跨期结算、税务或不规则计息先由AI按原文组织现金流，不从票息率猜现金流。续用读取已保存输入重新计算，不自动更新行情；更新资料须提供新输入。

可选exitScenarios：label、eligibility=confirmed、basis与cashFlows。实际退出日期、可行权主体和是否已公告须核对，未确认情景不能列为可执行退出。

可选clause：basis、tradingDaysComplete=true、window、required、ratio、direction（above/below，含等号）与observations。每项date、stockPrice、conversionPrice。当前脚本依赖明确的完整交易日声明，尚不自动校验交易所日历。实际条款是严格大于/小于时不能套用这一含等号计数；适用期间、暂停计数、重置条件先核对原文。

教学输入不代表真实标的、报价或投资机会。输出目录须不存在；输入缺项或无效时停止，保留原输入，不覆盖旧报告。

到期赎回金额注明包含末期利息时，末期现金流只记总额一次。赎回价核验不是持有人收益核验；缺买入价不补造，已摘牌标的不输出现时可交易判断。只有具体字段核验通过时，不将整个估值或条款模块标为已核。

## 从设计方案吸收与纠正

同一示例现金流0.3、0.5、1、111.5，年数1、2、3、4，贴现4.5%，现值应为95.120833；全价118.50对应税前到期收益率约−1.122642%，不能把方案中的95.13和−1.30%设成正确答案。

债底是按约兑付的估值，不是理论地板或保本线。触发价格条件与公告决定执行分开；计数达到门槛不输出卖出或转股指令。稀释率必须是股份比例，不能把余额/股本的带单位数直接加到1。组合权益敏感度需换算证券单位和市值弹性，不能把未经换算的加权Delta说成权益仓位。

## 尚未实现

自动条款原文取得与全条件核验、真实标的验收、零息曲线、违约概率校准、转股期权与下修定价、OAS、隐含波动率、累计巴黎蒙特卡洛、扫描池、新债中签概率与税后收益。不要把这些方案目标宣传成现有能力；新增法律、税务或交易规则参数时先查官方现行依据。
