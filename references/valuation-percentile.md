# 估值历史分位计算

调用 `python scripts/valuation_percentile.py INPUT.json --out NEW.json`。已有真实估值序列才能计算，本入口不自动获取全市场估值。

输入必需：code、market、subject（如tracking-index）、metric（如PE-TTM）、method（如aggregate）、frequency、sourceUrl、start、asOf、observedAt、history。history为date/value及可选publishedAt记录。minimumSamples默认60，可显式设定但不少于2。

缺失、非正估值及截止日后披露数据排除；日期重复乱序拒绝。当前观测缺失或有效样本不足不计算。采用中位秩公式，包含当前观测，同值占半权；报告明确公式与有效样本。最低样本门槛不是置信度或可靠性保证。

输出valuationPercentile字段可放入 multidimensional_screen.py 候选的 fields；其日期、窗口、单位、指标、对象、频率与算法口径一并保留，不跨口径排名。跟踪指数估值不是ETF价格或净值；负PE不能解释为便宜。分位不构成未来收益或买入依据。历史修订值不是事前冻结值。
