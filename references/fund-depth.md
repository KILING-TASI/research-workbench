# 经理观点、分类变化与行业归因

先按原文流程取得PDF与来源身份；按历史/行业流程取得已有数据。由AI组织参数，无需用户填JSON。未取得的年份与采访不得编造。

```text
python scripts/fund_depth.py manager INPUT.json --out NEW.json
python scripts/fund_depth.py changes INPUT.json --out NEW.json
python scripts/fund_depth.py attribution INPUT.json --out NEW.json
```

manager输入code、asOf、pdf、sha256、identityText、reportDate、publishedAt、sourceUrl。仅接受年末报告期且原文前五页匹配该年度“年年度报告”标题，不能将中报或访谈作为年报观点；特殊标题不能自动确认时保留缺口。pdfplumber原文提取，首页核对主体及文件哈希，读取管理人报告4.4回顾与4.5展望，返回逐页原文。目录不当正文，未匹配编号返回not-found，扫描PDF不内置OCR。原文自述不代表客观证实，不声称覆盖全渠道；AI核对上下文再总结观点并保留页码。

changes输入code、asOf、reports至少两期递增；每期code、reportDate、publishedAt、sourceUrl、weightBasis=equity、taxonomy、taxonomyVersion、taxonomyVerified和categories[{name,weight}]。权重为股票内部小数，包括未知项合计1。输出类别权重变化；分类体系版本均已核验且一致、无未知项时计算总变差（一半绝对变化和）。不是交易换手率；行业变化不冒称价值成长漂移。报告原生分类版本未核验时只展示原文类别对照，不给评分。不能通过把taxonomyVerified改为true替代核验。

attribution输入code、base（brinson日期、industrySystem、industryVersion、权重依据与total-return口径）、weights（industry、industryVersion、portfolioWeight、benchmarkWeight、sourceUrl）、returns（industry、industryVersion、start、end、industrySystem、portfolioReturnPct、benchmarkReturnPct、sourceUrl）。按行业键组装，日期、分类与三个输入中的industryVersion须一致；分类版本缺失返回明确gap，版本冲突拒绝组装，结果显示版本；行业收益缺失返回gap，不补零。组装后依research_library.brinson核对总权重与贡献。需要真实期初持仓和行业总收益；不从年末持仓倒推当年操作。

综合报告调用fund_diagnostics.js report时增加depthResults数组，包含以上生成结果；code/asOf须与报告一致。报告自动接入原文、类别对照、已取得归因，并分对象保留缺项。基金经理观点摘要仍需AI阅读全文，不把关键词规则当准确理解。不承诺自动联网取得任意基金全部输入。
