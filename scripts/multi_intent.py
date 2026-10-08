"""Explicit allocation of the same source assets across funding purposes."""
import argparse,copy,json,hashlib,shutil
from pathlib import Path
from decimal import Decimal
from investment_intent import analyze,nonnegative,number

def allocate(spec,locator_paths=None):
 source=spec['holdings'];currency=spec['currency']
 if not isinstance(source,list) or not source:raise ValueError('需提供原始持仓')
 assets={};allocated={}
 for h in source:
  key=h['assetId']
  if not isinstance(key,str) or not key.strip() or key in assets:raise ValueError('原始持仓身份重复或无效')
  if h['currency']!=currency:raise ValueError('先统一有来源的币种口径')
  nonnegative(h['marketValue']);assets[key]=h;allocated[key]=Decimal(0)
 if 'issuerRelations' in spec:
  relations=spec['issuerRelations'];relation_ids=set()
  if not isinstance(relations,list):raise ValueError('发行人关系须为列表')
  for rel in relations:
   if not isinstance(rel,dict) or rel.get('assetId') not in assets:raise ValueError('分组关系引用原始持仓以外的资产')
   if rel['assetId'] in relation_ids:raise ValueError('原始发行人关系重复，须先解释冲突')
   relation_ids.add(rel['assetId'])
 shared=spec.get('sharedScenarios');scenario_names=set()
 if shared is not None:
  if not isinstance(shared,list) or not shared:raise ValueError('共同压力情景须为非空列表')
  for scenario in shared:
   if not isinstance(scenario,dict) or not isinstance(scenario.get('name'),str) or not scenario['name'].strip() or scenario['name'] in scenario_names:raise ValueError('共同情景名称无效或重复')
   scenario_names.add(scenario['name']);shocks=scenario.get('returnShocksPct',{})
   if not isinstance(shocks,dict) or set(shocks)-set(assets):raise ValueError('共同冲击引用未知资产')
   for value in shocks.values():
    if number(value)<-100:raise ValueError('共同冲击不得低于-100%')
   adjustments=scenario.get('liquidationAdjustments',{})
   if not isinstance(adjustments,dict) or set(adjustments)-set(assets):raise ValueError('共同变现条件引用未知资产')
 tasks=spec['intents']
 if not isinstance(tasks,list) or not tasks:raise ValueError('需提供资金用途分配')
 seen=set();results=[]
 for task in tasks:
  intent=task['intent'];key=intent['id']
  if key in seen:raise ValueError('资金用途编号重复')
  seen.add(key)
  if intent['currency']!=currency:raise ValueError('资金用途币种不一致')
  rows=task['allocations']
  if not isinstance(rows,list) or not rows:raise ValueError('用途需有明确资产分配')
  selected=[];local=set()
  for row in rows:
   asset=row['assetId']
   if asset not in assets or asset in local:raise ValueError('用途资产未知或重复')
   local.add(asset);amount=nonnegative(row['marketValue'])
   if amount<=0:raise ValueError('分配金额须为正')
   allocated[asset]+=amount
   if allocated[asset]>nonnegative(assets[asset]['marketValue']):raise ValueError('同一资产跨用途重复计资超过原始市值：'+asset)
   holding=copy.deepcopy(assets[asset]);holding['marketValue']=str(amount);selected.append(holding)
  request={'asOf':spec['asOf'],'intent':copy.deepcopy(intent),'holdings':selected,'cashNeeds':copy.deepcopy(task.get('cashNeeds',[])),'scenarios':copy.deepcopy(task.get('scenarios',[]))}
  if shared is not None:
   if task.get('scenarios'):raise ValueError('共同情景不能静默覆盖用途自己的情景，请分别研究')
   request['scenarios']=[]
   for scenario in shared:
    current=copy.deepcopy(scenario);current['returnShocksPct']={k:v for k,v in scenario.get('returnShocksPct',{}).items() if k in local}
    current['liquidationAdjustments']={k:copy.deepcopy(v) for k,v in scenario.get('liquidationAdjustments',{}).items() if k in local};request['scenarios'].append(current)
  if 'issuerRelations' in spec:request['issuerRelations']=[copy.deepcopy(r) for r in spec['issuerRelations'] if r['assetId'] in local]
  results.append({'intentId':key,'allocatedInput':request,'result':analyze(request,locator_paths)})
 unallocated=[{'assetId':key,'marketValue':str(nonnegative(h['marketValue'])-allocated[key])} for key,h in assets.items() if nonnegative(h['marketValue'])>allocated[key]]
 return {'type':'multi-intent-allocation','asOf':spec['asOf'],'currency':currency,'intents':results,'sharedScenarioNames':sorted(scenario_names),'unallocated':unallocated,'status':'constraints-not-met' if any(r['result']['status']=='constraints-not-met' for r in results) else 'needs-data' if any(r['result']['status']=='needs-data' for r in results) else 'supplied-checks-met','limitations':['按用户指定金额分组，不自动优化分配或生成交易','未分配资金不用于任一用途的现金覆盖；每个用途单独检查预留和需求','不包括真实账户结算、未来收入或共享担保；不能把结果当成投资批准']}

def methods():
 return {name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() for name in ['multi_intent.py','investment_intent.py','buy_side_thesis.py','research_brief_html.py']}

def build(spec,out,include_originals=False):
 result=allocate(spec);export(result,out)
 out=Path(out);(out/'input.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2,allow_nan=False),'utf-8')
 if include_originals:
  from buy_side_thesis import locate
  attachments=[]
  for rel in spec.get('issuerRelations',[]):
   if not rel.get('locator'):
    attachments.append({'assetId':rel['assetId'],'status':'not-provided'});continue
   c=locate({'kind':'original','locator':rel['locator']});relative='sources/'+c['sha256']+'.pdf';target=out/relative;target.parent.mkdir(exist_ok=True)
   if not target.exists():shutil.copy2(c['path'],target)
   if hashlib.sha256(target.read_bytes()).hexdigest()!=c['sha256']:raise ValueError('关系原文副本变化')
   attachments.append({'assetId':rel['assetId'],'relativePath':relative,'status':c['status'],'sha256':c['sha256']})
  (out/'relation-attachments.json').write_text(json.dumps(attachments,ensure_ascii=False,indent=2),'utf-8')
  md=(out/'资金用途分组.md').read_text('utf-8')+'\n\n## 关系原文归档\n\n'
  for item in attachments:
   md+=('[查看'+item['assetId']+'原文]('+item['relativePath']+')。定位不等于关系语义认证。\n\n' if item.get('relativePath') else item['assetId']+'尚未提供原文定位。\n\n')
  md+='原文用于本地复查，不授予对外再分发权。\n'
  from research_brief_html import render
  (out/'资金用途分组.md').write_text(md,'utf-8');(out/'资金用途分组.html').write_text(render(md,title='多资金用途覆盖'),'utf-8')
 files={p.relative_to(out).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in out.rglob('*') if p.is_file()}
 (out/'manifest.json').write_text(json.dumps({'files':files,'methods':methods(),'hasOriginals':include_originals,'limitations':['检查本地完整性和同版本复算，不是数字签名或真实账户认证','原文按显式归档覆盖；缺定位仍是输入声明，不授予再分发权']},ensure_ascii=False,indent=2),'utf-8')
 return result

def replay(folder):
 folder=Path(folder).resolve();m=json.loads((folder/'manifest.json').read_text('utf-8'))
 if m['methods']!=methods():raise ValueError('方法版本变化，须另存新版本重新验收')
 if not {'input.json','result.json','资金用途分组.md','资金用途分组.html'}.issubset(m['files']):raise ValueError('分组包缺少必需文件')
 if m.get('hasOriginals') and 'relation-attachments.json' not in m['files']:raise ValueError('缺少关系附件映射')
 for name,expected in m['files'].items():
  p=(folder/name).resolve()
  if not p.is_relative_to(folder):raise ValueError('分组包引用越出目录')
  if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=expected:raise ValueError('分组包文件缺失或变化')
 from buy_side_thesis import digest
 spec=json.loads((folder/'input.json').read_text('utf-8'));paths={}
 if m.get('hasOriginals'):
  from buy_side_thesis import locate
  expected={r['assetId']:r for r in spec.get('issuerRelations',[])};attachments=json.loads((folder/'relation-attachments.json').read_text('utf-8'))
  if len(attachments)!=len(expected) or {r['assetId'] for r in attachments}!=set(expected):raise ValueError('关系归档覆盖不一致')
  for item in attachments:
   rel=expected[item['assetId']]
   if not item.get('relativePath'):
    if rel.get('locator'):raise ValueError('关系原文附件缺失')
    continue
   p=(folder/item['relativePath']).resolve()
   if not p.is_relative_to(folder) or item['relativePath'] not in m['files']:raise ValueError('关系附件引用无效')
   loc=copy.deepcopy(rel['locator']);loc['path']=str(p)
   if locate({'kind':'original','locator':loc})['status']!=item['status']:raise ValueError('关系原文定位复查不同')
   paths[item['assetId']]=str(p)
 result=allocate(spec,paths)
 if digest(result)!=digest(json.loads((folder/'result.json').read_text('utf-8'))):raise ValueError('分组结果重算不一致')
 return {'status':'replayed-identical','constraintStatus':result['status'],'limitations':m['limitations']}

def export(result,out):
 from research_brief_html import render
 out=Path(out);out.mkdir(parents=True,exist_ok=False)
 unmet=[x['result']['intent']['purpose'] for x in result['intents'] if x['result']['status']=='constraints-not-met']
 missing=[x['result']['intent']['purpose'] for x in result['intents'] if x['result']['status']=='needs-data']
 lines=['# 多资金用途覆盖研究','','每笔持仓按明确金额分组；不同用途不能重复使用同一笔资金。','']
 if result.get('sharedScenarioNames'):lines+=['各用途采用共同冲击：'+'、'.join(result['sharedScenarioNames'])+'。仅对各用途已分配资产核对；未分配余额不自动作为支援。一次冲击不等于未来最大回撤。','']
 else:lines+=['各用途情景分别提供，未认定为同一次统一市场压力测试。','']
 if unmet:lines+=['目前不满足所给约束的用途：'+'、'.join(unmet)+'。先查看下面对应的现金缺口、集中度或压力条件，不能用其他用途资金补算成满足。','']
 if missing:lines+=['尚无法完成判断的用途：'+'、'.join(missing)+'。需要补齐缺失资料或用户阈值。','']
 if not unmet and not missing:lines+=['各用途的已提供检查项均满足所给条件；这不是未来资金安全保证或投资批准。','']
 for entry in result['intents']:
  r=entry['result'];lines+=['## '+r['intent']['purpose'],'已分配市值：'+r['totalValue']+' '+result['currency']+'；用钱目标日：'+r['intent']['targetDate']+'。']
  for c in r['checks']:lines+=['- '+c['name']+'：'+{'pass':'满足所给条件','fail':'不满足条件','unknown':'资料不足'}[c['status']]+'；'+c['detail']]
  issuer=r.get('issuerExposure')
  if issuer:
   lines+=['','### 发行人关联与原文依据','关联市值占本用途'+issuer['knownCoveragePct']+'%；未归属市值'+issuer['unknownValue']+'。此处比例以本用途已分配市值为分母，不是全账户比例或核验准确率。']
   for group in issuer['groups']:lines += [group['issuerId']+'：合计'+group['marketValue']+'，占本用途'+group['weightPct']+'%。']
   if issuer.get('directBounds'):
    for group in issuer['groups']:lines += [group['issuerId']+'的直接证券占比上界为'+group['directWeightUpperPct']+'%；不是实际归属或超限判断。']
    lines += [issuer['directBounds']['assumption']]
   labels={'quote-located':'已定位原文引句','file-page-only':'仅核对文件与页码','not-located':'仅有关系声明，未定位原文'}
   for item in issuer.get('evidenceCoverage',[]):lines += [labels[item['status']]+'：市值'+item['marketValue']+'，占本用途'+item['portfolioWeightPct']+'%。']
   for item in issuer['excludedRelations']:lines += ['未采用关系：'+item['assetId']+'；'+item['reason']+'。']
   for item in issuer['unknown']:lines += ['未归属：'+item['assetId']+'，市值'+item['marketValue']+'。']
   lines += ['引句存在不证明发行人关系语义；基金底层、实控人及担保链未在此合并。']
  lines+=['']
 lines+=['## 尚未分配的持仓','']
 for row in result['unallocated']:lines+=[row['assetId']+'：'+row['marketValue']+' '+result['currency']+'，未用于任何用途的资金覆盖。']
 if not result['unallocated']:lines+=['所提供持仓已全部明确分配。']
 lines+=['','## 研究范围',*result['limitations']];md='\n'.join(lines)
 (out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf-8');(out/'资金用途分组.md').write_text(md,'utf-8');(out/'资金用途分组.html').write_text(render(md,title='多资金用途覆盖'),'utf-8')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--out-dir',type=Path);p.add_argument('--replay',action='store_true');p.add_argument('--include-originals',action='store_true');a=p.parse_args()
 if a.replay:print(json.dumps(replay(a.input),ensure_ascii=False))
 else:
  if not a.out_dir:p.error('构建需要--out-dir')
  build(json.loads(a.input.read_text('utf-8-sig')),a.out_dir,a.include_originals)
