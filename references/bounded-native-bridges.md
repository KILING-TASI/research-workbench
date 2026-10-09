# 有界可选原生接口（待审开发增量）

用户明确需要已安装独立引擎时调用；不下载依赖、不替换内置入口，不恢复真实账户。输入为对应引擎原生契约，不猜字段映射。

```sh
python scripts/bounded_engine_gateway.py rules --project-dir /trusted/cn-market-rules --input /data/envelope.json --out-dir local-data/new-rule-report
python scripts/bounded_engine_gateway.py bjx --project-dir /trusted/bjx-ipo-engine --input /data/native-request.json --out-dir local-data/new-ipo-report
python scripts/bounded_engine_gateway.py convertible --project-dir /trusted/convertible-bond-engine --input /data/bridge-fixed.json --out-dir local-data/new-bond-report
python scripts/bounded_engine_gateway.py portfolio-observed --project-dir /trusted/portfolio-decision-engine --engine-python /trusted/venv/python --input /data/observed.json --out-dir local-data/new-flow-report
python scripts/bounded_engine_gateway.py portfolio-cash-demand --project-dir /trusted/portfolio-decision-engine --engine-python /trusted/venv/python --input /data/cash-demand.json --out-dir local-data/new-cash-report
```

输出 input.json/result.json；engine_response 原样保留，nativeReturnCode、输入SHA、引擎commit、方法文件SHA、实际gateway源码SHA单列。旧目录拒绝。blocked不是成功，native-response-preserved只表示响应保存，不表示资料或资格通过。代码和数据指纹前后核对，规则包含 rules/version-catalog.json；调用期间改变则拒绝一致性交付。

|入口|本次范围|不认证|
|---|---|---|
|北交|API1.0的scenario.v1/cash_ledger.v1；无概率单发行与明确费用/日期|年度策略、滑点/融资/概率；额外字段前置拒绝，不当作原生失败等价|
|组合出入金|workbench-observed-cashflow-input-v1；CNY基本单位、流前/流后及费用声明|任意原生回测时点/真实账户/全部IRR根；只核对已证交集|
|现金需求|cash-demand原生透传|工作台没有独立同模型，不称双模型等价|
|可转债|cb-fixed-cashflow-1；固定未来现金流、显式税/全价/曲线|非平坦曲线不对照传统YTM久期；条款/实际退出unknown|
|规则|信封1.2/交接rule-handoff/1.0；同生产者回转核对，中文MD/HTML|交接1.1未消费；selected只选规则版本，项目partial/unknown、结算unknown不能变通过|

内置计算入口保留。本次为自愿调用隔离进程，不迁移或删除实现。方法变化按新SHA重新联调，不只看包版本。教学情景不代表实际收益或可交易。
