# 统一证据接口、字段冲突解释与研究快照包

scripts/research_evidence.py export|conflicts|package 输入.json --workspace 用户目录 --out 新结果.json；verify 包目录 --out 新结果.json。仅标准库；读取发行事实库需原模块，核验已登记文件不重新抽取PDF。旧命令不变。

export支持factsStore/code/asOf、companyResult（公司研究结果JSON）和显式nodes，可组合。输出schemaVersion=1、nodes与原文件attachments。节点遵循evidence-chain.md；发行事实保留所有截止日前版本，原文核验状态不升级。公司研究目前映射原文摘录/表格证据，不自动导出全部财务比率、估值及现金派生节点。显式derived节点须formula与dependsOn，检查重复ID、依赖缺失与循环；其他模块数值尚需明确接入，不能声称所有结果自动统一。

conflicts读取export输出，按subject/metric分组，比较单位、期间、口径和值；多个文档版本仅作为原因候选，不按最新日期裁决。声明supersedes会排除被更正版本，但其真实性仍需人工原文核对。不同单位不自动换算，不同年度不混为一个值，未解释冲突resolvedValue=null。consistent-under-declared-metadata仅代表声明元数据下一致，不是事实认证。

package输入示例：

```json
{"mode":"research","evidence":{"factsStore":"用户事实库","code":"920022","asOf":"2025-09-09"},
 "dependencies":[{"path":"研究输入.json","role":"research-input"},{"path":"适用规则.json","role":"rule"},{"path":"计算结果.json","role":"calculation-result"}]}
```

自动复制证据接口列出的原PDF、披露目录和公司研究原文件，以及用户声明的依赖。dependencies必须包含research-input/rule/calculation-result三种角色；相同文件可以有多个角色，但角色声明不证明文件内容真实或规则适用。计算代码、配置、其他报告和已有首次预测档案可继续加入清单。研究采用哪些文件由调用者完整声明，不能自动发现任意外部依赖；completeness只表示声明的依赖闭包检查通过，不认证全部研究完整。

包保存至research-data/bjx-research-packages/独立ID，包含files/哈希命名文件、spec.json、evidence.json、conflicts.json及manifest.json。原路径留作来源线索，复核包文件不依赖原目录。verify检查清单哈希、全部文件哈希、缺失与未登记文件；文件系统管理员仍可重写全部内容，不宣称不可篡改或外部签名认证。生成包不覆盖已有包或首次预测。

mode=research为普通研究归档；historical-replay为历史回放；predecision须未来decisionCutoff（带时区），每个依赖须availableAt且不晚于截止或执行时间。自动发现文件可通过availabilityBySha256对象声明可得时间。时间检查仅校验声明顺序，不检验文件内容中的未来信息，不证明真实首次公开日期。本工具不自动创建预测冻结样本；eligibleForModelImprovement始终false，不因打包成功宣传模型改善。

单文件上限100MiB。未知来源、取证日期及核验限制保留，包中规则索引不等于规则原文已完整归档。用户账单或身份资料只在明确提供时作为依赖，不自动连接账户。
