# ETF收盘价格与单位净值对照

输入指定证券的已取得历史价格档案和净值原始响应，计算共同日期的收盘价/单位净值−1。此功能不获取盘中IOPV，不将历史收盘偏离称为实时可交易套利收益。

输入示例：
```json
{"code":"512010","priceArchive":"/absolute/history-result.json","navFile":"/absolute/512010.js","start":"2025-01-01","end":"2026-10-05"}
```

价格档案为 market_collect 采集后的封装：results 列表中目标code必须唯一，history每项含date与close，sources保存地址。净值文件为已下载的东方财富pingzhongdata响应。证券身份和数据结构核对不等于交易所分类或原文认证。

调用：
```text
python scripts/etf_closing_premium.py INPUT.json --out-dir NEW_DIRECTORY
```

输出result.json及自然语言HTML，记录实际共同区间、逐日计算、缺净值日期、供应商事件文字、输入文件哈希及来源。重复日期、身份冲突、非法价格拒绝；无共同日期返回missing，不输出偏离数值。

净值所属日不证明当时已发布，输入档案截止日不代替披露时点。没有事件记录不代表分红拆分完整或已核验无事件；不据此宣称含分红总收益。本地哈希只检查文件一致性，不证明数据真实性。费率、持仓、规模和跟踪指数仍需各自资料。
