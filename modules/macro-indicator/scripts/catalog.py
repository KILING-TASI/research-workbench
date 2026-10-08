"""Complete macro pool and reviewable initial sensitivity assumptions."""
GROUPS=['增长', '通胀', '信用', '外部', '政策', '地产财政', '资金情绪']
ROWS=[('gdp', 'GDP增速', 0, '季度', '%', '不变价累计同比（公开源口径，非单季初值/终值）', '常看', 'growth'), ('industrial', '工业增加值', 0, '月', '%', '规模以上工业同比', '常看', 'growth'), ('retail', '社会消费品零售总额', 0, '月', '%', '当月同比', '常看', 'consumption'), ('investment', '固定资产投资', 0, '月', '%', '不含农户累计同比', '常看', 'growth'), ('pmi', '制造业PMI', 0, '月', '点', '官方PMI，50为荣枯线', '必看', 'growth'), ('cpi', 'CPI', 1, '月', '%', '居民消费价格同比', '必看', 'inflation'), ('cpi_food', 'CPI食品', 1, '月', '%', '食品分项同比', '选看', 'inflation'), ('cpi_nonfood', 'CPI非食品', 1, '月', '%', '非食品分项同比，不等同核心CPI', '选看', 'inflation'), ('core_cpi', '核心CPI', 1, '月', '%', '扣除食品与能源同比', '常看', 'inflation'), ('ppi', 'PPI', 1, '月', '%', '工业生产者出厂价格同比', '必看', 'inflation'), ('social_increment', '社融增量', 2, '月', '亿元', '当月新增社会融资规模，亿元，非存量或累计；未经季调，月间比较有季节性', '常看', 'credit'), ('m2', 'M2', 2, '月', '%', '广义货币供应量同比', '必看', 'liquidity'), ('loans', '新增人民币贷款', 2, '月', '亿元', '当月增量，有春节季节性', '常看', 'credit'), ('exports_cny', '出口（人民币）', 3, '月', '%', '人民币计价出口同比，不与美元序列拼接', '常看', 'growth'), ('exports_usd', '出口（美元）', 3, '月', '%', '美元计价出口同比', '常看', 'growth'), ('dxy', '美元指数', 3, '日', '点', 'ICE美元指数；不以广义美元指数冒充', '常看', 'dollar'), ('ust10', '美债10年收益率', 3, '日', '%', '美国国债10年固定期限收益率', '常看', 'rate'), ('oil', '原油价格', 3, '日', '美元/桶', 'WTI现货，非连续期货合约', '选看', 'inflation'), ('gold', '黄金价格', 3, '日', '美元/盎司', '伦敦/纽约基准须标识，不能混接', '选看', 'defense'), ('cny', '人民币中间价', 3, '日', '元/美元', '美元兑人民币中间价，非在岸/离岸成交价', '常看', 'dollar'), ('cnh', '离岸人民币', 3, '日', '元/美元', 'USD/CNH现汇报价，非中间价', '选看', 'dollar'), ('repo', '7天逆回购利率', 4, '日/周', '%', '7天政策操作利率', '常看', 'rate'), ('lpr1', 'LPR一年期', 4, '月', '%', '一年期贷款市场报价利率', '必看', 'rate'), ('lpr5', 'LPR五年期以上', 4, '月', '%', '五年期以上贷款市场报价利率', '必看', 'rate'), ('property_sales_area', '商品房销售面积', 5, '月', '%', '新建商品房销售面积累计同比，非销售金额', '常看', 'growth'), ('property_sales', '商品房销售额', 5, '月', '%', '新建商品房销售额累计同比', '常看', 'growth'), ('land_revenue', '土地出让收入', 5, '月', '%', '国有土地使用权出让收入累计同比', '选看', 'growth'), ('fiscal_income', '财政收入', 5, '月', '%', '一般公共预算收入累计同比', '常看', 'growth'), ('fiscal_expenditure', '财政支出', 5, '月', '%', '一般公共预算支出累计同比', '常看', 'growth'), ('margin', '两融余额', 6, '日', '亿元', '沪深交易所融资融券余额合计', '常看', 'sentiment'), ('new_funds', '新发基金规模', 6, '周/月', '亿元', '新成立公募份额/金额口径须标注', '选看', 'liquidity'), ('etf_flow', 'ETF份额流入', 6, '周/月', '亿元', '每日净份额变动×单位净值，合计后取5交易日均值；v2独立序列', '常看', 'liquidity'), ('equity_bond', '股债性价比', 6, '日', '百分点', '沪深300盈利收益率（1/PE）减人民币10年国债收益率；v2独立序列', '常看', 'attractiveness')]
SECTORS=[('BK1036','半导体','growth'),('BK0475','银行','financial'),('BK0473','证券','financial'),('BK1216','医药生物','defense'),('BK1200','电力设备','growth'),('BK0737','软件开发','growth'),('BK1218','国防军工','defense'),('BK0438','食品饮料','consumption')]
def catalog():
 sources=['https://www.stats.gov.cn/','https://www.stats.gov.cn/','https://www.pbc.gov.cn/','https://www.chinamoney.com.cn/','https://www.pbc.gov.cn/','https://www.mof.gov.cn/','https://www.sse.com.cn/']
 return [dict(id=id,name=name,group=GROUPS[group],frequency=freq,unit=unit,definition=definition,level=level,
   sensitivity=kind,sourceUrl=sources[group],parser='numeric',hidden=False,value=None,previous=None,expected=None,
   period=None,publishedAt=None,history=[],yoy=None,mom=None,stale=False,missing='尚未接入可核实的同口径序列')
  for id,name,group,freq,unit,definition,level,kind in ROWS]
def matrix(indicators):
 # Responses to a rising indicator, not claims about observed returns.
 patterns={'growth':[(1,2),(1,2),(1,2),(0,1),(1,3),(1,2),(1,1),(1,2)],
 'consumption':[(1,1),(1,1),(1,1),(1,1),(0,1),(1,1),(0,1),(1,3)],
 'inflation':[(-1,2),(1,1),(-1,1),(-1,1),(-1,2),(-1,2),(0,1),(1,1)],
 'liquidity':[(1,3),(1,1),(1,3),(1,1),(1,2),(1,3),(1,1),(1,1)],
 'credit':[(1,2),(1,3),(1,2),(1,1),(1,3),(1,2),(1,1),(1,1)],
 'rate':[(-1,3),(1,1),(-1,2),(-1,1),(-1,2),(-1,3),(-1,1),(-1,1)],
 'dollar':[(-1,2),(-1,1),(-1,2),(-1,1),(-1,2),(-1,2),(0,1),(-1,1)],
 'defense':[(0,1),(0,1),(0,1),(1,1),(0,1),(0,1),(1,1),(0,1)],
 'valuation':[(-1,2),(-1,2),(-1,2),(-1,2),(-1,2),(-1,2),(-1,2),(-1,2)],
 'attractiveness':[(1,2)]*8,
 'sentiment':[(1,2),(1,1),(1,3),(0,1),(1,2),(1,2),(0,1),(1,1)]}
 return {i['id']:{id:dict(sign=v[0],strength=v[1],reason='初始研究假设：指标上行的相对行业敏感性，未经团队评审或统计验证') for (id,_,_),v in zip(SECTORS,patterns[i['sensitivity']])} for i in indicators}
