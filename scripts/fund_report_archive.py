"""Archive disclosed annual/interim fund report copies, identity first."""
import argparse,datetime as dt,hashlib,json,re
from pathlib import Path
from decimal import Decimal
def pdf_module():
 try:
  import pdfplumber
 except ModuleNotFoundError as exc:
  if exc.name != 'pdfplumber': raise
  raise RuntimeError('PDF报告核验需要pdfplumber；请按references/standalone-install.md安装PDF依赖后重试。未执行原文核验。') from exc
 return pdfplumber

def discover(*args,**kwargs):
 from fof_reports import discover as operation
 return operation(*args,**kwargs)

def download(*args,**kwargs):
 from fof_reports import download as operation
 return operation(*args,**kwargs)

def inspect_and_parse(*args,**kwargs):
 from fof_reports import inspect_and_parse as operation
 return operation(*args,**kwargs)

def normalized_year_title(*args):
 from fof_reports import normalized_year_title as operation
 return operation(*args)

def compact(*args):
 from verify_original import compact as operation
 return operation(*args)

def dates_in(*args):
 from verify_original import dates_in as operation
 return operation(*args)
from collection_validation import day
from research_library import url as validate_source

def identity(path,code,period,metadata):
 if not isinstance(code,str) or not re.fullmatch(r'\d{6}',code) or not isinstance(metadata,dict) or not isinstance(metadata.get('title'),str) or not metadata['title'].strip():raise ValueError('报告代码或标题身份不明确')
 day(period);day(metadata['publishedAt'])
 with pdf_module().open(path) as doc:
  front_raw='\n'.join(p.extract_text() or '' for p in doc.pages[:12]);front=compact(front_raw)
  if not re.search(r'(?<!\d)'+code+r'(?!\d)',front_raw):raise ValueError('报告未确认基金代码')
  if compact(normalized_year_title(metadata['title'])) not in normalized_year_title(front) or period not in dates_in(front):raise ValueError('报告标题或所属期不匹配')
  if metadata['publishedAt'] not in dates_in(doc.pages[0].extract_text() or ''):raise ValueError('送出日期与目录不匹配')
  return dict(pages=len(doc.pages),checkedPages=min(12,len(doc.pages)),identityStatus='代码、标题、所属期、送出日期匹配；非官方网页核验')
def manager_name_evidence(pages):
 records=[]
 for page,text in pages:
  if page>12:continue
  for line in text.splitlines():
   match=re.match(r'^\s*基金管理人(?:名称\s*[:：]?\s*|[:：]\s*)([^\n]+)$',line)
   if not match:continue
   name=compact(match.group(1))
   if re.fullmatch(r'[\u4e00-\u9fffA-Za-z（）()·]+(?:股份有限公司|有限责任公司|有限公司)',name):records.append({'name':name,'physicalPage':page,'quote':line})
 names={x['name'] for x in records}
 return {'status':'unique-original-manager-name' if len(names)==1 else 'missing' if not names else 'conflict','name':next(iter(names)) if len(names)==1 else None,'records':records,'scope':'前12页管理人明确标签，不证明官方发布、当前生效关系或经理履历'}

def scope_notes(pages):
 notes=[]
 for number,text in pages:
  normalized=re.sub(r'\s+','',text)
  for match in re.finditer(r'(?:上表中的权益投资|股票投资的公允价值|股票投资的估值增值)[^。]{0,100}可退替代款[^。]{0,80}。',normalized):
   notes.append(dict(kind='refundable-substitution-valuation-scope',page=number,quote=match.group(0),adjustmentAmountCNY=None,meaning='会计股票或权益范围含替代款估值调整；未取得独立金额，不直接解释或核销持仓差额'))
  # Require body section and exact disclosure, not a table-of-contents mention.
  for match in re.finditer(r'(?m)^[78]\.4\s*期末按[^\n]*所有权益投资明细\s*\n(本基金本报告期末未持有股票及存托凭证[。.]?)',text):
   notes.append(dict(kind='no-direct-equity',page=number,quote=match.group(0),meaning='仅说明直接股票及存托凭证为空；不说明基金投资或衍生品底层权益风险为零'))
  if re.search(r'(?m)^[78]\.10\s*期末按[^\n]*前十名基金投资明细',text):
   notes.append(dict(kind='fund-investment-disclosure',page=number,quote=text,meaning='存在基金投资明细章节；须核对子基金身份及报告后穿透，前十名不自动视为完整基金表'))
  if '期货投资采用当日无负债结算制度' in text:
   match=re.search(r'期货投资采用当日无负债结算制度[^\n]*(?:\n[^\n]*){0,3}',text)
   notes.append(dict(kind='futures-net-value-not-exposure',page=number,quote=match.group(0),meaning='期货公允价值净额为零不代表名义敞口为零；合约市值、保证金及对冲方向需独立核对'))
 return notes

def top_fund_rows(document):
 rows=[];started=False;finished=False
 for page_no,page in enumerate(document.pages,1):
  starts=page.search(r'(?m)^[78]\.10\s*期末按[^\n]*前十名基金投资明细\s*$')
  if starts:started=True
  if not started or finished:continue
  if '单位：人民币元' not in compact(page.extract_text() or ''):raise ValueError('基金投资明细页未确认人民币金额单位')
  top=starts[0]['top'] if starts else 0
  ends=page.search(r'(?m)^[78]\.11\s*(?:投资组合报告附注|报告期末本基金投资股指期货的交易情况说明|本基金投资股指期货的投资政策)\s*$');bottom=ends[0]['top'] if ends else float('inf')
  for table in page.find_tables():
   if table.bbox[1]<top or table.bbox[1]>=bottom:continue
   cells=table.extract()
   if not cells or len(cells[0])!=7:continue
   for original in cells:
    c=[compact(x) for x in original]
    if len(c)!=7 or not c[0].isdigit():continue
    if int(c[0])!=len(rows)+1:raise ValueError('前十名基金表序号不连续，不能补造漏行')
    if not all(c[i] for i in [1,2,3,4,5,6]):raise ValueError('基金投资明细字段缺失')
    if len(rows)>=10:raise ValueError('前十名基金表超过十行，需复核章节范围')
    for token in [c[5],c[6]]:
     if not re.fullmatch(r'-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?',token):raise ValueError('基金投资金额或比例格式无效')
    amount=Decimal(c[5].replace(',',''));weight=Decimal(c[6].replace(',',''))
    if not amount.is_finite() or not weight.is_finite() or amount<0 or weight<0:raise ValueError('基金投资金额或披露权重无效')
    rows.append(dict(rank=int(c[0]),name=c[1],reportedFundType=c[2],reportedOperation=c[3],manager=c[4],marketValueCNY=str(amount),reportedWeightPct=str(weight),page=page_no,tableBBox=list(table.bbox),originalCells=original,code=None,market=None,identityStatus='原文未提供代码，待独立身份关联'))
  if ends:finished=True
 if not rows:return None
 if not finished:raise ValueError('前十名基金表结束边界未取得')
 return dict(rows=rows,disclosureScope='top-ten-fund-investments',complete=False,accountingTotalVerified=False,limitations=['只提取前十名，不证明基金投资全部披露','原文名称不替代证券代码身份，未自动关联底层报告','保留披露比例，尚未独立核对净资产分母与基金投资会计合计','基金投资与股票表分开；不可据子基金名称估算底层权益仓位'])

def report_markdown(result):
 meta=result['metadata']
 lines=['# 基金报告资料核对','',meta['title'],result['status'],f"报告期{result['reportDate']}；披露日期{meta['publishedAt']}。",'','## 原文口径说明']
 notes=[x for x in result.get('portfolioScopeEvidence',[]) if x['kind']!='fund-investment-disclosure']
 if not notes:lines.append('本次未提取到支持版式的范围说明；不代表原文不存在相关条款。')
 for x in notes:
  lines+=['- PDF第'+str(x['page'])+'页：'+x['quote'].replace('\n',' '),'  '+x['meaning']]
  if x['kind']=='refundable-substitution-valuation-scope':lines.append('  调整金额尚未单独取得，不能据此认定股票明细与会计余额已全额勾稽。')
 lines+=['','## 资料缺口']+['- '+x for x in result['gaps']]
 lines+=['','## 来源','[报告原文副本]('+meta['sourceUrl']+')','文件摘要（SHA-256）：'+result['sha256']]
 return '\n'.join(lines)

def run(code,period,asof,directory,parse_holdings=False,discover_fn=discover,download_fn=download,identity_fn=identity,parse_fn=inspect_and_parse):
 if not re.fullmatch(r'\d{6}',code):raise ValueError('基金代码须六位')
 for d in [period,asof]:day(d)
 if period>asof:raise ValueError('报告期晚于截止日')
 out=Path(directory)
 if out.exists():raise FileExistsError('输出目录已存在')
 meta=discover_fn(code,period,asof)
 if not isinstance(meta,dict) or not isinstance(meta.get('title'),str) or not meta['title'].strip():raise ValueError('公告目录标题缺失，不能下载后默认匹配')
 day(meta.get('publishedAt'));validate_source(meta.get('sourceUrl'))
 if not period<=meta['publishedAt']<=asof:raise ValueError('披露日期越界')
 raw=download_fn(meta['sourceUrl'])
 if not raw.startswith(b'%PDF'):raise ValueError('附件不是PDF')
 out.mkdir(parents=True);path=out/'report.pdf';path.write_bytes(raw)
 result=dict(code=code,reportDate=period,asOf=asof,metadata=meta,sha256=hashlib.sha256(raw).hexdigest(),retrievedAt=dt.datetime.now(dt.timezone.utc).isoformat(),documentPath=str(path.resolve()),status='已下载待核验',holdings=None,gaps=[])
 try:
  result.update(identity_fn(path,code,period,meta));result['status']='副本身份已匹配'
  try:
   with pdf_module().open(path) as doc:
    texts=[(n,p.extract_text() or '') for n,p in enumerate(doc.pages,1)]
    result['portfolioScopeEvidence']=scope_notes(texts)
    result['managerNameEvidence']=manager_name_evidence(texts)
    result['hasCompleteFundInvestmentSection']=any(re.search(r'(?m)^[78]\.12\.2\s*报告期末按公允价值',p.extract_text() or '') for p in doc.pages)
    result['hasTargetFundSection']=any(re.search(r'(?m)^2\.1\.1\s*目标基金基本情况\s*$',p.extract_text() or '') for p in doc.pages)
    try:
     result['fundInvestmentDisclosure']=top_fund_rows(doc)
     result['fundInvestmentParseStatus']='parsed-top-ten-only' if result['fundInvestmentDisclosure'] else 'not-found-or-layout-unrecognized'
     if result['fundInvestmentDisclosure'] is None and (result['hasTargetFundSection'] or result.get('hasCompleteFundInvestmentSection') or any(x['kind']=='fund-investment-disclosure' for x in result['portfolioScopeEvidence'])):result['gaps'].append('基金投资章节存在但明细未取得；不认定未持有基金')
    except Exception as exc:result['gaps'].append('基金投资明细未提取：'+str(exc))
  except Exception as exc:result['gaps'].append('投资范围原文说明未提取：'+str(exc))
  if parse_holdings:
   try:
    parsed=parse_fn(path,code,period,meta)
    if not isinstance(parsed,dict) or not isinstance(parsed.get('holdings'),list) or not parsed['holdings'] or parsed.get('disclosureScope')!='completeEquity':
     raise ValueError('完整股票解析结果缺失或结构无效')
    expected={'id':code,'reportDate':period,'publishedAt':meta['publishedAt'],'sourceUrl':meta['sourceUrl'],'sourceSha256':result['sha256']}
    if any(parsed.get(key)!=value for key,value in expected.items()):raise ValueError('股票结果身份、日期或文件来源与本报告不一致')
    reconciliation=parsed.get('accountingReconciliation',{})
    if not isinstance(reconciliation,dict):raise ValueError('会计勾稽状态无效')
    result['holdings']=parsed
    result['status']='副本身份及股票持仓勾稽完成'
    if reconciliation.get('status')=='unresolved':
     result['status']='股票明细与行业表勾稽完成，会计差额待核验'
     result['gaps'].append('股票明细与资产负债表余额存在未解释差额，暂不进入严格核验筛选及穿透链路')
   except Exception as exc:result['gaps'].append('股票持仓解析未完成：'+str(exc))
 except Exception as exc:result['gaps'].append('身份核验未完成：'+str(exc))
 result['gaps']+=['第三方PDF副本未核实官方发布网页','基金合同及最新费率原文仍需另取','股票持仓提取不代表债券及衍生品全部持仓完整']
 (out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 (out/'报告获取说明.md').write_text(report_markdown(result),encoding='utf-8');return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--code',required=True);p.add_argument('--period',required=True);p.add_argument('--as-of',required=True);p.add_argument('--out-dir',required=True);p.add_argument('--holdings',action='store_true');a=p.parse_args()
 try:
  pdf_module()  # Validate required PDF support before fetching or writing a report.
  run(a.code,a.period,a.as_of,a.out_dir,a.holdings)
 except RuntimeError as exc:
  p.exit(2,str(exc)+'\n')
