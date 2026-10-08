# 缺口分析、版本知识卡与来源交叉核对

三个入口均通过 `scripts/research_pipeline.py --workspace 用户数据目录 --out 新结果.json 命令 输入.json` 调用。结果文件不覆盖；知识卡保存到用户目录 `research-data/knowledge/品种/六位代码/`，不会随安装包携带用户PDF。

## 缺口分析

`gap-analysis` 输入示例：

```json
{"resultPath":"/absolute/模板结果.json","depth":"full","requiredPeriods":[{"code":"110011","component":"完整持仓","period":"2024-06-30"}],"availableReports":[]}
```

basic仅检查本次模板计算与来源；full另外列出后续尽调常需的持仓、费率、穿透或流动性资料。requiredPeriods/availableReports由研究者明确列出，程序报告尚未登记的特定报告期。每项写缺口、对本次结果的影响、建议补充项和高/中/低工作优先级。这是规则排序，不是统计意义的结论可信度分数；未登记的数据无法自动断言不存在。

## 版本知识卡

`knowledge-add` 输入需明确 `code`、`kind`、`period`、`publishedAt`、本地 `sourcePath` PDF、可选 `sourceUrl` 和 `verificationPath`，以及至少一个事实。知识卡按“品种＋代码”分开存放，避免六位代码跨资产串档：

```json
{"code":"110011","kind":"fund","period":"2025-12-31","publishedAt":"2026-03-31","sourcePath":"/absolute/report.pdf","sourceUrl":"https://publisher.example/report.pdf","verificationPath":"/absolute/verify-result.json","facts":[{"id":"income.0","field":"interest_income","originalLabel":"1.利息收入","value":"619685.16","unit":"CNY","currency":"CNY","basis":"annual","statementScope":"fund-all-share"}]}
```

程序按PDF哈希归档副本、追加有前版哈希的JSON版本，不覆盖旧报告。新报告期显示 `new-period`，同一期数据更正显示 `revised`。`knowledge-show` 输入 `{"kind":"fund","code":"110011"}`，校验版本链后列出每版报告、哈希、字段和证据等级。只给代码且跨品种有多个匹配时会要求明确品种。独立安装只需提供本地PDF路径；没有官网原文核验结果也可导入，但证据等级保持未核验。

`official-original-fields-verified` 只在提供通过的 `verify_original.py` 结果，且PDF哈希、来源地址、报告期、发布日期、字段ID、原文行标签与数值逐一匹配时设置。核验程序的官方域名清单仍由研究者提供并核对；知识卡不能单独证明原文历史首次上线时间。其他情况标为 `supplied-pdf-unverified-fields`。版本哈希用于发现意外修改，未使用签名或外部不可篡改存储。

## 交叉核对

`cross-validate` 输入 `asOf`，并提供 `observations` 或 `knowledgeCodes`（建议写 `[{"kind":"fund","code":"110011"}]`），可设置 `absoluteTolerance` 与 `relativeTolerancePct`。知识卡从当前 `--workspace` 读取，输出包含具体版本文件路径。一个观测要写对象、字段、报告期、期间类型、合并/母公司范围、计价口径、单位、币种、数值、发布日期和来源标识。

只在以上口径完全一致时比数值。不同报告期、币种、单位或报表范围显示在 `incomparable`，不换算或平均。相同文件哈希或同一发布方的数据只算一个独立来源；输出一致、差异或独立来源不足。发布晚于截止日的数据排除；抓取晚于截止日的副本标为事后取得，不冒充冻结输入。来源等级字段是输入或知识卡记录，交叉核对本身不证明供应商身份，也不自动推断差异原因。ETF IOPV等授权实时数据尚未接入。

来源分组同时按文件哈希、发布方和来源ID合并，可识别同一发布方多份文件及转载链；分组依据仍依赖来源登记，不能认证上游独立性。即使独立来源不足，`numericAgreement`也单独保留数字差异，避免把缺少独立来源误读成没有冲突。

## 跨期口径与可复算研究

`cross-period-review`使用相同统一入口。完整参数与报告、重放示例见[跨期证据研究](cross-period-review.md)。不同报告期的变化单独研究，不与同一期多来源冲突混用；必需口径缺失或不一致时，变化值留空。报告先说明变化和研究意义，再展示原文依据及缺口。

验收范围：110011两期真实基金年报完成版本归档；2025年利息收入字段与原文核验结果关联。差异与重复来源使用明确标注的模拟观测验证，不能称真实第三方数据已经交叉核验。FOF底层报告自动关联继续暂停。
