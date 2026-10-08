"""ETF evaluation metrics with evidence and date gates; no ranking or trades."""
import datetime as dt
import math
import statistics
from urllib.parse import urlsplit

def date(value):
    if not isinstance(value,str):raise ValueError('日期须为YYYY-MM-DD')
    parsed=dt.date.fromisoformat(value)
    if parsed.isoformat()!=value:raise ValueError('日期须为YYYY-MM-DD')
    return parsed

def num(x):
    return isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x)

def security_key(row):
    """Explicit security identity; never infer a market from code or name."""
    if not isinstance(row,dict):return None
    code=row.get('code');share=row.get('shareClass');market=row.get('market');namespace=row.get('securityNamespace')
    if not all(isinstance(x,str) and x.strip() for x in (code,share,market)):return None
    if namespace:
        markets={'CN-equity':{'SSE','SZSE','BSE','CN-exchange-unresolved'},'HK-equity':{'HKEX','HK-exchange-unresolved'},'US-equity':{'NASDAQ','NYSE','AMEX','US-exchange-unresolved'}}
        if namespace not in markets or market not in markets[namespace]:return None
    return (namespace or market,code,share)

def evaluate_layers(d):
    if not isinstance(d,dict) or not all(isinstance(d.get(k),dict) for k in ['current','candidate']):raise ValueError('ETF评价须提供两个产品对象')
    if not num(d.get('positionValue')) or d['positionValue']<=0 or not num(d.get('holdingYears')) or d['holdingYears']<=0:raise ValueError('资金与持有期限须为有限正数')
    if not isinstance(d.get('positionCurrency'),str) or not d['positionCurrency'].strip():raise ValueError('须声明持仓币种')
    cutoff=date(d['asOf'])
    def fact(p,key):
        if not isinstance(p,dict):return None
        e=p.get(key)
        if not isinstance(e,dict):return None
        try:
            if date(e['observedAt'])>cutoff or date(e['availableAt'])>cutoff:return None
            if not isinstance(e.get('sourceUrl'),str) or not e['sourceUrl'].startswith('https://') or not isinstance(e.get('locator'),str) or not e['locator'].strip() or e.get('verification') not in ['official-reviewed','third-party-observed']:return None
            if any(c.isspace() or ord(c)<32 or ord(c)==127 for c in e['sourceUrl']):return None
            source=urlsplit(e['sourceUrl']);port=source.port
            if not source.hostname or source.username is not None or source.password is not None or port not in (None,443):return None
        except (KeyError,ValueError,TypeError):return None
        return e
    def item(key,title,value=None,unit='',gap='',evidence=None):
        return dict(id=key,title=title,value=value,unit=unit,status=('已核对资料' if key in ['valuation','methodology','operations','sectorWeights','assets','premium'] else '已计算') if value is not None else '待补证据',gap=gap if value is None else '',evidence=evidence or [])
    def weights(e):
        if not e or not isinstance(e.get('value'),list):return None
        rows=e['value']
        if not all(isinstance(r,dict) for r in rows):return None
        ids=[security_key(r) for r in rows] if any(r.get('market') or r.get('securityNamespace') or r.get('shareClass') for r in rows) else [r.get('code') for r in rows]
        if not rows or not all(ids) or len(set(ids))!=len(ids):return None
        if not all(num(r.get('weight')) and 0<=r['weight']<=1 for r in rows):return None
        if abs(sum(r['weight'] for r in rows)-1)>0.00001:return None
        return rows
    def series(e,basis):
        if not e or e.get('basis')!=basis or e.get('currency')!=d['positionCurrency']:return None
        if e.get('frequency','daily') not in ['daily','trading_day']:return None
        rows=e.get('value');result={}
        if not isinstance(rows,list):return None
        try:
            for r in rows:
                day=dt.date.fromisoformat(r['date'])
                if day>cutoff or day>date(e['observedAt']) or day>date(e['availableAt']) or day.isoformat()!=r['date'] or r['date'] in result or not num(r['value']) or r['value']<=0:return None
                result[r['date']]=r['value']
        except (KeyError,TypeError,ValueError):return None
        return result
    def risk(s):
        if not s or len(s)<121:return None
        vals=[s[k] for k in sorted(s)];returns=[b/a-1 for a,b in zip(vals,vals[1:])]
        if any(not math.isfinite(r) for r in returns):raise ValueError('ETF收益计算溢出，需检查序列尺度')
        peak=vals[0];dd=0
        for v in vals:peak=max(peak,v);dd=min(dd,v/peak-1)
        return {'start':min(s),'end':max(s),'observations':len(s),'annualVolatilityPct':statistics.stdev(returns)*math.sqrt(252)*100,'maxDrawdownPct':dd*100}
    portfolio_risk=None
    holdings=d.get('portfolio',[])
    if not isinstance(holdings,list) or any(not isinstance(h,dict) for h in holdings):raise ValueError('组合持仓须为对象列表')
    if holdings and len({h.get('code') for h in holdings})==len(holdings) and all(h.get('code') for h in holdings) and all(num(h.get('weight')) and 0<=h['weight']<=1 for h in holdings) and abs(sum(h['weight'] for h in holdings)-1)<1e-8:
        hs=[series(fact(h,'navTotalReturn'),'nav-total-return') for h in holdings]
        if all(hs) and all(set(h)==set(hs[0]) for h in hs) and len(hs[0])>=121:
            dates=sorted(hs[0]);rets=[[h[b]/h[a]-1 for a,b in zip(dates,dates[1:])] for h in hs]
            if any(not math.isfinite(v) for row in rets for v in row):raise ValueError('组合收益计算溢出，需检查序列尺度')
            n=len(rets[0]);means=[statistics.mean(r) for r in rets]
            cov=[[sum((x-mx)*(y-my) for x,y in zip(rx,ry))/(n-1)*252 for ry,my in zip(rets,means)] for rx,mx in zip(rets,means)]
            ws=[h['weight'] for h in holdings];marginal=[sum(c*w for c,w in zip(row,ws)) for row in cov]
            variance=sum(w*m for w,m in zip(ws,marginal))
            if variance>0:
                portfolio_risk={'start':dates[0],'end':dates[-1],'returnObservations':n,'annualVolatilityPct':math.sqrt(variance)*100,'contributions':[{'code':h['code'],'weightPct':w*100,'varianceContributionPct':w*m/variance*100} for h,w,m in zip(holdings,ws,marginal)],'basis':'用户提供完整权重，共同全收益日期；方差贡献可为负；不等于收益贡献'}
    outputs=[]
    for p in [d['current'],d['candidate']]:
        ce=fact(p,'constituents');cw=weights(ce)
        ie=fact(p,'indexTotalReturn');ix=series(ie,'index-total-return')
        ne=fact(p,'navTotalReturn');nav=series(ne,'nav-total-return')
        concentration=None
        if cw:
            sector={}
            for r in cw:sector[r.get('sector','未分类')]=sector.get(r.get('sector','未分类'),0)+r['weight']
            concentration={'top10WeightPct':sum(sorted([r['weight'] for r in cw],reverse=True)[:10])*100,'hhi':sum(r['weight']**2 for r in cw),'classifiedWeightPct':sum(v for k,v in sector.items() if k!='未分类')*100,'sectorWeightsPct':{k:v*100 for k,v in sector.items() if k!='未分类'},'constituents':len(cw)}
        financial_quality=None
        fe=fact(p,'financials')
        if fe and cw and fe.get('unit')=='CNY' and isinstance(fe.get('value'),list):
            records=fe['value'];fm={};valid=True;periods=set()
            for row in records:
                try:
                    if row['code'] in fm or dt.date.fromisoformat(row['publishedAt'])>cutoff or dt.date.fromisoformat(row['period'])>cutoff or not num(row.get('netProfit')) or not (num(row.get('operatingCash')) or num(row.get('operatingCashPerShare'))):valid=False;break
                    fm[row['code']]=row;periods.add(row['period'])
                except (KeyError,TypeError,ValueError):valid=False;break
            if valid and len(periods)==1:
                covered=sum(r['weight'] for r in cw if r['code'] in fm)
                def positive_cash(row):
                    cash=row.get('operatingCash')
                    if not num(cash):cash=row.get('operatingCashPerShare')
                    return num(cash) and cash>0
                financial_quality={'reportPeriod':next(iter(periods)),'coveredWeightPct':covered*100,'profitableCoveredWeightPct':sum(r['weight'] for r in cw if r['code'] in fm and fm[r['code']]['netProfit']>0)*100,'positiveOperatingCashCoveredWeightPct':sum(r['weight'] for r in cw if r['code'] in fm and positive_cash(fm[r['code']]))*100,'assessment':('覆盖不足80%，不形成指数盈利质量判断' if covered<.8 else '仅为同报告期财务事实；须按行业区分金融企业经营现金流，不据此评分')}
        tr=None
        if nav and ix and p.get('indexId') and ne.get('indexId')==ie.get('indexId')==p['indexId'] and ne.get('indexVariant')==ie.get('indexVariant')==p.get('indexVariant') and p.get('indexVariant'):
            dates=sorted(set(nav)&set(ix))
            # Never silently skip absent trading observations in tracking calculations.
            if len(dates)>=121 and set(nav)==set(ix):
                nr=[nav[b]/nav[a]-1 for a,b in zip(dates,dates[1:])];ir=[ix[b]/ix[a]-1 for a,b in zip(dates,dates[1:])]
                if any(not math.isfinite(v) for v in nr+ir):raise ValueError('ETF跟踪收益计算溢出，需检查序列尺度')
                n=len(nr);tr={'start':dates[0],'end':dates[-1],'provisional':not ne.get('dividendCalendarVerified',False),'note':('区间内现金分红已核对；单位净值为第三方观测，理论除息日再投资，不模拟红利支付等待' if ne.get('dividendCalendarVerified') else '分红与除息事件尚未逐条公告核验时仅为研究测算'),'returnObservations':n,'trackingErrorPct':statistics.stdev([a-b for a,b in zip(nr,ir)])*math.sqrt(252)*100,'annualTrackingDifferencePct':((nav[dates[-1]]/nav[dates[0]])**(252/n)-(ix[dates[-1]]/ix[dates[0]])**(252/n))*100}
        li=fact(p,'liquidity');lv=li.get('value',{}) if li else {};liquidity=None
        if not isinstance(lv,dict):lv={}
        dates=lv.get('dates',[])
        try:valid=isinstance(dates,list) and len(set(dates))==len(dates)>=20 and lv.get('count')==len(dates) and all(date(x)<=min(cutoff,date(li['observedAt']),date(li['availableAt'])) for x in dates)
        except (TypeError,ValueError):valid=False
        if valid and num(lv.get('averageAmount')) and lv['averageAmount']>0:liquidity={'averageAmount':lv['averageAmount'],'orderParticipationPct':d['positionValue']/lv['averageAmount']*100,'start':min(dates),'end':max(dates)}
        fee=fact(p,'annualFeePct');fv=fee.get('value') if fee else None
        if not num(fv) or not 0<=fv<=10:fv=None
        qe=fact(p,'quote');q=qe.get('value',{}) if qe else {};spread=None
        if not isinstance(q,dict):q={}
        if all(num(q.get(k)) and q[k]>0 for k in ['bid','ask']) and q['ask']>=q['bid']:spread=(q['ask']-q['bid'])/((q['ask']+q['bid'])/2)*100
        overlap=[]
        for h in d.get('portfolio',[]):
            he=fact(h,'constituents');hw=weights(he)
            if not hw or not cw or he['observedAt']!=ce['observedAt'] or he.get('basis')=='index-constituents' or ce.get('basis')=='index-constituents':overlap.append({'code':h.get('code'),'overlapPct':None,'gap':'缺完整同日成分权重'});continue
            if any(security_key(r) is None for r in hw+cw):
                overlap.append({'code':h.get('code'),'overlapPct':None,'gap':'缺明确证券市场、代码或类别，不能仅按代码匹配'});continue
            hm={security_key(r):r['weight'] for r in hw}
            overlap.append({'code':h.get('code'),'overlapPct':sum(min(r['weight'],hm.get(security_key(r),0)) for r in cw)*100,'basis':'同日证券市场或命名空间、代码及类别；非公司主体或行业重叠'})
        outputs.append({'code':p['code'],'layers':[
            {'title':'指数评价','metrics':[item('concentration','成分与行业集中度',concentration,gap='需完整、同日、总权重为100%的成分表',evidence=[ce] if ce else []),item('indexRisk','指数历史风险',risk(ix),gap='需至少121期同币种全收益指数，252期年化',evidence=[ie] if ie else []),item('valuation','指数估值观测',value=(fact(p,'valuation') or {}).get('value'),gap='缺同口径估值；估值不是盈利质量',evidence=[fact(p,'valuation')] if fact(p,'valuation') else []),item('methodology','编制与调整机制',value=(fact(p,'methodology') or {}).get('value'),gap='需指数公司生效版本、调整和权重规则',evidence=[fact(p,'methodology')] if fact(p,'methodology') else []),item('earningsQuality','成分股盈利质量',value=financial_quality,gap='需完整成分财务、相同报告期和逐公司披露日；不能用PE替代',evidence=[fe] if fe else []),item('sectorWeights','官方行业权重',value=(fact(p,'sectorWeights') or {}).get('value'),gap='完整成分行业分类或官方同日聚合权重未取得',evidence=[fact(p,'sectorWeights')] if fact(p,'sectorWeights') else [])]},
            {'title':'产品评价','metrics':[item('navRisk','产品分红再投资历史风险',risk(nav),gap='需至少121期可核对分红及折算的净值历史',evidence=[ne] if ne else []),item('fees','管理及托管年费率',fv,'%',gap='缺年费来源；不是完整TER',evidence=[fee] if fee else []),item('tracking','全收益净值跟踪质量',tr,gap='需至少121期完整共同交易日、同币种同版本全收益序列',evidence=[x for x in [ne,ie] if x]),item('liquidity','历史成交与订单占比',liquidity,gap='需至少20期可核对成交日期',evidence=[li] if li else []),item('spread','报价买卖价差',spread,'%',gap='缺有效买卖盘；历史报价不代表当前成交',evidence=[qe] if qe else []),item('assets','规模与份额观测',value=(fact(p,'assets') or {}).get('value'),gap='需净资产及份额历史；单点不判断稳定性',evidence=[fact(p,'assets')] if fact(p,'assets') else []),item('premium','收盘折溢价',value=(fact(p,'closingPremium') or {}).get('value'),gap='缺同交易日收盘价格与单位净值；非实时IOPV',evidence=[fact(p,'closingPremium')] if fact(p,'closingPremium') else []),item('operations','复制、申赎与运营',value=(fact(p,'operations') or {}).get('value'),gap='需基金合同、申赎清单及公告',evidence=[fact(p,'operations')] if fact(p,'operations') else [])]},
            {'title':'组合适配','metrics':[item('overlap','与已有持仓的成分重叠',overlap if overlap else None,gap='未提供完整持仓及成分资料'),item('riskContribution','组合风险贡献',value=portfolio_risk,gap='需总和100%的真实权重和至少121期完整共同全收益历史'),item('constraints','期限、资金与再平衡约束',{'holdingYears':d['holdingYears'],'positionValue':d['positionValue'],'currency':d['positionCurrency']},evidence=[])]}]
        })
    for product in outputs:
        for layer in product['layers']:
            for metric in layer['metrics']:
                if metric['value'] is None:continue
                def finite_tree(value):
                    if isinstance(value,(int,float)) and not isinstance(value,bool):return math.isfinite(value)
                    if isinstance(value,dict):return all(finite_tree(v) for v in value.values())
                    if isinstance(value,list):return all(finite_tree(v) for v in value)
                    return True
                if not finite_tree(metric['value']):raise ValueError('ETF派生结果非有限，需检查数值尺度，不交付风险指标')
                if metric['id']=='overlap':
                    matched=[row for row in metric['value'] if num(row.get('overlapPct'))]
                    gaps=[row.get('gap','待补证据') for row in metric['value'] if not num(row.get('overlapPct'))]
                    if gaps:
                        metric['status']='部分已计算，部分待补证据' if matched else '待补证据'
                        metric['gap']='；'.join(dict.fromkeys(gaps))
                if metric['status']=='已核对资料' and any(e.get('verification')=='third-party-observed' for e in metric['evidence']):metric['status']='第三方观测，未核验官方原文'
                if metric['id']=='navRisk' and not any(e.get('dividendCalendarVerified',False) for e in metric['evidence']):metric['status']='研究测算，待分红核验'
                if metric['id']=='tracking' and metric['value'].get('provisional'):metric['status']='研究测算，待分红核验'
                if metric['id']=='earningsQuality' and metric['value']['coveredWeightPct']<80:metric['status']='覆盖不足，不判定质量'
                if metric['id']=='assets' and not isinstance(metric['value'],dict):
                    metric.update(value=None,status='待补证据',gap='规模与份额资料结构无效');continue
                if metric['id']=='assets':metric['status']='已接入规模及份额观测，未判定稳定性' if metric['value'].get('sharesHistory') else '已接入净资产，份额历史待补'
                if metric['id']=='operations':metric['status']='已取得部分运营资料'
                if metric['id'] in ['assets','operations'] and any(e.get('verification')=='third-party-observed' for e in metric['evidence']):metric['status']+='；第三方观测，未核验官方原文'
    return {'version':1,'products':outputs,'boundary':'登记状态不替代原文核验；已计算不表示优质。历史风险按252个日度观测年化；未声明频率的旧输入沿用日度假设，交易日历未独立核验；明确周度或月度序列不计算日度风险。缺失不计零，不产生综合排名或未来收益承诺。'}
