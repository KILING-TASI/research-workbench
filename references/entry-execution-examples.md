# 研究入口与接续示例

按已识别的任务读取本页；教学输入只用于验证运行，不代表真实研究验收。


首次使用、验证安装或用户不知道从哪里开始时，先读[五分钟快速开始](quickstart.md)。可用 `python scripts/start.py demo --out-dir local-data/first-comparison` 生成无需网络和可选组件的教学报告。正式研究使用真实输入；失败时向用户解释原因与下一步，不把教学成功当作联网或全维度评价通过。

单家A股近一/三个月公告问题，可使用 `scripts/start.py ask --question "用户问题" --as-of 实际截止日 --online --out-dir 新目录`。从自然语言识别名称并主动检索，不要求作者本地目录；取得元数据后继续按问题阅读关键原文，不能把partial线索报告说成完整公司评价。其他场景沿用对应研究入口，不误送入公告路由。

已有基金代码与区间、持仓表格或组合历史输入时，按[日常简明入口](practical-entry.md)使用start.py的funds、snapshot、portfolio，复用既有计算。仅有金额先交付结构快照，不能输出行业重叠、健康评分或未来风险；关键参数由AI从会话组织，未明确的币种、单位和资金用途需确认。

基金比较可使用完整名称；歧义先给候选，比较池名称可省略。续问优先复用当前结果的research-request.json和原响应，使用funds --continue-from并另建输出；不继承联网许可。用户想找旧报告时，使用research_results.py检索用户指定父目录，不扫描其他私人目录。比较正文先回答历史取舍，再解释回撤修复与月末阶段差异；这些不是个人回本预测或完整产品评价。

snapshot、portfolio、compare和news也支持保存请求接续；更新资料使用用户确认的新输入，不默认刷新价格。用户只想看结构时先用已有市值回答，不将完整穿透和交易历史作为所有问题的前置要求；失败时优先给可读处理说明，成功部分继续保留。新增证据再按实际问题深入，不机械追加完整研究章节。

style、lookthrough和rebalance接入同一结果导航与接续。再平衡先解释收益、回撤和费用取舍；复用已有历史，费用与频率由AI按用户要求准备，缺项须确认，不默认免费交易。通用份额模型不写成真实A股成交或场外基金申赎结算。穿透按证券别名、发行人及基金投资边分别处理，保留原路径和未知；有效持仓与冗余只描述已知股票范围，“独有公司为零”不能写成没有作用。用户未提供基准或底层报告时说明需要什么，不从净值或名称补造。

最小离线示例：用户问“这条消息关联哪些持仓？”时，可先用包内教学输入验证入口：

```bash
python scripts/retail_research.py references/examples/news-example.json --out-dir local-data/news-example
```

输出result.json、研究结果.md和研究结果.html。示例为教学消息与金额；正式研究换成实际持仓和已取得事件，不将关联暴露当作预计损失。输出目录须为新目录；依赖缺失、下载失败或字段缺失按[失败输出](execution-contract.md)保留原因，不伪造成功。安装和环境检查见[README](../README.md)与[独立安装](standalone-install.md)。

公式、参数、行业方法和专业依据见[方法与参数索引](capability-reference-index.md)。北交所、宏观指标与ETF轮动调用见[专用脚本](integrated-topics.md)，代码已在主包内；项目工作台和历史缓存路径不默认触发。数据源失败时按需读[体检说明](source-health.md)。

对外功能介绍见[功能说明](current-capabilities.md)，实际已核范围见[当前案例范围](acceptance-current.md)。分发或分享原文附件前查[许可说明](third-party-notices.md)。

找回与续问的完整模板见[日常入口](practical-entry.md)：按关键词查找、明确名称选择、参数复用及自动另存。常用续问可使用 `scripts/resume_research.py --previous <已选定结果目录> --question "沿用上一份，只看近一年" --out-dir <新目录>`。仅支持文档列出的短句；最近区间以旧截止日为基准，额外参数变化须明确，不继承联网许可。详见[日常入口](practical-entry.md)。
