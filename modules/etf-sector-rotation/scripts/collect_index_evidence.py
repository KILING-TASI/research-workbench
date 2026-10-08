"""CSI public index collection. Stdlib API; XLS files retained for host readers."""
import argparse,datetime as dt,json,urllib.request,urllib.parse,hashlib,re
from pathlib import Path
BASE='https://www.csindex.com.cn/csindex-home'
def collect(directory,index,start,end):
    if not re.fullmatch(r'[A-Z0-9]{6}',index):raise ValueError('六位指数代码无效')
    if dt.date.fromisoformat(start).isoformat()!=start or dt.date.fromisoformat(end).isoformat()!=end or dt.date.fromisoformat(start)>dt.date.fromisoformat(end):raise ValueError('起止日期无效')
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    now=dt.datetime.now(dt.timezone(dt.timedelta(hours=8)));run=directory/(index+'-'+now.strftime('%Y%m%dT%H%M%S%f'));run.mkdir()
    result={'indexCode':index,'retrievedAt':now.isoformat(),'start':start,'end':end,'sources':{},'errors':{},'files':[]}
    def get(url):
        req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.csindex.com.cn/'})
        with urllib.request.urlopen(req,timeout=25) as r:return r.read()
    routes={'basic':'/indexInfo/index-basic-info/'+index,'materials':'/indexInfo/index-details-data?'+urllib.parse.urlencode({'indexCode':index,'fileLang':2}),'derivatives':'/perf/get-derivative-index?indexCode='+index,'top10':'/index/weight/top10new/'+index}
    def api(key,path):
        url=BASE+path
        try:
            blob=get(url);doc=json.loads(blob)
            if str(doc.get('code'))!='200' or doc.get('data') is None:raise ValueError('官方接口未返回有效数据：'+str(doc.get('msg')))
            (run/(key+'.json')).write_bytes(blob);result['sources'][key]={'url':url,'sha256':hashlib.sha256(blob).hexdigest(),'data':doc['data']};return doc['data']
        except Exception as e:result['errors'][key]=type(e).__name__+': '+str(e)
    for key,path in routes.items():api(key,path)
    derivatives=result['sources'].get('derivatives',{}).get('data',[])
    tri=next((r['indexCode'] for r in derivatives if r.get('indexNameEn')=='CSI 300 TRI'),None) if index=='000300' else None
    # Other families require explicit verified mapping; no H-prefix guessing.
    if tri:api('totalReturn','/perf/index-perf?'+urllib.parse.urlencode({'indexCode':tri,'startDate':start.replace('-',''),'endDate':end.replace('-','')}))
    else:result['errors']['totalReturn']='未确认该指数的同币种全收益代码，不猜测映射'
    materials=result['sources'].get('materials',{}).get('data',{})
    for group in ['编制方案','样本权重','指数估值']:
        for record in materials.get(group) or []:
            url=record['filePath']
            if urllib.parse.urlsplit(url).hostname!='oss-ch.csindex.com.cn':continue
            try:
                blob=get(url);suffix=Path(urllib.parse.urlsplit(url).path).suffix;signature=hashlib.sha256(blob).hexdigest();path=run/(group+'-'+signature+suffix)
                if not path.exists():path.write_bytes(blob)
                result['files'].append({'group':group,'url':url,'path':str(path.resolve()),'sha256':hashlib.sha256(blob).hexdigest(),'boundary':'所属期以文件内日期为准；XLS由宿主阅读工具核对，不以抓取日替代'})
            except Exception as e:result['errors'][group]=type(e).__name__+': '+str(e)
    path=run/'collection.json';path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return {'output':str(path.resolve()),'sources':len(result['sources']),'files':len(result['files']),'errors':result['errors']}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--data-dir',required=True);p.add_argument('--index',required=True);p.add_argument('--start',required=True);p.add_argument('--end',required=True);a=p.parse_args();print(json.dumps(collect(a.data_dir,a.index,a.start,a.end),ensure_ascii=False))
