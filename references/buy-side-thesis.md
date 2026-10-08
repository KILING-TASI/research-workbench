# 投资假设与兑现复盘

用户提出买方研究、投资逻辑验证或后续复盘时使用。复用已有资料，AI整理输入；不要求用户填写JSON。关键研究问题不清时询问，缺反证条件时先作为待确认假设，不擅自归为事实。

## 调用

形成假设或解释复盘结论前，按需阅读[研究判断与检验方法](research-methods.md)。检查支持与竞争解释、同源转载、情景一致性及口径变化；档案脚本检查材料和时点，不自动证明语义、因果或预测能力。

`python scripts/buy_side_thesis.py freeze INPUT.json --out-dir NEW_DIR`

`python scripts/buy_side_thesis.py review REVIEW.json --snapshot FIRST_DIR/result.json --out-dir NEW_REVIEW_DIR`

## 最小输入示例（教学假设，不是真实公司数据）

```json
{"entityId":"stock:example","question":"收入增长能否转化为现金回款？","asOf":"2026-10-05","hypotheses":[{"id":"h1","claim":"收入增长将改善经营现金流","verificationMetric":"收入、应收账款与经营现金流","invalidation":"收入增长而回款持续恶化","reviewBy":"2026-11-05","evidence":[],"gaps":["尚未取得对应报告"]}]}
```

复盘输入：
```json
{"asOf":"2026-11-05","assessments":[{"hypothesisId":"h1","outcome":"unverified","explanation":"报告仍未取得，不能认定兑现或失效","evidence":[]}]}
```

每条证据需提供id、source、summary、kind（original/third-party/assumption）、publishedAt、acquiredAt；首次证据还需stance（support/oppose/context）。日期均为YYYY-MM-DD。晚于截止日的披露或取得记录排除，不能用于事前依据。日期及内容由输入声明，不证明网页首次上线时点或原文真实性。

复盘结论为supported、contradicted、unverified。非待验证结论必须有截止日内的非假设证据；这是材料前提检查，不是自动语义或因果认证。支持和反对证据必须同时检查，数量不转成置信度或评分。

输出HTML、Markdown与JSON，按研究问题、假设、验证指标、失效条件、证据、缺口、复盘解释组织。原始快照保留并核对摘要；本地摘要不是数字签名，不能防止恶意同时改写内容与摘要。错误时修正输入或保留缺口，不补造证据。输出目录须为新目录。

## 原文定位复查

证据可附locator对象：path为本地PDF，sha256为文件摘要，page为从1开始的物理页，quote为原文引句。可用证据会核对文件摘要、页码与去空白后的引句位置。引句找不到时明确提示人工核对，不把它标作匹配。无locator保留未定位，历史快照不因新版能力改写。扫描件没有可提取文字时不认定引句匹配。排除的未来资料不进行定位认证。

原文引句定位只证明文字存在，不证明摘要语义、数据含义或投资假设成立，也不认证输入日期。

## 历史时点与复盘角色

可提供effectiveAt（生效日期）、recordedAt（留存日期）。已披露但尚未生效的事件可用于条件研究，不能描述为已执行事实。留存晚于截止日或未提供时标注尚未证明事前留存；所有时间字段仍是输入声明，不是网页历史可得性认证。

复盘区分复用首次材料、新补充历史材料、首次研究后披露材料。复用不等于新增兑现证据；新补历史不改写首次判断。首次报告分别列支持、反对、背景材料；未提供反对材料不等于无风险。晚于复盘截止日的材料单列，不参与本次判断。

## 证据适用性与版本失效

证据可提供applicableUntil（适用截至日，含当天）、withdrawnAt（撤回日期）、supersededAt（替代生效日）与supersededBy（替代证据标识）。替代日期与标识需同时提供；撤回或替代不能早于披露。

研究截止日超过适用期限，或撤回/替代已经生效时，材料单列排除原因，不作为当前有效依据。未来撤回不改写早期快照；复盘按原有时间声明列旧依据当前状态，保留首次输入。缺有效证据时不认定假设已验证。

这些字段需有原文或明确用户说明支持，不能给历史财报金额任意设有效期；历史事实仍可作为历史材料。当前仅检查声明，不自动查后续公告，不证明替代文档身份、完整范围或法律效力。没有失效字段不等于自动认证最新有效。

## 数值失效条件检查

假设可提供invalidationCondition：metric、unit、periodBasis、operator（lt/le/gt/ge/eq）、threshold。规则必须来自用户或明确标注的研究假设，不替用户默认设阈值。

复盘assessment可附observation：entityId、metric、unit、periodBasis、value、observedAt、evidenceId。对应截止日内有效非假设证据；引句未找到时先列未知。主体/指标/单位/期间不匹配、未来观测或证据缺失均不计算判断。有限数值使用Decimal比较，边界按比较符处理。

结果为触及阈值、未触及阈值或资料不足；不自动改变人工复盘outcome，不生成交易行动。指标定义及数值语义仍需核对，单次触及不能替代连续期间、因果分析或全文核验。来源日期和观测日期依然是输入声明。

## 多期指标条件

在 `invalidationCondition` 中添加 `requiredPeriods`，指定2至24个升序、不重复的报告期日期，例如 `["2025-06-30", "2026-06-30"]`。复盘 `observation` 改为列表，每项沿用单期字段并填写 `periodEnd`，分别绑定有效证据。

所有指定期间均满足才显示条件达到；缺期、单位不匹配或证据缺失保持未知。同一期多值需先解释冲突，不能静默择一。指定日期不自动证明完整连续披露；同一文件中的多个比较期不算独立来源。阈值结果不自动修改投资假设结论。真实金额机制验收也不能替代事前冻结预测验收。


## 证据变更影响

复盘可提供 `evidenceUpdates` 列表：每项包含 `hypothesisId`、`evidenceId`、`reason`、`source`、`changes`。changes仅支持 applicableUntil、withdrawnAt、supersededAt、supersededBy；不能删除或覆盖首次事实。报告列出受影响假设和验证指标，原判断保留。失效证据不能继续支撑确认结论，新版本使用新编号。变更来源为输入声明，须另行核验原文；影响清单仅覆盖当前档案显式关联，尚非跨报告全量依赖追踪。


证据变更须另外提供 `publishedAt`、`acquiredAt`，均不得晚于复盘截止日；取得日不得早于披露日。缺日期或晚取得的变更列入未采用清单，不反向改变历史判断。旧格式仍可读取，但缺日期声明不直接生效。所有日期依然是输入声明，不能证明事前留存。


## 深度研究的组织与交付

深研执行按[研究流程](research-operating-flow.md)组织问题、证据任务、经营机制与适用估值，交付按[深度研究标准](research-depth-standard.md)复查。当前脚本完成取数、核对或格式导出，不自动完成商业模式、原因和投资价值判断。已有数据足够时继续分析；关键资料失败时说明其影响并交付有限结论，不将研究提纲称为完整深研。
