# 独立组合压力与相关性

执行 scripts/portfolio_stress.py 输入.json --out 新文件.json。标准库实现，不依赖工作台，不自动抓取或核验输入真实性。

需要历史组合收益与回撤时显式提供 `historicalPortfolioMode`：`buy-and-hold` 为期初研究权重买入持有，权重随收益漂移；`fixed-observation-weights` 为每个共同观察区间维持输入权重，隐含再平衡，不包含费用与真实成交。未提供时不自动计算路径。结果在 `historical.portfolioPath`，保留总收益、观察最大回撤、高低点日期与逐期资产路径。共同相邻收益区间存在断点时返回 `disconnected-observations`，不拼接遗漏时段。日历未认证、观测日期间低点未知，不能称真实账户或未来回撤。固定权重尾部平均收益与买入持有路径分开解释。

输入asOf、baseCurrency、holdings。每行code、currency、marketValue；可选history(date,value正值总收益指数)、basis=total-return、sourceUrl。正市值无杠杆且统一币种；分红拆分须事先核验。共同日期且各原序列相邻的观察区间才纳入计算，不填充。minimumObservations默认60；不足或零方差相关性留空。不假称跨市场对齐结果为连续日频。

windows可选，每行name/start/end，预先指定正常及危机窗口；结果是历史皮尔逊矩阵，不是未来相关性。没有实际危机窗口不得声称识别漂移。

scenarios每行name、assumptions、returnShocksPct按代码给百分比冲击。加权市值计算一次损益，缺任一持仓冲击整体留空，提供覆盖率。没有时间路径最大回撤始终留空。50bp利率冲击不是50%价格冲击，需要另外根据久期凸性信用利差转换，本入口未自动转换。

输出输入摘要，拒绝覆盖旧结果。仅客观分析不构成投资建议，有本金损失风险。合成数据测试只验证公式及输入边界。

本入口仍不含交易成本与成交限制、动态再平衡、利率映射或蒙特卡洛。主包其他模型的能力见[组合模型](portfolio-models.md)，不沿用历史待开发状态判断全包能力。

## 历史风险的分阶段观察

同一入口输出整体及预先指定windows的样本协方差（除以n-1，收益以小数计，未年化）。rollingWindowObservations可选，须不少于minimumObservations；rollingStride默认5，追加截止最新有效观测的最后窗口，输出最多约2000个窗口。未指定不自动启动滚动。

tailConfidence默认0.95、允许0.8至小于1；minimumTailObservations默认10、至少3。按ceil(n*(1-confidence))划入最差观察区间，求固定当前权重组合的平均收益。尾部样本不足则留空；置信参数用于历史切分，不是未来损失概率，负数不是未来最大回撤，尾部全部上涨时允许正收益。不按日历补行情、不自动年化或生成交易建议。

自然语言报告：`python scripts/portfolio_history_report.py INPUT.json --out-dir NEW_DIR`。沿用本页输入，输出input/result及Markdown/HTML。定额权重只是研究输入，不是实际账户再平衡。没有预设危机窗口时不称危机复盘；缺完整日历、分红核验与交易摩擦时单列局限。
