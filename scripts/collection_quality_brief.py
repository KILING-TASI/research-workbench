"""Human-readable acquisition scope; no performance or completeness claims."""
import argparse,json,datetime as dt,re,hashlib,tempfile,os
from pathlib import Path
from research_brief_html import render,safe_url
from collection_validation import day,timestamp,positive,quote,report_contract,unique_pairs,reject_constant,finite_json_float
from atomic_json import write as atomic_write
from observation_calendar import assess as calendar_assess,note as calendar_note

def cell(value):
 return str(value).replace('\n',' ').replace('\r',' ').replace('|','\\|')

def display_gap(value):
 text=str(value).replace('\n',' ')
 for key,label in [('history:','行情：'),('financials:','财务：'),('announcements:','公告：')]:
  if text.startswith(key):text=label+text[len(key):]
 text=re.sub(r'\b(?:ValueError|TypeError|RuntimeError):\s*','',text)
 text=text.replace('TimeoutError','取数超时').replace('PermissionError','文件读写受限')
 return text

def brief(bundle):
 report_contract(bundle)
 cutoff=bundle.get('asOf')
 if cutoff is not None:day(cutoff)
 rows=bundle.get('rows')
 if not isinstance(rows,list) or not rows:raise ValueError('无可整理的取数结果')
 lines=['# 资料获取与质量说明','本报告说明实际取得的资料及缺口，不代表完整标的评价。','## 已取得资料','| 代码 | 名称 | 历史记录数 | 首条日期 | 末条日期 |','|---|---|---|---|---|']
 seen=set()
 for row in rows:
  if not isinstance(row,dict):raise ValueError('资料条目须为对象')
  code=row.get('code')
  if not isinstance(code,str) or not re.fullmatch(r'\d{6}',code) or (row.get('kind'),code) in seen:raise ValueError('代码无效或对象重复')
  seen.add((row.get('kind'),code));identity=row.get('identity') or {}
  if not isinstance(identity,dict):raise ValueError('名称身份结构无效')
  name=identity.get('name') or ''
  if not isinstance(name,str):raise ValueError('名称须为文字')
  components=row.get('components',{})
  if not isinstance(components,dict) or any(not isinstance(c,dict) for c in components.values()):raise ValueError('组件状态结构无效')
  if identity.get('code') not in [None,code]:raise ValueError('名称资料与证券代码身份冲突')
  history=row.get('history',[])
  if not isinstance(history,list):raise ValueError('历史资料结构无效')
  if any(not isinstance(h,dict) or 'date' not in h for h in history):raise ValueError('历史行缺少日期')
  dates=[h['date'] for h in history]
  for observed_day in dates:
   day(observed_day)
   if cutoff is not None and observed_day>cutoff:raise ValueError('报告包含晚于研究截止日的观测')
   requested_start=row.get('requestScope',{}).get('start')
   if requested_start is not None and observed_day<requested_start:raise ValueError('报告历史观测早于请求起始日')
  for h in history:
   value=h.get('nav',h.get('close'))
   if not positive(value):raise ValueError('报告历史观测含无效净值或价格')
  if dates!=sorted(set(dates)):raise ValueError('历史日期重复或乱序')
  lines.append('| '+' | '.join(cell(x) for x in [code,name,len(history),dates[0] if dates else '',dates[-1] if dates else ''])+' |')
 usable=sum(bool(r.get('history') or r.get('quote') or r.get('financials') or r.get('announcements')) for r in rows)
 lines.insert(2,'本次整理'+str(len(rows))+'个标的，其中'+str(usable)+'个取得可展示资料，'+str(len(rows)-usable)+'个尚未取得可展示资料。资料数量不代表覆盖完整。')
 lines+=['','记录数不是交易日完整度；名称缺失保持空白，不猜测产品身份。净值分红和未复权价格采用不同口径，本报告不混算收益。','## 来源与缺口']
 aligned=[row for row in rows if len(row.get('history',[]))>=2]
 excluded=[row['code'] for row in rows if len(row.get('history',[]))<2]
 if len(rows)>1:
  alignment=['','## 比较区间能否对齐']
  if len(aligned)>=2:
   shared=sorted(set.intersection(*(set(h['date'] for h in row['history']) for row in aligned)))
   if len(shared)>=2:
    alignment.append(str(len(aligned))+'个标的可对齐的共同观测日期为'+shared[0]+'至'+shared[-1]+'，共'+str(len(shared))+'个日期；不能用各自不同起止区间的指标直接排名。')
   else:alignment.append('可用于对齐的共同观测日期不足2个，目前不能进行同区间收益或相关性比较。')
  else:alignment.append('取得至少2条历史观测的标的不足2个，目前不能进行多标的同区间比较。')
  if excluded:alignment.append('以下标的缺少足够历史序列，未纳入日期对齐：'+ '、'.join(excluded)+'。未用单点报价或其他标的数据替代。')
  alignment.append('日期交集不代表收益口径一致或交易日完整；分红、复权、币种及基准仍需确认，未对缺日期插值或填零。')
  lines[-1:-1]=alignment
 for row in rows:
  lines+=['### '+row['code']]
  identity=row.get('identity') or {}
  if not identity.get('name'):
   lines.append('尚未取得可展示的证券名称；以下资料按代码归集，产品名称与品种仍需从正式资料确认。不能仅凭代码推定投资范围。')
  else:lines.append('名称：'+cell(identity['name'])+'。第三方返回名称不等于基金合同或发行文件身份核验。')
  components=row.get('components',{})
  if components:
   labels={'history':'历史行情','financials':'财务摘要','announcements':'公告元数据'}
   statuses={'success':'本次取得','cached':'读取已保存资料','cached-after-failure':'刷新失败，保留旧资料','failed':'未取得','unsupported':'此链路尚未支持'}
   lines+=['| 资料项目 | 本次状态 | 已保存记录数 |','|---|---|---|']
   for key,component in components.items():
    values=row.get(key,[])
    count=len(values) if isinstance(values,list) else '未确认'
    lines.append('| '+cell(labels.get(key,key))+' | '+cell(statuses.get(component.get('status'),'状态未确认'))+' | '+str(count)+' |')
   lines.append('以上状态只说明本次获取或缓存使用情况，不表示原文核验、完整覆盖或数据仍为最新。')
  scope=row.get('requestScope')
  if row.get('calendar') is not None:
   if not scope or not scope.get('start'):raise ValueError('日历核查需完整请求起止区间')
   market=identity.get('exchange') or ('SSE' if identity.get('exchangePrefix')=='sh' else 'SZSE' if identity.get('exchangePrefix')=='sz' else None)
   assessment=calendar_assess([h['date'] for h in row.get('history',[])],scope['start'],scope['asOf'],row['calendar'],market)
   lines.append('日期覆盖：'+calendar_note(assessment))
   if assessment.get('missingDates'):lines.append('缺少观测的日期：'+'、'.join(assessment['missingDates'])+'。')
  if scope:
   if scope.get('start') is not None:
    lines.append('本次请求历史区间：'+scope['start']+'至'+scope['asOf']+'。')
    observed=row.get('history',[])
    if observed and (observed[0]['date']>scope['start'] or observed[-1]['date']<scope['asOf']):
     lines.append('实际取得的观测首末日期未覆盖请求边界；可能涉及非交易日、成立时间或来源缺口，当前不能据此判定漏数。收益与风险只能基于实际可用区间，不能标成完整请求期间的表现。')
   else:lines.append('未指定历史起始日，本次保留来源取得的历史记录并按截止日筛选；不承诺从成立日起完整覆盖。')
  if row.get('quote') is not None:
   quote(row['quote'])
   if cutoff is not None and row['quote']['asOf']>cutoff:raise ValueError('报价晚于研究截止日')
   lines.append('已取得单点报价：'+str(row['quote']['price'])+'；所属日：'+row['quote']['asOf']+'。单点报价不能替代历史行情。')
   lines.append('报价单位和币种以原来源为准，本次未独立核验。')
  for key,label in [('financials','财务摘要'),('announcements','公告元数据')]:
   values=row.get(key,[])
   if not isinstance(values,list):raise ValueError(label+'结构无效')
   if values:lines.append('已取得'+str(len(values))+'条'+label+'；数量不代表全部披露覆盖或原文核验完成。')
  sources=[]
  if row.get('source'):sources.append((row['source'],row.get('retrievedAt')))
  for component in row.get('components',{}).values():sources.extend((url,component.get('retrievedAt')) for url in component.get('sources',[]))
  for i,(url,stamp) in enumerate(dict.fromkeys(sources),1):
   if not isinstance(url,str) or not url.startswith('https://') or re.search(r'\s|[()]',url) or not safe_url(url):raise ValueError('来源链接格式无效')
   display_time=timestamp(stamp).astimezone(dt.timezone.utc).isoformat() if stamp is not None else '未取得'
   lines+=['- [资料来源'+str(i)+']('+url+')；抓取时间（UTC）：'+display_time]
  if not sources:lines.append('未取得可展示的来源链接。')
  if row.get('collectionStatus')=='cached' or any(c.get('status')=='cached' for c in row.get('components',{}).values()):lines.append('本次读取已保存资料，未重新刷新；原抓取时间不等于最新数据日期。')
  failed_components=[name for name,c in row.get('components',{}).items() if c.get('status') in ['failed','cached-after-failure'] or c.get('error')]
  if row.get('errors') or failed_components:lines.append('本次取数存在失败或资料缺口，不能将已有记录认定为完整取数。')
  shown_gaps=set()
  def show_gap(value):
   text=display_gap(value)
   if text not in shown_gaps:lines.append('- '+text);shown_gaps.add(text)
  if isinstance(row.get('errors'),str):show_gap(row['errors'])
  elif isinstance(row.get('errors'),dict):
   for name,error in row['errors'].items():
    if error:show_gap(name+': '+error)
  for name in failed_components:
   component=row['components'][name]
   if component.get('error'):show_gap(name+': '+str(component['error']))
  for name,component in row.get('components',{}).items():
   if component.get('cacheError') and component.get('status')=='success':lines.append(name+'旧缓存未通过校验，本次已重新获取；旧缓存原因：'+str(component['cacheError']))
  if row.get('cacheError') and not row.get('errors'):lines.append('旧基金缓存未通过校验，本次已重新获取；旧缓存原因：'+str(row['cacheError']))
  if row.get('cacheRetained') or any(x.get('status')=='cached-after-failure' for x in row.get('components',{}).values()):lines.append('刷新未完成，已保留旧缓存；以上时间为原抓取时间。')
  for gap in row.get('gaps',[]):show_gap(gap)
  unhandled=[h for h in row.get('history',[]) if h.get('distribution') and (not isinstance(h['distribution'],str) or not re.fullmatch(r'分红：每份派现金(\d+(?:\.\d+)?)元',h['distribution']))]
  if unhandled:lines.append('发现'+str(len(unhandled))+'条不能按普通现金分红处理的事件（例如'+str(unhandled[0]['date'])+'）；当前基础收益入口会停止计算，需先核验拆分或其他事件口径。')
  if row.get('kind')=='fund' and len(row.get('history',[]))>=2 and row.get('source'):
   from fund_series_tools import quality
   diagnosis=quality({'code':row['code'],'asOf':cutoff or row['history'][-1]['date'],'sourceUrl':row['source'],'history':row['history'],'eventCoverage':'unknown'})
   lines.append('净值序列核查发现'+str(len(diagnosis['findings']))+'条跳变或连续不变线索，尚不能判定为错误；'+('日期覆盖另按上方声明日历核对，不代表分红与数值均正确。' if row.get('calendar') else '未提供适用交易日历，完整度留空。'))
 lines+=['','资料来源和保存成功不代表原文核验成功。未取得的数据不补造；本报告不构成投资建议。']
 return '\n'.join(lines)

def method_files():
    return [Path(__file__).with_name(name) for name in ['collection_quality_brief.py','research_brief_html.py','collection_validation.py','fund_series_tools.py','atomic_json.py','observation_calendar.py']]

def publish(input_path,out):
 input_path=Path(input_path);out=Path(out);blob=input_path.read_bytes();bundle=json.loads(blob.decode('utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float)
 text=brief(bundle);source_hash=hashlib.sha256(blob).hexdigest()
 if out.exists():raise ValueError('输出目录已存在，请使用新目录以保留旧报告')
 text+='\n\n本报告依据本次保存的资料编写；来源真实性与数据更新状态仍需分别核对。'
 markup=render(text,'资料获取与质量说明');out.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.TemporaryDirectory(prefix='.report-',dir=out.parent) as stage_name:
  stage=Path(stage_name);assert stage.resolve().parent==out.parent.resolve()
  (stage/'资料质量说明.md').write_text(text,encoding='utf-8');(stage/'资料质量说明.html').write_text(markup,encoding='utf-8')
  methods=method_files()
  manifest={'schemaVersion':1,'inputFile':input_path.name,'inputSha256':source_hash,'asOf':bundle.get('asOf'),'methodSha256':hashlib.sha256(b''.join(p.read_bytes() for p in methods)).hexdigest(),'methodFiles':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in methods},'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in stage.iterdir() if p.is_file()},'visualReview':'not-performed','sourceVerification':'not-verified'}
  atomic_write(stage/'report-manifest.json',manifest)
  if out.exists():raise ValueError('输出目录已存在，请使用新目录')
  os.rename(stage,out)
 return manifest

def main():
 p=argparse.ArgumentParser();p.add_argument('input');p.add_argument('--out-dir',required=True);a=p.parse_args();publish(a.input,a.out_dir)

if __name__=='__main__':main()
