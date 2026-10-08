# 宏观网页标注时间核对

用于事前复盘避免晚出解读混入已知信息。调用：`python scripts/release_clock_review.py INPUT.json --out NEW.json`，输入输出路径相对当前调用位置，来源相对路径按输入JSON目录解析；新输出须不存在。仅读取已归档HTML，不下载、轮询或执行网页脚本。

输入clockBasis固定same-site-marked-local-time，siteLocalCutoff采用YYYY/MM/DD HH:MM；sources数组每项含id、siteId、path、sha256，可附dataPeriod。所有siteId须相同，调用者须确认同站点时间体系；不自动推断时区或转换国际事件窗口。

核对唯一PubDate元数据与正文可见时间相同，哈希改变、日期缺失或歧义、不同站点时区未知时拒绝。输出rows分别记录标注时间及状态：marked-after-cutoff-exclude为晚于时点应排除；marked-not-after-cutoff-historical-availability-unproven仅说明标注不晚于时点，历史可获得性仍未证明。

网页标注可能因更新改变；本入口不认证第一次公开、盘中送达、历史未修订或市场实际接收时间。数据所属月与公布日分开；事后解释可以使用后来资料，事前研究不能提前纳入。日度行情同期变化不当作宏观数据的独立因果贡献。

站点标注日期须严格`YYYY/MM/DD HH:MM`，PubDate重复属性拒绝。时间在正文提取文本出现不证明实际视觉显示；siteId仅输入声明，不证明来源站点身份或时区。早于截止的标注不认证首次公开及历史可得。其他格式或正文仅显示日期的站点，本入口不能确认精确时点，不自动舍弃秒或补时刻。

日期级核对显式选`clockBasis: same-site-marked-local-date`，提供`siteLocalCutoffDate`（YYYY-MM-DD）及`metadataFormat`（支持YYYY-MM-DD含秒、YYYY/MM/DD分钟或纯日期的对应strptime格式）。正文必须有“发布时间/发布日期”标签及匹配日期；同日返回时刻未知，不按元数据时刻排序。不自动从原精确模式降级，也不将日期核对称为首次公开认证。
