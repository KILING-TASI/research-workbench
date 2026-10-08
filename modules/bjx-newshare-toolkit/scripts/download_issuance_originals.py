"""Download explicit issuer announcement URLs, bounded and without address guessing."""
import argparse,datetime as dt,hashlib,json,re,urllib.request,urllib.error
from pathlib import Path
from announcements import document_location

def select(snapshot,limit=8,codes=None):
 selected=[];seen=set();missing=[]
 rows=sorted(snapshot['records'],key=lambda r:r.get('applyDate') or '',reverse=True)
 if codes:rows=[r for r in rows if r['code'] in codes]
 for r in rows:
  for kind,keyword in [('issue','发行公告'),('result','发行结果')]:
   links=[a for a in r.get('announcements',[]) if keyword in a.get('title','') and document_location(a.get('url'))]
   notices=[a for a in links if re.search(r'(更正|修订|补充)公告|取消|撤回',a.get('title',''))]
   for notice in notices:
    missing.append({'code':r['code'],'kind':kind,'status':'correction-notice-needs-body-comparison','sourceUrl':notice['url'],'title':notice.get('title')})
   # A correction notice is not the corrected full issuance document.
   links=[a for a in links if a not in notices]
   links.sort(key=lambda a:(a.get('date') or '',bool(re.search(r'更正后|修订版|更新后',a.get('title',''))),a['url']),reverse=True)
   if not links:missing.append({'code':r['code'],'kind':kind,'status':'no-supported-original-link'});continue
   a=links[0];key=(r['code'],a['url'])
   if key in seen:continue
   seen.add(key);selected.append({'code':r['code'],'name':r['name'],'kind':kind,'sourceUrl':a['url'],'metadataDate':a.get('date'),'title':a.get('title'),
    'selectionBasis':'Latest metadata date; same-date corrected-full title preferred, notice excluded; applicability not certified',
    'versionReviewRequired':bool(notices) or any(re.search(r'更正|修订|更新|补充',x.get('title','')) for x in links)})
  if len(selected)>=limit:break
 return selected[:limit],missing

def download(snapshot,out,limit=8,codes=None):
 out.mkdir(parents=True,exist_ok=False);selected,missing=select(snapshot,limit,codes);documents=[];details=[];stopped=False
 for item in selected:
  detail=dict(item)
  if stopped:detail.update(status='not-attempted',reason='Access-limit stop');details.append(detail);continue
  try:
   url=item['sourceUrl'];req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
   with urllib.request.urlopen(req,timeout=25) as response:
    if not document_location(response.geturl()):raise ValueError('Redirect outside supported original document hosts')
    body=response.read(40*1024*1024+1)
   if len(body)>40*1024*1024 or not body.startswith(b'%PDF-'):raise ValueError('Invalid or oversized PDF')
   digest=hashlib.sha256(body).hexdigest();file=out/(digest+'.pdf');file.write_bytes(body)
   doc={**item,'file':str(file.resolve()),'sha256':digest,'downloadedAt':dt.datetime.now(dt.timezone.utc).isoformat()};documents.append(doc);detail.update(status='downloaded',sha256=digest,bytes=len(body))
  except urllib.error.HTTPError as error:
   detail.update(status='failed',reason=str(error));stopped=error.code in [403,429]
  except Exception as error:detail.update(status='failed',reason=str(error))
  details.append(detail)
 manifest={'documents':documents,'details':details,'missing':missing,'accessLimitStopped':stopped,'boundary':'Download does not certify issuer text, values or publication time'}
 (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8');return manifest
def main():
 p=argparse.ArgumentParser();p.add_argument('--data',type=Path,required=True);p.add_argument('--out-dir',type=Path,required=True);p.add_argument('--limit',type=int,default=8);p.add_argument('--codes',nargs='*');a=p.parse_args()
 if not 1<=a.limit<=50:raise ValueError('Limit must be 1..50')
 result=download(json.loads(a.data.read_text(encoding='utf-8')),a.out_dir,a.limit,set(a.codes) if a.codes else None);print(json.dumps({'downloaded':len(result['documents']),'failed':sum(x['status']=='failed' for x in result['details']),'accessLimitStopped':result['accessLimitStopped']}))
if __name__=='__main__':main()
