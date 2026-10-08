# 公告与事件研究

公告目录、附件、条款、事件时间轴、经理年报观点及数字引句核验。目录、下载、文本解析、原文核验分别记录；单一网址失败不能证明资料不存在。

[公司池财报联动](company-report-workflow.md)：财报覆盖、巨潮原文与页码、季度分析、点评及Excel底稿。

[研报精读](research-report-reading.md)：通用PDF归档、三层阅读、页码引句校验与跨报告对照。

## 任务与已有入口

路径相对 Skill 根目录。读取所选参考中的完整调用模板和输入规范，再准备参数；表中的简称不替代实际 CLI。

| 请求 | 规范与入口 |
|---|---|
| 基金合同、更新招募说明书、费率与经理变更文档目录线索 | [公开文件目录](fund-document-catalog.md)：fund_document_catalog.py --code CODE --as-of DATE --kind contract|prospectus --out-dir NEW_DIRECTORY；披露日期不等于生效日期 |
| 基金PDF股票、行业及利润表提取 | [测算规范](research-analytics.md)：fund_report_holdings.py/fund_report_industries.py/fund_report_profit.py；仅已支持布局，原文身份分母另核 |
| 核验一段新闻或研究中的数字、引句与判断 | [逐条事实核验](claim-verification.md)：claim_verification.py INPUT.json --out NEW.json；先拆主张，排名与因果缺证据不确认 |
| 易方达原文缺代码时官方产品—法律文件关联 | [官方文件关联](efunds-document-binding.md)：efunds_document_binding.py --code CODE --title TITLE --published DATE --as-of DATE --out-dir NEW_DIRECTORY；仅该发行人适配，生效关系另核 |
| 已取得目录的明确公告附件下载、身份与费率措辞核对 | [附件原文](fund-document-archive.md)：fund_document_archive.py CATALOG_RESULT.json --id ID --out-dir NEW_DIRECTORY；当前有效版本仍需联合核验 |
| 已取得年报的经理任职表、职务和履历原文 | [任职表提取](report-manager-tenure.md)：report_manager_tenure.py REPORT_RESULT.json --out NEW.json；助理身份与其他产品线索需另核验 |
| 经理报告观点、多期分类变化、行业归因输入与综合报告 | [深度证据](fund-depth.md)：fund_depth.py manager/changes/attribution；depthResults接入综合报告，原文及口径先核验 |
| 直接输入问题开展单公司公告研究 | [统一问答流程](question-workflow.md)：research-question；自动身份/窗口/取数/线索/档案，未接通全专题研究 |
| 公告与新闻分类、事件时间轴、今日摘要和差异跟踪 | [事件追踪](event-research.md)：events/event-monitor；A股元数据自动获取，港美股新闻需输入；无常驻通知 |
| 已取得政策PDF的对象、生效时间与条件 | [政策原文解读](research-report-reading.md)：research_report_reading.py prepare/build，analyses 增加 policyAnalysis；公布、生效与当前有效性分开，传导缺证据留空 |
| 政策网页原文、发布日期与项目分界条件 | [网页政策原文](policy-original-reading.md)：policy_original_reading.py prepare/build；段落引句、原始哈希、日期分类及经营传导缺口，共用report-reading-review模板 |
| 原文数据逐项核验 | [原文规范](original-verification.md)：verify_original.py；送出日期不证明历史网页首次上线时间 |

## 共用步骤

按[共用能力分工](shared-research-layers.md)复用取数、证据、计算和表达；仅组合已有接口，不假设存在一个覆盖全部专题的自动执行器。报告与版本留存见[研究档案](archives-reports.md)。

涉及制度、条款、专业方法与解释时，使用[适用依据规范](research-basis-standard.md)，核对范围、版本和原始依据；规则核对不替代本场景计算或内容验收。

披露提示公告与报告全文分开核验：提示公告能提供产品身份、声明发布日期及官方入口线索，不能认证已取得第三方PDF与官方文件一致，也不能单独确认首次公开时间。检索失败不证明报告未发布；联接基金与目标ETF分别确认。全文未取得时保留文件来源缺口，不以提示公告替代原文。

管理人目录补充入口：华泰柏瑞产品可用 `python scripts/huatai_report_catalog.py --title "完整产品名称2026年中期报告" --max-pages 20 --out-dir NEW_DIRECTORY`，仅按完整标题匹配管理人官网PDF链接。代码使用标准库、保存每页响应与哈希、保留失败；上限不超过50页，找到候选即停止，不做后台刷新。目录候选仍需下载PDF核对代码、时期、名称和原文；联接基金不替代目标ETF。未检出表示本次已查页内未找到，不等于报告不存在或未发布。该入口只支持此管理人的当前目录结构。

工银管理人静态目录入口：`python scripts/icbc_report_catalog.py --code 000991 --title "完整目标文件标题" --out-dir NEW_DIRECTORY`。仅核对该代码本次返回的条目和完整标题，保存目录响应/哈希，分别记录公告日与更新时间；当前静态目录可截断，不自动认证全历史或最新法律文件。目录候选仍需下载PDF、核对代码/份额/期间及适用范围，公告日不当作精确历史可得时刻。网络或结构异常留失败记录，不转为“没有公告”。本入口只支持工银当前官方静态目录结构，不需要账号。
