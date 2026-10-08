"""Bind financial calculation inputs before commentary or workbook export."""
import hashlib,json
from pathlib import Path
from collection_validation import unique_pairs,reject_constant

def company_rows(document):
 if not isinstance(document,dict) or not isinstance(document.get("companies"),list):raise ValueError("财务输入须为公司对象列表")
 rows=document["companies"];codes=[]
 for row in rows:
  if not isinstance(row,dict) or not isinstance(row.get("code"),str) or len(row["code"])!=6 or not row["code"].isascii() or not row["code"].isdigit():raise ValueError("公司代码须为六位数字")
  codes.append(row["code"])
 if len(codes)!=len(set(codes)):raise ValueError("计算公司重复，不能重复计入分组")
 return rows


def bound_archives(financial,paths):
 companies=company_rows(financial)
 if not isinstance(paths,(list,tuple)):raise ValueError('财务档案路径须为列表')
 archives={};hashes={}
 for path in paths:
  raw=Path(path).read_bytes();a=json.loads(raw,object_pairs_hook=unique_pairs,parse_constant=reject_constant)
  if not isinstance(a,dict) or not isinstance(a.get('code'),str) or len(a['code'])!=6 or not a['code'].isascii() or not a['code'].isdigit():raise ValueError('档案公司代码无效')
  code=a['code']
  if code in archives:raise ValueError('重复公司财务档案，不能静默覆盖')
  archives[code]=a;hashes[code]=hashlib.sha256(raw).hexdigest()
 for c in companies:
  if c['code'] not in archives:raise ValueError('缺少计算所用公司财务档案：'+c['code'])
  if not c.get('archiveSha256') or hashes[c['code']]!=c['archiveSha256']:raise ValueError('财务档案与计算时哈希不一致')
 return archives,hashes


def bound_originals(original,archive_path):
 base=Path(archive_path).resolve().parent;bindings=[]
 for c in company_rows(original):
  if c.get('parseStatus')!='parsed':continue
  code=c['code']
  if not isinstance(code,str) or len(code)!=6 or not code.isdigit():raise ValueError('原文证券代码无效')
  path=base/code/'report.pdf'
  if not path.is_file() or not c.get('fileSha256') or hashlib.sha256(path.read_bytes()).hexdigest()!=c['fileSha256']:raise ValueError('原PDF缺失或哈希变化：'+code+'；应重新获取或解析')
  from research_report_reading import verify_pdf_pages
  integrity=verify_pdf_pages(dict(pdfPath=str(path),sha256=c['fileSha256'],parser=c.get('parser','pdfplumber'),pages=c.get('pages')))
  bindings.append(dict(code=code,path=str(path),sha256=c['fileSha256'],evidenceIntegrity=integrity))
 return bindings


def verify_financial_snapshot(financial,archives):
 from industry_financials import analyze_company,summarize_companies
 fresh=[]
 for company in company_rows(financial):
  rebuilt=analyze_company(archives[company['code']],company['metadata'],financial['period'])
  for key in ['period','metrics','ratios','signals','gaps','sourceUrls']:
   if company.get(key)!=rebuilt.get(key):
    raise ValueError('财务快照与绑定档案重新计算不一致：'+company['code']+' '+key)
  fresh.append(rebuilt)
 if financial.get('groups')!=summarize_companies(fresh):
  raise ValueError('分组快照与绑定档案重新计算不一致')
 return 'archive-recalculated-matched'


def report_metadata_warnings(report):
 if report and report.get('disclosureStatus') in ['explicit-source-unverified','user-provided-unverified']:
  return ['报告来自明确链接或补充文件；公告披露日期及版本关系未由目录核验。数值匹配不代表这些元数据已确认。']
 return []

def income_basis_warnings(archive,period):
 from industry_financials import observation
 total,tr,_=observation(archive,'income',period,'TOTAL_OPERATE_INCOME')
 operating,orr,_=observation(archive,'income',period,'OPERATE_INCOME')
 if tr or orr or abs(total-operating)<=max(0.02,abs(total)*1e-12):return []
 return [dict(kind='total-operating-income-differs',warning='本期累计营业总收入与营业收入不同；本工具收入字段取营业收入，净利润率为合并净利润除以营业收入，不能当作以营业总收入为分母的比率。差异的业务构成需结合附注核查。',totalOperatingIncome=total,operatingIncome=operating,period=period)]

def comparability_warnings(report):
 if not report or report.get('parseStatus')!='parsed':return []
 result=[]
 for page in report.get('pages',[])[:12]:
  text=page['text']
  import re
  compact=re.sub(r'\s+','',text)
  if '本报告期' in compact and '比较期间财务数据' in compact and ('追溯调整' in compact or '追溯重述' in compact):
   result.append(dict(page=page['page'],kind='comparative-restatement-disclosed',warning='本期报告披露比较期间财务数据追溯调整；渠道历史值未确认采用同一重述版本，同比及跨期差分需复核，不能称原文已确认。'))
  if all(term in compact for term in ['主要会计数据','上年同期','调整后','调整前']) and ('营业收入' in compact or '经营活动产生的' in compact):
   result.append(dict(page=page['page'],kind='comparative-adjusted-columns-disclosed',warning='主要会计数据并列披露上年同期调整后与调整前数值；比较基数存在版本差别。须确认渠道值采用哪一列及相邻期调整是否一致，不把新版比较列与旧报告直接混算，也不由表头推断调整原因。'))
 # Other consolidation changes are commonly in later notes, outside the
 # front-of-report comparative tables. Preserve a clue, never infer amounts.
 for page in report.get('pages',[]):
  import re
  compact=re.sub(r'\s+','',page['text'])
  heading='其他原因的合并范围变动'
  start=compact.find(heading)
  if start<0:continue
  segment=compact[start:start+350]
  checkbox=re.search(r'(√适用□不适用|□适用√不适用)',segment)
  if checkbox and checkbox.group(1)=='√适用□不适用':
   result.append(dict(page=page['page'],kind='other-consolidation-scope-change-disclosed',
                      excerpt=segment,
                      warning='原文其他原因的合并范围变动列为适用；新设或注销等影响需按附注核查。未量化对累计输入及单季差分的影响，不能称范围未变，也不能由此推断经营变化原因。'))
 return result
