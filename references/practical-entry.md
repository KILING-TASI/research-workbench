# 日常使用：少准备参数，直接拿到结果

更新日期：2026-10-08。以下命令从Skill根目录运行，输出目录必须不存在。对话使用时直接说问题，AI根据已确认资料准备这些参数，不让普通用户填JSON。

## 我想比较两只基金

```bash
python scripts/start.py funds --codes 005827 161005 --start 2025-01-02 --as-of 2026-09-30 --group "我的比较池" --online --out-dir local-data/my-funds
```

换成实际代码与研究区间。只支持2至10只明确六位代码的场外基金；ETF研究用ETF入口。比较池名称由用户声明，不认证为同类。--online 表示主动把代码发给第三方净值接口，不需要作者缓存或账号。

打开 `comparison/基金比较说明.html`。开头说明历史表现优势或收益与回撤的取舍；底稿保留原响应、哈希、实际共同日期、输入与计算结果。分红按供应商已记录事件理论再投，缺失或特殊事件不猜测；某只失败时不自动删掉它生成缩小池报告。查看collection.json，补资料后另建输出目录。

边界超过7个日历日未覆盖时停止该项比较，提示确认成立日、停更或研究区间；此检查不能认证交易日完整性。币种、分红完整性、合同基准、经理、持仓和费率尚未原文核验，此入口是历史比较，不是完整选基或经理排名。

## 我只有一张持仓表

将表格导出UTF-8 CSV，使用列 `code,name,market_value,currency,asset_class`；可加 `valuation_date`。示例见[教学持仓表](examples/holdings-example.csv)。market_value是当前市值，不能填份额或投入本金；currency如CNY；asset_class由用户确认，为fund、etf、stock、bond、convertible、cash或other。

```bash
python scripts/start.py snapshot --input my-holdings.csv --as-of 2026-10-08 --out-dir local-data/my-snapshot
```

报告回答“钱在哪里”：总金额、每项占比、最大持仓位置和资料缺口。不从基金名称猜行业，不把类型占比当成穿透的大类敞口。混币种拒绝相加，重复代码先确认后合并；A/C代码不同但可能共享底层组合。没有阈值、底层和历史时，不打健康分，不输出最大回撤或再平衡指令。

本入口不联网，原表与结果仅保存在指定目录。截图研究时先由AI识别并向用户说明不清楚的字段，再生成CSV；金额单位不明确时先确认，不猜万元。

## 我已经有组合历史资料

```bash
python scripts/start.py portfolio --input portfolio-input.json --out-dir local-data/my-portfolio
```

输入沿用[组合历史研究](portfolio-stress.md)，不是仅有金额的CSV。复用现有共同历史计算，报告解释组合收益、共同路径最大回撤、各资产收益贡献、相关性和尾部样本。买入持有与固定权重结果按指定口径区分；不还原实际账户交易，不预测未来损失。

## 怎样判定本次完成到哪一步

- snapshot的partial：结构快照完成，完整风险诊断未完成。
- funds的partial：共同区间历史比较完成，完整产品评价未完成。
- portfolio的partial：输入声明下历史分析完成，实际账户和来源完整性未认证。
- blocked：输入、数据或运行条件不满足，保留原因和下一步；不会把缺资料标成通过。

这三个入口改善日常操作，不新增全市场数据库、不创建后台任务。更深入研究按[现有功能](current-capabilities.md)继续处理。
