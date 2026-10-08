"""CSI public index collection. Stdlib API; XLS files retained for host readers."""
import argparse,datetime as dt,json,urllib.request,urllib.parse,hashlib,re
from pathlib import Path
from public_download import download
from collection_validation import day,unique_pairs,reject_constant
BASE='https://www.csindex.com.cn/csindex-home'
def collect(directory,index,start,end):
    if not isinstance(index,str) or not re.fullmatch(r'[A-Z0-9]{6}',index):raise ValueError('六位指数代码无效')
    if day(start)>day(end):raise ValueError('起止日期无效')
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    now=dt.datetime.now(dt.timezone(dt.timedelta(hours=8)));run=directory/(index+'-'+now.strftime('%Y%m%dT%H%M%S%f'));run.mkdir()
    result={'indexCode':index,'retrievedAt':now.isoformat(),'start':start,'end':end,'sources':{},'errors':{},'files':[]}
    def get(url):
        return download(url,limit=30*1024*1024,timeout=25,headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.csindex.com.cn/'})
    routes={'basic':'/indexInfo/index-basic-info/'+index,'materials':'/indexInfo/index-details-data?'+urllib.parse.urlencode({'indexCode':index,'fileLang':2}),'derivatives':'/perf/get-derivative-index?indexCode='+index,'top10':'/index/weight/top10new/'+index}
    def api(key,path):
        url=BASE+path
        try:
            blob=get(url);doc=json.loads(blob,object_pairs_hook=unique_pairs,parse_constant=reject_constant)
            if not isinstance(doc,dict) or str(doc.get('code'))!='200' or doc.get('data') is None:raise ValueError('官方接口未返回有效数据')
            (run/(key+'.json')).write_bytes(blob);result['sources'][key]={'url':url,'sha256':hashlib.sha256(blob).hexdigest(),'data':doc['data']};return doc['data']
        except Exception as e:result['errors'][key]=type(e).__name__+': '+str(e)
    for key,path in routes.items():api(key,path)
    derivatives=result['sources'].get('derivatives',{}).get('data',[])
    matches=[]
    if not isinstance(derivatives,list) or any(not isinstance(r,dict) for r in derivatives):result['errors']['derivatives']='衍生指数响应结构无效'
    elif index=='000300':matches=[r.get('indexCode') for r in derivatives if r.get('indexNameEn')=='CSI 300 TRI']
    tri=matches[0] if len(matches)==1 and isinstance(matches[0],str) and re.fullmatch(r'[A-Z0-9]{6}',matches[0]) else None
    # Other families require explicit verified mapping; no H-prefix guessing.
    if tri:api('totalReturn','/perf/index-perf?'+urllib.parse.urlencode({'indexCode':tri,'startDate':start.replace('-',''),'endDate':end.replace('-','')}))
    else:result['errors']['totalReturn']='未确认该指数的同币种全收益代码，不猜测映射'
    materials=result['sources'].get('materials',{}).get('data',{})
    if not isinstance(materials,dict):result['errors']['materials']='资料目录响应结构无效';materials={}
    for group in ['编制方案','样本权重','指数估值']:
        entries=materials.get(group,[])
        if not isinstance(entries,list):result['errors'][group]='资料分组须为数组';continue
        for ordinal,record in enumerate(entries,1):
            try:
                if not isinstance(record,dict) or not isinstance(record.get('filePath'),str):raise ValueError('资料条目缺少文件链接')
                url=record['filePath']
                if urllib.parse.urlsplit(url).hostname!='oss-ch.csindex.com.cn':raise ValueError('文件链接不属于登记中证资料域名')
                blob=get(url);suffix=Path(urllib.parse.urlsplit(url).path).suffix;path=run/(group+'-'+str(ordinal)+'-'+hashlib.sha256(blob).hexdigest()[:12]+suffix);path.write_bytes(blob)
                result['files'].append({'group':group,'url':url,'path':str(path.resolve()),'sha256':hashlib.sha256(blob).hexdigest(),'boundary':'所属期以文件内日期为准；XLS由宿主阅读工具核对，不以抓取日替代'})
            except Exception as e:result['errors'][group+':'+str(ordinal)]=type(e).__name__+': '+str(e)
    path=run/'collection.json';path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return {'output':str(path.resolve()),'sources':len(result['sources']),'files':len(result['files']),'errors':result['errors']}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--data-dir',required=True);p.add_argument('--index',required=True);p.add_argument('--start',required=True);p.add_argument('--end',required=True);a=p.parse_args();print(json.dumps(collect(a.data_dir,a.index,a.start,a.end),ensure_ascii=False))
