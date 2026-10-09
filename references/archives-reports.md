# 研究档案与报告

整合已经完成的研究结果、证据、笔记与快照差异，并生成报告。先说明本次结论，再解释来源和局限；缺模块不能用排版或摘要补成已完成。

[研报精读](research-report-reading.md)：通用PDF归档、三层阅读、页码引句校验与跨报告对照。

## 任务与已有入口

有实际出入金与流前/流后账户估值时，可用[组合现金流收益观察](portfolio-cashflow-review.md)区分TWR累计收益与XIRR资金加权年化；不是交易回测，不凭期末截图还原历史现金流。

用户说“找回上次报告”时，使用[日常入口](practical-entry.md)中的结果检索，只搜索明确结果父目录的直接子目录。新报告可在清单声明`primaryReport`，避免附件被误作正文；旧报告缺生成时间不倒推日期。北交年度报告可接着换资金规模重算，并查看资金调整说明；资料和权限不自动更新。

路径相对 Skill 根目录。读取所选参考中的完整调用模板和输入规范，再准备参数；表中的简称不替代实际 CLI。

| 请求 | 规范与入口 |
|---|---|
| 将已有取数结果整理成资料范围说明 | `python scripts/collection_quality_brief.py INPUT.json --out-dir NEW_DIR`；读取取数结果的rows，生成HTML/Markdown，保留名称缺失、来源、时间、错误与事件口径缺口，不计算绩效 |
| 指定基金池批量明细 | [基金明细](fund-details.md)：fund_details_batch.py INPUT.json --out-dir NEW_DIR；逐只失败留痕，不作共同区间排名 |
| 港美股明确代码行情快照、币种与数据域缺口 | [跨市场快照](cross-market-quote.md)：cross_market_quote.py --market HK/US --code CODE --as-of YYYY-MM-DD --out NEW.json；非历史财报全覆盖 |
| 逐结论证据、引用链、原文行定位、绑定笔记与版本比较 | [证据包](fund-evidence.md)：fund_evidence.py build/compare；覆盖率非置信度，完整快照非精确归因 |
| 净值异常、现金分红/再投、拆分、多基准和快照差异 | [序列与对标](fund-series-tools.md)：fund_series_tools.py quality/distributions/benchmarks/snapshot-diff；缺事件或日历不假定完整 |
| 基金池批量快照、分期归因面板、条款标签、专题导出、筛选入池 | [轻量增强](fund-enhancements.md)：fund_enhancements.py；相似差异沿用fund_diagnostics.js similar |
| 指标筛选并入对比池、笔记挂载、Markdown/Excel快照、调整情景、批量轻量诊断 | [研究输出](research-output-tools.md)：research_outputs.py、research_tasks.py note、fund_research.js simulate/scan；Excel导出依赖环境 |
| 数据源覆盖、选择与按域调用 | [数据源登记](source-registry.md)：source-list/source-plan/source-collect；授权未知与未接入保留缺项 |
| 数据采集、批量获取、比较、验证、留痕 | [六项流程](six-workflows.md)与[独立安装](standalone-install.md)与[历史和批量采集](standalone-collection.md)：research_pipeline.py；collect-batch逐对象报告状态 |
| 研究缺口、版本知识卡、多源数值核对 | [研究证据](research-evidence.md)：research_pipeline.py gap-analysis/knowledge-add/knowledge-show/cross-validate；异口径先隔离 |
| 研究保存与复查 | [六项流程](six-workflows.md)：research_tasks.py和review，保留首次依据与失效条件 |

## 共用步骤

按[共用能力分工](shared-research-layers.md)组织证据与结果；格式导出按实际入口覆盖说明，不承诺所有格式都可用。

资料说明入口读取已有取数结果，不触发新取数。输入必须保留证券代码、历史日期及净值或收盘价格；如有asOf，晚于截止日的观测会阻止报告生成。缓存读取、失败保留缓存、未知事件及来源缺失分别说明。生成的report-manifest.json记录输入快照、报告文件和生成方法摘要；摘要只用于内容一致性核对，不证明数据真实、最新或排版已验收。输出目录必须是新目录，以保留旧报告。

## 保存内容复查
`python scripts/verify_collection_report.py REPORT/report-manifest.json --input COLLECTION.json`
只读核对报告、输入与生成方法摘要，分别标记内容变化和方法变化；不证明原文真实性、数据最新或视觉排版通过。资料报告在临时目录完成后发布至新目录，失败不留下半份正式报告。旧版清单不满足新规范时重新生成报告，不改写历史清单。

## 资料报告输入与核对
报告生成前核对标的类型、身份、资料日期、组件状态、记录数、来源列表与缺口清单。不可用状态与已有资料、失败组件与已有资料互相冲突时停止生成；刷新失败保留旧资料须使用 cached-after-failure。错误信息在相应标的下显示，报告开头概括实际取得资料的标的数量，不将数量当作完整度。重复 JSON 字段和非有限数值拒绝处理。文件不可读取时保存内容核对返回明确问题，不以核对中断代替通过。


## 公司报告的首页表达
公司经营报告首页先回答本次核心问题，后续只展开与判断有关的增长、利润与现金证据。不要为凑发现数量拆散文章；核验数量、单位换算和页码规则放到底稿。仅取得核验结果时交付核验底稿，不称为经营研究结论。
同比优先使用同一份报告的可比列，并核对重述；现金利润比采用一致合并范围。公司对原因的说明标为公司解释，不能自动成为独立验证的因果判断。扣非与归母背离需检查分类与相关损益，不据单个比率认定经营优劣。

买方研究假设、截止日证据与兑现复盘见[投资假设档案](buy-side-thesis.md)。

资金用途、组合压力与首次假设的可重算整包见[买方研究包](buy-side-bundle.md)。原文归档与冻结引用范围分别说明。


## 多份研究的影响复查

公司版本对照区分已登记口径值改变、新版补充旧版缺少的记录，以及新版记录缺失。记录补充不证明实际业务口径改变；缺少一致性依据时仍不认定直接可比。方法版本变化继续单独提示，不将报告差异解释为经营变化。

公司财务研究即使两版均未登记单位、币种、报表范围、公司类别或行业分类版本，也列口径缺口并阻止直接比较；相同空值不证明口径一致。其他研究模板按各自记录范围检查，不借用公司字段要求。

运行 `python scripts/research_impact_batch.py INPUT.json --out-dir NEW_DIR`。输入 researches 列表（id、label、resultPath），resultPath须指向已有research-template-result封装；可选 replacements 为已登记来源路径的新路径映射。复用单研究完整性检查，输出文件变化影响哪些研究，参数和方法变更分别说明。未知替换和篡改封装拒绝。仅所选已登记依赖，不能声称覆盖全部历史报告；方法变化不等于经营事实变化。


## 深度研究的组织与交付

深研执行按[研究流程](research-operating-flow.md)组织问题、证据任务、经营机制与适用估值，交付按[深度研究标准](research-depth-standard.md)复查。当前脚本完成取数、核对或格式导出，不自动完成商业模式、原因和投资价值判断。已有数据足够时继续分析；关键资料失败时说明其影响并交付有限结论，不将研究提纲称为完整深研。

研究任务的步骤完成状态表示已登记结果与证据说明，不等于程序独立核验原文或认证整份研究。首次快照保留，后续笔记与步骤记录分别追加；空白或重复证据说明、非布尔完成标记不能登记为有效记录。

报告找回支持已取得的完整基金名称，包括比较池中第二只产品；旧基金比较仅按其登记的comparison/input.json补名称，不遍历其他私人目录。若正文没有明确结论标记，索引只展示正文开头摘录，不推导新判断。显示留存时间为北京时间，不认证数据最新；独立工具接续需沿用已确认项目安装位置和旧输入，外部原件另核。

同入口接续报告可返回本次明确选用的上次报告，保存相对关联，便于旧结论与新结论连着读。关联不自动读取其他目录，不认证旧资料最新，也不代替输入/原件核验。移动结果时应同时保留来源报告；只有新报告目录不保证旧链接仍可打开。

schema、输入/方法摘要与兼容迁移限制见[研究方法卡](research-method-cards.md)。未知显式schema不能自动按旧版解释；外部原件或组件未冻结时不称完整复现。
