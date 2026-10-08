# 公司一页纸研究

`python scripts/company_one_page.py INPUT.json --out NEW.json` 输出JSON、自然语言Markdown与HTML。资料较多时允许超过一页，不以压缩版式掩盖缺口。

最小输入：
```json
{"asOf":"2026-10-03","identity":{"name":"公司全名","market":"CN","code":"600001"},"business":[{"text":"原文业务说明","observedAt":"2025-12-31","publishedAt":"2026-03-31","sourceUrl":"https://example.org/report.pdf","locator":"PDF页12","basis":"source-statement"}]}
```
示例为参数格式，不是真实公司数据。market可为CN/HK/US。章节business/financial/valuation/events/risks均为条目列表；每项有text、所属日、披露日、来源、定位及basis（source-statement/calculation/assumption）。数值value必须配unit；缺章节显式留空。计算条目定位应指向公式与输入证据。引用不等于自动原文核验。

美国公司可增加secArchive：path为SEC原始companyfacts JSON、sha256为原始文件摘要、cik为十位申报主体编号。重新核对摘要、主体全名并解析八项US-GAAP标签；保留最近期末所有期间及版本冲突，不自动拼季度或选择冲突值。该入口不自动获取证券代码与CIK映射、业务、估值或完整财报。资料不全仍交付明确缺口，不宣称公司尽调已完成。


## 已有财报与估值结果联动

A股简报可传 financialReview（financialResult、originalResult、archives，格式同财报点评）。重新核对计算档案哈希、PDF哈希、代码、截止日、合并人民币范围，再从绑定档案重算指标及分组统计；快照与重算不一致时拒绝。单季数字与累计原文核验分开显示，支持字段保留可点击的PDF页码，缺业务或其他资料仍列缺口。

可选 valuationInputPath 指向 company_scenarios.py relative 的输入文件，复用源文件绑定及倍数计算；目标证券须在指定池内。显示估值比较日、财务期间和市值依据，假设市值不标成真实观测，负利润等不计算对应倍数。不自动把旧财年或半年倍数解释为TTM，也不把指定样本中位数称为全行业水平。

## 深度研究扩展
参见[专题研究分流](deep-research-profiles.md)。deepResearch:true启用扩展章节；未取得来源的节保持缺口。催化必须带触发和反证条件，预测必须带未来目标期和显式假设，不把预测标成事实。研发投入与研发费用、营业总收入与营业收入分别说明，不能按名称相近直接替换。

## 先建立判断
可选`judgment`列表，条目沿用text、observedAt、publishedAt、sourceUrl、locator，basis须为`research-explanation`，并提供scope（范围）、coreContradiction（核心矛盾）、alternatives（竞争解释）、counterEvidence（改变判断的证据）。正文优先展示此节；没有证据时不自动补判断。记录输入陈述不认证因果或投资价值。输出为输入独立快照，不随调用者后来修改而变化。
