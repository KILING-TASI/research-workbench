"""SEC reported US-GAAP facts, filed-date cutoff, no fabricated statement reconstruction."""
import argparse,json,datetime as dt,re,hashlib,urllib.request
from pathlib import Path
from research_brief_html import render
from fund_series_tools import day
from collection_validation import unique_pairs,reject_constant,finite_json_float
from urllib.parse import urlsplit
METRICS=['Assets','Liabilities','StockholdersEquity','RevenueFromContractWithCustomerExcludingAssessedTax','NetIncomeLoss','NetCashProvidedByUsedInOperatingActivities','NetCashProvidedByUsedInInvestingActivities','NetCashProvidedByUsedInFinancingActivities']

def filing_directory(cik,accession):
 if not isinstance(cik,str) or not re.fullmatch(r'\d{10}',cik) or not isinstance(accession,str) or not re.fullmatch(r'\d{10}-\d{2}-\d{6}',accession):raise ValueError('CIK或申报编号格式无效，不生成定位链接')
 return 'https://www.sec.gov/Archives/edgar/data/'+str(int(cik))+'/'+accession.replace('-','')+'/'

def period_groups(values):
 groups={}
 for x in values:groups.setdefault((x['start'],x['end']),[]).append(x)
 result=[]
 for (start,end),rows in sorted(groups.items(),key=lambda x:(x[0][1],x[0][0] or '')):
  result.append(dict(start=start,end=end,durationDays=(dt.date.fromisoformat(end)-dt.date.fromisoformat(start)).days+1 if start else None,observationCount=len(rows),accessionCount=len({x['accn'] for x in rows}),distinctValues=sorted({x['val'] for x in rows}),valueConflict=len({x['val'] for x in rows})>1,observations=rows))
 return result

def parse(payload,cik,asof):
 day(asof)
 if not isinstance(cik,str) or not re.fullmatch(r'\d{10}',cik) or not isinstance(payload,dict):raise ValueError('需SEC对象及10位CIK')
 if not isinstance(payload.get('entityName'),str) or not payload['entityName'].strip():raise ValueError('SEC主体名称无效')
 if str(payload.get('cik')).zfill(10)!=cik or not payload.get('entityName'):raise ValueError('SEC申报主体身份不一致')
 if not isinstance(payload.get('facts',{}),dict):raise ValueError('SEC facts结构无效')
 facts=payload.get('facts',{}).get('us-gaap',{});result={};gaps=[]
 if not isinstance(facts,dict):raise ValueError('SEC US-GAAP结构无效')
 for metric in METRICS:
  fact=facts.get(metric)
  if not fact:gaps.append(dict(metric=metric,reason='此US-GAAP标签未取得；不自动替换其他标签'));continue
  if not isinstance(fact,dict) or not isinstance(fact.get('units',{}),dict):raise ValueError('SEC标签单位结构无效')
  values=[];excluded=dict(nonUSD=0,missingDates=0,afterCutoff=0,unsupportedForm=0)
  for unit,rows in fact.get('units',{}).items():
   if not isinstance(rows,list) or any(not isinstance(x,dict) for x in rows):raise ValueError('SEC单位观测须为对象列表')
   if unit!='USD':excluded['nonUSD']+=len(rows);continue
   for row_index,x in enumerate(rows):
    filed=x.get('filed');end=x.get('end')
    if not filed or not end:excluded['missingDates']+=1;continue
    day(filed);day(end)
    if filed<end:raise ValueError('SEC申报日在财务期末之前，需核对期间')
    if filed>asof or end>asof:excluded['afterCutoff']+=1;continue
    if x.get('form') not in ('10-K','10-Q','10-K/A','10-Q/A'):excluded['unsupportedForm']+=1;continue
    if not x.get('accn'):raise ValueError('申报编号缺失')
    v=x.get('val')
    if isinstance(v,bool) or not isinstance(v,(int,float)):raise ValueError('财务数值无效')
    import math
    if not math.isfinite(v):raise ValueError('财务数值非有限')
    if metric not in ['Assets','Liabilities','StockholdersEquity'] and not x.get('start'):excluded['missingDates']+=1;continue
    if x.get('start'):
     day(x['start'])
     if x['start']>end:raise ValueError('财务期间倒置')
    item={k:x.get(k) for k in ['start','end','val','accn','fy','fp','form','filed','frame']};item.update(filingDirectoryUrl=filing_directory(cik,x['accn']),filingDocumentVerified=False,sourcePointer='/facts/us-gaap/'+metric+'/units/USD/'+str(row_index));values.append(item)
  result[metric]=dict(label=fact.get('label'),unit='USD',observations=values,periodGroups=period_groups(values),availableUnits=sorted(fact.get('units',{})),excludedObservations=excluded)
  if not values:gaps.append(dict(metric=metric,reason='截止日前未取得符合条件的USD申报观测；原始单位：'+('、'.join(sorted(fact.get('units',{}))) or '未提供')))
 return dict(type='sec-company-facts',cik=cik,entityName=payload['entityName'],asOf=asof,metrics=result,gaps=gaps,limitations=['按申报日筛选，不将期末日当披露日','保留同期间多次申报及修订，不静默选值；财年、季度及累计现金流不能直接横比','XBRL标签不是完整三张报表，缺少附注、维度及发行人自定义标签','CIK为申报主体，证券代码映射须另核验；不覆盖港股或所有美股会计准则','当前接口可能修订历史，不作为事前冻结回测数据'])

def select_period(r,start,end):
 day(start);day(end)
 if start>end or end>r['asOf']:raise ValueError('财务查询区间无效')
 selected={};excluded={}
 for key,m in r['metrics'].items():
  groups=[g for g in m['periodGroups'] if start<=g['end']<=end]
  selected[key]=[g for g in groups if not g['start'] or g['start']>=start]
  excluded[key]=[g for g in groups if g['start'] and g['start']<start]
 return dict(start=start,end=end,selectedPeriods=selected,crossBoundaryPeriods=excluded,basis='时点按期末；期间指标须完整起止落在查询区间；不推算单季')

def markdown(r):
 labels=dict(zip(METRICS,['资产','负债','股东权益','指定收入标签','净利润','经营现金流','投资现金流','筹资现金流']))
 lines=['# 美股申报财务资料','',r['entityName']+'；CIK '+r['cik']+'；截止日'+r['asOf']+'。','仅指定US-GAAP标签，不是完整三张报表。同一期间不同申报值保留待复核，未选择当前有效数值。','','| 财务标签 | 观测条数 | 期间数 | 数值不一致期间 | 期末范围 |','| --- | ---: | ---: | ---: | --- |']
 for key,m in r['metrics'].items():
  groups=m['periodGroups'];ends=[x['end'] for x in groups]
  lines.append('| '+labels[key]+' | '+str(len(m['observations']))+' | '+str(len(groups))+' | '+str(sum(x['valueConflict'] for x in groups))+' | '+(min(ends)+'至'+max(ends) if ends else '未取得')+' |')
 lines+=['','## 原始数据筛选范围','下列为排除原因统计，不能解释为公司不存在对应财务项目。',
  '| 财务标签 | 原始单位 | 非美元 | 缺日期 | 截止日外 | 非支持表单 |','| --- | --- | ---: | ---: | ---: | ---: |']
 for key,m in r['metrics'].items():
  if 'excludedObservations' not in m:continue
  e=m['excludedObservations'];lines.append('| '+labels[key]+' | '+('、'.join(m['availableUnits']) or '未提供')+' | '+' | '.join(str(e[k]) for k in ['nonUSD','missingDates','afterCutoff','unsupportedForm'])+' |')
 if r.get('periodSelection'):
  selection=r['periodSelection'];lines+=['','## 指定财务区间',selection['start']+'至'+selection['end']+'。'+selection['basis'],'| 标签 | 完整落入期间数 | 跨边界累计期间数 |','| --- | ---: | ---: |']
  for key in r['metrics']:lines.append('| '+labels[key]+' | '+str(len(selection['selectedPeriods'][key]))+' | '+str(len(selection['crossBoundaryPeriods'][key]))+' |')
 lines+=['','## 数值差异的申报定位','下列仅为按申报编号生成的目录定位，未下载申报正文；数值差异不等于报表错误。']
 for key,m in r['metrics'].items():
  for group in m['periodGroups']:
   if not group['valueConflict']:continue
   lines.append('- '+labels[key]+'：'+(group['start'] or '时点')+'至'+group['end'])
   seen=set()
   for x in group['observations']:
    token=(x['accn'],x['val'])
    if token in seen:continue
    seen.add(token);lines.append('  - '+str(x['val'])+' USD；申报日'+x['filed']+'；[申报目录]('+x['filingDirectoryUrl']+')')
 lines+=['','## 缺口']+['- '+labels[x['metric']]+'：'+x['reason'] for x in r['gaps']]
 lines+=['','季度、半年累计与年度期间按起止日区分；申报表单为10-Q或10-K并不自动决定该观测是单季或全年。','','[SEC资料来源]('+r.get('sourceUrl','https://data.sec.gov/')+')','']+['- '+x for x in r['limitations']]
 return '\n'.join(lines)

def run(cik,asof,out,user_agent,period_start=None,period_end=None):
 if not isinstance(cik,str) or not re.fullmatch(r'\d{10}',cik):raise ValueError('CIK须10位数字')
 day(asof)
 if bool(period_start)!=bool(period_end):raise ValueError('财务区间起止必须同时提供')
 if period_start:select_period(dict(asOf=asof,metrics={}),period_start,period_end)
 if not user_agent or '@' not in user_agent:raise ValueError('提供真实联系信息的SEC User-Agent，不自动编造')
 out=Path(out)
 if out.exists():raise FileExistsError('输出目录已存在')
 url=f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json';req=urllib.request.Request(url,headers={'User-Agent':user_agent,'Accept-Encoding':'identity'})
 with urllib.request.urlopen(req,timeout=30) as response:
  final=urlsplit(response.url)
  if final.scheme!='https' or final.hostname!='data.sec.gov' or final.username is not None or final.password is not None:raise ValueError('SEC响应来源发生跳转，未作为官方接口接受')
  raw=response.read(30*1024*1024+1)
 if len(raw)>30*1024*1024:raise ValueError('响应超限')
 r=parse(json.loads(raw,object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float),cik,asof)
 if period_start:r['periodSelection']=select_period(r,period_start,period_end)
 r.update(sourceUrl=url,sourceSha256=hashlib.sha256(raw).hexdigest(),retrievedAt=dt.datetime.now(dt.timezone.utc).isoformat());text=markdown(r);html=render(text);payload=json.dumps(r,ensure_ascii=False,indent=2,allow_nan=False)
 out.mkdir(parents=True);(out/'companyfacts.json').write_bytes(raw);(out/'result.json').write_text(payload,encoding='utf-8');(out/'财务资料简报.md').write_text(text,encoding='utf-8');(out/'财务资料简报.html').write_text(html,encoding='utf-8');return r
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--cik',required=True);p.add_argument('--as-of',required=True);p.add_argument('--user-agent',required=True);p.add_argument('--out-dir',required=True);p.add_argument('--period-start');p.add_argument('--period-end');a=p.parse_args();run(a.cik,a.as_of,a.out_dir,a.user_agent,a.period_start,a.period_end)
