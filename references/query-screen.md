# 标的查询与筛选

查询指定标的、获取名称候选、按有来源的条件筛选。输入代码、名称或条件；结果列身份、资料日期、命中/未命中原因及缺失项。名称主题不是投资范围证明，指定池不是全市场。

[宏观与跨资产观察](macro-asset-observation.md)：公开宏观观测、QQQ/TLT/BTC历史价格共同窗口；不做周期预测或因果归因。

## 任务与已有入口

路径相对 Skill 根目录。读取所选参考中的完整调用模板和输入规范，再准备参数；表中的简称不替代实际 CLI。

| 请求 | 规范与入口 |
|---|---|
| 港美股明确代码价格日线尝试、实际区间与空历史原因 | [跨市场日线](cross-market-history.md)：cross_market_history.py --market HK/US --code CODE --start DATE --end DATE --out NEW.json；价格未核验分红拆分 |
| 名称候选检索后自动取数、共同区间条件研究 | [名称研究联动](theme-research.md)：theme_research.py INPUT.json --out-dir NEW_DIRECTORY；候选超限不静默截取，支持冻结候选续采 |
| 红利、AI、新能源等名称关键词候选获取 | [名称候选](theme-candidates.md)：theme_candidates.py --term 关键词 --out NEW.json；投资主题与场内ETF身份需另核验 |
| 指定基金池自动取净值、共同区间指标和条件筛选、失败续采 | [批量筛选](fund-batch-screen.md)：fund_batch_screen.py INPUT.json --out-dir NEW_DIRECTORY；不把名称主题、缺失评级和失败对象自动剔除 |
| 指定基金净值、阶段表现、配置、持有人与经理资料线索 | [基金明细](fund-details.md)：fund_details.py --code 六位代码 --as-of YYYY-MM-DD --out NEW.json；第三方事实与原文核验分开 |
| 代码/名称检索、多个候选 | [标的检索](security-search.md)：security_search.py或research_pipeline.py search；债券细分品种未核验不猜 |

## 共用步骤

按[共用能力分工](shared-research-layers.md)复用取数、证据、计算和表达；仅组合已有接口，不假设存在一个覆盖全部专题的自动执行器。报告与版本留存见[研究档案](archives-reports.md)。

[ETF收盘净值对照](etf-closing-premium.md)：指定代码历史价格与单位净值共同日期计算，缺值单列；非盘中IOPV。

收益、回撤、波动率、夏普与定投收益筛选须指定 basis 和 window，缺失时列为资料不足。价格与净值口径不混用；自动基金批量采集仅在共同口径唯一时补入实际共同区间，不改写用户指定口径。

跨响应计算指标可在证据中附 sourceUrls，须为包含主要 sourceUrl 的非空 HTTP(S) 链接列表。筛选报告列出全部登记链接；链接登记不代表原始响应完整性已核验。

涉及制度、条款、专业方法与解释时，使用[适用依据规范](research-basis-standard.md)，核对范围、版本和原始依据；规则核对不替代本场景计算或内容验收。
