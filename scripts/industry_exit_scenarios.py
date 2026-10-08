"""Declared-scope supply balances, concentration bounds and dated exit cash scenarios."""
import argparse,datetime as dt,hashlib,json,math
from pathlib import Path
from company_scenarios import value,context,date_value,load_json
from fund_dca import xirr
from research_brief_html import render

def industry_context(s):
 date_value(s['asOf'])
 if not all(isinstance(s.get(k),str) and s[k].strip() for k in ['name','scope','unit']):raise ValueError('需研究主题、市场范围和数量单位')
 for binding in s.get('sourceFiles',[]):
  if hashlib.sha256(Path(binding['path']).read_bytes()).hexdigest()!=binding['sha256']:raise ValueError('输入来源文件哈希变化')
 return s['asOf']
def field(row,key,s):
 x=row.get(key)
 if x is None:return None
 if x.get('unit',s['unit'])!=s['unit']:raise ValueError('数量或金额单位不同')
 return value(x,s['asOf'])

def supply(s):
 asof=industry_context(s);rows=s['periods']
 if not 1<=len(rows)<=20:raise ValueError('需1至20期')
 out=[];last=None
 for row in rows:
  start=dt.date.fromisoformat(date_value(row['start']));end=dt.date.fromisoformat(date_value(row['end']))
  if start>end or (last and start<=last):raise ValueError('期间倒置、重叠或乱序')
  if row.get('scope',s['scope'])!=s['scope']:raise ValueError('供需市场口径不一致')
  for key in ['production','imports','exports','demand','closingInventory','capacity']:
   if end.isoformat()>asof and row.get(key) is not None and row[key]['basis']!='assumption':raise ValueError('未来期流量和期末值须明确假设')
  v={key:field(row,key,s) for key in ['openingInventory','production','imports','exports','demand','closingInventory','capacity']}
  if any(x is not None and x<0 for x in v.values()):raise ValueError('供需输入不得为负')
  if start.isoformat()>asof and row.get('openingInventory') is not None and row['openingInventory']['basis']!='assumption':raise ValueError('未来期初库存须明确假设')
  known=all(v[k] is not None for k in ['openingInventory','production','imports','exports']);available=sum(v[k] for k in ['openingInventory','production','imports'])-v['exports'] if known else None
  projected=available-v['demand'] if available is not None and v['demand'] is not None else None
  implied=available-v['closingInventory'] if available is not None and v['closingInventory'] is not None else None
  diff=projected-v['closingInventory'] if projected is not None and v['closingInventory'] is not None else None
  continuity=None
  if out and (start-dt.date.fromisoformat(out[-1]['end'])).days==1 and v['openingInventory'] is not None and out[-1]['inputs']['closingInventory'] is not None:continuity=v['openingInventory']-out[-1]['inputs']['closingInventory']
  utilization=v['production']/v['capacity'] if v['production'] is not None and v['capacity'] is not None and v['capacity']>0 else None
  alerts=[]
  if projected is not None and projected<0:alerts.append('给定需求超出可供量；负值是情景缺口，不是实际负库存')
  if implied is not None and implied<0:alerts.append('推算消耗为负，需要复核进出口、库存和范围')
  if diff is not None and abs(diff)>1e-9:alerts.append('供需存量未完全勾稽；差额保留，不自动配平')
  if utilization is not None and utilization>1:alerts.append('产量超过给定产能；产能期间、扩产或单位需复核')
  if continuity is not None and abs(continuity)>1e-9:alerts.append('相邻期库存口径存在差额')
  out.append(dict(start=start.isoformat(),end=end.isoformat(),inputs=v,availableSupply=available,projectedClosingInventory=projected,impliedDemandFromStockBalance=implied,balanceDifference=diff,inventoryContinuityDifference=continuity,capacityUtilization=utilization,supplyDeficit=max(-projected,0) if projected is not None else None,gaps=[k for k in ['openingInventory','production','imports','exports','demand'] if v[k] is None],alerts=alerts));last=end
 return dict(type='declared-scope-supply-balance',periods=out,formulas=['可供量=期初库存+产量+进口-出口','情景期末库存=可供量-需求','库存平衡推算消耗=可供量-披露期末库存'],limitations=['产能与产量必须覆盖同期间、同地区和同产品范围；模型不自动核实分类','未披露的进出口或库存不填零；闭合失败不自动配平','库存推算消耗不是公开披露需求，更不是终端需求证明','未来各期数量需显式假设，模型不生成三年供需预测'])

def concentration(s):
 asof=industry_context(s);date_value(s['period']);firms=s['firms'];total=field(s,'marketTotal',s)
 if total is None or total<=0 or not 1<=len(firms)<=200 or len({r['id'] for r in firms})!=len(firms):raise ValueError('需正市场总量与1至200家不重复主体')
 if not isinstance(s.get('universeComplete'),bool):raise ValueError('需声明主体范围是否完整')
 out=[]
 for row in firms:
  if row.get('scope',s['scope'])!=s['scope'] or row.get('period',s['period'])!=s['period']:raise ValueError('主体范围或期间不一致')
  if s['period']>asof and row['volume']['basis']!='assumption':raise ValueError('未来份额须明确假设')
  vol=field(row,'volume',s)
  if vol is None or vol<0:raise ValueError('主体数量缺失或为负')
  out.append(dict(id=row['id'],name=row['name'],volume=vol,share=vol/total))
 if s['period']>asof and s['marketTotal']['basis']!='assumption':raise ValueError('未来市场总量须明确假设')
 coverage=sum(r['share'] for r in out)
 if coverage>1+1e-10:raise ValueError('主体数量合计超过市场总量')
 if s['universeComplete'] and abs(coverage-1)>1e-10:raise ValueError('声明全量但合计不等于市场总量；不能归一配平')
 remainder=max(0,1-coverage);ranked=sorted(out,key=lambda r:-r['share']);metrics={}
 for k in [3,5]:
  lower=sum(r['share'] for r in ranked[:k]);metrics['CR'+str(k)]=dict(lower=lower,upper=min(1,lower+remainder),exact=lower if s['universeComplete'] else None)
 hhi=sum(r['share']**2 for r in out)*10000;metrics['HHI']=dict(lower=hhi,upper=hhi+remainder**2*10000,exact=hhi if s['universeComplete'] else None)
 return dict(type='declared-market-concentration',firms=ranked,knownCoverage=coverage,unknownShare=remainder,metrics=metrics,formulas=['份额=主体数量/市场总量','CRk=最大k个主体份额合计','HHI=10000*sum(份额平方)'],limitations=['部分样本的CR与HHI给出保守上下界，不把样本重新归一当成全市场','HHI下界未假设未知主体数量；上界假设未知份额集中一主体','市场定义、关联主体与全量声明来自输入，未独立核验','集中度不直接证明壁垒、盈利能力或垄断违法'])

def exit_cash(s):
 asof=context(s);cases=s['scenarios']
 if not 1<=len(cases)<=20 or len({c['name'] for c in cases})!=len(cases):raise ValueError('需1至20个不同名称情景')
 out=[]
 for case in cases:
  if case.get('costCoverage') not in ['declared-complete','partial'] or case.get('cashFlowCoverage') not in ['declared-complete','partial']:raise ValueError('需分别声明现金流与费用税收覆盖')
  if case.get('currency',s['currency'])!=s['currency'] or case.get('unit',s['unit'])!=s['unit']:raise ValueError('现金流币种或单位不一致')
  ledger=[];bydate={};totals={k:0. for k in ['investment','proceeds','distribution','fee','tax']}
  for row in case['flows']:
   day=date_value(row['date']);kind=row['kind']
   if kind not in totals:raise ValueError('未知现金流类别')
   if day>asof and row['amount']['basis']!='assumption':raise ValueError('未来现金流须明确假设')
   amount=field(row,'amount',s)
   if amount is None or amount<0:raise ValueError('现金流金额需非负，方向由类别定义')
   signed=amount if kind in ['proceeds','distribution'] else -amount;bydate[day]=bydate.get(day,0)+signed;totals[kind]+=amount;ledger.append(dict(date=day,kind=kind,amount=amount,signed=signed,basis=row['amount']['basis']))
  if totals['investment']<=0:raise ValueError('需正投入')
  kinds={r['kind'] for r in ledger}
  if case['costCoverage']=='declared-complete' and not {'fee','tax'}<=kinds:raise ValueError('完整费用声明需显式费用和税收，包括明确零假设')
  chronological=sorted(bydate.items());nonzero=[(d,v) for d,v in chronological if abs(v)>1e-12];signs=[1 if v>0 else -1 for d,v in nonzero];changes=sum(a!=b for a,b in zip(signs,signs[1:]));conventional=bool(signs and signs[0]<0 and signs[-1]>0 and changes==1)
  receipts=totals['proceeds']+totals['distribution'];costs=totals['fee']+totals['tax'];complete=case['costCoverage']=='declared-complete' and case['cashFlowCoverage']=='declared-complete';rate=xirr(nonzero) if conventional and complete else None
  out.append(dict(name=case['name'],route=case.get('route','未指定'),ledger=sorted(ledger,key=lambda r:r['date']),aggregatedFlows=chronological,totals=totals,knownCashChange=receipts-totals['investment']-costs,grossRecoveryMultiple=receipts/totals['investment'],netRecoveryMultiple=(receipts-costs)/totals['investment'] if complete else None,xirrPct=rate,annualizationStatus='calculated' if rate is not None else ('cashflow-or-costs-incomplete' if not complete else 'same-day-or-nonconventional-or-root-outside-range'),costCoverage=case['costCoverage'],cashFlowCoverage=case['cashFlowCoverage'],firstDate=chronological[0][0],lastDate=chronological[-1][0]))
 return dict(type='dated-exit-cash-scenarios',scenarios=out,formulas=['已知现金变化=回收及分配-投入-已知费用税收','扣费用回收倍数=(回收及分配-费用税收)/投入','XIRR用实际日期及365.25日年长，同日现金流先合并'],limitations=['费用完整性是输入声明，未独立核验实际税负或交易渠道','现金流或费用税收缺项不填零，不输出净回收倍数或年化','非传统多次正负切换可能多根，年化留空；总现金变化不因此丢弃','退出时间和回收额为情景假设，不承诺IPO、并购或转让能实现','未自动计入借款、外汇、资金占用、流动性限制或监管窗口，不生成退出指令'])

def scenario_judgment(mode,r):
 """Interpret existing results, without promoting assumptions into observed facts."""
 if mode=='supply':
  rows=r['periods'];missing=sum(bool(p['gaps']) for p in rows);short=sum(p['supplyDeficit'] is not None and p['supplyDeficit']>0 for p in rows);unbalanced=sum(p['balanceDifference'] is not None and abs(p['balanceDifference'])>1e-9 for p in rows)
  if missing:lead=f'有{missing}期缺少必要数量，当前不能形成完整供需平衡判断。'
  elif short:lead=f'给定输入下，有{short}期需求超过可供量；这一缺口说明情景需要调整，不证明实际市场已经短缺。'
  elif unbalanced:lead=f'给定输入下，有{unbalanced}期计算库存与披露库存不一致，尚不能把这套数据当作闭合的供需解释。'
  else:lead='给定输入未显示需求超过可供量，但这不证明需求强弱或价格方向；没有期末库存时，也不能确认库存勾稽。'
  return [lead,'先看产量、贸易与库存是否同范围同期间，再讨论需求含义。库存倒算消耗不是终端需求；差额可能涉及披露取整或统计口径，原因未核对时不直接认定数据错误。如果范围变化或库存修订改变平衡，应重新评价。']
 if mode=='concentration':
  coverage=r['knownCoverage'];unknown=r['unknownShare']
  lead=(f'已知主体只覆盖市场总量{coverage:.2%}，剩余{unknown:.2%}尚未归属；当前只能判断已知结构和保守范围，不能给出精确的全市场集中度。' if any(v['exact'] is None for v in r['metrics'].values()) else '按输入声明的完整市场范围，可以计算集中度；高份额仍不证明竞争壁垒或盈利能力。')
  return [lead,'未知份额可能分散，也可能集中在少数主体，二者会改变竞争格局的解释。应优先核对市场边界、关联主体和样本完整性，而不是把已知样本重新归一成全市场。']
 rows=r['scenarios'];partial=sum(c['cashFlowCoverage']!='declared-complete' or c['costCoverage']!='declared-complete' for c in rows)
 if partial:lead=f'有{partial}个情景的现金流或费用税收尚未完整，已知现金变化不能当作最终净收益，年化比较仍不充分。'
 else:lead='按声明完整的现金流与费用，可以比较回收结果；资金回收时间同样重要，回收倍数不能代替年化。'
 unavailable=sum(c['xirrPct'] is None for c in rows)
 return [lead,(f'其中{unavailable}个情景未能给出单根年化结果，不能把留空解释为零收益。' if unavailable else '所列年化依赖实际日期及现金流方向，不代表退出一定能实现。'),'如果回收日期、税费或额外投入发生变化，应重新计算；这些情景不提供退出指令，也不证明现实流动性。']

def run(mode,s,out):
 r={'supply':supply,'concentration':concentration,'exit':exit_cash}[mode](s);r.update(input=s,inputSha256=hashlib.sha256(json.dumps(s,ensure_ascii=False,sort_keys=True).encode()).hexdigest(),codeSha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
 r['judgment']=scenario_judgment(mode,r)
 def finite(obj):
  if isinstance(obj,(int,float)) and not isinstance(obj,bool) and not math.isfinite(obj):raise ValueError('计算溢出，检查输入尺度')
  if isinstance(obj,dict):
   for v in obj.values():finite(v)
  elif isinstance(obj,list):
   for v in obj:finite(v)
 finite(r);out=Path(out);out.mkdir(parents=True,exist_ok=False);lines=['# '+(s.get('name') or s['identity']['name'])+' · 研究情景','',s['asOf']+'；单位：'+s['unit']+'。事实、计算和假设分别留存；不承诺未来结果。']
 lines+=['','## 先看判断','> '+r['judgment'][0],*r['judgment'][1:]]
 if mode=='supply':
  lines+=['','## 供需与库存平衡']
  for p in r['periods']:
   lines.append(p['start']+'至'+p['end']+'。')
   if p['projectedClosingInventory'] is None:lines.append('必要数量缺失，未计算期末库存。')
   else:lines.append(f"按给定数量计算的期末库存为{p['projectedClosingInventory']:,.2f}；该值是平衡计算，不自动成为披露事实。")
   if p['impliedDemandFromStockBalance'] is not None:lines.append(f"库存平衡推算消耗{p['impliedDemandFromStockBalance']:,.2f}，不等于已披露终端需求。")
   if p['balanceDifference'] is not None:lines.append(f"披露期末库存{p['inputs']['closingInventory']:,.2f}，计算值与披露值差额{p['balanceDifference']:,.2f}。")
   if p['gaps']:lines.append('缺少：'+'、'.join(p['gaps'])+'，相应结果留空。')
   lines+=p['alerts']
 elif mode=='concentration':
  lines+=['','## 指定市场份额',f"已知主体覆盖市场总量{r['knownCoverage']:.2%}，剩余{r['unknownShare']:.2%}未归属。"]
  for k,v in r['metrics'].items():
   fmt=(lambda x:f'{x:.2f}') if k=='HHI' else (lambda x:f'{x:.2%}')
   lines.append(k+'：'+(fmt(v['exact']) if v['exact'] is not None else '保守范围'+fmt(v['lower'])+'至'+fmt(v['upper']))+'。')
 else:
  lines+=['','## 退出现金流情景']
  for c in r['scenarios']:
   lines += ['### '+c['name'],f"已知现金变化{c['knownCashChange']:,.2f}；费用前回收倍数{c['grossRecoveryMultiple']:.3f}。"]
   if c['netRecoveryMultiple'] is not None:lines.append(f"按声明费用税收计的回收倍数{c['netRecoveryMultiple']:.3f}。")
   if c['xirrPct'] is not None:lines.append(f"按实际日期计算的资金加权年化{c['xirrPct']:.2f}%，依赖情景现金流。")
   else:
    reason='现金流或费用税收尚未完整' if c['annualizationStatus']=='cashflow-or-costs-incomplete' else '日期或现金流方向不满足单根计算条件，或求根失败'
    lines.append('年化未计算：'+reason+'。')
 notes=[]
 def collect_notes(obj):
  if isinstance(obj,dict):
   if obj.get('basis')=='assumption' and obj.get('note') not in notes:notes.append(obj['note'])
   for v in obj.values():collect_notes(v)
  elif isinstance(obj,list):
   for v in obj:collect_notes(v)
 collect_notes(s)
 sources=[]
 def collect_sources(obj):
  if isinstance(obj,dict):
   if obj.get('sourceUrl') and obj.get('locator'):
    entry=(obj['sourceUrl'],obj['locator'],obj.get('publishedAt','未注明'))
    if entry not in sources:sources.append(entry)
   for v in obj.values():collect_sources(v)
  elif isinstance(obj,list):
   for v in obj:collect_sources(v)
 collect_sources(s)
 lines+=['','## 本次明确采用的假设',*(['- '+n for n in notes] or ['未提供独立数值假设；计算输入的说明与范围声明仍需复核。']),'','## 来源与口径']
 for url,locator,date in sources:lines.append(f'- [{locator}]({url})；来源日期：{date}。')
 lines+=['[查看完整输入、公式及来源底稿](result.json)；原文定位不自动等同全部字段已核验。','','## 局限',*['- '+x for x in r['limitations']]];md='\n'.join(lines)
 (out/'result.json').write_text(json.dumps(r,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8');(out/'研究情景.md').write_text(md,encoding='utf8');(out/'研究情景.html').write_text(render(md,title='研究情景'),encoding='utf8');return r
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['supply','concentration','exit']);p.add_argument('input',type=Path);p.add_argument('--out-dir',type=Path,required=True);a=p.parse_args();run(a.mode,load_json(a.input.read_text(encoding='utf-8-sig')),a.out_dir)
