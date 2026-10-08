# 日常使用：从问题到报告

说明版本：1.80 · 更新日期：2026-10-09。用户说问题、提供已有资料；AI准备参数和输入文件。以下为AI调用模板，均从Skill根目录运行，新结果目录必须不存在。

## 1. 第一次研究，先确认哪些资料？

|你想解决的问题|需要确认的内容|入口|
|---|---|---|
|比较基金或ETF的历史表现|2至10个不同代码/完整名称、日期区间|`start.py funds`，ETF在此比较公开净值，不是成交行情|
|看钱放在哪里|持仓名称、项目标识、市值、币种、类型|`start.py snapshot`，不从金额猜底层风险|
|看组合收益与历史风险|共同历史、权重、指定路径方式|`start.py portfolio`，不能仅用金额表算回撤|
|北交单只发行资金情景|发行、预算、资金日期、费用和明确情景|`start.py bjx`，年度问题另走年度入口|
|可转债现金流与条款|已取得现金流、条款、价格及适用日期|`start.py convertible`|

基金/ETF历史比较：

```bash
python scripts/start.py funds --codes 005827 161005 --start 2025-01-02 --as-of 2026-09-30 --online --out-dir local-data/my-funds
```

代码或完整名称二选一，名称歧义先给候选；比较池名称可省略，默认用户指定池，不认证为同类。`--online`明确开启查询，默认不会继承以前的联网许可。完整产品、经理、持仓和费率评价另按[基金评价框架](fund-evaluation.md)补资料。某只失败不删掉它缩小比较池；日期边界不足会说明实际范围，节假日与漏数需要进一步核对。

持仓表用UTF-8 CSV，必要列为`code,name,market_value,currency,asset_class`，可加`valuation_date`。支持对应中文列名及明确币种、类型，见[教学持仓表](examples/holdings-example.csv)。市值填币种基本单位数字，不能用份额、本金或未标单位的“金额”；规范千位逗号需按CSV规则加引号。币种与类型由用户确认，类型为fund/etf/stock/bond/convertible/cash/other。混币种不直接相加。截图模糊或单位不明先询问。

```bash
python scripts/start.py snapshot --input my-holdings.csv --as-of 2026-10-09 --out-dir local-data/my-holdings
python scripts/start.py portfolio --input portfolio-input.json --out-dir local-data/my-portfolio
```

持仓快照只回答声明金额结构，A/C名称相似仅提示份额线索；缺估值日不冒称当前账户。组合输入见[组合历史](portfolio-stress.md)，买入持有与固定权重按明确口径计算，不还原真实交易。

## 2. 找回报告，再继续问

```bash
python scripts/research_results.py --folder local-data --query "消费" --out local-data/我的研究结果.md
```

按登记名称、代码、目录、结论或区间查找，空格分隔的关键词必须同时匹配。只读指定父目录的直接子目录，不扫描其他私人目录。失败记录也保留；按登记留存时间新到旧排列，旧记录缺时间排在后面，不用文件修改日期猜最新。`--limit`只限制展示数，不替用户选择研究质量。

找回和续问可以合成一步：

```bash
python scripts/resume_research.py --folder local-data --query "510050" --question "只看近半年" --out-dir local-data/half-year
```

只有唯一匹配、具有接续请求记录时才执行；多份结果列出候选，AI让用户选定，不默认最新或第一份。也可用`--previous 已选定目录`直接指定。没有旧请求时明确准备原参数，不从正文猜输入。

## 3. 已选定报告，常用追问怎么处理？

|已有研究|可以直接说|处理方式|
|---|---|---|
|基金/ETF净值比较|只看近一年/半年/三个月/1至60个月；明确年份或日期区间|保留标的；最近以旧截止日为基准，不是今天|
|基金/ETF净值比较|哪只更稳、波动更小、回撤更小|分别解释波动和最深下跌，冲突不强行排统一名次|
|持仓快照|我的钱主要集中在哪|前三项金额与份额线索，不当作底层风险贡献|
|现金流复盘|我到底赚了多少、账户增长是不是收益|沿用已声明估值/出入金，区分本金与损益；缺新转账不猜|
|组合历史|谁在拖累组合、收益主要靠谁|按已声明路径解释收益百分点；无路径或无对应贡献不编造排名|
|北交单只情景|沿用上一份，把资金改为1,250万元|规范金额换算，仅改预算；原资金日期和其他情景保留|
|再平衡|改成按月再平衡|月初观察日信号，下一观察日执行；原规则已相同则明确仅重算|
|支持接续的研究|重算、沿用原资料重算|保留参数，不自动刷新资料|

```bash
python scripts/resume_research.py --previous local-data/my-funds --question "哪只更稳？" --out-dir local-data/risk-answer
```

这是常用短句的确定规则，不是任意问题解析器。不同模块各有支持范围；混入换标的、费用、调仓或刷新要求时不忽略额外条件，由AI明确后使用原入口。基金区间对照重新计算，不能将区间差别说成产品改善；同一截止日的两段收益按复利连接，不直接相减。

北交日期按输入声明显示，不表示今天可申购或实际到账。年度金额问题用[年度情景](../modules/bjx-newshare-toolkit/references/annual-yield.md)，可接`bjx_annual_followup.py --continue-from OLD_DIR --capital 元金额 --out-dir NEW_DIR`；不能把单只资金情景当成年化预测或替客户确认权限。

## 4. 新资料、日期或参数变了怎么办？

需要新数据时明确取数；基金入口可显式加`--online`，只补不可复用响应，保留取得日期。改费用、持仓、权重或其他条件时，由AI准备用户确认的新输入并另存结果：

```bash
python scripts/start.py portfolio --continue-from local-data/my-portfolio --input revised-portfolio.json --out-dir local-data/revised-portfolio
```

有登记输入摘要时先核对，文件改变、缺失或路径异常会提示复查，不冒称原资料未变；明确新输入仍可重算。旧无摘要保留兼容，不声称已完成冻结核对。旧报告不覆盖。摘要检查本地一致性，不认证来源、时效或防恶意重写。

## 5. 先打开哪个文件？

每次先打开`打开这里.html`，看针对问题的主报告、完成范围和下一步。风险或贡献追问优先显示直接回答，完整报告作为补充；结论前置，依据较小字号。原报告链接便于回看，不代表资料已刷新。

|状态|怎么理解|
|---|---|
|partial|本次指定分析已生成，但来源、完整评价或真实账户等仍有明确缺口|
|blocked|输入、数据或环境不满足，保留原因与处理方法|
|needs-clarification|先确认标的、匹配报告或关键参数|
|记录需要复查|登记内容变化或不可核对；旧摘要不继续展示为当前结果|

## 6. 其他入口与深入方法

`compare`、`news`、`style`、`lookthrough`、`rebalance`、`allocation`、`cashflow`、`convertible`及以上入口可按各自输入接续；`ask`公告入口暂不支持`--continue-from`。普通用户说需求，AI按相关文档准备数据，不要求用户填写结构化文件。

- [再平衡日常参数与费用](rebalance-daily-use.md)：Node依赖、频率、逐资产成本、分段和零摩擦反事实的适用边界。
- [配置候选](portfolio-allocation.md)、[现金流复盘](portfolio-cashflow-review.md)：候选配置不等于最优未来配置，现金流复盘需完整出入金与估值。
- [可转债基础诊断](convertible-review.md)：末期赎回额已含利息不重复添加；无成本不编造投资收益。
- [收益风格](returns-style.md)、[持仓与组合](holdings-portfolio.md)：缺基准或底层不猜测。
- [现有功能](current-capabilities.md)、[当前验收](acceptance-current.md)：分别查看能力范围与实测证据。独立包实测不等于新OS、全部模块或浏览器视觉均通过。

本流程不创建后台任务。资料、原响应和私人持仓不随代码包分发；每个新标的仍需按实际取得情况研究。
