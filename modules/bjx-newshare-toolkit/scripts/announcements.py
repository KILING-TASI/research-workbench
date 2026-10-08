"""Retrieve issuer-matched original disclosures from CNINFO; preserve cache on failure."""
import time
import datetime as dt
import json
import re
import urllib.parse
import urllib.request
from announcement_versions import version_review

def document_location(path):
    if not isinstance(path,str):return None
    final=re.fullmatch(r'(?:https://static\.cninfo\.com\.cn/)?finalpage/(\d{4}-\d{2}-\d{2})/\d+\.PDF',path,re.I)
    cloud=re.fullmatch(r'https://dataclouds\.cninfo\.com\.cn/(?:sjother/(?:documents|bse_onmarket)|sjother2/bse_onmarket)/(\d{4})/(\d{8})/[a-f0-9]{32}\.pdf',path,re.I)
    try:
        if final:
            day=dt.date.fromisoformat(final.group(1)).isoformat()
            return (path if path.startswith('https://') else 'https://static.cninfo.com.cn/'+path),day
        if cloud:
            raw=cloud.group(2)
            if raw[:4]!=cloud.group(1):return None
            return path,dt.date(int(raw[:4]),int(raw[4:6]),int(raw[6:])).isoformat()
    except ValueError:return None
    return None

def merge_links(previous,incoming):
    merged={a['url']:a for a in previous}
    for entry in incoming:
        prior=merged.get(entry['url'])
        # A listing path date cannot downgrade an explicitly body-reviewed date.
        if not prior or not prior.get('bodyChecked'):merged[entry['url']]=entry
    return merged

def request_json(path, params):
    req=urllib.request.Request('https://www.cninfo.com.cn'+path,
        data=urllib.parse.urlencode(params).encode('utf-8'),
        headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.cninfo.com.cn/',
                 'Content-Type':'application/x-www-form-urlencoded'})
    with urllib.request.urlopen(req,timeout=25) as response:
        return json.loads(response.read().decode('utf-8-sig'))

def issuer(stock):
    """Resolve code first. Name fallback must exactly match the issuer, not mention it."""
    def clean(s): return re.sub(r'\s+|<[^>]+>','',str(s or ''))
    for key in [stock['code'],stock['name']]:
        items=request_json('/new/information/topSearch/query',dict(keyWord=key,maxNum=20))
        if not isinstance(items,list): raise ValueError('巨潮证券查询响应异常')
        exact=[i for i in items if str(i.get('code',''))==stock['code'] and i.get('orgId')]
        if not exact:
            exact=[i for i in items if clean(i.get('zwjc'))==clean(stock['name'])
                   and i.get('orgId') and i.get('category')=='A股']
        identities={(str(i['code']),i['orgId']) for i in exact}
        if len(identities)==1:return exact[0]
        if len(identities)>1:raise ValueError('巨潮发行人匹配不唯一，待核验')
    raise ValueError('巨潮未解析到发行人，不能据此判断公告不存在')

# Only body-verified code changes; never derive a code from an orgId.
VERIFIED_OLD_CODES={'920106':dict(code='873682',orgId='gfbj0873682',
    source='https://static.cninfo.com.cn/finalpage/2024-12-13/1222017989.PDF'),
    '920111':dict(code='874021',orgId='nssc1000327',
    source='https://static.cninfo.com.cn/finalpage/2024-10-25/1221524457.PDF'),
    '920128':dict(code='873783',orgId='gfbj0873783',
    source='https://static.cninfo.com.cn/finalpage/2024-11-14/1221725466.PDF'),
    '920060':dict(code='873718',orgId='9900048400',
    source='https://static.cninfo.com.cn/finalpage/2024-11-06/1221641541.PDF')}

def query(stock,searchkey=None,_resolved=None,_code=None):
    resolved=_resolved if _resolved is not None else issuer(stock)
    query_code=_code or resolved['code']
    start=dt.date.fromisoformat(stock['applyDate'])-dt.timedelta(days=180)
    end=min(dt.date.today(),dt.date.fromisoformat(stock['applyDate'])+dt.timedelta(days=90))
    found=[]
    for page in range(1,11):
        data=request_json('/new/hisAnnouncement/query',dict(pageNum=page,pageSize=30,
            column='',tabName='fulltext',stock=f"{query_code},{resolved['orgId']}",
            searchkey='',seDate=f'{start}~{end}',isHLtitle='true',sortName='time',sortType='desc'))
        if not isinstance(data,dict) or 'announcements' not in data:
            raise ValueError('巨潮公告查询响应异常')
        items=data['announcements']
        if items is None:items=[]
        if not isinstance(items,list) or any(not isinstance(item,dict) for item in items):
            raise ValueError('巨潮公告列表结构异常，不能认定窗口无公告')
        if 'hasMore' in data and type(data['hasMore']) is not bool:
            raise ValueError('巨潮公告分页标记异常，不能认定检索完成')
        for item in items:
            name=re.sub('<[^>]+>','',item.get('secName',''))
            title=re.sub('<[^>]+>','',item.get('announcementTitle',''))
            path=item.get('adjunctUrl','')
            matched=(item.get('orgId')==resolved['orgId'] or
                     (not item.get('orgId') and str(item.get('secCode','')).strip()==str(query_code)))
            location=document_location(path)
            if not matched or location is None:
                continue
            if not any(word in title for word in ['发行公告','发行结果','招股说明书','上市公告','发行安排','网上路演','投资风险','申购','更正','修订','补充','撤回','取消']):
                continue
            url,day=location
            found.append(dict(title=title,date=day,source='巨潮资讯',
                              url=url,
                              issuerCode=item.get('secCode'),issuerOrgId=resolved['orgId']))
        if not data.get('hasMore'): break
    else: raise ValueError('公告分页超出限制，保留旧公告')
    alias=VERIFIED_OLD_CODES.get(stock['code'])
    if _code is None and alias and alias['orgId']==resolved['orgId']:
        found.extend(query(stock,searchkey,_resolved=resolved,_code=alias['code']))
    return list({a['url']:a for a in found}.values())

def enrich(snapshot,previous,max_queries=20):
    if type(max_queries)!=int or not 0<=max_queries<=50:raise ValueError('Announcement query limit must be 0..50')
    old={s['code']:s for s in previous.get('records',[])}
    now=snapshot['fetchedAt']
    today=dt.date.today()
    pending=[]
    for stock in snapshot['records']:
        prior=old.get(stock['code'],{})
        stock['announcements']=prior.get('announcements',[])
        stock['announcementCheckedAt']=prior.get('announcementCheckedAt')
        stock['announcementError']=prior.get('announcementError')
        stock['announcementStatus']=prior.get('announcementStatus','cached' if stock['announcements'] else 'not_checked')
        # Refresh active issuers each run; backfill missing historical disclosures.
        recent=stock['applyDate'] and (today-dt.date.fromisoformat(stock['applyDate'])).days<120
        if stock['applyDate'] and (recent or not stock['announcements']): pending.append(stock)
    def fetch_one(stock):
        try: return stock,query(stock),None
        except Exception as exc: return stock,None,str(exc)
    failures=0
    queried=0
    attempted={}
    access_stopped=False
    # Bounded incremental backfill, stop immediately on access limits.
    pending.sort(key=lambda s:((today-dt.date.fromisoformat(s['applyDate'])).days>=120,
                               s.get('announcementCheckedAt') or '',bool(s['announcements']),
                               -dt.date.fromisoformat(s['applyDate']).toordinal()))
    for target in pending[:max_queries]:
            stock,items,error=fetch_one(target)
            queried+=1
            attempted[stock['code']]={'code':stock['code'],'previousCheckedAt':stock.get('announcementCheckedAt'),'cachedLinkCount':len(stock['announcements'])}
            if error:
                failures+=1
                stock['announcementError']='官方公告未更新，保留旧链接：'+error
                stock['announcementStatus']='failed'
                attempted[stock['code']].update(status='failed-cache-retained',reason=error,newLinkCount=None)
                if '403' in error or '429' in error:access_stopped=True;break
            else:
                merged=merge_links(stock['announcements'],items)
                stock['announcements']=sorted(merged.values(),key=lambda a:a['date'],reverse=True)
                stock['announcementCheckedAt']=now
                stock['announcementStatus']='matched' if stock['announcements'] else 'no_match_in_window'
                stock.pop('announcementError',None)
                attempted[stock['code']].update(status='matched-this-run' if items else 'no-match-this-run',newLinkCount=len(items),checkedAt=now)
            time.sleep(.5)
    for stock in snapshot['records']:
        # Exchange original links, when verified and cached, take precedence.
        items=stock['announcements']
        stock['announcementVersionReview']=version_review(items)
        ranked=sorted(items,key=lambda a:(not a['url'].startswith('https://www.bse.cn/'),
            '发行公告' not in a['title'],'招股说明书' not in a['title']))
        if ranked:
            stock['announcementUrl']=ranked[0]['url']
            stock['announcementSource']=ranked[0]['source']
        else:
            status=stock['announcementStatus']
            label='官方检索未完成' if status=='not_checked' else '本次检索窗口未匹配' if status=='no_match_in_window' else '官方检索失败，待重试'
            stock['announcementSource']='东方财富（补充，'+label+'）'
    snapshot['announcementRefresh']=dict(checkedAt=now,queried=queried,failed=failures,pending=max(0,len(pending)-queried),
        covered=sum(bool(s['announcements']) for s in snapshot['records']),eligible=len(pending),outOfScope=len(snapshot['records'])-len(pending),accessLimitStopped=access_stopped,
        matchedThisRun=sum(x['status']=='matched-this-run' for x in attempted.values()),noMatchThisRun=sum(x['status']=='no-match-this-run' for x in attempted.values()),
        scope='Recent issuers and records without cached links; covered includes old links and is not this-run verification')
    snapshot['announcementRefreshDetails']=[attempted.get(s['code'],{'code':s['code'],'status':'not-attempted','reason':'access-limit-stop' if access_stopped else 'batch-limit','cachedLinkCount':len(s['announcements']),'previousCheckedAt':s.get('announcementCheckedAt')}) for s in pending]
