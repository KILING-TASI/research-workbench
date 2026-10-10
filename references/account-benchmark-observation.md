# 账户与基准差异观察（开发中，教学验收）

用于回答：账户赚得和产品、基准一样吗？差异有哪些证据支持的原因？本批只验收教学输入，不索取真实账户，不从期末截图重建路径。

从仓库根目录运行：
```sh
python scripts/account_benchmark_review.py references/examples/account-benchmark-teaching.json --out-dir local-data/account-benchmark
```
输出 input.json、result.json、报告.md、报告.html；目录须为新路径。

输入账户复用出入金复盘的流前/流后估值与现金流完整声明；产品和基准提供覆盖共同起止日的总回报序列。统一币种、分红处理、基准版本。总回报序列分红处理为输入声明，不由本入口复权认证；不换汇、不插值，不自动缩短期间。

累计账户TWR与产品/基准累计收益可作百分点比较；年化XIRR单列，不能直接相减。教学样本账户累计15.5%、产品20%、基准12%，账户与基准相差3.5个百分点。没有配置路径、买入起点和现金占用证据，三个原因均为未知，不编造贡献。已有文字线索只保留为未独立核验说明，不计算归因。

覆盖反例：区间/币种/分红/基准版本冲突拒绝；现金流不完整、只有期末估值拒绝。未完成真实账户验收、自动配置/择时/现金贡献拆解与浏览器视觉验收。报告是观察，不提供交易建议。


[本批教学报告](examples/account-benchmark-report.html)（下载后查看，未完成浏览器视觉验收）；[计算结果](examples/account-benchmark-result.json)。


输入schema可显式声明 account-benchmark-observation-v1，方法 account-benchmark-observation-1；未知显式版本（含null）拒绝，不静默执行。未声明版本的旧教学输入允许，结果记录实际schema及方法，旧产物保持冻结。
