# 组合模型扩展

运行环境需numpy。scripts/portfolio_models.py optimize|simulate 输入.json --out 新结果.json。输入asOf、frequency=daily/monthly、currency、assets（2至6个唯一代码，currency、basis=total-return、sourceUrl、history(date/value)）。日期完全对齐、递增且截至asOf；月度逐月连续，至少25个观察。来源声明不等于官方核验。

optimize：maxWeight统一单资产上限、frontierPoints=2至40；枚举箱约束边界并解二次规划，输出样本最小方差及从MVP到最大历史均值的有效前沿。历史算术均值与样本协方差年化，不是未来基准。仅无杠杆、非负、权重合计1；未支持行业分组约束、交易成本和稳健估计。

simulate：weights合计1、paths=100至10000、steps=1至1200、blockLength、seed。联合分块重采样保留同一观察期跨资产关系；每观察期无成本再平衡，输出终值收益与路径最大回撤分位。历史模拟不保证覆盖未知危机、相关性跳跃、违约和流动性断层；不是完整时变状态压力模型。不输出建议持仓。

验收：两资产MVP解析解、上限约束、前沿约束与风险单调、5000路径种子复现及异常拒绝。另已用000248、000191、000216第三方月度历史进行跨资产试跑；分红及分类未逐项官方核验，不是当时冻结的样本外验证。按需运行，不默认启动高开销模拟。

统一研究快照可用 portfolio-model-review，见[研究上下文](research-workflow.md)；按需执行优化、模拟或分阶段危机，不默认同时运行。
