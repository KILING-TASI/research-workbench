# 限定事件关联与研究解释

开发记录：2026-10-09，待审，未发布。围绕一个公司明确整理问询、回复、处罚文件、审计意见、审计师变更、更正和重述；不自动采集，不替规则库解释适用规则，不给统一风险分数或退市概率。

## 可运行的小案例

```bash
python scripts/event_review.py references/examples/event-evidence-example.json --format html --out local-data/new-event-review.html
```

输出须为新文件。Python3.11+标准库可生成声明证据报告；提供本地PDF路径后原页检查另需pypdf。示例来源上海沿浦2025年报问询回复：引用原函编号→公司回复内信用政策问题。原独立问询未取得、事件日期未知保留空值；同一回复中引用问询不等于原问询已认证。输入未附PDF，不把教学运行中的声明状态写成原文已核。

本地已有原件选择页1/17检查，原件不发布。仅这一条公开回复链有真实证据验证；处罚、审计、更正、重述目前通过声明接口/边界测试，未完成对应真实案例。不将现有案例泛化到全部七类事件。

## 输入与结果

使用event-evidence-ledger-v1：entity、asOf、documents、events、relations。文档保留entity/publishedAt/version/source/sha256；证据使用documentId/physicalPage/quote。事件保留kind、entity、eventDate、reportPeriod、summary、researchQuestion、limitation，未知日期为null，不拿披露日回填。审计意见额外独立opinionText与auditScope（financial-statements/internal-control/other），审计师变更独立auditorChange；两者不可替代。

relations明确from/to/type/reason/evidence；responds-to是问询到回复，corrects/restates由明确文档声明，context-for只是研究背景。没有足够依据不声明关联。输出保留工具、输入契约、规则版本与逐条原页状态，关系不会自动替换历史财报数据或判违法。

与现有核对/穿透衔接时保留同一主体、文档摘要与物理页；财务数值仍按独立核对接口处理。事件关系不调用外部仓库、不自动改动持仓/事实，不把处罚标签等同某资产损失。

## 报告交互

HTML可按当前表内文字筛选、按首列名称排序。它只改变显示，不重新计算、换情景或修改未知值；保存输入及方法摘要，新结果另存。分享前检查输入里的私人路径与内容。本批没有截图或浏览器视觉验收，不将HTML生成成功视为视觉通过。

[本次实际生成的HTML预览](examples/event-review-20261009.html)使用上述输入，不附PDF；页码仍为声明状态，不把本地另核结果冒充可公开复跑的原件认证。

## 新增有限更正案例

[国中水务更正输入](examples/correction-evidence-example.json)与[核对记录](examples/correction-validation.json)来自2026-05-06官方公告，选定页1/4短引句在新取得的原件中匹配。比例由20.89%更正21.89%，资金往来表单位由万元更正元；不是自动替换旧金额、财务改善或审计意见解除结论。原/修订全文尚未配对，处罚案例未新增，审计意见只在更正文件中出现，不作为独立审计意见认证。

浏览器截图曾重试，但file协议被安全策略明确拒绝且禁止绕过，因此三个本地报告的截图与视觉验收仍未完成。HTML生成、原页文字匹配、浏览器视觉分别记录，不合成截图。

[实际生成的更正HTML](examples/correction-review-20261009.html)使用公开短引句输入，不附原文；公开运行仍显示声明状态。
