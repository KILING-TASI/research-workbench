# 已披露股票的主题暴露

调用：`python scripts/holding_theme_exposure.py INPUT.json --out NEW.json`。输出JSON、自然语言Markdown和HTML。

输入包括 `asOf`、`theme`、`classificationVersion`、`report`（fund_report_archive已严格勾稽的报告结果对象）、`classifications`。每个分类包含股票 `market`（CN-equity/HK-equity）、`code`、`themes`列表、`classificationVersion`、`sourceUrl`、`publishedAt`、`effectiveFrom`、可选`effectiveTo`、原文`quote`与`locator`。空themes列表表示此版本明确未归入主题，不代表缺失。分类必须按用户指定口径提供并复核，不按名称生成。

先用名称候选定位研究对象，再获取报告。完整股票报告未通过勾稽时停止本次暴露计算。缺少分类或分类有效期不覆盖报告日时，保留未知权重，不填零。报告输出已确认主题股票占净资产、未分类权重、分类覆盖比例及股票主题权重上下界。上下界由未知股票可能归属得到，是确定性范围，不是置信区间。只覆盖股票表，不宣称全基金经济风险；主题可能相互重叠，不能把主题权重直接相加。提供的分类来源不等同自动完成原文核验。

最小结构：
```json
{"asOf":"2026-10-03","theme":"用户指定主题","classificationVersion":"用户指定版本","report":{},"classifications":[]}
```
report须替换为实际报告对象；分类为空时仍输出未知股票范围，不宣称主题为零。真实验收目前仅确认报告持仓接入与缺分类处理；分类示例测试不作为真实主题归属证明。

可选 minimumWeightPctOfNAV 为0至100的股票主题净资产权重阈值。按已确认下界/可能上界返回满足、不满足、资料不足；未知分类不按零处理，结论不涵盖债券或未穿透资产。

批量入口：`python scripts/holding_theme_batch.py INPUT.json --out NEW.json`。输入asOf、theme、classificationVersion、minimumWeightPctOfNAV、classifications及dossiers列表（1至500份基金档案）。共用分类版本，逐基金保留报告日期、上下界、阈值状态和缺口；不跨报告日排名。

报告行业阈值另用 `python scripts/report_industry_threshold.py INPUT.json --out NEW.json`，输入dossier、asOf、industryKey（原报告唯一代码）、minimumWeightPctOfNAV。重新核对PDF摘要、行业合计、身份和日期；保留分类版本和逐行证据。行业不是主题，不按名称模糊匹配。

未知分类分列未提供、报告日尚未生效、报告日前已失效。未适用分类保留unusedClassificationEvidence，并在简报中列有效期与未适用原因，仍不用于主题权重或把未知认定为非主题。
