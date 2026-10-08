"""Exact full-name row in a fee amendment; not a current-fee resolver."""
import argparse,json,hashlib,re,datetime as dt,math
from pathlib import Path
import pdfplumber
from fund_document_archive import normalize
from research_brief_html import render
from fund_series_tools import day,source,NOTICE

def fee_row(rows,name):
 if len(rows)<2 or [normalize(x or '') for x in rows[0]]!=['序号','基金名称','调整前','','调整后','']:return []
 if [normalize(x or '') for x in rows[1]][2:]!=['管理费率','托管费率','管理费率','托管费率']:raise ValueError('费率列含义不匹配')
 result=[]
 for row in rows[2:]:
  if len(row)!=6 or normalize(row[1] or '')!=normalize(name):continue
  values=[]
  for x in row[2:]:
   token=normalize(x or '')
   if not re.fullmatch(r'\d+(?:\.\d+)?%',token):raise ValueError('费率不是明确百分比')
   rate=float(token[:-1])
   if not math.isfinite(rate) or not 0<=rate<=100:raise ValueError('费率须为0至100的有限百分比')
   values.append(rate)
  result.append(dict(beforeManagementPct=values[0],beforeCustodyPct=values[1],afterManagementPct=values[2],afterCustodyPct=values[3],originalCells=row))
 return result

def run(archive,name):
 asof=day(archive['asOf']);published=day(archive['catalogItem']['publishedAt']);source(archive['metadata']['sourceUrl'])
 if published>asof:raise ValueError('公告披露日晚于研究截止日')
 if not isinstance(name,str) or not name.strip():raise ValueError('基金完整名称缺失')
 path=Path(archive['documentPath'])
 if hashlib.sha256(path.read_bytes()).hexdigest()!=archive['sha256']:raise ValueError('原文摘要不一致')
 records=[];dates=[]
 with pdfplumber.open(path) as doc:
  for n,p in enumerate(doc.pages,1):
   text=normalize(p.extract_text() or '')
   for m in re.finditer(r'自(\d{4})年(\d{1,2})月(\d{1,2})日起[，,]?调低旗下部分基金',text):dates.append(dict(value=dt.date(*map(int,m.groups())).isoformat(),page=n,quote=m.group(0)))
   for table in p.find_tables():
    for row in fee_row(table.extract(),name):records.append(dict(row,page=n,tableBBox=list(table.bbox)))
 if len(records)!=1 or len({x['value'] for x in dates})!=1:raise ValueError('基金全名行或生效日不唯一，需复核')
 date=dates[0]['value']
 if date>archive['asOf']:raise ValueError('调整尚未在截止日前生效')
 return dict(asOf=asof,publishedAt=published,riskNotice=NOTICE,type='fund-fee-amendment',fundFullName=name,effectiveFrom=date,effectiveDateEvidence=dates,feeEvidence=records[0],sourceUrl=archive['metadata']['sourceUrl'],sourceSha256=archive['sha256'],codeIdentityVerified=False,currentFeeVerified=False,limitations=['按输入全名精确匹配；原表未披露代码，不据此核验份额代码','仅确认这一公告的调整，不证明之后没有调整，也不认定当前有效费率','管理及托管费与申赎费用、销售服务费分开；不能直接相加为投资人实际扣费'])
def markdown(r):
 f=r['feeEvidence']
 lines=['# 基金费率调整核对','',r['fundFullName']+'。',f"公告披露日{r['publishedAt']}；生效日{r['effectiveFrom']}；研究截止日{r['asOf']}。",'',f"该次调整：管理费{f['beforeManagementPct']:.2f}%→{f['afterManagementPct']:.2f}%；托管费{f['beforeCustodyPct']:.2f}%→{f['afterCustodyPct']:.2f}%。",'名单依据：PDF第'+str(f['page'])+'页。生效措辞：']
 for x in r['effectiveDateEvidence']:lines.append('PDF第'+str(x['page'])+'页：'+x['quote'])
 lines+=['','[公告副本]('+r['sourceUrl']+')','','## 本次核验边界']+['- '+v for v in r['limitations']]+['',r['riskNotice']]
 return '\n'.join(lines)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('archive',type=Path);p.add_argument('--name',required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 if any(x.exists() for x in [a.out,a.out.with_suffix('.md'),a.out.with_suffix('.html')]):raise FileExistsError('输出已存在')
 r=run(json.loads(a.archive.read_text(encoding='utf-8-sig')),a.name);a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')

 text=markdown(r);a.out.with_suffix('.md').write_text(text,encoding='utf-8');a.out.with_suffix('.html').write_text(render(text),encoding='utf-8')
