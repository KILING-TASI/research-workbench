"""On-demand official ICBC fund static catalog, with explicit partial scope."""
import argparse,datetime,hashlib,json,re
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request,urlopen
from collection_validation import unique_pairs,reject_constant,finite_json_float
HOST='https://www.icbcubs.com.cn'
def select(data,code,title):
 if not isinstance(data,dict) or data.get('code')!='0000':raise ValueError('官方目录未返回成功结构')
 page=data.get('data')
 if not isinstance(page,dict) or not isinstance(page.get('content'),list):raise ValueError('官方目录条目结构异常')
 result=[]
 for row in page['content']:
  if not isinstance(row,dict) or not isinstance(row.get('fundCode'),list) or code not in row['fundCode']:raise ValueError('目录条目基金身份不一致')
  if row.get('announcementName')!=title:continue
  path=row.get('fileUrl','')
  if not isinstance(path,str) or not re.fullmatch(r'/\d{8}/[A-Za-z0-9_-]+\.pdf',path):raise ValueError('文件路径不符合已支持的官方目录格式')
  day=row.get('announcementDate');updated=row.get('updatedTime')
  if not isinstance(day,str) or datetime.date.fromisoformat(day).isoformat()!=day:raise ValueError('公告日期格式异常')
  result.append(dict(title=title,code=code,shareCodes=row['fundCode'],publishedDate=day,publisherUpdatedTime=updated,pdfUrl=HOST+'/gyrx-file'+path,firstPublicTimeVerified=False))
 return result
def download(url):
 with urlopen(Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=20) as r:
  if urlsplit(r.url).hostname!='www.icbcubs.com.cn':raise ValueError('响应来源跳转，不能自动认证官方目录')
  raw=r.read(3000001)
  if len(raw)>3000000:raise ValueError('目录响应超过限制')
  return raw
def run(code,title,out,fetch=download):
 if not isinstance(code,str) or not re.fullmatch(r'\d{6}',code):raise ValueError('基金代码须六位')
 if not isinstance(title,str) or not title.strip():raise ValueError('需完整目标文件标题')
 out=Path(out);out.mkdir(parents=True,exist_ok=False);url=HOST+'/gyrx-file/json/getFundAnnouncementList/'+code+'.json'
 result=dict(code=code,expectedTitle=title,url=url,retrievedAt=datetime.datetime.now(datetime.timezone.utc).isoformat(),candidates=[],completeCatalogVerified=False,pdfVerified=False,limitations='仅查本次静态目录返回条目；不自动翻页或认证PDF，未检出不等于文件不存在。公告日期和更新时间不作首次可得时刻。')
 try:
  raw=fetch(url);p=out/'catalog.json';p.write_bytes(raw);result.update(rawFile=str(p.resolve()),sha256=hashlib.sha256(raw).hexdigest());data=json.loads(raw,object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float);result['candidates']=select(data,code,title)
  page=data['data'];result['returnedCount']=len(page['content']);result['declaredTotal']=page.get('total');result['declaredHasNextPage']=page.get('hasNextPage');result['status']='candidate-found' if result['candidates'] else 'not-found-in-returned-items'
 except Exception as exc:result.update(status='failed',error=type(exc).__name__+': '+str(exc))
 (out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--code',required=True);p.add_argument('--title',required=True);p.add_argument('--out-dir',required=True);a=p.parse_args();run(a.code,a.title,a.out_dir)
