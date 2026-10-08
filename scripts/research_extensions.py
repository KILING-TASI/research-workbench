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
    alias_result=None
    if d.get('securityAliases') is not None:
        from security_aliases import normalize
        alias_spec=d['securityAliases']
        if not isinstance(alias_spec,dict):raise ValueError('securityAliases须为records与links对象')
        alias_result=normalize({**alias_spec,'asOf':d['asOf']})
        for record in alias_spec['records']:
            if record['id'] in leaf_kinds and record['assetClass']!=leaf_kinds[record['id']]:raise ValueError('证券别名主数据与穿透资产类型冲突')
        normalized={};kinds={}
        for key,value in leaves.items():
            canonical=alias_result['canonicalIds'].get(key,key)
            if canonical in kinds and kinds[canonical]!=leaf_kinds[key]:raise ValueError('别名合并后的资产类型冲突')
            kinds[canonical]=leaf_kinds[key];normalized[canonical]=normalized.get(canonical,0)+value
        for trace in traces:trace['canonicalSecurityId']=alias_result['canonicalIds'].get(trace['path'][-1],trace['path'][-1])
        leaves=normalized;leaf_kinds=kinds
    stock_values=[value for key,value in leaves.items() if leaf_kinds[key]=='stock' and value>0]
    stock_total=sum(stock_values)
    security_hhi=sum((value/stock_total)**2 for value in stock_values) if stock_total else None
    security_concentration={'scope':'disclosed-stock-security-identifiers-not-issuer-normalized','securityCount':len(stock_values),
                            'knownStockPortfolioWeightPct':stock_total*100,'effectiveSecurityCount':1/security_hhi if security_hhi else None,
                            'topTenKnownStockPct':sum(sorted(stock_values,reverse=True)[:10])/stock_total*100 if stock_total else None,
                            'limitation':'同发行人多证券尚未合并；标识来自输入，不认证实际交易所身份；未知仓位未计入'}
    from investment_intent import issuer_exposure
    stock_rows=[{'assetId':key,'assetClass':leaf_kinds[key],'marketValue':value} for key,value in leaves.items()]
    unresolved_id='__unresolved_lookthrough__'
    while unresolved_id in leaves:unresolved_id+='_'
    residual=sum(item['weight'] for item in unknown)
    if residual>0:stock_rows.append({'assetId':unresolved_id,'assetClass':'other','marketValue':residual})
    identity=issuer_exposure({'asOf':d['asOf'],'intent':{},'holdings':stock_rows,'issuerRelations':d.get('issuerRelations',[])}) if stock_rows else None
    concentration=identity['equityConcentration'] if identity else None
    if concentration:
        concentration['scope']='disclosed-lookthrough-known-equity-issuers'
        concentration['rawStockPathCount']=sum(item['kind']=='stock' and item['weight']>0 for item in traces)
        concentration['unresolvedPortfolioWeightPct']=residual*100
        concentration['reportDates']=sorted({item['reportDate'] for item in traces if item['kind']=='stock' and item['weight']>0})
        issuer_by_asset={relation['assetId']:group['issuerId'] for group in identity['groups'] for relation in group['assets']}
        routes={};issuer_weights={};position_weights={}
        for trace in traces:
            issuer=issuer_by_asset.get(trace.get('canonicalSecurityId',trace['path'][-1])) if trace['kind']=='stock' else None
            if issuer is None or trace['weight']<=0:continue
            routes.setdefault(issuer,set()).add(trace['path'][1])
            issuer_weights[issuer]=issuer_weights.get(issuer,0)+trace['weight']
            position=position_weights.setdefault(trace['path'][1],{})
            position[issuer]=position.get(issuer,0)+trace['weight']
        known_weight=sum(issuer_weights.values())
        concentration['heldThroughMultipleRootPositionsPct']=sum(value for issuer,value in issuer_weights.items() if len(routes[issuer])>=2)/known_weight*100 if known_weight else None
        concentration.pop('heldThroughMultipleDirectPositionsPct',None)
        concentration['positionDiagnostics']=[]
        for position,own in position_weights.items():
            own_total=sum(own.values());rest={issuer:sum(weights.get(issuer,0) for key,weights in position_weights.items() if key!=position) for issuer in issuer_weights}
            rest_total=sum(rest.values())
            overlap=sum(min(value/own_total,rest.get(issuer,0)/rest_total) for issuer,value in own.items()) if rest_total>0 else None
            unique=sum(value for issuer,value in own.items() if rest.get(issuer,0)==0)/own_total if rest_total>0 else None
            rest_hhi=sum((value/rest_total)**2 for value in rest.values()) if rest_total>0 else None
            concentration['positionDiagnostics'].append({'positionId':position,'knownMappedEquityPortfolioWeightPct':own_total*100,
                'replicatedByOtherKnownEquityPct':overlap*100 if overlap is not None else None,
                'uniqueCompanyShareOfOwnKnownEquityPct':unique*100 if unique is not None else None,
                'remainingKnownEquityEffectiveIssuerCount':1/rest_hhi if rest_hhi else None,
                'scope':'mapped disclosed equity only; excluding unknown holdings and non-equity',
                'limitation':'未披露仓位可能改变重叠和独有比例；移除后仅将其余已知股票归一化，不模拟现金、交易或收益风险'})
        concentration['limitations']=['只在已披露且有适用发行人关系的股票内部归一化，不是全部组合风险数量','未披露仓位可能包括额外股票；基金多期混合快照不等于同日真实组合','关系来自输入及其原文定位层次，未提供映射的证券不按名称猜发行人']
    return {'type':'recursive-disclosed-holdings','leaves':leaves,'unknown':unknown,'paths':traces,'securityAliases':alias_result,'securityConcentration':security_concentration,'equityConcentration':concentration,'issuerEvidenceCoverage':identity['evidenceCoverage'] if identity else [],'limitations':['输入披露快照不等于当前真实持仓','不还原MOM未公开子账户或真实交易；未知仓位保留','跨报告期混合快照逐路径标注，不称实时穿透']}

def fof_brief(result):
    concentration=result.get('equityConcentration') or {}
    lines=['# 组合是否只是看起来分散？','']
    if concentration.get('effectiveIssuerCount') is None:
        lines+=['目前尚不能评价公司层面的分散程度：缺少可用股票暴露或适用发行人关系。未知部分没有填成零。']
    else:
        lines+=['> 已关联股票的集中度，相当于'+format(float(concentration['effectiveIssuerCount']),'.2f')+'个等权主体；这是集中度，不是独立风险数量。',
                '', '已映射股票仅覆盖全组合'+format(float(concentration['portfolioCoveragePct']),'.2f')+'%。未披露或未分类仓位占'+format(concentration['unresolvedPortfolioWeightPct'],'.2f')+'%，不能据此认定全组合已分散。',
                '', '## 每项持仓给组合增加了什么？', '以下只比较已知、已映射的股票部分；不同报告期与未知仓位可能改变结论。']
        for row in concentration.get('positionDiagnostics',[]):
            label=row['positionId'].replace('\n',' ').replace('\r',' ')
            lines+=['','### '+label]
            if row['replicatedByOtherKnownEquityPct'] is None:
                lines+=['其余项目没有可比较的已知股票，不能计算重叠或独有公司比例。'];continue
            lines+=['与其余已知股票的权重重叠为'+format(row['replicatedByOtherKnownEquityPct'],'.2f')+'%；仅该项目触达的公司占其自身已知股票'+format(row['uniqueCompanyShareOfOwnKnownEquityPct'],'.2f')+'%。']
            if row['uniqueCompanyShareOfOwnKnownEquityPct']==0:
                lines+=['它没有增加新的已知公司，但仍可能改变公司权重、费用和风险特征，不能直接解释为没有作用。']
            lines+=['假设移除该项、只将其余已知股票重新归一化，集中度相当于'+format(row['remainingKnownEquityEffectiveIssuerCount'],'.2f')+'个等权主体。该比较没有模拟交易、费用、现金去向或未来风险。']
    securities=result.get('securityConcentration') or {}
    if securities.get('effectiveSecurityCount') is not None:
        lines+=['','## 不合并发行人时，证券权重是否均匀？','已知股票含'+str(securities['securityCount'])+'个输入证券标识，集中度相当于'+format(securities['effectiveSecurityCount'],'.2f')+'个等权证券；前十占已知股票'+format(securities['topTenKnownStockPct'],'.2f')+'%。这不是已经归一后的公司数，也不是全组合独立风险数。',
                '这些股票覆盖全组合输入权重'+format(securities['knownStockPortfolioWeightPct'],'.2f')+'%。'+securities['limitation']]
    if concentration.get('reportDates'):lines+=['','所用股票报告期：'+'、'.join(concentration['reportDates'])+'；不同报告期不是同日实时快照。']
    lines+=['','## 资料边界',*result['limitations'],'股票发行人关系保留声明与原文定位层次；同一公司的不同证券仍保留市场、币种及权利差异。']
    return '\n'.join(lines)

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

def publish_fof(document,out):
    import json,hashlib
    from pathlib import Path
    from research_brief_html import render
    out=Path(out)
    if out.exists():raise ValueError('输出目录已存在，请另存')
    result=fof(document);body=fof_brief(result)
    if document.get('exampleType')=='teaching-only':body='**教学样本：输入权重与关系为演示，不是真实账户。**\n\n'+body
    raw=json.dumps(document,ensure_ascii=False,indent=2,allow_nan=False)
    result['inputSha256']=hashlib.sha256(raw.encode()).hexdigest()
    out.mkdir(parents=True)
    (out/'input.json').write_text(raw,'utf-8');(out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),'utf-8')
    (out/'组合穿透说明.md').write_text(body,'utf-8');(out/'组合穿透说明.html').write_text(render(body,'组合穿透与冗余说明'),'utf-8')
    return result

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
    p.add_argument('--brief',help='fof：另存可读Markdown及HTML说明，须使用新的.md文件')
    a=p.parse_args()
    brief_path=Path(a.brief) if a.brief else None
    if brief_path and (a.mode!='fof' or brief_path.suffix!='.md' or brief_path.exists() or brief_path.with_suffix('.html').exists()):raise ValueError('仅fof支持--brief，使用尚不存在的.md文件')
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
    if brief_path:
        from research_brief_html import render
        body=fof_brief(result);brief_path.parent.mkdir(parents=True,exist_ok=True)
        brief_path.write_text(body,'utf-8');brief_path.with_suffix('.html').write_text(render(body,'组合穿透与冗余说明'),'utf-8')
