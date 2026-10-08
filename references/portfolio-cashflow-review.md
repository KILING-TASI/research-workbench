# 组合出入金与收益观察

用于回答“追加了钱以后，账户增长到底有多少是收益”。这是已有账户估值的复盘入口，不是组合交易模拟或配置求解器。AI整理输入，用户无需填写JSON。

```text
python scripts/portfolio_cashflow_review.py INPUT.json --out-dir NEW_DIRECTORY
```

输入需要`cashFlowCoverage: declared-complete`、非空`basis`和按日期递增的`observations`。每条记录有`date`、`beforeFlowValue`、`externalFlow`、`afterFlowValue`；现金流正为投入、负为取出，流后资产=流前资产+现金流。首条流前资产为期初本金。所有外部流必须列出，区间末也须估值；同一账户币种和金额单位一致，估值包含现金及已计费用。

时间加权收益为各次流前资产/前次流后资产的连乘减一；XIRR使用期初、每次投入/取出及期末假设变现。TWR是累计收益，XIRR是年化，两者不直接相减。非传统现金流可能多根，入口留空而不挑任意根。

生成中文HTML/Markdown、逐段结果和报告索引清单。缺现金流完整性或流前估值拒绝；不把总资产增长当收益，不认证实际账户。组合方案P0中的现金流交易规则、阈值再平衡和配置求解仍待实现，不能用本观察入口宣称完整引擎已交付。

币种currency为三位大写声明；amountUnit必须为base（基本单位）、thousand（千单位）或million（百万单位）。同一输入不混单位，入口不自动缩放。报告展示逐期流前资产、投入/取出、流后资产和分段收益，支持统一结果检索。

统一入口：python scripts/start.py cashflow --input INPUT.json --out-dir NEW_DIR；随后cashflow --continue-from OLD_DIR --out-dir NEW_DIR沿用估值资料，另存新报告。直接报告也保存接续请求与区间。更新估值/出入金由AI准备新输入，不自动补历史，不将复用称最新账户结果。

标准库教学例：python scripts/start.py cashflow --input references/examples/example-cashflow-review.json --out-dir NEW_DIR，无需NumPy或Node；示例虚构，报告及导航保留教学标记。

可选accountLabel为研究起名，例如长期账户；单行1至100字，不要求真实账号。报告和检索请求保留名称，后续可按名称找回；名字不是账户身份核验。

报告首段分开说明账户金额变化、净外部投入/取出与剔除出入金的损益，避免将新增本金当收益。页面金额按声明单位明确换算为币种基本单位；JSON数值仍保留原输入单位。时间加权累计收益与资金加权年化XIRR另列，不能直接比较判断择时。完整性仍为输入声明，不认证实际账单。
