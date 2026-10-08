# ETF份额变化估值代理

`python scripts/etf_share_flow.py INPUT.json --out NEW.json`

输入code/asOf/startShares/endShares/endNav，每项提供code、value、observedAt、sourceUrl、basis、unit；份额单位shares，单位净值CNY/share，净值basis为unit-nav或provider-unit-net-worth。两期份额口径一致，期末净值日期一致，禁止用市场价格或累计净值替代。输出JSON、Markdown、HTML。

代码须六位文字，来源和口径不得空缺；可选publishedAt不得早于观测日或晚于asOf。金额计算超出有限数值范围时停止，不生成Infinity结果。输入结构异常、JSON字段重复和缺失核验依据须报告失败原因，不填默认金额。

shareEventStatus默认为unknown，不输出金额；assumed-no-share-events表示明确假设无份额拆分/合并，报告前置披露；verified-no-share-events需shareEventEvidence.sourceUrl和匹配window。工具仅接受已提供核验依据，不自动检索所有事件。

计算为（期末份额－期初份额）×期末单位净值，仅两点估值代理，不是真实申赎结算现金流。netFlowCNY可接多维筛选，但须将规则basis限定到同一份额事件状态与口径，不能和供应商真实资金流混合排名。较长窗口不能代替逐日申赎金额汇总。第三方单位净值、官方份额与明确假设分别保留，不承诺实时或全市场自动接入。


verified-no-share-events的核验依据还需observedAt和quote，核验日期不得晚于asOf。工具保存引用但不把用户填写的状态当作独立审计认证。

## 实收基金表的数量核验

`python scripts/fund_share_ledger.py INPUT.json --out NEW.json`核对三列实收基金表。输入path（相对输入文件目录或绝对路径）、sha256、六位code、物理page及start/end（YYYY-MM-DD）。原件结构、前12页代码及期末、数量表期间、基金份额（份）与账面金额列分别确认。仅支持上年度末、本期申购、按负号填列的本期赎回、本期末四行；额外拆分行、缺行、歧义或不勾稽拒绝，不能跳过。

输出原表行及坐标、份额数量变化和勾稽差额，不使用账面金额列计算份额，也不把数量变化认作真实现金流。适用于明确年初至报告期末的选定表，不承诺所有报告布局。需要持有人比例联动仍用fund_holder_units_review.py；两期估值代理仍用etf_share_flow.py并遵守事件与净值限制。
数量破折号默认拒绝，不作为缺失零值。可明确提供dashPolicy: assumed-zero-for-explicit-dash进行条件测算；结果标conditional-reconciliation-with-dash-assumption并列dashRows，不能升级为无假设原文核验。空白仍拒绝。原行保留，未声明时不得为通过测试擅自添加假设。

最小调用：将示例复制到自己的研究目录，把对应原件放在同目录并命名original.pdf；原件哈希必须与示例匹配，不附带原件分发。用Skill根目录的脚本执行：

```text
python scripts/fund_share_ledger.py MY_DIRECTORY/fund-share-ledger-159915.json --out MY_DIRECTORY/NEW.json
```

示例见examples/fund-share-ledger-159915.json。结果净份额变化为-20757100000.00份，变化约-65.880657%，勾稽差额为0；不解释成资金净流出。输入原件缺失、哈希改变、代码/期间/原页不匹配时失败，不用缓存或其他报告替代。结果记录原件哈希、表格坐标、公式及选定方法脚本哈希；代码摘要不是第三方依赖环境冻结或完整真实性认证。
