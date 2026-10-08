"""Refresh official ETF product shares; keep dated SSE separate from undated SZSE snapshot."""
from pathlib import Path
import json, urllib.request, urllib.parse, datetime, io, re, math
ROOT=Path(__file__).resolve().parents[1]
def request(url,referer):
 return urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Referer':referer}),timeout=25).read()
def refresh(date=None):
 assets=ROOT/'assets'; path=assets/'market-official.json'
 old=json.loads(path.read_text(encoding='utf8')) if path.exists() else {'rows':[]}
 now=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
 groups={exchange:[r for r in old['rows'] if r['exchange']==exchange] for exchange in ['上交所','深交所']};errors={}
 q={'isPagination':'true','pageHelp.pageSize':'10000','pageHelp.pageNo':'1','sqlId':'COMMON_SSE_ZQPZ_ETFZL_XXPL_ETFGM_SEARCH_L','STAT_DATE':date or ''}
 try:
  data=json.loads(request('https://query.sse.com.cn/commonQuery.do?'+urllib.parse.urlencode(q),'https://www.sse.com.cn/'))
  rows=[]
  for r in data['result']:
   if not re.fullmatch(r'\d{6}',r['SEC_CODE']) or not r.get('STAT_DATE'):raise ValueError('invalid code/date')
   shares=float(r['TOT_VOL'])*10000
   if not math.isfinite(shares) or shares<0:raise ValueError('invalid shares')
   if datetime.date.fromisoformat(r['STAT_DATE']).isoformat()!=r['STAT_DATE']:raise ValueError('invalid date')
   rows.append({'code':r['SEC_CODE'],'name':r['SEC_NAME'],'shares':shares,'asOf':r['STAT_DATE'],'exchange':'上交所','retrievedAt':now,'source':'https://www.sse.com.cn/assortment/fund/etf/list/scale/'})
  if not rows:raise ValueError('empty SSE observation')
  if len({r['code'] for r in rows})!=len(rows):raise ValueError('duplicate SSE code')
  groups['上交所']=rows
 except Exception as e:errors['上交所']=str(e)
 try:
  import pandas as pd
  b=request('https://fund.szse.cn/api/report/ShowReport?SHOWTYPE=xlsx&CATALOGID=1000_lf&TABKEY=tab1','https://fund.szse.cn/marketdata/fundslist/index.html')
  frame=pd.read_excel(io.BytesIO(b),dtype=str);rows=[]
  for r in frame.to_dict('records'):
   if r['基金类别']!='ETF':continue
   code=str(r['基金代码']);shares=float(str(r['当前规模(份)']).replace(',',''))
   if not re.fullmatch(r'\d{6}',code) or not math.isfinite(shares) or shares<0:raise ValueError('invalid SZSE observation')
   rows.append({'code':code,'name':r['基金简称'],'shares':shares,'asOf':None,'exchange':'深交所','retrievedAt':now,'source':'https://fund.szse.cn/marketdata/fundslist/index.html'})
  if not rows:raise ValueError('empty SZSE observation')
  if len({r['code'] for r in rows})!=len(rows):raise ValueError('duplicate SZSE code')
  groups['深交所']=rows
 except Exception as e:errors['深交所']=str(e)
 out={'retrievedAt':now,'errors':errors,'periodBaselines':old.get('periodBaselines',{}),'priceHistory':old.get('priceHistory',{}),'rows':groups['上交所']+groups['深交所'],'note':'上交所份额原字段为万份，转换为份；深交所为份，未返回统计日，不能将抓取日冒充所属日。'}
 path.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8')
 return out
if __name__=='__main__':
 import sys
 data=refresh(sys.argv[1] if len(sys.argv)>1 else None)
 print(json.dumps({'rows':len(data['rows']),'errors':data['errors']},ensure_ascii=True))
