# 原文差异处理与批次留痕

同一指标出现两个数值时，先确认主体、指标、报告期、单位、公告版本适用性。已登记字段不等于此次重新核验，不能按小数差异大小直接判定第三方有误。

## 显式原文优先

`reconcile_original_values.py` 接受发行快照、已登记核验字段及本地PDF目录。内部重新核对文件哈希、代码、页码、摘录及字段数值；仅支持当前重核器的发行价、申购上限、配售率。未知字段、缺文件、页码或文本不匹配时不应用，输出待补清单。调用前AI还应审查公告是否被撤回、更正，以及期次和口径是否适用；数值重核不证明版本适用性。

输出到新目录：`data.json` 为显式原文取值的新快照，`reconciliation.json` 为逐项处理明细。保留原快照；新快照的 `thirdPartyValues` 和 `sourceConflicts` 保存第三方原值、差异与采用原文的依据。再次处理同一快照不把已采用的原文值冒充第三方值。

调用参数模板见SKILL.md。输入结构沿用发行快照的records及核验字段的records→代码→officialFieldVerification；每项须含status=original-numeric-matched、value、sha256、page、excerpt、sourceUrl。只有取得对应PDF并实际重新核对成功才应用。输出的resolved-original-rechecked仅表示采用重新核对的原文值，不表示第三方平台承认错误、不认证首次公开日期、不保证获配。

## 公告查询明细

`announcementRefreshDetails` 列出本轮符合查询范围的各代码：matched-this-run（本轮查得链接）、no-match-this-run（本轮窗口空结果）、failed-cache-retained（失败且保留缓存）、not-attempted（批次数量或限流停止）。即使旧缓存有链接，本轮空结果也不能标成本轮新增匹配。

`announcementRefresh.covered` 包含旧链接，仅用于缓存覆盖统计；查询范围是近期发行人及缺缓存的对象，eligible、outOfScope和pending分别说明范围及未尝试对象。pending=0仅表示本轮选定查询范围全部尝试；失败数、空结果及原文数值核验状态仍需单独说明。每次更新都需用户主动触发，不做后台轮询。
