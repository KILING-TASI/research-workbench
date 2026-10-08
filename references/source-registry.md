# 数据源登记与调用

research_pipeline.py 提供 source-list、source-plan、source-collect，均采用原有 --workspace、--out 和 JSON 输入路径。source-list 输入空对象即可。

请求示例：
```json
{"asOf":"2026-10-03","refresh":false,"requests":[{"kind":"etf","code":"510300","start":"2025-01-01","domains":["history","announcement-metadata","realtime-iopv"]}]}
```

先 source-plan 查看可采集、需用户提供原文、未支持的项；source-collect 调用现有 collect-batch，保留失败、缓存和实际来源。refresh=false 仅检查已有缓存；refresh=true 才尝试获取，遵守现有有限重试与访问拒绝停止规则。

数据域：history、financial-summary、announcement-metadata、original-pdf、realtime-iopv、industry、licensed-terminal、alternative。官方宏观观测由主包的[内置宏观专题](integrated-topics.md)处理，不属于本层采集器。

登记分别描述来源类型、数据域、传输方式、授权和再分发状态。公开第三方接口授权均未评估，不能因可访问而声明有授权；未接入的终端不能自动调用。original-pdf 路由到原文核验流程，但本命令不自动搜索下载PDF。

observed仅表示该组件非空，不证明完整区间、实时性或官方原文一致。实际数据URL、备用来源和旧缓存时间保留在bundle；登记sourceId不是实际单一供应商归属。当前采集按标的执行，可能同时取得请求域以外组件。缺项不填零、不升级为官方核验。需要强时效或原文等级时继续核对实际观测时间与verify_original输出。

## 主动数据源体检

需要检查当前接口、返回结构和样本日期时，使用[数据源体检](source-health.md)，区分请求失败、空样本、结构异常、日期超限和观测不足。仅主动调用，不后台轮询。
