"""Three research questions, reusing raw-input checks rather than trusting old reports."""
import argparse,json,copy,hashlib
from pathlib import Path
from datetime import date
from collection_validation import day,unique_pairs,reject_constant,finite_json_float

def run(spec,out):
 if not isinstance(spec,dict):raise ValueError('研究请求须为对象')
 serialized_input=json.dumps(spec,sort_keys=True,ensure_ascii=False,allow_nan=False)
 from research_brief_html import render
 from investment_intent import analyze,export,issuer_exposure
 from buy_side_thesis import timing,locate,review,markdown
 mode=spec.get('entry');out=Path(out)
 if out.exists():raise FileExistsError('输出目录须为新目录')
 if mode not in ['holdings','news','logic']:raise ValueError('入口须为holdings、news或logic')
 if mode=='holdings':
  result=analyze(spec['input']);title='我的持仓有什么问题'
  out.mkdir(parents=True);export(result,out/'details')
  # Use the existing report filename, not a new parallel calculation.
  reports=list((out/'details').glob('*.md'))
  body=reports[0].read_text('utf-8')
  failures=[c['name'] for c in result['checks'] if c['status']=='fail'];unknown=[c['name'] for c in result['checks'] if c['status']=='unknown']
  lead=('需要关注：'+'、'.join(failures)+'。' if failures else '已提供检查项未发现约束失败。')+(' 尚待补齐：'+'、'.join(unknown)+'。' if unknown else '')
  body='# '+title+'\n\n'+lead+'\n\n这次只检查已提供的资金用途、持仓与阈值，不是完整持仓健康认证。\n\n'+body
 elif mode=='logic':
  result=review(spec['snapshot'],spec['input']);title='我之前看好的逻辑，现在还成立吗'
  counts={key:sum(x['outcome']==key for x in result['assessments']) for key in ['supported','contradicted','unverified']}
  body='# '+title+'\n\n现有研究判断中，'+str(counts['supported'])+'项得到材料支持，'+str(counts['contradicted'])+'项受到反驳，'+str(counts['unverified'])+'项尚未验证。这些是所提供判断，不是程序自动认证。\n\n'+markdown(result)
  out.mkdir(parents=True)
 else:
  title='这条消息对我的持仓有什么影响';request=spec['input'];cutoff=day(request['asOf']);event=copy.deepcopy(request['event'])
  for key in ['entityId','title','source','publishedAt','acquiredAt']:
   if not isinstance(event.get(key),str) or not event[key].strip():raise ValueError('消息缺少'+key)
  check=timing(event,cutoff);eligible=not check['reasons'] and check['effectiveStatus']!='not-yet-effective'
  location=locate({'kind':'original','locator':event.get('locator')}) if eligible else {'status':'excluded-by-time'}
  if location['status']=='quote-not-found':eligible=False
  holdings=request['holdings'];seen=set();related=[]
  if not isinstance(request.get('currency'),str) or not request['currency'].strip():raise ValueError('须明确组合币种')
  from investment_intent import nonnegative
  total=0
  for h in holdings:
   if h.get('currency')!=request['currency']:raise ValueError('持仓币种不一致，需先明确换算')
   if h['assetId'] in seen:raise ValueError('持仓重复，须先合并')
   seen.add(h['assetId']);total+=nonnegative(h['marketValue'])
  if total<=0:raise ValueError('组合市值须为正')
  if eligible:
   for h in holdings:
    if h['assetId']==event['entityId']:related.append(dict(assetId=h['assetId'],marketValue=str(nonnegative(h['marketValue'])),relation='direct-asset'))
   if request.get('issuerRelations'):
    exposure=issuer_exposure(dict(asOf=request['asOf'],holdings=holdings,issuerRelations=request['issuerRelations'],intent={}))
    for group in exposure['groups']:
     if group['issuerId']==event['entityId']:
      for rel in group['assets']:
       h=next(h for h in holdings if h['assetId']==rel['assetId'])
       if not any(x['assetId']==h['assetId'] for x in related):related.append(dict(assetId=h['assetId'],marketValue=str(nonnegative(h['marketValue'])),relation='declared-direct-issuer'))
  related_value=sum(nonnegative(x['marketValue']) for x in related)
  result=dict(type='retail-event-exposure',asOf=request['asOf'],event=event,timingCheck=check,locationCheck=location,eligible=eligible,relatedHoldings=related,relatedValue=str(related_value),relatedWeightPct=str(related_value/total*100),status='related-for-research' if related else 'needs-evidence' if not eligible else 'no-known-direct-match',limitations=['关联市值不是事件损失，不能由标题推断股价影响','无直接匹配不等于不受影响；基金底层、行业和控制链需另核','日期、主体和影响路径来自输入声明，原文引句定位不认证语义'])
  lead='已识别相关持仓市值'+str(related_value)+'，占所给组合'+str(result['relatedWeightPct'])+'%。这不是预计损失。' if related else '目前没有可以确认的直接持仓关联；不能据此判断消息无影响。'
  body='# '+title+'\n\n'+lead+'\n\n## 消息依据\n\n'+event['title']+'\n\n来源：'+event['source']+'；披露日：'+event['publishedAt']+'；取得日：'+event['acquiredAt']+'。\n\n'
  body+='原文检查：'+{'quote-located':'引句已在指定页定位','file-page-only':'仅核对文件与页码','not-located':'未提供原文定位，仅为输入声明','quote-not-found':'引句未找到，需复核','excluded-by-time':'当前时点未采用'}[location['status']]+'。\n\n'
  if not eligible:body+='消息未用于当前关联判断：'+'；'.join(check['reasons'] or ['生效或原文定位尚待核实'])+'。\n\n'
  body+='## 关联与待验证路径\n\n'
  for h in related:body+=h['assetId']+'：关联市值'+h['marketValue']+'。\n\n'
  body+=(event.get('impactPath') or '尚未提供收入、现金流、信用或治理影响路径，需要阅读原文后核实。')+'\n\n影响路径为待验证解释，不是因果结论。\n\n## 研究边界\n\n'+'\n\n'.join(result['limitations'])
  out.mkdir(parents=True)
 (out/'研究结果.md').write_text(body,'utf-8');(out/'研究结果.html').write_text(render(body,title=title),'utf-8')
 wrapper=dict(entry=mode,result=result,inputSha256=hashlib.sha256(serialized_input.encode()).hexdigest())
 (out/'input.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2),'utf-8');(out/'result.json').write_text(json.dumps(wrapper,ensure_ascii=False,indent=2),'utf-8')
 return wrapper

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--out-dir',type=Path,required=True);a=p.parse_args();run(json.loads(a.input.read_text('utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float),a.out_dir)
