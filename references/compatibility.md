# 软件版本、接口与测试组合

本轮工作台版本为beta.10，专业版本为基金穿透0.2.3、财报核对0.2.3；组合引擎0.8.2是已发布版本。历史beta.7/专业0.2.0记录只说明当时组合，不作为当前兼容保证。

| 工作台入口 | 提供者 | 所需接口 | 验证与边界 |
|---|---|---|---|
| 六列完整股票表 | cn-fund-lookthrough 0.2.3 | report_adapter.issuer_order_values / legacy_domestic_rows / legacy_domestic_result | 当前CI固定源提交执行迁移回归；不表示任意基金PDF适用 |
| schema1原文核对 | cn-financial-reconcile 0.2.3 | original_compat.verify | 当前CI固定源提交执行正/反例；不表示全部财报自动审计 |
| 观察账户收益 | portfolio-decision-engine 0.8.2 | observed_review.review，observed-review-workbench-bisection-v1 | 当前CI固定源提交执行金额、时点与费用反例；不是真实账户恢复或全交易回测 |
| 其他有界原生入口 | 各仓明确版本/契约 | 见bounded-native-bridges.md | 分别验证，不从上述三仓组合推定其余工具兼容 |

固定提供者提交见.github/workflows/validate.yml；CI通过只能说明所列提交及测试范围。方法源文件摘要由实际调用记录保存。工作台只定位/加载用户明确选定的安装包或可信目录，不自动升级、不以版本号相似代替接口检查；doctor只检查定位，不执行真实资料验证。

软件版本说明代码包；输入schema说明结构；method/rules版本说明计算定义；数据日期、发布日期、研究截止日分别说明数据时点。改进安装、报告或提示不会要求重写历史计算方法版本。未来版本、未列组合和非固定提交不能自动当成已验兼容。

各工具可单独使用。基础教学不要求安装九仓；缺专业包仅阻断需要其接口的入口。pip安装、Skill注册、可选PDF/行情组件是不同步骤，按所用入口准备。真实案例见财报仓的美的现金覆盖案例，其问题范围不代表九仓全流程均已认证。

本轮显式源码探针的[记录](compatibility-probe-20261010.json)保存提供者版本与方法文件SHA，成功执行A/H排序和一组教学观察账户，财报项执行未知schema拒绝。该探针不代替固定提供者CI完整迁移正例，也不宣称PDF全格式或全部依赖组合通过。复现工具为scripts/compatibility_probe.py，必须明确三个可信项目目录和新输出文件。
