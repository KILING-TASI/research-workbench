# 联接基金目标报告关联

输入已取得且完成身份匹配的父基金报告结果；读取报告“2.1.1 目标基金基本情况”，提取明确披露的全名、代码、管理人和交易所，保留页码、表格位置、原文单元格和文件摘要。名称或代码冲突即停止，不按简称猜代码。

```powershell
python scripts/target_fund_link.py PARENT_REPORT.json --out NEW.json
python scripts/target_fund_link.py PARENT_REPORT.json --child-report CHILD_REPORT.json --out NEW_LINK.json
```

第二条命令关联已取得的同期间子基金报告：代码、报告期、全名和文件摘要必须匹配，子报告股票表须完成勾稽。可先用 fund_report_archive.py 按明确目标代码及期间获取子报告，再关联。输出 JSON、自然语言 Markdown 和 HTML。

目标基金关系不等于前十名基金表的简称行映射；本工具不推断父基金持有权重，不计算加权穿透，不假设非股票资产为零。报告副本关系也不代表最新有效合同或官方网页已经核验。尚不支持其他版式时明确失败，原报告保持不变。

父子报告使用同一个研究截止日。父关系与子报告的披露日期均须在报告期末至截止日之间；晚于截止日、未提供日期或截止日不一致时拒绝关联，避免事后资料混入历史研究。
