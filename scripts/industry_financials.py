"""Explicit scope quarter calculations and grouped financial research."""
import argparse,datetime as dt,hashlib,json,math,statistics
from decimal import Decimal
from pathlib import Path
from research_brief_html import render
from collection_validation import unique_pairs,reject_constant,finite_json_float
FIELDS={'revenue':('income','OPERATE_INCOME','营业收入',True),'cost':('income','OPERATE_COST','营业成本',True),'profit':('income','NETPROFIT','净利润',True),'parentProfit':('income','PARENT_NETPROFIT','归母净利润',True),'salesExpense':('income','SALE_EXPENSE','销售费用',True),'managementExpense':('income','MANAGE_EXPENSE','管理费用',True),'researchExpense':('income','RESEARCH_EXPENSE','研发费用',True),'financeExpense':('income','FINANCE_EXPENSE','财务费用',True),'receivables':('balance','ACCOUNTS_RECE','应收账款',False),'inventory':('balance','INVENTORY','存货',False),'assets':('balance','TOTAL_ASSETS','总资产',False),'liabilities':('balance','TOTAL_LIABILITIES','总负债',False),'operatingCash':('cashflow','NETCASH_OPERATE','经营现金流净额',True),'capex':('cashflow','CONSTRUCT_LONG_ASSET','购建长期资产支付现金',True)}
FINANCIAL_INAPPLICABLE_RATIOS={'grossMargin','expenseRatio','cashProfit','capexIntensity'}
RATIO_LABELS={'grossMargin':'毛利率','netMargin':'净利润率','cashProfit':'经营现金流与净利润之比','capexIntensity':'购建长期资产现金支出占收入比','leverage':'资产负债率','expenseRatio':'四项费用占收入比'}

def metadata_unit_warnings(meta):
 if any(token in meta['unit'] for token in ['待','未确认','未知']):
  return ['金额单位声明尚未明确；字段数值匹配不能替代完整单位口径确认，报告不可视为无缺口。']
 return []

def applicability_notes(company):
 if company['metadata'].get('sectorType')!='financial':return []
 return ['指标适用性：毛利率、四项费用占收入比、经营现金流与净利润之比及购建长期资产现金支出占收入比不套用普通企业评价规则；这些比率未计算属于不适用，不是取数失败。',
 '数据缺口：原始科目未取得仍逐项保留缺失，不能据此认定该科目为零、公司未披露或业务不存在；也不能用名称相近的金融科目直接替代。',
 '解释限制：净利润率不等于银行净息差，资产负债率不等于资本充足率；本报告的通用财务比率不能替代金融企业专属风险评价。']
def numeric(v):
 return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)
def previous(period):
 d=dt.date.fromisoformat(period);ends={3:(12,31,-1),6:(3,31,0),9:(6,30,0),12:(9,30,0)}
 if (d.month,d.day) not in [(3,31),(6,30),(9,30),(12,31)]:raise ValueError('仅支持自然年季度末，不猜财政年度')
 m,day,offset=ends[d.month];return dt.date(d.year+offset,m,day).isoformat()
def observation(archive,kind,period,field):
 rows=[r for r in archive['tables'][kind]['rows'] if r['period']==period and r['publishedAt']<=archive['asOf']]
 if not rows:return None,'报告缺期',[]
 identities={(r['currency'],r['raw'].get('SECUCODE'),r['raw'].get('ORG_TYPE')) for r in rows}
 values={r['raw'].get(field) for r in rows}
 refs=[dict(table=kind,period=period,publishedAt=r['publishedAt'],field=field) for r in rows]
 if len(identities)!=1 or len(values)!=1:return None,'同期版本或身份口径冲突',refs
 v=rows[0]['raw'].get(field)
 return (v,None,refs) if numeric(v) else (None,'字段缺失或非有限数值',refs)
def value(archive,key,period,quarter=True):
 kind,field,label,flow=FIELDS[key];current,reason,refs=observation(archive,kind,period,field)
 previous(period)
 if reason:return dict(value=None,reason=reason,inputs=refs)
 if not flow or not quarter or period[5:7]=='03':return dict(value=current,reason=None,inputs=refs)
 prior=previous(period);old,reason,oldrefs=observation(archive,kind,prior,field)
 if reason:return dict(value=None,reason='累计转单季需要上期：'+reason,inputs=refs+oldrefs)
 currencies={r['currency'] for r in archive['tables'][kind]['rows'] if r['period'] in [period,prior] and r['publishedAt']<=archive['asOf']}
 if len(currencies)!=1 or None in currencies:return dict(value=None,reason='币种不一致或缺失',inputs=refs+oldrefs)
 # Subtract the disclosed decimal amounts before converting for JSON metrics.
 # Binary-float subtraction can invent sub-cent residuals in later bridges.
 result=float(Decimal(str(current))-Decimal(str(old)))
 if not math.isfinite(result):return dict(value=None,reason='差分非有限数值',inputs=refs+oldrefs)
 if key=='capex' and (abs(current)<abs(old) or current*old<0):
  return dict(value=None,reason='累计购建资产付款绝对额下降或符号反转；需核对重分类、退款和调整，不能直接还原单季实际付款',inputs=refs+oldrefs,cumulativeDifference=result)
 return dict(value=result,reason=None,inputs=refs+oldrefs)
def change(now,old,metric=None):
 if now is None or old is None:return dict(value=None,reason='比较期数据缺失')
 if old<=0:
  label='基数为零' if old==0 else '负基数'
  if old<0 and now>0:label='转盈'
  elif old>0 and now<0:label='转亏'
  elif old<0 and now<0:label='亏损收窄' if now>old else '亏损扩大' if now<old else '亏损持平'
  if metric=='operatingCash':
   label='由净流出转净流入' if old<0 and now>0 else '净流出收窄' if old<0 and now<0 and now>old else '净流出扩大' if old<0 and now<0 and now<old else '净流出持平' if old<0 and now==old else label
  elif metric is not None and metric not in ['profit','parentProfit']:
   label='由负转正' if old<0 and now>0 else '负值绝对值减少' if old<0 and now<0 and now>old else '负值绝对值增加' if old<0 and now<0 and now<old else '负值持平' if old<0 and now==old else label
  return dict(value=None,reason=label)
 v=now/old-1
 transition='由净流入转净流出' if metric=='operatingCash' else '由正转负' if metric is not None and metric not in ['profit','parentProfit'] else '转亏'
 return dict(value=v if math.isfinite(v) else None,reason=(transition if now<0 else None) if math.isfinite(v) else '变化率非有限数值')
def ratio(a,b):
 v=a/b if a is not None and b is not None and b>0 else None
 return v if numeric(v) else None

def analyze_company(archive,meta,period):
 if meta.get('scope') not in ['consolidated','parent'] or not meta.get('currency') or not meta.get('unit') or not meta.get('classificationVersion'):raise ValueError('需明确报表范围、币种、单位和分组版本')
 if archive['asOf']<period:raise ValueError('研究报告期超过截止日')
 for table in archive['tables'].values():
  for r in table['rows']:
   if r['raw'].get('SECURITY_CODE')!=archive['code']:raise ValueError('公司身份不匹配')
   if r['currency']!=meta['currency']:raise ValueError('声明币种与资料不符')
   dt.date.fromisoformat(r['period']);dt.date.fromisoformat(r['publishedAt'])
   if r['period']>r['publishedAt']:raise ValueError('报告期晚于披露日')
 observed_types={str(r['raw'].get('ORG_TYPE','')) for table in archive['tables'].values() for r in table['rows'] if r['publishedAt']<=archive['asOf']}
 detected_financial=any(any(term in t for term in ['银行','保险','证券','金融']) for t in observed_types)
 if detected_financial and meta.get('sectorType')!='financial':raise ValueError('数据源标记为金融企业，不能使用普通企业分组及比率；请明确金融企业口径')
 yearago=str(int(period[:4])-1)+period[4:];prior=previous(period);metrics={}
 for key in FIELDS:
  now=value(archive,key,period);y=value(archive,key,yearago);q=value(archive,key,prior)
  metrics[key]=dict(label=FIELDS[key][2],current=now,yoy=change(now['value'],y['value'],key),qoq=change(now['value'],q['value'],key),comparators=dict(yoy=y,qoq=q))
 v={k:x['current']['value'] for k,x in metrics.items()}
 financial=meta.get('sectorType')=='financial'
 ratios=dict(netMargin=ratio(v['profit'],v['revenue']),cashProfit=None if financial else ratio(v['operatingCash'],v['profit']),capexIntensity=None if financial else ratio(v['capex'],v['revenue']),leverage=ratio(v['liabilities'],v['assets']))
 ratios['grossMargin']=None if financial else ratio(v['revenue']-v['cost'] if v['revenue'] is not None and v['cost'] is not None else None,v['revenue'])
 expenses=[v[k] for k in ['salesExpense','managementExpense','researchExpense','financeExpense']]
 ratios['expenseRatio']=None if financial or any(x is None for x in expenses) else ratio(sum(expenses),v['revenue'])
 signals=[]
 revenue=metrics['revenue']['yoy']['value'];receivables=metrics['receivables']['yoy']['value']
 if not financial and revenue is not None and receivables is not None and receivables>revenue:signals.append('应收账款同比增速高于营业收入；需要结合账龄和结算条款核查回款压力。')
 if not financial and v['profit'] is not None and v['operatingCash'] is not None and v['profit']>0 and v['operatingCash']<0:signals.append('本季度盈利但经营现金流为负；需要核查营运资金占用及季节性。')
 if financial:signals.append('金融企业未套用普通企业毛利率、费用率、现金利润比及营运资金规则；信用质量、资本充足率等专属指标尚需另行研究。')
 if not signals:signals.append('已计算项目未触发这两项规则；不代表不存在其他财务风险。')
 missing=[x['label']+'：'+x['current']['reason'] for x in metrics.values() if x['current']['reason']]+metadata_unit_warnings(meta)
 return dict(code=archive['code'],period=period,metadata=meta,metrics=metrics,ratios=ratios,signals=signals,gaps=missing,sourceUrls={k:t['sources'] for k,t in archive['tables'].items()},limitations=['单季利润/现金流按当年累计差分，资产负债为期末存量，存量环比不是季度新增额','报告范围及单位为调用者声明，未经原文核验时不能称公告已确认','会计政策变更、追溯重述与合并范围变化需额外核验，机械差分不能消除这些差异','现金利润比仅为本季度经营现金流除净利润，不等于现金收入或盈利真实性证明'])

def summarize_companies(companies):
 groups={}
 for c in companies:
  m=c['metadata'];key=tuple(m.get(k) for k in ['group','classificationVersion','sectorType','scope','currency','unit'])
  groups.setdefault(key,[]).append(c)
 summaries=[]
 for key,members in groups.items():
  fields={}
  for metric in ['grossMargin','netMargin','cashProfit','capexIntensity','leverage','expenseRatio']:
   valid=[c['ratios'][metric] for c in members if numeric(c['ratios'][metric])]
   inapplicable=sum(c['metadata'].get('sectorType')=='financial' and metric in FINANCIAL_INAPPLICABLE_RATIOS for c in members)
   fields[metric]=dict(median=statistics.median(valid) if valid else None,validCount=len(valid),missingCount=len(members)-len(valid)-inapplicable,notApplicableCount=inapplicable)
  changes={}
  for metric in ['revenue','parentProfit','receivables','inventory','operatingCash']:
   changes[metric]={}
   for kind in ['yoy','qoq']:
    valid=[c['metrics'][metric][kind]['value'] for c in members if numeric(c['metrics'][metric][kind]['value'])]
    changes[metric][kind]=dict(median=statistics.median(valid) if valid else None,validCount=len(valid),missingCount=len(members)-len(valid))
  summaries.append(dict(changes=changes,group=key[0],classificationVersion=key[1],sectorType=key[2],scope=key[3],currency=key[4],unit=key[5],sampleSize=len(members),ratios=fields))
 return summaries

def run(spec,out):
 period=spec['period'];previous(period);out=Path(out)
 if out.exists():raise FileExistsError('输出目录已存在')
 companies=[];failures=[];seen=set()
 for item in spec['companies']:
  a=None
  try:
   path=Path(item['archive']);raw=path.read_bytes();a=json.loads(raw,object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float)
  except (OSError,ValueError,TypeError,KeyError) as exc:
   failures.append(dict(code=item.get('code') or '主体未解析',archive=item.get('archive'),reason='资料读取失败：'+str(exc)));continue
  if not isinstance(a,dict) or not isinstance(a.get('code'),str) or not a['code']:
   failures.append(dict(code=item.get('code') or '主体未解析',archive=item.get('archive'),reason='资料主体结构无效'));continue
  if a['code'] in seen:raise ValueError('重复公司')
  seen.add(a['code'])
  try:
   c=analyze_company(a,item['metadata'],period);c['archiveSha256']=hashlib.sha256(raw).hexdigest();companies.append(c)
  except (ValueError,KeyError,TypeError) as exc:failures.append(dict(code=a['code'],reason=str(exc)))
 summaries=summarize_companies(companies)
 result=dict(period=period,companies=companies,failures=failures,groups=summaries,coverage=dict(requested=len(spec['companies']),analyzed=len(companies),currentRevenueAvailable=sum(c['metrics']['revenue']['current']['value'] is not None for c in companies)),limitations=['指定样本池，不冒称完整行业股票池','分组中位数描述已有样本，不代表行业整体判断；每项列有效样本数','未自动获取公告正文，经营原因和未来展望不由数字推断','规则信号非财务造假结论，不输出质量评分或买卖建议'])
 out.mkdir(parents=True);(out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8');text=markdown(result);(out/'财务研究.md').write_text(text,encoding='utf8');(out/'财务研究.html').write_text(render(text,title='公司与行业财务研究'),encoding='utf8');return result

def company_observation(c):
 if c['metadata'].get('sectorType')=='financial':
  return '本样本属于金融企业，通用收入利润及账面比率不能替代净息差、信用质量和资本约束评价；以下仅为已取得科目的财务对照。'
 metrics=c['metrics'];parts=[]
 revenue=metrics['revenue']['yoy']['value'];profit=metrics['parentProfit']['yoy']['value'];cash=metrics['operatingCash']['current']['value']
 if revenue is not None and profit is not None:
  parts.append('本季度收入同比'+format(revenue*100,'.2f')+'%，归母利润同比'+format(profit*100,'.2f')+'%。')
  if revenue>0 and profit<revenue:parts.append('收入扩张尚未等幅转成归母利润增长，研究重点应落在毛利、费用和其他损益如何影响利润兑现。')
  elif revenue<0 and profit<0:parts.append('收入与归母利润均较同期下降，需要区分需求、产品结构与成本费用的影响，不能仅靠同比降幅确定原因。')
  elif profit>revenue:parts.append('归母利润增速高于收入，但不因此认定盈利质量改善；仍需拆开毛利、费用与非经常性因素。')
 else:parts.append('收入或归母利润的同比口径不完整，尚不能判断两者的增长是否同步。')
 if cash is not None and cash<0:parts.append('本季度经营现金净流出，现金兑现需要结合营运资金与季节性检查；不直接认定财务危机。')
 elif cash is None:parts.append('经营现金数据缺失，利润的现金兑现尚不能评价。')
 elif cash==0:parts.append('本季度经营现金净额为零，不等于没有现金收支，也不支持净流入判断。')
 else:parts.append('本季度经营现金净流入，但不能仅凭正值确认回款质量或未来持续性。')
 parts.append('以上是声明口径下的财务观察，原文、重述及实际经营原因仍须另核，不构成完整公司评价。')
 return ''.join(parts)

def markdown(r):
 def pct(x):return '缺失' if x is None else format(x*100,'.2f')+'%'
 lines=['# 公司与行业财务研究','',r['period']+'。本次指定'+str(r['coverage']['requested'])+'家公司，完成'+str(r['coverage']['analyzed'])+'家计算。金额使用声明单位，未核验声明不等于原文确认。']
 for c in r['companies']:
  m=c['metadata'];lines+=['','## '+c['code']+' '+m.get('name',''),'本期利润和现金流使用单季度口径，资产负债项目为期末值。币种'+m['currency']+'，单位'+m['unit']+'，范围'+m['scope']+'。','',company_observation(c),'','| 指标 | 本期原单位 | 同比 | 环比 |','|---|---:|---|---|']
  for x in c['metrics'].values():
   now=x['current'];lines.append('| '+x['label']+' | '+(str(now['value']) if now['value'] is not None else now['reason'])+' | '+(pct(x['yoy']['value']) if x['yoy']['value'] is not None else x['yoy']['reason'])+' | '+(pct(x['qoq']['value']) if x['qoq']['value'] is not None else x['qoq']['reason'])+' |')
  lines+=['',*applicability_notes(c),*c['signals'],'净利润率为'+pct(c['ratios']['netMargin'])+'，资产负债率为'+pct(c['ratios']['leverage'])+'。上述比率描述本期资料，不解释未经核验的经营原因。',*c['limitations']]
  for urls in c['sourceUrls'].values():
   if urls:lines.append('[财务资料渠道]('+urls[0]+')')
 lines+=['','## 分组统计']
 for g in r['groups']:
  lines.append(g['group']+'：样本'+str(g['sampleSize'])+'家；分类版本'+g['classificationVersion']+'。')
  for k,v in g['ratios'].items():
   label='不适用' if v.get('notApplicableCount')==g['sampleSize'] else '资料不足'
   display=(format(v['median'],'.2f')+'倍' if k=='cashProfit' else pct(v['median'])) if v['median'] is not None else label
   lines.append(RATIO_LABELS[k]+'中位数 '+display+'；有效'+str(v['validCount'])+'家，缺失'+str(v['missingCount'])+'家，不适用'+str(v.get('notApplicableCount',0))+'家。')
  for k,changes in g['changes'].items():
   for kind,v in changes.items():lines.append(FIELDS[k][2]+('同比' if kind=='yoy' else '环比')+'中位数 '+pct(v['median'])+'；有效'+str(v['validCount'])+'家，缺失'+str(v['missingCount'])+'家。')
 lines+=['','## 资料缺口与边界',*r['limitations']]
 for f in r['failures']:lines.append(f['code']+'：'+f['reason'])
 return '\n'.join(lines)
def period_comparison(spec,out):
 before=spec['beforePeriod'];after=spec['period'];previous(before);previous(after)
 if before>=after:raise ValueError('对比报告期须递增')
 if not 1<=len(spec['companies'])<=20:raise ValueError('跨期对照需1至20家公司')
 rows=[];seen=set()
 for item in spec['companies']:
  raw=Path(item['archive']).read_bytes();archive=json.loads(raw);code=archive['code']
  if code in seen:raise ValueError('重复公司')
  seen.add(code);a=analyze_company(archive,item['metadata'],before);b=analyze_company(archive,item['metadata'],after)
  metrics=[]
  for key,field in FIELDS.items():
   av=a['metrics'][key]['current'];bv=b['metrics'][key]['current']
   metrics.append(dict(metric=key,label=field[2],basis='单季' if field[3] else '期末',before=av,after=bv,difference=bv['value']-av['value'] if av['value'] is not None and bv['value'] is not None else None,status='数值差异，非因果归因' if av['value'] is not None and bv['value'] is not None else '缺值不计算差异'))
  rows.append(dict(code=code,metadata=item['metadata'],archiveSha256=hashlib.sha256(raw).hexdigest(),archiveAsOf=archive['asOf'],metrics=metrics))
 result=dict(beforePeriod=before,period=after,companies=rows,limitations=['使用同一已获取档案中的历史数据，不代表当时可获得版本','单位与合并范围按输入声明，未自动完成两期原文及重述口径核验','单季利润与现金流按累计差分；期末资产负债按存量比较','数值差异可能受季节性、重述和报表范围变化影响，不直接认定经营改善'])
 lines=['# 公司跨期财务对照','',before+'与'+after+'。以下按同一资料档案计算，先阅读口径限制，再解释变化。',*result['limitations']]
 for row in rows:
  lines+=['','## '+row['code']+' '+row['metadata'].get('name',''),'金额单位：'+row['metadata']['unit'],'','| 指标 | 口径 | 前期 | 后期 | 差额 |','|---|---|---:|---:|---:|']
  for m in row['metrics']:
   display=lambda v:'缺失' if v is None else str(v)
   lines.append('| '+m['label']+' | '+m['basis']+' | '+display(m['before']['value'])+' | '+display(m['after']['value'])+' | '+display(m['difference'])+' |')
   if m['difference'] is None:lines.append(m['label']+'：'+str(m['before'].get('reason') or m['after'].get('reason'))+'；不以零替代。')
 out=Path(out);out.mkdir(parents=True,exist_ok=False);text='\n'.join(lines)
 (out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8');(out/'跨期财务对照.md').write_text(text,encoding='utf8');(out/'跨期财务对照.html').write_text(render(text,title='公司跨期财务对照'),encoding='utf8');return result

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--out-dir',type=Path,required=True);p.add_argument('--compare-periods',action='store_true');a=p.parse_args();(period_comparison if a.compare_periods else run)(json.loads(a.input.read_text(encoding='utf8')),a.out_dir)
