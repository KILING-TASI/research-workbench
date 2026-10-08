# 港美元价格的显式汇率换算

`python scripts/currency_price_bridge.py INPUT.json --out NEW.json`

输入 `asOf`、`asset`（cross_market_history的日线结果对象）、`fx`。fx包括baseCurrency（USD/HKD）、targetCurrency（CNY）、unit（CNY-per-USD或CNY-per-HKD）、sourceUrl、publishedThrough、basis、history（逐条date/value）。可由用户提供汇率序列；USD/CNY另可使用下述FRED主动采集，HKD/CNY可由同日两条FRED序列交叉计算。basis应说明真实定盘或假设；假设序列不能宣称真实账户收益。

逐日人民币换算价格=本币收盘价×同日汇率。仅使用日期交集，缺汇率日单列，不前向填充。不同汇率方向或单位拒绝；稀少交集不强行计算。原币价格变化与汇率变化按乘法组合，不简单相加。JSON、Markdown、HTML同时输出。

仅价格研究，未核验分红、拆分、税费、换汇摩擦、报价时刻及交易日历；换算后仍不是总收益，不满足portfolio_models要求的total-return输入。本入口不提供任意标的完整人民币投资收益。当前验收为公式、单位、缺日与错误处理测试，FRED美元人民币采集及真实AAPL日期交集已验收；其他汇率源与实际换汇交易核验未完成。

## 美元人民币主动取数

`python scripts/fred_usdcny.py --start 2026-01-01 --end 2026-09-30 --as-of 2026-10-03 --out-dir NEW_DIRECTORY`

保存FRED DEXCHUS原始CSV、哈希及读取时间，校验序列列名与日期，缺失留空。result.json可作为fx输入；纽约中午买入汇率，单位为人民币/美元，官方说明见 https://fred.stlouisfed.org/series/DEXCHUS 。这是当前版本历史，不是逐日首次披露快照。publishedThrough是研究截止标签，不证明历史发布时间；不把截止日标签当作事前可得性证据。

## 港币人民币交叉汇率

`python scripts/fred_hkdcny.py --usd-cny USD_CNY/result.json --start 2026-01-01 --end 2026-09-30 --as-of 2026-10-03 --out-dir NEW_DIRECTORY`

读取已保存DEXCHUS结果，主动取DEXHKUS（港币/美元），按同日计算人民币/港币=人民币/美元÷港币/美元。原始港币CSV、美元人民币输入及各自哈希保留；缺日不填充。不是银行直接港币人民币报价，不代表证券收盘时刻汇率。官方方向说明：https://fred.stlouisfed.org/series/DEXHKUS 。人民币价格报告保留两条汇率来源，不丢掉交叉计算的另一来源。

换算结果另保留规范JSON输入的SHA256、两路获取时间、汇率原始文件摘要与当前版本标记。港币交叉汇率逐日保留CNY/USD、HKD/USD组成观测，并与最终汇率校验一致；原始下载文件摘要和规范JSON输入摘要用途不同，分别保存。

换算报告另列端点价格变动的代数拆分：本币部分 r_local、汇率部分 r_fx、交互部分 r_local×r_fx，三者相加等于人民币换算价格变动。各部分用百分点表示，并绑定同一实际日期交集；不把这项代数恒等式解释成因果归因、分红总收益或账户净收益。
