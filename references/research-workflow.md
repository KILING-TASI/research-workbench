# 研究上下文、来源链与研究模板

`scripts/research_pipeline.py` 提供上下文及模板入口：`context-create`、`context-revise`、`run-template`、`impact`、`template-diff`。各命令接收一个 JSON 输入文件，`--out` 必须指向新文件；旧上下文、结果与来源快照不覆盖。

先建立参数上下文：

```json
{"sessionId":"study-001","baseCurrency":"CNY","frequency":"trading_day","dividendTreatment":"reinvest","asOf":"2026-10-03","benchmark":null,"riskFreeRate":0.015,"annualization":252,"missingData":"common_dates","timezone":"Asia/Shanghai"}
```

执行：`python scripts/research_pipeline.py --out context.json context-create context-input.json`。修改时使用 `{"previousPath":"context.json","changes":{"asOf":"2026-10-03"}}` 作为 `context-revise` 输入，获得新版本和字段差异。原文件保持可复查。

基金对比模板为 `fund-comparison`：

```json
{"template":"fund-comparison","contextPath":"/absolute/context.json","codes":["110011","000311"],"comparisonGroup":"同类研究池","refresh":false}
```

执行：`python scripts/research_pipeline.py --workspace 用户数据目录 --out result.json run-template template.json`。可选 `bundlePath` 指向已有批量采集结果；没有时自动采集或读取项目缓存。可选 `previousResultPath` 会在新结果中附带旧结果失效检查。模板要求2至10只基金，日度净值、人民币、现金分红再投、共同日期和252交易日年化；比较组由研究者声明，程序尚不能证明两只基金确实同类。基金分红文本无法解析或共同区间不足时显示缺口，不编造收益。

第二条模板为 `portfolio-diagnostic`：`{"template":"portfolio-diagnostic","contextPath":"/absolute/context.json","holdingsPath":"/absolute/portfolio.json"}`。portfolio.json 按已有组合入口提供 holdings 与 shocks。该模板继承上下文中的截止日和基准币种，输出权重、集中度及给定冲击下的一次损益；压力假设不完整时损益留空。来源链保留用户输入文件哈希，明确标为尚未核验账户的假设数据。

结果包含完整上下文、结果与缺口，以及来源链：原输入文件路径和哈希、各基金来源URL、抓取时间、历史序列摘要、每个指标所用的历史摘要、共同区间、函数名、参数与代码文件哈希。来源链证明本次计算使用了哪些本地记录，**不等于第三方数字已经官方原文核验**。抓取晚于研究截止日时明确标为事后研究。

检查已有结论：`{"resultPath":"/absolute/result.json","newContextPath":"/absolute/context-revised.json"}` 用于 `impact`。`replacements` 可把旧输入文件路径映射到新文件，比较哈希。参数、登记的数据文件或代码变化会标记受影响的模板结果；未使用的参数变化仅列出差异。远程网页变化必须先重新采集并登记，程序无法从固定快照自动发现远程修订。对项目模式，来源链登记实际读取的基金数据文件；独立模式登记逐基金缓存文件。

## 统一模板选择

每项 manifest 均须提供 template 与 contextPath。下表列其余主要输入；自然语言问题由AI准备这些字段，不让用户选择技术模板。原文获取与后续复核分开，按专题说明确认全部参数和限制。

| 用户问题 | template | 主要输入 | 说明 |
|---|---|---|---|
| 比较基金收益与风险 | fund-comparison | codes、comparisonGroup；可选 bundlePath | 已有或采集净值，共同窗口与分红口径 |
| 看组合权重与给定冲击 | portfolio-diagnostic | holdingsPath | 一次冲击，不是未来最大回撤 |
| 复核已有公司财报与点评 | company-financial-review | financialResult、originalResult、archives、outDir | 原文字段、累计与单季输入分列 |
| 宏观指标与资产观察 | macro-observation-review | inputPath、outDir | 原始观测、所属期与发布日期分列 |
| 精读报告或政策资料 | report-reading-review | inputPath、outDir | 三层阅读、引用与可比性说明 |
| 英文原文中文译文交付 | report-translation-review | inputPath、outDir | 已解析PDF及AI译段，覆盖检查不等于语义核验 |
| 公司经营与估值情景 | company-scenario-review | inputPath、outDir、mode=forecast/dcf/relative | 显式假设，不是盈利或价格预测 |
| 行业数量或竞争结构 | industry-scenario-review | inputPath、outDir、mode=supply/concentration | 单位与市场范围一致，未知保留 |
| 日期现金流与退出情景 | exit-scenario-review | inputPath、outDir、mode=exit | 费用税收完整时才按规则计算年化 |
| FOF已披露底层暴露 | fof-lookthrough-review | inputPath；可选 outDir | 未取得子报告保留未知敞口 |
| 历史组合模型或危机假设 | portfolio-model-review | inputPath、mode=optimize/simulate/crisis | 总收益与频率一致，模型按需运行 |
| 事件前后行情对照 | event-price-review | inputPath、outDir | 披露时间、共同日期和因果边界 |
| 复核原文股票持仓 | holdings-snapshot-review | inputPath、outDir；可选 node | 披露期、身份、明细及合计核对 |
| ETF收盘价与单位净值对照 | etf-closing-premium-review | inputPath、outDir | 收盘口径，不是盘中IOPV |
| 组合收益与风险贡献 | portfolio-contribution-review | inputPath；可选 node | 输入含 historyInput 与 weights，简报另行导出 |

ETF收盘对照与组合贡献已接通相应统一模板；不由此推导全部ETF数据域已接通。FOF自动关联取报及债券专门计算仍按专题入口调用，不由基金对比或基础组合模板自动触发。统一封装不保证所需市场资料全部可得。

## 已有公司财报复核

`company-financial-review` 接收 contextPath、financialResult、originalResult、archives（财务档案路径列表）、outDir（新点评目录）。通过 run-template 调用，复用已取得季度计算和原文归档，不重复取数。财务、原文与上下文截止日必须一致，声明币种须与上下文匹配；不自动汇兑。输入文件、计算模块哈希和核验结果保存到来源链。修改截止日或币种后，impact 标记旧结果失效；分红等不参与财报复核的参数变化不会强行判定其失效。

```json
{"template":"company-financial-review","contextPath":"/absolute/context.json","financialResult":"/absolute/financial/result.json","originalResult":"/absolute/originals/result.json","archives":["/absolute/statements/result.json"],"outDir":"/absolute/new-review"}
```

此模板生成已有财报的核对及点评，Excel仍按公司财报流程单独导出。季度报告缺失不能用其他期替代。

财报复核模板可选 interpretationsPath，指向经营解释列表JSON，格式按公司财报流程。该文件进入来源链；解释内容变化会令旧结果失效。没有提供时只生成已有数字与原文核对，不虚构经营判断。

## 已有宏观与研报资料复核

通过 run-template 调用 macro-observation-review 或 report-reading-review：提供 contextPath、inputPath（专题build输入JSON文件）、outDir（新目录）。不重复取数，截止日与资料归档必须一致。宏观资产价格的币种必须匹配上下文，dividendTreatment 必须为 price_only，不能包装成分红总收益。研报引用只证明文字定位，观点解释仍需复核。

登记上下文、build输入、资料归档、原始响应或PDF及计算模块版本，供 impact 检查。分享实际报告时仍使用专题输出目录；统一结果JSON用于研究留存，不要求用户阅读内部字段。

## 公司、行业与退出情景复核

company-scenario-review（dcf/relative/forecast）、industry-scenario-review（supply/concentration）、exit-scenario-review（exit）按 run-template 调用。提供 contextPath、inputPath（对应模型输入JSON）、mode、outDir。模式与模板不匹配时拒绝；截止日须一致，公司与退出模型币种须一致，行业数量单位继续按供需规范检查。

登记假设输入、实际提供的来源文件和计算代码。统一结果保留缺值、未知份额与年化未计算原因；scenario-calculated仅表示情景运行完成，不表示资料完整或未来结果得到验证。用户仍阅读各模型生成的自然语言报告。


## FOF披露持仓穿透

`fof-lookthrough-review` 使用 contextPath、inputPath；inputPath 指向 research_extensions.py fof 的既有递归输入。截止日、币种须与上下文一致，不自动重取报告或转换币种。可选 sourceFiles 为 path、sha256 列表，文件变化时拒绝计算。

输出逐路径缺口、股票/债券/现金/其他已知暴露、已知与未知总权重；未知不当现金、不重新归一化。来源链记录声明的报告日期、披露日期、URL及已提供文件哈希，保留未重新核验状态。文件绑定并不证明输入权重与原文一致；原文核验须先按FOF报告流程完成。


## 组合历史模型复核

`portfolio-model-review` 提供 contextPath、inputPath、mode=optimize/simulate/crisis。输入格式复用 portfolio_models.py 或 research_extensions.py crisis；需要numpy。统一币种、截止日；daily 对应 trading_day/252，monthly 对应 monthly/12，dividendTreatment 须 reinvest，价格或现金分红口径拒绝。可选 sourceFiles(path/sha256)登记来源文件，哈希变化拒绝。

保留模型参数、数据文件、代码版本及结果；上下文变更或登记文件变化可通过 impact 检查。总收益口径仍是输入声明，不等于已核验分红再投过程；不自动把价格序列转换成总收益。模拟分位不是未来保证，最小方差权重不是交易方案。

## 两次研究版本对照

`python scripts/research_pipeline.py --workspace <目录> --out <结果.json> template-diff <输入.json>`，输入含`beforePath`、`afterPath`，均指向统一模板结果。验证上下文及计算输出摘要，列参数、输入文件和代码版本变化；模板、参数或代码变化时阻止直接对比。仅说明版本变化，不按列表序号配对资产、不输出伪造跨期指标差值，也不把来源改变自动称为真实经营变化。

版本对比同时生成同名Markdown和HTML自然语言报告。识别已登记公司、报告、企业、FOF母基金及宏观指标/资产集合标识；宏观集合顺序变化不视为换对象，FOF底层持仓变化不视为换母基金。对象不同或缺少可比标识时阻止直接比较。旧FOF记录未保存母基金标识时需重新生成，不能从底层持仓猜测。报告用“方法版本变化”等说明差异，不向读者暴露内部模块名，不替代逐指标跨期核对。


公司点评结果保存输入声明的行业分类版本、报表范围、币种、金额单位和公司类别。版本对照按证券代码逐项匹配这些口径；值变化或一侧缺失时列出变化并阻止直接比较，不按公司排列顺序配对。口径留存不等于原文确认；未登记的口径不能据此视为已核验。

版本对照需完整的计算记录、结果摘要和方法版本。同一方法或同一来源文件登记冲突版本时拒绝比较，不以后一项覆盖前一项。

宏观复核将月度缺期和无共同月份同步列入统一缺口清单；仅查询宏观指标时不生成资产窗口，不把未请求的数据标为失败。

研报复核的尽调问题进入统一待核实清单，保留访谈对象、待取材料及 question-prepared-not-interviewed 状态。生成提纲不消除数据缺口，也不代表访谈完成。

事件价格复盘模板 event-price-review 使用 contextPath、inputPath、outDir。输入文件按 event_price_review.py 规范；截止日、币种和 price_only 口径须与上下文一致。事件日期身份未核验保留缺口，原始响应和参数版本进入来源链；不会因价格窗口完整而判定事件已验证。

## 原文持仓复核模板

`holdings-snapshot-review` 接收 contextPath、inputPath（holdings_snapshot_review 输入）、outDir（新目录），可选 node 指定Node可执行文件。报告研究截止日和币种必须与上下文一致；调用前不改写输入来消除冲突。重新解析每份原文后计算双口径重叠，登记输入、报告档案、PDF及计算模块哈希。非股票资产不冒充已穿透，配置权重不冒充真实账户验证；具体参数见基金综合诊断规范。


## 保存结果完整性与依赖复查

统一模板的新结果同时记录研究内容、状态、缺口清单及来源链的整体摘要。impact 与版本对照先验证保存结果，再检查依赖。历史结果没有整体摘要时仅核对已记录的计算摘要，明确提示汇总状态及缺口未获完整校验。摘要用于本地一致性检查，不是数字签名或来源真实性认证。

`python scripts/research_pipeline.py --workspace <目录> --out <复查.json> impact <输入.json>`；输入包含 resultPath，可选 newContextPath、replacements（已登记旧路径到新文件路径映射）。未登记替换路径拒绝处理。输出 JSON、Markdown、HTML，说明需要重做的范围；本地未变化不等于远程公告仍有效。政策研究仅以声明的同一来源网址辅助识别研究对象，不据此确认政策身份或效力。


财务 Excel 底稿复核跨公司比较中的每家原文页码、引句、文件摘要、比较状态和底层来源声明。同一第三方被多家公司转引不增加独立证据。新生成公司点评记录整体摘要，底稿拒绝摘要不一致的内容；历史无整体摘要的点评保留局限提示。引句定位不证明研究解释成立，本地摘要不认证来源真实性。


事件价格复盘支持分别声明 eventDate、publicationDate，以及 publishedAt（含偏移的ISO时刻）和 marketTimezone（IANA时区）。声明时刻转换到市场日期后，与 publicationDate 冲突则拒绝；披露晚于资料截止日拒绝。按事件与披露日期中较晚者对齐；已给时刻时取严格后续日期的共同收盘，前窗口截止于对齐日期之前。缺少时刻保留原日期口径，不推定盘中、盘后或首次公开时间。该保守口径不判断节假日、提前收市或即时反应；行情日期时区与来源身份需另行核验。

公司财报复核模板 company-financial-review 可选 interpretationsPath、comparisonsPath，分别读取经营解释列表和跨公司对照列表，按公司点评规范重新核对原文。两类文件均进入依赖记录，变更时需重新研究；引句与页码匹配不证明研究解释成立。

company-financial-review 可选 quarterReviewResults（不重复的已保存单季核验结果路径列表）。重新解析绑定原文并核对档案、口径、字段、状态和文件摘要后接入统一结果；公司必须属于本次样本且不重复。相邻期档案及PDF进入依赖复查。仅核对七项支持字段，不把未提供公司的单季依据视为已确认；跨期可比性和公告元数据提示仍保留。

接入相邻期核验后，同时生成自然语言的单季计算依据HTML/Markdown，分列本期、同比、环比输入状态，附已重新核验PDF页码链接。报告副本随输出保存；未提供核验的公司及跨期可比性、披露版本提示明确列示。

统一模板 etf-closing-premium-review 使用 contextPath、inputPath、outDir，输入格式见ETF收盘净值对照。要求CNY、price_only，输入end与研究asOf相同。保存价格档案、净值原始响应、计算参数和方法版本；缺单位净值日期及资料限制进入统一缺口。不自动采集盘中IOPV，不因本地文件未变而声称远程资料仍有效。


组合贡献模板 `portfolio-contribution-review`：manifest 提供 contextPath、inputPath（含 historyInput 与 weights），可指定 node 运行时。只接受与上下文一致的日/月频、币种、截止日、无风险利率、红利再投和共同日期；保留每项资产资料缺口及计算版本。输入序列未与原始来源逐点核验时明确列缺口，不能仅凭来源链接认定验证完成。

组合贡献结果可用 `python scripts/portfolio_contribution_report.py result.json --out-dir 新目录` 导出HTML和Markdown简报。支持统一封装或独立贡献结果；导出前核对权重、收益、回撤及非零波动贡献合计。数据缺口随报告显示；合计核对不等于原始来源验证。

事件价格统一结果的缺口逐项登记所选资产的原始观测核对、分红复权、同步定价时刻与交易日历状态；稀疏窗口另列，窗口完整不清除这些证据缺口。

FOF穿透复核模板提供 outDir 时，另存自然语言 Markdown/HTML 简报：已知大类敞口按原始组合分母展示，列完整未知路径及报告时点。不将未知归类现金；文件哈希绑定仍不等于原文已重新核验。输出目录必须为新目录。

FOF简报交付目录包含已登记来源文件副本，复制前再次核对哈希，正文使用相对链接。请连同整个目录分享；来源副本不等于节点对应关系或逐行原文已核验。未取得的子基金报告仍列缺口，副本不进入独立安装包。

译文模板按[研报阅读](research-report-reading.md)的译文输入执行，登记输入文件、原文档案、原PDF及翻译与阅读方法版本。缺页、文字不足、数字提示及语义尚未独立核验进入缺口。原文或译段文件变化后旧结果需另建版本，不把全部文字覆盖当作翻译准确率。

## 多份研究影响复查
`python scripts/research_impact_batch.py INPUT.json --out-dir NEW_DIR`，输入`researches`为研究记录列表，每项提供`id`、`label`、`resultPath`，可选`newContextPath`核对新参数；可选`replacements`映射已登记原路径到新来源。输出受影响研究及`affectedCalculations`，基于已登记文件与方法依赖；参数变化保守列相关计算。历史记录无计算ID时保留空ID并显示登记位置，不补造身份。它不自动定位全部正文结论、不重写旧报告；需重算、核原文并绑定最终正文后另作验收。
