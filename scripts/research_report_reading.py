"""Archive readable PDF pages; validate AI-authored three-layer reading against page quotes."""
import argparse,hashlib,json,re,shutil
from pathlib import Path
from datetime import date
from research_brief_html import render
from collection_validation import day,unique_pairs,reject_constant

def compact(text):return re.sub(r'\s+','',text)
def language(text):
 zh=len(re.findall(r'[\u4e00-\u9fff]',text));en=len(re.findall(r'[A-Za-z]',text))
 if zh+en<80:return 'undetermined'
 if zh/(zh+en)>.25:return 'Chinese-or-mixed'
 return 'English-dominant'

def language_profile(pages):
 groups={'Chinese-or-mixed':[],'English-dominant':[],'undetermined':[]}
 for p in pages:groups[language(p['text'])].append(p['page'])
 return dict(overall=language('\n'.join(p['text'] for p in pages)),pagesByLanguage=groups,scope='基于已提取文字的字符比例提示，非完整语言识别或翻译完成证明')

def prepare(spec,out):
 if not isinstance(spec,dict) or not isinstance(spec.get('reports'),list) or any(not isinstance(r,dict) for r in spec['reports']):raise ValueError('报告请求须为对象及报告列表')
 reports=spec['reports'];day(spec.get('asOf'))
 if not 1<=len(reports)<=20:raise ValueError('每次1至20份报告')
 ids=[r['id'] for r in reports]
 if len(set(ids))!=len(ids) or any(not isinstance(x,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,60}',x) for x in ids):raise ValueError('报告ID必须唯一且为安全标识')
 out=Path(out);out.mkdir(parents=True,exist_ok=False);items=[]
 for meta in reports:
  item={k:meta.get(k) for k in ['id','title','institution','publishedAt','sourceUrl','originGroup']};item.update(status='failed',pages=[],warnings=[])
  try:
   if meta.get('publishedAt'):
    day(meta['publishedAt'])
    if meta['publishedAt']>spec['asOf']:raise ValueError('报告发布日期晚于研究截止日')
   source=Path(meta['pdf'])
   if source.stat().st_size>64*1024*1024:raise ValueError('需64MB以内PDF')
   raw=source.read_bytes()
   if len(raw)>64*1024*1024 or not raw.startswith(b'%PDF-'):raise ValueError('需64MB以内PDF')
   item['sha256']=hashlib.sha256(raw).hexdigest();dest=out/meta['id'];dest.mkdir();(dest/'original.pdf').write_bytes(raw);item['pdfPath']=str((dest/'original.pdf').resolve())
   errors=[]
   try:
    import pdfplumber
    with pdfplumber.open(dest/'original.pdf') as pdf:
     if len(pdf.pages)>800:raise ValueError('超过800页上限')
     item['pages']=[dict(page=i+1,text=p.extract_text() or '') for i,p in enumerate(pdf.pages)]
    item['parser']='pdfplumber'
   except Exception as exc:
    errors.append('pdfplumber: '+str(exc));item['pages']=[]
   if not item['pages'] or sum(len(p['text']) for p in item['pages'])<100:
    try:
     from pypdf import PdfReader
     pdf=PdfReader(dest/'original.pdf')
     if len(pdf.pages)>800:raise ValueError('超过800页上限')
     candidate=[dict(page=i+1,text=p.extract_text() or '') for i,p in enumerate(pdf.pages)]
     if sum(len(p['text']) for p in candidate)>sum(len(p['text']) for p in item['pages']):item['pages']=candidate;item['parser']='pypdf'
    except Exception as exc:errors.append('pypdf: '+str(exc))
   text='\n'.join(p['text'] for p in item['pages']);item['language']=language(text);item['pageCount']=len(item['pages']);item['lowTextPages']=[p['page'] for p in item['pages'] if len(p['text'].strip())<40];item['status']='readable' if len(text.strip())>=100 else 'manual-review'
   item['languageProfile']=language_profile(item['pages'])
   item['warnings']+=errors
   if item['lowTextPages']:item['warnings'].append('部分页面文字不足，需查看PDF：'+','.join(map(str,item['lowTextPages'])))
   if item['status']=='manual-review':item['warnings'].append('可提取文字不足；扫描件需人工辅助，不提供内置OCR')
   item['warnings'].append('标题、机构和发布日期是输入元数据；未自动核验报告身份。页码为PDF物理页。')
   (dest/'pages.json').write_text(json.dumps(item['pages'],ensure_ascii=False,indent=2),encoding='utf8')
  except Exception as exc:item['error']=str(exc)
  items.append(item)
 result=dict(asOf=spec['asOf'],reports=items,limitations=['文本提取不保证图表、公式和复杂表格完整；必要时查看原PDF','内容为后续AI阅读的原始材料，下载或解析成功不等于观点正确'])
 (out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');return result

def check_entry(entry,report):
 if not isinstance(entry,dict) or not isinstance(entry.get('text'),str) or not entry['text'].strip():raise ValueError('观点条目需text与evidence')
 refs=entry.get('evidence',[])
 if not isinstance(refs,list) or not refs or any(not isinstance(r,dict) for r in refs):raise ValueError('观点条目必须有页码引句')
 pages={}
 for p in report['pages']:
  if not isinstance(p,dict) or type(p.get('page'))!=int or p['page']<1 or not isinstance(p.get('text'),str):raise ValueError('报告页面结构无效')
  if p['page'] in pages:raise ValueError('报告物理页重复')
  pages[p['page']]=p['text']
 checked=[]
 for ref in refs:
  page=ref['page'];quote=ref['quote']
  if type(page)!=int or not isinstance(quote,str) or len(compact(quote))<8:raise ValueError('引句需有效页码和至少8个非空白字符')
  if page not in pages or compact(quote) not in compact(pages[page]):raise ValueError('引句无法在指定原文页定位')
  checked.append(dict(page=page,quote=quote,sha256=report['sha256'],status='quote-located'))
 return dict(text=entry['text'],evidence=checked,status='AI-interpretation; quote-located-not-semantic-verification')

def assumption_tests(entries,report):
 if not isinstance(entries,list) or len(entries)>30:raise ValueError('假设核查须为不超过30项的列表')
 result=[]
 for entry in entries:
  if not isinstance(entry,dict) or set(entry)-{'text','evidence','invalidationSignal','requestedEvidence'}:raise ValueError('假设核查字段无效；不能声明已验证状态')
  for key in ['invalidationSignal','requestedEvidence']:
   if not isinstance(entry.get(key),str) or not entry[key].strip():raise ValueError('假设核查需明确反证信号及待取材料')
  checked=check_entry(entry,report)
  result.append(dict(checked,invalidationSignal=entry['invalidationSignal'],requestedEvidence=entry['requestedEvidence'],status='hypothesis-prepared-not-tested'))
 return result

def verify_pdf_pages(report):
 """Re-extract saved pages from the bound PDF before accepting quote evidence."""
 original=Path(report['pdfPath'])
 if hashlib.sha256(original.read_bytes()).hexdigest()!=report['sha256']:
  raise ValueError('原PDF哈希已变化，应重新解析')
 parser=report.get('parser')
 if parser=='pdfplumber':
  import pdfplumber
  with pdfplumber.open(original) as pdf:
   actual=[dict(page=i+1,text=p.extract_text() or '') for i,p in enumerate(pdf.pages)]
 elif parser=='pypdf':
  from pypdf import PdfReader
  actual=[dict(page=i+1,text=p.extract_text() or '') for i,p in enumerate(PdfReader(original).pages)]
 else:
  raise ValueError('缺少可复核的解析器记录，应重新prepare原PDF')
 if actual!=report.get('pages'):
  raise ValueError('保存的页码文字与原PDF重新解析结果不一致，应重新解析；不得修改证据文字')
 return 'pdf-reparsed-pages-matched'

def origin_assessment(ids,reports):
 hashes={reports[i]['sha256'] for i in ids}
 groups=[reports[i].get('originGroup') for i in ids]
 known={g for g in groups if isinstance(g,str) and g.strip()}
 unknown=sum(not isinstance(g,str) or not g.strip() for g in groups)
 if len(hashes)<len(ids):note='参与报告包含相同PDF，重复文件不增加独立证据。'
 elif unknown:note='部分报告的来源关系未确认，不能据此判断证据独立。'
 elif len(known)<len(ids):note='参与报告存在相同来源组，观点重复不增加独立证据。'
 else:note='文件与声明来源组不同，但独立性仍未外部核验。'
 return dict(reportCount=len(ids),distinctFileCount=len(hashes),distinctDeclaredOriginCount=len(known),unknownOriginCount=unknown,note=note)

def underlying_source_assessment(ids,mapping):
 """Record declared quote-level source relationships, not externally verified identities."""
 if mapping is None:return None
 if not isinstance(mapping,dict) or set(mapping)!=set(ids):raise ValueError('底层来源声明须覆盖所有参与报告，不能添加样本外来源')
 normalized={}
 for id,values in mapping.items():
  if not isinstance(values,list) or any(not isinstance(v,str) or not v.strip() or len(v)>160 for v in values):raise ValueError('底层来源须为非空名称列表；未知来源用空列表')
  clean=[v.strip() for v in values]
  if len(clean)!=len(set(clean)):raise ValueError('同报告底层来源名称不可重复计数')
  normalized[id]=clean
 unique=sorted({v for values in normalized.values() for v in values})
 shared=[v for v in unique if sum(v in values for values in normalized.values())>1]
 unknown=sum(not values for values in normalized.values())
 note=('参与报告转引相同的已声明底层来源，重复转引不增加独立证据。' if shared else '部分底层来源未登记，不能判断证据独立。' if unknown else '登记的底层来源不同，来源身份及独立性仍未外部核验。')
 return dict(declaredSources=normalized,distinctDeclaredSourceCount=len(unique),sharedDeclaredSources=shared,unknownSourceReportCount=unknown,status='input-declared-not-source-identity-verified',independentEvidenceConfirmed=False,note=note)

def citation_scope(analysis,report):
 pages=set()
 def visit(obj):
  if isinstance(obj,dict):
   for entry in obj.get('evidence',[]):pages.add(entry['page'])
   for key,value in obj.items():
    if key!='evidence':visit(value)
  elif isinstance(obj,list):
   for value in obj:visit(value)
 visit(analysis)
 return dict(citedPages=sorted(pages),citedPageCount=len(pages),documentPageCount=len(report['pages']),status='located-excerpts-not-full-document-verification')

def include_comparison_citations(analysis,comparisons):
 scope=analysis['citationScope'];original=scope['citedPages']
 pages=sorted({ref['page'] for row in comparisons for item in row['evidence'] if item['reportId']==analysis['reportId'] for ref in item['evidence']})
 combined=sorted(set(original)|set(pages))
 analysis['citationScope']=dict(scope,analysisCitedPages=original,comparisonCitedPages=pages,citedPages=combined,citedPageCount=len(combined))

def comparison_basis(ids,mapping):
 fields=('subject','period','definition')
 if mapping is None:return dict(status='unconfirmed',differences=[],note='尚未逐篇登记比较对象、期间与定义；本项只作观点对照，不据此确认同口径一致或分歧。')
 if not isinstance(mapping,dict) or set(mapping)!=set(ids):raise ValueError('比较口径须覆盖全部参与报告')
 for basis in mapping.values():
  if not isinstance(basis,dict) or set(basis)!=set(fields) or any(not isinstance(basis[k],str) or not basis[k].strip() for k in fields):raise ValueError('比较对象、期间与定义须为非空文字')
 differences=[k for k in fields if len({mapping[x][k].strip() for x in ids})>1]
 labels={'subject':'比较对象','period':'期间','definition':'指标或观点定义'}
 return dict(status='declared-different' if differences else 'declared-aligned-not-verified',differences=differences,byReport=mapping,note=('各篇'+ '、'.join(labels[k] for k in differences)+'不同，不能将差异直接解释为同一问题上的观点冲突。' if differences else '已登记相同对象、期间与定义；登记内容仍需语义复核，不证明结论一致或事实正确。'))

def comparison_display_kind(kind,basis):
 if kind=='not-comparable' or basis['status']=='declared-different':return 'not-comparable'
 if basis['status']=='unconfirmed':return 'viewpoint-comparison'
 return kind

def build(spec,out):
 archive=Path(spec['archive']);raw=archive.read_bytes();data=json.loads(raw,object_pairs_hook=unique_pairs,parse_constant=reject_constant);day(data.get('asOf'))
 if not isinstance(data.get('reports'),list) or any(not isinstance(r,dict) or not isinstance(r.get('id'),str) for r in data['reports']):raise ValueError('归档报告结构无效')
 if len({r['id'] for r in data['reports']})!=len(data['reports']):raise ValueError('归档报告ID重复，不可覆盖')
 reports={r['id']:r for r in data['reports']};analyses=spec['analyses'];ids=[a['reportId'] for a in analyses]
 if not 1<=len(ids)<=20 or len(set(ids))!=len(ids):raise ValueError('需1至20份不重复报告分析')
 analysed_ids=set(ids)
 validated=[]
 for analysis in analyses:
  r=reports[analysis['reportId']]
  if r['status']!='readable':raise ValueError('不可为未成功解析报告生成已完成精读')
  original=Path(r['pdfPath'])
  evidence_integrity=verify_pdf_pages(r)
  a=dict(reportId=r['id'],title=r.get('title') or r['id'],institution=r.get('institution'),originGroup=r.get('originGroup'),publishedAt=r.get('publishedAt'),sourceUrl=r.get('sourceUrl'),metadataStatus='input-declared-not-identity-verified',evidenceIntegrity=evidence_integrity,languageProfile=language_profile(r['pages']),layers={})
  if 'benchmarkReview' in analysis:
   if type(analysis['benchmarkReview']) is not bool:raise ValueError('基准核对开关须为布尔值')
   if analysis['benchmarkReview']:
    from report_benchmark_status import inspect
    a['benchmarkReview']=inspect(r['pages'])
  for layer in ['logic','assumptions','depth']:
   entries=analysis.get(layer)
   if not isinstance(entries,list) or not entries:raise ValueError('三层阅读每层至少一条有据说明')
   a['layers'][layer]=[check_entry(e,r) for e in entries]
  a['assumptionTests']=assumption_tests(analysis.get('assumptionTests',[]),r)
  chain=analysis.get('industryChain')
  if chain is not None:
   if not isinstance(chain,dict) or set(chain)-{'upstream','manufacturing','channels','downstream','gaps'}:raise ValueError('产业链只接受上游、生产、渠道、下游与缺口字段')
   checked={}
   for key in ['upstream','manufacturing','channels','downstream']:
    entries=chain.get(key,[])
    if not isinstance(entries,list):raise ValueError('产业链各环节须为列表；无资料保留空列表')
    checked[key]=[check_entry(e,r) for e in entries]
   gaps=chain.get('gaps',[])
   if not isinstance(gaps,list) or any(not isinstance(g,str) or not g.strip() for g in gaps):raise ValueError('产业链缺口须为非空文字列表')
   if not any(checked.values()):raise ValueError('产业链至少一个环节需要原文证据')
   checked['gaps']=gaps;a['industryChain']=checked
  if 'policyAnalysis' in analysis:
   policy=analysis['policyAnalysis']
   allowed={'scope','timing','transmission','risks'}
   if not isinstance(policy,dict) or set(policy)-allowed:raise ValueError('政策分析字段无效')
   checked={}
   for key in sorted(allowed):
    entries=policy.get(key,[])
    if not isinstance(entries,list):raise ValueError('政策分析各项须为引句条目列表')
    checked[key]=[check_entry(e,r) for e in entries]
   if not any(checked.values()):raise ValueError('政策分析至少需要一项原文依据')
   a['policyAnalysis']=checked
  questions=analysis.get('dueDiligenceQuestions',[])
  if not isinstance(questions,list) or len(questions)>30:raise ValueError('尽调问题须为不超过30项的列表')
  checked_questions=[]
  for question in questions:
   if not isinstance(question,dict) or question.get('respondent') not in ['management','customer','supplier','distributor','competitor','analyst']:raise ValueError('尽调对象须明确分类')
   for field in ['question','requestedEvidence']:
    if not isinstance(question.get(field),str) or not question[field].strip():raise ValueError('尽调问题与待取材料须为非空文字')
   checked=check_entry(dict(text=question['question'],evidence=question.get('evidence',[])),r)
   checked_questions.append(dict(respondent=question['respondent'],question=question['question'],requestedEvidence=question['requestedEvidence'],evidence=checked['evidence'],status='question-prepared-not-interviewed'))
  a['dueDiligenceQuestions']=checked_questions
  from report_reading_coverage import review_coverage
  a['readingCoverage']=review_coverage(analysis,r)
  a['gaps']=analysis.get('gaps',[])+a['readingCoverage']['gaps']+['待核查假设：'+entry['text'] for entry in a['assumptionTests']]
  if 'benchmarkReview' in a:
   status=a['benchmarkReview']['status']
   notices={'not-located':'本次未定位到业绩比较基准，不能据此认定基金没有基准。','conflicting-report-statements':'报告中的基准表述存在冲突，未选择其中一个作为计算依据。','formula-located-not-verified':'已定位基准公式，但未核验合同版本、组成指数与收益序列。'}
   if status in notices:a['gaps'].append(notices[status])
  a['citationScope']=citation_scope(a,r);validated.append(a)
 comparisons=[]
 for row in spec.get('comparisons',[]):
  ids=row['reportIds']
  if len(ids)!=len(set(ids)) or len(set(ids))<2 or any(x not in {a['reportId'] for a in validated} for x in ids):raise ValueError('对比需至少两份已分析报告')
  if row['kind'] not in ['agreement','difference','not-comparable']:raise ValueError('未知对比类型')
  evidence=row.get('evidence',[])
  if set(e['reportId'] for e in evidence)!=set(ids):raise ValueError('跨报告判断须引用所有参与报告')
  refs=[dict(reportId=e['reportId'],**check_entry(dict(text=row['text'],evidence=[e]),reports[e['reportId']])) for e in evidence]
  groups={reports[i].get('originGroup') for i in ids};hashes={reports[i]['sha256'] for i in ids}
  assessment=origin_assessment(ids,reports)
  underlying=underlying_source_assessment(ids,row.get('underlyingSources'))
  independent=bool(assessment['unknownOriginCount']==0 and len(groups)==len(ids) and len(hashes)==len(ids))
  comparisons.append(dict(kind=row['kind'],text=row['text'],reportIds=ids,evidence=refs,distinctDeclaredOrigins=independent,originAssessment=assessment,underlyingSourceAssessment=underlying,comparisonBasis=comparison_basis(ids,row.get('comparisonBasis')),independentEvidenceConfirmed=False,originNote='来源组仅为输入声明；独立性未外部核验，不将报告一致视为市场共识'))
 for comparison in comparisons:comparison['displayKind']=comparison_display_kind(comparison['kind'],comparison['comparisonBasis'])
 for analysis in validated:include_comparison_citations(analysis,comparisons)
 result=dict(asOf=data['asOf'],archiveSha256=hashlib.sha256(raw).hexdigest(),analyses=validated,comparisons=comparisons,unreadReports=[r['id'] for r in reports.values() if r['id'] not in analysed_ids],limitations=['引句定位只证明文字存在，不自动证明AI概括、假设或因果解释正确','跨报告一致不等于市场共识，更不等于投资结论已验证','全文翻译由AI另行完成，仅针对用户提供或有权处理的文本；不保证PDF原版式还原'])
 result['unreadReportDetails']=[dict(reportId=r['id'],title=r.get('title') or r['id'],status=r['status'],reason=(r.get('error') or ('正文提取不足，需人工辅助读取' if r['status']=='manual-review' else '本次尚未精读'))) for r in reports.values() if r['id'] not in analysed_ids]
 snapshot_pdfs=[]
 for report in reports.values():
  if report.get('pdfPath') and report.get('sha256'):
   raw_pdf=Path(report['pdfPath']).read_bytes()
   if hashlib.sha256(raw_pdf).hexdigest()!=report['sha256']:raise ValueError('交付前原PDF变化，应重新解析')
   snapshot_pdfs.append((report,raw_pdf))
 out=Path(out);out.mkdir(parents=True,exist_ok=False);source_links={}
 source_dir=out/'sources';source_dir.mkdir()
 for i,(report,raw_pdf) in enumerate(snapshot_pdfs,1):
  relative=f'sources/report-{i}.pdf';(out/relative).write_bytes(raw_pdf);source_links[report['id']]=relative
 method_modules=['research_report_reading.py','report_reading_coverage.py','research_brief_html.py']
 if any('benchmarkReview' in a for a in validated):method_modules.append('report_benchmark_status.py')
 result['methodVersions']={name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() for name in method_modules}
 result['sourceFiles']=[dict(reportId=id,path=path,sha256=reports[id]['sha256'],readingStatus=reports[id]['status'],analysed=id in analysed_ids,sourceUrl=reports[id].get('sourceUrl'),metadataStatus='input-declared-not-identity-verified') for id,path in source_links.items()]
 lines=['# 研报精读','',f"研究截止日：{data['asOf']}。下列解释基于所列报告；引句已定位，摘要仍需研究者复核。"]
 for a in validated:
  lines+=['','## '+a['title'],f"机构：{a.get('institution') or '未确认'}；发布日期：{a.get('publishedAt') or '未确认'}。"]
  english_pages=a['languageProfile']['pagesByLanguage']['English-dominant']
  if english_pages:lines.append('正文语言提示：第'+ '、'.join(map(str,english_pages))+'页提取文字以英文为主。需要中文阅读时应逐页翻译并复核表格数字；本次语言提示不表示翻译已完成。')
  lines+=['来源身份和日期为登记信息，原文文字核对不等于身份核验。']
  scope=a['citationScope'];lines+=['本篇正文共'+str(scope['documentPageCount'])+'页，本次逐项引用第'+ '、'.join(map(str,scope['citedPages']))+'页。这里仅说明引句定位范围，不代表全文已核验，也不代表摘要准确率。']
  if a.get('sourceUrl'):lines+=['登记下载来源：'+a['sourceUrl']]
  if 'benchmarkReview' in a:
   review=a['benchmarkReview']
   labels={'explicitly-not-defined':'报告明确说明未设业绩比较基准。','not-located':'本次未找到基准表述，仍需补查。','formula-located-not-verified':'已找到基准公式，尚未完成合同与数据口径核验。','conflicting-report-statements':'报告存在不同的基准表述，需核实冲突。'}
   lines+=['','### 业绩比较基准核对',labels[review['status']]]
   for evidence in review['evidence']:
    lines+=['原文：'+evidence['quote']+'（[第'+str(evidence['page'])+'页]('+source_links[a['reportId']]+'#page='+str(evidence['page'])+')）。']
   lines+=[review['limitation']]
  coverage=a['readingCoverage']
  if coverage['sections']:
   lines+=['','### 章节阅读范围','下列阅读状态为本次声明；原文引句定位不证明整章解释正确。']
   for section in coverage['sections']:lines.append(section['title']+'（第'+str(section['startPage'])+'—'+str(section['endPage'])+'页）：'+('已记录阅读' if section['status']=='reviewed' else '待阅读核查')+'。'+section['note'])
  if coverage['numericTables']:
   lines+=['','### 印刷表格数值核对','只核对所列数值与PDF文字，不代表复现回测或核对全部图表。']
   for table in coverage['numericTables']:
    labels=[(g+'／' if g else '')+c for g,c in zip(table.get('columnGroups') or ['']*len(table['columns']),table['columns'])]
    values='；'.join(c+'：'+v+('%' if table['unit']=='percent' else '') for c,v in zip(labels,table['values']))
    if table.get('columnGroups'):lines.append('分组表头及列顺序已定位；列分组对应为本次声明，未作图形坐标核验。')
    lines.append(table['rowLabel']+'，'+values+'（[第'+str(table['page'])+'页]('+source_links[a['reportId']]+'#page='+str(table['page'])+')）。')
  for key,label in [('logic','核心逻辑'),('assumptions','假设与证据'),('depth','研究深度与精读重点')]:
   lines+=['','### '+label]
   for e in a['layers'][key]:
    links='、'.join('[第'+str(v['page'])+'页]('+source_links[a['reportId']]+'#page='+str(v['page'])+')' for v in e['evidence'])
    lines += [e['text']+'（原文'+links+'）']
  if a['assumptionTests']:
   lines+=['','### 关键假设如何核查','以下为研究者提出的核查计划，尚未取得所需材料验证；原文引句存在不证明假设成立。']
   for entry in a['assumptionTests']:
    links='、'.join('[第'+str(v['page'])+'页]('+source_links[a['reportId']]+'#page='+str(v['page'])+')' for v in entry['evidence'])
    lines += [entry['text']+'（原文依据'+links+'）。','需要留意的反证信号：'+entry['invalidationSignal'],'待取材料：'+entry['requestedEvidence']]
  if 'industryChain' in a:
   lines+=['','### 产业链与经营关系','下列关系依据本篇披露整理；应用行业不等于具名客户，采购品类不等于已核验供应商。']
   for key,label in [('upstream','上游材料与零部件'),('manufacturing','生产与产品'),('channels','销售渠道'),('downstream','下游应用')]:
    lines+=['','#### '+label]
    entries=a['industryChain'][key]
    if not entries:lines+=['本次资料未支持此环节的说明。']
    for e in entries:
     links='、'.join('[第'+str(v['page'])+'页]('+source_links[a['reportId']]+'#page='+str(v['page'])+')' for v in e['evidence'])
     lines+=[e['text']+'（原文'+links+'）']
   if a['industryChain']['gaps']:lines+=['','#### 产业链待核实资料',*a['industryChain']['gaps']]
  if 'policyAnalysis' in a:
   lines+=['','### 政策适用与传导','原文措辞与研究解释须分别复核；不据此判定当前有效性或投资影响。']
   for key,label in [('scope','适用对象与工具'),('timing','公布与生效时间'),('transmission','待验证的传导路径'),('risks','风险与条件')]:
    lines+=['','#### '+label]
    entries=a['policyAnalysis'][key]
    if not entries:lines+=['本次未取得支持此项的原文依据。']
    for e in entries:
     links='、'.join('[第'+str(v['page'])+'页]('+source_links[a['reportId']]+'#page='+str(v['page'])+')' for v in e['evidence'])
     lines += [e['text']+'（原文'+links+'）']
  if a['dueDiligenceQuestions']:
   lines+=['','### 尽调追问与待取材料','以下仅为基于原文设计的问题，尚未访谈，也未获得独立验证。']
   names=dict(management='管理层',customer='客户',supplier='供应商',distributor='渠道商',competitor='同业',analyst='研究员')
   for question in a['dueDiligenceQuestions']:
    links='、'.join('[第'+str(v['page'])+'页]('+source_links[a['reportId']]+'#page='+str(v['page'])+')' for v in question['evidence'])
    lines += ['向'+names[question['respondent']]+'核实：'+question['question']+'（问题依据'+links+'）。','待取材料：'+question['requestedEvidence']]
  if a['gaps']:lines+=['','### 本篇局限',*a['gaps']]
 if comparisons:
  lines+=['','## 跨报告对照']
  for c in comparisons:
   links='、'.join('['+v['reportId']+' 第'+str(e['page'])+'页]('+source_links[v['reportId']]+'#page='+str(e['page'])+')' for v in c['evidence'] for e in v['evidence'])
   lines += [{'agreement':'一致性线索','difference':'分歧线索','not-comparable':'口径不可直接比较','viewpoint-comparison':'观点对照（口径待确认）'}[c['displayKind']]+'：'+c['text']+'（原文'+links+'）',c['comparisonBasis']['note'],c['originAssessment']['note'],c['originNote']]
   if c.get('underlyingSourceAssessment'):
    u=c['underlyingSourceAssessment'];lines += [u['note']+('共同登记来源：'+'、'.join(u['sharedDeclaredSources'])+'。' if u['sharedDeclaredSources'] else '')+'来源名称与转引关系是本次阅读登记，尚未取得原始数据作外部核验。']
 if result['unreadReports']:
  lines+=['','## 尚未精读的报告']
  lines += [item['title']+'：'+item['reason']+'。'+('[查看原文]('+source_links[item['reportId']]+')' if item['reportId'] in source_links else '本次未留存可打开的原文文件。') for item in result['unreadReportDetails']]
 lines+=['','## 使用说明',*result['limitations']];md='\n\n'.join(lines)
 html=render(md,title='研报精读');payload=json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)
 (out/'result.json').write_text(payload,encoding='utf8');(out/'研报精读.md').write_text(md,encoding='utf8');(out/'研报精读.html').write_text(html,encoding='utf8');return result

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('command',choices=['prepare','build']);p.add_argument('input',type=Path);p.add_argument('--out-dir',type=Path,required=True);a=p.parse_args();globals()[a.command](json.loads(a.input.read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant),a.out_dir)
