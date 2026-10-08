# 基金池快照、分期归因、差异与条款检索

所有计算仅用户主动触发，复用已获取资料。经理观点只从年报提取，不抓取路演或采访。当前会话中用户选定基金池/组合后后续问题复用其集合；条件变更明确更新，不把会话记忆称永久自动记忆。参数由AI整理，不要求用户填写JSON。

## 调用

```text
python scripts/fund_enhancements.py pool-snapshot INPUT.json --out NEW.json
python scripts/fund_enhancements.py attribution-panel INPUT.json --out NEW.json
python scripts/fund_enhancements.py clauses INPUT.json --out NEW.json
python scripts/fund_enhancements.py export INPUT.json --out NEW.json
python scripts/fund_enhancements.py screen-to-pool INPUT.json --store USER_DATA --out NEW.json
```

pool-snapshot输入pool（name、codes）及cards（fund_research.js scan结果中的cards，可附holdingsOverview含报告期与來源）。逐基金显示核心指标、窗口、持仓是否取得和缺项摘要。先按需采集或扫描；代码未覆盖保留missing。历史区间不同不自动排名；不以最大回撤阈值冒称未来安全。持仓概览必须来自已取得报告，不能由收益曲线推断。

attribution-panel输入periods[{start,end,input,reason}]，input为research_library.brinson输入；缺期不给input。已有单期重新校验后并列配置、选择、交互及快照超额，统计已有期间正负次数。空档保留，不填零、不认定经理能力稳定；缺期不调用完整累计链接。起止窗口须不重叠。每期报告快照边界在结果顶部与分期解释中注明。

similar沿用fund_diagnostics.js similar，现在额外显示differences：双方独有已披露股票（各最多5项）、覆盖率和净资产重合摘要。无行业分类核验与费率数据则列不可比较项。独有持仓仅在输入快照内成立，不能将其说成当前绝对不持有。

clauses输入documentResult（research_library.py documents结果）及query自然语言。固定主题：港股投资限制、流动性条款、业绩报酬、封闭期、巨额赎回。AI先用对应关键词取得原文候选，再按主题检索。返回页码、摘录、哈希与候选标签；标签仅主题，不判断允许投资、条款生效或实际执行。无命中不当不存在。例“查看这个基金合同里的巨额赎回条款”→documents用巨额赎回定位→clauses query=巨额赎回→核对全文上下文回答。

export输入template、result及可选title/notes。模板single-fund、fund-pool、fof、cross-asset分别限制对应结果类型并嵌入专题边界。FOF接recursive-disclosed-holdings结果，不把基金对比冒称穿透报告。生成JSON快照与Markdown，Excel继续使用export_research_xlsx.mjs；综合HTML继续使用fund_report_presentation.js。模板是现有结果导出，不触发新的完整深度研究。

screen-to-pool输入screenInput（research_outputs.screen相同）及poolName，输出筛选结果与追加后的基金池。只添加selectedCodes，缺指标不会添加。之后如有同报告期持仓，直接用该基金池代码限定similar/reverse。保存目录是用户自己的数据目录，旧池版本不覆盖。

## 已有组合能力的使用

收益、波动和同一峰谷区间贡献使用fund_research.js contributions。每期复利贡献不是一律用初始权重乘最终单品收益。调整前后用simulate；压力值称一次情景损益，不称未来最大回撤。穿透行业敞口及交易摩擦不足时保留缺项。调仓边际影响可视化、多季度完整时序、持仓因子、FOF大类汇总和档案版本差异未在本入口新增，不宣称完成。

多期归因面板：每期保留industrySystem、industryVersion、benchmarkId、portfolioId、weightScope、currency声明及权重报告的可得时间状态。声明缺失或各期不一致时仍列单期结果，但正负贡献次数留空，不能合并评价持续性。声明一致只说明输入一致，仍需原文核验。基金池指标全部为空时明确写未取得，缺口摘要使用中文指标名，不将字段存在当作数据取得。
