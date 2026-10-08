"""HK/US explicit-symbol daily price archive; empty history is a gap."""
import argparse,datetime as dt,hashlib,json,math
from pathlib import Path
from urllib.parse import urlencode
from cross_market_quote import symbol
from collection_validation import day as validated_day,unique_pairs,reject_constant
from public_download import download

def parse(payload,market,code,start,end,query_symbol=None):
 for d in [start,end]:validated_day(d)
 if not isinstance(payload,dict) or not isinstance(payload.get('data'),dict):raise ValueError('历史响应须为行情对象')
 if start>=end:raise ValueError('日期范围无效')
 base=symbol(market,code);sym=query_symbol or base
 if sym not in ([base] if market=='HK' else [base,base+'.OQ',base+'.N',base+'.A']):raise ValueError('查询映射与代码不匹配')
 if payload.get('code')!=0 or sym not in payload.get('data',{}):raise ValueError('历史响应失败或标识不匹配')
 data=payload['data'][sym]
 if not isinstance(data,dict) or not isinstance(data.get('qt',{}),dict):raise ValueError('证券行情节点结构无效')
 qt=data.get('qt',{}).get(sym,[])
 if not isinstance(qt,list) or len(qt)<3 or not isinstance(qt[1],str) or not qt[1].strip():raise ValueError('证券名称与报价结构无效')
 if len(qt)<3 or not qt[1] or qt[2] not in ([code] if market=='HK' else [code,code+'.OQ',code+'.N',code+'.A']):raise ValueError('证券身份线索不匹配')
 raw=data.get('day')
 if not isinstance(raw,list) or not raw:raise ValueError('供应商未返回日线；报价可用不代表历史可用')
 rows=[];all_dates=[]
 for x in raw:
  if not isinstance(x,list) or len(x)<5:raise ValueError('日线布局不匹配')
  day=validated_day(x[0]).isoformat();all_dates.append(day)
  vals=[float(v) for v in x[1:5]]
  if any(not math.isfinite(v) or v<=0 for v in vals):raise ValueError('价格无效')
  op,close,high,low=vals
  if high<max(op,close,low) or low>min(op,close,high):raise ValueError('OHLC勾稽不一致')
  if start<=day<=end:rows.append(dict(date=day,open=op,close=close,high=high,low=low))
 if all_dates!=sorted(set(all_dates)):raise ValueError('日期重复或乱序')
 if not rows:raise ValueError('请求区间无日线')
 return dict(market=market,code=code,name=qt[1],currency='HKD' if market=='HK' else 'USD',requestedStart=start,requestedEnd=end,actualStart=rows[0]['date'],actualEnd=rows[-1]['date'],history=rows,historyBasis='provider-day-price-unadjusted-no-total-return-verification',startGapDays=(dt.date.fromisoformat(rows[0]['date'])-dt.date.fromisoformat(start)).days,endGapDays=(dt.date.fromisoformat(end)-dt.date.fromisoformat(rows[-1]['date'])).days,calendarVerified=False,limitations=['仅价格日线，未核实分红拆分，不用于总收益比较','供应商返回身份线索不是交易所分类核验','返回上限可能截断窗口，实际日期必须展示','交易日历及缺日未核验，当前修订历史不是事前冻结数据'])
def history_url(sym,start,end):
 return 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?'+urlencode({'param':sym+',day,'+start+','+end+',640,'})
def mapped_symbol(payload,market,code):
 base=symbol(market,code)
 if market!='US' or payload.get('code')!=0:return None
 node=payload.get('data',{}).get(base,{})
 if node.get('day'):return None
 qt=node.get('qt',{}).get(base,[])
 if len(qt)<3:return None
 vendor=qt[2]
 if vendor not in [code+'.OQ',code+'.N',code+'.A']:return None
 return 'us'+vendor

def fetch(url):
 return download(url,limit=16*1024*1024,timeout=20)

def collect(market,code,start,end,fetch_fn=fetch):
 validated_day(start);validated_day(end)
 if start>=end:raise ValueError('日期范围无效')
 sym=symbol(market,code);initial=sym;attempts=[];payload=None;raw=None;error=None
 for attempt in range(2):
  url=history_url(sym,start,end)
  try:
   raw=fetch_fn(url)
   entry=dict(sourceUrl=url,sha256=hashlib.sha256(raw).hexdigest())
   try:payload=json.loads(raw,object_pairs_hook=unique_pairs,parse_constant=reject_constant)
   except Exception as exc:
    entry.update(error='响应不是有效JSON：'+str(exc),rawText=raw.decode('utf-8',errors='replace'));attempts.append(entry);error=entry['error'];break
   entry['payload']=payload;entry['rawText']=raw.decode('utf-8');attempts.append(entry)
   mapped=mapped_symbol(payload,market,code) if attempt==0 else None
   if mapped:sym=mapped;continue
   break
  except Exception as exc:
   error=type(exc).__name__+': '+str(exc);attempts.append(dict(sourceUrl=url,error=error));break
 try:
  if error:raise ValueError(error)
  result=parse(payload,market,code,start,end,sym)
  result['status']='已取得价格日线，完整性及复权未核验'
 except Exception as exc:
  result=dict(market=market,code=code,requestedStart=start,requestedEnd=end,history=[],status='历史未取得',reason=str(exc),limitations=['本次接口尝试失败不代表其他数据源无历史资料','不以报价、插值或旧缓存替代本次请求'])
 result.update(querySymbol=sym,initialQuerySymbol=initial,attemptCount=len(attempts),sourceUrl=attempts[-1]['sourceUrl'],retrievedAt=dt.datetime.now(dt.timezone.utc).isoformat(),sha256=attempts[-1].get('sha256'))
 return result,attempts

def write_result(result,attempts,out):
 out=Path(out)
 for path in [out,out.with_suffix('.md'),out.with_suffix('.raw.json')]:
  if path.exists():raise FileExistsError('输出已存在')
 out.parent.mkdir(parents=True,exist_ok=True)
 out.with_suffix('.raw.json').write_text(json.dumps(attempts,ensure_ascii=False,indent=2),encoding='utf-8')
 out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 lines=['# 跨市场日线资料','',result['market']+' '+result['code'],f"请求区间{result['requestedStart']}至{result['requestedEnd']}。"]
 if result['history']:
  lines += [f"实际区间{result['actualStart']}至{result['actualEnd']}，{len(result['history'])}个观测，币种{result['currency']}。",f"请求起点相差{result['startGapDays']}个自然日，终点相差{result['endGapDays']}个自然日；未核对交易日历，不能据此认定缺少交易日。",'价格日线未核实分红拆分，不作为总收益序列。']
 else:lines += ['历史未取得：'+result['reason'],'接口尝试与失败原因已保存；网络失败没有原始响应正文。']
 lines += result['limitations']+['',result['sourceUrl']]
 out.with_suffix('.md').write_text('\n'.join(lines),encoding='utf-8')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--market',required=True);p.add_argument('--code',required=True);p.add_argument('--start',required=True);p.add_argument('--end',required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 for path in [a.out,a.out.with_suffix('.md'),a.out.with_suffix('.raw.json')]:
  if path.exists():raise FileExistsError('输出已存在')
 result,attempts=collect(a.market,a.code,a.start,a.end)
 write_result(result,attempts,a.out)
