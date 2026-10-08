"""Extract six-column manager tenure table; preserve source and ambiguity."""
import argparse,datetime as dt,hashlib,json,re
from pathlib import Path
from io import BytesIO
from collection_validation import unique_pairs,reject_constant,finite_json_float
from research_library import url as validate_source
import pdfplumber
from verify_original import compact

def classify_role(text):
 manager=bool(re.search(r'本基金(?:的|现任|现任的)?基金经理(?!助理)',text))
 assistant=bool(re.search(r'本基金(?:的|现任|现任的)?基金经理助理',text))
 if manager and assistant:return 'ambiguous'
 if assistant:return 'assistant'
 if manager:return 'manager'
 return 'ambiguous'

def validate_report_dates(period,published):
 for value in (period,published):
  if not isinstance(value,str) or dt.date.fromisoformat(value).isoformat()!=value:raise ValueError('报告期与披露日期须为标准日期')
 if published<period:raise ValueError('披露日期早于报告期末，需核对来源记录')

def table_records(tables,period,published,url):
 validate_report_dates(period,published)
 validate_source(url)
 if not isinstance(tables,list):raise ValueError('任职表输入须为列表')
 active=False;rows=[];eight_column=False;previous_page=0
 for entry in tables:
  if not isinstance(entry,(list,tuple)) or len(entry)!=2:raise ValueError('表格须附物理页码')
  page,table=entry
  if type(page) is not int or page<1 or page<previous_page or not isinstance(table,list):raise ValueError('物理页码或表格结构无效')
  previous_page=page
  if active and rows and page>rows[-1]['pages'][-1]+1:active=False
  for cells in table:
   if not isinstance(cells,(list,tuple)) or any(x is not None and not isinstance(x,str) for x in cells):raise ValueError('表格单元格须为文字或空值')
   if len(cells)==8:
    parts=[compact(x) for x in cells]
    if parts[0]=='姓名' and '任本基金' in parts[3] and '证券' in parts[6]:
     eight_column=True;cells=[parts[0],parts[1],parts[3],parts[4],parts[6],parts[7]]
    elif eight_column and not parts[3] and not parts[5]:cells=[parts[0],parts[1],parts[2],parts[4],parts[6],parts[7]]
    else:continue
   if len(cells)!=6:continue
   c=[compact(x) for x in cells]
   if c[0]=='姓名' and '任本基金' in c[2] and '证券' in c[4]:active=True;continue
   if c[0]=='姓名':active=False;continue
   if not active:continue
   if not c[0] and rows and not c[2] and not c[3] and not c[4] and page<=rows[-1]['pages'][-1]+1:
    rows[-1]['roleText']+=c[1];rows[-1]['biographyText']+=c[5];rows[-1]['pages'].append(page);continue
   for index in [2,3]:
    match=re.fullmatch(r'(\d{4})年(\d{1,2})月(\d{1,2})日',c[index])
    if match:c[index]=dt.date(*map(int,match.groups())).isoformat()
   if not re.fullmatch(r'[\u4e00-\u9fff·]{2,10}',c[0]) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',c[2]):continue
   start=c[2];dt.date.fromisoformat(start)
   end=None if c[3] in ('-','－','—','') else c[3]
   if end and (not re.fullmatch(r'\d{4}-\d{2}-\d{2}',end) or dt.date.fromisoformat(end).isoformat()!=end):raise ValueError('离任日期须为标准日期，需复核原文')
   if start>period or end and (end<start or end>published):raise ValueError('任职日期越界，需复核')
   rows.append(dict(name=c[0],start=start,end=end,confirmedThrough=period,publishedAt=published,sourceUrl=url,locator='PDF页'+str(page),pages=[page],roleText=c[1],biographyText=c[5],reportedExperience=c[4],status='原文表格提取，需阅读角色上下文；非最新在管名单'))
 for r in rows:
  r['locator']='PDF页'+','.join(map(str,sorted(set(r['pages']))))
  r['roleCategory']=classify_role(r['roleText'])
  # Role text can finish on the following page. The active header is explicitly
  # scoped to this fund; never apply this fallback to unrelated product tables.
  if r['roleCategory']=='ambiguous' and '本基金' not in r['roleText'] and '其他基金' not in r['roleText']:
   manager=bool(re.search(r'基金经理(?!助理)',r['roleText']))
   assistant='基金经理助理' in r['roleText']
   if manager != assistant:r['roleCategory']='manager' if manager else 'assistant'
 if len({r['name'] for r in rows})!=len(rows):raise ValueError('同名经理重复行，需处理分段或冲突')
 return rows

def extract_archive(r,base_dir=None):
 if not isinstance(r,dict) or not isinstance(r.get('code'),str) or not re.fullmatch(r'[0-9]{6}',r['code']):raise ValueError('需明确六位基金代码的归档记录')
 metadata=r.get('metadata')
 if not isinstance(metadata,dict) or not all(isinstance(metadata.get(k),str) and metadata[k].strip() for k in ('publishedAt','sourceUrl')):raise ValueError('归档须提供披露日期与来源地址')
 validate_report_dates(r.get('reportDate'),metadata['publishedAt'])
 validate_source(metadata['sourceUrl'])
 if r['status'] not in ('副本身份已匹配','副本身份及股票持仓勾稽完成','股票明细与行业表勾稽完成，会计差额待核验'):raise ValueError('报告身份尚未匹配')
 path=Path(r['documentPath'])
 if base_dir is not None and not path.is_absolute():path=Path(base_dir)/path
 raw=path.read_bytes()
 if hashlib.sha256(raw).hexdigest()!=r['sha256']:raise ValueError('PDF哈希不一致')
 tables=[]
 with pdfplumber.open(BytesIO(raw)) as doc:
  for n,p in enumerate(doc.pages,1):
   for table in p.extract_tables():tables.append((n,table))
 records=table_records(tables,r['reportDate'],r['metadata']['publishedAt'],r['metadata']['sourceUrl'])
 return dict(code=r['code'],reportDate=r['reportDate'],publishedAt=r['metadata']['publishedAt'],sourceSha256=r['sha256'],managers=[x for x in records if x['roleCategory']=='manager'],assistantRecords=[x for x in records if x['roleCategory']=='assistant'],ambiguousRoleRecords=[x for x in records if x['roleCategory']=='ambiguous'],status='已提取需上下文复核' if records else '未发现支持版式任职表',limitations=['证券从业年限为报告自述，不等于本基金任期','任职表可能包含经理助理，必须阅读职务上下文后再纳入经理评价','其他产品名称只作为原文线索，不自动认定代码、任期或当前在管','旧报告不证明今天仍在管；不承诺完整职业履历'])
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('archive',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 if a.out.exists() or a.out.with_suffix('.md').exists():raise FileExistsError('输出已存在')
 r=extract_archive(json.loads(a.archive.read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float),a.archive.resolve().parent);a.out.write_text(json.dumps(r,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')

 lines=['# 年报经理任职记录','',r['status']]
 for m in r['managers']:lines += ['',m['name']+'：任职起点'+m['start']+'；离任日期'+(m['end'] or '未披露')+'；确认至'+m['confirmedThrough']+'。',m['locator'],m['roleText'],m['biographyText'],m['sourceUrl']]
 lines += ['',*r['limitations']];a.out.with_suffix('.md').write_text('\n'.join(lines),encoding='utf-8')
