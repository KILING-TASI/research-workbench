# 组合行业快照汇总

回答“多只基金的已披露行业合起来有多集中”。先取得同报告期的行业金额、净资产、股票总额与原文页码，核对基金身份、披露日期及金额合计，再执行汇总。不按产品名称猜行业，不用行业快照解释整段历史回撤。

## 调用

路径相对Skill根目录：

```bash
python scripts/portfolio_industry_exposure.py INPUT.json --out NEW.json
```

输入文件示例：

```json
{
  "reportDate": "2026-06-30",
  "assets": [
    {"code": "000991", "allocation": "0.5", "industryReport": "000991-industries.json"},
    {"code": "006228", "allocation": "0.5", "industryReport": "006228-industries.json"}
  ]
}
```

行业文件路径相对输入JSON目录。行业文件为`fund_report_industries.extract`的归档结果，必须登记code、currency、reportDate、netAssetsCNY、equityMarketValueCNY、taxonomy、taxonomyVersion、sourceSha256、sectors；各行业保留金额及components中的原文locator。该汇总器检查金额与已登记股票总额，不替代PDF解析与官方来源核验。

未取得行业表的资产仍登记代码和权重，以`missingReason`替代`industryReport`。全部权重须合计1，含未分类资产；不得删除缺资料标的后重新归一化冒充全组合。

## 输出与解读

输出各行业的`portfolioNavWeight`、基金分项金额/净资产/权重/页码，已知股票合计`knownEquityExposure`、剩余未分类`unclassifiedResidual`、缺报告清单及来源哈希。计算为“基金在组合中的静态权重×行业金额÷基金净资产”，重新计算金额比例，不信任旧的navWeight字段。

同分类、同版本及同代码才能暂作算术汇总；名称冲突拒绝合并。不同分类或版本分组保留；未核验分类版本不能认证可比性。境内A—S与港股GICS分别解释，不合并行业榜。剩余部分是未分类，不等于现金、零风险或没有持仓。

报告先给出有范围的判断，再说明主要敞口、分类局限和改变判断的证据。例如宽泛制造业占比较高，可提示大类集中，但没有逐股业务映射时不能认定重复押注同一细分赛道。固定报告期权重不是随收益漂移的历史账户。

身份/日期/币种不一致、权重未合计1、金额合计不符、行业重复或缺页码时拒绝计算，列明问题并请求补充资料；不补零。当前入口仅处理人民币、股票金额不超过基金净资产的快照；杠杆或跨币种情景使用相应专项模型，不强行套用。
