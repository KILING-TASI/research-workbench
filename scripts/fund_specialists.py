"""Evidence-bound fund specialty modules; no transaction or forecasting inference."""
import argparse,math,copy
from pathlib import Path
from research_library import day,url,number,read,dump,NOTICE
from fund_depth import changes
from research_library import code as fund_code

def report_inputs(s):
 if not isinstance(s,dict) or not isinstance(s.get('reports'),list) or not s['reports'] or any(not isinstance(r,dict) for r in s['reports']):raise ValueError('需非空报告对象列表，缺报告不生成成功快照')
 return s['reports']

def metadata(s,r):
 if r['code']!=s['code'] or day(r['reportDate'])>day(r['publishedAt']) or day(r['publishedAt'])>day(s['asOf']):raise ValueError('主体或报告日期冲突')
 url(r['sourceUrl'])

def allocation(s):
 reports=report_inputs(s);rows=[];last=''
 for r in reports:
  metadata(s,r)
  if r['reportDate']<=last:raise ValueError('报告期须递增')
  last=r['reportDate'];weights=r['weights']
  if not isinstance(weights,dict) or not weights:raise ValueError('资产仓位须为非空对象，缺失资产不可当零')
  allowed={'aEquity','hkEquity','otherEquity','straightBonds','convertibles','cash','other','unknown'}
  if not set(weights)<=allowed:raise ValueError('未知资产类型')
  for k,v in weights.items():number(v,k,0)
  if abs(sum(weights.values())-1)>1e-6:raise ValueError('仓位合计须1，未知仓位必须保留')
  rows.append({'reportDate':r['reportDate'],'publishedAt':r['publishedAt'],'sourceUrl':r['sourceUrl'],'weights':weights,'unknownPct':weights.get('unknown',0)*100})
 pairs=[]
 for a,b in zip(rows,rows[1:]):pairs.append({'startReport':a['reportDate'],'endReport':b['reportDate'],'changesPp':{k:(b['weights'].get(k,0)-a['weights'].get(k,0))*100 for k in a['weights'].keys()|b['weights'].keys()},'observedAllocationDistancePct':sum(abs(b['weights'].get(k,0)-a['weights'].get(k,0)) for k in a['weights'].keys()|b['weights'].keys())*50 if not a['unknownPct'] and not b['unknownPct'] else None})
 return {'type':'fund-asset-allocation','code':s['code'],'asOf':s['asOf'],'rows':rows,'pairs':pairs,'sources':[r['sourceUrl'] for r in reports],'riskNotice':NOTICE,'limitations':['披露日资产仓位，不是日内仓位或当前配置','可转债从债券分类中单独拆出，不能与总债券权重重复计数','仓位差异不是换手或择时收益；未知仓位不当现金','未执行C-L/H-M/T-M择时模型，不宣称择时能力']}

def holding_key(h):
 from etf_evaluation import security_key
 key=security_key(h)
 if key is None:raise ValueError('证券身份须明确市场、代码及类别，命名空间不得与市场冲突')
 return key

def behavior(s):
 reports=report_inputs(s);states=[];timeline={};last=''
 for r in reports:
  metadata(s,r)
  if r['reportDate']<=last:raise ValueError('报告期须递增')
  last=r['reportDate']
  if r.get('scope') not in ['top10','completeEquity']:raise ValueError('需明确披露范围')
  held={}
  if not isinstance(r.get('holdings'),list) or any(not isinstance(h,dict) for h in r['holdings']):raise ValueError('持仓须为对象列表')
  equity=number(r.get('equityWeight'),'权益总仓位',0)
  if equity>1:raise ValueError('权益总仓位须为0至1')
  for h in r['holdings']:
   k=holding_key(h)
   if k in held:raise ValueError('重复证券，先合并')
   number(h['weight'],'净资产权重',0)
   if h['weight']>1:raise ValueError('权重须小数')
   held[k]=h
   timeline.setdefault(k,[]).append(r['reportDate'])
  if sum(h['weight'] for h in held.values())>equity+1e-6:raise ValueError('披露股票权重超过权益总仓位')
  if r['scope']=='completeEquity' and abs(sum(h['weight'] for h in held.values())-number(r['equityWeight'],'权益总仓位',0))>1e-6:raise ValueError('完整股票快照与权益总仓位不勾稽')
  states.append((r,held))
 pairs=[]
 for (a,wa),(b,wb) in zip(states,states[1:]):
  common=wa.keys()&wb.keys();full=a['scope']==b['scope']=='completeEquity'
  pairs.append({'startReport':a['reportDate'],'endReport':b['reportDate'],'commonCount':len(common),'observedRetentionPct':len(common)/len(wa)*100 if wa else None,'newlyDisclosed':[wb[k] for k in sorted(wb.keys()-wa.keys())],'noLongerDisclosed':[wa[k] for k in sorted(wa.keys()-wb.keys())],'weightAbsoluteChangePp':sum(abs(wb.get(k,{}).get('weight',0)-wa.get(k,{}).get('weight',0)) for k in sorted(wa.keys()|wb.keys()))*100 if full else None,'scopeMeaning':'完整股票快照变化，仍非真实交易' if full else '披露榜单变化，不能认定买入或卖出','sources':[a['sourceUrl'],b['sourceUrl']]})
 return {'type':'fund-disclosed-behavior','code':s['code'],'asOf':s['asOf'],'pairs':pairs,'timeline':[{'marketOrNamespace':k[0],'code':k[1],'shareClass':k[2],'observedDates':v,'observedReportCount':len(v)} for k,v in sorted(timeline.items())],'riskNotice':NOTICE,'sources':[r['sourceUrl'] for r in reports],'limitations':['持续出现在报告中不证明期间连续持有，缺期不插值','未再披露不等于卖出，特别是前十大榜单；数量权重变动可能来自价格、申赎或公司行动','不计算真实交易胜率、实际持股周期、左侧右侧交易或隐形交易能力']}

def style(s):
 reports=[];stats=[];previous=''
 for r in report_inputs(s):
  metadata(s,r)
  if r['reportDate']<=previous:raise ValueError('报告期须递增唯一')
  previous=r['reportDate']
  if r.get('scope')!='completeEquity':
   stats.append({'reportDate':r['reportDate'],'status':'gap','reason':'完整股票持仓未取得，不输出风格分布评分'});continue
  held=r['holdings']
  if len({holding_key(h) for h in held})!=len(held):raise ValueError('持仓证券重复')
  equity=number(r['equityWeight'],'股票仓位',0)
  if not equity or abs(sum(number(h['weight'],'持仓',0) for h in held)-equity)>1e-6:raise ValueError('完整股票权重不勾稽')
  classification=r['classification']
  if not isinstance(classification,dict) or any(not isinstance(classification.get(k),str) or not classification[k].strip() for k in ['taxonomy','version']):raise ValueError('风格分类体系与版本必须明确')
  url(classification['sourceUrl']);day(classification['effectiveAt'])
  if classification.get('effectiveTo'):
   day(classification['effectiveTo'])
   if classification['effectiveTo']<classification['effectiveAt'] or classification['effectiveTo']<r['reportDate']:raise ValueError('分类有效期倒置或在报告日前已失效')
  if classification.get('publishedAt'):
   if day(classification['publishedAt'])>day(s['asOf']):raise ValueError('分类资料晚于研究截止日')
  if classification['effectiveAt']>r['reportDate']:raise ValueError('分类晚于快照日，不能伪称当期风格')
  lookup={holding_key(x):x for x in classification['securities']}
  if len(lookup)!=len(classification['securities']):raise ValueError('分类证券重复')
  groups={};known=0;metrics={}
  for h in held:
   x=lookup.get(holding_key(h));w=h['weight']/equity;label=x.get('styleLabel') if x else None
   if label and classification.get('verified') is True:known+=w
   else:label='未知'
   groups[label]=groups.get(label,0)+w
   for k,v in (x.get('metrics',{}) if x else {}).items():
    if v is None:continue
    number(v,k);acc=metrics.setdefault(k,[0,0]);acc[0]+=w*v;acc[1]+=w
  reports.append({'code':s['code'],'reportDate':r['reportDate'],'publishedAt':r['publishedAt'],'sourceUrl':r['sourceUrl'],'weightBasis':'equity','taxonomy':classification['taxonomy'],'taxonomyVersion':classification['version'],'taxonomyVerified':classification.get('verified') is True,'categories':[{'name':k,'weight':v} for k,v in groups.items()]})
  stats.append({'reportDate':r['reportDate'],'status':'classified' if known>1-1e-6 else 'partial','coveragePct':known*100,'distributionPct':{k:v*100 for k,v in groups.items()},'holdingMetricExposure':{k:{'weightedMeanOnKnown':v[0]/v[1] if v[1] else None,'metricCoveragePct':v[1]*100} for k,v in metrics.items()},'classificationSourceUrl':classification['sourceUrl'],'classificationVersion':classification['version'],'classificationPublicationStatus':('retrospective-only' if classification['publishedAt']>r['reportDate'] else 'declared-before-or-on-snapshot-not-externally-verified') if classification.get('publishedAt') else 'missing-not-point-in-time-proof','metricEvidenceStatus':'input-provided-not-original-numerically-verified'})
 change=changes({'code':s['code'],'asOf':s['asOf'],'reports':reports}) if len(reports)>1 else None
 return {'type':'fund-holdings-style','code':s['code'],'asOf':s['asOf'],'rows':stats,'change':change,'sources':[r['sourceUrl'] for r in s['reports']],'riskNotice':NOTICE,'limitations':['风格标签依据明确的外部分类型、版本与截止日，未核验分类记未知，不按基金名称猜风格','指标均值只代表有数据持仓并附覆盖率；PE等均值非组合整体估值','非晨星认证九宫格或完整BARRA模型；不将行业分布当价值成长风格','不包含合同约束评分，不将分布变化等同违约或主动交易']}

def conditions(s):
 cutoff=day(s['asOf']);facts=[]
 for x in s['facts']:
  url(x['sourceUrl'])
  if day(x['observedAt'])>cutoff:raise ValueError('事实晚于截止日')
  if not x.get('field') or x.get('value') is None:raise ValueError('事实字段或值缺失')
  facts.append(x)
 results=[]
 for rule in s.get('rules',[]):
  if not isinstance(rule,dict) or not isinstance(rule.get('field'),str) or not rule['field'].strip() or rule.get('op') not in ['lt','gt','le','ge']:raise ValueError('规则字段或运算符无效')
  number(rule.get('threshold'),'阈值')
  matches=[x for x in facts if x['field']==rule['field']]
  if len(matches)!=1:results.append({'field':rule['field'],'status':'unknown','reason':'字段缺失或多来源冲突'});continue
  x=matches[0];number(x['value'],'规则值');number(rule['threshold'],'阈值')
  if rule['op'] not in ['lt','gt','le','ge']:raise ValueError('未知规则')
  matched={'lt':x['value']<rule['threshold'],'gt':x['value']>rule['threshold'],'le':x['value']<=rule['threshold'],'ge':x['value']>=rule['threshold']}[rule['op']]
  results.append({'field':rule['field'],'value':x['value'],'threshold':rule['threshold'],'status':'flag' if matched else 'not-triggered','sourceUrl':x['sourceUrl'],'label':rule.get('label','用户阈值条件')})
 gaps=[]
 if not facts:gaps.append('研究条件未提供输入事实，不能判定条件通过')
 if not results:gaps.append('本次未指定可执行规则，没有形成条件评价')
 return {'type':'fund-research-conditions','code':s['code'],'asOf':s['asOf'],'facts':facts,'checks':results,'status':'partial-or-not-assessed' if gaps or any(x['status']=='unknown' for x in results) else 'declared-rules-evaluated','evidenceGaps':gaps,'sources':[x['sourceUrl'] for x in facts],'riskNotice':NOTICE,'limitations':['用户阈值研究检查，不是机构准入评级或买卖建议','机构持有人占比不证明投资能力，规模阈值不代表必然清盘','只核对输入事实，不保证完整经理履历或所有申赎限制']}

COMMANDS={'allocation':allocation,'behavior':behavior,'style':style,'conditions':conditions}

def research(s):
 from fund_depth import manager,attribution
 if not isinstance(s,dict) or not isinstance(s.get('inputs',{}),dict):raise ValueError('专项输入须为模块对象映射')
 fund_code(s['code']);day(s['asOf'])
 inputs=s.get('inputs',{});results=[];gaps=[]
 runners={'allocation':allocation,'behavior':behavior,'style':style,'conditions':conditions,'manager':manager,'attribution':attribution}
 for kind,run in runners.items():
  if kind not in inputs:gaps.append({'module':kind,'reason':'未取得对应资料'});continue
  try:
   if not isinstance(inputs[kind],dict):raise ValueError('模块参数须为对象')
   data={**inputs[kind],'code':s['code'],'asOf':s['asOf']}
   if kind=='attribution':data['base']={**data['base'],'asOf':s['asOf']}
   result=run(data);results.append(result)
   gaps.extend({'module':kind,'reason':gap} for gap in result.get('evidenceGaps',[]))
  except (ValueError,KeyError,TypeError,OSError,ImportError) as e:gaps.append({'module':kind,'reason':str(e)})
 return {'type':'fund-specialist-research','code':s['code'],'asOf':s['asOf'],'depthResults':results,'gaps':gaps,'riskNotice':NOTICE,'limitations':['按已取得输入串联专项，不自动取得任意基金全部数据','单项失败保留缺口，不能称完整评价；资料错误先纠正']}
COMMANDS['research']=research

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('command',choices=COMMANDS);p.add_argument('input',type=Path);p.add_argument('--out',required=True,type=Path);a=p.parse_args();dump(a.out,COMMANDS[a.command](read(a.input)))
