"""Issuer-specific Efunds document binding; not an all-manager resolver."""
import argparse,datetime as dt,hashlib,json,re,urllib.request
from pathlib import Path
from urllib.parse import urlparse
from fund_document_archive import read_pages,normalize
from fof_reports import download,normalized_year_title
from report_fee_evidence import statements
from research_brief_html import render
from verify_original import dates_in
from collection_validation import day,unique_pairs,reject_constant
API='https://api.efunds.com.cn/xcowch/front/contents'

def report_identity(pages,code,title):
 normalized=normalize(normalized_year_title(title))
 period=re.search(r'(\d{4})年(中期|半年度|年度)报告',normalized)
 quarter=re.search(r'(\d{4})年第([1-4])季度报告',normalized)
 if period:end=period[1]+('-06-30' if period[2] in ('中期','半年度') else '-12-31')
 elif quarter:end=quarter[1]+{'1':'-03-31','2':'-06-30','3':'-09-30','4':'-12-31'}[quarter[2]]
 elif re.search(r'(中期|半年度|年度|季度)报告',normalized):return {'status':'pending','expectedPeriodEnd':None,'codeMatchedInFront':False,'periodEndMatchedInFront':False,'checkedPageLimit':12,'scope':'识别为定期报告，但年份或期间类型未唯一解析；不按法律文件绕过期间检查。'}
 else:return {'status':'not-periodic-report','scope':'法律文件或其他公告仍按目录与标题关联，不自动要求单一报告期末。'}
 front='\n'.join(text for n,text in pages if n<=12)
 code_match=bool(re.search(r'(?<!\d)'+re.escape(code)+r'(?!\d)',front));date_match=end in dates_in(front)
 return {'status':'matched' if code_match and date_match else 'pending','expectedPeriodEnd':end,'codeMatchedInFront':code_match,'periodEndMatchedInFront':date_match,'checkedPageLimit':12,'scope':'前部代码与标题对应期末核对，非全文、有效版本或首次公开认证。'}
def select(payload,title,published):
 if not isinstance(payload,dict) or type(payload.get('status'))!=int or payload['status']!=1 or not isinstance(payload.get('data'),dict):raise ValueError('官方目录响应失败')
 rows=payload.get('data',{}).get('data')
 if not isinstance(rows,list) or any(not isinstance(r,dict) for r in rows):raise ValueError('官方目录布局异常')
 matched=[r for r in rows if r.get('title')==title and str(r.get('publishDate',''))[:10]==published]
 if len(matched)!=1:raise ValueError('指定标题/披露日未唯一匹配；不自动选择最近版本')
 row=matched[0];url=row.get('path');parsed=urlparse(url or '')
 if parsed.scheme!='https' or parsed.hostname!='cdn.efunds.com.cn' or parsed.username is not None or parsed.password is not None or not parsed.path.endswith('.pdf'):raise ValueError('官方目录未返回明确官方PDF')
 return row

def fetch_catalog(params):
 req=urllib.request.Request(API,data=json.dumps(params).encode(),headers={'Content-Type':'application/json','User-Agent':'Mozilla/5.0','Referer':'https://www.efunds.com.cn/'})
 with urllib.request.urlopen(req,timeout=20) as r:raw=r.read(8*1024*1024+1)
 if len(raw)>8*1024*1024:raise ValueError('官方目录响应超过容量限制')
 return json.loads(raw,object_pairs_hook=unique_pairs,parse_constant=reject_constant)

def run(code,title,published,asof,out,fetch=fetch_catalog,download_fn=download,catalog_scope='legal'):
 if not isinstance(code,str) or not re.fullmatch(r'\d{6}',code):raise ValueError('六位基金代码')
 if not isinstance(title,str) or not title.strip():raise ValueError('需明确文件标题')
 for date in [published,asof]:day(date)
 if published>asof:raise ValueError('披露日晚于截止日')
 out=Path(out)
 if out.exists():raise FileExistsError('输出目录已存在')
 if catalog_scope not in ('legal','all-public'):raise ValueError('目录范围仅支持legal或all-public')
 params=dict(siteID='1',title=title,fundCode=code,isIncludeTransFund='N',pageSize=20,pageIndex=0,platformID='Mobile')
 if catalog_scope=='legal':params['catalogAlias']='xxplflwj'
 payload=fetch(params);row=select(payload,title,published);raw=download_fn(row['path'])
 if not raw.startswith(b'%PDF'):raise ValueError('官方附件非PDF')
 out.mkdir(parents=True);path=out/'official.pdf';path.write_bytes(raw)
 pages=read_pages(path);title_match=normalize(title) in ''.join(normalize(t) for n,t in pages if n<=20)
 identity=report_identity(pages,code,title)
 if identity.get('expectedPeriodEnd') and identity['expectedPeriodEnd']>published:
  identity.update(status='pending',publicationTimingStatus='before-report-period-end',scope='目录披露日早于标题报告期末，不能作为该期正式报告依据。')
 r=dict(documentPath=str(path.resolve()),pageCount=len(pages),titleCheckedPages=min(20,len(pages)),code=code,title=title,publishedAt=published,asOf=asof,sourceUrl=row['path'],sourceSha256=hashlib.sha256(raw).hexdigest(),officialCatalogRequest=dict(sourceUrl=API,parameters=params),officialCatalogResponse=payload,catalogScope=catalog_scope,identityMethod='官方按基金代码及声明目录范围查询，标题/披露日唯一匹配，再核对PDF标题',titleMatched=title_match,effectiveVersionVerified=False,fees=statements(pages) if title_match else None,limitations=['仅易方达公开接口适配，不保证任意基金公司覆盖','只请求首20条明确标题目录，不证明历次修订全部取得','目录范围无目标不代表未披露；跨目录查询仍须唯一标题/日期及附件身份核对','官方目录与附件关联不证明截至研究日仍为有效版本','共同份额、补充公告和收费减免须另核验；不输出当前有效费率结论'])
 r['periodicReportIdentity']=identity
 if identity['status']=='pending':
  r['fees']=None;r['limitations'].append('定期报告身份或披露时间仍待核验，暂停费用抽取，不以目录成功代替报告身份。')
 (out/'result.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
 lines=['# 官方基金文件依据','',title,f'基金{code}；目录披露日{published}；资料截止日{asof}。','官方目录关联及PDF标题匹配。' if title_match else 'PDF标题未匹配，不输出费率。','当前有效版本尚未核验。']
 if identity['status']!='not-periodic-report':lines.append('定期报告前部代码与期末：'+('匹配。' if identity['status']=='matched' else '尚未匹配，身份仍待核验。'))
 if identity.get('publicationTimingStatus')=='before-report-period-end':lines.append('目录披露日期早于标题报告期末；即使代码与期末文字匹配，也不能作为该期正式报告依据。')
 for label,item in (r['fees'] or {}).items():
  lines.append(label+'：'+(str(item['value'])+'%/年' if item['value'] is not None else item['status']))
  for e in item['evidence']:lines.append(f"PDF第{e['page']}页：{e['context']}")
 lines+=['']+r['limitations']+['',r['sourceUrl']]
 text='\n'.join(lines);(out/'官方原文依据.md').write_text(text,encoding='utf-8');(out/'官方原文依据.html').write_text(render(text),encoding='utf-8');return r
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--code',required=True);p.add_argument('--title',required=True);p.add_argument('--published',required=True);p.add_argument('--as-of',required=True);p.add_argument('--out-dir',required=True);p.add_argument('--catalog-scope',choices=('legal','all-public'),default='legal');a=p.parse_args();run(a.code,a.title,a.published,a.as_of,a.out_dir,catalog_scope=a.catalog_scope)
