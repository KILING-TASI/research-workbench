"""Comparable report-period financial summaries, not complete statements or valuation."""
import argparse,json,math,re
from pathlib import Path
from market_collect import financials
from fund_series_tools import day
from research_brief_html import render
FIELDS={'TOTALOPERATEREVE':'营业总收入','PARENTNETPROFIT':'归母净利润','ROEJQ':'加权ROE','EPSJB':'基本每股收益','BPS':'每股净资产','ZCFZL':'资产负债率'}
def compare(archives,asof):
 day(asof);seen=set();periods=[]
 for a in archives:
  if a['code'] in seen:raise ValueError('重复公司代码')
  seen.add(a['code']);available=set()
  for r in a['rows']:
   day(r['period']);day(r['publishedAt'])
   if r['publishedAt']<r['period']:raise ValueError('财务披露日期早于报告期，不能纳入比较')
   if r['raw'].get('SECURITY_CODE')!=a['code']:raise ValueError('财务证券身份不一致')
   if r['period']<=r['publishedAt']<=asof:available.add(r['period'])
  periods.append(available)
 common=sorted(set.intersection(*periods)) if periods else [];period=common[-1] if common else None;companies=[]
 for a in archives:
  records=[r for r in a['rows'] if r['period']==period and r['publishedAt']<=asof] if period else []
  fields={}
  for key,label in FIELDS.items():
   values=[]
   for r in records:
    value=r['raw'].get(key)
    if value is not None:
     try:valid=not isinstance(value,bool) and isinstance(value,(int,float)) and math.isfinite(value)
     except OverflowError:valid=False
     if not valid:raise ValueError('财务数值非法')
    values.append(dict(value=value,publishedAt=r['publishedAt'],currency=r['raw'].get('CURRENCY'),reportType=r['raw'].get('REPORT_TYPE')))
   fields[key]=dict(label=label,observations=values,conflict=len({x['value'] for x in values if x['value'] is not None})>1)
  companies.append(dict(code=a['code'],name=records[0]['raw'].get('SECURITY_NAME_ABBR') if records else None,fields=fields,sources=a['sources']))
 return dict(asOf=asof,commonPeriods=common,comparisonPeriod=period,companies=companies,status='available' if period else 'insufficient',limitations=['第三方主要指标摘要，不是完整三表或原文核验','同期间不同版本保留，不静默选取；累计期间不拆成单季度','数值保留供应商原单位，未独立核实单位和计算定义，不转换金额或跨币种排名','银行与非银行指标不可直接作经营质量排名；共同期末不保证会计口径完全相同'])
def markdown(r):
 lines=['# 上市公司财务对照','', '共同报告期：'+(r['comparisonPeriod'] or '未取得')+'；披露截止日'+r['asOf']+'。','数值为渠道原值，单位尚未独立核验，不作金额换算或优劣排序。']
 for c in r['companies']:
  lines+=['','## '+(c['name'] or c['code'])+' '+c['code']]
  for f in c['fields'].values():
   text='；'.join(str(x['value'])+'（披露'+x['publishedAt']+'，币种'+str(x['currency'])+'）' for x in f['observations']) or '缺失'
   lines.append(f['label']+'：'+text+('；版本数值冲突' if f['conflict'] else ''))
  lines+=['[财务渠道]('+url+')' for url in c['sources']]
 lines+=['','## 比较边界',*r['limitations']];return '\n'.join(lines)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--codes',nargs='+',required=True);p.add_argument('--start',required=True);p.add_argument('--as-of',required=True);p.add_argument('--out-dir',type=Path,required=True);a=p.parse_args()
 day(a.start);day(a.as_of)
 if a.start>a.as_of or not 2<=len(a.codes)<=20 or len(set(a.codes))!=len(a.codes) or any(not re.fullmatch(r'\d{6}',x) for x in a.codes):raise ValueError('需2至20个不重复沪深代码及有效区间')
 if a.out_dir.exists():raise FileExistsError('输出已存在')
 a.out_dir.mkdir(parents=True);archives=[];failures=[]
 for code in a.codes:
  try:
   rows,urls=financials(code,a.start,a.as_of);archive=dict(code=code,rows=rows,sources=urls);archives.append(archive);(a.out_dir/(code+'.json')).write_text(json.dumps(archive,ensure_ascii=False,indent=2),encoding='utf8')
  except Exception as exc:failures.append(dict(code=code,reason=str(exc)))
 r=compare(archives,a.as_of) if len(archives)>=2 else dict(asOf=a.as_of,comparisonPeriod=None,companies=[],status='insufficient',limitations=['不足两家有效公司，未执行对比'])
 r.update(requestedCodes=a.codes,failures=failures);text=markdown(r)
 if failures:text+='\n\n采集失败：'+str(failures)
 (a.out_dir/'result.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf8');(a.out_dir/'财务对比.md').write_text(text,encoding='utf8');(a.out_dir/'财务对比.html').write_text(render(text,title='财务对比'),encoding='utf8')
