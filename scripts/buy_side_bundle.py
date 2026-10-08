"""Portable intent/portfolio input replay with optional frozen hypothesis reference."""
import argparse,json,hashlib,copy,shutil
from pathlib import Path
from investment_intent import analyze,link_portfolio,export
from buy_side_thesis import digest,locate,numeric,timing
from datetime import date
from collection_validation import unique_pairs,reject_constant,finite_json_float

def read_json(path):
 return json.loads(Path(path).read_text(encoding="utf-8-sig"),object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float)

def thesis_exposure(intent,thesis):
 snap=thesis['snapshot']
 if digest(snap)!=thesis['snapshotSha256']:raise ValueError('假设快照摘要不符')
 if snap['asOf']>intent['asOf']:raise ValueError('假设快照晚于组合研究截止日')
 holdings=intent['holdings'];matched=[h for h in holdings if h['assetId']==snap['entityId']]
 if not matched:raise ValueError('假设主体未明确关联组合持仓')
 total=sum(numeric(h['marketValue']) for h in holdings);amount=sum(numeric(h['marketValue']) for h in matched)
 if total<=0:raise ValueError('组合市值须为正')
 hypotheses=[]
 for h in snap['hypotheses']:
  checks=[{'evidenceId':e['id'],**timing(e,date.fromisoformat(intent['asOf']))} for e in h['evidence']]
  invalid=[c for c in checks if c['reasons'] or c['effectiveStatus']=='not-yet-effective']
  hypotheses.append({'id':h['id'],'claim':h['claim'],'status':h['status'],'verificationMetric':h['verificationMetric'],'currentEvidenceChecks':checks,'evidenceNeedsRecheck':bool(invalid) or not checks,'recheckReasons':[reason for c in invalid for reason in (c['reasons'] or ['依据尚未生效'])]+(['未提供首次可用证据'] if not checks else [])})
 return {'entityId':snap['entityId'],'linkedMarketValue':float(amount),'portfolioWeightPct':float(amount/total*100),'currency':intent['intent']['currency'],'snapshotSha256':thesis['snapshotSha256'],'hypotheses':hypotheses,'limitation':'仅按相同资产编号关联直接持仓；不穿透发行人关系，不代表这些资金必然损失；多个假设不可重复相加敞口。依据时效仅按首次声明重查，未自动取得新公告'}

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False),'utf-8')
def methods():
 return {name:sha(Path(__file__).with_name(name)) for name in ['buy_side_bundle.py','investment_intent.py','portfolio_stress.py','buy_side_thesis.py','research_brief_html.py']}
def build(intent,out,portfolio=None,thesis=None,include_originals=False):
 result=link_portfolio(intent,portfolio) if portfolio is not None else analyze(intent)
 if thesis is not None:
  result['thesisExposure']=thesis_exposure(intent,thesis)
 attachments=[]
 if include_originals:
  if thesis is None and not intent.get('issuerRelations'):raise ValueError('包含原文需要假设或发行人关系')
  for h in (thesis['snapshot']['hypotheses'] if thesis else []):
   for e in h['evidence']:
    if not e.get('locator'):
     attachments.append({'hypothesisId':h['id'],'evidenceId':e['id'],'status':'not-provided'});continue
    checked=locate(e)
    attachments.append({'hypothesisId':h['id'],'evidenceId':e['id'],'status':checked['status'],'sourcePath':checked['path'],'relativePath':'sources/'+checked['sha256']+'.pdf','sha256':checked['sha256'],'page':checked['page'],'quote':checked['quote']})
 relations=[]
 if include_originals:
  for rel in intent.get('issuerRelations',[]):
   if not rel.get('locator'):
    relations.append({'assetId':rel['assetId'],'status':'not-provided'});continue
   c=locate({'kind':'original','locator':rel['locator']})
   relations.append({'assetId':rel['assetId'],'status':c['status'],'sourcePath':c['path'],'relativePath':'sources/'+c['sha256']+'.pdf','sha256':c['sha256']})
 out=Path(out);export(result,out)
 for item in attachments+relations:
  if not item.get('relativePath'):continue
  target=out/item['relativePath'];target.parent.mkdir(exist_ok=True)
  if not target.exists():shutil.copy2(item['sourcePath'],target)
  if sha(target)!=item['sha256']:raise ValueError('原文副本发生变化')
 if include_originals:
  dump(out/'original-attachments.json',attachments);dump(out/'relation-attachments.json',relations)
 dump(out/'intent-input.json',intent)
 if portfolio is not None:dump(out/'portfolio-input.json',portfolio)
 if thesis is not None:dump(out/'thesis-reference.json',thesis)
 labels={'constraints-not-met':'按所给条件，存在未满足的约束','needs-data':'资料不足，尚不能确认所给约束全部满足','supplied-checks-met':'所提供检查项满足所给约束'}
 content=['# 买方研究包','', '**'+labels[result['status']]+'。这不是投资适当性或组合健康认证。**','', '研究用途：'+intent['intent']['purpose']+'。','', '本包保存资金用途、约束检查及原始计算输入。']
 for status,label in [('fail','当前最需要解释'),('unknown','仍不能判断')]:
  rows=[c for c in result['checks'] if c['status']==status]
  if rows:
   content+=['','## '+label,'']
   content += ['- '+c['name']+'：'+c['detail']+'。' for c in rows[:3]]
   if len(rows)>3:content+=['','其余项目见完整约束报告；首页仅展开前三项，不表示其他问题不存在。']
 content+=['', '判断更新取决于原始资料、所给约束或情景假设是否改变；不自行放宽阈值，也不把假设损失当成未来预测。','', '[查看完整组合约束](组合约束.html)','', '原始输入保留，已有目录不会覆盖。']
 if thesis is not None:
  e=result['thesisExposure']
  content+=['','## 与组合资金的联系','',e['entityId']+'直接持仓市值为'+format(e['linkedMarketValue'],',.2f')+' '+e['currency']+'，占组合'+format(e['portfolioWeightPct'],'.2f')+'%。这些持仓关联以下待验证逻辑：']
  for h in e['hypotheses']:
   content+=['','- '+h['claim']+'；需要观察'+h['verificationMetric']+'。首次档案状态：'+('尚未验证' if h['status']=='unverified' else h['status'])+'。']
   if h['evidenceNeedsRecheck']:content+=['','当前依据需要重查：'+'；'.join(h['recheckReasons'])+'。首次假设未改写，不能把旧依据作为当前已验证结论。']
  content+=['',e['limitation'],'','首次假设档案保持冻结；原文定位核对与投资假设验证分别说明。']
 if include_originals:
  for item in relations:
   if item.get('relativePath'):content+=['','发行人关系原件：[查看'+item['assetId']+'的原文]('+item['relativePath']+')。文件归档不代表关系语义已经认证。']
   else:content+=['','发行人关系'+item['assetId']+'尚无原文定位，本包仅保存输入声明。']
  for item in attachments:
   if item.get('relativePath'):content+=['','[查看证据原文]('+item['relativePath']+'#page='+str(item['page'])+')：PDF第'+str(item['page'])+'页；'+('引句已定位' if item['status']=='quote-located' else '引句尚未确认，需人工核对')+'。']
   else:content+=['','部分证据未提供PDF定位，本包原文覆盖不完整。']
  content+=['','原文副本用于本地复查，不授予对外再分发权。']
 elif thesis is not None:content+=['','未包含原文副本，外部路径可能失效，不能把本包称为完整原文档案。']
 content+=['','文件摘要是本地完整性清单，不是签名或真实性认证。研究包可能含用户持仓，分享前需自行确认范围。']
 md='\n'.join(content)
 from research_brief_html import render
 (out/'研究包.md').write_text(md,'utf-8');(out/'研究包.html').write_text(render(md,title='买方研究包'),'utf-8')
 files={p.relative_to(out).as_posix():sha(p) for p in out.rglob('*') if p.is_file()}
 dump(out/'manifest.json',{'version':1,'files':files,'methods':methods(),'hasPortfolio':portfolio is not None,'hasThesis':thesis is not None,'hasOriginals':include_originals,'resultSha256':digest(result),'limitations':['仅本地完整性和同版本重算检查','原文覆盖按实际附件说明；原文定位不等于投资判断认证']})
 return result

def replay(folder):
 folder=Path(folder).resolve();m=read_json(folder/'manifest.json')
 required={'intent-input.json','result.json','组合约束.md','组合约束.html','研究包.md','研究包.html'}
 if m.get('hasPortfolio'):required.add('portfolio-input.json')
 if m.get('hasThesis'):required.add('thesis-reference.json')
 if m.get('hasOriginals'):required.update(['original-attachments.json','relation-attachments.json'])
 if not required.issubset(m['files']):raise ValueError('清单缺少必需研究包文件')
 if m['methods']!=methods():raise ValueError('计算或报告方法版本变化，需另存新版重新验收')
 for name,expected in m['files'].items():
  p=(folder/name).resolve()
  if not p.is_relative_to(folder):raise ValueError('研究包引用越出目录')
  if not p.is_file() or sha(p)!=expected:raise ValueError('研究包文件缺失或变化:'+name)
 load=lambda name:read_json(folder/name)
 intent=load('intent-input.json');paths={}
 if m.get('hasOriginals'):
  relations=load('relation-attachments.json');expected={x['assetId']:x for x in intent.get('issuerRelations',[])}
  if len(relations)!=len(expected) or {x['assetId'] for x in relations}!=set(expected):raise ValueError('关系附件覆盖不一致')
  for item in relations:
   rel=expected[item['assetId']]
   if not item.get('relativePath'):
    if rel.get('locator'):raise ValueError('关系附件缺失')
    continue
   p=(folder/item['relativePath']).resolve()
   if not p.is_relative_to(folder) or item['relativePath'] not in m['files']:raise ValueError('关系附件引用无效')
   loc=copy.deepcopy(rel['locator']);loc['path']=str(p)
   if locate({'kind':'original','locator':loc})['status']!=item['status']:raise ValueError('关系定位重查不同')
   paths[item['assetId']]=str(p)
 r=link_portfolio(intent,load('portfolio-input.json'),paths) if m['hasPortfolio'] else analyze(intent,paths)
 if m['hasThesis']:r['thesisExposure']=thesis_exposure(intent,load('thesis-reference.json'))
 if digest(r)!=m['resultSha256'] or digest(load('result.json'))!=digest(r):raise ValueError('原始输入重算结果不一致')
 if m['hasThesis']:
  t=load('thesis-reference.json')
  if digest(t['snapshot'])!=t['snapshotSha256']:raise ValueError('假设引用摘要不一致')
 if m.get('hasOriginals'):
  evidence={(h['id'],e['id']):e for h in (t['snapshot']['hypotheses'] if m['hasThesis'] else []) for e in h['evidence']}
  attachments=load('original-attachments.json')
  if len(attachments)!=len(evidence) or {(x['hypothesisId'],x['evidenceId']) for x in attachments}!=set(evidence):raise ValueError('原文附件覆盖清单不一致')
  for item in attachments:
   e=copy.deepcopy(evidence[item['hypothesisId'],item['evidenceId']])
   if not item.get('relativePath'):
    if e.get('locator'):raise ValueError('原文定位附件缺失')
    continue
   p=(folder/item['relativePath']).resolve()
   if not p.is_relative_to(folder) or item['relativePath'] not in m['files']:raise ValueError('附件引用无效')
   e['locator']['path']=str(p)
   if locate(e)['status']!=item['status']:raise ValueError('原文定位重查结果不同')
 return {'status':'replayed-identical','constraintStatus':r['status'],'limitations':m['limitations']}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--portfolio-input',type=Path);p.add_argument('--thesis',type=Path);p.add_argument('--include-originals',action='store_true');p.add_argument('--out-dir',type=Path);p.add_argument('--replay',action='store_true');a=p.parse_args()
 if a.replay:print(json.dumps(replay(a.input),ensure_ascii=False))
 else:
  if not a.out_dir:p.error('构建需要--out-dir')
  load=read_json
  build(load(a.input),a.out_dir,load(a.portfolio_input) if a.portfolio_input else None,load(a.thesis) if a.thesis else None,a.include_originals)
