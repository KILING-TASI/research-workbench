# 首次预测、历史回放与实际复盘

scripts/prediction_review.py freeze|replay|review|compare 输入.json --workspace 用户目录 --out 新结果.json。不刷新旧模型，不调参或自动替换。

来源偏差记分卡使用scorecard子命令，输入reviews为已保存复盘JSON路径列表（1至500份）。只纳入first-live-capture、eligibleForFrozenComparison=true且evidenceGrade为原文实际率数值匹配的档案；回放、未匹配实际值单列排除，同来源版本/标的/截止时点重复拒绝。逐情景输出有符号百分比偏差、平均绝对误差、RMSE、样本标准差及n；n<5仅描述小样本，不计算融合权重或宣称预测校准。评分目标为比例百股资金，不是余股最低获配资金；情景标签不是概率分位。

freeze输入modelVersion、decisionCutoff（带时区的申购日截止时间）、allocation（第二批single输入）、inputs。inputs项path、availableAt、retrievedAt（带时区）、可选sourceUrl/sha256。程序以实际执行时钟记录recordedAt，拒绝截止时点之后冻结及未来可得/抓取时间；复制原输入文件与哈希、代码版本、计算结果。来源可得时间由调用者提供，未自动证明发布时间或原文已核验。

首次预测存research-data/bjx-predictions/frozen/模型版本/代码/first.json。同模型同代码只保留首次，相同输入返回原记录，变更拒绝；新版本单独保存。未来真实样本才能形成实时捕获，不能补造历史recordedAt；本地时钟、哈希不是外部可信时间戳。复制文件不保证包含全部研究输入，宿主需提供完整输入清单。

replay沿用相同输入，允许当前抓取历史修订资料，但availableAt不得晚于决策截止日，显示retrospectiveCopy；存独立replays目录且永不升级为首次冻结预测。后续不能使用目标实际率作为预测输入，数据来源内容是否含未来信息还需外部核验，程序仅检查声明时间。

review输入predictionPath及actual：code、publishedAt（带时区、不得在未来且必须晚于决策截止）、ratePct、sourcePath。可加factsStore：按实际公布日期读取第一批实际配售率，比对率值与原PDF哈希，核验等级为原文率匹配，时间仍是输入声明。实际率只计算核验目标，不回写预测。复盘文件追加保存至research-data/bjx-reviews，预测档案和输入先核验哈希。

逐档输出资金绝对误差、绝对百分比误差、低估标记、配售率百分点误差、整手获配偏差及实际条件门槛可达性。门槛是按实际配售率计算的整手条件门槛，不是包含零股竞争的真实最低获配资金。

可提供allocatedShares：账户实际获配整手，与预测整手比较，零股差异不自动归因为模型错误。cashflows为date/amount/kind（subscription/refund/settlement/fees/financing），金额有符号、统一人民币。cashflowsComplete须布尔值；不完整流水不算最终收益误差，完整时对照情景净利润，但完整性是用户声明且账单未核验。避免费用重复进入结算与单独费用流水。

compare输入before/after两个复盘文件路径数组。仅首次实时捕获记录，按代码与decisionCutoff交集，要求同实际率与发行价，三档数据完整；各组仅一个模型版本，重复样本拒绝。输出共同覆盖MAE（元）、平均绝对百分比误差、最近秩P90/最大金额误差、低估比例、剔除和未配对数量。历史回放单独复盘，不混入成绩。收益概率、因果归因和策略有效性未由这些指标证明。

automaticReplacement永远false：均值改善不足以替换，需更充分的共同样本、尾部风险、来源及时间证据复核。当前未实施训练集/样本外划分自动选参，不声称已有模型获得新改善。

当前验收没有新增真实事前冻结样本，无法证明模型预测能力改善。现阶段复盘仅用于记录偏差，不作为模型调优或效果宣称依据。MAE不是准确率，不能用100%减误差来宣传准确率；展示同时报告样本数、单位、共同覆盖范围、回放/真实冻结分类与来源核验等级。

关键数值留痕按evidence-chain.md解释；原文核验等级和时间可得等级分别保留。

余股分支与实际目标分离：review用实际配售率复算比例百股门槛时移除预测的additionalSharesAssumptions，不能把假设余股当作实际率条件。账户allocatedShares独立记录；新增actualVsDeclaredAllocationAssumption对照含声明余股的预测合计，旧档案没有合计字段则留空，不补造。
