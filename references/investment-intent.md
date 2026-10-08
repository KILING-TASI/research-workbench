# 资金用途与组合约束

用户明确资金用途、用钱日期、最低现金预留与可接受阈值后，AI整理输入，运行：

`python scripts/investment_intent.py INPUT.json --out-dir NEW_DIR`

必需顶层：asOf、intent、holdings。intent含id、purpose、currency、targetDate、allowedAssetClasses、minimumCash、maximumAssetWeightPct；可选maximumStressLossPct。阈值由用户明确提供，不按年龄或聊天推断。

持仓含assetId、assetClass、currency、marketValue；可附valuationDate、availableBy。只接受正向、无杠杆市值，同一意图内同一资产先合并；多账户或多意图不能直接混算。cash专指输入确认的现金类，基金或现金管理产品不自动当作立即可用现金。

cashNeeds为date、amount列表；日期在研究日至目标日内。需求累计计算并保留最低现金。变现时间未提供时保持未知，不填零。availableBy是用户提供的假设，不保证到账；当前市值不含变现折价、成本和税费。

scenarios为name及returnShocksPct对象，键为assetId。缺冲击不能算完整损失，单次冲击不是未来最大回撤；无情景而设置风险阈值时明确资料不足。禁止自动提供预期收益。

完整教学输入与边界案例由脚本test_investment_intent.py验证；输入金额、日期采用明确值。结果为constraints-not-met、needs-data或supplied-checks-met，分别表示存在约束失败、资料不足或所给检查项满足。任何结果都不是投资批准、适当性认证或订单。输出HTML/Markdown/JSON且保留输入摘要，目录需为新目录。

币种混合需在上游明确汇率来源和时点；本入口拒绝静默转换。直接发行人检查见下节；行业穿透、杠杆、真实交易费用及审批身份尚未覆盖。这些缺口不能由阈值检查通过掩盖。

## 接入已有组合压力输入

`python scripts/investment_intent.py INTENT.json --portfolio-input PORTFOLIO.json --out-dir NEW_DIR`

PORTFOLIO.json采用portfolio_stress.py原始输入（asOf、baseCurrency、holdings、scenarios），不是旧结果文件。意图输入提供stressCodeMap，将每个组合code明确对应一个assetId，完整一对一；截止日、币种和逐项市值必须一致。已有意图scenarios不允许静默覆盖，需分别运行比较。

入口重新运行现有压力模型，记录双方输入摘要、映射及模型结果，再核对用户的压力损失阈值。冲击未覆盖的资产保持未知，历史样本不足不冒充稳定相关性。当前桥接仅支持该压力模型输入，不代表所有组合模型自动接通。

## 估值快照时效

intent可提供maximumValuationAgeDays（非负整数，自然日）。阈值由用户明确设置，不能由AI替用户设置。估值日期至asOf间隔超阈值时，标记过期及资料不足；日期缺失或时效阈值未指定时也不能认定快照足够新。旧金额仅供旧快照计算，报告要求刷新后重查，不能包装为当前价格。

未指定maximumStressLossPct时风险预算检查为未知。更新模型后旧研究包方法摘要变化会要求另存新版验收，不覆盖历史结果。已有完整满足约束的教学输入需显式提供时效阈值；仍不代表投资审批。

## 压力后资金用途覆盖

完整冲击情景不仅检查损失比例，还逐个资金需求日核对冲击后的可用市值与累计支出及现金预留。假设冲击在用钱前一次发生且之后不恢复；它不是价格路径预测。可用日期仍采用输入声明，不加入默认变现保证。

同一持仓的资金不能在多个需求日重复分配：需求累加。未知变现日期且已明确金额不足时列资料不足；已知不能及时变现时列约束不满足。压力预算满足不保证资金用途可完成。额外赎回延迟与变现扣减可按下节明确输入；未提供时不假设已完整覆盖。资金流入和实际税费仍需后续扩展。

## 情景变现延迟与扣减

每个scenario可提供liquidationAdjustments，按assetId给出availableBy（到账日期，null表示未知）和deductionPct（冲击后市值再扣减0至100%）。扣减为明确输入的综合折价/费用情景，不自动读取实际费率，也不要与价格冲击重复表达同一损失。例：原值70、价格冲击-10%、再扣减10%，可用金额为56.7。

情景到账日期覆盖正常availableBy；现金也可指定冻结后到账，不能因资产类型是cash而忽略延迟。未知到账日期保留未知。未提供额外变现条件时沿用已声明日期和零额外扣减，报告明确未含压力延迟/折价，不称为完整极端流动性模型。

桥接原始组合输入时，可在意图的scenarioLiquidity中按唯一情景名称填相同assetId条件。名称未知或不唯一拒绝联动。压力损失预算仍检查市值冲击，资金覆盖另外计入变现扣减，二者分开解释。


## 发行人合并约束

可设置 intent.maximumIssuerWeightPct，并提供 issuerRelations 列表，每项 assetId、issuerId、source、publishedAt、acquiredAt，可选 applicableUntil。股票stock、债券bond、转债convertible按直接发行人合并占全组合比例。关系晚取得或过期不采用，缺关系保留未知。基金管理人不等于底层发行人，不支持以此代替持仓穿透。现金银行及担保、控制链尚未覆盖；有未知部分时，已知部分未超限不代表全组合通过。所有关系来源为输入声明，仍需原文核验。


发行人关系可选 locator（path、sha256、page、quote），检查PDF和引句位置。引句未找到时关系不参与合并；未提供定位仍明确标作输入声明。定位成功不认证关系语义。可按买方研究包规范显式归档原件；未归档仍依赖外部路径，移动或删除原件可能导致重算失败。

发行人结果分别列关联市值覆盖与三层原文覆盖：引句定位、仅文件页码、未定位声明。全部按全组合市值为分母；排除关系归入未知部分。关联100%不等于原文核验100%，定位也不认证关系语义。

已知发行人另列直接证券占比上界：假设全部未归属股票、债券、转债归于该发行人。各发行人上界互斥不能相加，不是置信区间或实际归属；基金底层、现金银行及其他间接暴露不纳入此界限。即使直接证券上界未超限，其他未知范围仍保留未知，不把它转为全组合通过。


关系可显式填写 relationRole="issuer"，受托管理人trustee、承销商underwriter及担保人不能用于直接发行人归属。兼容旧输入时角色默认仍属用户声明，不会从PDF首页公司名自动推定发行人；须人工核对发行概况和角色上下文。


发行人关系支持 effectiveAt、withdrawnAt、supersededAt/supersededBy；未生效或失效关系不参与当前归属。报告给出已知市值覆盖和未知金额，覆盖比例不是准确率。日期均为输入声明，关系的法定生效和版本替代需另行原文核验。


## 多资金用途分组

用户明确每个用途的金额分配时，运行 `python scripts/multi_intent.py INPUT.json --out-dir NEW_DIR`。顶层 asOf、currency、holdings 为原始市值；intents 列表每项包含完整 intent 参数、allocations（assetId、marketValue）、可选 cashNeeds 和 scenarios。同一资产可拆分，但跨用途合计不得超过原始市值；每用途资产不可重复。支持顶层 issuerRelations 按用途资产关联。未分配余额单列，不自动借给其他用途；缺阈值或情景仍按单用途规则保留未知。只按用户给定方案研究，不自动优化分配，不构成交易。


多用途入口现保存 input.json、result.json、自然语言报告与 manifest.json。复算：`python scripts/multi_intent.py PACKAGE_DIR --replay`。同版本核对原输入与结果；文件变化、缺失、方法变化拒绝。本地摘要不是数字签名；原文迁移按下述显式归档方式执行。


多用途报告开头列出约束不满足和资料不足的用途；明细随后展开。分组前检查顶层关系的资产引用和唯一性，不把未知关系静默过滤。未分配资产不代表已做完整研究或关系语义核验。

各用途单独展示发行人合并、未归属金额与原文定位层次。比例以该用途分配金额为分母，不是全账户暴露；失效关系原因保留，不将原文附件存在当作关系语义认证。


多用途包可用 `--include-originals` 显式归档发行人PDF；relation-attachments.json保存逐资产覆盖，相同PDF按哈希去重。包移动后从内部附件重查与重算；没有归档时仍依赖外部原件，无定位关系列缺口。原文归档不授予再分发权。


多用途可提供顶层 sharedScenarios（非空列表，唯一 name、returnShocksPct，可选 liquidationAdjustments），统一市场冲击按用途已分配资产过滤，缺冲击保持未知。未知原始资产与非法冲击拒绝；不得同时填写用途自有scenarios以避免静默覆盖。报告区分共同情景和独立假设，一次冲击不代表未来最大回撤，未分配余额不自动挪用。
