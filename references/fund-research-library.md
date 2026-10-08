# 基金池、归因与资料档案

AI从自然语言提取对象、报告期、区间、资金权重和用户评分偏好。缺少关键参数时询问，不能要求用户填写JSON。以下参数由AI整理；直接聊天即可使用。

## 路由与调用

在Skill目录执行，INPUT.json由AI生成，NEW.json必须不存在；用户资料目录由用户指定或使用其既有研究目录。

```text
python scripts/research_library.py brinson INPUT.json --out NEW.json
python scripts/research_library.py pool INPUT.json --store USER_DATA --out NEW.json
python scripts/research_library.py score INPUT.json --out NEW.json
python scripts/research_library.py reverse INPUT.json --out NEW.json
python scripts/research_library.py documents INPUT.json --out NEW.json
python scripts/research_library.py archive INPUT.json --store USER_DATA --out NEW.json
node scripts/fund_research.js contributions INPUT.json NEW.json
```

## 最小示例：建立观察池

用户：“把110011、000311加入观察池，按回撤40%、夏普60%评分。”先保存成员和评分偏好：

```json
{"name":"观察池","add":["110011","000311"],"scoreModel":[{"metric":"maximumDrawdownPct","direction":"lower","weight":0.4},{"metric":"Sharpe","direction":"higher","weight":0.6}]}
```

执行pool命令得到fund-pool结果，包含name、revision、codes、scoreModel。评分再调用score：输入pool为上述结果；comparisonScope为共同日期窗口，comparisonGroup为经确认的可比风格；rows每项包含code、相同comparisonScope/comparisonGroup、sourceUrl及metrics。用compare已取得的同区间指标填充，不凭名称认定同风格。缺指标或组别不同的成员列入excluded。池内完整样本按min-max标准化后加权，无差异指标50分；不将评分称为买入排序。新增/移除成员分别用add/remove，版本追加不覆盖。

## Brinson单期披露快照归因

输入start/end/asOf/weightDate，basis为disclosed-snapshot-estimate或period-start-holdings；industrySystem明确版本，returnBasis为total-return。sectors每项包含industry、portfolioWeight、benchmarkWeight（0至1）、portfolioReturnPct、benchmarkReturnPct（百分数）、sourceUrl。两组权重分别合计1，现金/未知部分不能删掉后冒称全基金。可另传actualPortfolioReturnPct，实际与快照差额单列。

示例输入（仅演示公式，不是证券数据）：

```json
{"start":"2026-01-01","end":"2026-03-31","asOf":"2026-04-30","weightDate":"2025-12-31","basis":"disclosed-snapshot-estimate","industrySystem":"示例分类","returnBasis":"total-return","sectors":[{"industry":"A","portfolioWeight":0.6,"benchmarkWeight":0.4,"portfolioReturnPct":12,"benchmarkReturnPct":10,"sourceUrl":"https://example.org/A"},{"industry":"B","portfolioWeight":0.4,"benchmarkWeight":0.6,"portfolioReturnPct":0,"benchmarkReturnPct":-5,"sourceUrl":"https://example.org/B"}]}
```

输出快照组合收益7.2%、基准1%、超额6.2个百分点，拆成配置3、选择3.8、交互-0.6个百分点；三项与超额核对。单期公式依据[CFA Institute绩效归因综述](https://rpc.cfainstitute.org/sites/default/files/-/media/documents/book/rf-lit-review/2019/rflr-performance-attribution.pdf)。不能用期末持仓解释过去收益；只有前十大时仅分析已披露子组合。选择项不是经理纯alpha，多期贡献不能简单相加冒称复利归因。没有行业收益与期初权重时列待补资料，不声称已完成真实归因。

## 持仓反查

输入asOf、reportDate、target、funds；可传poolCodes、minimumWeight、limit。target证券形如kind=security/market=HKEX/code=01179/shareClass=ordinary，行业形如kind=industry/name=行业名，另给industrySystem。funds沿用holdingsStudy报告结构：id、reportDate、publishedAt、sourceUrl、holdings，并明确weightBasis=fund-nav和disclosureScope=top10|completeEquity|complete；行业查询须各基金industrySystem相同。holdings权重为占基金净资产的小数。

输出matches按披露权重排序、excluded记录范围不符或未知。仅反查已有输入报告及指定池，不能称全市场前20；报告市场身份未解析时不能改写成交易所身份。前十大未命中不证明没有持仓，报告权重不是实时权重。

## 公开文档精读

输入pdf本地路径、sourceUrl、sha256、publishedAt、asOf、identityText及可选keywords。先核对文件哈希、前5页主体与披露日期，再提取原文关键词附近摘录和页码。返回candidates及emptyTextPages。每项status为文字候选，AI需阅读上下文后概括合同限制或经理自述，保留页码、原链接和摘录；目录命中不能当有效条款。扫描页不做内置OCR，未命中不当不存在。pypdf缺失时报告依赖缺口；只处理已获取公开文件，不后台监听。

## 结构化研究档案

archive输入code、tags、userNote、riskLabels、documentSummaries、resultFiles（已有JSON结果路径）。每次追加独立条目，结果按SHA256保存副本，原分析不改写。单一结果明确code时须与主体一致。用户笔记与工具结果分开；摘要保留原文来源及页码，不把用户标签当买卖指令。本地资料需用户备份，不承诺永久在线保存。

## 跨资产贡献

contributions输入historyInput（与compare同一历史序列规范）及weights（每项代码、非负小数、合计1）。输出各资产累计收益贡献、波动风险贡献/占比，以及组合最大回撤同一峰谷区间的资产贡献。基于共同观察日期、每期恢复权重、零成本假设。收益贡献考虑复利财富路径；风险贡献采用协方差Euler分解，可以为负；零波动时占比为空。回撤贡献不能把各资产自身最大回撤加权求和。不是行业贝塔/选股回撤归因，也不代表未来风险预算。

## 错误与输出

输入日期、主体、权重、来源或口径不一致则停止该计算，指出缺项；未知不补零。输出已存在则换新文件名，不覆盖历史。最终用户答复前置简短风险提示，展示结论、分项表、区间与来源、未知与假设；不倾倒JSON或执行字段。没有必要数据时先给资料缺口，不能靠情景数字冒充实测。

多期 attribution_link 输入每期单独声明 industryVersion，并保持一致；与行业分类名称industrySystem分别核对。版本不一致拒绝链接；未声明版本保留可比性缺口。旧输入不因名称相同而获得版本一致结论，代数勾稽通过不代表分类版本或原始持仓已核验。

基准状态须区分：原文明确未设定（explicitly-not-defined）、公式已定位但未验证（formula-located-not-verified）、原文冲突、未定位。可将已取得的pages传入report_benchmark_status.inspect定位原文，不能将未设基准记为网络失败，也不能自动套用指数。用户自定义对照须另标非合同基准；段落定位不证明法律文件版本有效。


多期归因可使用 `python scripts/attribution_link.py input.json --out result.json --report report.md` 导出自然语言简报。简报显示逐期链接贡献、登记来源和可比性缺口；声明缺失时不将代数结果称为完整归因，输出文件须为新路径。


单期与多期归因支持可选 `weightPublishedAt`（持仓报告披露日）。未知日期不能证明事前可得；起点同日缺少时刻时不确认事前可得；起点后披露只供事后解释。晚于研究截止日、早于持仓快照日均拒绝。自然语言多期简报逐期提示资料时间边界。


组合日频年化先筛查日期间隔：中位间隔超过3日或最长间隔超过14日时拒绝按252期年化，提示补齐资料或重新声明实际频率。间隔筛查通过不代表交易日历完整性已核验；法定长假仍需人工核查。


组合贡献输出逐资产资料可得日、分红拆分核验声明与缺口，综合报告同步列出缺口。未来可得日拒绝计算；未登记不视为当时可得。分红核验布尔声明只代表输入声明，不代替独立原文审计。

行业口径：直接brinson调用也必须提供industryVersion，声明适用于全部行业行；行内另有版本时必须一致。缺失/冲突拒绝归因。行业持仓反查须同时指定industrySystem和industryVersion，输入基金版本不同或未知时单列排除，不视为无持仓。分类声明仍须有原文依据，填写版本不代替核验。
