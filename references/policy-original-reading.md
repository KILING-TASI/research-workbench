# 政策网页原文与经营传导

用于已取得的政策网页或按用户请求获取的HTTPS政策原文。归入公告与事件研究，不增加工作台菜单。PDF政策继续使用研报原文阅读；网页按正文段落定位，不伪造PDF页码。

## 最小调用

AI检查网页实际结构，指定唯一正文容器class；可选metadataClass定位发布时间。动态渲染、容器重复、编码不符或文字不足时停止，另取可读取原文，不猜正文。

```json
{"asOf":"2026-10-05","sourceUrl":"https://www.ndrc.gov.cn/xwdt/tzgg/202502/t20250209_1396067.html","title":"新能源上网电价市场化改革通知","contentClass":"TRS_Editor","metadataClass":"time","encoding":"utf-8"}
```

```text
python scripts/policy_original_reading.py prepare INPUT.json --out-dir NEW_ARCHIVE
```

可选htmlPath读取已经保存的原始HTML，并保留其声明来源；本地文件不会因为填入官方URL而自动升级为来源身份已验证。单页最多2MB，仅支持声明的utf-8或gb18030编码。不执行网页脚本，不提取正文外的导航；表格、图片明确提示需要另核验。

AI阅读result.json中的paragraphs，组织scope、timing、transmission、risks四栏，每栏条目格式为`{"text":"依据原文写出的解释","basis":"policy-statement或research-explanation","evidence":[{"paragraph":10,"quote":"必须填该段真实引句"}]}`。空栏保留缺口。原文转述与研究解释分开；解释有引句不意味着解释已经证实。

```text
python scripts/policy_original_reading.py build READING.json --out-dir NEW_READING
```

READING包含archive（归档result.json路径）及上述四栏，可选gaps、clocks。输出JSON、自然语言Markdown/HTML、原始HTML副本和经过转义的原文段落查看页。引句链接打开本地段落；段落号只在该文件哈希与解析版本下有效。

## 日期与法律有效性

clocks每项包含date（ISO日期）、kind、text、basis及evidence。kind区分issue-date发文日、publication-date公布日、project-cutoff项目分界日、effective-date原文明示施行时点、implementation-deadline实施期限、expiry-date到期日、other其他时点。日期须在对应引句明确出现；只有年份或“年底”的措辞不能补成虚构的12月31日。施行时点另外需要明确施行措辞，项目分界日不能替代。

网页元数据引句使用`{"locatorType":"metadata","paragraph":1,"quote":"页面上真实的发布时间文字"}`。正文默认locatorType为body。落款日和网页公布日分别记录，不静默取其一。

当前有效性、更正、地方版本及法律含义不自动判定。即使日期与引句匹配，clocks的意义仍是研究者分类。本工具不输出法律或买卖结论。经营传导需另外取得项目纳入范围、电量、合同、价格和公司财务等证据；国家通知不能替代某省实施方案或企业利润测算。

## 共用流程

仍使用report-reading-review模板：contextPath、inputPath、outDir；inputPath指向本入口READING.json。流程根据归档类型选择网页或PDF阅读，记录原始HTML依赖及哈希，将缺口传入统一结果。归档正文或保存段落变化时停止，不能沿用旧引句。

验收范围为实际取得的网页结构和引句，不代表全部政府网站、所有政策版本或全文法律审查。
