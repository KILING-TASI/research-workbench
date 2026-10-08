# 发行事实与规则底座

入口 scripts/issuance_facts.py register|view 输入.json --workspace 用户目录 --out 新结果.json。不运行toolkit刷新、不调参、不改旧预测。

register输入：code、issuer、title、publishedAt、asOf、sourceUrl、documentPath、fields；可提供sha256。PDF需要pdfplumber，文本扫描页尚无OCR，提取失败不伪装通过。代码、发行人、标题须在前8页匹配。来源限制为明确北交所/巨潮域名；本地文件与线上URL是否一致尚需下载哈希复核，不能仅凭URL标成已联网认证。

披露日：可提供publicationPage/publicationExcerpt唯一匹配日期，但正文日期不证明首次网络披露；没有可提取落款时提供metadataPath（公告数组，含url/date/issuerCode/title），记录目录匹配等级，不把正文申购日当披露日。目录中的路径日期可能与实际披露不同，不能证明历史时点可得性；字段factorEligible=false，禁止直接喂入事前模型。

字段支持price、onlineFinalShares、maxShares、refundDate、strategicShares、greenshoeShares、ratePct。每项须提供field/value/page/label/excerpt/basis，数值另需originalUnit（元/股、股、万股、%）。摘录须在指定页唯一出现，同单位出现多个值则拒绝；单位显式转换，日期不推算。单位在表头、值在另列的版式暂不支持此紧凑校验器，不能强行拼接摘录。

示例字段：
```json
{"field":"maxShares","value":"745700","originalUnit":"万股","page":5,"label":"申购上限","excerpt":"但申购上限不超过网上发行数量（含超额配售选择权）的5.00%，即74.57万股","basis":"网上每账户上限，含超额配售"}
```

特别区分：网上初始数量与最终数量；战略配售总量与非延期交付量；网上超额配售数量与最终选择权行使量；未获配退款与获配本金释放。程序匹配摘录，不自动证明用户指定field和basis的语义映射正确，需研究人员复核上下文。

保存research-data/bjx-facts/代码/documents下原PDF，versions保存不覆盖版本及哈希链。重复内容不新增，supersedes指定已存在版本标识，日期不得倒置。更正关系由输入声明，仍需人工核对；没有显式更正关系的数值/口径冲突保留候选，view置该字段null，不按登记先后静默覆盖。view按publishedAt截止，不向申购前回填结果；历史网络可得性仍未证明。

view输入：{"code":"920022","asOf":"2025-09-09"}。缺项保留null，输出missing/conflicts；读档核验版本链及PDF哈希。故障不修改旧发行缓存或模型快照。

规则源索引见issuance-rule-sources.json：已记录版本日期、官方URL和核验等级。当前是有限规则证据索引，尚未实现完整规则原文归档、变更自动监控或全量自动合规判定。官网访问受限不猜链接、不强行宣布现行规则已全部核验。

扩展发行结构字段：initialIssueShares、initialOnlineShares、postIssueSharesBefore、postIssueSharesFull、validSubscriptionShares、actualNewShares、actualRepurchasedShares（股）。初始、全额行使假设和实际实施口径分别核验，不能互代；原有字段及版本档案保持兼容。
