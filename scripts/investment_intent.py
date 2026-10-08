"""Research-only checks against explicit user constraints; no trade approval."""
import argparse,json,hashlib,copy
from decimal import Decimal,InvalidOperation
from datetime import date
from pathlib import Path

def number(x):
 if isinstance(x,bool) or x is None:raise ValueError('金额或阈值不得为空或布尔值')
 try:n=Decimal(str(x))
 except InvalidOperation:raise ValueError('金额或阈值格式无效')
 if not n.is_finite():raise ValueError('金额或阈值须有限')
 return n

def nonnegative(x):
 n=number(x)
 if n<0:raise ValueError('金额不得为负数')
 return n

def issuer_exposure(spec,locator_paths=None):
 cutoff=date.fromisoformat(spec['asOf']);holdings={h['assetId']:h for h in spec['holdings']}
 if len(holdings)!=len(spec['holdings']):raise ValueError('发行人检查持仓重复，须先合并')
 total=sum(nonnegative(h['marketValue']) for h in holdings.values())
 if total<=0:raise ValueError('发行人检查组合市值须为正')
 relations=spec.get('issuerRelations',[])
 if not isinstance(relations,list):raise ValueError('发行人关系须为列表')
 seen=set();mapped={};excluded=[]
 for rel in relations:
  if not isinstance(rel,dict):raise ValueError('发行人关系须为对象')
  key=rel.get('assetId')
  if key not in holdings or key in seen:raise ValueError('发行人关系资产未知或重复')
  seen.add(key)
  if rel.get('relationRole','issuer')!='issuer':raise ValueError('受托管理人、承销商或担保人不能作为直接发行人')
  if holdings[key]['assetClass'] not in ['stock','bond','convertible']:raise ValueError('直接发行人关系仅用于股票、债券和转债；基金管理人不等于底层发行人')
  for field in ['issuerId','source','publishedAt','acquiredAt']:
   if not isinstance(rel.get(field),str) or not rel[field].strip():raise ValueError('发行人关系缺少'+field)
  from buy_side_thesis import locate,timing
  validity=timing(rel,cutoff);reasons=list(validity['reasons'])
  if validity['effectiveStatus']=='not-yet-effective':reasons.append('关系尚未生效')
  if reasons:
   excluded.append({'assetId':key,'reason':'；'.join(reasons),'relation':copy.deepcopy(rel)});continue
  checked=copy.deepcopy(rel);checked['timingCheck']=validity;locator=copy.deepcopy(rel.get('locator'))
  if locator and locator_paths and key in locator_paths:locator['path']=locator_paths[key]
  checked['locationCheck']=locate({'kind':'original','locator':locator})
  if locator and locator_paths and key in locator_paths:checked['locationCheck']['path']=str(Path(rel['locator']['path']).resolve())
  if checked['locationCheck']['status']=='quote-not-found':
   excluded.append({'assetId':key,'reason':'关系原文引句未在指定页定位，需先复核','relation':checked});continue
  mapped[key]=checked
 groups={};unknown=[]
 for key,h in holdings.items():
  if nonnegative(h['marketValue'])==0:continue
  if key not in mapped:
   unknown.append({'assetId':key,'marketValue':str(nonnegative(h['marketValue'])),'reason':'未提供有效直接关系，或属于基金/现金等尚未穿透范围'});continue
  rel=mapped[key];g=groups.setdefault(rel['issuerId'],{'issuerId':rel['issuerId'],'value':Decimal(0),'assets':[]})
  g['value']+=nonnegative(h['marketValue']);g['assets'].append(copy.deepcopy(rel))
 cap=spec['intent'].get('maximumIssuerWeightPct')
 if cap is not None and not 0<number(cap)<=100:raise ValueError('发行人上限须在0至100之间')
 rows=[{'issuerId':g['issuerId'],'marketValue':str(g['value']),'weightPct':str(g['value']/total*100),'assets':g['assets']} for g in groups.values()]
 failures=[r['issuerId'] for r in rows if cap is not None and number(r['weightPct'])>number(cap)]
 status='fail' if failures else 'unknown' if unknown or cap is None else 'pass'
 unknown_value=sum(number(x['marketValue']) for x in unknown)
 unknown_direct=sum(number(x['marketValue']) for x in unknown if holdings[x['assetId']]['assetClass'] in ['stock','bond','convertible'])
 for row in rows:
  row['directWeightUpperPct']=str((number(row['marketValue'])+unknown_direct)/total*100)
  row['couldExceedFromUnknownDirect']=None if cap is None else number(row['directWeightUpperPct'])>number(cap)
 unknown_direct_pct=unknown_direct/total*100
 direct_bounds={'unknownDirectValue':str(unknown_direct),'unknownDirectWeightPct':str(unknown_direct_pct),'unidentifiedIssuerCouldExceed':None if cap is None else unknown_direct_pct>number(cap),'otherUnknownValue':str(unknown_value-unknown_direct),'assumption':'上界假设全部未归属直接证券属于同一发行人，各发行人的上界互斥，不能相加；基金底层、现金银行和担保链不在此界限内。不是概率区间或实际归属判断。'}
 evidence_values={'quote-located':Decimal(0),'file-page-only':Decimal(0),'not-located':Decimal(0)}
 for key,rel in mapped.items():
  state=rel['locationCheck']['status']
  evidence_values[state]+=nonnegative(holdings[key]['marketValue'])
 evidence_coverage=[{'status':state,'marketValue':str(value),'portfolioWeightPct':str(value/total*100)} for state,value in evidence_values.items()]
 return {'status':status,'groups':rows,'unknown':unknown,'unknownValue':str(unknown_value),'knownCoveragePct':str((total-unknown_value)/total*100),'evidenceCoverage':evidence_coverage,'directBounds':direct_bounds,'excludedRelations':excluded,'maximumIssuerWeightPct':cap,'exceededIssuers':failures,'limitation':'仅直接证券发行人合并；无关系不填零；基金穿透、实控人、担保链和现金银行信用尚未覆盖。日期与关系来自输入声明，不认证原文真实性；覆盖比例不是准确率'}

def link_portfolio(spec,portfolio,locator_paths=None):
 """Recompute from the original portfolio input; never trust an old result alone."""
 from portfolio_stress import analyze as stress_analyze
 if spec['asOf']!=portfolio['asOf']:raise ValueError('组合与意图截止日不一致')
 if spec['intent']['currency']!=portfolio['baseCurrency']:raise ValueError('组合与意图币种不一致')
 mapping=spec.get('stressCodeMap',{})
 if not isinstance(mapping,dict):raise ValueError('代码映射须为对象')
 target={h['assetId']:h for h in spec['holdings']}
 source={h['code']:h for h in portfolio['holdings']}
 if len(target)!=len(spec['holdings']) or len(source)!=len(portfolio['holdings']):raise ValueError('桥接持仓身份重复')
 if set(mapping)!=set(source) or set(mapping.values())!=set(target) or len(set(mapping.values()))!=len(mapping):raise ValueError('代码映射须完整且一对一，不能猜测资产身份')
 for code,asset in mapping.items():
  a,b=source[code],target[asset]
  if a['currency']!=b['currency'] or number(a['marketValue'])!=number(b['marketValue']):raise ValueError('桥接持仓金额或币种不一致:'+asset)
 if spec.get('scenarios'):raise ValueError('已有意图情景与组合情景不能静默覆盖，请分别运行比较')
 model=stress_analyze(portfolio)
 linked=copy.deepcopy(spec)
 linked['scenarios']=[{'name':r['name'],'returnShocksPct':{mapping[k]:v for k,v in r.get('returnShocksPct',{}).items()},'assumptions':r.get('assumptions',[])} for r in portfolio.get('scenarios',[])]
 if spec.get('scenarioLiquidity'):
  names=[r['name'] for r in linked['scenarios']]
  if len(set(names))!=len(names):raise ValueError('流动性联动需要唯一情景名称')
  if not isinstance(spec['scenarioLiquidity'],dict) or set(spec['scenarioLiquidity'])-set(names):raise ValueError('流动性联动情景名称不存在')
  for scenario in linked['scenarios']:scenario['liquidationAdjustments']=spec['scenarioLiquidity'].get(scenario['name'],{})
 result=analyze(linked,locator_paths)
 result['portfolioLink']={'originalIntentInputSha256':hashlib.sha256(json.dumps(spec,ensure_ascii=False,sort_keys=True).encode()).hexdigest(),'portfolioInputSha256':hashlib.sha256(json.dumps(portfolio,ensure_ascii=False,sort_keys=True).encode()).hexdigest(),'codeMap':mapping,'recomputedStressResult':model,'limitation':'使用原始组合输入重新计算，映射与资料由输入声明；不是实际账户认证'}
 return result

def analyze(spec,locator_paths=None):
 asof=date.fromisoformat(spec['asOf']);intent=spec['intent'];currency=intent['currency']
 for key in ['id','purpose','currency']:
  if not isinstance(intent.get(key),str) or not intent[key].strip():raise ValueError('缺少投资意图字段:'+key)
 target=date.fromisoformat(intent['targetDate'])
 if target<asof:raise ValueError('资金目标日早于研究日')
 allowed=intent.get('allowedAssetClasses')
 if not isinstance(allowed,list) or not allowed or any(not isinstance(x,str) or not x for x in allowed):raise ValueError('需明确允许的资产类型')
 reserve=nonnegative(intent['minimumCash']);limit=number(intent['maximumAssetWeightPct'])
 maximum_age=intent.get('maximumValuationAgeDays')
 if maximum_age is not None and (isinstance(maximum_age,bool) or not isinstance(maximum_age,int) or maximum_age<0):raise ValueError('估值有效期须为非负整数天数')
 if not 0<limit<=100:raise ValueError('单资产上限须在0至100之间')
 holdings=spec['holdings']
 if not isinstance(holdings,list) or not holdings:raise ValueError('需提供持仓列表')
 ids=set();rows=[];total=Decimal(0);cash=Decimal(0)
 for h in holdings:
  key=h['assetId']
  if not isinstance(key,str) or not key.strip() or key in ids:raise ValueError('资产身份无效或重复；先合并同一意图内同一资产')
  ids.add(key)
  if h['currency']!=currency:raise ValueError('币种不一致；需先提供有来源的汇率转换结果')
  value=nonnegative(h['marketValue']);total+=value
  category=h.get('assetClass')
  if not isinstance(category,str) or not category:raise ValueError('缺少资产类型')
  age=None
  if h.get('valuationDate') is None:valuation='unknown'
  else:
   d=date.fromisoformat(h['valuationDate'])
   if d>asof:raise ValueError('持仓估值包含未来日期')
   age=(asof-d).days
   valuation='stale' if maximum_age is not None and age>maximum_age else 'declared'
  if category=='cash' and (h.get('availableBy') is None or date.fromisoformat(h['availableBy'])<=asof):cash+=value
  liquid=h.get('availableBy')
  if liquid is not None:date.fromisoformat(liquid)
  rows.append({'assetId':key,'assetClass':category,'value':str(value),'availableBy':liquid,'valuationStatus':valuation,'valuationDate':h.get('valuationDate'),'valuationAgeDays':age})
 if total<=0:raise ValueError('组合总金额须大于零')
 checks=[]
 def add(name,status,detail):checks.append({'name':name,'status':status,'detail':detail})
 for r in rows:
  weight=number(r['value'])/total*100;r['weightPct']=str(weight)
  add('资产范围：'+r['assetId'],'pass' if r['assetClass'] in allowed else 'fail','资产类型为'+r['assetClass'])
  add('集中度：'+r['assetId'],'pass' if weight<=limit else 'fail','权重'+format(weight,'.2f')+'%，用户上限'+str(limit)+'%')
  if r['valuationStatus']=='unknown':add('估值日期：'+r['assetId'],'unknown','未提供估值日期，不能确认快照时点')
  elif r['valuationStatus']=='stale':add('估值有效期：'+r['assetId'],'unknown','估值已间隔'+str(r['valuationAgeDays'])+'天，用户有效期为'+str(maximum_age)+'天；需刷新后重查，当前金额仅作旧快照计算')
 if maximum_age is None:add('快照时效阈值','unknown','未提供估值最大有效天数，不能认定市值足够新；不会自行设置有效期')
 add('现金预留','pass' if cash>=reserve else 'fail','现金'+str(cash)+'，用户最低预留'+str(reserve)+'；仅按现金类别与声明可用日期核对，现金类之外不自动视为现金')
 needs=spec.get('cashNeeds',[])
 if not isinstance(needs,list):raise ValueError('资金需求须为列表')
 schedule={}
 for need in needs:
  when=date.fromisoformat(need['date'])
  if when<asof or when>target:raise ValueError('资金需求日期须在研究日和目标日之间')
  amount=nonnegative(need['amount']);schedule[when]=schedule.get(when,Decimal(0))+amount
 cumulative=Decimal(0)
 for when,amount in sorted(schedule.items()):
  cumulative+=amount;available=sum((number(r['value']) for r in rows if r['assetClass']=='cash' and (r['availableBy'] is None or date.fromisoformat(r['availableBy'])<=when)),Decimal(0));unknown=[]
  for r in rows:
   if r['assetClass']=='cash':continue
   if r['availableBy'] is None:unknown.append(r['assetId'])
   elif date.fromisoformat(r['availableBy'])<=when:available+=number(r['value'])
  required=cumulative+reserve
  status='pass' if available>=required else 'unknown' if unknown else 'fail'
  add('流动性：'+when.isoformat(),status,'累计需求及预留'+str(required)+'；按当前市值与声明日期可用'+str(available)+('；未明确变现时间：'+ '、'.join(unknown) if unknown else '')+'；未预测价格或保证实际可变现')
 if not schedule:add('未来资金需求','unknown','未提供未来支出，不能认定期限匹配')
 stress=intent.get('maximumStressLossPct');scenarios=spec.get('scenarios',[])
 if stress is None:add('压力损失预算','unknown','用户尚未指定压力损失上限，不能认定风险预算满足')
 if stress is not None:
  threshold=number(stress)
  if not 0<=threshold<=100:raise ValueError('压力损失上限须为0至100')
  if not scenarios:add('压力损失','unknown','未提供压力情景，不能认定风险预算满足')
  for scenario in scenarios:
   shocks=scenario.get('returnShocksPct',{})
   adjustments=scenario.get('liquidationAdjustments',{})
   if not isinstance(adjustments,dict) or set(adjustments)-ids:raise ValueError('变现条件须对应已知资产')
   for asset,adjustment in adjustments.items():
    if not isinstance(adjustment,dict) or not adjustment or set(adjustment)-{'availableBy','deductionPct'}:raise ValueError('变现条件字段无效')
    if 'availableBy' in adjustment and adjustment['availableBy'] is not None:date.fromisoformat(adjustment['availableBy'])
    if 'deductionPct' in adjustment and not 0<=number(adjustment['deductionPct'])<=100:raise ValueError('变现扣减比例须为0至100')
    add('情景变现假设：'+scenario['name']+'／'+asset,'unknown' if 'availableBy' in adjustment and adjustment['availableBy'] is None else 'pass','输入声明：'+('到账日期'+str(adjustment['availableBy'])+'；' if 'availableBy' in adjustment else '')+('冲击后市值再扣减'+str(adjustment['deductionPct'])+'%；' if 'deductionPct' in adjustment else '')+'仅为情景参数，不是实际费用或赎回时效核验')
   if set(shocks)-ids:raise ValueError('压力情景含未知资产')
   for v in shocks.values():
    if number(v)<-100:raise ValueError('无杠杆冲击不能低于-100%')
   missing=ids-set(shocks)
   if missing:add('压力情景：'+scenario['name'],'unknown','冲击未覆盖全部持仓：'+'、'.join(sorted(missing)));continue
   pnl=sum((number(r['value'])*number(shocks[r['assetId']])/100 for r in rows),Decimal(0))
   loss=max(Decimal(0),-pnl/total*100)
   add('压力情景：'+scenario['name'],'pass' if loss<=threshold else 'fail','假设一次冲击损失'+format(loss,'.2f')+'%，上限'+str(threshold)+'%；不是未来最大回撤')
   cumulative_stress=Decimal(0)
   for when,amount in sorted(schedule.items()):
    cumulative_stress+=amount;available=Decimal(0);unknown_liquid=[]
    for r in rows:
     shocked=number(r['value'])*(1+number(shocks[r['assetId']])/100)
     adjustment=adjustments.get(r['assetId'],{})
     net=shocked*(1-number(adjustment.get('deductionPct',0))/100)
     liquid=adjustment.get('availableBy',r['availableBy'])
     immediate=r['assetClass']=='cash' and r['availableBy'] is None and 'availableBy' not in adjustment
     if immediate or liquid is not None and date.fromisoformat(liquid)<=when:available+=net
     elif liquid is None:unknown_liquid.append(r['assetId'])
    required=cumulative_stress+reserve
    status='pass' if available>=required else 'unknown' if unknown_liquid else 'fail'
    add('压力后资金覆盖：'+scenario['name']+'／'+when.isoformat(),status,'假设冲击后按声明变现日可用'+format(available,'.2f')+'，累计需求及预留'+str(required)+('；变现日期未明确：'+'、'.join(unknown_liquid) if unknown_liquid else '')+('；已采用明确输入的情景到账日或变现扣减' if adjustments else '；未提供额外情景变现条件，不含压力赎回延迟或折价')+'；假设冲击先于用钱发生且之后不恢复，不是未来价格路径或实际到账保证')
 issuer=None
 if 'issuerRelations' in spec or 'maximumIssuerWeightPct' in intent:
  issuer=issuer_exposure(spec,locator_paths)
  add('发行人合并集中度',issuer['status'],'超过所给上限的发行人：'+('、'.join(issuer['exceededIssuers']) or '已知部分未发现')+'；关系未知资产数：'+str(len(issuer['unknown']))+'；未知部分可能增加已有发行人暴露，不等于全组合满足约束')
 status='constraints-not-met' if any(c['status']=='fail' for c in checks) else 'needs-data' if any(c['status']=='unknown' for c in checks) else 'supplied-checks-met'
 return {'type':'investment-intent-review','asOf':spec['asOf'],'intent':intent,'totalValue':str(total),'holdings':rows,'checks':checks,'issuerExposure':issuer,'status':status,'inputSha256':hashlib.sha256(json.dumps(spec,ensure_ascii=False,sort_keys=True).encode()).hexdigest(),'limitations':['仅核对用户提供的约束和资料，不认证投资适当性或审批通过','可用日期和市值是输入声明，不含流动性折价、费用、税费及市场冲击','不构成交易指令，不自动修改阈值或推断未来收益']}

def export(result,out):
 from research_brief_html import render
 out=Path(out);out.mkdir(parents=True,exist_ok=False)
 labels={'constraints-not-met':'存在约束不满足','needs-data':'尚需补充资料','supplied-checks-met':'所提供检查项满足约束'}
 md=['# 资金用途与组合约束研究','',result['intent']['purpose'],'',labels[result['status']]+'。此结果不是投资批准。','研究日：'+result['asOf']+'；资金目标日：'+result['intent']['targetDate'],'']
 for c in result['checks']:md+=['## '+c['name'],{'pass':'满足所给条件','fail':'不满足所给条件','unknown':'资料不足'}[c['status']]+'：'+c['detail'],'']
 if result.get('issuerExposure'):
  issuer=result['issuerExposure'];md+=['## 同一发行人的重复暴露','']
  md+=['已关联市值覆盖组合'+format(number(issuer['knownCoveragePct']),'.2f')+'%；尚未归属金额'+issuer['unknownValue']+'。覆盖比例不是准确率，未知部分可能增加已有发行人的集中度。','']
  evidence_labels={'quote-located':'已定位原文引句','file-page-only':'仅核对文件与页码','not-located':'仅有关系声明，未定位原文'}
  for item in issuer.get('evidenceCoverage',[]):
   md+=[evidence_labels[item['status']]+'：市值'+item['marketValue']+'，占全组合'+format(number(item['portfolioWeightPct']),'.2f')+'%。']
  md+=['上述定位层次与关联市值覆盖分开；引句存在不证明关系语义或披露日期真实。','']
  for g in issuer['groups']:md+=[g['issuerId']+'：合计'+g['marketValue']+'，占组合'+format(number(g['weightPct']),'.2f')+'%；关联证券：'+'、'.join(a['assetId'] for a in g['assets'])+'。']
  bounds=issuer.get('directBounds')
  if bounds:
   md+=['未归属直接证券市值'+bounds['unknownDirectValue']+'；其他未穿透范围市值'+bounds['otherUnknownValue']+'。']
   for g in issuer['groups']:md+=[g['issuerId']+'的直接证券占比范围为'+format(number(g['weightPct']),'.2f')+'%至'+format(number(g['directWeightUpperPct']),'.2f')+'%；上界仅反映未知直接证券可能归属，不认定实际超限。']
   md+=[bounds['assumption'],'']
  for g in issuer['groups']:
   for a in g['assets']:
    loc=a['locationCheck'];status={'not-located':'尚未提供原文定位','file-page-only':'文件与页码已检查，未提供引句','quote-located':'原文引句已定位'}[loc['status']]
    md+=['关系来源：'+a['source']+'；披露日：'+a['publishedAt']+'；取得日：'+a['acquiredAt']+'；'+status+('，PDF第'+str(loc['page'])+'页' if 'page' in loc else '')+'。定位不等于证券发行人关系语义已经认证。']
  for x in issuer['excludedRelations']:md+=['未采用关系：'+x['assetId']+'；'+x['reason']+'。']
  for u in issuer['unknown']:md+=['未归属：'+u['assetId']+'，市值'+u['marketValue']+'；'+u['reason']+'。']
  md+=[issuer['limitation'],'']
 md+=['## 研究范围',*result['limitations']];content='\n'.join(md)
 (out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf-8');(out/'组合约束.md').write_text(content,'utf-8');(out/'组合约束.html').write_text(render(content,title='资金用途与组合约束'),'utf-8')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--portfolio-input',type=Path);p.add_argument('--out-dir',required=True,type=Path);a=p.parse_args()
 spec=json.loads(a.input.read_text('utf-8-sig'))
 result=link_portfolio(spec,json.loads(a.portfolio_input.read_text('utf-8-sig'))) if a.portfolio_input else analyze(spec)
 export(result,a.out_dir)
