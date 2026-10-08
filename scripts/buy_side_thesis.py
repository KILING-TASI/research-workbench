"""Freeze supplied investment hypotheses; review evidence without rewriting history."""
import argparse,copy,hashlib,json
from datetime import date
from pathlib import Path
from decimal import Decimal,InvalidOperation

def numeric(value):
 if isinstance(value,bool) or value is None:raise ValueError('指标数值不得为空或布尔值')
 try:n=Decimal(str(value))
 except InvalidOperation:raise ValueError('指标数值格式无效')
 if not n.is_finite():raise ValueError('指标数值须有限')
 return n

def validate_condition(rule):
 if not isinstance(rule,dict):raise ValueError('指标条件须为对象')
 for k in ['metric','unit','periodBasis']:text(rule.get(k),k)
 if rule.get('operator') not in ['lt','le','gt','ge','eq']:raise ValueError('条件比较符无效')
 numeric(rule.get('threshold'))
 if rule.get('requiredPeriods') is not None:
  periods=rule['requiredPeriods']
  if not isinstance(periods,list) or not 2<=len(periods)<=24 or any(not isinstance(p,str) for p in periods):raise ValueError('多期条件须指定2至24个日期字符串')
  if len(set(periods))!=len(periods):raise ValueError('多期条件报告期不得重复')
  for p in periods:date.fromisoformat(p)
  if periods!=sorted(periods):raise ValueError('报告期须按时间升序指定')

def condition_check(rule,observation,usable,entity,cutoff):
 validate_condition(rule)
 result={'status':'unknown','rule':copy.deepcopy(rule),'observation':copy.deepcopy(observation),'note':'仅比较声明指标和阈值，不自动认定投资假设失效或产生交易指令'}
 if rule.get('requiredPeriods'):
  if observation is None:observation=[]
  if not isinstance(observation,list):raise ValueError('多期条件须提供观测列表')
  periods=rule['requiredPeriods'];seen={}
  for row in observation:
   if not isinstance(row,dict) or row.get('periodEnd') not in periods:raise ValueError('观测报告期不在指定范围')
   if row['periodEnd'] in seen:raise ValueError('同一报告期观测重复，需先解释冲突')
   seen[row['periodEnd']]=row
  single={k:v for k,v in rule.items() if k!='requiredPeriods'}
  checks=[{'periodEnd':p,**condition_check(single,seen.get(p),usable,entity,cutoff)} for p in periods]
  statuses=[c['status'] for c in checks]
  result.update(periodChecks=checks,status='unknown' if 'unknown' in statuses else 'threshold-met' if all(s=='threshold-met' for s in statuses) else 'threshold-not-met',reason='逐期核对明确指定的报告期；缺期不替代，不证明这些日期构成完整连续披露')
  return result
 if observation is None:result['reason']='未提供对应指标观测';return result
 if not isinstance(observation,dict):raise ValueError('指标观测须为对象')
 mismatches=[k for k in ['metric','unit','periodBasis'] if observation.get(k)!=rule[k]]
 if observation.get('entityId')!=entity:mismatches.append('entityId')
 if mismatches:result['reason']='标的或指标口径不匹配：'+'、'.join(mismatches);return result
 if date.fromisoformat(observation['observedAt'])>cutoff:result['reason']='指标观测晚于复盘截止日';return result
 if observation.get('periodEnd'):
  period=date.fromisoformat(observation['periodEnd'])
  if period>date.fromisoformat(observation['observedAt']):raise ValueError('报告期晚于指标观测日')
 evidence_row=next((e for e in usable if e['id']==observation.get('evidenceId') and e['kind']!='assumption'),None)
 if evidence_row is None:result['reason']='缺截止日内有效的非假设证据';return result
 if evidence_row.get('locationCheck',{}).get('status')=='quote-not-found':result['reason']='证据引句未定位，需先人工核对';return result
 value=numeric(observation['value']);threshold=numeric(rule['threshold'])
 operators={'lt':value<threshold,'le':value<=threshold,'gt':value>threshold,'ge':value>=threshold,'eq':value==threshold}
 result.update(status='threshold-met' if operators[rule['operator']] else 'threshold-not-met',reason='按所给口径和数值比较；数值与原文语义仍需核验')
 return result

def locate(row):
 locator=row.get('locator')
 if locator is None:return {'status':'not-located','explanation':'尚未提供可检查的原文定位'}
 if row['kind']=='assumption':raise ValueError('研究假设不能标作原文定位证据')
 if not isinstance(locator,dict):raise ValueError('原文定位须为对象')
 p=Path(locator.get('path',''))
 if not p.is_file() or p.suffix.lower()!='.pdf':raise ValueError('定位原文PDF不存在')
 raw=p.read_bytes();sha=hashlib.sha256(raw).hexdigest()
 if not raw.startswith(b'%PDF-') or locator.get('sha256')!=sha:raise ValueError('定位原文摘要不一致')
 page=locator.get('page')
 if isinstance(page,bool) or not isinstance(page,int) or page<1:raise ValueError('原文页码无效')
 import pdfplumber
 with pdfplumber.open(p) as doc:
  if page>len(doc.pages):raise ValueError('原文页码超出范围')
  content=doc.pages[page-1].extract_text() or ''
 quote=locator.get('quote')
 if quote is not None:text(quote,'原文引句')
 compact=lambda s:''.join(s.split())
 matched=bool(quote and compact(quote) in compact(content))
 return {'status':'quote-located' if matched else 'quote-not-found' if quote else 'file-page-only','path':str(p.resolve()),'sha256':sha,'page':page,'quote':quote,'explanation':'仅检查文件、页码与引句文字位置，不证明摘要、因果或投资假设成立'}

def digest(value):
 return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def text(value,name):
 if not isinstance(value,str) or not value.strip():raise ValueError('缺少'+name)
 return value

def timing(row,cutoff):
 published=date.fromisoformat(row['publishedAt']);acquired=date.fromisoformat(row['acquiredAt'])
 if acquired<published:raise ValueError('取得日期早于披露日期')
 effective=date.fromisoformat(row['effectiveAt']) if row.get('effectiveAt') else None
 recorded=date.fromisoformat(row['recordedAt']) if row.get('recordedAt') else None
 applicable=date.fromisoformat(row['applicableUntil']) if row.get('applicableUntil') else None
 withdrawn=date.fromisoformat(row['withdrawnAt']) if row.get('withdrawnAt') else None
 superseded=date.fromisoformat(row['supersededAt']) if row.get('supersededAt') else None
 if applicable and applicable<published:raise ValueError('适用截止日早于原披露日')
 if applicable and effective and applicable<effective:raise ValueError('适用截止日早于生效日')
 if superseded and not row.get('supersededBy'):raise ValueError('替代版本须提供对应证据标识')
 if row.get('supersededBy') and not superseded:raise ValueError('替代版本须提供生效日期')
 if withdrawn and withdrawn<published or superseded and superseded<published:raise ValueError('撤回或替代日期早于原披露日')
 if recorded and recorded<acquired:raise ValueError('留存日期早于取得日期')
 reasons=[]
 if published>cutoff:reasons.append('披露日期晚于研究截止日')
 if acquired>cutoff:reasons.append('取得日期晚于研究截止日')
 if applicable and applicable<cutoff:reasons.append('资料适用期限已过，不能作为当前有效依据')
 if withdrawn and withdrawn<=cutoff:reasons.append('资料已声明撤回，需核对撤回原文')
 if superseded and superseded<=cutoff:reasons.append('资料已声明被版本'+str(row['supersededBy'])+'替代，需核对新旧差异')
 return {'publishedAt':row['publishedAt'],'acquiredAt':row['acquiredAt'],'effectiveAt':row.get('effectiveAt'),'recordedAt':row.get('recordedAt'),'applicableUntil':row.get('applicableUntil'),'withdrawnAt':row.get('withdrawnAt'),'supersededAt':row.get('supersededAt'),'supersededBy':row.get('supersededBy'),
         'availability':'excluded' if reasons else 'declared-available',
         'effectiveStatus':'not-yet-effective' if effective and effective>cutoff else 'effective-declared' if effective else 'not-specified',
         'historicalRetention':'declared-retained-by-cutoff' if recorded and recorded<=cutoff else 'not-demonstrated',
         'limitation':'时间字段为输入声明，不能据此证明历史网页可得性或事前留存','reasons':reasons}

def evidence(rows,cutoff):
 if not isinstance(rows,list):raise ValueError('证据须为列表')
 usable=[];excluded=[];ids=set()
 for row in rows:
  text(row.get('id'),'证据编号');text(row.get('source'),'来源');text(row.get('summary'),'证据摘要')
  if row['id'] in ids:raise ValueError('证据编号重复')
  ids.add(row['id'])
  if row.get('kind') not in ['original','third-party','assumption']:raise ValueError('来源类型无效')
  check=timing(row,cutoff)
  item=copy.deepcopy(row)
  item['timingCheck']=check
  if check['reasons']:
   item['exclusionReason']='；'.join(check['reasons']);excluded.append(item)
  else:
   item['locationCheck']=locate(row)
   usable.append(item)
 return usable,excluded

def freeze(spec):
 cutoff=date.fromisoformat(spec['asOf']);text(spec.get('entityId'),'标的身份');text(spec.get('question'),'研究问题')
 rows=spec.get('hypotheses',[])
 if not isinstance(rows,list) or not 1<=len(rows)<=100:raise ValueError('假设数量须为1至100')
 hypotheses=[];ids=set()
 for row in rows:
  for k in ['id','claim','invalidation','verificationMetric']:text(row.get(k),k)
  if row.get('invalidationCondition') is not None:validate_condition(row['invalidationCondition'])
  if row['id'] in ids:raise ValueError('假设编号重复')
  ids.add(row['id']);date.fromisoformat(row['reviewBy'])
  if row['reviewBy']<spec['asOf']:raise ValueError('验证日期早于研究截止日')
  usable,excluded=evidence(row.get('evidence',[]),cutoff)
  gaps=row.get('gaps',[])
  if not isinstance(gaps,list) or any(not isinstance(g,str) or not g.strip() for g in gaps):raise ValueError('资料缺口须为非空文字列表')
  for item in usable+excluded:
   if item.get('stance') not in ['support','oppose','context']:raise ValueError('证据方向无效')
  hypotheses.append({**copy.deepcopy(row),'evidence':usable,'excludedEvidence':excluded,'status':'unverified','gaps':gaps})
 result={'type':'buy-side-thesis','version':1,'entityId':spec['entityId'],'question':spec['question'],'asOf':spec['asOf'],'hypotheses':hypotheses,'limitations':['证据内容及日期由输入提供，未自动认证原文真实性','支持证据数量不是可信度评分；未验证不等于假设成立','只用于研究假设验证，不生成买卖指令']}
 return {'snapshot':result,'snapshotSha256':digest(result)}

def review(frozen,spec):
 snapshot=frozen['snapshot']
 if digest(snapshot)!=frozen['snapshotSha256']:raise ValueError('首次研究快照已变化')
 cutoff=date.fromisoformat(spec['asOf'])
 if spec['asOf']<snapshot['asOf']:raise ValueError('复盘日期不得早于首次研究')
 known={h['id'] for h in snapshot['hypotheses']};seen=set();rows=[]
 originals={h['id']:h for h in snapshot['hypotheses']}
 assessments=spec.get('assessments',[])
 if not isinstance(assessments,list):raise ValueError('复盘条目须为列表')
 for item in assessments:
  key=item['hypothesisId']
  if key not in known or key in seen:raise ValueError('假设编号未知或重复')
  seen.add(key)
  if item.get('outcome') not in ['supported','contradicted','unverified']:raise ValueError('验证结论无效')
  text(item.get('explanation'),'复盘解释')
  usable,excluded=evidence(item.get('evidence',[]),cutoff)
  prior=originals[key]['evidence']
  for e in usable:
   reused=any(e['source']==p['source'] and e['publishedAt']==p['publishedAt'] and e['summary']==p['summary'] for p in prior)
   e['reviewRole']='reused-original-context' if reused else 'newly-supplied-context' if e['publishedAt']<=snapshot['asOf'] else 'later-disclosure'
  if item['outcome']!='unverified' and not any(e['kind']!='assumption' and e.get('locationCheck',{}).get('status')!='quote-not-found' for e in usable):raise ValueError('验证结论须有截止日内非假设证据；引句未找到的材料不能独立支撑确认')
  entry={**copy.deepcopy(item),'evidence':usable,'excludedEvidence':excluded}
  if originals[key].get('invalidationCondition'):entry['conditionCheck']=condition_check(originals[key]['invalidationCondition'],item.get('observation'),usable,snapshot['entityId'],cutoff)
  rows.append(entry)
 for key in sorted(known-seen):
  entry={'hypothesisId':key,'outcome':'unverified','explanation':'尚未提供复盘材料','evidence':[],'excludedEvidence':[]}
  if originals[key].get('invalidationCondition'):entry['conditionCheck']=condition_check(originals[key]['invalidationCondition'],None,[],snapshot['entityId'],cutoff)
  rows.append(entry)
 updates=spec.get('evidenceUpdates',[])
 if not isinstance(updates,list):raise ValueError('证据变更须为列表')
 mapped={};update_keys=set();deferred=[]
 for u in updates:
  if not isinstance(u,dict):raise ValueError('证据变更须为对象')
  key=(u.get('hypothesisId'),u.get('evidenceId'))
  if key[0] not in originals or not any(e['id']==key[1] for e in originals[key[0]]['evidence']):raise ValueError('变更引用的首次证据不存在')
  if key in update_keys:raise ValueError('同一证据变更重复')
  update_keys.add(key)
  text(u.get('reason'),'变更说明');text(u.get('source'),'变更来源')
  changes=u.get('changes')
  allowed={'applicableUntil','withdrawnAt','supersededAt','supersededBy'}
  if not isinstance(changes,dict) or not changes or set(changes)-allowed:raise ValueError('仅允许更新证据适用期、撤回及替代声明')
  if any(v is None or v=='' for v in changes.values()):raise ValueError('不得通过空值删除证据变更')
  candidate=next(e for e in originals[key[0]]['evidence'] if e['id']==key[1])
  timing({**candidate,**changes},cutoff)
  if not u.get('publishedAt') or not u.get('acquiredAt'):
   deferred.append({**copy.deepcopy(u),'exclusionReason':'变更披露或取得日期缺失，尚未用于历史时点判断'});continue
  published=date.fromisoformat(u['publishedAt']);acquired=date.fromisoformat(u['acquiredAt'])
  if acquired<published:raise ValueError('变更取得日期早于披露日期')
  if published>cutoff or acquired>cutoff:
   deferred.append({**copy.deepcopy(u),'exclusionReason':'变更披露或取得晚于复盘截止日，未反向改写依据'});continue
  mapped[key]=u
 current=[];impacts=[]
 for h in snapshot['hypotheses']:
  for e in h['evidence']:
   updated=copy.deepcopy(e);u=mapped.get((h['id'],e['id']))
   if u:updated.update(u['changes'])
   check=timing(updated,cutoff)
   current.append({'hypothesisId':h['id'],'evidenceId':e['id'],'timingCheck':check,'update':copy.deepcopy(u)})
   if check['reasons']:
    impacts.append({'hypothesisId':h['id'],'claim':h['claim'],'verificationMetric':h['verificationMetric'],'evidenceId':e['id'],'reasons':check['reasons'],'status':'requires-recheck','update':copy.deepcopy(u)})
 for entry in rows:
  retained=[]
  for e in entry['evidence']:
   u=mapped.get((entry['hypothesisId'],e['id']))
   prior=next((p for p in originals[entry['hypothesisId']]['evidence'] if p['id']==e['id']),None)
   if u and prior and (e['source']!=prior['source'] or e['publishedAt']!=prior['publishedAt']):raise ValueError('新版本须使用新证据编号，不能覆盖旧证据身份')
   checked=copy.deepcopy(e)
   if u:checked.update(u['changes'])
   t=timing(checked,cutoff)
   if t['reasons']:
    checked['timingCheck']=t;checked['exclusionReason']='；'.join(t['reasons']);entry['excludedEvidence'].append(checked)
   else:
    checked['timingCheck']=t
    retained.append(checked)
  entry['evidence']=retained
  if entry['outcome']!='unverified' and not any(e['kind']!='assumption' and e.get('locationCheck',{}).get('status')!='quote-not-found' for e in retained):raise ValueError('变更后的失效证据或未定位引句不能独立支撑验证结论')
  rule=originals[entry['hypothesisId']].get('invalidationCondition')
  if rule:entry['conditionCheck']=condition_check(rule,entry.get('observation'),retained,snapshot['entityId'],cutoff)
 return {'type':'buy-side-thesis-review','asOf':spec['asOf'],'originalSnapshotSha256':frozen['snapshotSha256'],'original':copy.deepcopy(snapshot),'originalEvidenceCurrentValidity':current,'evidenceImpact':impacts,'excludedEvidenceUpdates':deferred,'assessments':rows,'limitations':snapshot['limitations']+['验证结论来自所提供的研究判断，程序不自动证明因果或经理能力','证据变更按输入声明追踪，不自动认证更正原文；影响范围仅覆盖此档案的显式证据关联']}

def markdown(result):
 original=result.get('original',result.get('snapshot',{}));lines=['# 投资假设研究档案','',original['question'],'','标的：'+original['entityId']+'；首次研究截止日：'+original['asOf']+'。','']
 assessments={r['hypothesisId']:r for r in result.get('assessments',[])}
 labels={'supported':'现有证据支持','contradicted':'现有证据反对','unverified':'尚未验证'}
 for u in result.get('excludedEvidenceUpdates',[]):lines+=['本次未采用的证据变更：'+u['reason']+'。'+u['exclusionReason']+'；来源：'+u['source']+'。','']
 if result.get('evidenceImpact'):
  lines+=['## 需要重新核对的判断','']
  for impact in result['evidenceImpact']:
   lines+=['“'+impact['claim']+'”的依据发生适用性变化；需要重查'+impact['verificationMetric']+'。原因：'+'；'.join(impact['reasons'])+'。首次判断保留，这不自动证明原判断错误。']
   if impact.get('update'):lines+=['变更说明：'+impact['update']['reason']+'；所给来源：'+impact['update']['source']+'。该变更声明尚未自动完成原文核验。']
  lines+=['']
 for h in original['hypotheses']:
  lines+=['## '+h['claim'],'验证指标：'+h['verificationMetric'],'失效条件：'+h['invalidation'],'下次核对日期：'+h['reviewBy'],'']
  for e in h['evidence']:
   stance={'support':'支持材料','oppose':'反对材料','context':'背景材料'}[e['stance']]
   lines+= [stance+'：'+e['summary']+'。来源：'+e['source']+'；披露日：'+e['publishedAt']+'；取得日：'+e['acquiredAt']+'。',location_note(e)]
  if not any(e['stance']=='oppose' for e in h['evidence']):lines+=['反方检查：本次未提供反对材料，不代表没有反对证据。']
  if not h['evidence']:lines+=['当前没有截止日内的可用证据，此项仍是待验证假设。']
  for e in h['excludedEvidence']:lines+=['未用于首次判断：'+e['summary']+'（'+e['exclusionReason']+'）。']
  if h['gaps']:lines+=['资料缺口：'+'；'.join(h['gaps'])+'。']
  for validity in result.get('originalEvidenceCurrentValidity',[]):
   if validity['hypothesisId']==h['id'] and validity['timingCheck']['reasons']:lines+=['首次依据当前状态：'+ '；'.join(validity['timingCheck']['reasons'])+'。历史依据保留，当前判断需重新核对。']
  if h['id'] in assessments:
   a=assessments[h['id']];lines+=['复盘：'+labels[a['outcome']]+'。'+a['explanation']]
   if a.get('conditionCheck'):
    c=a['conditionCheck'];rule=c['rule'];symbols={'lt':'低于','le':'不高于','gt':'高于','ge':'不低于','eq':'等于'}
    lines+=['用户设定条件：'+rule['metric']+symbols[rule['operator']]+str(rule['threshold'])+rule['unit']+'；期间口径：'+rule['periodBasis']+'。']
    if c.get('periodChecks'):
     for pc in c['periodChecks']:
      obs=pc.get('observation') or {};lines+=['报告期'+pc['periodEnd']+'：'+str(obs.get('value','缺失'))+str(obs.get('unit',''))+'；'+{'unknown':'资料不足','threshold-met':'触及阈值','threshold-not-met':'未触及阈值'}[pc['status']]+'。']
    elif c.get('observation'):lines+=['所给观测：'+str(c['observation'].get('value','缺失'))+str(c['observation'].get('unit',''))+'；观测日：'+str(c['observation'].get('observedAt','缺失'))+'。']
    lines+=['指标条件检查：'+{'unknown':'资料不足','threshold-met':'所给观测触及阈值，需复核原判断','threshold-not-met':'所给观测未触及阈值，不代表假设已成立'}[c['status']]+'。'+c['reason']]
   for e in a['evidence']:lines+=['复盘依据：'+e['summary']+'。来源：'+e['source']+'；披露日：'+e['publishedAt']+'。',location_note(e)]
   for e in a['excludedEvidence']:lines+=['未用于本次复盘：'+e['summary']+'（'+e['exclusionReason']+'）。']
  lines+=['']
 lines+=['## 研究范围',*original['limitations']]
 return '\n'.join(lines)

def location_note(e):
 check=e.get('locationCheck',{});labels={'not-located':'原文尚未定位','quote-located':'原文引句已定位','quote-not-found':'所给引句未在指定页找到，需人工核对','file-page-only':'文件与页码已检查，尚未核对引句'}
 note='定位核对：'+labels.get(check.get('status'),'未进行定位检查')+('；PDF第'+str(check['page'])+'页' if 'page' in check else '')+'。定位不代表研究判断已获验证。'
 timing=e.get('timingCheck',{})
 if timing.get('historicalRetention')=='not-demonstrated':note+=' 尚未证明这份材料在首次研究时已经留存。'
 if timing.get('effectiveStatus')=='not-yet-effective':note+=' 截止日尚未生效，不能作为已经执行的事实。'
 roles={'reused-original-context':'复用首次研究材料，不是新增兑现证据','newly-supplied-context':'新补充的历史材料，不改变首次研究依据','later-disclosure':'首次研究之后披露的材料'}
 if e.get('reviewRole'):note+=' '+roles[e['reviewRole']]+'。'
 return note

def export(result,out):
 from research_brief_html import render
 out=Path(out);out.mkdir(parents=True,exist_ok=False)
 (out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf-8')
 md=markdown(result);(out/'研究档案.md').write_text(md,'utf-8');(out/'研究档案.html').write_text(render(md,title='投资假设与验证'),'utf-8')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('command',choices=['freeze','review']);p.add_argument('input',type=Path);p.add_argument('--snapshot',type=Path);p.add_argument('--out-dir',required=True,type=Path);a=p.parse_args()
 spec=json.loads(a.input.read_text('utf-8-sig'))
 if a.command=='review' and not a.snapshot:p.error('复盘需要--snapshot')
 r=freeze(spec) if a.command=='freeze' else review(json.loads(a.snapshot.read_text('utf-8-sig')),spec)
 export(r,a.out_dir)
