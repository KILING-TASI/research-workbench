"""Bind a declared content review to exact report bytes; never certify semantics."""
import hashlib,json,re
from io import BytesIO
from pathlib import Path
from html.parser import HTMLParser
from collection_validation import unique_pairs,reject_constant,finite_json_float
REQUIRED=('question','evidence','meaning','alternatives','falsification','gaps','comparability','basis','scope')

def html_prose(source):
 """Extract text outside head/script/style/template; not a DOM visibility test."""
 class Parser(HTMLParser):
  def __init__(self):super().__init__(convert_charrefs=True);self.suppressed=0;self.parts=[]
  def handle_starttag(self,tag,attrs):
   if tag in ('head','script','style','template'):self.suppressed+=1
  def handle_endtag(self,tag):
   if tag in ('head','script','style','template') and self.suppressed:self.suppressed-=1
  def handle_data(self,data):
   if not self.suppressed:self.parts.append(data)
 parser=Parser();parser.feed(source);parser.close();return ' '.join(parser.parts)

def json_value_at(document,pointer):
 if not isinstance(pointer,str) or (pointer and not pointer.startswith('/')):raise ValueError('JSON定位须为JSON Pointer')
 value=document
 for token in pointer.split('/')[1:] if pointer else []:
  if re.search(r'~(?![01])',token):raise ValueError('JSON定位转义无效')
  key=token.replace('~1','/').replace('~0','~')
  if isinstance(value,dict):
   if key not in value:raise ValueError('JSON证据位置不存在')
   value=value[key]
  elif isinstance(value,list):
   if not re.fullmatch(r'0|[1-9][0-9]*',key) or int(key)>=len(value):raise ValueError('JSON证据索引不存在')
   value=value[int(key)]
  else:raise ValueError('JSON证据位置不能继续读取')
 return value
def prose_lines(body):
 """Exclude fenced examples; this is not a complete Markdown renderer."""
 fence=None
 for line in body.splitlines():
  marker=re.match(r'^ {0,3}(`{3,}|~{3,})(.*)$',line)
  if fence is not None:
   if marker and marker[1][0]==fence[0] and len(marker[1])>=fence[1] and not marker[2].strip():fence=None
   continue
  if marker and (marker[1][0]!='`' or '`' not in marker[2]):
   fence=(marker[1][0],len(marker[1]));continue
  yield line

def bind_review(spec):
 if not isinstance(spec,dict) or not isinstance(spec.get('reportPath'),str) or not spec['reportPath'].strip():raise ValueError('内容复查须为对象并指定正文路径')
 p=Path(spec['reportPath']);raw=p.read_bytes();digest=hashlib.sha256(raw).hexdigest()
 if spec.get('reportSha256')!=digest:raise ValueError('正文已变化，原验收记录不能沿用')
 if spec.get('reviewer') not in ('AI-content-review','human-review'):raise ValueError('须标明内容复查方式')
 rows=spec.get('checks')
 if not isinstance(rows,list):raise ValueError('需逐项复查记录')
 headings=set();sections={};current=None
 for line in prose_lines(raw.decode('utf-8-sig')):
  heading=re.match(r'^#{1,6}\s+(.+?)\s*$',line)
  if heading:
   current=[];headings.add(heading[1]);sections.setdefault(heading[1],[]).append(current)
  elif current is not None:current.append(line)
 seen=set()
 for row in rows:
  if not isinstance(row,dict):raise ValueError('复查条目须为对象')
  key=row.get('key')
  if key not in REQUIRED or key in seen:raise ValueError('检查项未知或重复')
  seen.add(key)
  if row.get('status') not in ('passed','partial','failed','not-applicable'):raise ValueError('复查状态无效')
  for field in ('location','reason'):
   if not isinstance(row.get(field),str) or not row[field].strip():raise ValueError('须给出段落位置及具体理由')
  if 'sectionHeading' in row and (not isinstance(row['sectionHeading'],str) or row['sectionHeading'] not in headings):raise ValueError('复查章节不在当前正文，不能沿用旧位置')
  if 'sectionQuote' in row:
   quote=row['sectionQuote'];matches=sections.get(row.get('sectionHeading'),[])
   if not isinstance(quote,str) or not quote.strip():raise ValueError('章节引句不能为空')
   if len(matches)!=1:raise ValueError('章节引句须指定唯一章节')
   if quote not in '\n'.join(matches[0]):raise ValueError('引句不在指定章节正文')
 if seen!=set(REQUIRED):raise ValueError('复查项不齐全')
 return dict(reportSha256=digest,reportPath=str(p.resolve()),reviewer=spec['reviewer'],checks=rows,status='declared-content-review-passed' if all(x['status'] in ('passed','not-applicable') for x in rows) else 'partial-or-failed',semanticCertification=False,scope='绑定正文与逐项复查声明，不自动证明判断正确、原文真实或独立专家认可')


def bind_claims(spec):
 """Bind conclusion locations and evidence files; do not infer semantic support."""
 if not isinstance(spec,dict) or not isinstance(spec.get('reportPath'),str) or not spec['reportPath'].strip():raise ValueError('结论记录须为对象并指定正文路径')
 p=Path(spec['reportPath']);raw=p.read_bytes();body='\n'.join(prose_lines(raw.decode('utf-8-sig')));digest=hashlib.sha256(raw).hexdigest()
 if spec.get('reportSha256')!=digest:raise ValueError('正文版本不一致')
 level=spec.get('researchLevel')
 if level not in ('data-check','historical-comparison','focused-appraisal','deep-research'):raise ValueError('研究范围分级无效')
 for field in ('answeredQuestions','unansweredQuestions'):
  if not isinstance(spec.get(field),list) or any(not isinstance(x,str) or not x.strip() for x in spec[field]):raise ValueError('须列明已回答和未回答问题')
 if any(len(x)!=len(set(x)) for x in [spec['answeredQuestions'],spec['unansweredQuestions']]) or set(spec['answeredQuestions'])&set(spec['unansweredQuestions']):raise ValueError('已回答与未回答问题须不重复且不交叉')
 if not spec['answeredQuestions']:raise ValueError('须明确实际回答的问题')
 gap_impacts=spec.get('gapImpacts')
 if gap_impacts is not None:
  if not isinstance(gap_impacts,list):raise ValueError('缺口影响须为列表')
  for gap in gap_impacts:
   if not isinstance(gap,dict) or any(not isinstance(gap.get(key),str) or not gap[key].strip() for key in ('missingData','affectedQuestion','impact','nextStep')):raise ValueError('缺口须说明资料、受影响问题、影响与补充路径')
   if gap['affectedQuestion'] not in spec['unansweredQuestions']:raise ValueError('缺口影响须关联尚未回答的问题')
   if gap['impact'] not in body:raise ValueError('缺口对判断的影响未在正文披露')
   if 'nextStepQuote' in gap and (not isinstance(gap['nextStepQuote'],str) or not gap['nextStepQuote'].strip() or gap['nextStepQuote'] not in body):raise ValueError('补取路径原句未在当前正文定位')
 rows=spec.get('claims')
 if not isinstance(rows,list) or not rows:raise ValueError('须提供核心结论')
 seen=set();bound=[];pdf_pages={}
 for row in rows:
  if not isinstance(row,dict):raise ValueError('结论条目须为对象')
  cid=row.get('id');text=row.get('conclusion')
  if not isinstance(cid,str) or not cid.strip() or cid in seen:raise ValueError('结论编号为空或重复')
  seen.add(cid)
  if not isinstance(text,str) or not text.strip() or text not in body:raise ValueError('结论未出现在绑定正文')
  if not isinstance(row.get('limitations'),str) or not row['limitations'].strip():raise ValueError('结论须附范围与限制')
  evidence=row.get('evidence')
  if not isinstance(evidence,list) or not evidence:raise ValueError('核心结论缺证据')
  if any(not isinstance(item,dict) for item in evidence):raise ValueError('证据条目须为对象')
  required=row.get('requiredEvidenceIds',[])
  if not isinstance(required,list) or any(not isinstance(x,str) or not x.strip() for x in required) or len(set(required))!=len(required):raise ValueError('必需证据编号须为不重复的非空字符串列表')
  evidence_ids=[item.get('id') for item in evidence if 'id' in item]
  if any(not isinstance(x,str) or not x.strip() for x in evidence_ids) or len(set(evidence_ids))!=len(evidence_ids):raise ValueError('证据编号为空或重复')
  if set(required)-set(evidence_ids):raise ValueError('必需证据缺失：'+','.join(sorted(set(required)-set(evidence_ids))))
  bindings=[]
  for item in evidence:
   if not isinstance(item.get('path'),str) or not item['path'].strip():raise ValueError('证据路径缺失')
   ep=Path(item['path']);evidence_raw=ep.read_bytes();ed=hashlib.sha256(evidence_raw).hexdigest()
   if ed!=item.get('sha256'):raise ValueError('证据文件已变化')
   if not isinstance(item.get('locator'),str) or not item['locator'].strip():raise ValueError('须提供证据定位')
   if 'htmlLocator' in item:
    loc=item['htmlLocator']
    if not isinstance(loc,dict) or not isinstance(loc.get('quote'),str) or not loc['quote'].strip():raise ValueError('HTML定位须给出非空正文引句')
    try:prose=html_prose(evidence_raw.decode('utf-8-sig'))
    except (OSError,UnicodeError) as exc:raise ValueError('HTML原文读取失败：'+str(exc)) from exc
    compact=lambda text:re.sub(r'\s+','',text)
    if compact(loc['quote']) not in compact(prose):raise ValueError('引句不在HTML正文提取文本；脚本或样式不作为原文引句')
   if 'pdfLocator' in item:
    loc=item['pdfLocator']
    if not isinstance(loc,dict) or not isinstance(loc.get('page'),int) or isinstance(loc.get('page'),bool) or loc['page']<1 or not isinstance(loc.get('quote'),str) or not loc['quote'].strip():raise ValueError('PDF定位须给出正整数物理页及非空引句')
    cache_key=(str(ep.resolve()),ed)
    if cache_key not in pdf_pages:
     try:
      from pypdf import PdfReader
      pdf_pages[cache_key]=PdfReader(BytesIO(evidence_raw))
     except Exception as exc:raise ValueError('PDF原页读取失败，需依赖或原文复核：'+str(exc)) from exc
    reader=pdf_pages[cache_key]
    if loc['page']>len(reader.pages):raise ValueError('PDF物理页超出文件范围')
    try:page_text=reader.pages[loc['page']-1].extract_text() or ''
    except Exception as exc:raise ValueError('PDF指定页文字提取失败：'+str(exc)) from exc
    normalize=lambda v:re.sub(r'\s+','',v)
    if normalize(loc['quote']) not in normalize(page_text):raise ValueError('引句不在指定PDF物理页；扫描件或特殊版式需另行复核')
   if 'jsonPointer' in item:
    if 'expectedValue' not in item:raise ValueError('结构化定位须保留预期值')
    actual=json_value_at(json.loads(evidence_raw.decode('utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float),item['jsonPointer'])
    if json.dumps(actual,sort_keys=True,ensure_ascii=False,allow_nan=False)!=json.dumps(item['expectedValue'],sort_keys=True,ensure_ascii=False,allow_nan=False):raise ValueError('JSON证据值与记录不一致')
   bindings.append(dict(item,path=str(ep.resolve())))
  if 'limitationQuote' in row:
   if not isinstance(row['limitationQuote'],str) or not row['limitationQuote'].strip() or row['limitationQuote'] not in body:raise ValueError('限制原句未在当前正文定位')
  bound.append(dict(row,evidence=bindings,limitationDisclosureScope='原句存在，不自动证明其与登记限制语义一致或充分',limitationDisclosureStatus='text-bound' if row['limitations'] in body or 'limitationQuote' in row else 'registered-not-located-in-body'))
 return dict(reportPath=str(p.resolve()),reportSha256=digest,researchLevel=level,answeredQuestions=spec['answeredQuestions'],unansweredQuestions=spec['unansweredQuestions'],claims=bound,gapImpacts=gap_impacts,gapNextStepDisclosure=[dict(affectedQuestion=g['affectedQuestion'],status='text-bound' if g['nextStep'] in body or 'nextStepQuote' in g else 'registered-not-located-in-body',scope='文字定位，不认证补取可行性或资料已取得') for g in gap_impacts or []],gapImpactStatus='declared-and-text-bound' if gap_impacts else 'not-declared',status='version-and-evidence-files-bound',semanticCertification=False)


def verify_snapshot_binding(record_path):
 """Check saved files/dependency IDs only; never certify research semantics."""
 p=Path(record_path).resolve()
 data=json.loads(p.read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float)
 if not isinstance(data,dict) or not isinstance(data.get('reportPath'),str):raise ValueError('快照须声明正文路径')
 report=Path(data['reportPath']);report=report if report.is_absolute() else p.parent/report
 if hashlib.sha256(report.read_bytes()).hexdigest()!=data.get('reportSha256'):raise ValueError('正文版本不匹配')
 rows=data.get('evidence');claims=data.get('conclusions')
 if not isinstance(rows,list) or not rows or not isinstance(claims,list) or not claims:raise ValueError('需证据及结论列表')
 ids=set();checked=[]
 for e in rows:
  if not isinstance(e,dict) or not isinstance(e.get('id'),str) or not e['id'].strip() or e['id'] in ids or not isinstance(e.get('path'),str):raise ValueError('证据身份或路径无效/重复')
  ids.add(e['id']);q=Path(e['path']);q=q if q.is_absolute() else p.parent/q
  if hashlib.sha256(q.read_bytes()).hexdigest()!=e.get('sha256'):raise ValueError('证据版本不匹配：'+e['id'])
  checked.append(e['id'])
 seen=set()
 for c in claims:
  if not isinstance(c,dict) or not isinstance(c.get('id'),str) or not c['id'].strip() or c['id'] in seen:raise ValueError('结论身份无效/重复')
  seen.add(c['id']);required=c.get('requiredEvidenceIds')
  if not isinstance(required,list) or not required or any(not isinstance(x,str) for x in required) or len(set(required))!=len(required) or not set(required)<=ids:raise ValueError('结论依赖未完整声明或缺失')
 return {'status':'local-file-versions-and-dependencies-matched','reportSha256':data['reportSha256'],'evidenceIds':checked,'conclusionCount':len(seen),'scope':'仅本地文件版本及依赖引用；非语义充分性、原文真实性或视觉验收'}
