"""Same-date closing price/unit NAV comparison; never intraday IOPV."""
import argparse,datetime as dt,hashlib,json,math,re
from decimal import Decimal
from pathlib import Path
from portable_collect import named
from research_brief_html import render
from collection_validation import day,unique_pairs,reject_constant

def calculate(code,prices,text,start,end):
 if not isinstance(code,str) or not re.fullmatch(r"\d{6}",code) or str(named(text,'fS_code'))!=code:raise ValueError('净值证券身份不匹配')
 if day(start)>day(end):raise ValueError('日期范围无效')
 if not isinstance(prices,list) or any(not isinstance(p,dict) for p in prices):raise ValueError('价格须为对象数组')
 nav={};events=[]
 history=named(text,'Data_netWorthTrend')
 if not isinstance(history,list) or any(not isinstance(h,dict) for h in history):raise ValueError('单位净值须为对象数组')
 for h in history:
  if isinstance(h.get('x'),bool) or not isinstance(h.get('x'),(int,float)) or not math.isfinite(h['x']):raise ValueError('净值时间戳无效')
  date=dt.datetime.fromtimestamp(h['x']/1000,dt.timezone(dt.timedelta(hours=8))).date().isoformat()
  value=h['y']
  if isinstance(value,bool) or not isinstance(value,(float,int)) or not math.isfinite(value) or value<=0:raise ValueError('单位净值非法')
  if date in nav:raise ValueError('净值日期重复')
  nav[date]=Decimal(str(value))
  if start<=date<=end and h.get('unitMoney'):events.append(dict(date=date,text=h['unitMoney']))
 dates=[];rows=[];missing=[]
 for p in prices:
  date=day(p.get('date')).isoformat();dates.append(date);close=p.get('close')
  if isinstance(close,bool) or not isinstance(close,(float,int)) or not math.isfinite(close) or close<=0:raise ValueError('收盘价非法')
  if not start<=date<=end:continue
  if date not in nav:missing.append(date);continue
  premium=float((Decimal(str(close))/nav[date]-1)*100)
  if not math.isfinite(premium):raise ValueError('收盘净值偏离计算溢出')
  rows.append(dict(date=date,close=close,unitNAV=float(nav[date]),closingPremiumPct=premium))
 if dates!=sorted(set(dates)):raise ValueError('价格日期重复或乱序')
 return dict(code=code,name=named(text,'fS_name'),requestedStart=start,requestedEnd=end,history=rows,missingNavDates=missing,eventRecords=events,eventCoverage='provider-events-unverified',status='available' if rows else 'missing',limitations=['仅同日收盘价与单位净值；非盘中IOPV或可交易价差','所属日期不证明历史披露时点；第三方资料未作官方核验','事件记录未核验完整，不据此认定无分红拆分或完整总收益'])

def run(spec,out):
 out=Path(out)
 if out.exists():raise FileExistsError('输出目录已存在')
 if not isinstance(spec,dict):raise ValueError('ETF收盘净值请求须为对象')
 price_path=Path(spec['priceArchive']);nav_path=Path(spec['navFile']);raw=price_path.read_bytes();nav_raw=nav_path.read_bytes();text=nav_raw.decode('utf-8-sig');archive=json.loads(raw,object_pairs_hook=unique_pairs,parse_constant=reject_constant)
 if not isinstance(archive,dict) or not isinstance(archive.get('results'),list) or any(not isinstance(r,dict) for r in archive['results']):raise ValueError('价格档案须含结果对象数组')
 candidates=[r for r in archive['results'] if r['code']==spec['code']]
 if len(candidates)!=1 or not isinstance(candidates[0].get('history'),list):raise ValueError('价格档案需唯一目标证券历史')
 result=calculate(spec['code'],candidates[0]['history'],text,spec['start'],spec['end'])
 result['sourceFiles']=[dict(role='price-archive',path=str(price_path.resolve()),sha256=hashlib.sha256(raw).hexdigest()),dict(role='nav-response',path=str(nav_path.resolve()),sha256=hashlib.sha256(nav_raw).hexdigest())]
 result['priceSources']=candidates[0].get('sources',[]);result['navSource']='https://fund.eastmoney.com/pingzhongdata/'+spec['code']+'.js'
 lines=['# ETF收盘净值对照','',str(result['name'])+'（'+spec['code']+'）。本次共同日期'+str(len(result['history']))+'个，缺少单位净值的价格日期'+str(len(result['missingNavDates']))+'个。']
 if result['history']:
  latest=result['history'][-1];lines.append('实际截止'+latest['date']+'，收盘价'+str(latest['close'])+'，单位净值'+str(latest['unitNAV'])+'，计算偏离'+format(latest['closingPremiumPct'],'.3f')+'%。')
 else:lines.append('未取得共同日期，不输出折溢价。')
 lines+=['','## 口径与缺口',*result['limitations']]
 out.mkdir(parents=True);(out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8');(out/'收盘净值对照.html').write_text(render('\n'.join(lines),title='ETF收盘净值对照'),'utf8');return result

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--out-dir',type=Path,required=True);a=p.parse_args();run(json.loads(a.input.read_text('utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant),a.out_dir)
