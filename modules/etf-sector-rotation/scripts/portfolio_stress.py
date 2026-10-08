"""Historical correlation and user-defined one-period shocks; no forecasts."""
import argparse, datetime, json, math, statistics
from pathlib import Path
from urllib.parse import urlsplit

def pairs(items):
    result={}
    for key,value in items:
        if key in result:raise ValueError('输入JSON字段重复')
        result[key]=value
    return result

def reject_constant(value):raise ValueError('输入JSON包含非有限常量')

def num(x):
    if isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x): raise ValueError('数值必须有限且非布尔值')
    return x

def day(x):
    if not isinstance(x,str) or datetime.date.fromisoformat(x).isoformat()!=x:raise ValueError('日期须为YYYY-MM-DD')
    return datetime.date.fromisoformat(x)
def corr(a,b):
    if len(a)!=len(b):raise ValueError('相关性样本长度不一致')
    if len(a)<3: return None
    for x in a+b:num(x)
    scale_a=max(abs(x) for x in a);scale_b=max(abs(x) for x in b)
    if not scale_a or not scale_b:return None
    a=[x/scale_a for x in a];b=[x/scale_b for x in b]
    ma,mb=statistics.mean(a),statistics.mean(b)
    sa=sum((x-ma)**2 for x in a); sb=sum((x-mb)**2 for x in b)
    return sum((x-ma)*(y-mb) for x,y in zip(a,b))/math.sqrt(sa*sb) if sa*sb>0 else None

def analyze(d):
    if not isinstance(d,dict) or not isinstance(d.get('holdings'),list) or any(not isinstance(r,dict) for r in d['holdings']):raise ValueError('持仓请求须为对象及持仓对象数组')
    cutoff=day(d.get('asOf')); currency=d.get('baseCurrency'); holdings=d['holdings']
    if not isinstance(currency,str) or not currency.strip() or any(not isinstance(r.get('code'),str) or not r['code'].strip() for r in holdings):raise ValueError('币种及持仓代码须为非空文字')
    for key in ['windows','scenarios']:
        if not isinstance(d.get(key,[]),list) or any(not isinstance(x,dict) or not isinstance(x.get('name'),str) or not x['name'].strip() for x in d.get(key,[])):raise ValueError('窗口及情景须为含名称的对象数组')
    if not holdings or len({r['code'] for r in holdings})!=len(holdings): raise ValueError('持仓须非空且代码唯一')
    histories={}; values={}
    for r in holdings:
        if r['currency']!=currency: raise ValueError('须先统一市值和收益序列币种')
        v=num(r['marketValue'])
        if v<=0: raise ValueError('目前只支持正市值无杠杆持仓')
        values[r['code']]=v
        h=r.get('history',[])
        if not isinstance(h,list) or any(not isinstance(x,dict) for x in h):raise ValueError('历史须为对象数组')
        if h and (r.get('basis')!='total-return' or not r.get('sourceUrl')): raise ValueError('历史需要总收益口径和来源')
        if h:
            u=urlsplit(r['sourceUrl']);u.port
            if u.scheme not in ('http','https') or not u.hostname or u.username is not None or u.password is not None:raise ValueError('历史来源链接无效')
        obs={}
        for x in h:
            date=day(x['date'])
            if date>cutoff or date.isoformat() in obs: raise ValueError('历史含未来或重复日期')
            price=num(x['value'])
            if price<=0: raise ValueError('总收益序列须为正值')
            obs[date.isoformat()]=price
        histories[r['code']]=obs
    total=num(sum(values.values())); weights={k:v/total for k,v in values.items()}; codes=list(values)
    common=sorted(set.intersection(*(set(histories[k]) for k in codes)))
    # Compute returns only over identical consecutive observations in every supplied series.
    intervals=[(a,b) for a,b in zip(common,common[1:]) if all(sorted(histories[k]).index(b)==sorted(histories[k]).index(a)+1 for k in codes)]
    returns={k:[histories[k][b]/histories[k][a]-1 for a,b in intervals] for k in codes}
    for row in returns.values():
        for value in row:num(value)
    def matrix(indices):
        return {a:{b:corr([returns[a][i] for i in indices],[returns[b][i] for i in indices]) for b in codes} for a in codes}
    minobs=d.get('minimumObservations',60)
    if not isinstance(minobs,int) or isinstance(minobs,bool) or minobs<3: raise ValueError('最少观测数须为大于等于3的整数')
    allidx=list(range(len(intervals)))
    groups=[]
    for window in d.get('windows',[]):
        start,end=day(window['start']),day(window['end'])
        if start>end or end>cutoff: raise ValueError('窗口日期无效')
        idx=[i for i,(a,b) in enumerate(intervals) if start<=day(a) and day(b)<=end]
        groups.append({'name':window['name'],'observations':len(idx),'correlations':matrix(idx) if len(idx)>=minobs else None,'status':'已计算' if len(idx)>=minobs else '样本不足'})
    scenarios=[]
    for scenario in d.get('scenarios',[]):
        shocks=scenario.get('returnShocksPct',{})
        if not isinstance(shocks,dict):raise ValueError('情景冲击须为代码数值对象')
        assumptions=scenario.get('assumptions',[])
        if not isinstance(assumptions,list) or any(not isinstance(x,str) or not x.strip() for x in assumptions):raise ValueError('情景假设须为文字数组')
        unknown=set(shocks)-set(codes)
        if unknown: raise ValueError('冲击包含未知持仓代码')
        for v in shocks.values():
            if num(v)<-100: raise ValueError('无杠杆冲击不能低于-100%')
        missing=[k for k in codes if k not in shocks]
        pnl=num(sum(values[k]*shocks[k]/100 for k in shocks))
        if not missing:num(pnl/total*100)
        scenarios.append({'name':scenario['name'],'assumptions':scenario.get('assumptions',[]),'coveragePct':sum(weights[k] for k in shocks)*100,'missingCodes':missing,'coveredPnl':pnl,'portfolioPnl':None if missing else pnl,'portfolioReturnPct':None if missing else pnl/total*100,'maximumDrawdown':None,'note':'用户给定的一次冲击，不是价格预测；无时间路径不能计算最大回撤'})
    return {'version':1,'asOf':d['asOf'],'currency':currency,'totalValue':total,'weights':weights,'historical':{'observations':len(intervals),'intervalStart':intervals[0][0] if intervals else None,'intervalEnd':intervals[-1][1] if intervals else None,'correlations':matrix(allidx) if len(intervals)>=minobs else None,'windows':groups,'note':'共同连续观测的历史皮尔逊相关，不代表未来；窗口由使用者预先定义，危机窗口少量样本不作稳定性结论'},'scenarios':scenarios,'risk':'仅客观历史及假设压力分析，不构成投资建议；可能本金亏损。未含自动行业穿透、利率久期映射、动态再平衡或蒙特卡洛。'}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('input');ap.add_argument('--out',required=True);args=ap.parse_args()
    raw=Path(args.input).read_bytes();result=analyze(json.loads(raw.decode('utf-8-sig'),object_pairs_hook=pairs,parse_constant=reject_constant))
    import hashlib
    result['inputSha256']=hashlib.sha256(raw).hexdigest()
    path=Path(args.out);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2,allow_nan=False)
if __name__=='__main__':main()
