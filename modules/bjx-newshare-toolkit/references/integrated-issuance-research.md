# 北交所完整研究流程

统一入口：scripts/issuance_research.py run 输入.json --workspace 用户目录 --out 新结果.json。按实际提供的模块执行，不要求每次填完整表格；宿主从用户问题识别所需模块、复用已核验资料，只有影响结果的未知输入才询问。不要把JSON配置表交给普通用户反复填写。

单项入口为panel/rates/structure/timeline/rules/cash/counterfactual/matched-review，输入均为JSON；统一run输出证据、冲突、查询面板、选定计算模块及缺失模块。原来的取数、PDF核验、company_research和prediction_review命令保留。该入口不自动下载任意新股全部资料，不连接账户，不恢复工作台，不训练旧模型。

## 新版十二项功能的接入

| 设计功能 | 实现与输出 |
| --- | --- |
| 发行事实证据面板 | panel按字段返回值、单位、候选原文、核验状态和是否实际用于计算 |
| 配售率证据等级 | rates逐档核对A/B/C/D及依据，D阻止计算，A/B阻止进入predecision目标情景 |
| 冻结时点预测快照 | 原prediction_review.freeze保留首次预测；统一run可生成截止前研究包，二者性质分开 |
| 配售率情景传导 | rates调用整手、百股门槛、边际档位、上限及现金成本计算，三档名称不证明统计分位 |
| 现金时间账 | cash逐自然日显示期初/期末现金、日内缺口、占用本金和各项收支 |
| 规则变化影响隔离 | rules保存披露/生效日期、参数差异、影响字段及待核验状态，不自动切换计算规则 |
| 反事实复盘 | counterfactual从显式基线或原首次预测读取，一次只替换一个输入，返回三档指标差额 |
| 证据质量评分 | panel提供查询字段覆盖率、原文数值匹配率、冲突/缺失数和版本新鲜度限制，无投资综合分 |
| 发行口径转换器 | structure区分绿鞋前、假设全额行使和实际增发，勾稽股本及PE，购回不算新增股份 |
| 战配与绿鞋时间线 | timeline保存有证据引用的战配限售、延期交付、稳定期、实施等事件，未知日期留空 |
| 财务质量证据卡 | companyCards复用已核验财务数值、现金流信号及缺口，审计意见/追溯调整未抽取时明确未知 |
| 同行可比口径卡 | companyCards返回同年度扣非合并口径同行及排除理由，同行不足不输出相对结论 |

## 配置与边界

run必填code/asOf；evidence采用research_evidence.export的factsStore/code/asOf、companyResult及nodes格式。所有已声明披露日期不得晚于截止日，研究主体须与公司及获配输入一致。证据等级沿用原文匹配状态，不把“链接在官网域名”当线上文件认证。规则适用性仍需复核。

allocationResearch包含allocation（原single参数）和rateEvidence，每档对应一个声明：

- A：grade/value/basis/evidenceIds；引用同标的原文ratePct百分数证据，数值必须一致，仅事后事实核验。
- B：grade/basis/onlineShares/validSubscriptionShares/onlineEvidenceIds/totalEvidenceIds；明确onlineBasis与totalBasis（须分别与证据一致），网上发行量和有效申购总量都为正式原文股数。按网上量/有效申购量*100推算，非超额申购不套此公式；不是零股获配概率。
- C：grade/value/basis，明确用户假设；可选假设或第三方来源节点，不能冒充已核验结果。
- D：grade即可；返回blocked-missing-rate，门槛和获配结果为空，不补默认值。

purpose=predecision阻止A/B作为本次目标实际率输入。scenario为给定条件计算；截止日前已知的历史实际率也不能混入目标实际结果而冒充预测。完整内容前视风险不能只靠声明日期自动识别。

structure字段price/preIssueShares/postIssueSharesBefore/initialIssueShares/initialOnlineShares/strategicShares/overallocatedShares/actualNewShares/actualRepurchasedShares/adjustedProfit为对象，包含value/unit/kind及evidenceIds或明确假设basis。价格元/股、利润CNY、股数股。原文扣非利润必须有唯一年度，与profitPeriod一致。发行前股本可由原文发行后股本减初始发行量推导；实际增发与实际购回同时给出时合计须解释超额配售量。overallotmentDestination=online才输出初始网上量加超额配售量。不内置默认15%或默认战配比例；全额行使情景不等于实际实施。

timeline.events每项id/subject/type/evidenceIds，可选date/conditions；日期未知仍保存待核验事件，条件日期不伪称确定实施日。锁定期、延期交付和实施结果由宿主先逐项原文核验、再映射，程序不自动理解任意公告全部事件，不按默认月份算解禁日期。

rules.versions每项id/evidenceIds/parameters、可选publishedAt/effectiveDate/reviewed。缺日期或缺原文引用时为pending-applicability；reviewed是人工适用性声明，不是自动法律认证。before/after比较参数，impactMap指明受影响字段，selected选择待研究版本。发布未生效的版本不能标为当前适用；差异永不自动改旧计算。研究公式未核对适用规则时，run显示not-confirmed-conditional-formula-only。

cash采用原collision参数，每只issue另需三档rateEvidence。refundAvailableDate表示用户提供、且不早于公告退款日期的可用日，需availabilityEvidenceIds；未提供时只有公告日期情景，不能宣称券商已到账。sameDayReleasedFundsUsable=true还需sameDayAvailabilityEvidenceIds及sameDayRuleReviewed=true；默认同日先申购后释放。每日账最多3660自然日，涨跌幅和费用仍是假设，不预测交易收益。

counterfactual可用baseline或predictionPath（二者不能同时存在），changes每项field/value/category/evidenceIds。支持价格、上限、预算、日期和单档配售率；category为input/scope/rule/correction/calculation，仅是声明分类。档案来源校验原首次文件及归档输入哈希，原事实值从冻结结果读取，不回读后来更新的事实库覆盖基线。单因子变化不证明因果，非线性取整使差异不可直接相加；规则变化需显式传入受影响参数。

matched-review的before/after为对象数组，每项reviewPath/predictionPath/packagePath。先检查原复盘和首次档案哈希、冻结输入、截止前包、已打包的comparisonScope及已复核规则；要求研究输入在原预测输入清单。共同样本还须规则文件哈希和比较口径一致，才交由旧compare统计三档MAE、P90、最大误差、低估比例。排除项逐条留原因。无真实共同样本时指标为空，不把合成测试或历史回放当改善证据。

## 自动研究快照

run的snapshot包含mode、可选decisionCutoff/availabilityBySha256/dependencies。自动归档研究输入、结果、计算代码、原PDF与披露目录、使用的事实版本；规则原文/规则配置通过dependencies明确给出role=rule。快照保留代码文件哈希，规则索引也可归档但仍标明“非完整规则原文”。涉及predictionPath时归档预测记录及其输入。其他外部资料由宿主明确声明，不能声称任意依赖都自动发现。

mode为research/historical-replay/predecision。predecision须执行时在截止前，每项原始资料需可得时间声明；本地生成结果及代码使用本地记录时点，输入文件和原资料不能从目录时间猜测首次公开时间。快照不是可信时间戳，eligibleForModelImprovement始终false；生成研究包不自动成为真实预测样本。失败不覆盖已有包或首次记录。

## 真实验收定位

当前端到端真实材料是世昌股份920022的发行公告、结果公告和招股书；其他规则变更、延后到账、危机场景、缺失门禁及共同样本检查另用合成测试。原文采集覆盖不等于全市场验收。真实事前冻结样本、真实账户流水、战配逐主体解禁日期和绿鞋最终实施结果仍需后续资料，不能用代码通过代替这些验收。
