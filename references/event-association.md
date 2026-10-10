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

## 职责边界校准

公司问询、处罚、审计、更正的资料组织、证据关联与研究解释由research-workbench承接，规则库不作为公司事件库。当前实现是显式小样本事件台账和本页筛选；公司事件检索复用已有公告入口，尚不是全量事件搜索或自动历史时间轴。披露日与事件发生日分别保留，缺原件、发生日和规则均不回填。

cn-market-rules负责规则定义、适用条款、有效版本与情景口径；其事件页只能作有限规则例子。主包引用规则时须保留规则标识、版本/有效日期与原文来源，不能因引用到条款就自动认定事件违法。当前未接通规则版本查询接口，不把职责约定说成自动调用实现。本次不修改规则库工作区，不扩大采集范围。审计信息与处罚分别解释，财务/内控审计与审计师变更继续区分。

事件公开时点、混杂、选择偏差与事实/假设/版本边界见[研究方法卡](research-method-cards.md)。未取得行情与时分级公开信息时不称事件回测或因果推断完成。


## 原问询未取得时的限定替代（2026-10-10）

上海沿浦已按巨潮官方主体9900037900查询2026-01-01至2026-06-09问询相关披露，取得三份回复/独董意见索引；未取得独立原函。检索结果不证明原函不存在，原问询日期仍未知，不能拿回复披露日或第三方F10日期回填。

[取得缺口记录](examples/yanpu-inquiry-acquisition-gap.json)保留正确主体与查询窗口/响应SHA/标题。[三项回复内转引输入](examples/yanpu-inquiry-quoted-input.json)、[本地原页结果](examples/yanpu-inquiry-quoted-result.json)、[可读底稿](examples/yanpu-inquiry-quoted-report.html)分别定位主营业务/应收账款/关联交易至物理页1/17/27，问题与回复依据注明 quoted-in-reply，不冒充原函全文或所有子问题已核。原来样本和记录未覆盖。

问询入口新方法 explicit-association-2 保留 questionOrigin/originalInquiryStatus/originalInquiryDate；未知显式schema/方法拒绝，旧未声明版本输入仍输出当前实际方法。原函完整性、发函日期及实质回答充分性仍是缺口。
