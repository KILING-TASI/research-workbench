"""Prepare numeric raw inputs for formula-driven financial workbook, no invented zeros."""
import argparse,hashlib,json
from pathlib import Path
from collection_validation import unique_pairs,reject_constant,finite_json_float

def load_json(text):
 value=json.loads(text,object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float)
 if not isinstance(value,dict):raise ValueError("底稿关联JSON须为对象")
 return value

from industry_financials import FIELDS,observation,previous,value,applicability_notes,metadata_unit_warnings
from financial_source_binding import bound_archives,bound_originals,verify_financial_snapshot,comparability_warnings,income_basis_warnings,report_metadata_warnings

def verify_commentary_coverage(saved,financial):
 if 'coverage' not in saved:return 'legacy-coverage-not-recorded'
 if saved['coverage']!=financial.get('coverage',{}) or saved.get('failures')!=financial.get('failures',[]):raise ValueError('点评样本覆盖或失败清单与财务输入不一致')
 by_code={c['code']:c for c in financial['companies']}
 for item in saved.get('companies',[]):
  if item['code'] not in by_code:raise ValueError('点评覆盖存在样本外公司')
  if any(g not in item.get('gaps',[]) for g in by_code[item['code']].get('gaps',[])):raise ValueError('点评遗漏已登记的财务字段缺口')
  pending=['待核实问题：'+q for entry in item.get('interpretations',[]) for q in entry.get('followUp',[])]
  if any(q not in item.get('gaps',[]) for q in pending):raise ValueError('点评遗漏待核实问题的研究缺口')
 return 'financial-coverage-and-gaps-matched'

def verified_commentary_checks(spec,financial,original,archives):
 if not spec.get('commentaryResult'):return []
 saved=load_json(Path(spec['commentaryResult']).read_text(encoding='utf8'))
 if saved.get('envelopeSha256'):
  raw={k:v for k,v in saved.items() if k!='envelopeSha256'}
  actual=hashlib.sha256(json.dumps(raw,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode('utf8')).hexdigest()
  if actual!=saved['envelopeSha256']:raise ValueError('点评整体摘要不一致，内容或核验状态已修改')
 if saved.get('period')!=financial['period']:raise ValueError('点评与财务所属期不一致')
 for key in ['financialResult','originalResult']:
  if saved.get('inputHashes',{}).get(key)!=hashlib.sha256(Path(spec[key]).read_bytes()).hexdigest():
   raise ValueError('点评绑定的输入与本次底稿不一致：'+key)
 items=saved.get('companies',[])
 codes=[item.get('code') for item in items]
 if len(codes)!=len(set(codes)) or set(codes)!={c['code'] for c in financial['companies']}:
  raise ValueError('点评公司集合与财务样本不一致')
 verify_commentary_coverage(saved,financial)
 from company_financial_report import original_checks,checked_interpretation,checked_comparisons
 reports={r['code']:r for r in original['companies']}
 for item in items:
  report=reports.get(item['code'])
  expected=original_checks(archives[item['code']],report,financial['period']) if report else []
  if item.get('checks')!=expected:
   raise ValueError('点评原文核验状态与重新核对不一致：'+item['code'])
  if 'comparativeChecks' in item:
   expected_comparative=original_checks(archives[item['code']],report,financial['period'],column='comparative') if report else []
   if item['comparativeChecks']!=expected_comparative:raise ValueError('点评比较列核验与重新核对不一致：'+item['code'])
  if item.get('reportHash')!=(report.get('fileSha256') if report else None):
   raise ValueError('点评报告哈希与本次原文不一致')
  for entry in item.get('interpretations',[]):
   if not report or report.get('parseStatus')!='parsed':raise ValueError('经营点评缺少可解析原文')
   checked=checked_interpretation(entry,report)
   if any(entry.get(key)!=checked[key] for key in ['basis','evidence','followUp','status']):
    raise ValueError('经营点评的引句或待核实状态与原文不一致')
 verify_saved_comparisons(saved,reports,set(codes),checked_comparisons)
 return items

def verify_saved_comparisons(saved,reports,codes,checker=None):
 if checker is None:
  from company_financial_report import checked_comparisons
  checker=checked_comparisons
 rows=saved.get('comparisons',[]);inputs=[]
 for row in rows:
  assessment=row.get('underlyingSourceAssessment')
  inputs.append({**row,'underlyingSources':assessment.get('declaredSources') if isinstance(assessment,dict) else None})
 expected=checker(inputs,reports,codes)
 if rows!=expected:raise ValueError('跨公司点评的引句、状态或底层来源说明与重新核对不一致')
 return expected

def financial_stage_limitations(financial):
 rows=financial['limitations']
 if not isinstance(rows,list) or any(not isinstance(x,str) for x in rows):raise ValueError('财务限制须为文字列表')
 return [('结构化财务计算阶段不获取公告正文；本次原文取得和核验状态见来源与覆盖，经营原因和未来展望不由数字推断' if x=='未自动获取公告正文，经营原因和未来展望不由数字推断' else x) for x in rows]

def verify_quarter_alignment(commentary,quarters):
 by_code={q['code']:q for q in quarters}
 for item in commentary:
  declared=item.get('quarterOriginalChecks')
  if declared is None:continue
  if item['code'] not in by_code:raise ValueError('点评已含单季核验，底稿须关联对应结果，不能静默丢弃')
  if declared!=by_code[item['code']]:raise ValueError('点评与底稿的单季核验版本或状态不一致')

def prepare(spec):
 if not isinstance(spec,dict):raise ValueError('底稿输入须为对象')
 paths=[spec['financialResult'],spec['originalResult']]
 if spec.get('commentaryResult'):paths.append(spec['commentaryResult'])
 if not isinstance(spec.get('archives'),list) or not isinstance(spec.get('quarterReviewResults',[]),list):raise ValueError('档案和单季核验路径须为列表')
 paths+=spec['archives']+spec.get('quarterReviewResults',[])
 initial_hashes={str(Path(p).resolve()):hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths}
 fin=load_json(Path(spec['financialResult']).read_text(encoding='utf8'));original=load_json(Path(spec['originalResult']).read_text(encoding='utf8'));period=fin['period'];prior=previous(period);yearago=str(int(period[:4])-1)+period[4:];dates=[period,previous(period),yearago,previous(yearago),prior,previous(prior)]
 bound_originals(original,spec['originalResult'])
 archives,_=bound_archives(fin,spec['archives'])
 verify_financial_snapshot(fin,archives)
 rows=[];sources=[]
 for c in fin['companies']:
  a=archives[c['code']]
  for key,(kind,field,label,flow) in FIELDS.items():
   observations=[observation(a,kind,d,field) for d in dates];rawvalues=[x[0] for x in observations];verified=[value(a,key,d) for d in [period,yearago,prior]]
   rows.append(dict(code=c['code'],name=c['metadata'].get('name',c['code']),key=key,label=label,flow=flow,dates=dates,values=rawvalues,calculate=[x['value'] is not None for x in verified],subtract=[flow and d[5:7]!='03' for d in [period,yearago,prior]],expected=[x['value'] for x in verified],yoy=c['metrics'][key]['yoy'],qoq=c['metrics'][key]['qoq'],unit=c['metadata']['unit'],group=c['metadata']['group']))
   for date,(_,reason,refs) in zip(dates,observations):
    for ref in refs:sources.append(dict(code=c['code'],metric=label,field=field,period=date,publishedAt=ref['publishedAt'],table=kind,url=a['tables'][kind]['sources'][0] if a['tables'][kind]['sources'] else None,archiveSha256=c['archiveSha256'],reason=reason))
 checks=verified_commentary_checks(spec,fin,original,archives)
 quarter_checks=[]
 if spec.get('quarterReviewResults'):
  from quarter_original_review import verified_saved_result
  by_code={c['code']:c for c in fin['companies']};seen=set()
  for path in spec['quarterReviewResults']:
   supplied=load_json(Path(path).read_text('utf-8-sig'));code=supplied['code']
   if code in seen or code not in by_code:raise ValueError('单季核验公司重复或不在底稿范围')
   seen.add(code);quarter_checks.append(verified_saved_result(path,archives[code],by_code[code]['metadata'],period))
 verify_quarter_alignment(checks,quarter_checks)
 warnings=[dict(code=c['code'],**w) for c in original['companies'] for w in comparability_warnings(c)]
 basis_warnings=[dict(code=c['code'],**w) for c in fin['companies'] for w in income_basis_warnings(archives[c['code']],period)]
 result=dict(quarterOriginalChecks=quarter_checks,incomeBasisWarnings=basis_warnings,comparabilityWarnings=warnings,originalChecks=checks,period=period,rows=rows,companies=fin['companies'],groups=fin['groups'],coverage=original['companies'],sources=sources,limitations=financial_stage_limitations(fin)+[c['code']+'：'+note for c in fin['companies'] for note in applicability_notes(c)+metadata_unit_warnings(c['metadata'])]+[c['code']+'：'+w for c in original['companies'] for w in report_metadata_warnings(c)]+[w['code']+'：'+w['warning'] for w in basis_warnings]+[w['code']+'：'+w['warning'] for w in warnings]+(['历史点评无整体摘要时仅复核引句和状态，研究解释文本未获完整性认证'] if spec.get('commentaryResult') and not load_json(Path(spec['commentaryResult']).read_text('utf8')).get('envelopeSha256') else [])+['报表范围和单位为声明，未经核验的输入不写作原文确认','Excel公式基于原始累计值；多期核验仅覆盖所列字段，未列字段不视为原文已确认'])
 for path,digest in initial_hashes.items():
  if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=digest:raise ValueError('底稿准备期间关联文件变化，须重新计算：'+path)
 result['inputFileHashes']=initial_hashes
 return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 if a.out.exists():raise FileExistsError('输出已存在')
 a.out.write_text(json.dumps(prepare(load_json(a.input.read_text(encoding='utf8'))),ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')
