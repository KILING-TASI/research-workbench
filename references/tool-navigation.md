# 按问题选择工具

更新日期：2026-10-11。本页是当前源码的工具导航。十二个仓库分别开发、测试和发布；存在仓库不等于主包已集成其全部能力。

|你想解决什么|工具|交付与衔接范围|
|---|---|---|
|研究公司、基金、ETF，比较产品，找回报告继续问|[research-workbench](https://github.com/KILING-TASI/research-workbench)|理解问题、组织公开资料、建立判断并生成报告；工作台可选|
|多只基金是否重复持有同一批公司|[cn-fund-lookthrough](https://github.com/KILING-TASI/cn-fund-lookthrough)|证券/公司敞口、未知路径、已映射股票集中度；主包已有显式JSON桥，独立仓增量另核华夏成长2025年报和单日选定发行人；主包PDF桥仍只接原限定产品|
|财报金额是不是同口径、原文差多少|[cn-financial-reconcile](https://github.com/KILING-TASI/cn-financial-reconcile)|金额差异/舍入/不可比；主包有显式JSON桥，行列定位仍限定金额，不是完整三表认证|
|比较组合配置、回撤预算、成本与现金流|[portfolio-decision-engine](https://github.com/KILING-TASI/portfolio-decision-engine)|窄范围TWR/XIRR对照与现金需求原生透传已验；全部模型迁移未验，不自动替换|
|北交网上发行比例获配情景、占款与复盘|[bjx-ipo-engine](https://github.com/KILING-TASI/bjx-ipo-engine)|有限单发行API原生桥已验；年度/滑点/融资不等价，内置专题保留|
|可转债现金流、收益率与条款条件|[convertible-bond-engine](https://github.com/KILING-TASI/convertible-bond-engine)|固定未来现金流原生桥已验；非平坦曲线/条款权利不作全部等价，内置诊断保留|
|证券市场规则、个案条款与离线情景|[cn-market-rules](https://github.com/KILING-TASI/cn-market-rules)|信封1.2/共用1.0可选消费已验，版本选择与项目未知分开；不认证实际资格|
|公开宏观数据与周期代理指标看板|[macro-dashboard-engine](https://github.com/KILING-TASI/macro-dashboard-engine)|独立宏观看板；不是主包全量数据库或自动后台监控|
|REITs经营、权益与扩募的条件估值|[cn-reits-research](https://github.com/KILING-TASI/cn-reits-research)|产权/经营权、多项目、基金费用/债务/份额、分派与IRR；独立使用，工作台只组织资料和档案，不声称自动接入|
|净值采集格式、冻结重放和宏观微观表映射|[cn-data-adapters](https://github.com/KILING-TASI/cn-data-adapters)|一个净值渠道及两个原生档案格式；CSV表显式映射；来源不自动认证|
|校验资料身份、单位、时点和来源结构|[cn-research-contracts](https://github.com/KILING-TASI/cn-research-contracts)|净值采集及显式观察表版本；保留规则库既有信封，不强制安装共用仓|
|市场叙事是否有证据，计划是否真的执行|[MarketLens](https://github.com/KILING-TASI/marketlens)|股票/ETF/政策叙事证据、限定观察池代理、份额估值/融资分歧及计划执行区分；[发布版本](https://github.com/KILING-TASI/marketlens/releases)，尚未接入主包，不替换既有份额观察/事件台账|

## 工具关系

```mermaid
flowchart TD
    U[用户研究问题] --> W[research-workbench：组织资料与判断]
    U --> I[也可直接使用独立工具]
    W -. 可选显式JSON调用 .-> L[cn-fund-lookthrough：披露持仓]
    W -. 可选显式JSON调用 .-> F[cn-financial-reconcile：金额核对]
    I --> L
    I --> F
    I --> P[portfolio-decision-engine：组合]
    I --> B[bjx-ipo-engine：北交发行]
    I --> C[convertible-bond-engine：转债]
    I --> R[cn-market-rules：规则]
    I --> M[macro-dashboard-engine：宏观]
    I --> N[MarketLens：市场叙事证据]
    I --> T[cn-reits-research：REITs经营估值]
    I --> D[cn-data-adapters：资料接入与重放]
    D -. 固定旧版净值实现随包，非全部新入口集成 .-> W
    I --> K[cn-research-contracts：格式校验]
    W -. 有界原生契约，限定范围 .-> P
    W -. 有界原生契约，限定范围 .-> B
    W -. 有界原生契约，限定范围 .-> C
    W -. 信封1.2/交接1.0，限定范围 .-> R
```

虚线代表已提供的有限可选JSON/原生接口；未画连线的工具不意味着主包已经自动调用。用户不必安装全部仓库。主包不自动下载或安装独立工具，调用者明确可信目录；各仓库的README和版本记录决定实际可运行范围。

## 先看什么结果

- [主包教学比较预览](examples/readme-preview.html)：说明共同区间表现取舍，不是完整基金评价。
- [独立持仓预览](https://github.com/KILING-TASI/cn-fund-lookthrough/blob/main/examples/readme-preview.html)：已知/未知一起展示，不把覆盖率当准确率。
- [独立财报预览](https://github.com/KILING-TASI/cn-financial-reconcile/blob/main/examples/readme-preview.html)：数值结论与原页状态分开。

HTML需下载后用浏览器打开。三份为 demo 生成的教学结果；各页面的输入、生成时间及验收范围见对应 README，不把历史预览推定为最新版本验收。链接指向各仓当前默认分支；预览按自身生成记录阅读，不代表使用最新资料重算。

## 有限真实案例与缺口

007119中报77条股票的独立适配与旧主包逐项等价，财报原表选定六个金额重新提取一致；见[本批验证](development-validation.md)。原件不随代码发布；这不能外推到其他管理人/任意版式。独立持仓库另验华夏成长132条股票；主包新增离线预测档案，公开转述缺机构原文/实际配对；REITs估值已由独立仓按完整声明底稿实现，真实公告案例仅核两份分配公告；完整真实产品经营底稿仍需自行准备，不把教学现金流冒充实际估值。预测/实际与重述已有显式配对入口，原公开转述样本缺口仍保持。更完整的接口与迁移边界见[独立工具衔接](independent-engines.md)。

公司监管事件由主包组织证据与解释；规则库只提供定义、条款与版本。现有小样本事件台账不等于全量检索/完整时间轴，规则接口只在已验有限范围消费，其他版本仍保留缺口，不给自动违规或退市概率。


主包负责问题入口、资料组织、薄调用和报告找回；独立算法/样本维护归各仓。MarketLens只新增问题导航和归属，不创建第二套市场噪音模块，不宣称接入或迁移。它独立发布，工作台导航不代表已集成调用。各仓代码/第三方/数据许可逐仓核验；本页不因共同作者而推定新仓全部素材MIT。
