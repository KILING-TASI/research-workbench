"""Recursive disclosed holdings, scheduled crisis paths and timestamped quote status."""
import datetime as dt,math
import numpy as np
from portfolio_models import prepare,number
from collection_validation import day,unique_pairs,reject_constant,finite_json_float
from research_library import url as source_url

def fof(d):
    cutoff=day(d['asOf']);nodes=d['nodes'];root=d['root'];max_depth=d.get('maxDepth',10)
    if not isinstance(nodes,dict) or root not in nodes or isinstance(max_depth,bool) or not isinstance(max_depth,int) or not 1<=max_depth<=20:raise ValueError('节点、根或深度无效')
    leaves={};unknown=[];traces=[];leaf_kinds={}
    def walk(key,exposure,path):
        if key in path:unknown.append({'path':path+[key],'weight':exposure,'reason':'循环引用'});return
        if len(path)>=max_depth:unknown.append({'path':path+[key],'weight':exposure,'reason':'深度上限'});return
        if key not in nodes:unknown.append({'path':path+[key],'weight':exposure,'reason':'子基金资料缺失'});return
        n=nodes[key]
        if n.get('currency')!=d['currency']:raise ValueError('节点币种未统一')
        if not n.get('sourceUrl') or not n.get('reportDate') or not n.get('publishedAt'):raise ValueError('披露来源或日期缺失')
        source_url(n['sourceUrl'])
        if not day(n['reportDate'])<=day(n['publishedAt'])<=cutoff:raise ValueError('报告日期越界')
        holdings=n.get('holdings',[]);total=0;seen=set()
        for h in holdings:
            w=number(h['weight'])
            if not 0<=w<=1:raise ValueError('权重越界')
            ident=h.get('node') if h.get('kind')=='fund' else h.get('id')
            if not isinstance(ident,str) or not ident.strip() or ident in seen:raise ValueError('节点持仓身份重复或缺失')
            seen.add(ident);total+=w
            if h.get('kind')=='fund':walk(ident,exposure*w,path+[key])
            elif h.get('kind') in ['stock','bond','cash','other']:
                if ident in leaf_kinds and leaf_kinds[ident]!=h['kind']:raise ValueError('同一底层资产身份存在类型冲突')
                leaf_kinds[ident]=h['kind']
                leaves[ident]=leaves.get(ident,0)+exposure*w
                traces.append({'path':path+[key,ident],'weight':exposure*w,'kind':h['kind'],'reportDate':n['reportDate'],'publishedAt':n['publishedAt']})
            else:raise ValueError('未知资产类型')
        if total>1+1e-10:raise ValueError('节点权重超过1')
        if total<1:unknown.append({'path':path+[key],'weight':exposure*(1-total),'reason':'未披露或未分类仓位'})
    walk(root,1,[])
    if abs(sum(leaves.values())+sum(x['weight'] for x in unknown)-1)>1e-9:raise ValueError('穿透权重不守恒')
    return {'type':'recursive-disclosed-holdings','leaves':leaves,'unknown':unknown,'paths':traces,'limitations':['输入披露快照不等于当前真实持仓','不还原MOM未公开子账户或真实交易；未知仓位保留','跨报告期混合快照逐路径标注，不称实时穿透']}

def crisis(d):
    r,mean,cov,dates=prepare(d);weights=np.array([number(x) for x in d['weights']]);n=r.shape[1]
    if weights.shape!=(n,) or min(weights)<0 or abs(sum(weights)-1)>1e-10:raise ValueError('权重无效')
    paths=d.get('paths',5000);seed=d.get('seed',42)
    if isinstance(paths,bool) or not isinstance(paths,int) or not 100<=paths<=10000 or isinstance(seed,bool) or not isinstance(seed,int) or not 0<=seed<2**32:raise ValueError('路径或种子无效')
    log_r=np.log1p(r);mu=log_r.mean(axis=0);cov=np.cov(log_r,rowvar=False);sd=np.sqrt(np.diag(cov));corr=np.divide(cov,np.outer(sd,sd),out=np.eye(n),where=np.outer(sd,sd)>0)
    rng=np.random.default_rng(seed);logwealth=np.zeros(paths);peak=np.zeros(paths);mdd=np.zeros(paths);regimes=[];steps=0
    for state in d['regimes']:
        periods=state['periods'];scale=number(state['volatilityMultiplier']);blend=number(state['correlationBlend']);shift=np.array([number(x) for x in state['logMeanShift']])
        if isinstance(periods,bool) or not isinstance(periods,int) or periods<1 or steps+periods>1200 or not 0<scale<=10 or not 0<=blend<=1 or shift.shape!=(n,):raise ValueError('情景参数无效')
        C=((1-blend)*corr+blend*np.ones((n,n)))*np.outer(sd,sd)*scale**2
        for _ in range(periods):
            sample=rng.multivariate_normal(mu+shift,C,size=paths,check_valid='raise');period_log=np.logaddexp.reduce(sample+np.where(weights>0,np.log(np.maximum(weights,1e-300)),-np.inf),axis=1)
            logwealth+=period_log;peak=np.maximum(peak,logwealth);mdd=np.maximum(mdd,-np.expm1(logwealth-peak))
        steps+=periods;regimes.append({**state,'periodCovariance':C.tolist()})
    if not regimes or not np.isfinite(logwealth).all() or np.max(logwealth)>700:raise ValueError('空情景或模拟溢出')
    return {'type':'scheduled-regime-crisis-simulation','paths':paths,'steps':steps,'seed':seed,'regimes':regimes,'terminalReturnPercentilesPct':{str(q):float(np.expm1(np.quantile(logwealth,q)))*100 for q in [.05,.5,.95]},'maxDrawdownPercentilesPct':{str(q):float(np.quantile(mdd,q))*100 for q in [.5,.95,.99]},'limitations':['状态顺序、波动倍数、相关性对冲强度、均值冲击均为明确假设，不预测危机','分状态正态对数收益仍可能低估厚尾、信用与流动性风险','每期无成本恢复权重；非完整市场状态估计或交易模型']}

def quote_status(row,now=None,max_age_seconds=900):
    now=now or dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None or not 0<number(max_age_seconds)<=86400:raise ValueError('时间须带时区，时效阈值须有效')
    quote=row.get('quote') or {};stamp=quote.get('quoteAt')
    if not stamp:return {'status':'unavailable','quote':quote or None,'reason':'缺少行情时间'}
    when=dt.datetime.fromisoformat(stamp)
    if when.tzinfo is None:raise ValueError('行情时间须有时区')
    age=(now-when).total_seconds()
    status='invalid-future' if age<0 else 'cached-after-failure' if row.get('errors') else 'recent-observation' if age<=max_age_seconds else 'stale-observation'
    return {'status':status,'quote':quote,'ageSeconds':age,'evaluatedAt':now.isoformat(),'maxAgeSeconds':max_age_seconds,'limitations':'第三方快照非交易所实时授权流；休市行情会标过期，未接IOPV或PCF'}


if __name__=='__main__':
    import argparse,json,hashlib
    from pathlib import Path
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['fof','crisis','quotes']);p.add_argument('input');p.add_argument('--out',required=True);p.add_argument('--workspace',default='.')
    a=p.parse_args()
    if Path(a.out).exists():raise FileExistsError('不覆盖首次结果')
    blob=Path(a.input).read_bytes();d=json.loads(blob.decode('utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float)
    if a.mode=='quotes':
        from portable_collect import collect
        if d.get('kind') not in ['stock','etf']:raise ValueError('行情仅支持stock或etf')
        b=collect(Path(a.workspace),d['kind'],d['codes'],d['asOf'],True)
        result={'type':'timestamped-quote-observations','rows':[{'code':r['code'],'errors':r.get('errors'),**quote_status(r,max_age_seconds=d.get('maxAgeSeconds',900))} for r in b['rows']]}
    else:result={'fof':fof,'crisis':crisis}[a.mode](d)
    result['inputSha256']=hashlib.sha256(blob).hexdigest();result['input']=d
    with Path(a.out).open('x',encoding='utf8') as f:json.dump(result,f,ensure_ascii=False,indent=2,allow_nan=False)
