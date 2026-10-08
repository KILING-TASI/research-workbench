# 持仓双口径、相似基金与综合报告

用户直接提问，AI整理参数并按需取得资料，不要求用户挑技术模块。先使用检索/采集与原文解析流程准备输入，已有资料复用；不宣称所有基金均有完整数据。最终输出客观结果、来源和缺项，不展示执行细节。

## 调用

```text
node scripts/fund_diagnostics.js overlap INPUT.json NEW.json
node scripts/fund_diagnostics.js similar INPUT.json NEW.json
node scripts/fund_diagnostics.js report INPUT.json NEW.json
python scripts/attribution_link.py INPUT.json --out NEW.json
```

overlap沿用research_analytics holdingsStudy完整输入：asOf、currency、industrySystem、industryVersion、funds；每项id、allocation合计1、currency、reportDate、publishedAt、sourceUrl、locator、disclosureScope、equityWeight、holdings。证券须market/code/shareClass/name/weight，权重占净资产的小数。有金额优先金额勾稽。ETF或FOF需先用现有穿透流程取得底层，不能把基金代码当股票代码。

两两净资产重叠为共同证券min(wA,wB)之和；已披露股票结构重叠为min(wA/已披露A,wB/已披露B)之和。不将第二项解释为全基金重合。HHI分别给净资产平方和与已披露股票内部归一化平方和；有效持股数=1/归一化HHI。未披露权益和非权益分别保留；不同报告期重叠留空。共同证券列出所属基金及组合暴露，前十大/其他披露分段沿用底层结果。

similar输入targetCode与holdingsInput。同一报告期的池内成员按已披露股票结构相似度排序，返回净资产重叠、报告覆盖和来源。仅持仓相似，不是风格/行业综合相似，不是替代品买入建议，不作全市场搜索。

report输入title、asOf、subjectCodes，可选historyInput（compare历史输入）、holdingsInput、weights（组合贡献权重）。示例：用户问“比较110011与000311，看看业绩、持仓重叠和组合风险”。AI复用两只基金相同截止日历史和持仓输入，组装上述字段，调用report。输出JSON和同名.json.md简报。历史、双口径持仓、组合贡献自动计算；本次问题要求但资料不足的维度列为缺口；未请求且未取得的经理观点、分类变化或归因列为未评价，不默认要求补齐，不虚构完整评级。历史参考基准在historyInput.reference声明；无基准不称跑赢合同基准。主体和截止日冲突拒绝；报告期冲突隔离。综合报告并非通用联网问答后台。 AI按本次问题可在requiredDepthTypes声明manager-public-passages、disclosed-category-change或brinson-fachler-single-period；默认空列表，用户不需填写此参数。该声明仅决定哪些专项必须列缺口，不自动执行取数。提供已有fund-evidence-package时，其结论与逐条局限先于指标表展示；未提供时仅交付资料汇总，研究评价仍需AI基于实际证据完成。

## 多期归因

输入asOf及periods，每期是fund-research-library.md的brinson输入。起止日期按净值端点连续相接（下一期start=上一期end），分类和总收益口径一致；每期权重日期不得晚于期初。股票子组合归因不得冒称整基金。

链接系数=此前各期组合财富因子乘积×此后各期基准财富因子乘积；每期各项贡献乘该系数后汇总。这是明确的顺序望远镜恒等式，使三项贡献与累计快照组合收益减累计基准收益勾稽；不是GRAP或唯一归因方法，分项结果依链接方法而异。每期来源与实际-vs快照残差保留，不还原真实交易。累计口径依据[CFA归因综述](https://rpc.cfainstitute.org/sites/default/files/-/media/documents/book/rf-lit-review/2019/rflr-performance-attribution.pdf)对复利与算术贡献差异的说明；本链接恒等式独立勾稽，不声称论文指定实现。

## 失败处理

缺权重/历史/报告先列待补资料，不补零。报告拒绝主体、日期或权重冲突；输出不覆盖已有文件。资料范围内能计算的部分可单独输出。没有盘中行情与完整披露，不估算实时完整净值；不从快照认定真实交易、择时或隐形交易能力。

## 综合评价与阶段复盘报告呈现

生成综合研究JSON后执行：

```text
node scripts/fund_report_presentation.js RESULT.json NEW.html
```

输出独立HTML，可直接阅读或浏览器打印。结构依次为核心观点、共同区间业绩、持仓重叠与覆盖、组合贡献、风格/行业/经理观点资料状态、阶段复盘、风险与来源。仅借鉴机构报告的论证结构，独立排版，不复制券商标识、正文或评级。报告中的核心观点由本次数字生成，不输出买入评级。

当前模板使用已计算历史和持仓结果。没有行业归因、观点和交易记录时说明缺项；复盘不编造事前预测。未来接入对应证据时，应扩展结构化输入与校验后展示，不能仅修改缺项文字。综合研究中的完整精度保留，报告显示两位小数。它是报告输出，不重建工作台入口。

多期输入每期可声明 benchmarkId、portfolioId、weightScope、currency。任一字段跨期不同即阻断合并；未完整声明时，comparabilityStatus 为 incomplete-declarations，并逐项列出缺口。完整一致只代表输入声明一致，不代表基准身份、范围或来源已外部核验。不能将权益子组合归因冒充全基金归因。

双口径计算记录附带已披露权重分母、共同证券输入、公式和报告期是否一致。集中度记录逐证券权重、净资产分母1、已披露权重总和与三项公式。供复算使用，不代表原文已核验；不同报告期不输出可比重叠值。

## 已取得报告的持仓复核衔接

`python scripts/holdings_snapshot_review.py INPUT.json --out-dir NEW_DIR --node NODE_PATH`。输入 holdingsPath（双口径输入文件）、reportPaths（基金代码到 fund_report_archive 结果文件的映射）。重新核对PDF哈希、身份、股票表及分母，再运行双口径计算；修改后的持仓输入不能沿用旧核验标签。源PDF缺失或股票明细不同即停止，输出目录不会创建。配置权重仍为用户假设，非账户结算；行业未分类不形成行业结论。此入口支持已取得报告，也可由统一 run-template 的 holdings-snapshot-review 调用。

原文持仓复核逐证券比较名称、代码与命名空间、市场声明、股数、金额、权重、页码及分表明细，并比较披露范围与基金份额范围。行业标签和分类版本属于另行提供的研究输入，不因股票原文核验通过自动升级为官方行业核验。

持仓复核交付含自然语言HTML/Markdown、前十条共同证券表与双方净资产权重、股票覆盖及非股票未展开说明。sources/ 保存本次核验PDF副本，sourceFiles 登记相对路径与哈希；分享时连同整个目录移动，不单独发送HTML。PDF不打进独立安装包，行业判断与全部资产穿透仍需单独证据。


证据结论进入综合报告时，复核身份、主体、状态、输入依赖、计算声明和结论分级；缺失、冲突或假设沿依赖传递，不能标成确定计算或原文披露。正文区分披露记录、计算结果、研究估算和暂不判断。此入口检查登记结构，不重验原PDF或实际执行公式；证据包先按fund_evidence.py构建，关键报告结论仍按原文与正文验收。


报告先在目标目录内完成暂存，再独占发布Markdown与JSON，JSON最后发布；重复或竞争输出不覆盖。常规发布失败仅清理本次创建且未被修改的产物，非有限结果写入前拒绝。此方式要求目标文件系统支持同目录硬链接，不承诺断电时两文件整体原子性；无支持时明确失败，不静默降级覆盖。

发布与暂存清理分别报告：成品已经独占保存后，清理失败返回cleanupIssues并提示，不误报成品失败；发布失败仍保留原始异常，附带清理问题。publishResult返回publishedPaths和cleanupIssues。临时目录只清理本次已登记文件，不递归删除。
