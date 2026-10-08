# 日期核对与评价交付

用于完整公司评价、基金比较或用户要求核查历史数据完整性时。单字段查询沿用轻量入口，不加载完整评价流程。

## 评价输出

公司评价的正文先给一句话结论，再解释依据与仍需核实的原因。研究解释的条目示意：

```json
{"role":"earnings","basis":"research-explanation","title":"盈利质量","conclusion":"利润改善仍需现金兑现支持。","text":"结合本次取得的利润及现金流证据解释，不能仅凭利润增速判断。","evidence":[{"page":12,"quote":"替换为实际原文中的完整引句"}],"alternatives":["营运资金季节性可能影响现金流"],"followUp":["核对下一期回款与存货变化"]}
```

示意引句不能直接运行。须按真实报告替换页码与原句；报告生成时检查引句。falsification条目另提供非空invalidationSignal。角色与字段齐备只证明结构覆盖，不能证明因果成立或完整投资判断。

## 适用日历

```json
{"market":"SSE","start":"2026-09-28","end":"2026-10-06","dates":["2026-09-28","2026-09-29","2026-09-30"],"sourceUrl":"https://www.sse.com.cn/disclosure/announcement/general/c/c_20260915_10832273.shtml","applicabilityConfirmed":true}
```

这是指定沪市窗口的日历示例，不是全年日历。使用前检查来源和标的适用性。基金净值尤其要确认QDII、货币基金和暂停披露等安排，不能自动套用交易所股票日历。

- 体检：放到每条requests的calendar。
- 资料质量：放到每条rows的calendar，并提供requestScope.start/asOf。
- 基金比较：放到每条rows的calendar，calendarMarket用于约束市场；start/asOf定义本次窗口。

start/end须覆盖全部请求区间，dates有序、唯一且在范围内。缺日与日历外日期分别列出，缺失不填充。未提供日历、适用性未确认、无预期观测日分别处理，不生成虚假的完整度。日历来源仅是输入声明，本模块不自动认证网站内容。

## 状态解读

| 输出 | 可以说明 | 不能说明 |
|---|---|---|
| appraisalCoverage | 评价六项及必要解释是否覆盖 | 语义正确、因果成立、估值有吸引力 |
| originalVerification | 支持字段的本期和比较列是否与原文匹配 | 完整三表全部科目均核验 |
| quarterInputVerification | 七项字段的本期单季及同比环比依赖是否匹配 | 报告中任何单季度结论均有依据 |
| calendarCheck | 声明日历窗口内日期齐备程度 | 数值、复权、分红、公布时间均正确 |

出现差异时保留已取得资料与失败原因。报告开头说明对判断的影响，支持查看原文和复算；不把测试用例数或模板齐备当作投研准确率。
