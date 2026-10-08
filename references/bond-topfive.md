# 披露前五名债券集中度

用于已有定期报告前五名债券表的局部分析，不代替完整债券持仓、发行人合并或信用评价。

调用：`python scripts/bond_topfive_concentration.py INPUT.json --out NEW.json`。输出文件须不存在；相对原件路径按输入JSON目录解析。需要pypdf。

输入包含sourcePath、sourceSha256、denominatorBasis（固定disclosed-bond-portfolio）、bondPortfolioAmountCNY；denominatorOriginal包含physicalPage与originalQuote，绑定债券品种表合计。entries须为五行，每行提供rank（1至5）、六位字符串code、amountCNY、reportedNAVPercentage、physicalPage与originalQuote。金额单位人民币元，比例单位百分数；数量或名称可附加，但此入口不认证债券身份。

输出result给出前五名金额、占披露债券组合金额比例、原报告净资产比例之和；source保存原件哈希与检查范围。排名不连续、代码重复、金额非有限或负数、金额顺序不符、合计超过分母、原件变化或指定页引句不匹配均停止，不补缺行。其他债券代码格式暂不支持。

分母是债券金额，不能称为净资产占比；原报告净资产比例之和受逐行舍入影响。前五名占比低不能证明完整发行人或地区风险分散。品种表与会计余额差异保留，不能因计算成功解释差额；简称不能替代发行人身份核对。原页引句核对不是官方真实性、版式完整或会计正确认证。

原文核对按原表行精确识别排名、代码、金额及比例，分母须对应品种表第10行合计；不接受数字子串碰巧出现。原件结构复查有警告时停止已核结果；特殊断行版式需先人工复核，不放宽为全文金额搜索。

父基金加权：python scripts/bond_topfive_parent.py INPUT.json --out NEW.json。输入parentFundDetails（已核父基金明细JSON路径）与children数组，每项含code、topFiveInput、balanceSnapshot路径。相对路径按输入目录解析；同报告期人民币口径，子代码及余额原件哈希须与前五名原件一致。输出逐债券路径、同精确代码合计和文件依赖哈希。使用原披露金额/净资产计算，不采用舍入权重；重复子份额、错期、原件异常、子净资产非正数拒绝。所选子份额金额超过父净资产的杠杆口径暂不支持。不同债券代码不能视为发行人独立；父明细与余额快照须事先原文核验，此入口不重核全部报表。

父组合分母复核要求：children每项另须提供balanceInput（余额原文提取输入JSON路径）。入口按该输入重新提取PDF本期余额，代码、报告期、币种和全部amountsCNY必须与balanceSnapshot一致；缺少balanceInput时停止，不沿用仅带来源哈希的旧输入。此复核需要pdfplumber及pypdf，确认分母来源但不认证会计正确或全部报告。
