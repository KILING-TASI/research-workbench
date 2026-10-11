# 问题导向的证据复查

本专题借鉴公开网站的流程组织方式，代码与教学数据由本仓原创实现，没有复制对方源码、报告或数据。先看资料能支持什么，再看计算与缺口；不把网页能打开或程序退出成功当成原文已核验。

## 单仓最短流程

安装本仓即可运行，不要求作者缓存、其他仓库、付费终端或网络取数。示例是原创教学资料。

```text
pip install .
research-workbench script evidence_status_review review --input examples/expansion-teaching/evidence-status-teaching.json --out-dir reports/question-review
```

输出新目录中的 `report.html`、`input.json`、`result.json` 和 `receipt.json`。先读结论和缺口，再展开底稿。换资料或假设时另用新目录，历史结果不覆盖。输入字段见示例；示例链接与哈希为教学占位，不能冒充真实证据。

资料状态分别列出取得、空表、失败、未授权、过期、未提供和截止后资料；估算、代理、披露类型保留。教学预期：4 项中 3 项有缺口；不会输出“资料齐全”或投资结论。

完整真实案例可沿用财报专业仓已归档的[美的现金覆盖案例](https://github.com/KILING-TASI/cn-financial-reconcile/tree/main/examples/midea-cash-coverage-20261010)。它验证该案例所填证据与现金路径，不能推广为全行业准确率。工作台只组织问题和证据，财报计算仍在专业仓。

## 真实研究与验收边界

教学只验收流程和边界，不作为真实研究案例或准确率证据。实际研究须填入有权使用的原始来源、期间、单位和版本，按报告提示复核原文与缺失项。第三方代码、公告、研报和数据仍按各自权利范围处理。
