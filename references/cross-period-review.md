# 跨期证据研究与研究包重放

适用于“和上期相比哪些是真变化、哪些是口径变化”“这两版报告能否直接比较”。AI复用已选标的，准备输入并解释结果；不要求用户填写JSON。原文核验、同一期交叉核对、跨期变化分别记录。

## 最小输入和命令

用户问“比较两期收入，给出原文依据”。先取得两期PDF或当前报告中的明确比较列，核对证券身份、报表范围、单位及字段；不能把比较列冒充前期首次披露的原始版本。填写原文真实哈希和物理页码，不使用以下示意占位值执行。

```json
{
  "asOf": "2026-10-05",
  "requiredMethodKeys": ["definitionVersion", "consolidationScope"],
  "pairs": [{
    "label": "营业收入",
    "before": {
      "entityId": "stock:600036", "field": "营业收入",
      "period": "2025-06-30", "publishedAt": "2026-08-29",
      "periodBasis": "H1", "statementScope": "consolidated",
      "basis": "reported-current-filing-comparative-column", "unit": "人民币元", "currency": "CNY",
      "value": 169969000000,
      "methods": {"definitionVersion": "original-label-v1", "consolidationScope": "consolidated-current-report"},
      "source": {"path": "本地原文.pdf", "sha256": "替换为实际SHA256", "page": 7, "fieldVerification": "not-verified"}
    },
    "after": {
      "entityId": "stock:600036", "field": "营业收入",
      "period": "2026-06-30", "publishedAt": "2026-08-29",
      "periodBasis": "H1", "statementScope": "consolidated",
      "basis": "reported-current-filing-comparative-column", "unit": "人民币元", "currency": "CNY",
      "value": 178181000000,
      "methods": {"definitionVersion": "original-label-v1", "consolidationScope": "consolidated-current-report"},
      "source": {"path": "本地原文.pdf", "sha256": "替换为实际SHA256", "page": 7, "fieldVerification": "not-verified"}
    },
    "meaning": "收入增长仍需结合息差、信用成本与资产质量解释。",
    "followUp": "核对比较期重述及合并范围，不从收入增长自动推断未来盈利。"
  }]
}
```

仅输出JSON结果：

```bash
python scripts/research_pipeline.py --workspace 用户目录 --out 新结果.json cross-period-review 输入.json
```

生成可阅读研究包：

```bash
python scripts/cross_period_review.py 输入.json --out-dir 新研究包目录
python scripts/cross_period_review.py 新研究包目录 --replay
```

## 处理与输出

检查证券、字段、期间类型、报表范围、计价口径、单位及币种。方法字段可选definitionVersion、industryClassificationVersion、benchmarkId、distributionPolicy、adjustmentVersion、consolidationScope；按指标明确requiredMethodKeys，禁止把不相关方法字段强行套给全部指标。

已登记的任一方法字段两期不一致、缺失，或存在comparabilityWarning时，delta与changePct保持null，列出差异。零或负基数不输出百分比。相同报告期标为版本差异，不解释为经营跨期增长。发布日期越界、PDF哈希变化、页码越界时停止；不猜测或自动填补原文。

人读报告依次呈现：发生什么、研究意义、需要进一步核对什么、前后数值和页码、核验状态。经营意义是研究者输入的解释，不自动成为事实；没有提供时明确待解释。

研究包包括input.json、result.json、Markdown、HTML、原文副本与manifest.json。来源用相对路径，复制或移动整个目录后仍可重算。输入、原文、报告或方法与版式代码版本变化时提示重新核验。清单未签名，不能防止恶意同时改文件与清单；分享原文副本需遵守[许可说明](third-party-notices.md)。

## 核验等级

本入口检查PDF文件完整性和页码范围，不自动把金额、标签、单位与原文表格逐项匹配。fieldVerification是输入声明，报告明确区分。需自动原文核验时先使用verify_original.py及支持版式流程。相同口径名称也不能证明实际会计政策一致；只有声明口径一致时计算变化，不宣称完成所有跨期可比性审计。
输入日期须为标准YYYY-MM-DD，方法字段只接受已支持的口径名称及文字值；空或未提供仍是缺口，布尔或对象不能作为一致声明。跨期警告须为具体文字。原文解析使用已核对摘要的相同PDF字节；文件完整性与字段核验声明分开。
