# 持仓与组合诊断

诊断基金、ETF、股票、债券等跨资产持仓，分析重叠、穿透、集中度、风险贡献和假设调整。区分披露快照、历史回测、未来情景；未穿透仓位保留未知。

[宏观与跨资产观察](macro-asset-observation.md)：公开宏观观测、QQQ/TLT/BTC历史价格共同窗口；不做周期预测或因果归因。

## 任务与已有入口

路径相对 Skill 根目录。读取所选参考中的完整调用模板和输入规范，再准备参数；表中的简称不替代实际 CLI。

| 请求 | 规范与入口 |
|---|---|
| 已取得节点的有效持仓、根持仓冗余及证券别名关系 | [递归穿透](research-extensions.md)：start.py lookthrough --input INPUT.json --out-dir NEW_DIR；证券与公司层次分开，未知不填零 |
| 基金投资明细与当期会计余额、净资产比例核对 | [基金投资核对](fund-investment-reconcile.md)：fund_investment_reconcile.py REPORT_RESULT.json --out NEW.json；不等于完整组合穿透 |
| 已有港美元日线与同日汇率的人民币换算 | [跨币种价格](currency-price-bridge.md)：currency_price_bridge.py INPUT.json --out NEW.json；美元、港币汇率支持按请求获取；换算价格不是总收益 |
| 已核验同日行业表按静态基金权重汇总 | [组合行业敞口](portfolio-industry-exposure.md)：portfolio_industry_exposure.py INPUT.json --out NEW.json；分类与版本分组保留，未知资产不当现金 |
| 一次压力损益、历史相关性 | [组合压力](portfolio-stress.md)：portfolio_stress.py；损益不当作最大回撤 |
| MVP、有效前沿、分块蒙特卡洛 | [组合模型](portfolio-models.md)：portfolio_models.py；按需执行，不称未来最优或损失上限 |
| 联接基金已核验股票穿透反查与权重条件 | [穿透反查](feeder-holdings-screen.md)：feeder_holdings_screen.py INPUT.json --out NEW.json；未展开部分不按零持仓处理 |
| 已核验联接基金直接股票与目标ETF一层股票暴露 | [联接股票穿透](feeder-equity-exposure.md)：feeder_equity_exposure.py DOSSIER_RESULT.json --out NEW.json；重叠合并，其他资产保留未展开 |
| 联接基金原文明示目标代码及同期间子报告关系 | [目标报告关联](target-fund-link.md)：target_fund_link.py PARENT_REPORT.json --child-report CHILD_REPORT.json --out NEW.json；不按简称猜代码，不推断持有权重 |
| 已核验股票持仓与有来源的主题分类暴露 | [主题暴露](holding-theme-exposure.md)：holding_theme_exposure.py INPUT.json --out NEW.json；分类缺项保留未知权重，不按名称猜主题 |
| 已核验年报持仓转为筛选、规模字段与股票反查 | [报告筛选联动](report-screen-bridge.md)：report_screen_bridge.py INPUT.json --out NEW.json；股票市场命名空间与交易所身份分开 |
| 一次获取基金明细与指定年报/中报持仓研究 | [基金资料联动](fund-dossier.md)：fund_dossier.py --code CODE --period YYYY-MM-DD --as-of YYYY-MM-DD --out-dir NEW_DIRECTORY；各路失败保留其他结果 |
| 按代码报告期获取年报/中报副本、身份匹配和股票持仓解析 | [报告获取](fund-report-archive.md)：fund_report_archive.py --code CODE --period YYYY-MM-DD --as-of YYYY-MM-DD --out-dir NEW_DIRECTORY --holdings；副本与官方来源核验分开 |
| 多维基金/ETF条件、主题标签筛选、实际持仓反查及分组排序 | [多维筛选](multidimensional-screen.md)：multidimensional_screen.py INPUT.json --out NEW.json；指定候选池，不冒称全市场七维覆盖 |
| 持仓风格、仓位时序、披露行为、研究条件及专项组合调用 | [基金专项](fund-specialists.md)：fund_specialists.py research/style/allocation/behavior/conditions；复用既有业绩、观点、归因 |
| 持仓双口径重叠、指定池内相似基金、综合研究简报、多期快照归因 | [综合诊断](fund-diagnostics.md)：fund_diagnostics.js overlap/similar/report、attribution_link.py；先准备已有来源资料 |
| 披露快照Brinson归因、基金池与自定义评分、持仓反查、文档条款精读、基金档案、跨资产贡献 | [基金池与归因](fund-research-library.md)：research_library.py brinson/pool/score/reverse/documents/archive；fund_research.js contributions；先读取参数与范围规范 |
| 参数上下文、基金对比与基础组合诊断、来源链与失效检查 | [研究工作流](research-workflow.md)：research_pipeline.py context-create/context-revise/run-template/impact；包括基金对比、基础组合、FOF披露穿透等已接通模板 |
| 持仓重合、两期变化、行业、年度利润 | [测算规范](research-analytics.md)：holdingsStudy/holdingsChange/industryStudy/fundProfitStudy；报告快照不还原交易 |
| 子基金毛资产与负债单层分列 | [资产池与分母规范](fund-report-archive.md)：python scripts/gross_asset_lookthrough.py INPUT.json --out NEW.json；同池份额合并，未知保留，不等于逐券递归 |
| 子基金原文披露利率冲击及单项父权重影响 | [原文情景规范](fund-report-archive.md)：python scripts/disclosed_rate_scenario.py INPUT.json --out NEW.json；净资产与冲击金额绑定原页，非整体组合压力测试 |
| FOF递归、时变假设危机、行情时效 | [扩展规范](research-extensions.md)：research_extensions.py；FOF完整表另用fund_report_fof.py |
| 债券基础计算、转债条款状态、财务勾稽 | [测算规范](research-analytics.md)：bondResearch/convertibleTerms/financial；基础模型非完整含权定价 |

归因与基金池：参见[基金池与归因](fund-research-library.md)、[综合诊断](fund-diagnostics.md)和[深度证据](fund-depth.md)。期初权重、分类版本、总收益或匹配基准不足时不输出完整归因。

## 共用步骤

按[共用能力分工](shared-research-layers.md)复用取数、证据、计算和表达；仅组合已有接口，不假设存在一个覆盖全部专题的自动执行器。报告与版本留存见[研究档案](archives-reports.md)。

组合评价先给有范围的总体判断，例如“本窗口分散效果有限”，再说明核心矛盾及支持证据。重叠、行业快照、历史相关性、波动贡献与共同回撤回答不同问题，不能拼成真实账户的因果解释；逐项标明日期、权重维持方式与费用假设。不能仅因股票重叠低就认定分散充分，也不能仅因历史相关性高就解释具体原因。

若用户未提供目标、期限与可承受亏损范围，仍交付已知结构和历史风险判断，但不生成健康分数、适配认证或调整比例。说明哪类目标尚不能评价，以及什么证据会改变判断；不把补资料清单当作最终评价。完整内容复查按[报告验收](report-content-acceptance.md)执行。

统一组合贡献快照导出前检查登记的本地输入和代码版本。已变化时在报告前部标明需要重新计算，仍可作为历史快照阅读；未变化也注明没有重新采集远程数据，不把历史导出宣称最新诊断。

用户要求按资金用途、期限、现金预留核对组合时，见[投资意图与约束](investment-intent.md)。所给检查项通过不等于投资适当性认证。

## 指数与积极投资行业分表
ETF中报/年报的行业合计可分别披露指数投资和积极投资。解析时两段分别定位、保留物理页和表格坐标；分表缺失、同段多种合计或总表混入时拒绝相加。股票明细与行业合计一致仍不证明会计余额差额已解释。可退替代款注释只作为口径线索，不据此自动核销差额；差额未解释时暂不进入严格FOF自动穿透。


组合贡献报告先指出本段历史中承担最多波动风险的资产，并对照其资金权重。协方差贡献可为负或超过100%，零波动时保留空值，不把等资金权重解释为等风险。示例权重测算与真实账户收益必须区分；没有实际交易与分红记录时，不把每日无成本再平衡模拟称为实盘验收。

涉及制度、条款、专业方法与解释时，使用[适用依据规范](research-basis-standard.md)，核对范围、版本和原始依据；规则核对不替代本场景计算或内容验收。

需要观察分散关系随时间变化时，使用[组合压力](portfolio-stress.md)的滚动历史协方差与尾部样本检查，并生成自然语言报告。当前权重只用于研究加权，不还原真实交易；少量尾部样本不出稳定结论。


再平衡成本敏感性复用[研究测算](research-analytics.md)中的`rebalance`，支持逐资产成本及逐笔账目。费率与方向税费是输入假设，实际申赎与交易适用规则需另行核对。

组合贡献报告必须解释三个窗口与单位：收益贡献为完整共同区间的组合收益百分点；波动占比为该区间协方差贡献；回撤贡献仅来自同一组合峰谷，负为拖累、正为缓冲。三者不合成单一风险评分，不以收益贡献抵消回撤段贡献。导出前核对峰谷位于共同区间，非零回撤须有不同峰谷日期；数值自洽仍不证明原行情、分红或账户已核验。

资产与负债桥接可用 `python scripts/portfolio_asset_bridge.py INPUT.json --out NEW.json`。输入同日CNY基金快照，含 `asOf/currency/assets`，每只基金需唯一六位代码、`reportDate/currency/weight`，股票、债券、银行及备付金、其他资产、总资产、负债和净资产金额（十进制字符串）；空金额保留null并用 `missingReasons` 说明。附来源PDF路径、SHA256与资产/余额表物理页。入口核金额加总、净资产及权重，复查来源哈希，不重解析原文；类别全缺失保持null，部分缺失仅合计已知金额。总资产比与净资产比分开，银行备付金不作可用现金证明。

资产组合表跨页时，可补 `assetPages`（唯一递增物理页数组，首项等于 `assetPage`）；底稿保留全部所用页，不能只引用首个标题页。510880官方中报第39—40页资产表、第15页负债与净资产已作真实样本桥接；金额核对仍不认证实际可用现金或所有负债性质。

## 证券重叠与发行人风险分开核对

代码重叠只回答是否持有同一证券。涉及A/H股或跨市场同名证券时，先从公司正式披露的股票简况、上市资料核实发行人及市场；保留原文日期、物理页和文件哈希。名称相同仅作为检索候选，不能直接合并。港股补足五位须以已确认的市场为前提，不能对所有代码全局补零。

需要汇总主体暴露时，逐基金计算：该发行人各证券的人民币市值合计 ÷ 该基金净资产 × 该基金组合权重，再加总各基金贡献。保留每行证券、市场、原币种/换算依据和各自分母；不同基金原比例不能不加权直接相加。披露金额已为人民币时不重复换汇。证券交易身份、价格及流动性仍分别保留，主体风险合并不生成一个可交易证券。

交付先说明核实了哪些关系、暴露意味着什么，再列尚未核实的关系及影响。历史身份文件与当期持仓的日期分开，未确认期间变更时标注缺口。未检出仅限定于已解析披露表，不自动当作完整主体持仓为零；部分关系已核不能输出全池主体排名或完整集中度判断。

示例：两基金各50%时，同一发行人在A基金占净资产8%、在B基金占2%，组合主体暴露为5%，不是10%。这是静态研究权重；没有当期净资产、可比币种或正式身份依据时，只列待核关系，不能补造比例。

此步骤复用已取得持仓、原文核验、计算及结论绑定，尚无自动全市场发行人映射入口。按具体研究准备并核实映射，不把说明当作已实现的自动功能。


### 标题与比例分母冲突

官方产品页也可能存在标题与比例口径不一致。取得持仓金额、基金净资产及总资产后，分别复算并对照原报告的表头；显式列出两种分母的结果与来源，不静默选择或混合相加。整只基金A+C合计持仓使用对应合计净资产，不能除以单一份额规模。网页只取得选定内容时说明范围，不能当成完整响应认证。境内行业分类与港股GICS分别记录；没有明确映射不合并为细分行业敞口。


持仓原文重验命令中的 `holdingsPath` 和 `reportPaths` 相对路径按任务输入JSON所在目录解析；报告记录里的 `documentPath` 按该记录所在目录解析。绝对路径保持原样。命令从其他目录启动仍可找到随附资料，之后仍会核对PDF哈希并重新解析股票明细；路径成功不代替来源与判断验收。


### 选定QDII美股指数持仓九列表

`python scripts/qdii_us_holdings.py INPUT.json --out NEW_RESULT.json`。输入给 `path`（相对输入文件）、`sha256`、`code`、`reportDate`、连续 `holdingsPages`；`navEvidence`、`equityEvidence` 分别给物理 `page`、原行 `quote` 与金额 `value`。当前限明确自然年中报7.4.1指数权益九列、7.4.2结束边界及人民币元表头；只接受US当地证券代码，其他市场或版式不强行转换。

入口核封面、代码、结构、章节坐标，保留同序号多证券与原代码单元格，逐行核净资产比例、连续序号和权益合计。续名碎片保留，不自动补全法律主体；报告序号组数不叫发行人数量。公允价值闭合不代表债券、基金、衍生品名义敞口或完整组合风险已核。输出必须新建，不覆盖原件、输入或旧结果。

九列表结果补充：`reportedGroups` 按原表序号合并同组证券金额并保留代码列表，核对金额递减及组内名称一致；`firstTenReportedGroupsToNetPct` 为前十报告组对净资产的比例，不叫已认证前十大法律发行人集中度。碎片名称及公司主体关系仍待核，不能由序号数量直接评价法律主体分散。


九列表最小示例见[513100中报输入](examples/qdii-us-holdings-513100.json)。将输入复制到新研究目录，旁边放与示例哈希一致的管理人中报 `fund-report.pdf`；不附带或重新分发原件。调用 `python scripts/qdii_us_holdings.py RESEARCH_DIR/input.json --out RESEARCH_DIR/new-result.json`。本例应返回102证券、101报告序号组、权益合计17,686,928,778.66元及前十报告组约43.47%，同时保留碎片与范围限制。更换文件或基金必须重新核原页和参数，不只换代码沿用金额；失败检查退出状态，不继续引用旧结果。

披露利率情景入口可选parentWeightEvidence，含reportDate（与子报告同日）、holdingAmountCNY、parentNetAssetsCNY、path、sha256及locators[{page,quote,field}]；field分别为holdingAmountCNY和parentNetAssetsCNY。程序重新定位两项金额并复算权重，缺证据时仅标输入声明；报告身份、币种单位适用范围仍须独立核对。冲击参数只有在同一金额引句明确利率方向及百分比/基点时标原句定位与单位换算，不认证经济模型或整体FOF压力。

## 配置候选与现金流复盘

方法、上下限、类别约束、收缩及接续方式统一见[配置候选研究](portfolio-allocation.md)；账户出入金与TWR/XIRR见[现金流收益观察](portfolio-cashflow-review.md)。不把配置候选与完整交易回测混为一体。
