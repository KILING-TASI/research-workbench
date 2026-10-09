# 独立工具与主Skill如何配合

主Skill负责理解问题、组织资料、建立判断和交付；独立仓库各自开发、测试和发布，均可不安装主Skill使用。它们是可选工具，不是新的强制安装依赖。

|工具|地址|适用问题|当前边界|
|---|---|---|---|
|中国基金持仓穿透|[cn-fund-lookthrough](https://github.com/KILING-TASI/cn-fund-lookthrough)|联接/FOF嵌套权重、重复公司暴露和未知余额|显式披露输入，非全市场自动PDF采集；不处理毛额杠杆或自动身份映射|
|中国财报字段核对|[cn-financial-reconcile](https://github.com/KILING-TASI/cn-financial-reconcile)|渠道值与原文提取金额、期间范围冲突和本地原页引句|金额字段核对，不是自动提取完整三表，不出审计意见|

两个独立工具采用自己的输入契约，不能把主包fof、公司财务或原文结果JSON直接送入。按对应仓库README与教学示例组织输入，保留来源、单位、日期和未核字段；转换完成再计算，不能以字段同名推定口径相同。

用户已安装可信项目且本次需要它时，可由AI指定路径执行：

```bash
python scripts/independent_engine.py lookthrough --project-dir TRUSTED_PROJECT --input INPUT.json --format html --out NEW.html
python scripts/independent_engine.py financial --project-dir TRUSTED_PROJECT --input INPUT.json --format markdown --out NEW.md
python scripts/independent_engine.py lookthrough --project-dir TRUSTED_PROJECT --input INPUT.json --out-dir NEW_RESULT_DIR
python scripts/independent_engine.py lookthrough --project-dir TRUSTED_PROJECT --continue-from OLD_RESULT_DIR --out-dir NEW_RESULT_DIR
```

没有安装时继续主包已有能力，不要求普通用户选择技术模块。此入口不下载、不自动安装、不读取作者目录；使用子进程隔离模块命名。显式项目目录必须可信，目录检查不证明任意代码安全。输出须新文件；执行失败、超时或没产生报告时不写成功。生成不等于重新核验原文或视觉。

主包既有流程暂不自动替换；要迁移计算，须对照同一输入的口径与结果，避免静默改变权重、舍入和未知处理。各仓库版本分别记录，本地安装和GitHub发布状态不互相推定。原创MIT许可不授予外部行情、研报或公告附件的再分发权。

日常研究优先使用out-dir，保存输入快照、计算结果、中文Markdown/HTML和研究请求，可由research_results.py按持仓或公司名称找回。continue-from沿用旧JSON；旧输入或请求改动时拒绝静默复用，代码换版时提示差异，仍重新计算。项目安装位置由AI复用会话中明确路径，不要求用户反复填写技术参数。外部PDF与依赖组件不随输入留痕冻结，必须另核；没有承诺完整研究资料复用或自动刷新。


开发中的归属、输入/schema/规则版本、尚不等价流程及有限迁移见[契约与迁移](engine-ownership-and-migration.md)。现有JSON桥保留，新增限定PDF适配仅在显式指定可信项目时使用；不按仓库存在就判功能等价。
