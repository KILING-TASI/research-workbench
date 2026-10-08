# 专用脚本调用：北交所、宏观指标与ETF轮动

本文是执行层的调用参考，不是另一套用户功能目录。北交所新股研究、宏观与跨资产观察，以及基金与ETF产品研究均按[六类研究场景](current-capabilities.md)介绍；ETF轮动按问题归入产品研究、组合研究或宏观观察。

主包自带 modules 下三组专用脚本与参考，不再要求另外安装Skill。旧独立包可保留用于旧研究复查，主Skill不调用其安装路径。模块内 TOPIC.md 是按需阅读说明，不是额外注册的Skill。共同研究问题、证据与报告按主包流程组织，专题保留自己的输入结构；这不是所有专题schema已统一。

## 脚本选择

|用户问题|入口|先读|
|---|---|---|
|北交所发行事实、整手或边际资金、多股现金冲突|bjx research，子命令panel/rates/cash/run|[北交所说明](../modules/bjx-newshare-toolkit/TOPIC.md)，按问题读相应参数|
|公告登记、证据或首次预测复盘|bjx facts/evidence/review|北交所说明相应参考|
|给定新股、利率及日期的申购/回购现金账|bjx cash-ledger|[逐笔账](../modules/bjx-newshare-toolkit/references/cash-repo-ledger.md)|
|宏观指标初始化或用户请求刷新|macro standalone|[宏观说明](../modules/macro-indicator/TOPIC.md)|
|指定ETF基础报价或旧用户缓存|etf standalone|[ETF专用脚本说明](../modules/etf-sector-rotation/TOPIC.md)|
|ETF替换对照、组合压力|etf replacement/stress，已有主包对应入口也可继续复用|ETF说明对应参考|
|ETF历史、持仓、筛选及组合研究|优先主包原有ETF、基金与组合入口|[实际能力](current-capabilities.md)|

ETF独立专题基础报价不替代主包历史研究，宏观指标结果不自动改变ETF权重。北交所配售率、实际结果与情景严格区分；门槛不是保证获配。

## 统一调用

从主包根目录运行，参数由AI准备，用户不填JSON。输入和输出可用绝对路径；调用器保留当前目录，模块间用独立进程隔离同名Python依赖。

```text
python scripts/research_topics.py --list
python scripts/research_topics.py bjx research -- panel modules/bjx-newshare-toolkit/assets/example-panel-input.json --out USER_DIR/panel.json
python scripts/research_topics.py bjx research -- rates modules/bjx-newshare-toolkit/assets/example-rates-input.json --out USER_DIR/rates.json
python scripts/research_topics.py macro standalone -- --data-dir USER_DIR/macro
python scripts/research_topics.py macro standalone -- --data-dir USER_DIR/macro --refresh
python scripts/research_topics.py etf standalone -- --data-dir USER_DIR/etf --codes 510300 --as-of 2026-10-05 --out USER_DIR/etf.json --refresh
```

panel例子演示三项未知；rates是教学假设，不是真实新股。宏观不加refresh只初始化或读取用户库，初始值为空。ETF代码、区间与截止日来自用户问题，不沿用教学日期。无refresh不称刚更新。输出使用新路径，宏观用户数据目录按原模块维护自己的缓存。

## 合并后的继续规则

共享研究问题、对象、截止日和报告证据目录，但先核各模块时间与单位字段再关联，不因为JSON同在一包就认为口径一致。专题结果附来源、日期、假设和缺失状态；报告链接原始结果，保持首次记录。跨专题结论仍需经营或风险传导证据，不能把宏观标签自动转成轮动信号。

不附作者data.json、市场历史、PDF、生成页面或完整工作台缓存。只带必要计算引擎、目录、方法配置和明确教学例子。历史日历文件仅适用其标注年份，不替代新年度交易日依据。

完整工作台build/update、历史现金回放及部分轮动模型仍依赖外部项目数据，不进入统一默认动作。项目脚本虽保留参考，但缺资源时不运行；独立路径可用不代表完整轮动有效。合并没有新增实时数据、全量资料或后台调度。

分发须同时查看主包及各模块 references/third-party-notices.md；内部整合不变更第三方许可或数据使用权。独立环境验证与联网取数验证分别记录，不把教学测试称为真实标的验收。

## 服务与超时

统一调度默认总时限600秒，可用调度器 --timeout 在专题名前调整；超时返回 blocked，不称已完成。旧本地服务刷新只接受带启动时生成令牌的POST，GET仅供阅读；不要把令牌写入公开网页或研究报告。旧网页GET刷新按钮不可用，改用已授权CLI刷新或受保护POST。

涉及制度、条款、专业方法与解释时，使用[适用依据规范](research-basis-standard.md)，核对范围、版本和原始依据；规则核对不替代本场景计算或内容验收。
