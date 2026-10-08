# 持有人结构与份额分母核验

调用：`python scripts/fund_holder_units_review.py INPUT.json --out NEW.json`。输入holderSnapshot、shareFlowSnapshot两条已提取JSON路径及shareClassOrder（按原表核对的类别列顺序，如A、C）。相对快照路径按输入目录解析，新输出须不存在；需要pdfplumber与pypdf。

持有人快照包含code、reportDate、sourcePath、sourceSha256、entries。每类别行含shareClass、institutionUnits、personalUnits、totalUnits、reportedInstitutionPercentage、reportedPersonalPercentage、physicalPage、originalCells、tableBBox；合计行可保留，但不重复相加。

份额快照包含同代码、期间及来源，flowRows固定opening、closing、subscription、redemption、split五项。每行含原label、按类别顺序的values、physicalPage、originalCells、tableBBox。横线保留原表空金额标记，默认拒绝解释为零；条件假设规则见下文，缺失行不得自动填零；拆分变动可以为正或负，其余数量不可为负。

入口复查PDF哈希、结构、前页代码与自然年中期/年度报告年份；按表格坐标重新核对应原行，再核机构+个人份额与期末一致，期初+申购−赎回+拆分=期末，披露比例在两位小数舍入容差内一致。原行标签须对应计算项目，不能互换申购、赎回等行。

输出result按类别列份额数量、比例和变化，不产生资金流估值；source与dependencies保留原件和输入哈希。只核所选原表，不认证官方真实性、全部报告或类别去重关系。类别顺序须事先核对；户数不等于去重人数，盈利投资者数量指标仍需另核统计定义。

低机构比例及未达到单一投资者20%披露阈值不代表流动性安全；期末份额减少不代表同额净现金流。份额时点、份额单位与资产净值、净值收益分别呈现，不给安全评分或未来盈利概率。

路径兼容：原件sourcePath的相对路径按各自快照JSON目录解析，可从其他工作目录调用。合计行不重复计入，但须与各类别的机构、个人及总份额分别一致；原行户数和报告户均份额只核字段一致，不认证去重人数或独立重算统计定义。


原表破折号默认拒绝解释为零；确需条件测算时，在相应holderSnapshot或shareFlowSnapshot中显式给出dashPolicy: assumed-zero-for-explicit-dash，结果保留dashAssumptions并标为conditional-with-dash-assumption。这是输入假设，不是已披露零值；空白不按零处理，份额数量列不接受百分号，千分位必须正确。

## 明确份额的有限算术核对
模块函数`explicit_flow_residual(flows, shareClassOrder)`只使用期初、期末、申购、赎回四项明确值，输出未解释净变动。拆分未知仍保留未知；净残差零不证明无拆分，也不升级为完整勾稽通过。该函数不执行原文核验，正式CLI仍要求完整五行和原表核对；不能把此局部结果冒称正式CLI成功。
