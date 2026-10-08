"""Company-pool statements -> report coverage -> commentary -> optional workbook."""
import argparse,json,shutil,subprocess
from pathlib import Path
from stock_statements import collect,validate
from company_report_batch import run as reports,acquisition_summary,acquisition_lines
from industry_financials import run as financials
from company_financial_report import run as commentary,CHECK_FIELDS
from financial_workbook_inputs import prepare
from research_brief_html import render
from export_runtime import component_environment,verify_workbook
from collection_validation import unique_pairs,reject_constant

def verification_summary(data,codes):
 def identities(checks):
  declared=[c.get('metric') for c in checks if 'metric' in c]
  if any(not isinstance(key,str) or key not in CHECK_FIELDS for key in declared) or len(declared)!=len(set(declared)):raise ValueError('原文核验字段未知或重复，不按条数重复计算')
  return bool(checks) and len(declared)==len(checks)
 rows=[]
 indexed={c['code']:c for c in (data or {}).get('companies',[])}
 for code in codes:
  checks=indexed.get(code,{}).get('checks',[]);counts={}
  for check in checks:counts[check['status']]=counts.get(check['status'],0)+1
  comparative=indexed.get(code,{}).get('comparativeChecks',[]);comparative_counts={}
  current_identity=identities(checks);comparative_identity=identities(comparative)
  for check in comparative:comparative_counts[check['status']]=comparative_counts.get(check['status'],0)+1
  expected=len(CHECK_FIELDS);matched=counts.get('matched',0)
  warnings=indexed.get(code,{}).get('comparabilityWarnings',[])
  research_gaps=indexed.get(code,{}).get('gaps',[])
  research_gaps=list(research_gaps)
  if not current_identity or not comparative_identity:research_gaps.append('本期或比较列未完整登记字段身份；匹配条数不能证明字段覆盖')
  rows.append(dict(code=code,matched=matched,differences=counts.get('difference',0),unverified=max(expected-matched-counts.get('difference',0),0),supportedFieldCount=expected,statusCounts=counts,comparabilityWarnings=warnings,researchGaps=research_gaps,reportMetadataWarnings=indexed.get(code,{}).get('reportMetadataWarnings',[]),comparativePeriodVerified=False,comparativeColumnStatusCounts=comparative_counts,comparativeColumnMatched=comparative_counts.get('matched',0),comparativeColumnDifferences=comparative_counts.get('difference',0),comparativeColumnUnverified=max(expected-comparative_counts.get('matched',0)-comparative_counts.get('difference',0),0),comparativeColumnScope='利润和现金流为去年同期累计；资产负债为上年末；非全部单季同比输入'))
 return dict(companies=rows,scope='当前支持字段的报告累计值及期末值；不是所有科目或单季计算的完整核验')

def appraisal_summary(data,codes):
 from appraisal_contract import coverage
 indexed={c['code']:c for c in (data or {}).get('companies',[])}
 rows=[]
 for code in codes:
  entries=indexed.get(code,{}).get('interpretations',[])
  rows.append(dict(code=code,**coverage(entries)))
 return dict(companies=rows,scope='评价结构与引句齐备程度，非语义准确率')

def quarter_verification_summary(reviews,codes,requested):
 indexed={}
 for review in reviews:
  code=review['code']
  if code not in codes or code in indexed:raise ValueError('单季核验公司重复或不在本次样本')
  indexed[code]=review
 rows=[]
 for code in codes:
  review=indexed.get(code);counts={'matched':0,'comparabilityWarning':0,'unverified':0};fields={}
  for field in (review or {}).get('fields',[]):
   key=field['metric']
   if key not in CHECK_FIELDS or key in fields:raise ValueError('单季核验字段重复或超出支持范围')
   fields[key]=field
  for metric in CHECK_FIELDS:
   for part in ['current','yoy','qoq']:
    entry=fields.get(metric,{}).get('parts',{}).get(part,{})
    dependencies=entry.get('dependencies',[])
    proven=entry.get('value') is not None and bool(dependencies) and all(d.get('status')=='matched' for d in dependencies)
    state=entry.get('status')
    if proven and state=='supported-inputs-matched':counts['matched']+=1
    elif proven and state=='supported-inputs-matched-with-comparability-warning':counts['comparabilityWarning']+=1
    else:counts['unverified']+=1
  rows.append(dict(code=code,requested=requested,reviewAvailable=review is not None,supportedInputGroupCount=len(CHECK_FIELDS)*3,reportMetadataWarnings=(review or {}).get('reportMetadataWarnings',[]),comparabilityWarnings=(review or {}).get('comparabilityWarnings',[]),**counts))
 return dict(companies=rows,scope='当前登记支持字段的本期单季及同比、环比基数输入组；不代表全部财务科目核验')


def delivery_assessment(stages,summary,quarter,issues):
 gaps=list(issues)
 for key in ['reports','financials','commentary','excel']:
  if stages.get(key)!='completed':gaps.append(key+'交付尚未完成')
 for row in summary['companies']:
  gaps.extend(row['code']+'：'+reason for reason in row.get('researchGaps',[]))
  if row['matched']!=row['supportedFieldCount'] or row['comparativeColumnMatched']!=row['supportedFieldCount']:gaps.append(row['code']+'本期或比较列未全部匹配支持字段')
  if row['comparabilityWarnings'] or row['reportMetadataWarnings']:gaps.append(row['code']+'原文身份或跨期口径仍需复核')
 for row in quarter['companies']:
  if row.get('reportMetadataWarnings'):gaps.append(row['code']+'相邻报告披露日期或版本关系仍需复核')
  if row.get('comparabilityWarnings'):gaps.append(row['code']+'相邻期报表可比性仍需复核')
  if not row['requested']:gaps.append(row['code']+'未核验相邻期单季输入')
  elif row['matched']!=row['supportedInputGroupCount']:gaps.append(row['code']+'单季及比较基数输入未全部匹配')
 gaps=list(dict.fromkeys(gaps))
 return dict(status='partial' if gaps else 'supported-scope-verified',gaps=gaps,scope='指定样本当前登记支持字段及其计算输入；不证明全三表、全文阅读或全行业研究完成',note='仍有交付或核验缺口，已成功的成果可单独使用。' if gaps else '指定样本的支持字段与计算输入已核对，仍应按本次范围使用。')

def delivery_gaps(result):
 return list(dict.fromkeys([*result.get('issues',[]),*result.get('deliveryAssessment',{}).get('gaps',[])]))

def commentary_options(spec):
 result={}
 for key in ['interpretations','comparisons']:
  file_key=key+'Path'
  if spec.get(file_key) and key in spec:
   raise ValueError(key+'同时给出文件和直接内容，不能静默选择')
  if spec.get(file_key):result[key]=json.loads(Path(spec[file_key]).read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant)
  elif key in spec:result[key]=spec[key]
  if key in result and not isinstance(result[key],list):
   raise ValueError(key+'需列表')
 return result

def report_request(period,asof,companies,resume_from=None):
 request=dict(period=period,asOf=asof,companies=companies)
 if resume_from is not None:
  if not isinstance(resume_from,str) or not resume_from.strip():raise ValueError('原文续采路径需非空字符串')
  request['resumeFrom']=resume_from
 return request

def document_formats(spec):
 formats=spec.get('exportFormats',[])
 if not isinstance(formats,list) or any(x not in ['docx','pptx'] for x in formats) or len(set(formats))!=len(formats):raise ValueError('exportFormats需不重复的docx/pptx列表')
 return formats

def export_documents(spec,out,commentary_ready,node=None,env=None):
 """Keep optional format failure separate from completed research steps."""
 import hashlib
 formats=document_formats(spec);out=Path(out);results={};issues=[]
 source=out/'commentary/公司与行业点评.md'
 for fmt in formats:
  label={'docx':'Word','pptx':'PPT'}[fmt]
  if not commentary_ready or not source.is_file():
   results[fmt]={'status':'dependency-missing','reason':'点评正文尚未完成'};issues.append(label+'未生成：点评正文尚未完成；已有取数及核验结果保留。');continue
  request=dict(markdownPath=str(source.resolve()),markdownSha256=hashlib.sha256(source.read_bytes()).hexdigest(),outDir=str((out/(fmt+'-export')).resolve()))
  try:
   if fmt=='docx':
    from export_financial_docx import export
    exported=export(request)
   else:
    if not node:raise ImportError('缺少可用Node运行时')
    request['fontFamily']=spec.get('fontFamily')
    request_path=out/'pptx-export-input.json';request_path.write_text(json.dumps(request,ensure_ascii=False,indent=2),encoding='utf-8')
    process=subprocess.run([node,str(Path(__file__).with_name('export_financial_pptx.mjs')),str(request_path)],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=180,env=env)
    if process.returncode:raise RuntimeError(process.stderr[-1200:])
    exported=json.loads((out/'pptx-export/export-result.json').read_text(encoding='utf-8'))
   manifest_path=out/(fmt+'-export')/'export-result.json'
   manifest_hash=hashlib.sha256(manifest_path.read_bytes()).hexdigest()
   results[fmt]={'status':'generated-awaiting-review','bodySha256':request['markdownSha256'],'exportManifestSha256':manifest_hash,'export':exported}
   issues.append(label+'已生成，尚需最终文件及逐页排版验收；不因导出成功认定研究完整。')
  except (ImportError,ModuleNotFoundError) as exc:
   results[fmt]={'status':'dependency-missing','reason':str(exc)};issues.append(label+'导出组件不可用；已完成的研究及底稿保留。')
  except Exception as exc:
   results[fmt]={'status':'failed','reason':str(exc)};issues.append(label+'导出未完成；已完成的研究及底稿保留。')
 return results,issues

def run(spec,out,node=None,artifact_node_modules=None):
 if not isinstance(spec,dict):raise ValueError('财务研究输入须为对象')
 if not isinstance(spec.get('companies'),list) or any(not isinstance(c,dict) or not isinstance(c.get('code'),str) for c in spec['companies']):raise ValueError('公司池须为有字符串代码的对象列表')
 export_env=component_environment(artifact_node_modules)
 verification_data=None
 payload=None
 if 'verifyQuarterInputs' in spec and type(spec['verifyQuarterInputs']) is not bool:raise ValueError('verifyQuarterInputs需明确布尔值')
 period=spec['period'];asof=spec['asOf'];companies=spec['companies'];codes=[c['code'] for c in companies]
 if not 1<=len(codes)<=20 or len(set(codes))!=len(codes):raise ValueError('需1至20家不重复公司')
 for c in companies:
  validate(c['code'],period,asof)
  meta=c.get('metadata')
  if not isinstance(meta,dict):raise ValueError(c['code']+'需提供公司研究口径 metadata')
  if meta.get('scope') not in ['consolidated','parent']:raise ValueError(c['code']+'需明确报表范围 consolidated 或 parent')
  for field,label in [('currency','币种'),('unit','单位'),('classificationVersion','分组版本')]:
   if not isinstance(meta.get(field),str) or not meta[field].strip():raise ValueError(c['code']+'需明确'+label+'，取数前不能猜测口径')
 formats=document_formats(spec)
 if 'pptx' in formats and (not isinstance(spec.get('fontFamily'),str) or not spec['fontFamily'].strip()):raise ValueError('PPT导出需先指定fontFamily；目标字体可用性及排版仍需验收')
 if spec.get('originalResumeFrom'):
  resume=Path(spec['originalResumeFrom'])
  if not resume.is_file():raise ValueError('originalResumeFrom需指向原文归档result.json文件，不能使用目录或缺失路径')
 prepared_commentary=commentary_options(spec)
 out=Path(out);out.mkdir(parents=True,exist_ok=False);archives=[];issues=[];fin_spec=dict(period=period,companies=[])
 for c in companies:
  try:
   dest=out/('statements-'+c['code']);a=collect(c['code'],str(int(period[:4])-2)+'-01-01',asof,dest);path=dest/'result.json';archives.append(str(path.resolve()));fin_spec['companies'].append(dict(archive=str(path.resolve()),metadata=c['metadata']))
   if a['status']!='available':issues.append(c['code']+'三表部分缺失')
  except Exception as exc:issues.append(c['code']+'三表采集失败：'+str(exc))
 stages=dict(reports='not-attempted',financials='not-attempted',commentary='not-attempted',excel='not-attempted',quarterInputs='not-requested')
 quarter_reviews=[]
 report=dict(companies=[],coverage={})
 try:
  report=reports(report_request(period,asof,[{k:v for k,v in c.items() if k in ['code','selectedId','uploadedPdf','sourceDocument']} for c in companies],spec.get('originalResumeFrom')),out/'originals');stages['reports']='completed'
  for c in report['companies']:
   if c['parseStatus']!='parsed':issues.append(c['code']+'原文未完成解析：'+str(c.get('error') or c['disclosureStatus']))
 except Exception as exc:
  stages['reports']='failed';issues.append('原文获取步骤失败：'+str(exc)+'；已保留三表取数结果')
 if fin_spec['companies']:
  try:
   financials(fin_spec,out/'financial');stages['financials']='completed'
  except Exception as exc:
   stages['financials']='failed';issues.append('财务计算失败：'+str(exc)+'；已保留取数及原文结果')
  payload=None
  if stages['financials']=='completed' and stages['reports']=='completed':
   link=dict(financialResult=str((out/'financial/result.json').resolve()),originalResult=str((out/'originals/result.json').resolve()),archives=archives)
   try:
    link.update(prepared_commentary)
    result=commentary(link,out/'commentary');verification_data=result;stages['commentary']='completed';link['commentaryResult']=str((out/'commentary/result.json').resolve())
   except Exception as exc:
    stages['commentary']='failed';issues.append('原文核对及点评失败：'+str(exc)+'；已保留季度财务计算')
   try:
    payload=prepare(link);input_path=out/'workbook-inputs.json';input_path.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf8')
   except Exception as exc:
    stages['excel']='failed';issues.append('底稿输入准备失败：'+str(exc))
 if spec.get('verifyQuarterInputs') is True and stages['financials']=='completed':
  from quarter_original_review import run as quarter_review
  financial_data=json.loads((out/'financial/result.json').read_text('utf-8'))
  stages['quarterInputs']='completed'
  for calculated in financial_data['companies']:
   code=calculated['code']
   try:
    needed=set()
    for key in CHECK_FIELDS:
     metric=calculated['metrics'][key]
     for entry in [metric['current'],*metric['comparators'].values()]:needed.update(ref['period'] for ref in entry['inputs'])
    paths=[]
    for report_period in sorted(needed):
     if report_period==period and stages['reports']=='completed':paths.append(str(out/'originals/result.json'));continue
     dest=out/('quarter-report-'+code+'-'+report_period)
     options=dict(spec.get('quarterReportSelections',{}).get(code,{}).get(report_period,{}))
     resume=options.pop('resumeFrom',None)
     reports(report_request(report_period,asof,[dict(code=code,**options)],resume),dest)
     paths.append(str(dest/'result.json'))
    reviewed=quarter_review(dict(archive=str(out/('statements-'+code)/'result.json'),metadata=calculated['metadata'],period=period,originalResults=paths),out/('quarter-review-'+code))
    quarter_reviews.append(reviewed)
    incomplete=sum(p['status']!='supported-inputs-matched' for f in reviewed['fields'] for p in f['parts'].values())
    if incomplete:issues.append(code+'：单季及比较基数有'+str(incomplete)+'项输入组未确认或存在跨期可比性提示。')
   except Exception as exc:
    stages['quarterInputs']='partial';issues.append(code+'单季原文输入核验失败：'+str(exc)+'；已保留财务及原文结果。')
 if spec.get('verifyQuarterInputs') is True and stages['financials']!='completed':stages['quarterInputs']='dependency-missing';issues.append('季度财务计算未完成，无法核对单季输入依赖。')
 if payload is not None and quarter_reviews:
  try:
   link['quarterReviewResults']=[str(out/('quarter-review-'+r['code'])/'result.json') for r in quarter_reviews]
   payload=prepare(link);input_path.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf8')
  except Exception as exc:
   payload=None;stages['excel']='failed';issues.append('多期原文核验导入底稿失败：'+str(exc)+'；不沿用未复核状态。')
 runtime=node or shutil.which('node')
 if payload is not None and runtime:
  try:
   process=subprocess.run([runtime,str(Path(__file__).with_name('export_financial_workbook.mjs')),str(input_path),str(out/'财务分析底稿.xlsx')],capture_output=True,text=True,encoding='utf8',errors='replace',timeout=180,env=export_env)
   if process.returncode==0:
    verify_workbook(out/'财务分析底稿.xlsx',input_path)
   stages['excel']='completed' if process.returncode==0 else 'failed'
   if process.returncode:
    (out/'excel-export-error.log').write_text(process.stderr,encoding='utf-8')
    reason='当前环境未提供可用的Excel导出组件；HTML、Markdown和JSON已保留。' if 'Excel导出需要@oai/artifact-tool' in process.stderr else '导出器执行失败；已有原文与研究结果保留，详细原因已保存到排查日志。'
    issues.append('Excel未生成：'+reason)
  except (subprocess.TimeoutExpired,OSError) as exc:
   stages['excel']='failed';issues.append('Excel运行未完成：'+str(exc)+'；已保留前序研究结果')
 elif payload is not None:stages['excel']='dependency-missing';issues.append('未找到Node运行时；HTML和JSON已保留，Excel需另行导出')
 document_exports,export_issues=export_documents(spec,out,stages['commentary']=='completed',runtime,export_env)
 issues.extend(export_issues)
 summary=verification_summary(verification_data,codes)
 appraisal=appraisal_summary(verification_data,codes)
 stages['appraisal']='prepared-awaiting-review' if all(r['status']=='covered-awaiting-semantic-review' for r in appraisal['companies']) else 'partial' if any(r['status']!='data-only' for r in appraisal['companies']) else 'not-completed'
 for row in appraisal['companies']:
  if row['status']=='data-only':issues.append(row['code']+'仅完成数据整理与核对，研究评价尚未完成。')
  elif row['missingRoles'] or row['issues']:
   labels=dict(overall='总体判断',business='经营驱动',earnings='盈利质量',cash='现金兑现',risk='主要风险',falsification='改变判断的条件')
   issues.append(row['code']+'评价结构仍有缺口：'+'、'.join([labels[r] for r in row['missingRoles']]+row['issues']))
 for company in summary['companies']:
  if company['unverified']:issues.append(company['code']+'：'+str(company['unverified'])+'项支持字段尚未通过原文核验；步骤完成不等于核验通过。')
  if company['comparativeColumnUnverified']:issues.append(company['code']+'：'+str(company['comparativeColumnUnverified'])+'项比较列尚未核验；不把缺失比较值当作零。')
  if company['comparativeColumnDifferences']:issues.append(company['code']+'：'+str(company['comparativeColumnDifferences'])+'项历史渠道值与报告比较列有差异；需检查重述或口径变化。')
  if company['differences']:issues.append(company['code']+'：'+str(company['differences'])+'项支持字段与原文有差异，需复核。')
 result=dict(period=period,asOf=asof,stages=stages,issues=issues,coverage=report['coverage'],originalVerification=summary,limitations=['仅指定公司池，不自动获取全行业股票池','逐项原文匹配仅覆盖当前支持字段和版式，不证明全部季度计算已获原文核验','原文线索与财务事实分别呈现，经营原因和展望不自动定性'])
 result['documentExports']=document_exports
 result['appraisalCoverage']=appraisal
 result['originalAcquisitionSummary']=acquisition_summary(report['companies'])
 result['quarterInputReviews']=quarter_reviews
 result['quarterInputVerification']=quarter_verification_summary(quarter_reviews,codes,spec.get('verifyQuarterInputs') is True)
 result['deliveryAssessment']=delivery_assessment(stages,summary,result['quarterInputVerification'],issues)
 (out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');lines=['# 公司财报研究','',period+'，截止'+asof+'。','','## 本次交付']
 lines += [result['deliveryAssessment']['note'],result['deliveryAssessment']['scope']]
 for key,relative,label in [('reports','originals/财报覆盖.html','财报覆盖清单'),('financials','financial/财务研究.html','季度财务计算'),('commentary','commentary/公司与行业点评.html','公司与样本点评'),('excel','财务分析底稿.xlsx','Excel底稿')]:
  if key=='commentary' and stages['appraisal']=='not-completed':label='财务核对（研究评价尚未完成）'
  elif key=='commentary' and stages['appraisal']=='partial':label='财务与已有评价（部分内容待补）'
  if stages[key]=='completed':lines.append('['+label+']('+relative+')')
  else:lines.append(label+'：未完成，见资料缺口。')
 for fmt,entry in document_exports.items():
  label={'docx':'Word','pptx':'PPT'}[fmt]
  lines.append(label+'材料已生成，尚需文件及排版验收。' if entry['status']=='generated-awaiting-review' else label+'材料未生成；已有研究成果可使用，见资料缺口。')
 for reviewed in quarter_reviews:lines.append('[单季及同比环比输入核验 '+reviewed['code']+'](quarter-review-'+reviewed['code']+'/单季输入核验.html)')
 lines+=['','## 本次原文资料',*acquisition_lines(result['originalAcquisitionSummary'])]
 lines+=['','## 原文核验范围',result['originalVerification']['scope']]
 for c in result['originalVerification']['companies']:
  lines.append(c['code']+f"：支持字段{c['supportedFieldCount']}项，已匹配{c['matched']}项、差异{c['differences']}项、尚未核验{c['unverified']}项。")
  lines.append(c['code']+f"：比较列已匹配{c['comparativeColumnMatched']}项、差异{c['comparativeColumnDifferences']}项、尚未核验{c['comparativeColumnUnverified']}项。利润及现金流比较去年同期累计，资产负债比较上年末。")
  for warning in c['reportMetadataWarnings']:lines.append(c['code']+'：'+warning)
  for warning in c['comparabilityWarnings']:
   lines.append(c['code']+'：'+warning['warning']+'（报告第'+str(warning['page'])+'页）')
 lines+=['','## 单季计算输入范围',result['quarterInputVerification']['scope']]
 for c in result['quarterInputVerification']['companies']:
  if not c['requested']:lines.append(c['code']+'：本次未请求相邻期原文核验，不把已完成计算视为输入已确认。')
  else:lines.append(c['code']+f"：{c['supportedInputGroupCount']}组支持输入，已匹配{c['matched']}组、跨期口径待复核{c['comparabilityWarning']}组、尚未核验{c['unverified']}组。")
 lines.append('上述核验分列本期及报告比较列；单季度同比仍依赖相邻期间和历史差分输入，不能据此声称全部输入已确认。')
 lines+=['','## 资料缺口',*(delivery_gaps(result) or ['本次已执行步骤未报告额外缺口；不代表全部资料均已核验。']),'','## 范围说明',*result['limitations']];(out/'研究入口.html').write_text(render('\n'.join(lines),title='公司财报研究'),encoding='utf8');return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--out-dir',type=Path,required=True);p.add_argument('--node');p.add_argument('--artifact-node-modules');a=p.parse_args();run(json.loads(a.input.read_text(encoding='utf8')),a.out_dir,a.node,a.artifact_node_modules)
