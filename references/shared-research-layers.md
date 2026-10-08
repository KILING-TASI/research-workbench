# 共用能力分工

此文件用于选择已有实现，不是新的统一数据接口或已经完成的代码搬迁。原脚本路径、命令和输入格式保留；跨专题只复用确实可接通的结果。

| 共用层 | 职责 | 主要已有入口 | 不应承担 |
|---|---|---|---|
| 数据获取 | 身份、检索、下载、缓存、续采与逐项失败 | security_search.py、portable_collect.py、market_collect.py、fund_details.py、fund_report_archive.py、stock_statements.py | 原文确认、完整研究结论 |
| 原文与证据 | 身份、页码、哈希、同名字段冲突、参数与版本 | verify_original.py、fund_evidence.py、fund_document_archive.py、claim_verification.py | 把下载成功改写为核验成功 |
| 计算模型 | 历史指标、费用、季度财务、归因、穿透、情景与组合模型 | fund_series_tools.py、fund_research.js、industry_financials.py、research_library.py、research_extensions.py、portfolio_models.py | 猜测缺数据、无依据的因果与未来结果 |
| 报告表达 | 组织已有结论、可读说明、模板与导出 | research_brief_html.py、fund_report_presentation.js、research_outputs.py、research_tasks.py | 补造输入或掩盖未完成模块 |

## 复用约定

- 已下载文件满足证券身份、报告期、披露截止日和版本要求时复用；重新解析另存结果，保留原件哈希。
- 日期、币种、单位、分红、行业分类和报表范围不一致时先隔离，不能因为JSON结构相似就拼接。
- 原有脚本schema仍各有约定。复用前读对应规范，不把四层说明宣传成统一schema已全面落地。
- 用户报告先呈现自然语言发现，再列事实与计算依据、口径、缺口。来源等级、核验状态和假设不得在摘要里省略或升级。
- [基金代码索引](fund-code-map.md)保留细节；[研究工作流](research-workflow.md)只覆盖其真实接通的模板，不能默认全部任务自动运行。
