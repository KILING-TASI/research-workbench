# 投研工作台：详细使用说明

当前安装与教学入口见[首页](README.md)，资料准备见[BEGINNER](BEGINNER.md)。历史下载说明见[版本记录](CHANGELOG.md)。以下保留具体命令、方法、样本和限制，历史案例按各自日期阅读。

## 看几个历史研究案例

以下摘自2026-10-06的案例范围记录，展示当时回答过的问题及仍未完成的部分。它们不是今天重新取数或验收的结论；本页不公开原始 PDF、私人账户和作者缓存。

| 场景 | 代表报告 | 当时已回答 | 仍未完成 |
|---|---|---|---|
|公司研究|国电南瑞：订单增长，利润与现金兑现仍待跟上|半年收入与利润现金是否同步；披露的产品及地区增长是否均衡|完整估值吸引力；现金调节项目的逐笔经济原因与结算明细|
|组合诊断|两基金组合：低重叠，为什么仍有明显回撤？|历史组合回撤与相关性；不同维持权重方式影响|完整细分行业及剩余资产暴露；真实账户和费用后收益|
|北交所新股研究|莫森泰克：预算增加，为什么未必多获一百股？|历史资金档位；发行PE口径|完整价值与年化；首次公开与真实账户|
|公司研究·医药新案例|恒瑞医药：利润持平，哪些变化被掩盖了？|选定财务表现方向差异；归母与扣非差额桥接|非经常性项目交易、估值及上期构成；现金变化来源与持续性|
|FOF穿透|南方全天候FOF：债券毛额为主，仍需看权益、利率与融资|直接与已核间接股票暴露怎样相加；取得报告数量与底层解析覆盖如何区分|来源警告、1元股票会计差额及511090不计息负调整182,210.66元的具体经济构成；完整逐券及多层非股票穿透；完整行业、发行人重复风险及衍生品净敞口|
|公司研究·水电新案例|长江电力：利润改善，现金与经营驱动仍需分开看|选定利润与现金同比方向是否一致；财务费用下降能否直接当归母利润贡献|完整三表及利润现金经济原因；来水、同范围售电量价与业务拆分|

[全部16份历史案例及版本范围](references/acceptance-current.md#2026年10月6日16份历史范围记录) · [当时范围摘要](references/validation/current-case-scope-20261006.json)


## 按问题选择独立工具

| 你想核对什么 | 工具 |
|---|---|
| REITs经营、扩募与份额估值 | [cn-reits-research](https://github.com/KILING-TASI/cn-reits-research) |
| 净值与宏观微观资料格式和重放 | [cn-data-adapters](https://github.com/KILING-TASI/cn-data-adapters) |
| ETF相对强弱、轮动规则与固定池历史情景 | [cn-etf-rotation-engine](https://github.com/KILING-TASI/cn-etf-rotation-engine) |
| 基金底层公司是否重叠 | [cn-fund-lookthrough](https://github.com/KILING-TASI/cn-fund-lookthrough) |
| 财报金额与口径是否一致 | [cn-financial-reconcile](https://github.com/KILING-TASI/cn-financial-reconcile) |
| 组合敞口、配置情景与现金占用 | [portfolio-decision-engine](https://github.com/KILING-TASI/portfolio-decision-engine) |
| 北交所比例获配情景 | [bjx-ipo-engine](https://github.com/KILING-TASI/bjx-ipo-engine) |
| 转债现金流、收益率与条款 | [convertible-bond-engine](https://github.com/KILING-TASI/convertible-bond-engine) |
| 规则版本与公告适用条件 | [cn-market-rules](https://github.com/KILING-TASI/cn-market-rules) |
| 宏观指标、来源与缺口 | [macro-dashboard-engine](https://github.com/KILING-TASI/macro-dashboard-engine) |
| 市场消息与执行证据 | [marketlens](https://github.com/KILING-TASI/marketlens) |

各工具独立发布。导航不代表工作台已自动集成全部功能；具体接口范围见[衔接说明](references/tool-navigation.md)。


## 已有报告，可以怎样接着问

| 可以直接说 | 处理边界 |
|---|---|
| 这几只基金只看近一年，哪只更稳？ | 沿用旧截止日，分别看波动和回撤；不强选统一赢家 |
| 我的组合收益主要靠谁？ | 需要已声明收益路径，不把持仓金额当风险贡献 |
| 沿用上一份，把资金改为1,250万元 | 仅更改明确预算，原资料与日期保留，另存结果 |

需先选定支持接续的报告，并由已注册 Skill 的助手或相应入口处理。[更多句式与支持范围](references/practical-entry.md)


## 结果是什么样

教学例子会先说明：**在这段区间里，A 上涨 10%，B 下跌 10%；A 的区间表现更好，但不能据此判断长期能力。** 随后列出依据、计算口径和还缺哪些资料。

这里只有两个日期，年化波动等长期指标不输出，也不评价经理能力。你可以下载[教学报告](references/examples/readme-preview.html)后在本地打开，或查看[对应输入](references/examples/readme-preview-input.json)和[生成记录](references/examples/readme-preview-manifest.json)。这份预览保留原有版本；该页面已于2026-10-11完成桌面显示检查，记录见上方截图说明。


## 能做什么

| 你想解决的问题 | 主要能得到什么 |
|---|---|
| 这家公司值得继续研究吗？ | 业务、财务、同行和估值研究；结论所依赖的假设、风险与后续核对事项 |
| 几只基金或 ETF 有什么区别？ | 对齐区间后的收益风险、费用、经理及公开持仓比较；资料不足的维度单独说明 |
| 我的组合是否重复押注？ | 持仓集中度、底层重合和未知部分；有历史明细时再分析收益、风险及调整情景 |
| 宏观和政策变化意味着什么？ | 指标与政策解读、不同资产的同期表现；不把同期变化直接当成因果关系 |
| 北交所新股申购资金怎样测算？ | 发行事实、给定获配率下的情景与资金占用；不能保证获配或收益 |
| 上次的研究还能接着用吗？ | 找回报告、沿用已保存输入继续研究、追加笔记及比较新旧结果 |

本项目负责组织研究、写出判断和报告；需要专门的持仓、财报或组合计算时，再调用对应工具。[完整功能说明](references/current-capabilities.md)和[按问题选择工具](references/tool-navigation.md)列出具体范围。

**暂不支持：**任意标的全量资料的一键获取、实时行情保证、默认后台监控、交易执行或收益承诺。REITs 条件估值由独立 cn-reits-research 提供，完整真实产品经营底稿仍需准备；机构预测档案可以离线留存观察，但不是完整一致预期数据库。其他缺口见[详细交付说明](references/development-validation.md)。


## 怎么安装，哪些依赖要准备

这是一个 **Skill，也提供 Python 命令行入口**。实际 Skill 名称是 `research-workbench`，展示名称是“投研研究助手”。在支持 Skill 的 AI 工具中安装时，使用 `research-workbench` 目录并保留完整资源，不要只复制一份说明文件：

```text
research-workbench/
  SKILL.md
  agents/openai.yaml
  scripts/
  references/
  modules/
```

只想运行命令，不必先把 Skill 装进 AI 工具。把文件放进 Skill 目录后，所需软件仍要另行准备，具体步骤见[安装说明](references/standalone-install.md)。不启动网页工作台也能研究。

| 使用范围 | 软件前提 |
|---|---|
| 上面的离线教学、已有净值比较、持仓表整理 | 基础 Python 环境；不统一要求安装专业包 |
| PDF 文字和表格读取 | 按入口准备 `pdfplumber`、`pypdf` 等组件 |
| 六列完整股票表解析 | 兼容的 `cn-fund-lookthrough` 和 PDF 组件 |
| 指定财务行列的原文核对（schema1 入口） | 兼容的 `cn-financial-reconcile` 和 PDF 组件 |
| 含出入金的账户收益测算 | 兼容的 `portfolio-decision-engine` |

配置矩阵、部分 Excel 和 JavaScript 入口有各自依赖，不必为了试用一次就全部安装。普通组件、可选 PDF 组件和自家专业包是三类不同前提；安装了 PDF 组件不等于安装了专业工具。

历史beta.7 对应的专业版本是 `cn-fund-lookthrough 0.2.0`、`cn-financial-reconcile 0.2.0` 和 `portfolio-decision-engine 0.8.0`，这三版均已上线；这不是当前版本的兼容结论。[当前兼容矩阵](references/compatibility.md)区分已测接口、软件版本和未认证范围。从各仓库的 GitHub Release 页面取得对应 wheel 或源码，再装入当前 Python 环境；不假设这些包已经上传 PyPI，也不把旧版默默当成兼容替代。

[持仓工具 Release](https://github.com/KILING-TASI/cn-fund-lookthrough/releases) · [财报工具 Release](https://github.com/KILING-TASI/cn-financial-reconcile/releases) · [组合工具 Release](https://github.com/KILING-TASI/portfolio-decision-engine/releases)。安装后检查例子见下文；本程序不自动下载或安装。

只检查账户收益入口，可以运行：

```powershell
python scripts/start.py doctor --for-entry cashflow --out-dir local-data/check-cashflow
```

检查不会联网或安装软件。缺专业包只暂停需要它的那项计算，其他研究按各自资料条件继续；来源未核、数据缺期也不会被当成软件缺失。

[基金持仓穿透](https://github.com/KILING-TASI/cn-fund-lookthrough)和[财报金额核对](https://github.com/KILING-TASI/cn-financial-reconcile)都提供 Skill 说明与命令行入口，可以独立使用，不依赖本工作台运行。其他工具的职责见[工具导航](references/tool-navigation.md)。


## 联网与资料使用

上面的试用完全离线。按名称查询公司公告、刷新基金净值等入口需要显式启用联网，并取决于来源是否可访问；软件检查通过不代表数据已取得。

正式研究会保留来源、日期、口径及资料缺口。未知值不补造，假设不写成已发生的事实。[数据源检查](references/source-health.md)和[执行说明](references/execution-contract.md)解释获取失败、资料不足时怎样处理。


## 验证、许可与使用边界

离线教学、隔离安装和部分研究场景已做实际运行检查，具体范围见[验证说明](references/validation-scope.md)、[当前案例范围](references/acceptance-current.md)。这些检查不代表任意真实标的都能分析，也没有证明 AI 工具已经识别安装，或报告排版已通过视觉检查。

有权授权的原创代码和说明采用 [MIT](LICENSE)。第三方代码、公告、研报、行情数据和品牌的权利分别处理，详见[第三方与数据说明](THIRD_PARTY_NOTICES.md)及[来源许可核查](references/third-party-notices.md)。

本项目用于学习和研究，不构成投资建议，不执行交易，也不保证收益。请结合本次来源、假设和缺口独立判断；[完整免责声明](DISCLAIMER.md)保留具体使用边界。


## 公告问答的可用句式

当前公告路由只支持单家A股、近一或三个月，并非任意自然语言解析器。可以说“查询招商银行近三个月的公告”或“查看600036近一个月的公告”。输入JSON也可明确填写 `code` 或 `query`，并提供 `asOf`。名称无法唯一确认、日期冲突或超出支持范围时，先澄清，不猜测代码或忽略条件。


## 验证范围

源码教学启动、软件环境查询和安装后教学入口分别验证；软件就绪不等于真实资料已取得。中文问答需要助手按本仓Skill准备已声明输入，没有宣称任意自然语言自动发现或全市场数据闭环。旧报告、历史tag与案例证据保留。


本轮新增预测实际配对、公开问答、假设变化与可迁移引擎索引。独立入口、底稿与限制见 [EXPANSION.md](EXPANSION.md)。


共同采集与观察表的单位、时间及版本范围见 [FORMAT_SCOPE.md](FORMAT_SCOPE.md)。宏观、微观和规则事件保留各自口径，不混作净值。
