# 财报与公告原文核验

## 通用模式 v2

输入增加 `schemaVersion: 2`，使用同一个 verify_original.py 入口。v1保留兼容，已修复“先按数值过滤导致漏报同名歧义”：不同值的同名行也必须计入候选。

v2适用于基金、上市公司财报和事件公告的显式字段核验，不根据文档类别限定表格。仍须提供 documentPath/sourceUrl/trustedPublisherHosts/sha256/title/issuer/publishedAt/asOf/publicationExcerpt/fields；事件公告可不填reportDate。identityPages可明确指定身份信息页，默认前8页。

表格字段示例：
```json
{"id":"revenue","page":20,"mode":"table","label":"一、营业总收入","labelColumn":0,"column":2,"columnHeader":"本期","unitText":"单位：人民币元","periodText":"2025年1月1日至2025年12月31日","value":"1384073616.80","tableLayout":"lines"}
```

- page从1开始，column/labelColumn/tableIndex从0开始。
- tableLayout=lines适合有框线表格；text使用文本对齐推断，适合部分无边框表格，不承诺任意合并单元格准确。
- 可用bbox=[左,上,右,下]限定PDF点坐标区域，或tableIndex选择表格；限定范围后必须仍包含单位、期间与列头。
- 先列出全部同标签候选，再比较数值。同名不同值也报ambiguous；指定tableIndex后保留全部候选供审计。
- 单位和期间须在选定范围出现，列头须在目标列上方。缺失返回context-mismatch，不猜跨页表头、不自动换算单位。括号负数和千分位可解析；横线/空白返回reported-empty，不认定为零。
- 正文 mode=text 要求label与完整excerpt；摘录重复报歧义。若核数值，需value/unitText/periodText均能在摘录找到。仅证明摘录存在，不证明事件实施或自动完成语义归因。

扫描件或图片型PDF需人工辅助提取和复核。内置自动OCR已移除，ocr.enabled、executable、renderer、pages 等程序配置不接受；不会调用外部识别程序。

输出每字段matched/mismatch/ambiguous/missing/context-mismatch/reported-empty/unparseable/invalid/needs-review，附候选表号行号和原行；单字段失败不丢弃其他结果。只有原生文本身份、全部字段匹配且没有OCR/错误时总状态passed。

## 调用与输出

从主包根目录运行 `python scripts/verify_original.py 输入.json --out 新结果.json`。依赖pdfplumber。输入字段见上述v2要求；v1仅兼容已有输入。

按字段输出状态、原文页码、候选表格与差异。失败项保留，不能把个别匹配称为整份报告核验。若身份或期间不能确认，整体为 needs-review。

仅核验明确列出的字段和摘录，不证明财务真实性或公告实施，不自动猜测PDF地址，不保证所有版式可解析。
