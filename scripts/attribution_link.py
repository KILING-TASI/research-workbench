import datetime as dt,math
from research_library import brinson,NOTICE,day

def link(spec):
 if not isinstance(spec,dict):raise ValueError('跨期归因输入须为对象')
 periods=spec.get('periods')
 if not isinstance(periods,list) or not 1<=len(periods)<=100 or any(not isinstance(s,dict) for s in periods):raise ValueError('需1至100期归因对象输入')
 comparability={};gaps=[]
 for key in ['benchmarkId','portfolioId','weightScope','currency','industryVersion']:
  values=[s.get(key) for s in periods]
  if any(v is not None and (not isinstance(v,str) or not v.strip()) for v in values):raise ValueError('跨期身份或范围声明须为非空文字：'+key)
  known={v.strip() for v in values if v is not None}
  if len(known)>1:raise ValueError('跨期身份或范围不一致：'+key)
  status='declared-consistent-not-externally-verified' if all(v is not None for v in values) else 'missing-declaration'
  comparability[key]=dict(value=next(iter(known)) if known else None,status=status)
  if status=='missing-declaration':gaps.append('部分或全部期间未声明'+key+'，未证明可直接跨期比较')
 cutoff=day(spec.get('asOf'));results=[brinson(s) for s in periods]
 for i,(s,r) in enumerate(zip(periods,results)):
  if day(s['asOf'])>cutoff:raise ValueError('子期截止日超出总截止日')
  if i and s['start']!=periods[i-1]['end']:raise ValueError('子期须连续，按区间起止净值端点相接；不能遗漏或重叠')
  if s['industrySystem']!=periods[0]['industrySystem'] or s['returnBasis']!=periods[0]['returnBasis']:raise ValueError('跨期分类或收益口径不同')
  if r['portfolioSnapshotReturnPct']<=-100 or r['benchmarkReturnPct']<=-100:raise ValueError('累计归因需正财富路径')
 p=[1+r['portfolioSnapshotReturnPct']/100 for r in results];b=[1+r['benchmarkReturnPct']/100 for r in results]
 totals={k:0 for k in ['allocationPp','selectionPp','interactionPp']};linked=[];industries={}
 for i,r in enumerate(results):
  factor=math.prod(p[:i])*math.prod(b[i+1:]);contrib={k:r['totals'][k]*factor for k in totals}
  if not math.isfinite(factor) or any(not math.isfinite(v) for v in contrib.values()):raise ValueError('跨期归因链接数值溢出，不能输出非有限贡献')
  for k in totals:totals[k]+=contrib[k]
  for row in r['sectors']:
   dest=industries.setdefault(row['industry'],{k:0 for k in totals})
   for k in totals:dest[k]+=row[k]*factor
  linked.append({'start':r['start'],'end':r['end'],'linkFactor':factor,'effectsPp':contrib,'snapshot':r})
 active=(math.prod(p)-math.prod(b))*100;residual=active-sum(totals.values())
 if any(not math.isfinite(v) for v in [active,residual,*totals.values(),*[(math.prod(p)-1)*100,(math.prod(b)-1)*100]]) or any(not math.isfinite(v) for values in industries.values() for v in values.values()):raise ValueError('跨期累计收益或贡献数值溢出')
 if abs(residual)>1e-7:raise ValueError('多期贡献勾稽失败')
 return {'comparability':comparability,'gaps':gaps,'comparabilityStatus':'incomplete-declarations' if gaps else 'declared-consistent-not-externally-verified','type':'multi-period-snapshot-attribution','method':'chronological-telescoping-identity','formula':'C_t * product(1+Rp before t) * product(1+Rb after t)','portfolioReturnPct':(math.prod(p)-1)*100,'benchmarkReturnPct':(math.prod(b)-1)*100,'activeReturnPp':active,'effectsPp':totals,'industryEffectsPp':industries,'residualPp':residual,'periods':linked,'riskNotice':NOTICE,'limitations':['以代数望远镜恒等式链接单期贡献，与累计快照超额勾稽；不是GRAP，分项结果会因链接方法不同而不同','只解释披露快照组合的累计收益，不解释未提供的真实净值、交易或未知资产','连续端点不证明净值日历和报告持仓完整；数据来源仍按每期单独核验']}

def interpret_link(result):
 if result['gaps']:return '身份或口径声明不完整，暂不评价跨期贡献优劣；现有数值仅用于检查链接算术。'
 effects=result['effectsPp'];labels={'allocationPp':'行业配置','selectionPp':'行业内选择','interactionPp':'交互项'}
 active=result['activeReturnPp']
 if abs(active)<1e-7:return '快照组合与基准的累计收益差接近零，正负贡献可能相互抵消；不把贡献除以接近零的收益差，也不据此认定经理没有能力。'
 strongest=max(effects,key=lambda k:abs(effects[k]));direction='正向' if effects[strongest]>0 else '负向'
 if abs(effects[strongest])<1e-7:return '贡献金额接近零，当前精度下不区分主要来源；仍需核对输入及披露精度。'
 return ('在本次链接方法与已声明快照范围内，'+labels[strongest]+'的绝对贡献最大，为'+direction+'作用。'
         +'这解释的是输入快照与基准的历史差额，不是基金真实交易或经理个人能力；正负贡献抵消时不能把单项比例当作稳定能力。'
         +'若换用一致口径的实际持仓、基准或链接方法后排序改变，应修正这个来源判断。')

def render_summary(result):
 names={'benchmarkId':'基准身份','portfolioId':'组合身份','weightScope':'持仓分析范围','currency':'币种','industryVersion':'行业分类版本'}
 def readable_gap(text):
  for key,label in names.items():text=text.replace(key,label)
  return text
 lines=['# 多期持仓快照归因','本结果解释输入的固定权重快照组合，不能视为基金真实交易业绩归因。']
 if result['gaps']:
  lines+=['## 可比性待核实','部分期间缺少身份、范围或口径声明，下面仅保留代数核对结果，不能据此得出完整跨期归因结论。',*[readable_gap(g) for g in result['gaps']]]
 else:lines+=['各期声明一致，但来源、持仓完整性和基准身份仍需另行核验。']
 lines+=['## 怎样理解这个结果',interpret_link(result)]
 lines+=['## 累计结果',f"快照组合累计收益 {result['portfolioReturnPct']:.4f}%，基准累计收益 {result['benchmarkReturnPct']:.4f}%，差额 {result['activeReturnPp']:.4f} 个百分点。",'|期间|快照收益|基准收益|行业配置贡献|行业内选择贡献|交互贡献|','|---|---:|---:|---:|---:|---:|']
 for period in result['periods']:
  r=period['snapshot'];c=period['effectsPp']
  lines.append(f"|{period['start']} 至 {period['end']}|{r['portfolioSnapshotReturnPct']:.4f}%|{r['benchmarkReturnPct']:.4f}%|{c['allocationPp']:.4f}|{c['selectionPp']:.4f}|{c['interactionPp']:.4f}|")
 lines+=['表中贡献已按时间链接，单位为百分点；不是单期贡献的简单求和。行业内选择贡献不是基金经理纯 Alpha。','## 每期输入依据']
 for period in result['periods']:
  r=period['snapshot'];lines+=[f"{period['start']} 至 {period['end']}：权重快照日期 {r['weightDate']}；行业分类版本 {r.get('industryVersion','未提供')}。"]
  lines+=[r['informationTiming']['note']]
  for row in r['sectors']:lines.append(f"{row['industry']}：登记来源 {row['sourceUrl']}。")
 lines+=['## 局限',*result['limitations'],result['riskNotice']]
 return '\n'.join(lines)

if __name__=='__main__':
 import argparse
 from pathlib import Path
 from research_library import read,dump
 p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--out',required=True,type=Path);p.add_argument('--report',type=Path);a=p.parse_args()
 if a.report and (a.report.exists() or a.report.resolve()==a.out.resolve()):raise ValueError('报告须使用独立且不存在的新文件路径')
 result=link(read(a.input));report_text=render_summary(result) if a.report else None;dump(a.out,result)
 if a.report:
  a.report.parent.mkdir(parents=True,exist_ok=True)
  with a.report.open('x',encoding='utf8') as f:f.write(report_text)
