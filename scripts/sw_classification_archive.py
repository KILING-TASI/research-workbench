"""Read official SW classification workbook without inventing validity intervals."""
import argparse,json,re,hashlib,datetime as dt,urllib.request
from urllib.parse import urlparse
from public_download import download as public_download
from pathlib import Path
URL='https://www.swsresearch.com/swindex/pdf/SwClass2021/StockClassifyUse_stock.xls'

def parse(path,asof):
 try:import xlrd
 except ImportError as exc:raise RuntimeError("行业Excel解析需xlrd；请在当前Python环境安装xlrd后重试") from exc
 dt.date.fromisoformat(asof);path=Path(path);raw=path.read_bytes()
 b=xlrd.open_workbook(file_contents=raw);rows=[];excluded=[]
 for sheet in b.sheets():
  if sheet.nrows==0 or sheet.row_values(0)!=['股票代码','计入日期','行业代码','更新日期']:raise ValueError('行业原表标题不匹配')
  for i in range(1,sheet.nrows):
   code,entry,industry,updated=sheet.row_values(i)
   if not isinstance(code,str) or not re.fullmatch(r'\d{6}',code) or not isinstance(industry,str) or not re.fullmatch(r'\d{6}',industry):raise ValueError('证券或行业代码格式异常')
   for col in [1,3]:
    if sheet.cell_type(i,col)!=xlrd.XL_CELL_DATE:raise ValueError('分类日期不是Excel日期')
   start=xlrd.xldate_as_datetime(entry,b.datemode).date().isoformat();changed=xlrd.xldate_as_datetime(updated,b.datemode).isoformat()
   item=dict(code=code,industryCode=industry,includedAt=start,updatedAt=changed,locator=dict(sheet=sheet.name,row=i+1),effectiveTo=None)
   if start>asof or changed>asof:excluded.append(item)
   else:rows.append(item)
 return dict(type='sw-classification-archive',asOf=asof,sourceUrl=URL,sourceSha256=hashlib.sha256(raw).hexdigest(),inputPath=str(path.resolve()),rows=rows,excludedAfterCutoff=excluded,limitations=['当前下载的历史记录不是事前冻结资料','更新日期不是公告披露日期；计入日期不自动证明区间终止','保留同证券多行，不自动裁决唯一有效分类','仅行业代码，不推断行业名称或主题标签','输入副本须另核验获取来源，文件摘要不证明官方下载'])

def fetch(asof,out):
 dt.date.fromisoformat(asof);out=Path(out)
 if out.exists():raise FileExistsError('输出目录已存在；保留旧归档')
 response=public_download(URL,limit=15*1024*1024,timeout=25,allowed_hosts={'www.swsresearch.com'},return_metadata=True)
 resolved=response['resolvedUrl'];raw=response['raw']
 if urlparse(resolved).scheme!='https' or urlparse(resolved).hostname!='www.swsresearch.com':raise ValueError('官方文件重定向来源不符')
 if len(raw)>15*1024*1024:raise ValueError('行业原表响应超限')
 if not raw.startswith(bytes.fromhex('d0cf11e0a1b11ae1')):raise ValueError('响应不是预期Excel原表，拒绝网页错误内容')
 out.mkdir(parents=True);path=out/'original.xls';path.write_bytes(raw)
 provenance=dict(sourceUrl=URL,resolvedUrl=resolved,retrievedAt=dt.datetime.now(dt.timezone.utc).isoformat(),sha256=hashlib.sha256(raw).hexdigest())
 (out/'source.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2),encoding='utf-8')
 try:
  result=parse(path,asof);result['retrievalEvidence']=provenance
 except Exception as exc:
  (out/'failure.json').write_text(json.dumps(dict(reason=str(exc),rawFileRetained=True),ensure_ascii=False),encoding='utf-8');raise
 (out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');return result

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('input',nargs='?');p.add_argument('--as-of',required=True);p.add_argument('--out',type=Path);p.add_argument('--fetch',action='store_true');p.add_argument('--out-dir',type=Path);a=p.parse_args()
 if a.fetch:
  if a.input or a.out or not a.out_dir:p.error('--fetch仅搭配--out-dir，不提供input/--out')
  fetch(a.as_of,a.out_dir)
 else:
  if not a.input or not a.out or a.out_dir:p.error('本地解析需要input及--out')
  if a.out.exists():raise FileExistsError('输出已存在')
  r=parse(a.input,a.as_of);a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
