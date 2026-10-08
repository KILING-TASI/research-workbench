# 五分钟开始第一次研究

更新日期：2026-10-08。先跑通教学示例，再换成真实资料。工作台不是必需品。

## 你只需准备 Python

需要 Python 3.11 或更高版本。以下示例只使用标准库，不需要账户、网络、Node.js、PDF组件或作者的数据目录。终端切换到解压后的 research-workbench 根目录；如果系统命令是 python3，把下文 python 换成 python3。

## 第一次：直接得到一份比较报告

```bash
python scripts/start.py demo --out-dir local-data/first-comparison
```

打开 `local-data/first-comparison/基金比较说明.html`，或阅读同目录的 Markdown。开头会给出判断，随后展示两组教学净值的收益、回撤、口径与缺口；JSON、原始输入和报告清单供复核。

**这是教学演示，不是真实基金评价。** 输入只有两个日期，不能用于判断波动、经理能力、同类排名或未来收益。报告清单证明保存内容可以核对，不证明数据来源真实。

## 第二次：消息与持仓的关联

```bash
python scripts/start.py demo --example news --out-dir local-data/first-news
```

打开生成的 `研究结果.html`。示例说明消息直接关联哪些教学持仓；关联市值不是预计损失，也不提供买卖建议。

## 第三次：检查自己的环境

```bash
python scripts/start.py doctor --out-dir local-data/first-environment
```

阅读 `环境检查.md`。缺少 PDF、矩阵或专用导出组件时，先完成上面的离线示例，再按[独立安装](standalone-install.md)为实际任务安装所需组件。HTML/JSON不依赖财务Excel专用组件。本命令不安装、不联网。

## 换成真实研究

按基金代码自动比较、持仓CSV快照及已有组合历史报告，见[日常简明入口](practical-entry.md)。不需要先寻找多个脚本；已有资料比较与需要联网取数分别明确。

**没有本地目录，也可以直接用公司名称查询公告：**

```bash
python scripts/start.py ask --question "分析招商银行最近三个月有什么重要公告变化" --as-of 2026-10-08 --online --out-dir local-data/cmb-notices
```

将名称换成目标公司，截止日换成实际研究日期。当前 ask 仅接通单家A股、近一或三个月公告；“招商银行”在此入口指A股，不替代港股研究。`--online` 会把问题中识别的公司名称或代码发送给第三方证券检索及公告接口，主动取数且不后台刷新。不加该选项时只使用本地目录/缓存；缺少目录会说明如何启用查询，不要求使用作者数据。

输出 `研究结果.html`、Markdown、结构化结果以及研究档案。报告先概括公告类别、给出阅读重点，再列事件和来源链接；类别数量不是重要性或盈利影响。`partial` 表示取得了公告线索，尚未完成正文核验与完整公司评价，不能视为完整研究成功。来源链接可能为第三方公告展示页，不是官方附件认证。

已有两只基金净值输入：`python scripts/start.py compare --input comparison-input.json --out-dir local-data/my-comparison`。

已有消息与持仓输入：`python scripts/start.py news --input news-input.json --out-dir local-data/my-news`。

输入结构分别参考 [比较教学输入](examples/comparison-example.json) 和 [消息教学输入](examples/news-example.json)。对话使用时直接告诉 AI 研究对象、期间和问题，由 AI 准备参数，普通用户不用填写 JSON。没有真实资料时不能把演示输入改名后当作真实结果。

此快速入口目前统一离线演示、环境检查、已有资料比较、消息关联及单公司公告问答；其他六类场景继续按 [功能说明](current-capabilities.md) 路由。它不声称已经统一全部脚本或具备全市场名称目录。联网取数另需数据源可用，官方原文核验另行完成。

## 失败后怎么办

| 看到的问题 | 下一步 |
|---|---|
| 找不到 python 或版本不足 | 安装/切换 Python 3.11+，再试教学示例 |
| 输出目录已存在 | 换一个新目录；程序不会覆盖旧报告 |
| 找不到输入文件 | 检查实际文件路径，或先用 demo 无输入试跑 |
| 输入格式、日期或净值错误 | 阅读输出的 `下一步.md`，按对应教学输入核对；不填零凑数 |
| 缺少可选组件 | 用 doctor 查看，再按独立安装说明按需配置 |
| 联网入口失败 | 保留来源与失败原因；按[源体检](source-health.md)检查本次来源，或提供已有资料。演示成功不代表联网可用 |

失败输出的 `start-result.json` 保留状态、原因和下一步；未能取得资料或需澄清时退出码为2。ask 的 partial 返回0表示线索报告已生成，状态仍明确保留资料缺口，不表示深度研究完成。输出目录占用时仅提示，不写入该目录。诊断是用户主动操作，无后台任务。

## 首次使用验收标准

- 干净目录、无作者缓存且不安装可选包，可以按前三条命令运行。
- 两份报告均包含自然语言判断、关键证据、教学标记和资料限制。
- 文件缺失、输入非法与输出冲突均给出下一步，且不覆盖旧文件、不留下伪成功报告。
- 五分钟指基础环境已就绪后的命令到报告流程目标；不包含安装 Python、下载包和人工阅读耗时，不保证所有设备都在同样时间内完成。
