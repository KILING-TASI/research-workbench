# 结论证据包与版本

## 调用

```text
python scripts/fund_evidence.py build INPUT.json --out NEW.json
python scripts/fund_evidence.py compare INPUT.json --out NEW.json
```

build输入subjectCodes/asOf/methodology/evidence/conclusions/notes。证据id唯一、code在主体内；status为original-disclosed/derived/assumption/missing/conflict；原文有sourceUrl/disclosedAt/locator。有本地pdf时需fileSha256/page，可选bbox[x0,top,x1,bottom]及quote，按pdfplumber坐标验页边界和摘录。哈希/摘录校验不能替代数值语义核对、主体核验或真实性认定。

计算证据需formula/inputEvidenceIds/parameters（非空）。所有引用必须存在且无环；这是路径记录，不自动执行任意公式。缺失不能填值；冲突保留至少两个alternatives，不静默选值。

结论id/text/evidenceIds/grade/limitations；grade为disclosed-fact/calculated/estimate/withheld。引用链中存在假设、缺失或冲突时不能标为确定计算。可选coverage{known,total,basis}，输出比例不是置信度/准确率。没有模型不要构造估算上下界。

notes有text及evidenceIds/conclusionIds至少一种绑定。不替用户自动写研究观点。

compare输入before/after证据包，复验引用与原文哈希，再输出证据字段、口径、结论和笔记变化；同一天重新解析也可比较。packageVersion按标准化内容哈希，不改写旧文件。使用新版解析器时在methodology记录版本。

## 接入报告

fund_diagnostics.js report输入supplementaryResults数组，允许fund-series-quality、fund-distribution-bases、fund-multi-benchmark、fund-research-snapshot-diff和fund-evidence-package。主体及截止日必须一致；快照对比用afterAsOf。

fund_report_presentation.js显示分项结果及可展开结论；来源链接带PDF页码。依赖证据的完整路径保存在JSON，不声称HTML已完整可视化计算图。交付PDF本身与证据包便于复查，原文URL可能变化。

用户报告以自然语言解释发现、含义与局限，字段名、枚举状态及JSON不直接展示。技术依据按需展开，代码需配基金名称；不能只将机器结果表格化当作人类研究报告。

原文检查范围另列originalVerification：只登记URL为source-declared-not-original-checked；PDF哈希与页码检查为hash-and-page-checked-only；提供摘录时即使未给bbox，也核对指定物理页全文，匹配标quote-found-on-declared-page；区域摘录匹配为quote-found-in-declared-region。以上均不等于自动认证数值定义或全部原文真实性。版本比较同时保留beforeStoredVersion/afterStoredVersion，当前重新校验生成的版本标识不冒充旧方法版本。


CLI中本地PDF相对路径以输入JSON所在目录解析（build及compare的before/after均适用），不依赖运行时当前目录。结论正文、身份和局限采用非空文本/文本列表，引用身份不重复；证据日期须合法且不晚于截止日。上述登记与展示检查仍不执行公式或认证来源真实性。
