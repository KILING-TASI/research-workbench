# 基金专项分析与统一调用

复用业绩、行业、归因、费用、比较与原文模块，不重写现有公式。新增公开快照的风格、资产配置、行为和研究条件分析。用户直接提出研究问题，AI收集现有资料并整理输入，不要求用户选择脚本或填写JSON。经理观点仅从年报提取。

## 调用

```text
python scripts/fund_specialists.py research INPUT.json --out NEW.json
python scripts/fund_specialists.py allocation INPUT.json --out NEW.json
python scripts/fund_specialists.py behavior INPUT.json --out NEW.json
python scripts/fund_specialists.py style INPUT.json --out NEW.json
python scripts/fund_specialists.py conditions INPUT.json --out NEW.json
```

共同字段code、asOf。research另外有inputs对象，可给allocation/behavior/style/conditions/manager/attribution对应输入。先按已有检索、采集、报告解析、历史对比流程取得资料，再自动运行已有输入，单项失败留gaps；结果depthResults可直接传综合报告。manager/attribution复用fund_depth参数。无数据的模块不运行不编造，不称全市场自动闭环。

### 资产配置

reports递增数组，每期code/reportDate/publishedAt/sourceUrl/weights。weights是占NAV小数且合计1，键aEquity/hkEquity/otherEquity/straightBonds/convertibles/cash/other/unknown。普通债券不含已单列转债，避免重复；未取得债券/现金分类时保留unknown。输出时序仓位、变化百分点；unknown非零不给完整配置距离。距离不是交易换手、不是择时收益。未补C-L/H-M/T-M择时能力模型。

### 披露持仓行为

reports每期共同元数据加scope=top10|completeEquity、equityWeight、holdings（market/code/shareClass/weight，支持明确securityNamespace）。完整权益需与股票总仓位勾稽。输出相邻快照共同证券数、观察留存率、新披露/不再披露、逐证券观察期时间线。只有完整股票快照给绝对权重变化；前十大不再披露不认定卖出。连续报告出现不证明期间连续持有。不能还原交易流水、平均真实持股周期、交易胜率或隐形交易能力。

### 持仓风格与指标暴露

reports每期完整股票数据加classification：sourceUrl/effectiveAt/taxonomy/version/verified/securities。securities按同证券主键提供styleLabel与可选metrics数值。分类来源、定义和版本须实际核验；不能把verified改为true替代核验。分类生效日晚于报告日拒绝。只有完整权益才分析，未知分类保留未知，不输出完整漂移评分。多期分类一致并覆盖完整时复用fund_depth.changes计算分布总变差。

metrics计算已知持仓的加权均值及每项覆盖率，可放ROE等原始指标。PE加权均值不称组合整体PE；不将输入标签或均值称晨星认证九宫格、BARRA五因子或经理纯alpha。五因子分数与证券自动分类数据源仍需另外补齐。

### 研究条件核对

facts每项field/value/observedAt/sourceUrl，规则rules每项field/op=lt|gt|le|ge/threshold/label。日期不超过asOf；同字段多事实视冲突，不随意选值。输出触发/未触发/未知，不输出准入投资评级。可检查规模、费用、机构持有人比例等已取得事实；经理履历与申赎限制缺项不猜。

## 综合报告

fund_diagnostics.js report允许上述四种结果加入depthResults，主体与截止日核对，来源并入引用。HTML展示仓位、快照变迁、风格覆盖和研究条件，边界伴随对应表格。阶段复盘区别快照变化与真实交易。依赖已取得资料，任意基金完整全自动、盘中净值、全市场拥挤度、完整经理画像和言行一致评分尚不提供。

风格分类须有明确taxonomy和version；可提供effectiveTo、publishedAt。分类已失效或披露晚于研究截止日时拒绝；晚于持仓快照才披露的分类标为retrospective-only，缺披露日不证明事前可得性。指标暴露仅为输入数据计算，另标未进行原文数值核验。研究条件的字段、运算符及阈值在匹配事实前检查；单项参数/文件/依赖失败保留该项缺口并继续其他已授权专项，不声明完整评价。
