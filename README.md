# 投研研究助手

研究公司、比较基金和 ETF、检查持仓组合，把关键判断和数据来源一起留下来。

[![原创代码 MIT](https://img.shields.io/badge/%E5%8E%9F%E5%88%9B%E4%BB%A3%E7%A0%81-MIT-green)](LICENSE)
[![运行检查](https://github.com/KILING-TASI/research-workbench/actions/workflows/validate.yml/badge.svg?branch=main)](https://github.com/KILING-TASI/research-workbench/actions/workflows/validate.yml)

## 安装和首次试用

本轮对应[发布页](https://github.com/KILING-TASI/research-workbench/releases/tag/v0.1.0-beta.8)；下载时以实际上传的完整源码、wheel、sdist 与校验清单为准。源码按下面步骤安装；下载 wheel 后，将安装命令末尾的 `.` 换成该 wheel 文件路径。pip 安装不会自动注册 AI 工具中的 Skill。

本轮源码版本为 `0.1.0-beta.8`。安装入口需要 Python 3.11 或以上。在完整源码目录新建自己的 Python 环境，下面的 Windows 命令不需要激活脚本：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install .
.\.venv\Scripts\research-workbench.exe --help
.\.venv\Scripts\research-workbench.exe demo --out-dir reports/demo --auto-name
```

工具名与仓库名相同；在已激活的环境中可以直接输入工具名。Linux/macOS 使用 `.venv/bin/python` 和 `.venv/bin/research-workbench`。教学结果写入当前工作目录；`--auto-name` 自动另选新名字，旧结果保留。不加该参数时，教学入口拒绝已有目录。`research-workbench run --help` 查看原生参数，原来的命令继续兼容。其他专题可用 `research-workbench script --help` 查看入口，以脚本名调用，不需要记住源码路径。pip 安装提供 CLI；作为 Skill 使用仍须保留完整源码及许可资源，不能只复制 SKILL.md。安装可能需要联网获取普通构建依赖；教学离线。下面保留原生入口及此前发行记录，本轮安装和版本以本节为准。

## 先试一次

需要 **Python 3.11 或更高版本**。下面的教学例子不联网，不需要账户、PDF 组件或其他专业工具。

下载或克隆仓库后，在仓库根目录打开 PowerShell：

```powershell
python scripts/start.py demo --out-dir local-data/first-comparison
Invoke-Item ".\local-data\first-comparison\打开这里.html"
```

会生成 HTML、Markdown、计算结果和输入记录。先打开 `打开这里.html`，再看基金比较说明。如果输出目录已经存在，把 `first-comparison` 换成 `first-comparison-2`；程序不会覆盖旧报告。

更多用法见[快速开始](references/quickstart.md)。真实资料需要另行提供或按请求获取，教学输入不能改个名字就当成真实基金。

## 结果是什么样

教学例子会先说明：**在这段区间里，A 上涨 10%，B 下跌 10%；A 的区间表现更好，但不能据此判断长期能力。** 随后列出依据、计算口径和还缺哪些资料。

这里只有两个日期，年化波动等长期指标不输出，也不评价经理能力。你可以下载[教学报告](references/examples/readme-preview.html)后在本地打开，或查看[对应输入](references/examples/readme-preview-input.json)和[生成记录](references/examples/readme-preview-manifest.json)。这份预览保留原有版本，尚未完成浏览器视觉验收。

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

**暂不支持：**任意标的全量资料的一键获取、实时行情保证、默认后台监控、交易执行或收益承诺。REITs 完整估值尚未完成；机构预测档案可以离线留存观察，但不是完整一致预期数据库。其他缺口见[详细交付说明](references/development-validation.md)。

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

beta.7 对应的专业版本是 `cn-fund-lookthrough 0.2.0`、`cn-financial-reconcile 0.2.0` 和 `portfolio-decision-engine 0.8.0`，这三版均已上线。从各仓库的 GitHub Release 页面取得对应 wheel 或源码，再装入当前 Python 环境；不假设这些包已经上传 PyPI，也不把旧版默默当成兼容替代。

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

## 当前源码与下载包

当前软件版本是 **`0.1.0-beta.7`**，已于 **2026-10-10** 发布。Skill 元数据和安装包使用这个版本号；说明版本、接口及计算方法各自保留原编号。发布内容见[beta.7 发布说明](references/release-notes-beta7.md)。

可以克隆默认 `main` 源码，也可以从 [v0.1.0-beta.7 Release](https://github.com/KILING-TASI/research-workbench/releases/tag/v0.1.0-beta.7) 下载 [安装 ZIP](https://github.com/KILING-TASI/research-workbench/releases/download/v0.1.0-beta.7/research-workbench-v0.1.0-beta.7.zip)及[SHA256 校验清单](https://github.com/KILING-TASI/research-workbench/releases/download/v0.1.0-beta.7/SHA256SUMS.txt)。旧 [beta.6](https://github.com/KILING-TASI/research-workbench/releases/tag/v0.1.0-beta.6) 保留，不替换历史资产。

下载旧压缩包或使用旧安装，不会自动得到这些新增内容。专业工具也要使用支持对应接口的版本，不能默认用旧包替代。[功能归属与依赖](references/engine-ownership-and-migration.md)列出已经转交的计算和仍留在主包的部分。

解压安装包得到完整的 `research-workbench` 目录；命令行试用可在该目录运行，安装 Skill 则按所用 AI 工具的规则放入 Skill 目录。不要覆盖自己保存的研究资料，安装步骤见[安装说明](references/standalone-install.md)。旧 beta.7 只交付 Skill 源码 ZIP；本轮新增 pyproject 与 wheel/sdist，完整 Skill 源码仍单独提供。资产保留构建时的说明，发布状态以本页和 Release 页为准；更新本页不重打旧标签或安装包。

## 验证、许可与使用边界

离线教学、隔离安装和部分研究场景已做实际运行检查，具体范围见[验证说明](references/validation-scope.md)、[当前案例范围](references/acceptance-current.md)。这些检查不代表任意真实标的都能分析，也没有证明 AI 工具已经识别安装，或报告排版已通过视觉检查。

有权授权的原创代码和说明采用 [MIT](LICENSE)。第三方代码、公告、研报、行情数据和品牌的权利分别处理，详见[第三方与数据说明](THIRD_PARTY_NOTICES.md)及[来源许可核查](references/third-party-notices.md)。

本项目用于学习和研究，不构成投资建议，不执行交易，也不保证收益。请结合本次来源、假设和缺口独立判断；[完整免责声明](DISCLAIMER.md)保留具体使用边界。
