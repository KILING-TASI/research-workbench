---
name: bjx-newshare-toolkit
description: 核验北交所新股发行公告和招股书，测算整手获配、边际资金档位与现金占用，研究发行定价，保存证据快照和首次预测偏差；不保证获配，不执行申购。
---

# 北交所新股研究助手

AI 根据用户问题选择任务、准备输入文件、执行脚本并解释结果。用户直接输入代码或问题；预算、研究区间等关键参数缺失时询问，不要求用户填写 JSON。除教学示例外，不把示例参数当成用户输入。

## 用户沟通

支持直接在聊天中查询和分析，工作台仅为可选展示界面；不得要求用户先打开页面或选择技术模块。面向用户的功能说明见 [使用说明](references/user-guide.md)。

最终回答、功能介绍和界面文案只包含功能、输入要求、结果、数据来源与必要限制。不得展示内部决策、开发进度、验收计数、待办台账、调用路由、脚本命令、JSON准备过程或AI执行过程。技术调用规范用于内部执行，不能照搬为用户说明；用户明确要求技术细节时再提供相关内容。将限制转换为实际影响，如“部分字段待核验”“历史日期缺少依据”，不要报告内部阻塞状态。保留来源时间、假设、证据冲突与风险，不把隐藏执行过程当作隐藏信息缺口。

## 执行准备

评价招股书经营与财务时，按需读取主包[会计与审计依据](../../references/accounting-audit-basis.md)。分别核对年度审计、期后审阅及预测期间，客户集团称谓按原文释义保留。发行PE使用的历史利润不能自动代表最新正常化盈利；资金档位复算不代替公司价值评价。

以下命令均以 research-workbench 主包根目录为工作目录；`python` 为可用的 Python 3 解释器。其他目录调用时将脚本及输入路径展开为绝对路径。JSON 由 AI 写入用户研究目录，输出使用新文件名。依赖与安装方法见 [独立安装](references/standalone-install.md)。

参考链接不会自动加载正文。执行所选任务前，AI 应读取对应参考文件的输入结构；简单任务只读该任务所需内容。主包必须保留本专题的脚本、参考与必要教学素材；完整工作台页面和作者市场数据不随包提供。单独复制 TOPIC.md 无法运行。专题参考中的旧相对脚本路径应按本专题目录展开，不能指向主包同名脚本。

## 任务路由

`INPUT.json` 是该子命令的输入文件，`OUTPUT.json` 是新结果文件，`WORKSPACE` 是用户研究目录。以下均为真实 CLI 模板；不要凭名称推断参数。

| 触发需求 | 调用模板 | 必须按需读取 |
| --- | --- | --- |
| 多模块研究 | `python modules/bjx-newshare-toolkit/scripts/issuance_research.py run INPUT.json --workspace WORKSPACE --out OUTPUT.json` | [完整研究流程](references/integrated-issuance-research.md) |
| 查字段、来源、冲突和缺项 | `python modules/bjx-newshare-toolkit/scripts/issuance_research.py panel INPUT.json --out OUTPUT.json` | [证据接口](references/research-evidence-interface.md) |
| 给定预算与配售率，算整手及边际档位 | `python modules/bjx-newshare-toolkit/scripts/issuance_research.py rates INPUT.json --out OUTPUT.json` | [获配与现金流](references/allocation-cash.md)、[等级输入](references/integrated-issuance-research.md) |
| 多新股现金冻结冲突 | `python modules/bjx-newshare-toolkit/scripts/issuance_research.py cash INPUT.json --out OUTPUT.json` | [完整研究流程](references/integrated-issuance-research.md) |
| 核验并登记公告 / 查询事实库 | `python modules/bjx-newshare-toolkit/scripts/issuance_facts.py register INPUT.json --workspace WORKSPACE --out OUTPUT.json`；查询改为 `view` | [发行事实](references/issuance-facts.md) |
| 财务、招股书与同行研究 | `python modules/bjx-newshare-toolkit/scripts/company_research.py INPUT.json --out OUTPUT.json`；关键词候选另加 `--discover` | [公司研究](references/company-research.md) |
| 股本口径 / 事件日期 / 规则版本 | `python modules/bjx-newshare-toolkit/scripts/issuance_research.py structure INPUT.json --out OUTPUT.json`；子命令可替换为 `timeline` 或 `rules` | [完整研究流程](references/integrated-issuance-research.md) |
| 证据导出 / 冲突 / 快照包 | `python modules/bjx-newshare-toolkit/scripts/research_evidence.py export INPUT.json --workspace WORKSPACE --out OUTPUT.json`；子命令可替换为 `conflicts` 或 `package`；`verify` 的输入为包目录 | [证据与快照](references/research-evidence-interface.md) |
| 首次冻结及复盘 | `python modules/bjx-newshare-toolkit/scripts/prediction_review.py freeze INPUT.json --workspace WORKSPACE --out OUTPUT.json`；可替换为 `replay`、`review`、`compare` | [冻结与复盘](references/prediction-review.md) |

## 最小调用示例

两个示例均随包提供，可离线运行。代码920022只用作格式演示，没有伪造该公司的原文数值。

### 例1：用户问“查920022的发行价、上限和配售率”

AI 先检索现有证据；没有资料时不能编造。以下演示空证据的可运行兜底。

输入 `modules/bjx-newshare-toolkit/assets/example-panel-input.json`：

```json
{"code":"920022","asOf":"2026-10-03","fields":["price","maxShares","ratePct"],"evidence":{"nodes":[]}}
```

调用：

```bash
python modules/bjx-newshare-toolkit/scripts/issuance_research.py panel modules/bjx-newshare-toolkit/assets/example-panel-input.json --out research-output/panel.json
```

结果中 `fields` 每项含 `metric`、`value`、`unit`、`status`、`candidates`，本例三项 `value=null`、`status=missing-unknown`；`quality.missingCount=3`。完整实跑输出见 `modules/bjx-newshare-toolkit/assets/example-panel-output.json`。给用户说明：三项尚无证据，需检索发行及结果公告；不能称这些字段未披露。已有事实库时按证据接口传 `factsStore/code/asOf`，不可用示例空证据替代已取得资料。

### 例2：用户问“假设发行价10元、预算10万元、上限10万股，配售率1%，百股门槛是多少？”

AI 准备 `modules/bjx-newshare-toolkit/assets/example-rates-input.json`。完整文件包含 `allocation`（代码、价格、预算、上限、三档配售率、涨幅假设、申购/退款/结算日期）、`rateEvidence`、`evidence` 和截止日；逐字段见该JSON。三档2%/1%/0.5%仅为教学情景；日期和零涨幅同样是假设。若真实用户只给单一配售率，可让三档采用同一值并明确三档相同，不自行增加预测。

```bash
python modules/bjx-newshare-toolkit/scripts/issuance_research.py rates modules/bjx-newshare-toolkit/assets/example-rates-input.json --out research-output/rates.json
```

本例 P50 的 `rateEvidence.grade=C`，`result.scenarios.P50.wholeLotShares=100`。1%条件下比例百股申购量为10000股、资金100000元；完整实际JSON见 `modules/bjx-newshare-toolkit/assets/example-rates-output.json`。回复先说明条件测算风险，再给预算下整手结果、门槛、上限可达性与日期/费用假设；不称为保证获配或实际公告结果。缺配售率时声明D级，返回阻止测算，不填默认值。

输出文件已存在时换新路径，禁止覆盖研究记录。两个示例不是联网取数或公告核验通过案例。

## 三项研究铁律

1. **证据优先**：关键数值标注原文、第三方、假设、派生或缺失。已逐字段核验的适用原文优先；更正关系、口径冲突仍须核对，不能仅按域名或发布日期自动裁决。
2. **不确定留空**：未知不猜，冲突保留；实际结果不混入事前目标情景。门槛与现金日期都受输入、规则及披露精度约束。
3. **客观分析**：前置相关风险，不给买卖/申购指令、价格预测或收益承诺；财报异常仅描述风险信号。

配售率等级、冻结记录、证据链和精度等执行细则见 [详细边界](references/research-boundaries.md)，涉及对应任务时必须读取。

## 高级与特殊场景

以下按用户需求触发，不作为每次研究的默认步骤。

- 数据或工作台更新：`python modules/bjx-newshare-toolkit/scripts/update_delivery_candidate.py --out-dir NEW_DIRECTORY`。只生成候选，不自动发布；读 [更新与发布](references/workbench-delivery.md)。不触发模型训练或旧模型刷新。
  此路径依赖项目资料；执行前运行 `python modules/bjx-newshare-toolkit/scripts/delivery_preflight.py update`。缺资源时列明缺项，改用独立查询或显式输入测算，不尝试用空缓存替代真实历史。预检只证明资源存在，不证明资料有效。独立安装不承诺此项目路径可用。
- 历史申购现金回放：`python modules/bjx-newshare-toolkit/scripts/generate_cash_plan.py --data assets/data.json --overlays assets/calendar-verified-fields.json --calendar assets/bse-trading-calendar-2026.json --capital 10000000 --start 2026-01-01 --end 2026-10-03 --out-dir NEW_DIRECTORY`。与 `cash` 区别：从历史发行缓存生成计划，实际配售率/首日涨幅为事后输入；用户本金及区间由AI确认。读 [逐笔现金账](references/cash-repo-ledger.md)。
- 已知申购及通用回购逐笔结算：`python modules/bjx-newshare-toolkit/scripts/cash_repo_ledger.py INPUT.json --out OUTPUT.json`。显式日期、逐笔本金利率费用，真实账户结算验证不属于交付范围，日期仍须注明输入或假设依据；与 `cash` 的纯新股情景分开。读 [逐笔现金账](references/cash-repo-ledger.md)。
- 更正公告：取得两版原文后运行 `python modules/bjx-newshare-toolkit/scripts/compare_original_versions.py --before OLD.pdf --after NEW.pdf --name NAME --document-code CODE --out OUTPUT.json`。标题线索与正文比较分开；读 [交付说明](references/workbench-delivery.md)。
- 第三方数值与已登记原文冲突：取得适用原文后，用 `python modules/bjx-newshare-toolkit/scripts/reconcile_original_values.py --data SNAPSHOT.json --overlays REGISTERED_FIELDS.json --pdf-dir ORIGINALS --out-dir NEW_DIRECTORY` 显式生成新结果。逐项重核页码、哈希及数值后才采用原文，第三方值及差异另存；不能仅因差异很小或怀疑是四舍五入而解除冲突。读 [原文差异处理](references/original-reconciliation.md)。
- 扫描件：按 [交付说明](references/workbench-delivery.md) 的PDF清单传入外部OCR旁文件。AI准备哈希绑定输入，识别结果仍需页图复核；内置自动OCR不属于交付范围。

## 错误处理

- 网络超时、403/429或PDF下载失败：停止受限访问，保留旧缓存及时间，报告失败标的和原因；可接收用户原文。不能将旧缓存描述成刚刷新。
- 缺依赖：说明具体依赖和受影响步骤；保留已有结果，不编造输出。
- 字段缺失、同名表格歧义、代码不符或哈希变化：保留缺失/冲突状态，停止依赖该字段的计算；列出待补证据。空面板不证明公告没披露。
- 输出已存在、参数非法或程序错误：保留原记录，修正输入后使用新输出路径；错误日志不算研究结果。先检查命令成功及结果文件，再总结。
- 扫描或无法提取的PDF：不报原文核验通过；转人工页图/OCR候选复核，明确尚未完成步骤。

## 输出格式

默认用自然语言或简表，不把JSON交给用户作为答案：相关风险 → 已核验事实/条件结果（数值、单位、口径、日期、来源及定位）→ 假设与冲突 → 缺失信息及其影响 → 可复查结果文件。未知显示“待核验”，不显示0；只引用实际生成的文件。技术输出保留原JSON、证据哈希和核验状态，不将示例、测试通过或登记通过称为投资结论。

用户查询功能与使用方式时读取 [使用说明](references/user-guide.md)。内部覆盖记录供执行者判断证据范围，不能作为面向用户的进度介绍。

分发、商业部署或分享含原文附件的研究包前，查阅[第三方许可说明](references/third-party-notices.md)。
