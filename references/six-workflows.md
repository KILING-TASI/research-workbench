# 统一脚本：常用命令参考

文档版本：1.0 · 更新日期：2026-10-05 · 定位：参数参考

产品范围以[现行功能说明](current-capabilities.md)为准。本页保留原链接路径，介绍统一脚本的常用命令；命令数量不对应产品的六类研究场景，也不是完整命令目录。

## 调用约定

在Skill根目录使用Python 3.11+执行。`<...>`是需要替换的参数；含空格的路径加引号。`--workspace`指定用户数据目录，`--out`必须是新结果文件。工具拒绝覆盖已有输出。

```text
python scripts/research_pipeline.py --workspace <用户数据目录> --out <新结果.json> <子命令> <参数>
```

先按[执行契约](execution-contract.md)检查输入和环境。下表中的命令都接在上面的全局参数之后。

| 任务 | 子命令与参数 | 输入与结果 |
|---|---|---|
| 按代码采集 | `collect --kind <品种> --codes <代码,代码> --start <YYYY-MM-DD> --as-of <YYYY-MM-DD> [--refresh] [--market <0或1>]` | 品种支持fund、stock、etf、bond、convertible、government-bond、credit-bond；按指定范围获取或读取缓存，债券须明确沪深市场 |
| 批量采集 | `collect-batch <批量请求.json>` | 逐项保留组件状态、来源、时间与错误，支持有限重试和同参数断点续采；格式与边界见[独立采集](standalone-collection.md) |
| 保存原文证据 | `evidence <证据输入.json>` | 登记主体、数值、原文路径、页码和摘录；本命令本身不判断金额是否与摘录一致 |
| 同区间比较 | `compare <比较输入.json>` | 共同日期的收益、回撤和样本充分时的波动；输入和口径见下文 |
| 冻结预测复盘 | `validate <预测实际对照.json>` | 检查冻结与发布时间先后，计算误差；不验证外部档案中的冻结真实性 |
| 基础组合快照 | `portfolio <组合输入.json>` | 按输入市值计算权重、集中度、已知分类敞口及给定冲击损益；此命令不自动穿透或计算交易成本 |
| 档案差异 | `review <首次档案.json> <最新档案.json>` | 比较同类型档案字段，保留首次档案摘要；变化不自动等于原判断失效 |

`--refresh`触发主动获取；不使用时按缓存规则处理，缓存缺失会列出缺口。股票财务摘要与[专门的三表入口](stock-statements.md)分别说明，字段取得不等于原文核验。批量上限、重试次数和续采参数统一在[独立采集](standalone-collection.md)维护。

## 输入格式要点

- **evidence**：securityCode、field、value、unit、currency、period、publishedAt、statementScope、periodBasis、sourceUrl、documentPath、page、excerpt、reviewer。原文文件须存在；证券代码为六位数字。记录证据不代表已核验原文金额。
- **compare**：asOf、rows，可选start和benchmarkCode。每行提供code、comparisonGroup、basis、history，可选frequency。basis支持nav-with-distributions、qfq、total-return；历史行含date及nav或close。基金分红保留原始distribution说明，按可解析事件处理。可运行的教学输入见[比较示例](examples/comparison-example.json)。
- **validate**：rows每行含id、unit、modelVersion、prediction、actual、frozenAt、inputMaxPublishedAt、actualPublishedAt。同批次单位和模型版本一致，actual须为正数。时间须带时区；输入不晚于冻结，冻结早于结果发布。输出平均绝对误差、P90、最大绝对误差和低估率，不称作投资准确率。
- **portfolio**：asOf、baseCurrency、holdings。持仓行含code、marketValue、marketValueCurrency，可选assetClass、industry、currency；shocks按资产类别声明百分比冲击。市值需统一币种，压力覆盖不足留空。

比较组由输入声明，仍需核对是否可比；复权价格代理不等于总收益。缺少匹配基准，不计算超额收益。更完整的组合穿透、贡献与模型研究使用[持仓与组合入口](holdings-portfolio.md)，不受基础快照命令范围替代。

## 研究任务与复查

研究任务由主包脚本管理。`--store`必填，指向Skill安装目录外的用户档案目录；每个任务单独保存为文件。AI整理参数，用户无需自行填写结构化数据。

```text
python scripts/research_tasks.py --store <用户档案目录> create --title <标题> --snapshot <首次档案.json> --review-date <YYYY-MM-DD> --claim <判断> --invalidation <失效条件>
python scripts/research_tasks.py --store <用户档案目录> due --as-of <YYYY-MM-DD>
python scripts/research_tasks.py --store <用户档案目录> review <任务ID> --changes <变化档案.json> --conclusion <结论> --next-review <YYYY-MM-DD> --invalidation-status <yes或no或unknown>
```

复查须匹配首次依据摘要，不自动判定买卖或创建定时任务。更多上下文、来源链和模板说明见[研究上下文与模板](research-workflow.md)；历史实测见[验证范围](validation-scope.md)，与当前命令规范分开维护。
