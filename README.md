# 投研研究助手

说明版本：1.92 · 更新日期：2026-10-09。现行说明与历史文档的用途见[文档索引](references/documentation-status.md)。

持仓穿透与财报字段核对提供两个可独立使用的研究预览工具：[cn-fund-lookthrough](https://github.com/KILING-TASI/cn-fund-lookthrough)、[cn-financial-reconcile](https://github.com/KILING-TASI/cn-financial-reconcile)。它们各自开发测试，主Skill仅按需衔接，不强制安装或自动下载，详见[接口与范围](references/independent-engines.md)。

面向个人与买方研究的多资产投研助手，提供可追溯的资料、分析与研究报告。

将本目录复制到AI工具支持的Skill目录，读取SKILL.md。工作台可选，不需要作者项目路径或数据库。

## 第一次使用

先读[五分钟快速开始](references/quickstart.md)：Python 3.11+ 即可离线生成一份有结论、有论据的教学报告，无须配置账户或安装可选组件。

```bash
python scripts/start.py demo --out-dir local-data/first-comparison
```

打开输出目录中的 `基金比较说明.html`。这是教学示例，不能当作真实基金评价。失败时入口说明原因与下一步，不覆盖旧文件。

真实公司公告可直接按名称查询：`python scripts/start.py ask --question "分析招商银行最近三个月有什么重要公告变化" --as-of 2026-10-08 --online --out-dir local-data/cmb-notices`。换成你的公司名称与实际截止日；此入口仅支持单家A股公告，主动联网，报告区分目录线索与原文核验。

试用看[快速开始](references/quickstart.md)；了解能做什么看[功能说明](references/current-capabilities.md)；修改代码时看[方法与参数索引](references/capability-reference-index.md)。

基金代码或完整名称比较、持仓CSV整理、组合历史及报告找回可通过[日常简明入口](references/practical-entry.md)调用。常用研究支持沿用保存请求、补失败资料并另存新结果；仅有持仓金额时先给结构快照，不冒充完整风险诊断。报告首页先给判断，再展开论据。

## 主要功能

功能合并为六类研究场景：标的查询与候选筛选、基金与ETF产品研究、持仓与组合研究、公司与行业研究、宏观与跨资产观察、北交所新股研究。公告与研报阅读、原文核验、证据、笔记和导出作为共用能力，贯穿研究过程。深度报告与一页纸属于交付形式；代码目录与专用脚本不另列为用户功能模块。具体交付与前提见[功能说明](references/current-capabilities.md)，基金细节见[基金说明](references/fund-user-guide.md)。

已有成功与失败样本、工程检查范围及未完成的验证见[验证范围与样本](references/validation-scope.md)。历史验收不代表当前所有数据源都可用。

研究解释覆盖[申万31个一级行业框架（SW2021）](references/sw-level1-research.md)，并按细分业务检查增长驱动、现金兑现、竞争优势、证据冲突和假设反证；估值及组合情景依赖已取得资料与明确参数。框架覆盖不代表行业数据全覆盖，也不新增自动预测或全市场数据库。

可以直接问：“这家公司利润增长有没有现金支持？”“我的基金是否重复押注同一行业？”“这份研报的核心假设有哪些反证？”AI复用已有入口取得资料并给出自然语言分析；不能确认的事项明确列示。

## 最小离线调用

在本目录运行：

```bash
python scripts/environment_check.py --out local-data/environment.json
python scripts/retail_research.py references/examples/news-example.json --out-dir local-data/news-example
```

示例是教学消息与教学金额，不是真实持仓或公告。输出目录须为新目录。结果只展示直接关联暴露，不是预计损失或买卖建议。环境检查不联网、不安装依赖。

## 依赖按需启用

基础取数与目录使用Python标准库，联网入口另需来源可访问。PDF表格与持仓提取需要pdfplumber；FOF关联、基金资产负债表及来源结构检查同时需要pypdf。可按需安装：

```bash
python -m pip install pdfplumber pypdf
```

其他可选组件及本地验收版本见references/requirements-optional.txt和references/constraints-tested.txt；版本记录不是全部功能通过证明，不要求一次安装所有组件。矩阵计算需numpy，部分Excel需xlrd/openpyxl，JavaScript入口需Node.js。

完整步骤见references/standalone-install.md。数据、原文、计算与假设分别说明，缺失不补造，不提供收益保证或自动后台更新。第三方及数据权限见references/third-party-notices.md；本项目有权授权的原创代码与说明采用 [MIT 许可证](LICENSE)。第三方代码保留原许可；本许可不授予行情、研报、公告、品牌或外部组件的使用及再分发权。MIT 允许原创部分商用，不代表全部数据与导出链路均获商业授权。

## 同区间比较说明

已有净值资料可调用：

```bash
python scripts/fund_comparison_brief.py comparison-input.json --out-dir local-data/comparison
```

输入沿用research_pipeline.py compare格式：asOf、start、rows；每个标的提供code、可选name、comparisonGroup、basis、frequency及history。输出JSON计算结果、Markdown和HTML自然语言说明。比较组是研究者声明，不代表已核验同类；缺基准不输出超额收益，分红记录完整性未核验时明确保留缺口。

基金净值及行情缓存缺少内容摘要或摘要不一致时需重新取数，保留旧文件。升级采集方法后，旧批量断点须另建jobId，不直接复用旧成功状态。

比较报告附input.json快照及report-manifest.json。可运行：`python scripts/verify_collection_report.py local-data/comparison/report-manifest.json --input local-data/comparison/input.json`。检查保存内容与方法版本，不代表来源真实性、数值正确性或视觉验收。

最小离线比较示例：`python scripts/fund_comparison_brief.py references/examples/comparison-example.json --out-dir local-data/comparison-example`。输入是两组教学净值，非真实基金；仅2个日期，因此年化波动不输出。

财务Excel底稿的现有JavaScript导出器另需可定位的@oai/artifact-tool，Node或openpyxl存在不等于该导出器可运行。环境检查单列结果；组件缺失时保留HTML/JSON。该组件的许可与部署条件见第三方许可说明，本工具不自动安装或授予使用权限。

## 执行环境与数据位置

使用 Python 3.11+，JavaScript入口使用 Node.js 20+。用户研究记录必须通过 --store 存入独立目录，不写入Skill安装目录。内置专题调用、输入前置条件及错误输出见 references/integrated-topics.md 和 references/execution-contract.md。PPT须指定 fontFamily 并在目标环境验证字体及排版，组件可定位不代表报告已验收。

## 主动数据源体检

需要检查当前接口、返回结构和样本日期时，使用[数据源体检](references/source-health.md)，区分请求失败、空样本、结构异常、日期超限和观测不足。仅主动调用，不后台轮询。

## 免责声明

本项目仅供学习与研究，不构成投资建议或交易指令，不保证收益或结果准确性。请在使用前阅读[免责声明与使用边界](DISCLAIMER.md)，并结合本次数据来源、假设与缺口独立判断。代码许可不包含第三方数据使用授权。
