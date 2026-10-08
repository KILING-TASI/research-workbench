"""Build known manager-product links from verified fund report archives."""
import argparse,json,hashlib,re,datetime
from pathlib import Path
import pdfplumber
from verify_original import compact
from report_manager_tenure import extract_archive
from manager_products import build as registry_build,markdown
from fund_series_tools import NOTICE
from research_brief_html import render
from collection_validation import day

def company_rows(tables):
 records=[]
 for page,bbox,rows in tables:
  if not rows:continue
  header=[compact(x) for x in rows[0]]
  if header.count('基金管理人')!=1:continue
  column=header.index('基金管理人')
  for row in rows[1:]:
   if row and compact(row[0])=='名称' and len(row)>column:
    value=compact(row[column])
    if value:records.append(dict(value=value,page=page,tableBBox=bbox,originalCells=row))
 if not records or len({x['value'] for x in records})!=1:raise ValueError('管理公司名称缺失或冲突')
 return records

COMPANY_START=r'(?m)^(?:2\.3\s*)?基金管理人和基金托管人\s*$'
COMPANY_END=r'(?m)^(?:2\.[45]\s*)?信息披露方式\s*$'

def company(report):
 path=Path(report['documentPath'])
 if not report.get('identityStatus') or hashlib.sha256(path.read_bytes()).hexdigest()!=report['sha256']:raise ValueError('报告身份或摘要未核验')
 tables=[];active=False;ended=False
 with pdfplumber.open(path) as d:
  for n,page in enumerate(d.pages,1):
   starts=page.search(COMPANY_START)
   if starts:active=True
   if not active:continue
   ends=page.search(COMPANY_END)
   for t in page.find_tables():
    if starts and t.bbox[3]<=starts[0]['top'] or ends and t.bbox[1]>=ends[0]['top']:continue
    tables.append((n,list(t.bbox),t.extract()))
   if ends:ended=True;break
 if not ended:raise ValueError('基金管理人章节边界未取得')
 return company_rows(tables)

def run(dossiers,asof,manager_name=None):
 day(asof)
 if manager_name is not None and (not isinstance(manager_name,str) or not manager_name.strip()):raise ValueError('经理姓名筛选须为非空文字或明确未指定')
 if not isinstance(dossiers,list) or not 1<=len(dossiers)<=500:raise ValueError('需要1至500份档案')
 products=[];pending=[];evidence={};seen=set()
 for dossier in dossiers:
  if not isinstance(dossier,dict):raise ValueError('基金档案必须为对象')
  code=dossier.get('code')
  if not isinstance(code,str) or not re.fullmatch(r'\d{6}',code) or code in seen:raise ValueError('基金代码非法或重复')
  seen.add(code)
  try:
   report=dossier['report']
   if dossier['asOf']!=asof or report['asOf']!=asof or report['code']!=code:raise ValueError('档案与报告代码/截止日不一致')
   published=day(report['metadata']['publishedAt']);period=day(report['reportDate'])
   if period>published or published>day(asof):raise ValueError('任职报告期、披露日与研究截止日不一致；不使用截止日后的履历')
   issuer=company(report);tenure=extract_archive(report)
   if not tenure['managers']:raise ValueError('没有明确本基金经理任职记录')
   products.append(dict(managerCompany=issuer[0]['value'],name=report['metadata']['title'],evaluationInput=dict(code=code,asOf=asof,managers=tenure['managers'])))
   evidence[code]=dict(companyEvidence=issuer,sourceSha256=report['sha256'],sourceUrl=report['metadata']['sourceUrl'],reportDate=report['reportDate'],publishedAt=report['metadata']['publishedAt'],assistantRecords=tenure.get('assistantRecords',[]),ambiguousRoleRecords=tenure.get('ambiguousRoleRecords',[]))
  except (ValueError,KeyError,OSError,TypeError) as exc:pending.append(dict(code=code,reason='原文任职关联未完成：'+str(exc)))
 if products:r=registry_build(dict(asOf=asof,managerName=manager_name,products=products))
 else:r=dict(type='manager-product-registry',asOf=asof,query=manager_name,scope='已提供公开任职证据，不是经理全职业履历',managers=[],conflicts=[],gaps=[],riskNotice=NOTICE,limitations=['未取得可核验任职关系，不代表经理没有管理产品；当前名单及职业履历均未完成核验'])
 r['status']='partial' if pending else 'verified-input-scope'
 if not products:r['status']='unavailable'
 r['gaps']+=pending;r['reportEvidence']=evidence;r['requestedCodes']=[x['code'] for x in dossiers];r['limitations'].append('本次桥接不计算任期收益，需另提供口径已核验的历史净值；渠道阶段收益不能代替任期收益')
 return r
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('input');p.add_argument('--out',required=True);a=p.parse_args();out=Path(a.out)
 if any(x.exists() for x in [out,out.with_suffix('.md'),out.with_suffix('.html')]):raise FileExistsError('输出已存在')
 s=json.loads(Path(a.input).read_text(encoding='utf-8-sig'));r=run(s['dossiers'],s['asOf'],s.get('managerName'));out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8');text=markdown(r);out.with_suffix('.md').write_text(text,encoding='utf-8');out.with_suffix('.html').write_text(render(text),encoding='utf-8')
