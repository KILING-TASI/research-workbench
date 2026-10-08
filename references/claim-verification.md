# 逐条事实核验

用户粘贴新闻或研究段落后，AI拆为数字、原文引句、排名、因果判断，取得对应证据后执行：
`python scripts/claim_verification.py INPUT.json --out NEW.json`

输入asOf与claims列表，每项id/text/kind。numeric另有value、decimalPlaces（默认2）、scope（entity/metric/period/unit）。quotation另有quote；支持文本或PDF明确页码。evidence各项path/sha256/sourceUrl/publishedAt，数字用JSON Pointer的pointer及相同scope。保留所获取来源与日期，不把复算结果的生成日冒充基金披露日；计算证据必须同时附原输入和算法来源。

输出JSON、自然语言Markdown、HTML；状态supported/inconsistent/conflict/insufficient。报价或收益证据必须同对象、同期间、同单位；文件改变、字段缺失、未来披露均不标支持。多个数字来源支持情况不一致时标冲突。排名在未核验完整池时留证据不足；因果需专项识别和归因，不由文本命中确认。引句命中仅支持原文确有这段话，不代表来源陈述本身正确。

此入口不附带Wind或商业数据库，也不自动裁决任意文本真伪。核验结果可作为公司简报和基金比较的来源附件，结论仍需逐项表述，不将整份报告标为全面核验。
