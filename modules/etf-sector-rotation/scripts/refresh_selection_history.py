import json,datetime,urllib.request,concurrent.futures,math
from pathlib import Path
from tdx_parser import _tdx_parse_package,TDX_PACKAGE_URL
ROOT=Path(__file__).resolve().parents[1];CACHE=ROOT/'assets/selection-history';CACHE.mkdir(exist_ok=True)
def refresh():
 data=json.loads((ROOT/'assets/selection-data.json').read_text(encoding='utf8'));market=json.loads((ROOT/'assets/market-official.json').read_text(encoding='utf8'));end=max(r['asOf'] for r in data['rows'].values());dates=sorted(d for d in market['priceHistory']['510300']['closes'] if d<=end)[-20:]
 if len(dates)!=20 or dates[-1]!=end:raise ValueError('common calendar window unavailable')
 codes=set(data['rows']);errors=[]
 def get(day):
  path=CACHE/(day+'.json')
  if path.exists():return day,json.loads(path.read_text(encoding='utf8')),None
  try:
   compact=day.replace('-','');url=TDX_PACKAGE_URL.format(ymd=compact)
   req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
   with urllib.request.urlopen(req,timeout=25) as response:body=response.read()
   rows=_tdx_parse_package(body,compact);selected={r['code']:r for r in rows if r['code'] in codes and r['market']==('sh' if r['code'].startswith('5') else 'sz')}
   path.write_text(json.dumps(selected,ensure_ascii=False),encoding='utf8');return day,selected,None
  except Exception as e:return day,{},type(e).__name__+': '+str(e)
 observations={}
 for day,rows,error in concurrent.futures.ThreadPoolExecutor(3).map(get,dates):
  observations[day]=rows
  if error:errors.append(day+': '+error)
  print(day,len(rows),'OK' if not error else 'failed',flush=True)
 for code,row in data['rows'].items():
  values=[observations[day].get(code,{}).get('amount') for day in dates]
  if all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) and v>=0 for v in values):row['avgAmount20']=sum(values)/20;row['amountWindow']={'start':dates[0],'end':end,'dates':dates,'count':20,'source':'https://www.tdx.com.cn/products/data/data/g4day/'}
  else:row['avgAmount20']=None;row['amountWindow']=None
 data['historyErrors']=errors;data['historyAttemptedAt']=datetime.datetime.now().isoformat();(ROOT/'assets/selection-data.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps({'complete20':sum(r.get('avgAmount20') is not None for r in data['rows'].values()),'total':len(codes),'errors':errors}),flush=True)
if __name__=='__main__':refresh()
