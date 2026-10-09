# 独立安装与验收

安装完整research-workbench目录，保留scripts与modules的相对位置。内置专题的评价、替换和计算入口复用主包代码，单独抽出专题脚本不能作为独立安装方式。

核心独立采集与记录依赖宿主提供的 Python 标准库和网络；PDF能力按入口分别需要pypdf、pdfplumber或pypdfium2；缺少组件仅影响依赖它的入口。用户数据输出到自己指定的目录，不依赖本机姓名、旧项目路径或现有数据库。

研究 Skill：`scripts/research_pipeline.py --workspace <用户数据目录> --out <新文件> collect --kind fund|stock|etf --codes 六位代码 --as-of YYYY-MM-DD --refresh`。空目录自动启用独立采集。基金提供净值历史；股票/ETF及明确沪深市场的债券可取指定区间未复权历史，股票可取财务摘要和公告元数据；覆盖及失败状态见[独立采集](standalone-collection.md)，不保证全历史或原文已核验。没有 --refresh 时只读该用户目录缓存。失败保留成功缓存、抓取时间并附本次错误。

计算与记录：compare / evidence / validate / portfolio / review 参数见 six-workflows.md；使用 `scripts/research_tasks.py --store <用户任务目录> create|due|review|show`。以新文件冻结依据，比较与压力假设由使用者提供；程序检查不等于研究有效性。

北交所：`scripts/research_topics.py bjx standalone -- --out <新文件> fetch` 获取第三方发行数据，不触发模型优化；`scripts/research_topics.py bjx standalone -- --out <新文件> threshold --price 发行价 --rate-pct 配售率百分数 --max-shares 申购上限` 使用 Decimal 向上取整申购手数。最终配售率未知时需给定有依据的情景；不保证获配。

ETF：`scripts/research_topics.py etf standalone -- --data-dir <用户目录> --out <新文件> --codes 510300 --refresh`。数据为第三方报价，不能作为完整择优排名或配置引擎。

宏观：`scripts/research_topics.py macro standalone -- --data-dir <用户目录>` 初始化37项定义，所有观测为空；增加 --refresh 尝试官方公告采集。缺项留空，不复用安装者历史，不输出已验证的四周期阶段。

完整HTML工作台、旧refresh/build入口属于项目模式，需要齐全的同级模块与资产；本轮不将它们标为独立安装通过。工作台审计的 --workspace 明确指向待检查项目，不能用来证明陌生用户已有项目。

本轮验收记录：standalone-acceptance.json。真实数据获取与测试夹具分列；夹具不入用户数据库。没有定时抓取、交易执行或账户连接。


## 新增独立入口
统一检索、批量采集、原文逐项核验、FOF解析与递归、MVP/有效前沿/路径模拟见[current-capabilities.md](current-capabilities.md)。优化与扩展还需要numpy；独立包不附带本项目真实验收用PDF和市场库。工作台属于可选项目界面，独立安装不保证附带该界面。


交付包包含SKILL.md、README.md、scripts、references与agents配置，不包含作者研究任务、账户资料、输出缓存或PDF库。安装到既有目录不会要求删除用户自有研究记录。发布检查可执行 `python scripts/package_audit.py PACKAGE.zip --source SKILL_DIRECTORY --out NEW.json`；此检查仅证明文件一致和交付范围，不代表功能或数据覆盖验收。


## 安装后环境检查

运行 `python scripts/environment_check.py --out NEW.json`，得到环境依赖清单和自然语言说明。缺少pdfplumber仅影响PDF原文/表格提取，缺少numpy影响矩阵与模拟模型，缺少Node影响JavaScript计算入口。目录检索、基金净值/条件筛选和跨市场价格日线使用标准库。检查不会安装组件或联网；依赖可找到不代表真实数据或业务核验通过。

Excel相关组件单独检查：xlrd用于申万股票行业历史XLS原表，openpyxl用于新版行业代码XLSX原表解析，以及明确使用该库的其他导出入口；它不能替代财务底稿的专用导出组件。缺失时不影响标准库取数，但下载后的Excel解析无法完成；环境检查仅报告状态，不自动安装。


独立包最小离线示例见README.md。按需依赖和本地验收版本记录位于references/requirements-optional.txt与references/constraints-tested.txt；教学输入位于references/examples/，不是真实投资数据。维护时使用 `python scripts/build_package.py --source SKILL_DIRECTORY --out NEW_PACKAGE.zip` 生成并核对允许交付文件，旧包不覆盖，不打包运行库。

运行环境：Python 3.11+；JavaScript 功能使用 Node.js 20+。DOCX 需要 python-docx，PDF 读取按具体入口需要 pypdf/pdfplumber/pypdfium2，部分专题需要 pandas。内置自动OCR不提供。环境检查只列依赖状态，不替代实际运算与视觉验收。PPT 导出必须指定 fontFamily，并在目标环境核验该字体和分页；不得默认认为 Windows 字体存在。

## 导出依赖按入口确认

|用途|依赖|缺少时|
|---|---|---|
|HTML、Markdown研究正文|Python及相应计算入口依赖|不需要Office导出组件|
|财务Excel底稿|Node.js 20+、可定位的@oai/artifact-tool|保留已生成正文与结构化结果，明确Excel未生成|
|明确使用openpyxl的其他Excel入口|openpyxl|仅该入口不可用，不说明财务底稿可用|
|公司行业Word|python-docx|正文结果保留，Word未生成|
|PPT|Node、相应专用组件、显式字体参数|依赖和字体确认后仍需逐页检查|

专用组件可通过导出参数或ARTIFACT_NODE_MODULES定位；具体参数见[导出说明](archives-reports.md)。组件不随Skill打包，可定位不等于获得分发或商业授权，许可见[第三方说明](third-party-notices.md)。


## 专题测试资源

主包离线回归与项目集成验收范围不同。北交专题部分测试需要已有真实数据及可选工作台页面，这些不随独立包分发。显式设置`BJX_VALIDATION_DATA_DIR`到本地完整验收资源目录后运行专题测试；目录应包含data.json、calendar-verified-fields.json、bse-trading-calendar-2026.json及bjx-panel.html。测试使用当前包内计算代码与已提供素材，不下载、不制造数据、不自动跳过缺失项。无资源时对应集成测试明确报错，不代表独立研究计算不可运行。页面结构检查不是浏览器视觉验收，历史数据回放不是最新行情采集。


组件定位失败与组件未安装分开排查：先确认调用环境是否已提供专用组件目录，再通过 `--artifact-node-modules` 或 `ARTIFACT_NODE_MODULES` 显式传入。只验证可定位和真实导出，不搜索或复制第三方运行库进交付包；当前机器可导出不代表其他安装环境自动具备组件。

存货原文核验：`inventory_reconciliation.py` 的文字路径需pypdf，单元格坐标另需pdfplumber。相对PDF路径以输入JSON所在目录解析；结果目录可自动创建，既有结果不覆盖，核验失败不写成功结果。依赖缺失只影响该入口。


报告证据中的PDF物理页引句验收（`pdfLocator`）需要pypdf。缺少组件、PDF损坏或指定页无法提取文字时，结论绑定返回明确失败，不静默取消原页检查；不提供该项定位的旧记录仍按原规则检查，不能宣称已完成原页引句验收。扫描件和特殊版式另行人工复核。

基金报表与穿透依赖：fund_balance_snapshot.py与fof_reports.py同时使用pdfplumber、pypdf；fund_balance_gross_bridge.py、disclosed_rate_scenario.py需pypdf核对原件结构或页文。毛额和父子剔重计算复用这些已核输入，不因缺少PDF组件静默跳过来源检查。安装组件只解决运行依赖，仍须核对报告版式与字段口径。


工作台登记检查仅用于已有项目：`python scripts/audit_workbench.py --workspace PROJECT --run-checks`。Node默认从PATH定位，也可由调用者以`--node NODE_PATH`指定；支持.js、.cjs和.mjs。缺Node时保留失败原因，不使用Python执行JavaScript。此入口检查缓存与登记脚本，不替代独立安装、原文、内容或视觉验收。

## 运行版本验证范围

当前Windows环境已实际运行Python3.12主包检查；另以Python3.14.7、禁用第三方site-packages运行环境检查、教学消息研究、教学基金比较及留存真实组合历史报告，四入口成功，组合收益、最大回撤、收益贡献与期末距高点结果和原运行时一致。461份Python源码通过3.11语法模式检查，本机没有3.11运行时，语法检查本身不证明运行；后续GitHub独立环境已实际运行3.11，范围见下节。可选PDF、Excel、字体、网络来源及其他平台另按实际环境核验。

## GitHub独立矩阵实际结果

2026-10-08，[独立运行37785852969](https://github.com/KILING-TASI/research-workbench/actions/runs/37785852969)在Ubuntu/Windows和Python3.11/3.12四组均成功，每组实际2053项主包测试通过，另有三个禁用site-packages的教学入口成功。声明依赖按已测试约束安装；不携带专有导出组件或作者数据。首次Windows运行的3项路径断言失败已保留，修正短路径/规范路径比较后复验通过。

该结果对应提交658395355b2b46c1f683f086ce38b691af00c61c。流程仅拉取请求及手动事件触发，无定时设置；后续代码变化须重新运行，不能沿用此状态。上述检查不代表联网数据稳定、全部专题资源、视觉或经济判断全部通过。


## 待审去重路径的专业依赖

基础比较demo仍标准库可运行。六列持仓、schema1原页字段、观察出入金的计算已迁入专业仓：cn-fund-lookthrough、cn-financial-reconcile、portfolio-decision-engine。安装支持当前兼容入口的专业包，或给可信源码目录设置RESEARCH_WORKBENCH_LOOKTHROUGH_DIR、RESEARCH_WORKBENCH_FINANCIAL_DIR、RESEARCH_WORKBENCH_PORTFOLIO_DIR。不是后台安装；旧v0.1.0发布包不包含新增兼容接口时会报明确不可用。报告和综合判断仍在主包；schema2/九列QDII/定投等未迁移路径见归属说明，不视为全部独立化。
