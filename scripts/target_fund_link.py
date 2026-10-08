"""Bind an ETF feeder target explicitly disclosed in its report, without guessing row aliases."""
import argparse,hashlib,json,re,datetime as dt
from pathlib import Path
import pdfplumber
from verify_original import compact
from research_brief_html import render
from collection_validation import day,unique_pairs,reject_constant,finite_json_float
from research_library import url as source_url

def read_report(path):
 path=Path(path).resolve();r=json.loads(path.read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float)
 if isinstance(r,dict) and isinstance(r.get('documentPath'),str):
  p=Path(r['documentPath']);r['documentPath']=str(p if p.is_absolute() else path.parent/p)
 return r

def select_records(records):
 values={}
 for record in records:
  cells=[compact(c) for c in record['cells']]
  if len(cells)!=2:continue
  key={'基金名称':'name','基金主代码':'code','基金管理人名称':'manager','基金份额上市的证券交易所':'exchange'}.get(cells[0])
  if key:
   if not cells[1]:raise ValueError('目标基金字段为空')
   values.setdefault(key,[]).append(dict(value=cells[1],page=record['page'],tableBBox=record['tableBBox'],originalCells=record['cells']))
 for key in ['name','code']:
  if key not in values or len({r['value'] for r in values[key]})!=1:raise ValueError('目标基金名称或代码缺失/冲突')
 code=values['code'][0]['value']
 if not re.fullmatch(r'\d{6}',code):raise ValueError('目标基金代码不是明确六位代码')
 for key,items in values.items():
  if len({r['value'] for r in items})!=1:raise ValueError('目标基金同名字段冲突：'+key)
 return dict(code=code,name=values['name'][0]['value'],fields=values)

def extract(report):
 for key in ['reportDate','asOf']:day(report[key])
 published=report['metadata']['publishedAt'];day(published);source_url(report['metadata']['sourceUrl'])
 if not report['reportDate']<=published<=report['asOf']:raise ValueError('父报告披露日期越界')
 if not report.get('identityStatus'):raise ValueError('父基金报告身份未核验')
 path=Path(report['documentPath']);digest=hashlib.sha256(path.read_bytes()).hexdigest()
 if digest!=report['sha256']:raise ValueError('父基金报告哈希不一致')
 records=[];started=False;ended=False
 with pdfplumber.open(path) as document:
  for number,page in enumerate(document.pages,1):
   starts=page.search(r'(?m)^2\.1\.1\s*目标基金基本情况\s*$')
   if starts:started=True
   if not started or ended:continue
   ends=page.search(r'(?m)^2\.2\s*基金产品说明\s*$')
   top=starts[0]['top'] if starts else 0;bottom=ends[0]['top'] if ends else float('inf')
   for table in page.find_tables():
    if table.bbox[1]<top or table.bbox[1]>=bottom:continue
    records += [dict(cells=row,page=number,tableBBox=list(table.bbox)) for row in table.extract()]
   if ends:ended=True
 if not ended:raise ValueError('目标基金章节边界未取得')
 target=select_records(records)
 return dict(type='report-target-fund-link',parentCode=report['code'],reportDate=report['reportDate'],asOf=report['asOf'],target=target,sourceUrl=report['metadata']['sourceUrl'],publishedAt=report['metadata']['publishedAt'],sourceSha256=digest,relation='报告明确披露的目标基金',holdingRowMatched=False,weight=None,limitations=['关系仅适用于该报告期，非当前合同关系','目标基金身份不证明前十名表的简称、权重或全部资产覆盖','未核验发行人网页；代码关系依据已匹配身份的报告副本'])

def attach_child(link,child):
 for value in [link['reportDate'],link['asOf'],link['publishedAt'],child['metadata']['publishedAt'],child['asOf']]:day(value)
 source_url(child['metadata']['sourceUrl'])
 if not link['reportDate']<=link['publishedAt']<=link['asOf']:raise ValueError('父关系披露日期越界')
 if child['asOf']!=link['asOf']:raise ValueError('父子报告研究截止日不一致')
 if not link['reportDate']<=child['metadata']['publishedAt']<=link['asOf']:raise ValueError('子报告披露日期越界')
 if child.get('code')!=link['target']['code'] or child.get('reportDate')!=link['reportDate']:raise ValueError('子基金代码或报告期不匹配')
 if child.get('status')!='副本身份及股票持仓勾稽完成' or not child.get('identityStatus') or not child.get('holdings'):raise ValueError('子基金股票持仓未完成勾稽核验')
 if compact(link['target']['name']) not in compact(child['metadata']['title']):raise ValueError('目标基金全名与子报告标题不一致')
 digest=hashlib.sha256(Path(child['documentPath']).read_bytes()).hexdigest()
 if digest!=child['sha256']:raise ValueError('子报告原文哈希变化')
 h=child['holdings']
 if any(h.get(k)!=v for k,v in {'id':child['code'],'reportDate':child['reportDate'],'publishedAt':child['metadata']['publishedAt'],'sourceSha256':digest,'sourceUrl':child['metadata']['sourceUrl']}.items()):raise ValueError('子报告与持仓身份、来源或日期不一致')
 result=dict(link)
 result['childReport']=dict(code=child['code'],reportDate=child['reportDate'],sourceUrl=child['metadata']['sourceUrl'],publishedAt=child['metadata']['publishedAt'],sourceSha256=digest,holdingsCount=len(child['holdings']['holdings']),status=child['status'])
 result['limitations']=link['limitations']+['子报告股票表已关联；父基金投资权重与非股票资产仍未核验，不计算加权组合敞口']
 return result

def markdown(result):
 t=result['target'];lines=['# 联接基金目标报告关系','',f"{result['parentCode']}的{result['reportDate']}报告明确披露目标基金代码{t['code']}，名称为{t['name']}。",'该关系可用于按代码查找同期间报告，本节只核对报告关系，投资权重与穿透结果需分别核验。','','| 字段 | 原文值 | PDF页码 |','| --- | --- | --- |']
 for key,rows in t['fields'].items():
  label={'name':'基金全名','code':'基金代码','manager':'管理人','exchange':'上市交易所'}.get(key,key)
  for x in rows:lines.append('| '+label+' | '+x['value']+' | '+str(x['page'])+' |')
 if result.get('childReport'):lines+=['',f"目标基金同期间报告已关联，股票明细{result['childReport']['holdingsCount']}条；本项关联不核验父基金投资权重。",result['childReport']['sourceUrl']]
 lines+=['',result['sourceUrl'],'']+['- '+x for x in result['limitations']]
 return '\n'.join(lines)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('report');p.add_argument('--out',required=True);p.add_argument('--child-report');a=p.parse_args();out=Path(a.out)
 if any(x.exists() for x in [out,out.with_suffix('.md'),out.with_suffix('.html')]):raise FileExistsError('输出已存在')
 r=extract(read_report(a.report))
 if a.child_report:r=attach_child(r,read_report(a.child_report))
 out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8');text=markdown(r);out.with_suffix('.md').write_text(text,encoding='utf-8');out.with_suffix('.html').write_text(render(text),encoding='utf-8')
