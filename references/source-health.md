# 按需数据源体检

文档版本：1.1 · 更新日期：2026-10-06

用户询问数据源是否可用，或同一来源连续取数失败时，用本入口检查指定标的的小窗口样本。每次主动运行，不创建轮询或定时任务。环境依赖继续使用environment_check.py；数据源体检实际联网。

```text
python scripts/source_health.py INPUT.json --out-dir NEW_DIR
```

AI根据问题准备输入，确认代码与市场，不要求用户填写JSON。

```json
{"asOf":"2026-10-05","timeoutSeconds":8,"requests":[{"profile":"fund-nav","code":"161005"},{"profile":"cn-history-eastmoney","code":"510500","market":"1","start":"2026-09-01","maxLagDays":14},{"profile":"cn-history-tencent","code":"510500","market":"1","start":"2026-09-01","maxLagDays":14}]}
```

示例代码是实际接口查询对象，不是预设成功样本。使用时替换截止日、标的和窗口，不把示例参数当成用户持仓或研究结论。

## 检查范围

| profile | 检查对象 | 参数和日期口径 |
|---|---|---|
| fund-nav | 东方财富基金单位净值 | 六位代码；最新窗口净值所属日，默认30日窗口、14自然日间隔阈值 |
| cn-history-eastmoney | 东方财富沪深价格日线 | 六位代码，market为0深市或1沪市；默认30日窗口，最多60自然日 |
| cn-history-tencent | 腾讯沪深未复权价格日线 | 同上；可与主源对照本次是否取得样本，不比较全历史准确率 |
| hk-us-history | 腾讯港美股价格日线 | market为HK或US；明确代码，最多60自然日；供应商明确返回US映射时最多追加一次查询 |
| stock-financial-summary | 东方财富财务摘要 | 六位代码；默认365日窗口，检查最近5条响应中的符合披露截止日样本，阈值默认210自然日 |
| stock-announcements | 东方财富股票公告目录 | 六位代码；默认180日窗口，最多5条样本；空目录不证明没有公告 |

请求1至12项，timeoutSeconds为1至20秒。maxLagDays可按资料频率设为0至730自然日。阈值是本次研究规则，不是官方时效或交易日标准。基金假期、暂停申赎、低频财报等需要另行解释。历史窗口的间隔相对asOf，不代表当前日期下资料新鲜。

不接收任意网址、密钥、Cookie或可执行程序。只使用已登记公开HTTPS接口；公共下载器检查DNS及跳转地址、关闭环境代理、限制每次8MiB响应。单项不重试；出现401/403/429时停止本轮同域名请求，其他来源可以继续。

## 结果含义

- endpointResponded：取得响应或HTTP拒绝状态，不等于数据可用。
- sampleValid：窗口内非空样本通过字段结构、证券代码和数值等检查，不是官方身份或原文认证。
- minimumReturnObservationsMet：价格或净值至少有两条观测，仅是区间收益的最低数量条件。只有一条时保留响应，明确不能计算区间收益或波动；即使数量足够，分红、频率和完整性仍需正式研究检查。
- freshness：默认比较窗口末端与asOf的自然日间隔；提供且确认适用日历时，另按最后预期观测日判断。calendarVerified仍为false，表示本入口不认证日历来源；日期对照见calendarCheck。
- coverageVerified、originalVerified均为false。小样本不能证明完整区间、全市场覆盖、财务真实性或长期接口可用率。
- status区分observed、empty-sample、blocked、network-error、invalid-sample及skipped-source-blocked。取得但超过日期阈值时保留样本，同时记录freshness=stale。

输出input.json、result.json、自然语言Markdown/HTML与原始响应及哈希。结果记录每次实际请求；不得把体检成功替代正式采集、持仓核验或财务核验。主源失败而备用样本可用时列出候选，后续研究仍使用实际采集入口验证、归档和标明来源。

体检不更改原有市场缓存，不安装组件。宏观官方页面、SEC、基金PDF、实时IOPV及授权终端尚未纳入本入口；未检查来源不标为通过。完整数据范围见[数据源登记](source-registry.md)，实测说明见[验证范围](validation-scope.md)。

## 可选的日期完整性核对

基金净值和行情请求可附 `calendar`。完整格式见[日期核对与评价交付](p0-delivery-contract.md)。日历需声明市场、覆盖整个请求窗口、预期日期、HTTPS来源和适用性；其他资料类型不套用交易日历。它是显式研究输入，不由星期几推定所有基金都遵循A股交易日。

日历未确认、日期缺口、日历外观测分别保留。空休市窗口不计为100%完整；记录不足两条或日历有缺口时不列为可用历史备用源。提供日历不提升原文认证或全市场覆盖等级。


财报获取入口对缺少PDF文件头的下载或上传内容记录 `rejectedResponse` 的字节数、SHA-256及拒绝原因，不写成报告PDF，不进入解析成功状态。HTTP成功或文件名含.pdf不能代替内容校验；该留痕不证明失败原因是验证码、权限或未披露，也不自动重试受限制页面。
