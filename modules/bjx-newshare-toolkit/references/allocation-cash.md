# 整手获配与边际资金档位、现金时间账与占用分析

scripts/allocation_cash.py single|collision 输入.json --out 新结果.json。核心计算标准库Decimal，不运行模型优化。仅使用明确输入的配售率和卖出涨跌幅，P75/P50/P25名称不证明输入来自统计分位。

single必填：code、price、budget、maxShares、ratesPct（P75/P50/P25百分数）、rateBasis、gainPct（同三档百分数假设）、applyDate、refundDate、saleSettlementDate。minShares默认100。人民币预算最多两位小数；申购上下限100股整倍数。日期均为已确认或明确假设日期，不自动按T+2推算，卖出结算日不是上市日。

可选factsStore与asOf接入第一批事实库：读取已核验price/maxShares/refundDate；存在冲突或缺项即停止，输入与事实不同即拒绝。目录披露日仍不证明历史首次公开，输出保留factEvidence与publicationVerification。不会自动读取实际ratePct进入情景。

```json
{"code":"920022","price":"10.90","budget":"5000000","maxShares":745700,
 "ratesPct":{"P75":"0.03","P50":"0.025","P25":"0.02"},"rateBasis":"示例假设，不是预测",
 "gainPct":{"P75":"30","P50":"10","P25":"-20"},
 "applyDate":"2025-09-09","refundDate":"2025-09-11","saleSettlementDate":"2025-09-22",
 "opportunityRatePct":"2","fees":{"commissionPct":"0.02","minimumCommission":"5","taxPct":"0.05","slippagePct":"0.1"}}
```

申购股数按预算向下取整100股、受公告上限和最低数量约束；整手获配为100*floor(申购股数*配售比例/100)。零股结果未知，只给最多额外100股的数学上界，不是概率。配售率0时门槛不可计算且整手为0。输出百股门槛可达性、距现有预算新增资金（扣除未使用现金）及新增申购资金两种口径；下一整手档位超过上限则留空。

分段自然日：申购日至退款日前，实际申购金额全部占用；退款日至卖出结算日前，仅整手获配本金占用。资金日=sum(金额*自然日天数)，机会成本=资金日*年机会成本率/365。不是把整个获配本金都在退款日释放。

卖出成交额=获配本金*(1+假设涨跌幅)。卖出费用包括百分比佣金及最低佣金、税费、滑点；无获配不收卖出费。费用率均为用户假设，未宣称默认费率是最新法定费率。financingRatePct与borrowedFraction计算分段借款成本，假设卖出结算统一支付；不模拟每日付息与追加保证金。净结算现金扣除费用与融资成本，亏损会减少后续可用资金。profitAfterOpportunityCost另扣基准机会成本；借款资金与机会成本可能重复，按用户实际资金来源解释。

输出申购资金收益率与资金日简单年化，不是未来预期或复利收益。未纳入未知零股，对正收益可能低估收益，对负收益可能低估损失；不把整手情景视为最坏损失上限。

collision输入totalFunds及issues（1至50项single输入，不可重复代码）。逐档建立现金账：申购扣全额，退款释放未获配本金，卖出结算计入净现金。默认同日先申购后释放；有明确到账可用依据才设置sameDayReleasedFundsUsable=true。输出是否可行、最低现金、所需额外初始资金及逐日账。允许假设盈利参与后续周转，应与实测区分。仅检验输入方案，不自动寻找资金分配或提供申购指令。

能力名称调整不改变single/collision命令、输入字段或旧档案。关键数值按evidence-chain.md区分事实、假设和派生结果。

新增transferFeePct（过户费百分数）与saleCostBreakdown逐项费用。未给费用字段按零假设，不代表免税；未按券商分项舍入或结算账单核验。多组联合假设见[情景研究](scenario-engine.md)，使用现有精确整手与资金日计算，不默认为概率或忽略未知余股。

additionalSharesAssumptions按P75/P50/P25可声明0或100股额外余股。有比例零头且总假设获配不超过申购股数才接受；不是实际获配证据。wholeLotShares继续为比例整手，allocatedSharesAssumption为含声明余股的合计；费用/资金日/退款依合计重算，下一比例整手档位仍依比例部分。联合情景入口自动把余股作为独立分支，不混入基线。
