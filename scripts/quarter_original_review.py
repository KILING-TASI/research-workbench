"""Bind each quarter/comparator cumulative input to separately archived reports."""
import argparse,hashlib,json,re,shutil
from pathlib import Path
from industry_financials import analyze_company
from company_financial_report import original_checks,CHECK_FIELDS
from financial_source_binding import bound_originals,comparability_warnings,report_metadata_warnings
from research_brief_html import render
from company_report_batch import report_title_variants,report_identity_confirmed

def method_versions():
 names=['quarter_original_review.py','company_financial_report.py','industry_financials.py','financial_source_binding.py','research_report_reading.py','company_report_batch.py']
 return {name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() for name in names}

def review(archive,metadata,period,reports):
 calculation=analyze_company(archive,metadata,period)
 checks={};warnings=[]
 for report in reports:
  if report['code']!=archive['code']:raise ValueError('相邻报告证券代码不一致')
  if report['period'] in checks:raise ValueError('同一报告期有多个版本，需明确版本后核验')
  checks[report['period']]={c['metric']:c for c in original_checks(archive,report,report['period'])}
  warnings.extend(dict(period=report['period'],**w) for w in comparability_warnings(report))
 fields=[]
 for key in CHECK_FIELDS:
  metric=calculation['metrics'][key];parts={}
  for kind,entry in [('current',metric['current']),('yoy',metric['comparators']['yoy']),('qoq',metric['comparators']['qoq'])]:
   dependencies=[]
   for ref in entry['inputs']:
    check=checks.get(ref['period'],{}).get(key)
    dependencies.append(dict(period=ref['period'],field=ref['field'],status=check['status'] if check else 'report-missing',pages=[r['page'] for r in check['original']] if check else [],difference=check['difference'] if check else None,channelValue=check['expectedCumulativeOrStock'] if check else None,originalValues=check['original'] if check else []))
   matched=bool(dependencies) and all(x['status']=='matched' for x in dependencies) and entry['value'] is not None
   periods={d['period'] for d in dependencies}
   relevant_warnings=[w for w in warnings if w['period'] in periods]
   parts[kind]=dict(value=entry['value'],calculationReason=entry['reason'],status='supported-inputs-matched-with-comparability-warning' if matched and relevant_warnings else 'supported-inputs-matched' if matched else 'not-verified',dependencies=dependencies,comparabilityWarnings=relevant_warnings)
  fields.append(dict(metric=key,label=metric['label'],parts=parts,yoy=metric['yoy'],qoq=metric['qoq']))
 return dict(code=archive['code'],period=period,fields=fields,comparabilityWarnings=warnings,reportMetadataWarnings=[dict(period=r['period'],warning=w) for r in reports for w in report_metadata_warnings(r)],scope='七项支持字段逐个累计输入核对；不证明完整报表、合并范围一致或经营因果')

def load_inputs(spec):
 raw=Path(spec['archive']).read_bytes();archive=json.loads(raw);reports=[];bindings=[]
 for path in spec['originalResults']:
  result=json.loads(Path(path).read_text('utf-8-sig'))
  if result['asOf']!=archive['asOf']:raise ValueError('报告与财务截止日不一致')
  selected=dict(result,companies=[r for r in result['companies'] if r['code']==archive['code']])
  if len(selected['companies'])!=1:raise ValueError('报告包需包含唯一目标公司')
  bindings.extend(dict(period=result['period'],**b) for b in bound_originals(selected,path))
  for report in selected['companies']:
   if report['period']!=result['period']:raise ValueError('报告包期间与公司报告期间不一致')
   if report.get('parseStatus')=='parsed':
    if not report_identity_confirmed(report,archive['code']):raise ValueError('归档正文身份或报告期未确认')
  reports.extend(selected['companies'])
 return archive,raw,reports,bindings

def verified_saved_result(path,expected_archive,metadata,period):
 saved=json.loads(Path(path).read_text('utf-8-sig'));spec=saved['input']
 if saved.get('methodVersions')!=method_versions():raise ValueError('单季核验方法版本已变化或留痕不完整；需重新核验')
 if spec['metadata']!=metadata or spec['period']!=period:raise ValueError('单季核验与财务模型的口径或期间不一致')
 archive,raw,reports,bindings=load_inputs(spec)
 if archive!=expected_archive:raise ValueError('单季核验来源档案与底稿不一致')
 rebuilt=review(archive,metadata,period,reports)
 for key in ['code','period','fields','comparabilityWarnings','reportMetadataWarnings','scope']:
  if saved.get(key)!=rebuilt[key]:raise ValueError('单季核验状态与重新核对不一致：'+key)
 if saved.get('archiveSha256')!=hashlib.sha256(raw).hexdigest() or saved.get('originalBindings')!=bindings:raise ValueError('单季核验来源文件绑定已变化')
 return saved

def dependency_note(label,dep):
 prefix=label+'，'+dep['period']+'：'
 state=dep['status']
 if state=='difference':
  values=[str(v['convertedValueCNY']) for v in dep.get('originalValues',[]) if v.get('convertedValueCNY') is not None]
  original='、'.join(values) if values else '尚未确认'
  return prefix+'渠道累计或期末值为'+str(dep.get('channelValue'))+'元，原文换算值为'+original+'元；差额（渠道减原文）为'+str(dep.get('difference'))+'元。差异原因尚未确认，不自动采用其中一个值。'
 if state=='unit-unconfirmed':return prefix+'原文金额单位或币种未确认，无法换算比较；不把未确认数值当作零。'
 if state=='report-missing':return prefix+'缺少所需报告，无法完成该项输入核验。'
 if state!='matched':return prefix+'该输入尚未确认，需复核原文定位、金额及比较列，不能以已取得报告代替数值核验。'
 return None

def run(spec,out):
 out=Path(out)
 if out.exists():raise FileExistsError('输出目录已存在')
 archive,raw,reports,bindings=load_inputs(spec)
 result=review(archive,spec['metadata'],spec['period'],reports)
 result.update(archiveSha256=hashlib.sha256(raw).hexdigest(),codeSha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),originalBindings=bindings,methodVersions=method_versions())
 result['input']=spec
 out.mkdir(parents=True);(out/'sources').mkdir()
 for b in bindings:shutil.copy2(b['path'],out/'sources'/(b['period']+'.pdf'))
 lines=['# 单季度财报输入核验','',archive['code']+' · '+spec['period']+'。分别核对当季、同比基数和环比基数所用的累计报告值。','','|指标|本期输入|同比基数输入|环比基数输入|','|---|---|---|---|']
 labels={'supported-inputs-matched':'支持输入已匹配','supported-inputs-matched-with-comparability-warning':'数值匹配，跨期口径待复核','not-verified':'尚未核验完整'}
 references=[]
 for f in result['fields']:
  lines.append('|'+f['label']+'|'+'|'.join(labels[f['parts'][k]['status']] for k in ['current','yoy','qoq'])+'|')
  for k,p in f['parts'].items():
   for dep in p['dependencies']:
    if dep['pages']:references.append(f['label']+'：'+dep['period']+'，'+ '、'.join('[原文第'+str(page)+'页](sources/'+dep['period']+'.pdf#page='+str(page)+')' for page in dep['pages'])+'。')
    note=dependency_note(f['label'],dep)
    if note:references.append(note)
 lines+=['','## 各项输入原文依据','',*dict.fromkeys(references)]
 for w in result['comparabilityWarnings']:lines.append(w['period']+'：'+w['warning'])
 for w in result['reportMetadataWarnings']:lines.append(w['period']+'：'+w['warning'])
 lines+=['','## 核验范围',result['scope'],'数值匹配不保证会计政策或合并范围相同；重述提示保留，不将机械差分当成可比性证明。未覆盖字段仍需另核验。']
 md='\n'.join(lines);(out/'单季输入核验.md').write_text(md,'utf-8');(out/'单季输入核验.html').write_text(render(md,title='单季度财报输入核验'),'utf-8');(out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf-8');return result

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--out-dir',type=Path,required=True);a=p.parse_args();run(json.loads(a.input.read_text('utf-8-sig')),a.out_dir)
