# 机构盈利预测历史留档：下一批优先范围

## 事实与反证
[AKShare官方股票文档](https://akshare.akfamily.xyz/data/stock/stock.html)已列stock_profit_forecast_ths机构/研究员/报告日期和财年预测；stock_research_report_em列研报预测与PDF链接。因此首批先接结构化离线档案，不从任意PDF解析器起步。字段存在不证明本次接口已可用或全市场覆盖。

## 档案契约
每条预测保留主体、机构、研究员、reportId/reportDate、acquiredAt（含时区）、forecastYear、metric、value/unit/currency、scope/basis、rawResponseSha256、source、接口与转换版本。预测与已报告实际值分开，不投喂到实际财报pairs冒充披露数。

同机构同报告同预测年度/科目/口径重复内容去重但保留获取记录；同报告不同响应值作为源版本冲突，不当作分析师再次修正。同机构新报告仅对同财年、同口径与单位比较修正；同日多报告未明顺序时不任意排序。

当前网页补录旧预测须标reconstructed，不称当时可得样本；历史回放只按已留存取得时间筛选，不能用报告日期倒推可用性。实际业绩匹配须核对首次披露、重述版本、合并范围、每股分母和指标定义；缺依据不评分析师准确率。

## 首批/后续/缺口
下一批先实现标准化离线档案、重复和冲突记录、修正比较及截至时点筛选，使用明确教学输入验收。再选少数真实标的主动联网，记录接口失败，不承诺数据齐全。待补：实际业绩及重述关系匹配，真实在线接口和历史前视偏差验收。本批只落实设计，尚未实现档案引擎。

## 不据此宣称独家
[IPO_crawler](https://github.com/sqwqwqw1/IPO_crawler)提供已有招股/问询采集线索，未验收当前运行，问询专题仍聚焦逐项关联。[REITs工作台](https://kirisame.cn/reits-val)展示已有估值工作流，不证明开源或成熟。原调研里的零竞争不作为产品事实。
