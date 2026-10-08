"""Coverage-aware source planning and dispatch through existing collectors."""
import datetime as dt
from collection_validation import day

KINDS = ['stock','fund','etf','bond','convertible','government-bond','credit-bond']
DOMAINS = ['history','financial-summary','announcement-metadata','original-pdf','realtime-iopv','industry','licensed-terminal','alternative']

def registry():
    definitions = [
        ('public-market-history','third-party','history',KINDS,'batch','第三方未复权日线；基金为净值序列；债券需明确交易所；不保证完整区间'),
        ('eastmoney-financial-summary','third-party','financial-summary',['stock'],'batch','第三方财务摘要，不等于三张报表原文核验'),
        ('eastmoney-announcement-metadata','third-party','announcement-metadata',['stock','etf','bond','convertible','government-bond','credit-bond'],'batch','公告标题与链接元数据，空响应不能证明没有公告'),
        ('supplied-original-pdf','user-supplied','original-pdf',KINDS,'verify_original.py','需提供真实PDF及核验清单；尚无任意发行人自动下载闭环'),
        ('realtime-iopv','unconnected','realtime-iopv',['etf'],None,'未接入'),
        ('industry-data','unconnected','industry',KINDS,None,'未接入统一产业数据源'),
        ('licensed-terminal','licensed-vendor','licensed-terminal',KINDS,None,'未配置授权接口'),
        ('alternative-data','unconnected','alternative',KINDS,None,'未接入')]
    return {'type':'research-source-registry','version':1,'sources':[{
        'id':i,'publisherTier':tier,'dataDomain':domain,'kinds':kinds,'adapter':adapter,
        'delivery':'pdf' if domain=='original-pdf' else 'api' if adapter=='batch' else None,
        'authorization':'user-supplied' if domain=='original-pdf' else 'not-assessed',
        'redistribution':'not-assessed','coverage':coverage,
        'verification':'requires-field-verification','historyRange':'request-dependent',
        'publicationTime':'observation-dependent','retrievedAt':None,
        'automatic':adapter=='batch'} for i,tier,domain,kinds,adapter,coverage in definitions]}

def plan(spec):
    if not isinstance(spec,dict):raise ValueError('数据源请求须为对象')
    day(spec.get('asOf'))
    requests=spec.get('requests')
    if not isinstance(requests,list) or not 1<=len(requests)<=1000:raise ValueError('requests须为1至1000项')
    sources=registry()['sources'];rows=[];seen=set()
    for index,r in enumerate(requests):
        if not isinstance(r,dict):raise ValueError('标的请求须为对象')
        kind=r.get('kind');code=r.get('code');domains=r.get('domains',['history'])
        if kind not in KINDS or not isinstance(code,str) or len(code)!=6 or not code.isascii() or not code.isdigit():raise ValueError('类型或六位代码无效')
        if not isinstance(domains,list) or not domains or any(not isinstance(d,str) or d not in DOMAINS for d in domains) or len(set(domains))!=len(domains):raise ValueError('未知或重复数据域')
        key=(kind,code,str(r.get('market','')))
        if key in seen:raise ValueError('重复标的')
        seen.add(key)
        if 'start' in r and day(r['start'])>day(spec['asOf']):raise ValueError('起点晚于截止日')
        bond=kind in ['bond','convertible','government-bond','credit-bond']
        for domain in domains:
            candidates=[s for s in sources if s['dataDomain']==domain and kind in s['kinds']]
            source=candidates[0] if candidates else None
            ready=bool(source and source['automatic'])
            reason=source['coverage'] if source else '该标的类型无此采集器'
            if ready and bond and str(r.get('market','')) not in ['0','1']:
                ready=False;reason='债券须明确market=0深市或1沪市；银行间未支持'
            rows.append({'requestIndex':index,'kind':kind,'code':code,'domain':domain,'sourceId':source['id'] if source else None,
                'status':'collectable' if ready else 'requires-input' if source and source['adapter']=='verify_original.py' else 'unsupported',
                'reason':reason,'authorization':'not-assessed','verification':'not-verified'})
    return {'type':'research-source-plan','asOf':spec['asOf'],'rows':rows,
        'limitations':['登记覆盖不证明本次取得数据','公开可访问不证明授权采集或再分发','当前修订历史不是历史时点冻结数据']}

def collect(spec,workspace,collector):
    result=plan(spec)
    executable={r['requestIndex'] for r in result['rows'] if r['status']=='collectable'}
    indices=[index for index in range(len(spec['requests'])) if index in executable]
    positions={index:position for position,index in enumerate(indices)}
    requests=[{k:v for k,v in spec['requests'][index].items() if k!='domains'} for index in indices]
    bundle=collector(workspace,{**{k:v for k,v in spec.items() if k!='requests'},'requests':requests}) if requests else None
    for r in result['rows']:
        if r['status']!='collectable':continue
        returned=bundle.get('rows',[]) if isinstance(bundle,dict) else []
        position=positions[r['requestIndex']]
        observed=returned[position] if isinstance(returned,list) and position<len(returned) else None
        if not isinstance(observed,dict) or observed.get('kind')!=r['kind'] or observed.get('code')!=r['code']:observed=None
        field={'history':'history','financial-summary':'financials','announcement-metadata':'announcements'}[r['domain']]
        r['status']='observed' if observed and observed.get(field) else 'missing'
        r['collectionStatus']=observed.get('collectionStatus') if observed else None
        r['errors']=observed.get('errors') if observed else '采集结果缺少对象'
        r['sourceVerification']='not-verified'
    return {**result,'type':'research-source-collection','bundle':bundle,
        'dispatchNote':'复用现有按标的采集器，可能同时采集其他组件；sourceId为路由登记，不替代结果中的实际URL、备用源和缓存时间'}
