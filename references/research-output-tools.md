# 筛选、笔记与快照导出

## 指标筛选与对比池

`python scripts/research_outputs.py screen 输入.json --out-dir 新目录`

输入result为historical结果（assets）或fund_research.compare结果（comparisons），conditions为metric/op/value数组。支持CAGRPct、annualVolatilityPct、maximumDrawdownPct、Sharpe、Sortino、Calmar；op为lt/le/gt/ge/eq。收益、回撤、波动用百分点：20表示20%，不是0.2。严格小于不包含边界，空值或非有限数不通过，输出selectedCodes、excluded及unknown。

例如条件 `[{"metric":"maximumDrawdownPct","op":"lt","value":20},{"metric":"Sharpe","op":"gt","value":1.2}]`。同时提供historyInput（原历史输入）可生成comparison-input.json，仅含入选标的与原基准，等权只用于统计比较。没有全部入选标的历史则阻止入池。结果可直接调用 `node scripts/fund_research.js compare comparison-input.json 新比较.json`。不同窗口指标不要混池排序。

## 用户笔记

`python scripts/research_tasks.py --store 用户任务目录 note 任务ID --text-file 笔记.txt`

文字以user-note追加，带日期与独立ID，原始sourceRecord与snapshot不改。笔记是用户观点，不是来源事实或工具结论。show/export可读取笔记。

## 快照简报

`python scripts/research_outputs.py snapshot 输入.json --out-dir 新目录`

输入title、result（跨资产组合/多基金比较/穿透结果）；可选notes数组（kind=user-note/text/at）。可选taskId、taskStore，自动挂载该任务已保存笔记。返回result.json标准快照及report.md，保留结果来源URL、必要假设、未知字段、风险说明和用户笔记。仅导出实际结果，不补造缺失；底层缺来源时明确提示。内部执行日志、验收字段、原文件路径不进入对外简报。原结果哈希写入标准快照，用于复查。

`node scripts/export_research_xlsx.mjs 标准快照result.json 新报告.xlsx`

Excel可选，需要安装环境提供@oai/artifact-tool；非包内自带依赖，缺少时提示并保留Markdown，不自动安装。可设置ARTIFACT_NODE_MODULES为环境依赖目录。两张表为研究结果、来源与说明，数值保留数值类型，基金代码保留文本前导零；用户文字不作为公式执行。导出是静态研究快照，不是假设调整后自动重新计算的Excel模型。RESEARCH_EXPORT_QA=1可生成页图与检查结果，普通使用不默认产生辅助文件。

## 调整情景与批量轻量诊断

`node scripts/fund_research.js simulate 输入.json 新结果.json`

输入historyInput为包含原有及新增资产的总收益历史，beforeWeights和afterWeights为代码→权重对象（非负合计1），可选scenarios[{name,shocksPct:{代码:百分数}}]。统一联合共同日期后比较历史收益风险、相关性、标的权重HHI及一次假设冲击损益；缺某资产冲击则该情景留空。支持股票、ETF、基金等统一币种历史输入。标的集中度不代替穿透行业或个股集中度；历史统计无费用周期恢复权重，不是下单预览，不提供调整建议。

`node scripts/fund_research.js scan 输入.json 新结果.json`

输入codes（最多50个）和historyInput。先用collect-batch取得历史资料，再轻量逐标的输出实际区间、指标解释、来源及风险；缺数据/失败逐只报告，不拖垮其余对象。扫描不运行深度分析或蒙特卡洛，不按不同区间做可靠排名。

合同风格漂移与回撤归因：需把有效合同条款映射到量化范围，及取得期间行业/个股持仓与收益。快照权重变化不能证明主动交易，净值相关或回归不能直接替代行业/个股贡献。资料缺失时不强行计算漂移百分比或归因。
