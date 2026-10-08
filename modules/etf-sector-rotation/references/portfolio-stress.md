# 独立组合压力与相关性

执行 scripts/portfolio_stress.py 输入.json --out 新文件.json。标准库实现，不依赖工作台，不自动抓取或核验输入真实性。

输入asOf、baseCurrency、holdings。每行code、currency、marketValue；可选history(date,value正值总收益指数)、basis=total-return、sourceUrl。正市值无杠杆且统一币种；分红拆分须事先核验。共同日期且各原序列相邻的观察区间才纳入计算，不填充。minimumObservations默认60；不足或零方差相关性留空。不假称跨市场对齐结果为连续日频。

windows可选，每行name/start/end，预先指定正常及危机窗口；结果是历史皮尔逊矩阵，不是未来相关性。没有实际危机窗口不得声称识别漂移。

scenarios每行name、assumptions、returnShocksPct按代码给百分比冲击。加权市值计算一次损益，缺任一持仓冲击整体留空，提供覆盖率。没有时间路径最大回撤始终留空。50bp利率冲击不是50%价格冲击，需要另外根据久期凸性信用利差转换，本入口未自动转换。

输出输入摘要，拒绝覆盖旧结果。仅客观分析不构成投资建议，有本金损失风险。合成数据测试只验证公式及输入边界。

待补蒙特卡洛分布校准、路径回撤、久期映射、真实持仓验证及界面；财报勾稽、事件复盘、多口径估值与回答打分器也未因本入口而完成。
