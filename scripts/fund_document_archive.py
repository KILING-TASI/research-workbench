"""Archive an explicit catalog item; effective version remains unresolved."""
import argparse,datetime as dt,hashlib,json,re,unicodedata
from pathlib import Path
from urllib.parse import urlencode,urlparse
import pdfplumber
from fof_reports import download
from research_brief_html import render
from collection_validation import day,unique_pairs,reject_constant
from research_library import url as validate_source

def resolve(identifier):
 url='https://np-cnotice-stock.eastmoney.com/api/content/ann?'+urlencode(dict(art_code=identifier,client_source='web',page_index=1))
 if not isinstance(identifier,str) or not identifier.strip():raise ValueError('公告ID须非空文本')
 raw=download(url);decoded=json.loads(raw,object_pairs_hook=unique_pairs,parse_constant=reject_constant)
 if not isinstance(decoded,dict) or not isinstance(decoded.get('data'),dict):raise ValueError('公告详情数据结构无效')
 data=decoded['data']
 if data.get('art_code')!=identifier:raise ValueError('公告详情ID不一致')
 attachment=data.get('attach_url')
 if not isinstance(attachment,str) or urlparse(attachment).scheme!='https':raise ValueError('未返回HTTPS附件，不猜下载地址')
 validate_source(attachment)
 return dict(sourceUrl=attachment,detailUrl=url,detailSha256=hashlib.sha256(raw).hexdigest(),detailResponse=data)

def read_pages(path):
 with pdfplumber.open(path) as doc:
  if len(doc.pages)>300:raise ValueError('单次最多提取300页，请明确文档范围')
  return [(n,p.extract_text() or '') for n,p in enumerate(doc.pages,1)]

def normalize(text):return re.sub(r'\s+','',unicodedata.normalize('NFKC',text))

def identity(pages,code,title):
 if not isinstance(code,str) or not re.fullmatch(r'\d{6}',code) or not isinstance(title,str) or not title.strip():raise ValueError('文件代码及标题须明确')
 if not isinstance(pages,list) or any(not isinstance(x,(list,tuple)) or len(x)!=2 or type(x[0])!=int or x[0]<1 or not isinstance(x[1],str) for x in pages):raise ValueError('原文页码与文本结构无效')
 if [x[0] for x in pages]!=sorted(set(x[0] for x in pages)):raise ValueError('原文物理页码须唯一递增')
 front=''.join(normalize(t) for n,t in pages if n<=20)
 title_match=normalize(title) in front
 locations=[n for n,t in pages if re.search(r'(?<!\d)'+re.escape(code)+r'(?!\d)',normalize(t))]
 return dict(matched=title_match and bool(locations),titleMatched=title_match,codePages=locations,checkedPages=len(pages),titleCheckedPages=min(20,len(pages)),limitations=['代码和标题同文档匹配不证明当前生效版本','目录披露日期未据此认定为文件生效日期','份额代码未出现或扫描件无法提取时，保留待核验'])

def report_period(pages,start,end):
 day(start);day(end)
 start=dt.date.fromisoformat(start).isoformat();end=dt.date.fromisoformat(end).isoformat()
 if start>end:raise ValueError('报告期起始日晚于末日')
 evidence=[]
 pattern=r'本报告期自(\d{4})年(\d{1,2})月(\d{1,2})日(?:起)?至(?:(\d{4})年)?(\d{1,2})月(\d{1,2})日止'
 for number,text in pages:
  if number>20:continue
  for match in re.finditer(pattern,normalize(text)):
   y,m,d,y2,m2,d2=match.groups()
   try:
    observed_start=dt.date(int(y),int(m),int(d)).isoformat();observed_end=dt.date(int(y2 or y),int(m2),int(d2)).isoformat()
    if observed_start>observed_end:raise ValueError('原文期间日期顺序异常')
   except ValueError:
    evidence.append({'page':number,'quote':match.group(0),'invalid':True});continue
   evidence.append({'page':number,'quote':match.group(0),'start':observed_start,'end':observed_end})
 pairs={(x.get('start'),x.get('end')) for x in evidence}
 status='matched' if pairs=={(start,end)} else 'missing' if not evidence else 'conflict'
 return {'status':status,'expectedStart':start,'expectedEnd':end,'evidence':evidence,'checkedPageLimit':20,'limitations':['仅核对明确报告期句，不以标题年份或封面日期代替期间','未核验目录首次公开时间、正文数值或全报告适用性']}

def catalog_from_bundle(bundle,code):
 from collection_validation import report_contract
 report_contract(bundle)
 if not isinstance(code,str) or not re.fullmatch(r'\d{6}',code):raise ValueError('基金代码须六位字符串')
 matches=[row for row in bundle.get('rows',[]) if row.get('code')==code and row.get('kind') in ['fund','etf']]
 if len(matches)!=1:raise ValueError('需唯一基金或ETF对象，不将股票公告当作基金文件')
 row=matches[0];items=row.get('announcements',[])
 if not items:raise ValueError('未取得该基金公告目录，先取目录或补充正式来源')
 if any(item.get('provenance')!='third-party-fund-catalog' for item in items):raise ValueError('目录来源类型不符，不能转换股票公告')
 return {'code':code,'asOf':bundle['asOf'],'rows':[{'id':item['id'],'title':item['title'],'publishedAt':item['date'],'documentRole':'catalog-announcement'} for item in items],
         'sourceBundleType':bundle.get('type'),'originalVerified':False}

def run(catalog,identifier,directory,resolve_fn=resolve,download_fn=download,pages_fn=read_pages,expected_period=None):
 if not isinstance(catalog,dict):raise ValueError('基金目录须为对象')
 code=catalog['code'];day(catalog['asOf'])
 if expected_period is not None:
  if not isinstance(expected_period,dict) or set(expected_period)!={'start','end'}:raise ValueError('报告期须提供start及end')
  day(expected_period['start']);day(expected_period['end'])
  start=dt.date.fromisoformat(expected_period['start']).isoformat();end=dt.date.fromisoformat(expected_period['end']).isoformat()
  if start>end or end>catalog['asOf']:raise ValueError('报告期无效或晚于截止日')
 if not isinstance(code,str) or not re.fullmatch(r'\d{6}',code):raise ValueError('基金代码无效')
 rows=catalog.get('rows',catalog.get('candidates'))
 if not isinstance(rows,list):raise ValueError('目录候选列表缺失')
 if 'rows' in catalog and 'candidates' in catalog and catalog['rows']!=catalog['candidates']:raise ValueError('目录候选字段冲突')
 clues=catalog.get('amendmentClues',[])
 if not isinstance(clues,list):raise ValueError('修订线索须列表')
 if any(not isinstance(x,dict) or any(not isinstance(x.get(k),str) or not x[k].strip() for k in ['id','title','publishedAt']) for x in rows+clues):raise ValueError('目录条目须明确公告ID、标题与披露日')
 matches=[(x,'legal-document') for x in rows if x['id']==identifier]+[(x,'amendment-clue') for x in clues if x['id']==identifier]
 if len(matches)!=1:raise ValueError('需唯一且已取得的目录公告ID')
 item,item_kind=matches[0]
 if item.get('documentRole')=='catalog-announcement':item_kind='catalog-announcement'
 day(item['publishedAt'])
 if item['publishedAt']>catalog['asOf']:raise ValueError('公告披露晚于截止日')
 out=Path(directory)
 if out.exists():raise FileExistsError('输出目录已存在')
 out.mkdir(parents=True);result=dict(catalogItemKind=item_kind,code=code,catalogItem=item,asOf=catalog['asOf'],status='附件未取得',documentPath=None,sha256=None,identity=None,reportFees=None,gaps=[],effectiveVersionVerified=False,reportPeriod=None)
 try:
  metadata=resolve_fn(identifier);validate_source(metadata['sourceUrl']);result['metadata']=metadata;raw=download_fn(metadata['sourceUrl'])
  if not raw.startswith(b'%PDF'):raise ValueError('附件不是PDF')
  path=out/'document.pdf';path.write_bytes(raw);result.update(documentPath=str(path.resolve()),sha256=hashlib.sha256(raw).hexdigest(),status='PDF已下载，身份待核验')
  pages=pages_fn(path);check=identity(pages,code,item['title']);result['identity']=check
  empty=[n for n,text in pages if not text.strip()]
  result['textExtractionSummary']={'totalPages':len(pages),'pagesWithText':len(pages)-len(empty),'emptyTextPages':empty,'meaning':'未取得文本可能为空白页、扫描页或提取失败，不自动认定缺页'}
  if empty:result['gaps'].append('有'+str(len(empty))+'页未取得文本，可能为空白或扫描页，需核对原页；不据此认定缺页或条款不存在')
  if check['matched']:
   result['status']='PDF代码与标题已匹配，正文及报告期待核验' if item_kind=='catalog-announcement' else 'PDF代码与标题已匹配，生效关系待核验'
   if expected_period is not None:
    result['reportPeriod']=report_period(pages,start,end)
    if result['reportPeriod']['status']=='matched':result['status']='PDF代码、标题及明确报告期已匹配，正文数值待核验'
    else:
     result['status']='PDF身份已匹配，报告期缺失或冲突待核验'
     result['gaps'].append('原文明示报告期未唯一匹配请求期间，不能作为该期研究依据')
   from report_fee_evidence import statements,sales_service_statements
   if item_kind=='legal-document':
    result['reportFees']=statements(pages)
    result['salesServiceFees']=sales_service_statements(pages)
   elif item_kind=='amendment-clue':result['gaps'].append('修订公告须逐基金名单核对，不以全文通用费率抽取替代')
   else:result['gaps'].append('本次只核对公告身份，未核验正文数值、报告期适用性或费率')
  else:result['gaps'].append('PDF全文代码与前20页标题未同时匹配，不输出费率')
 except Exception as exc:result['gaps'].append(type(exc).__name__+': '+str(exc))
 if item_kind=='catalog-announcement':result['gaps']+=['第三方附件副本尚未核实官方发布网页','本次尚未逐项核验正文数值、报告期及披露口径','代码与标题匹配不代表完整持仓、财务勾稽或投资范围核验完成']
 else:result['gaps']+=['第三方附件副本尚未核实官方发布网页','未联合核对合同修订、补充公告及生效日期，费率不作为当前有效费率','本入口未自动提取申购/赎回费阶梯及多份额全部收费规则']
 if result.get('reportPeriod',{} ) and result['reportPeriod']['status']=='matched':result['gaps']=[g.replace('正文数值、报告期适用性或费率','正文数值、其他适用条件或费率').replace('正文数值、报告期及披露口径','正文数值及披露口径') for g in result['gaps']]
 lines=['# 基金文件原文资料','',item['title'],result['status'],f"目录披露日期{item['publishedAt']}；资料截止日{catalog['asOf']}。"]
 if result['identity']:
  check=result['identity'];lines+=['','## 文件身份依据','代码出现的PDF物理页：'+('、'.join(map(str,check['codePages'])) if check['codePages'] else '未匹配')+'。','标题在前'+str(check['titleCheckedPages'])+'页'+('匹配。' if check['titleMatched'] else '未匹配。')]
 if result.get('reportPeriod'):
  period=result['reportPeriod'];lines+=['','## 报告期依据','请求期间：'+period['expectedStart']+'至'+period['expectedEnd']+'；'+('原文明示期间匹配。' if period['status']=='matched' else '未唯一匹配，保留待核验。')]
  for item in period['evidence']:lines.append('PDF第'+str(item['page'])+'页：'+item['quote'])
 if result.get('textExtractionSummary'):
  quality=result['textExtractionSummary'];lines+=['','## 文本提取范围','取得文本'+str(quality['pagesWithText'])+'/'+str(quality['totalPages'])+'页。']
  if quality['emptyTextPages']:lines.append('未取得文本的物理页：'+ '、'.join(map(str,quality['emptyTextPages']))+'。'+quality['meaning'])
 if result['sha256']:lines.append('文件摘要（SHA-256）：'+result['sha256'])
 if result['reportFees']:
  lines+=['','## 原文费率依据','以下为文件中的费率措辞，不等于当前有效收费规则。']
  for label,fee in result['reportFees'].items():
   lines.append(label+'：'+(str(fee['value'])+'%/年' if fee['value'] is not None else fee['status']))
   for e in fee['evidence']:lines.append(f"PDF第{e['page']}页：{e['context']}")
 lines+=['','## 待核验事项']+['- '+g for g in result['gaps']]
 if result.get('metadata'):lines+=['',result['metadata']['sourceUrl']]
 text='\n'.join(lines);html=render(text);serialized=json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)
 (out/'result.json').write_text(serialized,encoding='utf-8')
 (out/'原文资料.md').write_text(text,encoding='utf-8');(out/'原文资料.html').write_text(html,encoding='utf-8');return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('catalog',type=Path);p.add_argument('--period-start');p.add_argument('--period-end');p.add_argument('--code',help='输入统一取数结果时指定基金或ETF代码');p.add_argument('--id',required=True);p.add_argument('--out-dir',required=True);a=p.parse_args();document=json.loads(a.catalog.read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant);catalog=catalog_from_bundle(document,a.code) if a.code else document
 if bool(a.period_start)!=bool(a.period_end):p.error('报告期须同时提供起始日和末日')
 period={'start':a.period_start,'end':a.period_end} if a.period_start else None
 run(catalog,a.id,a.out_dir,expected_period=period)
