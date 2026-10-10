# ETF轮动计算独立维护

新专业仓cn-etf-rotation-engine负责相对强弱、轮动门槛、市场风险档位与固定池历史情景。独立安装或设置RESEARCH_WORKBENCH_ETF_DIR为明确可信项目目录后，工作台只调用并组织报告：

```text
python scripts/research_topics.py etf rotation-review -- --input 资料.json --out-dir reports/etf-review
python scripts/research_topics.py etf rotation-backtest -- --input 资料.json --out-dir reports/etf-history
```

缺包、接口或执行失败明确不可用，不回到旧算法。方法摘要、选择目录和模块来源随新结果保存。旧standalone/replacement/stress入口参数保持，它们不自动成为新轮动引擎；基金比较、费用和整体组合仍各按原职责处理。

旧JavaScript模型作为历史网页兼容资源保留固定版本，不继续独立修改；在专业仓登记同一源与对比测试。新计算只调用专业Python实现。完整旧网页资源与综合评分工作流尚未证等价，不能为减少文件数量删除或宣称全部迁移；这部分继续单列，不把历史缓存改成新报告。
