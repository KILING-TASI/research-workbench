# 基金研究代码索引

本文件供执行与维护使用；用户功能说明见 [fund-user-guide.md](fund-user-guide.md)。不将实现数量、内部状态或调试命令写入用户报告。

## 调用约定

以下路径相对Skill根目录。Python用 `python scripts/文件.py 子命令 INPUT.json --out NEW.json`；JS用 `node scripts/文件.js 子命令 INPUT.json NEW.json`，实际例外见各模块参考。AI根据用户提问组织参数，不要求用户填写JSON。新结果使用新文件名，避免覆盖首次证据。

| 层次 | 主要代码 | 实际职责 | 参数说明 |
|---|---|---|---|
| 采集与身份 | research_pipeline.py、security_search.py、portable_collect.py、batch_collect.py | 代码检索、净值历史、批量状态及缓存 | standalone-collection.md、security-search.md |
| 结论证据 | fund_evidence.py | build、compare；证据/计算路径与绑定笔记 | fund-evidence.md |
| 序列与对标 | fund_series_tools.py | quality、distributions、benchmarks、snapshot-diff | fund-series-tools.md |
| 基础研究 | fund_research.js | compare、feeStudy、monitor、simulate、scan、contributions | fund-research.md |
| 通用测算 | research_analytics.js、research_analytics_cli.js | 历史指标、持仓/行业快照及两期变化 | research-analytics.md |
| PDF结构 | fund_report_holdings.py、fund_report_industries.py、fund_report_profit.py、fund_report_fof.py | 版式限定提取与金额核对 | research-analytics.md |
| 原文核验 | verify_original.py、original_layouts.py | 身份、页码、字段歧义与哈希核对 | original-verification.md |
| 深度证据 | fund_depth.py | manager、changes、attribution | fund-depth.md |
| 专项研究 | fund_specialists.py | allocation、behavior、style、conditions、research | fund-specialists.md |
| 池与归因 | research_library.py、attribution_link.py | pool、score、reverse、documents、archive、brinson；多期链接 | fund-research-library.md、fund-diagnostics.md |
| 诊断汇总 | fund_diagnostics.js | overlap、similar、report；供导出使用的markdown函数 | fund-diagnostics.md |
| 报告排版 | fund_report_presentation.js | 既有综合结果的HTML展示 | fund-diagnostics.md |
| 联动与模板 | fund_enhancements.py | pool-snapshot、attribution-panel、clauses、export、screen-to-pool | fund-enhancements.md |
| 留存导出 | research_outputs.py、research_tasks.py、export_research_xlsx.mjs | screen、snapshot、笔记和Excel | research-output-tools.md |
| 组合扩展 | research_extensions.py、fof_reports.py、portfolio_models.py、portfolio_stress.py | 递归穿透、底层报告关联、优化/模拟及压力损益 | research-extensions.md、portfolio-models.md、portfolio-stress.md |

## 默认资料流程

1. 确认代码、份额类别、报告类型、研究截止日及观察窗口。
2. 取净值并检查日期、分红口径；报告优先正式披露入口，失败后换其他正式入口，第三方用于寻找原文线索。各渠道有界重试，记录失败原因。
3. PDF下载后核对主体、报告期与送出日期，保存URL、文件哈希；全文读取与结构化表解析分开。
4. 持仓分析先核对完整范围及金额合计；报告快照和净值窗口分别标注，不用年末替代中报而不说明。
5. 完成支持的计算再汇总；缺基准、分类、收益或报告时只跳过依赖项，保留具体缺项。
6. 输出用户报告及可复查证据；不能仅净值成功就宣称完整研究成功。

## 依赖与职责边界

Python用于采集/证据，Node用于确定性量化；PDF需要pdfplumber，组合优化/模拟需要numpy。Excel有额外导出依赖。各专题脚本继续复用，不搬迁文件或合并独立数学实现。基金业务使用跨资产通用引擎，不重复维护另一套组合公式。

报告抓取不是上述全部脚本已自动完成的闭环；最近样本临时提取结果只能算样本证据，不能称通用版式已支持。HTML排版修改不等于数据能力新增。

## 验证索引

对应test_fund_research.js、test_fund_diagnostics.js、test_fund_depth.py、test_fund_specialists.py、test_fund_enhancements.py、test_research_library.py及test_attribution_link.py。测试覆盖所述输入边界，不保证任意真实基金资料可得。


基金评价基础补充：产品定位、规模与持有人结构、已核验任职区间分析及缺口清单。调用 `python scripts/fund_evaluation.py INPUT.json --out NEW.json`，输入与边界见 [fund-evaluation.md](fund-evaluation.md)。报告以自然语言解释结果，不将产品表现直接视为经理能力。


历史定投回测：支持固定金额/份额、每周/每月计划、现金分红/理论再投、总投入、期末资产、累计收益率、XIRR、逐期明细及同基金多方案对比。事件完整性和申购费假设必须说明，期末资产不等于赎回到手收益。调用与参数见 [fund-dca.md](fund-dca.md)。


经理任职与产品关系：支持按姓名汇总已取得报告中的产品任职记录、区间表现、共同管理和冲突项，最新在管状态需最新证据。参数见 [经理任职](manager-products.md)。
