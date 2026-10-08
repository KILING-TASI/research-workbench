"""Bounded, on-demand official periodic-report candidates; not PDF verification."""
import argparse,datetime,hashlib,json,re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin,urlsplit
from urllib.request import Request,urlopen
BASE='https://www.huatai-pb.com'
class Links(HTMLParser):
 def __init__(self):super().__init__(convert_charrefs=True);self.items=[]
 def handle_starttag(self,tag,attrs):
  if tag!='a':return
  a=dict(attrs);title=a.get('title','');href=a.get('href','');url=urljoin(BASE,href);u=urlsplit(url)
  if title and u.scheme=='https' and u.hostname=='www.huatai-pb.com' and not u.username and not u.password and u.path.startswith('/upload/pdf/') and u.path.lower().endswith('.pdf'):
   self.items.append(dict(title=title,url=url))
def select(raw,expected_title):
 p=Links();p.feed(raw.decode('utf-8-sig'));return [x for x in p.items if x['title']==expected_title]
def download(url):
 with urlopen(Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=20) as r:
  if urlsplit(r.url).hostname!='www.huatai-pb.com':raise ValueError('目录跳转至其他来源，未作为官方目录接受')
  raw=r.read(3000001)
  if len(raw)>3000000:raise ValueError('目录响应超过限制')
  return raw
def run(title,out,max_pages=20,fetch=download):
 if not isinstance(title,str) or not title.strip() or not re.search(r'\d{4}年.*报告$',title):raise ValueError('需完整产品名称、年份及报告类型')
 if type(max_pages)!=int or not 1<=max_pages<=50:raise ValueError('分页上限须1至50')
 out=Path(out);out.mkdir(parents=True,exist_ok=False);attempts=[];found={}
 for page in range(1,max_pages+1):
  url=BASE+'/news/information/fundReport/'+('index.html' if page==1 else f'index{page}.html')
  try:
   raw=fetch(url);p=out/f'catalog-{page}.html';p.write_bytes(raw);matches=select(raw,title)
   attempts.append(dict(page=page,url=url,rawFile=str(p.resolve()),sha256=hashlib.sha256(raw).hexdigest(),matches=matches))
   for item in matches:found[item['url']]=item
   if found:break
  except Exception as exc:
   attempts.append(dict(page=page,url=url,error=type(exc).__name__+': '+str(exc)));break
 result=dict(expectedTitle=title,candidates=list(found.values()),attempts=attempts,maxPages=max_pages,retrievedAt=datetime.datetime.now(datetime.timezone.utc).isoformat(),status='candidate-found' if found else 'failed' if attempts and 'error' in attempts[-1] else 'not-found-within-checked-pages',completeCatalogVerified=False,pdfVerified=False,limitations='只定位管理人目录中的全名候选，不下载或认证PDF身份、全部报告、首次公开时间；未检出不证明不存在。')
 (out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--title',required=True);p.add_argument('--max-pages',type=int,default=20);p.add_argument('--out-dir',required=True);a=p.parse_args();run(a.title,a.out_dir,a.max_pages)
