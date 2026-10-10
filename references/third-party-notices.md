# 第三方代码、依赖与资料许可说明

本说明区分工具代码、外部运行依赖与研究数据。项目有权授权的原创代码与说明采用根目录 [MIT 许可证](../LICENSE)，版权署名保留 research-workbench contributors，并注明 KILING-TASI。已有第三方代码及其改编部分仍保留适用的上游许可、版权与修改标识，不以根许可证替换。MIT 不覆盖外部数据、原文、商标或专有运行组件，也不代表第三方为本产品背书。

## 已注明来源的改编代码

ETF轮动包的 scripts/tdx_parser.py 注明改编自 simonlin1212/a-stock-data，并参考 jing2uo/tdx2db 的行情二进制布局。原始改编版本号未记录，本次核对的是当前上游许可证；不能把当前版本号当作最初使用版本。

- a-stock-data：Apache-2.0，Copyright 2026 Simon Lin。许可证保留在ETF包 scripts/a-stock-data-LICENSE.txt。上游：https://github.com/simonlin1212/a-stock-data/blob/main/LICENSE
- tdx2db：MIT，Copyright (c) 2025 Komh。许可证保留在ETF包 scripts/tdx2db-LICENSE.txt。上游：https://github.com/jing2uo/tdx2db/blob/main/LICENSE
- 本工具已修改校验、异常包处理和市场覆盖检查。保留原版权、许可及修改标识；不能将第三方片段宣称为全部原创。当前上游目录检查未发现单独NOTICE文件。

## 外部运行依赖

当前脚本可能使用pdfplumber（MIT）、python-docx（MIT）、pypdf（BSD-3-Clause）、openpyxl（MIT）、xlrd（BSD式多作者声明）、numpy和pandas（BSD-3-Clause）。pypdfium2包含BSD-3-Clause、Apache-2.0及PDFium依赖声明。此列表是直接依赖说明，非完整递归软件物料清单。

独立包不携带上述运行库或二进制。安装对应版本时保留其随包许可证；若另行捆绑Python、Node、PDFium、字体或运行库，必须检查该实际发行版本的全部依赖和版权声明。不要用主库许可证替代其附带的二进制依赖许可。

## Excel与PPT导出组件

当前Excel/PPT脚本调用外部 @oai/artifact-tool，不在独立包中。已检查本地2.8.59版本：许可证限定内部评估和测试，并限制未经书面许可的分发、生产和商业用途。因此不能将当前导出链路承诺为无条件商业可用。持有其他适用授权时应保存证据并按其条款核对；否则商业交付需改用获准的导出方案。HTML和Markdown生成逻辑不依赖该组件。

## 数据与原文的权限

代码的Apache/MIT/BSD许可不授予行情、研报、公告、商标或网页的使用和再分发权。访问成功、下载成功、付费订阅和标明出处均不自动等于可商业再分发。

东方财富公开法律声明对内容复制、传播和行情再分发设有限制，商业展示及数据分发需核对适用授权：https://about.eastmoney.com/home/disclaimer

腾讯、通达信、新浪、Yahoo、交易所、中证/申万、基金公司和巨潮等来源，未取得可覆盖本工具商业再分发的授权证据；按具体来源、内容和用途另核。巨潮公开公告中的发行人内容也不能一概视为无版权素材。

FRED按系列来源、版权注记及用途核查，不能将其全部系列视为统一无条件开放数据：https://fred.stlouisfed.org/legal/

研报全文、翻译、图表、PDF副本与机构品牌不随工具代码许可开放。向外分享研究包前，分别核对正文引用、原文附件和数据表的分发权。缺少授权证据时仅登记为未确认，不标为已获许可。

## 发行检查

保留本说明与ETF包的两份上游许可证。分发工具代码时不附带作者账户资料、市场缓存、研报原文或专有运行组件。当前来源扫描和声明检查不能证明所有代码均为原创，也不是律师出具的知识产权意见。

## Ledoit–Wolf常相关收缩适配
脚本scripts/covariance_shrinkage.py参考并适配作者公开covCor方法：https://github.com/oledoit/covShrinkage/blob/main/covCor.m 。原版权(c)2014–2021 Olivier Ledoit and Michael Wolf，BSD-2-Clause。完整原版权、条件和免责保留在该脚本头部；此部分不改为主包MIT。数值测试为项目自有。2026-10-09核对公开源文件；方法接入不表示市场效果已认证。
