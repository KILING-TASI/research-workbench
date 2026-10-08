"""On-demand pool snapshots, period panels, clause labels and export presets."""
import argparse,copy,math
from pathlib import Path
from research_library import read,dump,pool,brinson,NOTICE,url,day
from research_outputs import snapshot,markdown,screen

def pool_snapshot(s):
 if not isinstance(s,dict) or not isinstance(s.get('pool'),dict) or not isinstance(s['pool'].get('codes'),list) or not isinstance(s.get('cards',[]),list) or any(not isinstance(x,dict) for x in s.get('cards',[])):raise ValueError('基金池及卡片须为有效对象/数组')
 members=s['pool']['codes'];cards=s.get('cards',[]);by={x['code']:x for x in cards}
 if len(by)!=len(cards) or len(set(members))!=len(members):raise ValueError('重复基金代码')
 out=[]
 for c in members:
  r=by.get(c)
  if not r:out.append({'code':c,'status':'missing','summary':'资料缺失，未形成诊断','metrics':{}});continue
  metrics=r.get('metrics',{});valid={}
  if not isinstance(metrics,dict):raise ValueError('指标须为字段对象')
  for k,v in metrics.items():
   value=v.get('value') if isinstance(v,dict) else v
   if value is not None and (isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value)):raise ValueError('非法指标值')
   valid[k]=value
  available=any(v is not None for v in valid.values())
  if available:url(r['sourceUrl'])
  gaps=[k for k in ['CAGRPct','maximumDrawdownPct','Sharpe'] if valid.get(k) is None]
  holdings=r.get('holdingsOverview');summary='历史指标已取得；' if available else '历史指标未取得；'
  summary+='持仓结构'+('已提供，需核对报告期' if holdings else '未取得')
  if gaps:summary+='；缺少'+ '、'.join({'CAGRPct':'年化收益率','maximumDrawdownPct':'最大回撤','Sharpe':'夏普比率'}[k] for k in gaps)
  out.append({'code':c,'status':r.get('status','provided'),'summary':summary,'metrics':valid,'start':r.get('start'),'end':r.get('end'),'holdingsOverview':holdings,'sourceUrl':r.get('sourceUrl'),'gaps':gaps})
 return {'type':'pool-diagnostic-snapshot','poolName':s['pool']['name'],'cards':out,'riskNotice':NOTICE,'limitations':['只处理本次已取得资料；缺失不评分、不填零','不同观察窗口不横向排名；持仓概览与净值区间分别标注','仅主动触发，无后台刷新；摘要描述证据缺口而非买卖风险评级']}

def attribution_panel(s):
 if not isinstance(s,dict) or not isinstance(s.get('periods'),list) or any(not isinstance(p,dict) for p in s['periods']):raise ValueError('多期归因须提供期间对象数组')
 rows=[];previous=''
 for p in s['periods']:
  start,end=p['start'],p['end'];day(start);day(end)
  if start>=end or (previous and start<previous):raise ValueError('期间重叠或乱序')
  previous=end
  if not p.get('input'):rows.append({'start':start,'end':end,'status':'missing','reason':p.get('reason','缺少该期归因输入')});continue
  if p['input']['start']!=start or p['input']['end']!=end:raise ValueError('归因窗口不匹配')
  r=brinson(p['input']);rows.append({'start':start,'end':end,'status':'calculated','allocationPp':r['totals']['allocationPp'],'selectionPp':r['totals']['selectionPp'],'interactionPp':r['totals']['interactionPp'],'activeReturnPp':r['activeSnapshotReturnPp'],'sources':[x['sourceUrl'] for x in r['sectors']],'weightDate':r['weightDate'],'informationTiming':r['informationTiming'],'comparisonDeclarations':{key:p['input'].get(key) for key in ['industrySystem','industryVersion','benchmarkId','portfolioId','weightScope','currency']}})
 calculated=[x for x in rows if x['status']=='calculated']
 declarations=[x['comparisonDeclarations'] for x in calculated];comparable=bool(calculated) and all(all(isinstance(v,str) and v.strip() for v in d.values()) for d in declarations) and all(d==declarations[0] for d in declarations)
 signs={k:{'positivePeriods':sum(x[k]>0 for x in calculated) if comparable or not calculated else None,'negativePeriods':sum(x[k]<0 for x in calculated) if comparable or not calculated else None,'availablePeriods':len(calculated)} for k in ['allocationPp','selectionPp','interactionPp']}
 return {'type':'brinson-period-panel','rows':rows,'signCounts':signs,'comparisonStatus':'declared-consistent-not-externally-verified' if comparable else 'not-established','comparisonGaps':[] if comparable else ['基准、组合、范围、币种或分类版本缺失/不一致，不能合并评价贡献持续性'],'riskNotice':NOTICE,'limitations':['仅披露快照归因，不能还原期间交易','缺期只留缺口；有缺期不输出完整累计归因，连续性不推断','正负次数只描述已有样本，不认定持续能力或未来贡献；贡献是百分点']}

LABELS={'港股投资限制':['港股','港股通'],'流动性条款':['流动性','侧袋'],'业绩报酬':['业绩报酬','超额业绩'],'封闭期':['封闭期','封闭运作'],'巨额赎回':['巨额赎回']}
def clauses(s):
 result=s['documentResult'];items=[]
 for c in result['candidates']:
  tags=[tag for tag,words in LABELS.items() if any(w in c['excerpt'] for w in words)]
  if tags:items.append({**c,'tags':tags,'status':'keyword-candidate-needs-context-verification'})
 query=s.get('query','');selected=[tag for tag in LABELS if tag in query or any(w in query for w in LABELS[tag])]
 if query and not selected:raise ValueError('未识别条款主题，请明确港股、流动性、业绩报酬、封闭期或巨额赎回')
 if selected:items=[x for x in items if set(x['tags'])&set(selected)]
 return {'type':'clause-tag-index','items':items,'requestedTags':selected,'sourceUrl':result['sourceUrl'],'documentSha256':result['documentSha256'],'riskNotice':NOTICE,'limitations':['固定关键词主题标签，不等于条款生效或允许投资的判断','未命中不证明没有条款，扫描页与目录需另核','回答须依据候选全文上下文及页码，不将目录标题当完整条款']}

TEMPLATES={'single-fund':'单基金投研简报','fund-pool':'基金池对比报告','fof':'FOF穿透报告','cross-asset':'跨资产组合诊断'}
def export_template(s):
 kind=s['template']
 if kind not in TEMPLATES:raise ValueError('未知模板')
 result=s['result']
 # Explicit suitability prevents a generic export from pretending it performed another analysis.
 types={'single-fund':['fund-comparison','integrated-fund-research'],'fund-pool':['pool-diagnostic-snapshot','fund-pool-score','fund-comparison'],'fof':['recursive-disclosed-holdings'],'cross-asset':['portfolio-return-risk-contributions','portfolio-adjustment-scenario','historical']}
 if result.get('type') not in types[kind]:raise ValueError('结果类型与模板不符，请提供对应分析结果，不进行自动转换')
 out=snapshot(result,s.get('title',TEMPLATES[kind]),s.get('notes',[]));out['template']=kind;out['templateFocus']={'single-fund':'业绩、风险与公开持仓；缺少基准不评价超额能力','fund-pool':'池内比较与逐标的数据缺口；样本内排序不是全市场排名','fof':'穿透路径、已知底层与未知部分；缺底层报告不归零','cross-asset':'资产权重、贡献与情景；情景损益不当未来回撤'}[kind];return out

COMMANDS={'pool-snapshot':pool_snapshot,'attribution-panel':attribution_panel,'clauses':clauses,'export':export_template}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('command',choices=list(COMMANDS)+['screen-to-pool']);p.add_argument('input',type=Path);p.add_argument('--out',required=True,type=Path);p.add_argument('--store',type=Path);a=p.parse_args();s=read(a.input)
 if a.out.exists() or (a.command=='export' and a.out.with_suffix('.md').exists()):raise ValueError('输出已存在')
 if a.command=='screen-to-pool':
  if not a.store:raise ValueError('需用户基金池目录')
  selected=screen(s['screenInput']);r={'type':'screen-pool-handoff','screen':selected,'pool':pool({'name':s['poolName'],'add':selected['selectedCodes']},a.store)}
 else:r=COMMANDS[a.command](s)
 text=markdown(r).replace(r['riskNotice'],r['riskNotice']+'\n\n'+r['templateFocus'],1) if a.command=='export' else None
 dump(a.out,r)
 if a.command=='export':
  dest=a.out.with_suffix('.md')
  if dest.exists():raise ValueError('Markdown文件已存在')
  dest.write_text(text,encoding='utf-8')
