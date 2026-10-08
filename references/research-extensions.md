# 跨资产、危机场景、行情时效与递归穿透

独立入口：scripts/research_extensions.py fof|crisis|quotes 输入.json --out 新结果.json。quotes另用--workspace指定缓存目录。需要numpy及已有portable_collect、portfolio_models。

fof：asOf、currency、root、nodes对象、maxDepth（1至20）。节点currency、sourceUrl、reportDate、publishedAt、holdings；持仓kind=fund及node，或kind=stock/bond/cash/other及市场唯一id；weight为占本节点净资产比例0至1。循环、缺子基金、深度限制和未披露部分保留unknown，路径累计相乘，同底层合并，权重守恒。日期在截止前、币种一致。未公开MOM子账户不能自动还原。输入节点需要使用者取得真实报告，现有真实006859报告及两只子ETF部分穿透验收；全子基金覆盖未完成。

crisis：沿用portfolio_models历史输入，weights、paths（100至10000）、seed、regimes数组。每状态name、periods、volatilityMultiplier、correlationBlend（0至1）、logMeanShift逐资产向量。按指定状态顺序改变样本对数收益协方差：相关矩阵与全正相关矩阵凸组合、波动倍数缩放；均值冲击显式假设。不是预测状态或已校准危机模型，正态对数路径仍缺信用、流动性和未知厚尾。每观察期无成本恢复权重。

quotes：kind=stock/etf、codes、asOf、maxAgeSeconds。获取腾讯行情快照，保留行情时间、检查时刻及年龄；未来、过期、失败缓存分别标注。第三方快照不等于交易所授权实时行情；没有IOPV、PCF或盘口深度，不用于宣称实时套利。

真实验证：000248权益联接、000191信用债、000216黄金联接，共81个月（2020-01至2026-09）共同观察完成MVP前沿、历史分块模拟与分阶段危机模拟，固定种子复现。第三方分红与基金分类未逐项官方核验，这是当前修订数据模型试跑，不是当时可交易策略样本外验证。000012身份失败保留记录。510300/518880行情为休市前过期快照，未冒称实时。递归多路径、未知仓位及循环引用使用合成节点通过。


## 子基金报告关联与待复核资料

父基金已提取出子基金代码和报告期后，使用：

```bash
python scripts/fof_reports.py PARENT.json --workspace REPORT_LIBRARY --as-of YYYY-MM-DD --out NEW_RESULT.json
```

PARENT.json包含reportDate及holdings列表，每项code为六位代码，weight为占父基金净资产比例（未知可省略）。默认读取本地报告库；需要本次主动检索时加--online。用户补充PDF时加--uploads UPLOADS.json，上传清单每项包含code、reportDate、path、title、publishedAt、sourceUrl。--limit与--start-index用于分批处理，不创建后台更新。

输出nodes仅包含可以用于当前股票穿透的已解析节点，pendingReports列出缺失或待复核项及reason。报告下载成功不等于穿透完成。股票明细已核对但会计差额未解释时，待复核项保留parsedPath、holdingsCount及accountingReconciliation；从parsedPath查看解析底稿，差额处理前不加入nodes。缺失报告、不支持的债券或黄金版式、原件结构警告均保留实际原因，不按零持仓处理。

此入口关联公开或用户提供的资料，不证明父基金当前实际持仓、不确认第三方文件为官方原件，也不能生成未公开MOM内部持仓。

## 真实FOF报告验收（2026-10-03）
fund_report_fof.py PDF --metadata 元数据.json --out 新结果.json；仅适配八列§8.12.2完整基金表至§8.13边界。metadata明确code/title/issuer/reportDate/publishedAt/sourceUrl/sha256/netAssetsCNY/fundInvestmentCNY。跨页续行拼接、序号与身份检查、逐行净资产权重舍入校验、金额合计逐分勾稽；分母另用verify_original原文单元格核验，不猜或自动缩放。

006859官方2025年年报67只子基金完整取得；159915同期完整股票表118只与159934同期黄金原文核验，3只直接国债总额一致。根与子基金报告期均2025-12-31，送出日均2026-03-31，截止2026-10-03。净资产使用基金全部份额资产池，不按A/Y拆分，也不把总资产比例当净资产权重。末名子基金披露权重0.00但公允价值5.63元，使用金额/净资产保留非零权重。

真实递归输出已识别底层权重10.7701693154%，未知89.2298306846%；65只子基金报告缺失以及根/子基金非穿透残余单独保留，残余不是现金。股票市场使用CN-equity命名空间，不按代码猜交易所；黄金SGE:Au99.99。真实报告验收通过不等于整只FOF完整穿透、实时持仓或交易还原。子ETF身份、代码、报告期、送出日和分母原文检查通过；未来披露、币种冲突拒绝。
