"""Public sector/ETF snapshot. Standard library; atomic cache and independent failures."""
import argparse,concurrent.futures,datetime as dt,html,json,math,re,statistics,time,urllib.parse,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
TZ=dt.timezone(dt.timedelta(hours=8))
SECTORS=[('半导体','BK1036',['159995','512480']),('银行','BK0475',['512800','512700']),
 ('证券','BK0473',['512880','512000']),('医药生物','BK1216',['512010','159938']),
 ('电力设备','BK1200',['159875','516160']),('软件开发','BK0737',['515230','159852']),
 ('国防军工','BK1218',['512660','512810']),('食品饮料','BK0438',['515170','159862'])]
def get(url,params=None):
 if params:url+='?'+urllib.parse.urlencode(params,safe=',:')
 req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://quote.eastmoney.com/'})
 with urllib.request.urlopen(req,timeout=25) as response:return response.read().decode('utf-8-sig')
def js(url,params=None):return json.loads(get(url,params))
def finite(x):return isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x)
def num(x):
 try:
  v=float(x);return v if math.isfinite(v) else None
 except (TypeError,ValueError):return None
def median(a):
 a=[x for x in a if finite(x)];return statistics.median(a) if a else None
def mean(a):return statistics.mean(a) if a else None

def validate_prices(rows):
 previous=''
 for row in rows:
  observed=row['date']
  if not isinstance(observed,str) or dt.date.fromisoformat(observed).isoformat()!=observed or observed<=previous:raise ValueError('价格日期无效、重复或乱序')
  if not finite(row['close']) or row['close']<=0 or not finite(row['amount']) or row['amount']<0:raise ValueError('价格或成交额无效')
  if row.get('volume') is not None and (not finite(row['volume']) or row['volume']<0):raise ValueError('成交量无效')
  previous=observed
 return rows
def tx_market():
 url='https://proxy.finance.qq.com/cgi/cgi-bin/rank/hs/getBoardRankList'
 def page(offset):
  data=js(url,dict(_appver='11.17.0',board_code='aStock',sort_type='price',direct='down',offset=offset,count=200))
  if data.get('code')!=0 or not data.get('data'):raise ValueError('腾讯行情分页失败')
  return data['data']
 first=page(0);rows=first['rank_list']
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
  for result in pool.map(page,range(200,int(first['total']),200)):rows.extend(result['rank_list'])
 if len(rows)<int(first['total'])*.95:raise ValueError('备用行情覆盖不足')
 return {r['code'][2:]:r for r in rows}
def tx_prices(code,today):
 symbol=('sh' if code.startswith('5') else 'sz')+code
 data=js('https://web.ifzq.gtimg.cn/appstock/app/fqkline/get',dict(param=symbol+',day,,,260,'))
 item=data.get('data',{}).get(symbol,{})
 series=[dict(date=p[0],close=float(p[2]),volume=float(p[5]),amount=float(p[5])*100*float(p[2]))
         for p in item.get('day',[]) if len(p)>=6 and p[0]<=today and num(p[2]) and num(p[5]) is not None]
 if len(series)<60:raise ValueError('备用ETF价格不足60日')
 validate_prices(series)
 qt=item.get('qt',{}).get(symbol,[])
 name=qt[1] if len(qt)>1 else code
 return name,series
def klines(secid,today):
 data=js('https://push2his.eastmoney.com/api/qt/stock/kline/get',dict(secid=secid,klt=101,fqt=1,lmt=260,end='20500101',fields1='f1,f2,f3,f4,f5,f6',fields2='f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61')).get('data')
 if not data:raise ValueError('价格序列为空')
 rows=[]
 for line in data.get('klines',[]):
  p=line.split(',')
  if p[0]<=today and len(p)>=7 and num(p[2]) and num(p[6]) is not None:
   rows.append(dict(date=p[0],close=float(p[2]),volume=num(p[5]),amount=float(p[6])))
 if len(rows)<60:raise ValueError('价格序列不足60个交易日')
 validate_prices(rows)
 return data['name'],rows
def financial(today):
 periods=[dt.date(today.year,m,d) for m,d in [(3,31),(6,30),(9,30),(12,31)] if dt.date(today.year,m,d)<today]
 periods.extend([dt.date(today.year-1,12,31)])
 for date in sorted(periods,reverse=True):
  params=dict(reportName='RPT_LICO_FN_CPD',columns='ALL',filter=f"(REPORTDATE='{date}')(NOTICE_DATE<='{today}')",pageSize=500,pageNumber=1)
  result=js('https://datacenter-web.eastmoney.com/api/data/v1/get',params).get('result')
  if not result or result.get('count',0)<1000:continue
  rows=result['data']
  for page in range(2,int(result['pages'])+1):
   params['pageNumber']=page
   nxt=js('https://datacenter-web.eastmoney.com/api/data/v1/get',params).get('result')
   if not nxt:raise ValueError('财报分页缺失')
   rows.extend(nxt['data'])
  a={}
  for r in rows:
   if r.get('NOTICE_DATE','9999')[:10]>str(today) or r.get('SECURITY_TYPE')!='A股':continue
   code=r['SECURITY_CODE']
   if code not in a or r.get('UPDATE_DATE','')>a[code].get('UPDATE_DATE',''):a[code]=r
  return str(date),a
 raise ValueError('没有覆盖足够公司的已公告财报')
def fund_info(code,today):
 url=f'https://fundf10.eastmoney.com/jbgk_{code}.html'
 raw=get(url)
 text=html.unescape(re.sub('<[^>]+>',' ',raw))
 text=re.sub(r'\s+',' ',text)
 def extract(pattern):
  m=re.search(pattern,text);return m.group(1) if m else None
 size=extract(r'净资产规模\s+([\d.]+)亿元')
 size_date=extract(r'净资产规模.*?截止至：\s*(\d{4}年\d{2}月\d{2}日)')
 inception=extract(r'成立日期/规模\s+(\d{4}年\d{2}月\d{2}日)')
 def date(value):return value.replace('年','-').replace('月','-').replace('日','') if value else None
 manage=num(extract(r'管理费率\s+([\d.]+)%'))
 custody=num(extract(r'托管费率\s+([\d.]+)%'))
 tracking_match=re.search(r'<th[^>]*>\s*跟踪标的\s*</th>\s*<td[^>]*>(.*?)</td>',raw,re.S)
 tracking=html.unescape(re.sub('<[^>]+>','',tracking_match.group(1))).strip() if tracking_match else None
 return dict(code=code,sizeYi=num(size) if date(size_date) and date(size_date)<=today else None,sizeDate=date(size_date),
  feePct=manage+custody if manage is not None and custody is not None else None,
  feeBasis='管理费＋托管费；不含其他运作费用及交易佣金',inceptionDate=date(inception),
  trackingErrorPct=None,trackingErrorBasis='缺少同口径实际年化跟踪误差，未纳入优选',benchmark=tracking,
  sourceUrl=url,source='天天基金（第三方）')
def refresh():
 dest=ROOT/'assets';dest.mkdir(parents=True,exist_ok=True)
 previous=json.loads((dest/'data.json').read_text(encoding='utf-8')) if (dest/'data.json').exists() else {}
 now=dt.datetime.now(TZ);today=now.date();errors=[]
 try:report_date,financials=financial(today)
 except Exception as e:report_date=None;financials={};errors.append('财报：'+str(e))
 try:market=tx_market()
 except Exception as e:market={};errors.append('备用行情：'+str(e))
 groups={
  '半导体':['半导体'], '银行':['银行'], '证券':['证券'],
  '医药生物':['化学制药','生物制品','医药商业','中药','医疗器械','医疗服务'],
  '电力设备':['电池','光伏设备','风电设备','电网设备','电机','其他电源设备'],
  '软件开发':['软件开发'], '国防军工':['军工电子','航空装备','航天装备','航海装备','地面兵装'],
  '食品饮料':['白酒','饮料乳品','食品加工','休闲食品','调味发酵品','非白酒']}
 def sector_job(spec):
  name,board,codes=spec
  old=next((r for r in previous.get('sectors',[]) if r['id']==board),{})
  try:
   if market:raise ValueError('统一使用腾讯备用横截面，避免混合资金与估值定义')
   actual,series=klines('90.'+board,str(today))
   if actual!=name:raise ValueError(f'行业代码不匹配：{name} / {actual}')
   constituents=[]
   for page in range(1,10):
    result=js('https://push2.eastmoney.com/api/qt/clist/get',dict(pn=page,pz=100,fs='b:'+board,fields='f12,f14,f9',fid='f12',po=1,fltt=2)).get('data')
    if not result:raise ValueError('成分列表缺失')
    part=result['diff'];part=part if isinstance(part,list) else list(part.values());constituents.extend(part)
    if len(constituents)>=result['total']:break
   else:raise ValueError('成分列表超限')
   matched=[financials[r['f12']] for r in constituents if r['f12'] in financials]
   coverage=len(matched)/len(constituents) if constituents else 0
   enough=len(matched)>=10 and coverage>=.7
   earning=median([num(r.get('SJLTZ')) for r in matched]) if enough else None
   roe=median([num(r.get('WEIGHTAVG_ROE')) for r in matched]) if enough else None
   pes=[num(r.get('f9')) for r in constituents];pe=median([p for p in pes if finite(p) and p>0])
   flow=js('https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get',dict(secid='90.'+board,lmt=30,klt=101,fields1='f1,f2,f3,f7',fields2='f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63')).get('data')
   if not flow or flow.get('name')!=name:raise ValueError('行业资金流缺失或名称不匹配')
   flows=[p.split(',') for p in flow['klines'] if p.split(',')[0]<=str(today)]
   amounts={r['date']:r['amount'] for r in series}
   aligned=[p for p in flows if p[0] in amounts and num(p[1]) is not None][-5:]
   flow_ratio=sum(float(p[1]) for p in aligned)/sum(amounts[p[0]] for p in aligned)*100 if len(aligned)==5 and sum(amounts[p[0]] for p in aligned)>0 else None
   closes=[r['close'] for r in series];ma20=mean(closes[-20:]);ma60=mean(closes[-60:])
   trend=(closes[-1]/closes[-21]-1)*100
   structure=(ma20/ma60-1)*100
   vol=mean([r['amount'] for r in series[-5:]])/mean([r['amount'] for r in series[-20:]])
   if trend<0:vol=-vol
   raw_metrics=dict(earnings=earning,roe=roe,valuation=pe,flow=flow_ratio,northbound=None,trend=trend,ma=structure,volume=vol)
   row=dict(id=board,name=name,date=series[-1]['date'],fetchedAt=now.isoformat(timespec='seconds'),raw=raw_metrics,
    reportDate=report_date,coverage=coverage,matched=len(matched),constituentCount=len(constituents),
    sourceUrl=f'https://quote.eastmoney.com/bk/90.{board}.html',etfs=[],stale=False,
    notes=['动态PE为有效正值成分股中位数；跨行业估值分位，不是历史估值分位。',
     '盈利增速、ROE为当期已公告财报成分股中位数，不是行业利润总额增速。',
     '北向持仓改按季披露，暂无同口径季度变化，资金维度仅使用5日主力净流入/同期成交额。',
     '医药、电力设备等行业与ETF指数覆盖不同；映射为主题近似，选标的须核对跟踪指数。'])
  except Exception as e:
   try:
    actual,series=tx_prices(codes[0],str(today))
    samples=[r for r in financials.values() if any(k in (r.get('PUBLISHNAME') or '') for k in groups[name])]
    matched=[r for r in samples if r['SECURITY_CODE'] in market]
    if len(matched)<10 or len(matched)/max(1,len(samples))<.7:raise ValueError('财报与行情共同样本不足')
    quotes=[market[r['SECURITY_CODE']] for r in matched]
    pe=median([num(q.get('pe_ttm')) for q in quotes if (num(q.get('pe_ttm')) or -1)>0])
    flow_pairs=[(num(q.get('zllr_d5')),num(q.get('zllc_d5'))) for q in quotes]
    flow_pairs=[p for p in flow_pairs if all(finite(n) and n>=0 for n in p)]
    denominator=sum(a+b for a,b in flow_pairs)
    flow_ratio=sum(a-b for a,b in flow_pairs)/denominator*100 if denominator and len(flow_pairs)>=len(matched)*.7 else None
    closes=[r['close'] for r in series];trend=(closes[-1]/closes[-21]-1)*100
    volume=mean([r['volume'] for r in series[-5:]])/mean([r['volume'] for r in series[-20:]])
    row=dict(id=board,name=name,date=series[-1]['date'],fetchedAt=now.isoformat(timespec='seconds'),
      raw=dict(earnings=median([num(r.get('SJLTZ')) for r in matched]),roe=median([num(r.get('WEIGHTAVG_ROE')) for r in matched]),
       valuation=pe,flow=flow_ratio,northbound=None,trend=trend,ma=(mean(closes[-20:])/mean(closes[-60:])-1)*100,
       volume=volume if trend>=0 else -volume),reportDate=report_date,coverage=len(matched)/len(samples),matched=len(matched),
      constituentCount=len(samples),sourceUrl='https://data.eastmoney.com/bbsj/',etfs=[],stale=False,
      proxy=True,technicalProxy=codes[0],notes=[
       '备用来源：腾讯A股行情＋东方财富已公告财报，按财报行业分类合并；不是ETF指数成分股。',
       '估值为样本正值TTM市盈率中位数的跨行业分位，不是历史估值分位。',
       '资金为样本5日主力净流入/主力流入流出合计；非行业全量资金，北向季度变化缺失。',
       f'技术指标使用代表ETF {codes[0]} 未复权价格代理，分红可能影响趋势；量能以成交量计算并随趋势定方向。',
       '宽行业与ETF指数覆盖不同；映射为主题近似。'],primaryError=str(e))
   except Exception as fallback_error:
    row=dict(old) if old else dict(id=board,name=name,date=None,raw={},etfs=[])
    row['stale']=True;row['error']=str(fallback_error)
  for code in codes:
   try:
    info=fund_info(code,str(today))
    try:
     etf_name,prices=klines(('1.' if code.startswith('5') else '0.')+code,str(today));basis='20日实际成交额均值（东方财富）'
    except Exception:
     etf_name,prices=tx_prices(code,str(today));basis='20日成交量×当日未复权收盘价估计（腾讯），非实际日均成交额'
    info.update(name=etf_name,date=prices[-1]['date'],avgAmountYi=mean([p['amount'] for p in prices[-20:]])/1e8,
      fetchedAt=now.isoformat(timespec='seconds'),liquidityBasis=basis,stale=prices[-1]['date']!=str(today))
    row['etfs']=[x for x in row.get('etfs',[]) if x['code']!=code]+[info]
   except Exception as e:
    prior=next((x for x in old.get('etfs',[]) if x['code']==code),None)
    info=dict(prior) if prior else dict(code=code,name=code)
    info.update(stale=True,error=str(e));row['etfs']=[x for x in row.get('etfs',[]) if x['code']!=code]+[info]
  if row.get('date')!=str(today):
   row['stale']=True;row['freshnessStatus']='last-trading-date-not-confirmed'
  return row
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:sectors=list(pool.map(sector_job,SECTORS))
 if not any(s.get('date') for s in sectors):raise ValueError('全部行业数据获取失败，保留旧快照：'+json.dumps([(s['name'],s.get('error')) for s in sectors],ensure_ascii=False)+'；'+str(errors))
 events_path=dest/'events.json'
 events=json.loads(events_path.read_text(encoding='utf-8')) if events_path.exists() else dict(events=[],reviewedAt=None)
 snapshot=dict(schemaVersion=1,fetchedAt=now.isoformat(timespec='seconds'),date=max(s['date'] for s in sectors if s.get('date')),
  source='东方财富财报/行业数据；腾讯备用行情/资金；天天基金ETF资料（第三方）',sectors=sectors,events=events.get('events',[]),
  newsReviewedAt=events.get('reviewedAt'),newsScope=events.get('scope','消息样本未更新'),errors=errors,
  macro=dict(stage=None,source='宏观模块尚未接入，周期由用户手动选择'),
  northboundSource='https://www.sse.com.cn/aboutus/mediacenter/hotandd/c/c_20240412_10753188.shtml')
 content=json.dumps(snapshot,ensure_ascii=False,allow_nan=False,indent=2)
 path=dest/'data.json';tmp=path.with_suffix('.tmp');tmp.write_text(content,encoding='utf-8');tmp.replace(path)
 history=dest/'snapshots';history.mkdir(exist_ok=True)
 (history/(str(today)+'.json')).write_text(content,encoding='utf-8')
 return snapshot
if __name__=='__main__':
 try:
  s=refresh();print(json.dumps(dict(date=s['date'],sectors=len(s['sectors']),errors=[(x['name'],x.get('error')) for x in s['sectors'] if x.get('error')]),ensure_ascii=False))
 except Exception as e:raise SystemExit('未更新，保留最近快照：'+str(e))
