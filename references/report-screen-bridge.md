# 已核验报告到筛选与持仓反查

`python scripts/report_screen_bridge.py INPUT.json --out NEW.json`

输入例：
```json
{"asOf":"2026-10-03","reports":["REPORT_DIRECTORY/result.json"],"conditions":[{"kind":"holding","code":"600519","market":"CN-equity","minimumWeightPct":5}]}
```

reports为fund_report_archive或fund_dossier生成的报告result.json路径。检查身份、报告期、披露日期、PDF哈希、来源、完整股票范围及权重合计后，生成多维筛选候选；净资产规模带全基金份额口径。输出screenInput可复用，附自然语言简报、不可用报告清单。

境内股票使用CN-equity、港股HK-equity进行命名空间反查，不猜具体交易所。完整范围仅指股票；债券、衍生品不在该反查域。报告快照不代表今天持仓。不同份额共用全基金规模，禁止重复累计。第三方PDF副本勾稽不能替代官方发布网页核验。非法或不完整报告单列缺口，不生成伪候选；全部不可用时报错。


## 场内ETF与联接基金身份

输入可附 `identities` 列表，每项包含 `code`、`instrumentType`（`exchange-traded-etf` / `etf-link` / `fund`）、`observedAt`、`sourceUrl`、`quote`；场内ETF另需 `exchange`（`SSE` / `SZSE`）。身份必须与报告代码一致，日期不晚于截止日。来源和引用原文随结果保留；输入来源并不自动等同官方网页核验。没有身份资料时保持 `fund-unclassified`，不得凭名称判为场内ETF。联接基金保留基金类型。同代码重复身份要求先解释冲突。抓取时间不能替代名册所属日期。股票表会计差额待核验的报告仍不进入严格筛选，不因补齐证券身份而绕过。

## 结果阅读

同时输出 JSON、Markdown 和 HTML。简报展示研究条件、实际可判定数量、每只基金的结果与差异原因、资料日期和来源。完整股票表以明确证券命名空间限定反查范围；范围外证券返回资料不足，不解释为未持有。已有任一输出文件时停止，不覆盖旧研究。

九列QDII报告中的明确US证券代码可使用US-equity命名空间反查；美国代码不补零，不与境内代码混用。跨市场金额使用报告披露人民币市值，不能用美元报价替代。

每次列明请求、可用和失败报告数；筛选统计只针对可用报告。整批失败仍输出缺口简报：status=unavailable、result=null，不生成假筛选结果，不解释为没有匹配基金。空报告请求属于参数错误，需明确提供1至5000份报告。
