# 基金公开附件获取与身份核对

先取得公开文件目录，再按明确公告ID下载：

`python scripts/fund_document_archive.py CATALOG_RESULT.json --id ANNOUNCEMENT_ID --out-dir NEW_DIRECTORY`

AI从本次研究需求选取相关记录；不把目录最新一条直接认定为当前有效合同。仅处理目录内唯一ID，公告详情ID必须匹配，附件须为HTTPS PDF。保存PDF、详情响应、来源哈希和原文资料Markdown/HTML。下载失败输出具体缺口；PDF下载成功但解析失败时保留文件。

标题在前20页核对，基金代码在全文核对，并记录代码页码。两者未同时匹配，不提取收费数字。代码未出现时可另补官方产品与文件关联证据，但本入口不自动推断共用份额关系。

身份匹配后尝试明确措辞的管理费和托管费原文提取，附页码、上下文；多费率冲突保留，不静默选值。此结果不证明当前生效版本，亦未核验官方发布网页、完整份额费率阶梯和合同补充修订关系。

## 从ETF取数结果归档明确公告

```bash
python scripts/fund_document_archive.py COLLECTION.json --code 159869 --id AN_EXPLICIT_ID --out-dir NEW_DIRECTORY
```

仅支持已取得基金目录的基金/ETF对象，先核对明确公告ID，提示性公告或摘要不能代替完整报告。保留PDF、文件哈希、标题匹配及代码所在物理页；未匹配时保留文件和缺口。此入口仅核对文件身份，不自动核验正文数字、报告期、完整持仓或现行费率。

## 明确报告期核对
归档定期报告时可同时传入 `--period-start 2026-01-01 --period-end 2026-06-30`。两项缺一不执行，末日不得晚于资料截止日。前20页仅匹配“本报告期自……至……日止”明确表述，保留原句与物理页。封面日期、送出日期及标题年份不代替期间；期间缺失、日期无效或多种期间冲突时保留待核验，不作为请求期间的已核对资料。期间匹配不证明正文数字全部核验。

## 归档后继续核对股票持仓

```bash
python scripts/archive_holdings.py ARCHIVE_RESULT.json --out-dir NEW_DIRECTORY
```

输入上一入口的result.json，不要求使用工作台。先重新读PDF，核对登记哈希、代码、标题及明示报告期；缺少匹配期间不能解析。按现有布局提取股票，输出result.json及自然语言HTML/Markdown。记录解析失败原因或会计差额，旧输出目录不覆盖。股票与行业表一致但会计差额未解释时，严格FOF自动穿透仍阻断。报告不把未取得非股票资产当作零。

## 检查持仓报告保存内容

```bash
python scripts/verify_collection_report.py REPORT_DIRECTORY/report-manifest.json --input ARCHIVE_RESULT.json --original ORIGINAL.pdf
```

清单登记归档输入、原文、解析方法与JSON/Markdown/HTML输出摘要。验证分别列出输入、原文、文件内容与方法变化；不提供原文时不会声称已检查原文。检查通过只证明本地保存内容与清单一致，不证明来源真实、数字正确、数据最新或视觉排版通过。内容与清单一起改写不属于该摘要检查能认证的范围。

文本提取范围：结果记录totalPages、pagesWithText和emptyTextPages，并在原文资料正文展示。无文本可能为空白、扫描或提取失败，不能据此判定缺页或不存在条款。单次提取上限300页；超过限制明确返回缺口，不默认截断后声明完整。代码与标题匹配不消除未取得文本的页，费用或条款仍需原页复核。
