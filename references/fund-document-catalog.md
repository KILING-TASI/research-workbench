# 基金合同与招募说明书目录检索

主动调用：`python scripts/fund_document_catalog.py --code 005827 --as-of 2026-10-03 --kind contract --out-dir NEW_DIR`。kind也可为prospectus。

输出result.json和逐页原始目录，包含候选标题、公告ID、发布日期、目录来源及哈希。最多1000条公告，未读完标记truncated，不宣称全量。排除摘要、提示、修订公告及英文标题；修订公告仍须独立关联核验。

这一步仅定位第三方目录候选，不下载PDF、不核验官方发布网页、不确认现行有效性，不据标题输出费率或合同条款。没有候选明确空列表，不能用旧报告费率回填当前费用。

候选原文归档：`python scripts/fund_document_archive.py CATALOG_RESULT.json --id 公告ID --out-dir NEW_DIR`。支持本入口candidates及原目录rows格式，两个字段冲突时拒绝。保存PDF与详情来源，全文代码/前20页标题匹配后才提取费率措辞，现行有效性仍待修订关联核验。

目录同时输出amendmentClues：最近完整文件候选同日及之后的合同/招募修订、费率调整标题线索。公告日期不作为生效日，relationVerified始终为false；必须读取原文才能确认关联及生效。标题未命中不证明没有变化。自然语言清单同步输出。

费用调整原文表核对：`python scripts/fund_fee_amendment.py ARCHIVE.json --name 基金完整名称 --out NEW.json`。仅精确匹配有调整前后管理/托管费列的名单及明确生效措辞；保留页码、表格坐标、原行和哈希，不确认份额代码及当前费率。

归档入口可直接选择amendmentClues中的公告ID，catalogItemKind明确为amendment-clue。修订公告不执行全文通用费率提取，须按基金全名核对名单；同ID跨候选类型重复时拒绝，不静默选择。

档案证据补充：`python scripts/fund_legal_evidence.py INPUT.json --out NEW.json`，输入dossier、amendmentArchive及fundFullName。重新核对双方截止日、报告代码及PDF摘要、报告标题全名和调整表全名；输出独立JSON/自然语言Markdown/HTML，原档案不改，currentEffectiveFees保持null。
