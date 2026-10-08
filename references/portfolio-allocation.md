# 配置候选与历史风险比较

比较方法与用户明确约束，不生成交易指令。输入有2至6只资产完全对齐的总回报序列、币种、daily/monthly频率、截止日和来源；至少25个价格观察。净值代理限制放入scopeNotes。

## 入口

```text
python scripts/start.py allocation --input INPUT.json --out-dir NEW_DIR
python scripts/start.py allocation --continue-from OLD_DIR --out-dir NEW_DIR
python scripts/portfolio_allocation_report.py --continue-from OLD_DIR --max-weight 0.6 --out-dir NEW_DIR
```

用户用自然语言给条件，由AI准备参数。统一下限minWeight、上限maxWeight为小数比例，默认0和1须在报告明示。两资产40%上限无解，不能自动增加现金。失败保留有效输入与下一步，修正后另存续算。

## 方法和约束

- 等权基线；最小方差与历史前沿实际执行统一上下限。
- 每资产assetClass注明类别，classConstraints为类别到{min,max}映射，最多3类；类别约束贯穿最小方差与前沿。
- 风险平价是原始ERC候选，检查残差和上下限，不满足则标不合格；不裁剪冒充约束ERC。
- covarianceMethod默认sample；可选ledoit-wolf-constant-correlation自动常相关收缩。shrinkageIntensity是显式强度对照，不能与自动方法同时给。记录强度与依据，不保证样本外风险改善。
- sensitivityWindows为最多8个唯一收益观察数，范围24至5000；截止日一致，资料不足单列，窗口重叠不是样本外。

逐资产差异上下限、现金缓冲、卖空和Black–Litterman观点尚未接入，指定时拒绝。历史均值不称未来收益。

## 交付

中文HTML/Markdown、输入、结果和主报告清单，可检索与续算。换上限时比较权重和估计波动；旧条件无解不做数值对照。未含实际成交、完整现金流交易模拟、回撤预算及样本外选择，不能称完整组合决策引擎。

## 独立教学例
安装numpy后，可离线运行python scripts/start.py allocation --input references/examples/example-allocation.json --out-dir NEW_DIR。本例虚构3资产序列，带上下限、类别约束、自动常相关收缩及窗口缺口。生成与追问均保留teaching-only，不是真实市场资料。

补充风险集中度、协方差诊断和自举误差的范围见[补丁核对](engine-patch-review.md)。
