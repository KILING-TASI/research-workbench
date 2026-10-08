# 申万行业原表记录

`python scripts/sw_classification_archive.py ORIGINAL.xls --as-of YYYY-MM-DD --out NEW.json`。依赖xlrd，未安装时明确提示依赖缺失。官方原表来源为https://www.swsresearch.com/swindex/pdf/SwClass2021/StockClassifyUse_stock.xls。用户提供或按请求下载副本，保留获取时点及摘要。

逐行核验固定表头、证券/行业代码与Excel日期，保留计入日、更新日、工作表和原始行号，按截止日单列未来记录。同证券可能多行，不裁决唯一有效行业、不推断终止日期。更新日不是披露日，不直接用于事前回测；行业代码不是AI、新能源主题，行业名称需另有版本化代码表。

按请求自动获取：`python scripts/sw_classification_archive.py --fetch --as-of YYYY-MM-DD --out-dir NEW_DIRECTORY`。固定官方地址，核验HTTPS最终域名与Excel文件签名、限制大小；保存original.xls、source.json与result.json。解析失败保留原文件和failure.json，不覆盖已有目录，不自动后台刷新。获取留证不改变历史记录的有效期限制。

新版行业代码名称核对：`python scripts/sw_codebook_archive.py ORIGINAL.xlsx --out NEW.json`，依赖openpyxl。限定官方2014to2021.xlsx的“新旧对比版本2”新版列，固定表头核验，不填充旧版名称；同代码冲突拒绝，相同重复保留多行定位。没有新版代码的旧版行单列，不能据此推断股票行业有效期。

代码表官方自动获取：`python scripts/sw_codebook_archive.py --fetch --out-dir NEW_DIRECTORY`。固定官方原表地址，核验最终HTTPS域名及大小、文件签名，再由Excel解析器核对结构。保留original.xlsx、source.json；解析失败保留failure.json，不覆盖旧文件。只按用户请求获取，不后台轮询。

基金持仓记录联动：`python scripts/holding_industry_records.py INPUT.json --out NEW.json`。输入asOf、已核验report及stockArchive/codebook（各含path、sha256）。重新解析两份原表并核验摘要，股票只按境内命名空间匹配。保留原始多条分类、日期、名称表定位；名称仅为SW2021代码表候选，不证明旧历史分类也使用此版本。输出自然语言Markdown/HTML，不生成确定行业权重。
