"""Derived same-day CNY per HKD from two FRED H.10 series."""
import argparse,csv,datetime as dt,hashlib,io,json,urllib.request
from pathlib import Path
from urllib.parse import urlencode
from fund_series_tools import day,num
from collection_validation import unique_pairs,reject_constant
from public_download import download

def derive(usd,raw,start,end,asof):
 if not isinstance(usd,dict) or not isinstance(usd.get('history'),list) or any(not isinstance(x,dict) for x in usd['history']):raise ValueError('美元人民币输入须含历史对象数组')
 if not isinstance(raw,bytes):raise ValueError('港币汇率响应须为原始CSV字节')
 day(start);day(end);day(asof)
 if not start<end<=asof:raise ValueError('日期区间无效')
 if usd.get('unit')!='CNY-per-USD' or usd.get('baseCurrency')!='USD' or usd.get('targetCurrency')!='CNY' or usd.get('sourceUrl')!='https://fred.stlouisfed.org/series/DEXCHUS':raise ValueError('需明确FRED美元人民币序列，不接受方向不明汇率')
 reader=csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
 if reader.fieldnames!=['observation_date','DEXHKUS']:raise ValueError('HKD/USD列名不匹配')
 cny={};last=''
 for x in usd['history']:
  d=day(x['date']);v=num(x['value'],True)
  if d<=last or d>asof:raise ValueError('美元人民币日期重复、乱序或越界')
  last=d
  if start<=d<=end:cny[d]=v
 hk={};missing=[];last=''
 for x in reader:
  if None in x or x.get('observation_date') is None or x.get('DEXHKUS') is None:raise ValueError('港币汇率CSV列数不一致')
  d=day(x['observation_date'])
  if d<=last:raise ValueError('港币日期重复或乱序')
  last=d
  if not start<=d<=end:continue
  if x['DEXHKUS'] in ('','.'):missing.append(d);continue
  hk[d]=num(float(x['DEXHKUS']),True)
 dates=sorted(cny.keys() & hk.keys())
 if len(dates)<2:raise ValueError('两汇率同日交集不足，不插值')
 rows=[]
 for d in dates:
  rate=cny[d]/hk[d];num(rate,True);rows.append(dict(date=d,value=rate,cnyPerUSD=cny[d],hkdPerUSD=hk[d]))
 return dict(baseCurrency='HKD',targetCurrency='CNY',unit='CNY-per-HKD',sourceUrl='https://fred.stlouisfed.org/series/DEXHKUS',sources=[usd['sourceUrl'],'https://fred.stlouisfed.org/series/DEXHKUS'],publishedThrough=asof,basis='FRED-H10-same-date-DEXCHUS-divided-by-DEXHKUS-current-vintage',history=rows,missingHKDObservationDates=missing,unmatchedUSDCDates=sorted(cny.keys()-hk.keys()),unmatchedHKDDates=sorted(hk.keys()-cny.keys()),formula='CNY/HKD=(CNY/USD)/(HKD/USD)',actualStart=dates[0],actualEnd=dates[-1],currentVintageOnly=True,historicalPublicationVerified=False,limitations=['交叉汇率是两条同日纽约中午观测相除，不是银行直接港币人民币成交价','同日不代表港股收盘时刻一致；交易日与报价时刻未完全对齐','当前版本可能修订，不作为事前冻结输入；publishedThrough仅研究截止标签'])

def collect(usd_path,start,end,asof,directory):
 out=Path(directory)
 if out.exists():raise FileExistsError('输出目录已存在')
 usd_raw=Path(usd_path).read_bytes();usd=json.loads(usd_raw.decode('utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant)
 day(start);day(end);day(asof)
 if not start<end<=asof:raise ValueError('日期区间无效')
 url='https://fred.stlouisfed.org/graph/fredgraph.csv?'+urlencode(dict(id='DEXHKUS',cosd=start,coed=end))
 raw=download(url,limit=8*1024*1024,timeout=20)
 r=derive(usd,raw,start,end,asof);r.update(downloadUrl=url,rawSha256=hashlib.sha256(raw).hexdigest(),usdInputSha256=hashlib.sha256(usd_raw).hexdigest(),retrievedAt=dt.datetime.now(dt.timezone.utc).isoformat());out.mkdir(parents=True);(out/'DEXHKUS.csv').write_bytes(raw);(out/'美元人民币输入.json').write_bytes(usd_raw);(out/'result.json').write_text(json.dumps(r,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8');return r
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--usd-cny',required=True);p.add_argument('--start',required=True);p.add_argument('--end',required=True);p.add_argument('--as-of',required=True);p.add_argument('--out-dir',required=True);a=p.parse_args();collect(a.usd_cny,a.start,a.end,a.as_of,a.out_dir)
