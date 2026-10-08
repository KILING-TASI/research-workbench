"""Official NBS release adapters. Preserve published observation types and dates."""
import re,html,urllib.parse,concurrent.futures
from resilient_fetch import get_text
INDEX='https://www.stats.gov.cn/sj/zxfb/'
KINDS={'pmi':'中国采购经理指数运行情况','profit':'全国规模以上工业企业利润','industrial':'规模以上工业增加值','investment':'全国固定资产投资','housing':'全国房地产市场','ppi':'工业生产者出厂价格','capacity':'工业产能利用率'}
def plain(s):
 s=re.sub(r'<(script|style)\b.*?</\1>','',s,flags=re.S|re.I)
 return re.sub(r'\s+','',html.unescape(re.sub('<[^>]+>','',s)))
def tables(s):
 return [[ [plain(c) for c in re.findall(r'<t[dh]\b[^>]*>(.*?)</t[dh]>',row,re.S|re.I)] for row in re.findall(r'<tr\b.*?</tr>',t,re.S|re.I)] for t in re.findall(r'<table\b.*?</table>',s,re.S|re.I)]
def deduplicate_observations(observations):
 result={}
 for key,items in observations.items():
  unique={}
  for item in items:
   period=item['period']
   if period in unique:
    previous={k:v for k,v in unique[period].items() if k!='repeatedSourceRowCount'}
    if previous!=item:raise ValueError('同指标同月原文观测冲突，不能静默覆盖')
    unique[period]['repeatedSourceRowCount']=unique[period].get('repeatedSourceRowCount',1)+1
   else:unique[period]=dict(item)
  result[key]=list(unique.values())
 return result

def parse(kind,s,url):
 pub=re.search(r'<meta\s+name="PubDate"\s+content="([^"]+)"',s,re.I)
 if not pub:pub=re.search(r'class="detail-title-des".*?(20\d{2}/\d{2}/\d{2}[^<]*)',s,re.S)
 if not pub:raise ValueError('官方发布日期字段缺失')
 released=pub[1][:10].replace('/','-');body=plain(s);ts=tables(s);out={}
 def put(id,value,period,yoy=None,**extra):
  out.setdefault(id,[]).append(dict(period=period,value=float(value),yoy=yoy,official_release_date=released,sourceUrl=url,**extra))
 def number(pattern):
  m=re.search(pattern,body)
  if not m:raise ValueError('字段未匹配：'+pattern)
  return float(m[1])
 def growth(pattern):
  m=re.search(pattern,body)
  if not m:raise ValueError('增速字段未匹配')
  return float(m[2])*(-1 if m[1]=='下降' else 1)
 if kind=='annual':
  year=re.search(r'中华人民共和国(20\d{2})年国民经济和社会发展统计公报',body)
  if not year:raise ValueError('年度未匹配')
  period=year[1]
  for id,pattern in [('urbanization',r'常住人口城镇化率为([\d.]+)%'),('labor_productivity',r'全员劳动生产率\[4\]为([\d.]+)元/人'),('research_intensity',r'研究与试验发展（R&D）经费支出[\d.]+亿元.*?与国内生产总值之比为([\d.]+)%'),('hightech_value_share',r'高技术制造业\[13\]增加值增长[\d.]+%，占规模以上工业增加值比重为([\d.]+)%')]:
   put(id,number(pattern),period)
 elif kind=='pmi':
  for t in ts:
   header=''.join(''.join(row) for row in t[:3])
   cols={'pmi_new_orders':3,'pmi_raw_inventory':4} if '供应商配送时间' in header and 'PMI' in header else {'pmi_finished_inventory':6,'pmi_purchase_quantity':3,'pmi_backlog_orders':7} if '产成品库存' in header and '新出口订单' in header else {}
   for row in t:
    if not row:continue
    m=re.fullmatch(r'(\d{4})年(\d{1,2})月',row[0])
    if not m:continue
    period=f'{m[1]}-{int(m[2] if m.lastindex>=2 else 12):02d}'
    for id,col in cols.items():
     if len(row)>col:
      put(id,row[col],period)
      # Earlier rows republished in current release are NOT original publication dates.
      if period!=released[:7]:out[id][-1]['official_release_date']=None;out[id][-1]['observed_release_date']=released
 else:
  m=re.search(r'(20\d{2})年(?:1[—－-])?(\d{1,2})月',body)
  if not m and kind=='profit':m=re.search(r'(20\d{2})年.*?(12)月',body) or re.search(r'(20\d{2})年全国',body)
  if not m and kind!='capacity':raise ValueError('数据所属期未匹配')
  period=f'{m[1]}-{int(m[2] if m.lastindex>=2 else 12):02d}' if m else None
  if kind=='profit':
   financial=next(t for t in ts if '营业收入' in ''.join(''.join(r) for r in t[:4]) and '利润总额' in ''.join(''.join(r) for r in t[:4]))
   row=next(r for r in financial if r and r[0]=='总计')
   put('industrial_revenue',row[1],period,float(row[2]));put('industrial_profit',row[5],period,float(row[6]))
   ops=next(t for t in ts if '周转天数' in ''.join(''.join(r) for r in t[:4]))
   row=next(r for r in ops if r and r[0]=='总计')
   put('industrial_profit_margin',row[1],period);put('inventory_days',row[7],period)
   m=re.search(r'产成品存货([\d.]+)(万亿元|亿元)[，,](?:同比)?(增长|下降)([\d.]+)%',body)
   if not m:raise ValueError('库存金额与可比同比未匹配')
   put('finished_inventory',float(m[1])*(10000 if m[2]=='万亿元' else 1),period,float(m[4])*(-1 if m[3]=='下降' else 1),precision_note='保留公告金额原精度及官方可比同比')
  elif kind=='industrial':put('industrial_output',growth(r'规模以上工业增加值同比(?:实际)?(增长|下降)([\d.]+)%'),period)
  elif kind=='investment':
   t=next(t for t in ts if any(r and r[0]=='设备工器具购置' for r in t))
   for id,label in [('equipment_investment','设备工器具购置'),('manufacturing_investment','制造业')]:put(id,next(r[1] for r in t if r and r[0]==label),period)
   put('infrastructure_investment',growth(r'基础设施投资(?:（口径详见附注1）|（不含电力、热力、燃气及水生产和供应业）)同比(增长|下降)([\d.]+)%'),period)
  elif kind=='housing':
   put('real_estate_investment',growth(r'全国房地产开发投资[\d.]+亿元，同比(增长|下降)([\d.]+)%'),period)
   for id,pat in [('housing_starts',r'房屋新开工面积([\d.]+)万平方米'),('housing_completions',r'房屋竣工面积([\d.]+)万平方米'),('housing_sales_area',r'(?:新建)?商品房销售面积([\d.]+)万平方米'),('housing_for_sale',r'(?:新建)?商品房待售面积([\d.]+)万平方米')]:put(id,number(pat),period)
  elif kind=='ppi':put('producer_prices',growth(r'工业生产者出厂价格同比(上涨|下降)([\d.]+)%'),period)
  elif kind=='capacity':
   q=re.search(r'(20\d{2})年([一二三四])季度',body)
   if not q:raise ValueError('季度未匹配')
   period=f'{q[1]}-Q'+str('一二三四'.index(q[2])+1)
   put('capacity_utilization',number(r'工业产能利用率为([\d.]+)%'),period)
 return deduplicate_observations(out)

def discover():
 def page(n):return get_text(INDEX+('index_'+str(n)+'.html' if n else ''),timeout=10)
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:pages=list(pool.map(page,range(4)))
 candidates={k:[] for k in KINDS}
 for s in pages:
  for link,title in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>',s,re.S):
   title=plain(title);url=urllib.parse.urljoin(INDEX,link)
   if not re.match(r'https://www.stats.gov.cn/sj/zxfb/\d{6}/t\d{8}_\d+\.html$',url):continue
   for kind,needle in KINDS.items():
    if needle in title:candidates[kind].append(url)
 urls={k:max(set(v)) for k,v in candidates.items() if v}
 annual_index='https://www.stats.gov.cn/xxgk/sjfb/tjgb2020/'
 try:
  text=get_text(annual_index,timeout=10)
  links=[urllib.parse.urljoin(annual_index,link) for link,title in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>',text,re.S) if re.search(r'中华人民共和国20\d{2}年国民经济和社会发展统计公报',plain(title))]
  if links:urls['annual']=max(links)
 except Exception:pass
 return urls

def fetch_all():
 urls=discover();data={};errors={}
 def job(item):
  kind,url=item
  try:return kind,parse(kind,get_text(url,timeout=10),url),None
  except Exception as e:return kind,{},str(e)
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
  for kind,rows,error in pool.map(job,urls.items()):
   data.update(rows)
   if error:errors[kind]=error
 for kind in KINDS:
  if kind not in urls:errors[kind]='当前发布窗口未发现公告'
 return data,errors,urls
