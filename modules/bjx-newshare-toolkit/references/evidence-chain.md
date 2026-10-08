# 贯穿研究过程的证据链

本规范用于统一研究输出和后续模块接口。现有脚本字段保留，按下表解释；scripts/research_evidence.py已适配发行事实及公司原文证据，详见research-evidence-interface.md；其余计算派生节点可显式提供，尚未全部自动迁移。

每个对结论有影响的数值必须区分原文观测、第三方观测、用户假设、计算结果或缺失。原文观测带来源、页码、披露日期、文件哈希、核验状态；非PDF数据页码为null并说明定位方式；不知道的日期与来源留空，不补造。

统一证据节点字段：

| 字段 | 含义 |
| --- | --- |
| id / subject / metric | 唯一证据ID、证券或发行主体、指标 |
| kind | original / third-party / assumption / derived / missing |
| value / unit / basis / period | 数值、单位、统计口径、所属期；缺失为null |
| sourceUrl / documentSha256 | 来源地址、原始文件SHA256；假设可为空 |
| page / locator / excerpt | PDF页码从1开始；表格行列沿用脚本从0开始；非PDF提供记录定位 |
| publishedAt / publicationVerification | 披露日期及其证据等级；目录日期不证明首次公开时点 |
| retrievedAt / asOf | 获取时间、研究截止时点；不以获取时间替代披露日期 |
| verification / limitation | 原文数值匹配、仅摘录匹配、第三方未核验、用户声明、派生或缺失；逐项说明限制 |
| dependsOn / formula / parameters | 派生结果引用输入节点ID，保存公式与参数；不伪造派生结果的原文页码 |

既有字段映射：issuance_facts的facts字段直接提供value/unit/basis/page/excerpt/sourceUrl/publishedAt/documentSha256/verification；公司研究的evidence提供原文定位，financials.lineage.evidenceIds关联数值，documents.sha256对应documentSha256；获配计算的factEvidence沿用发行事实，ratesPct/gainPct和费用参数属于声明假设，不能标为原文核验；预测inputs.sha256对应输入文件哈希，availableAt是调用者声明的可得时间，不能自动升级为publishedAt；recordHash仅证明档案内容一致，不证明原文真实性或可信时间。

证据状态不得因被计算引用而升级。摘录匹配不等于数值语义已核验；计算结果正确不等于输入真实。冲突节点保留候选来源与版本，结论字段留空。更正公告新增版本，派生结果记录采用哪个版本。证据依赖不能循环；缺少关键依赖时输出缺口，不输出确定结论。

输出研究说明时，以“输入—处理—输出—留痕”组织，并附关键数值证据表；无需用户手动填写已可自动取得的字段。原始档案不改写，导出或展示可按本规范映射，保留原字段以便回查。

发行市盈率按利润年份、扣非前后、发行前后股本和超额配售假设分别记录。同公告的10.00倍与10.21倍等不同股本口径不自动认定数据冲突，也不静默只选一个值。目录路径日期、正文落款日期和发行日程中的计划披露日分别保存；不以其中任一单点证明历史首次公开时点。仅复算获配资金时，排除为执行综合引擎而提供的假设卖出日期、涨幅及收益字段，不作为真实收益或年化依据。
