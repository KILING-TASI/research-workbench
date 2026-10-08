"""Extract only explicit new-side names from SW official comparison workbook."""
import argparse,json,re,hashlib,datetime as dt,urllib.request
from urllib.parse import urlparse
from public_download import download as public_download
from pathlib import Path
URL='https://www.swsresearch.com/swindex/pdf/SwClass2021/2014to2021.xlsx'
HEAD=['旧版一级行业','旧版二级行业','旧版三级行业','行业代码','新版一级行业','新版二级行业','新版三级行业','行业代码']

def extract(rows,sheet):
 if len(rows)<2 or list(rows[1][:8])!=HEAD:raise ValueError('新版对照表表头不匹配')
 entries={};unmapped=[]
 for i,row in enumerate(rows[2:],3):
  names=row[4:7];code=row[7]
  if code in (None,''):
   if row[3] not in (None,''):unmapped.append(dict(row=i,oldCode=row[3],newCode=None))
   continue
  if isinstance(code,bool) or not isinstance(code,(int,str)) or not re.fullmatch(r'\d{6}',str(code)):raise ValueError('新版行业代码无效')
  explicit=[(j+1,name.strip()) for j,name in enumerate(names) if isinstance(name,str) and name.strip()]
  if len(explicit)!=1:raise ValueError('新版行业名称歧义')
  level,name=explicit[0];key=str(code)
  if key in entries and (entries[key]['name'],entries[key]['level'])!=(name,level):raise ValueError('同新版代码名称或层级冲突')
  entries.setdefault(key,dict(code=key,name=name,level=level,locators=[]))['locators'].append(dict(sheet=sheet,row=i))
 return list(entries.values()),unmapped

def parse(path):
 try:import openpyxl
 except ImportError as exc:raise RuntimeError('行业代码表解析需openpyxl，请安装后重试') from exc
 path=Path(path);raw=path.read_bytes();book=openpyxl.load_workbook(path,read_only=True,data_only=True)
 try:
  sheet=book['新旧对比版本2'];entries,unmapped=extract(list(sheet.values),sheet.title)
 finally:book.close()
 return dict(type='sw-codebook-archive',classificationVersion='SW2021',sourceUrl=URL,sourceSha256=hashlib.sha256(raw).hexdigest(),inputPath=str(path.resolve()),entries=entries,oldRowsWithoutNewCode=unmapped,limitations=['仅取原表新版列，不把旧版名称补到新版空白','未提供新版代码的旧版行保留，不判定股票归属','代码表不证明股票当前行业、分类有效期间或主题归属','当前原表副本不是事前冻结输入；获取来源需另留证'])
def fetch(out):
 out=Path(out)
 if out.exists():raise FileExistsError('输出目录已存在，保留旧归档')
 response=public_download(URL,limit=15*1024*1024,timeout=25,allowed_hosts={'www.swsresearch.com'},return_metadata=True)
 resolved=response['resolvedUrl'];raw=response['raw']
 if urlparse(resolved).scheme!='https' or urlparse(resolved).hostname!='www.swsresearch.com':raise ValueError('行业代码表最终来源域名不符')
 if len(raw)>15*1024*1024 or not raw.startswith(b'PK'):raise ValueError('响应不是预期XLSX或超限')
 out.mkdir(parents=True);path=out/'original.xlsx';path.write_bytes(raw)
 ev=dict(sourceUrl=URL,resolvedUrl=resolved,retrievedAt=dt.datetime.now(dt.timezone.utc).isoformat(),sha256=hashlib.sha256(raw).hexdigest())
 (out/'source.json').write_text(json.dumps(ev,ensure_ascii=False,indent=2),encoding='utf-8')
 try:r=parse(path);r['retrievalEvidence']=ev
 except Exception as exc:
  (out/'failure.json').write_text(json.dumps(dict(reason=str(exc),rawFileRetained=True),ensure_ascii=False),encoding='utf-8');raise
 (out/'result.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8');return r
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('input',nargs='?');p.add_argument('--out',type=Path);p.add_argument('--fetch',action='store_true');p.add_argument('--out-dir',type=Path);a=p.parse_args()
 if a.fetch:
  if a.input or a.out or not a.out_dir:p.error('--fetch仅搭配--out-dir')
  fetch(a.out_dir)
 else:
  if not a.input or not a.out or a.out_dir:p.error('本地解析需要input与--out')
  if a.out.exists():raise FileExistsError('输出已存在')
  r=parse(a.input);a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
