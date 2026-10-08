"""FRED DEXCHUS current-vintage daily CNY per USD archive."""
import argparse,csv,datetime as dt,hashlib,io,json,urllib.request
from pathlib import Path
from urllib.parse import urlencode
from fund_series_tools import day,num
from public_download import download
SERIES='https://fred.stlouisfed.org/series/DEXCHUS'
def parse(raw,start,end,asof):
 if not isinstance(raw,bytes):raise ValueError('汇率响应须为原始CSV字节')
 day(start);day(end);day(asof)
 if not start<end<=asof:raise ValueError('日期区间无效')
 reader=csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
 if reader.fieldnames!=['observation_date','DEXCHUS']:raise ValueError('CSV列名或汇率序列身份不匹配')
 rows=[];missing=[];last=''
 for x in reader:
  if None in x or x.get('observation_date') is None or x.get('DEXCHUS') is None:raise ValueError('美元汇率CSV列数不一致')
  d=day(x['observation_date'])
  if d<=last:raise ValueError('汇率日期重复或乱序')
  last=d
  if not start<=d<=end:continue
  if x['DEXCHUS'] in ('','.'):missing.append(d);continue
  v=float(x['DEXCHUS']);num(v,True);rows.append(dict(date=d,value=v))
 if not rows:raise ValueError('请求区间没有有效汇率')
 return dict(baseCurrency='USD',targetCurrency='CNY',unit='CNY-per-USD',sourceUrl=SERIES,publishedThrough=asof,basis='FRED-DEXCHUS-New-York-noon-current-vintage',history=rows,missingObservationDates=missing,requestedStart=start,requestedEnd=end,actualStart=rows[0]['date'],actualEnd=rows[-1]['date'],historicalPublicationVerified=False,currentVintageOnly=True,limitations=['publishedThrough为本次研究截止标签，不证明历史逐日首次披露时间','当前版本历史可能修订，不能当作当时可得样本','纽约中午买入汇率与证券收盘时刻不一致；并非实际换汇成交价','缺失不插值，实际末日可能早于请求末日'])
def collect(start,end,asof,directory):
 day(start);day(end);day(asof)
 if not start<end<=asof:raise ValueError('日期区间无效')
 out=Path(directory)
 if out.exists():raise FileExistsError('输出目录已存在')
 url='https://fred.stlouisfed.org/graph/fredgraph.csv?'+urlencode(dict(id='DEXCHUS',cosd=start,coed=end))
 raw=download(url,limit=8*1024*1024,timeout=20)
 r=parse(raw,start,end,asof);r.update(downloadUrl=url,rawSha256=hashlib.sha256(raw).hexdigest(),retrievedAt=dt.datetime.now(dt.timezone.utc).isoformat());out.mkdir(parents=True);(out/'DEXCHUS.csv').write_bytes(raw);(out/'result.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8');return r
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--start',required=True);p.add_argument('--end',required=True);p.add_argument('--as-of',required=True);p.add_argument('--out-dir',required=True);a=p.parse_args();collect(a.start,a.end,a.as_of,a.out_dir)
