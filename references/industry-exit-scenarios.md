# 供需、集中度与退出现金流

三个模式共用来源、单位、截止日和文件哈希校验，按需调用，不新增工作台菜单。

## 调用

```powershell
python scripts/industry_exit_scenarios.py supply supply-input.json --out-dir supply-report
python scripts/industry_exit_scenarios.py concentration concentration-input.json --out-dir concentration-report
python scripts/industry_exit_scenarios.py exit exit-input.json --out-dir exit-report
```

输出目录须为新目录。输出 result.json、研究情景.md、研究情景.html，保存完整输入、公式和计算代码哈希。

## 数值来源

每个数值采用 `{value: 100, basis: "assumption", note: "明确假设依据"}`。basis 可为 source-statement、calculation、assumption；前两者还需 sourceUrl（HTTPS）、locator、publishedAt。日期使用 YYYY-MM-DD。未知值使用 null，不填零。sourceFiles 为 path、sha256 列表。

## 供需输入与输出

顶层 name、scope、unit、asOf；periods 内 start、end、openingInventory、production、imports、exports、demand、closingInventory，capacity 可选。数量单位与产品地区范围一致。期间连续时核对库存衔接。计算可供量、期末库存、差额和产能利用率；不自动配平。未来期流量须为显式假设；当前接口不将原文预测当历史实绩。

## 集中度输入与输出

顶层 name、scope、unit、asOf、period、marketTotal、universeComplete；firms 内 id、name、volume。完整样本须与市场总量一致。部分样本输出未知份额及 CR3/CR5、HHI 保守上下界，不归一成全市场。品类结构与企业竞争份额必须明确区分。

## 退出输入与输出

顶层 identity.name、currency、unit、asOf；scenarios 内 name、cashFlowCoverage、costCoverage，后两者分别为 declared-complete 或 partial；flows 内 date、kind、amount。kind 为 investment、proceeds、distribution、fee、tax。明确完整费用时也须提供费用和税收条目，零值需有依据。现金流和费用均完整、日期有效且聚合现金流仅一次变号才计算 XIRR；其他情况保留缺口。完整声明是输入声明，不等于真实账户验证。

## 验收范围

USDA 2026年9月 WASDE 第11页的两期美国小麦数据用于供需核对；后一年度整数合计差额保留，并结合原文四舍五入说明解释。三个品类仅用于部分份额结构验收，不证明企业竞争格局。退出计算区分行情锚定的假设现金流与真实交易，分红、税费不全不输出完整年化。

## 失败处理

单位冲突、来源日期晚于截止日、哈希变化、样本超过市场总量或现金流类别无效时停止该计算，保留输入以供复核。模型不自动获取所有产业数据，不提供退出路径执行或收益保证。

企业竞争份额另以IDC 2026Q2全球智能手机新出货数据验收：五家按来源母公司口径的企业，覆盖约72.28%，其他主体约27.72%保留未知。依据企业出货/市场总量计算份额，与来源四舍五入份额对照；Others不视为单家公司。来源表为2026年8月发布、网页可更新，因此保留原网页哈希快照；范围不含OEM或翻新机，亦非终端零售销量。不据集中度推断企业壁垒或违法垄断。
