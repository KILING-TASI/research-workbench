"""Batch registered research impact checks, reusing the existing integrity gate."""
import argparse,json
from pathlib import Path
from research_workflow import impact,load

def analyze(spec):
 if not isinstance(spec,dict):raise ValueError('批量研究请求须为对象')
 rows=spec.get('researches')
 if not isinstance(rows,list) or not rows:raise ValueError('需提供研究记录列表')
 seen=set();records=[];registered=set()
 for row in rows:
  if not isinstance(row,dict):raise ValueError('研究记录须为对象')
  for key in ['id','label','resultPath']:
   if not isinstance(row.get(key),str) or not row[key].strip():raise ValueError('研究记录缺少'+key)
  if row['id'] in seen:raise ValueError('研究编号重复')
  if row.get('newContextPath') is not None and (not isinstance(row['newContextPath'],str) or not row['newContextPath'].strip()):raise ValueError('新上下文路径须为非空文字')
  seen.add(row['id']);old=load(row['resultPath']);impact(old)
  paths={r['path'] for r in old['lineage']['files']};registered.update(paths);records.append((row,old,paths))
 replacements=spec.get('replacements',{})
 if not isinstance(replacements,dict) or set(replacements)-registered:raise ValueError('替换来源未在所选研究登记')
 results=[];sources={}
 for row,old,paths in records:
  check=impact(old,new_context_path=row.get('newContextPath'),replacements={k:v for k,v in replacements.items() if k in paths})
  affected=[]
  for index,calc in enumerate(old['lineage']['calculations'],1):
   reasons=[]
   for reason in check['reasons']:
    if reason['type'] in ['file-changed','file-missing']:
     registered=[k for k in paths if replacements.get(k,k)==reason['path']]
     if set(registered)&set(calc.get('dependsOnFiles',[])):reasons.append(reason)
    elif reason['type']=='code-changed' and reason['module'] in {c['module'] for c in calc['code']}:reasons.append(reason)
    elif reason['type']=='parameter':reasons.append(reason)
   if reasons:affected.append(dict(calculationId=calc.get('id'),registeredPosition=index,function=calc.get('function'),reasons=reasons,scope='登记计算依赖待重验；未自动推断所有正文结论'))
  results.append({'id':row['id'],'label':row['label'],'resultPath':row['resultPath'],'check':check,'affectedCalculations':affected})
  for reason in check['reasons']:
   key=reason.get('path') if reason['type'] in ['file-changed','file-missing'] else None
   if key and row['id'] not in sources.setdefault(key,[]):sources[key].append(row['id'])
 return {'type':'batch-research-impact','researches':results,'affectedResearchIds':[r['id'] for r in results if r['check']['impactStatus']=='stale'],'sourceImpacts':[{'path':p,'researchIds':ids} for p,ids in sorted(sources.items())],'limitation':'仅复查所选已登记研究依赖，不自动发现所有历史报告；文件变化不等于经营事实变化，不自动重写结论或认证新版本原文'}

def export(result,out):
 from research_brief_html import render
 out=Path(out);out.mkdir(parents=True,exist_ok=False)
 affected=[r for r in result['researches'] if r['id'] in result['affectedResearchIds']]
 lines=['# 多份研究的影响复查','',('需要重查的研究：'+'、'.join(r['label'] for r in affected)+'。' if affected else '所选研究的已登记本地依赖未发现变化；远程公告仍需另行检查。'),'']
 for r in result['researches']:
  lines+=['## '+r['label'],'当前状态：'+('需要重新核对' if r['id'] in result['affectedResearchIds'] else '登记依赖未发现变化')+'。']
  displayed=set()
  for reason in r['check']['reasons']:
   identity=(reason['type'],reason.get('path'),reason.get('module'),reason.get('field'))
   if identity in displayed:continue
   displayed.add(identity)
   labels={'file-changed':'来源文件已变化','file-missing':'来源文件缺失','code-changed':'方法版本变化','parameter':'研究参数变化'}
   lines+=[labels[reason['type']]+'：'+str(reason.get('path',reason.get('module',reason.get('field',''))))+'。']
   actions={'file-changed':'先对照新旧来源，核对依赖该文件的数字和判断；文件变化本身不能证明经营事实变化。','file-missing':'先恢复或补取已登记来源；在重新核验之前，依赖该来源的结论不能作为已复核结果引用。','code-changed':'按新方法重算并比较结果，说明口径变化；不能直接把数值差异解释为标的表现变化。','parameter':'按新参数重新计算并标注假设变化；旧结论不能直接套用到新情景。'}
   lines+=['下一步：'+actions[reason['type']]]
  for calc in r.get('affectedCalculations',[]):lines+=['需重新验收的登记计算：'+str(calc['calculationId'] or ('记录第'+str(calc['registeredPosition'])+'项'))+'。这里只关联已登记计算，尚未逐条定位正文判断。']
  lines+=['']
 lines+=['## 复查范围',result['limitation']];md='\n'.join(lines)
 html=render(md,title='多份研究影响复查');payload=json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)
 (out/'result.json').write_text(payload,'utf-8');(out/'研究影响复查.md').write_text(md,'utf-8');(out/'研究影响复查.html').write_text(html,'utf-8')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--out-dir',required=True,type=Path);a=p.parse_args();export(analyze(load(a.input)),a.out_dir)
