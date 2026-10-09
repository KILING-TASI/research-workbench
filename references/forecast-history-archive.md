# 机构盈利预测历史留档：有界离线入口

## 事实与反证
[AKShare官方股票文档](https://akshare.akfamily.xyz/data/stock/stock.html)已列stock_profit_forecast_ths机构/研究员/报告日期和财年预测；stock_research_report_em列研报预测与PDF链接。因此首批先接结构化离线档案，不从任意PDF解析器起步。字段存在不证明本次接口已可用或全市场覆盖。

## 档案契约
每条预测保留主体、机构、研究员、reportId/reportDate、acquiredAt（含时区）、forecastYear、metric、value/unit/currency、scope/basis、rawResponseSha256、source、接口与转换版本。预测与已报告实际值分开，不投喂到实际财报pairs冒充披露数。

同机构同报告同预测年度/科目/口径重复内容去重但保留获取记录；同报告不同响应值作为源版本冲突，不当作分析师再次修正。同机构新报告仅对同财年、同口径与单位比较修正；同日多报告未明顺序时不任意排序。

当前网页补录旧预测须标reconstructed，不称当时可得样本；历史回放只按已留存取得时间筛选，不能用报告日期倒推可用性。实际业绩匹配须核对首次披露、重述版本、合并范围、每股分母和指标定义；缺依据不评分析师准确率。

## 首批/后续/缺口
已实现离线观察留存、源值冲突、显式修正关联及取得时点筛选，见下文教学与公开转述样本。待补机构原研报、实际业绩/重述原文配对与在线接口；不承诺数据齐全。

## 不据此宣称独家
[IPO_crawler](https://github.com/sqwqwqw1/IPO_crawler)提供已有招股/问询采集线索，未验收当前运行，问询专题仍聚焦逐项关联。[REITs工作台](https://kirisame.cn/reits-val)展示已有估值工作流，不证明开源或成熟。原调研里的零竞争不作为产品事实。


## 已实现：有界离线档案（2026-10-10）

现行入口为 scripts/forecast_archive.py，schema forecast-observations-v1 / 方法 acquisition-bound-history-1。

```sh
python scripts/forecast_archive.py references/examples/forecast-archive-teaching.json --archive-dir local-data/forecast-history --out-dir local-data/new-forecast-view
```

同一档案目录可以追加，新报告目录不能覆盖。id是一次观察，不是产品代码；同一id内容改变拒绝，新的取得/冲突需新id。每条保留机构、报告标识、财年/科目、单位/币种、发布日期（中国市场+08:00日历日）、含时区取得时间、口径/版本与来源摘要。历史筛选只按留存取得时点，不从发布日期倒推可得。日期仅到日时不能排序同日研报。未知显式schema/方法拒绝，金额单位与EPS单位分开。

同报告多源值冲突保留，不默选最新，不当作分析师修正。同财年新报告修正需要显式supersedesId和依据；期间/口径/归属不一致或同日顺序未知不计算差额。依据只为输入声明，不冒充原文核验。实际业绩/重述未配对，不评价准确率。

[教学输入](examples/forecast-archive-teaching.json)和[公开补录样本](examples/forecast-archive-public-summary.json)：只摘大智慧公开网页研报摘要所列美的2026/27/28年归母利润465/493/520亿元；第三方转述，华兴原研报未取得、合并范围未知，不采预测明细表或Wind数据。取得时点与网页字节摘要保留，不声称当时已可得。截止2026-09-30时三个补录观察均排除，见[历史缺口结果](examples/forecast-archive-historical-gap-result.json)。[当前补录结果](examples/forecast-archive-public-result.json)与[可读报告](examples/forecast-archive-public-report.html)不作投资建议。

本轮通过反例：发布日期不冒充取得时点、同报告源值冲突、同日新报告顺序不明、单位换算及未知口径、同id拒绝覆盖、未知方法/历史可得回填、时区跨日。机构原文样本/实际值及重述原文关联仍未完成，不能据此称完整预测历史服务。
