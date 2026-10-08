"""Historical long-only frontier and joint block-bootstrap path simulation. Requires numpy."""
import argparse,datetime as dt,hashlib,itertools,json,math
from pathlib import Path
import numpy as np
from collection_validation import day,urls,unique_pairs,reject_constant

def number(x):
    if isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x):raise ValueError('必须为有限数')
    return x

def prepare(d):
    if not isinstance(d,dict):raise ValueError('组合模型输入须为对象')
    assets=d.get('assets');cutoff=day(d.get('asOf'));freq=d.get('frequency')
    if not isinstance(assets,list) or any(not isinstance(a,dict) or not isinstance(a.get('code'),str) or not a['code'].strip() for a in assets):raise ValueError('资产须为含代码的对象数组')
    if freq not in ['daily','monthly'] or not 2<=len(assets)<=6:raise ValueError('频率或资产数量不支持（2至6）')
    if len({a['code'] for a in assets})!=len(assets):raise ValueError('代码重复')
    dates=None;values=[]
    for a in assets:
        if not isinstance(d.get('currency'),str) or not d['currency'].strip() or a.get('currency')!=d['currency'] or a.get('basis')!='total-return':raise ValueError('统一币种、总收益口径和来源必填')
        urls([a.get('sourceUrl')])
        history=a.get('history')
        if not isinstance(history,list) or any(not isinstance(h,dict) or 'value' not in h for h in history):raise ValueError('历史须为含日期与数值的对象数组')
        ds=[day(h.get('date')).isoformat() for h in history]
        if ds!=sorted(set(ds)) or any(day(x)>cutoff for x in ds):raise ValueError('日期重复、乱序或超截止日')
        if dates is not None and ds!=dates:raise ValueError('日期必须完全对齐，不填充')
        dates=ds;v=[number(h['value']) for h in history]
        if any(x<=0 for x in v):raise ValueError('历史值须为正')
        values.append(v)
    if len(dates)<25:raise ValueError('至少25个观察值')
    if freq=='monthly':
        months=[dt.date.fromisoformat(x).year*12+dt.date.fromisoformat(x).month for x in dates]
        if any(b-a!=1 for a,b in zip(months,months[1:])):raise ValueError('月度样本必须逐月连续')
    prices=np.array(values,dtype=float).T
    with np.errstate(over='raise',divide='raise',invalid='raise'):
        try:r=prices[1:]/prices[:-1]-1
        except FloatingPointError as exc:raise ValueError('历史收益率数值溢出') from exc
    if not np.isfinite(r).all():raise ValueError('历史收益率非有限')
    annual=252 if freq=='daily' else 12
    with np.errstate(over='raise',invalid='raise'):
        try:mean=r.mean(axis=0)*annual;cov=np.cov(r,rowvar=False,ddof=1)*annual
        except FloatingPointError as exc:raise ValueError('历史统计数值溢出') from exc
    if not np.isfinite(mean).all() or not np.isfinite(cov).all():raise ValueError('历史统计非有限')
    return r,mean,cov,dates

def solve(cov,mean,cap,target=None):
    cov=np.asarray(cov,dtype=float);mean=np.asarray(mean,dtype=float);n=len(mean);best=None
    if mean.ndim!=1 or not 2<=n<=6 or cov.shape!=(n,n) or not np.isfinite(cov).all() or not np.isfinite(mean).all():raise ValueError('无效均值或协方差维度')
    cap=number(cap)
    if not 0<cap<=1 or n*cap<1-1e-12:raise ValueError('上限不可行')
    if not np.allclose(cov,cov.T,rtol=0,atol=1e-12) or np.linalg.eigvalsh(cov).min() < -1e-12:raise ValueError('协方差须对称半正定')
    if target is not None:number(target)
    # Enumerate box faces; solve equality-constrained quadratic on each face.
    for states in itertools.product([0,1,2],repeat=n):
        free=[i for i,s in enumerate(states) if s==1];fixed=[i for i,s in enumerate(states) if s!=1]
        w=np.array([cap if s==2 else 0.0 for s in states]);A=np.ones((1,n));b=np.array([1.0])
        if target is not None:A=np.vstack([A,mean]);b=np.array([1.0,target])
        rhs=b-A[:,fixed]@w[fixed]
        if free:
            Q=cov[np.ix_(free,free)];Af=A[:,free]
            K=np.block([[2*Q,Af.T],[Af,np.zeros((len(b),len(b)))]])
            y=np.concatenate([-2*cov[np.ix_(free,fixed)]@w[fixed],rhs])
            solution=np.linalg.lstsq(K,y,rcond=None)[0]
            if np.max(np.abs(K@solution-y))>1e-8:continue
            w[free]=solution[:len(free)]
        if np.max(np.abs(A@w-b))>1e-8 or min(w)<-1e-8 or max(w)>cap+1e-8:continue
        variance=float(w@cov@w)
        if best is None or variance<best[0]:best=(variance,w.copy())
    if best is None:raise ValueError('约束不可行或无法稳定求解')
    return {'weights':best[1].tolist(),'annualizedVolatilityPct':math.sqrt(max(best[0],0))*100,'historicalArithmeticMeanPct':float(best[1]@mean)*100}

def optimize(d):
    r,mean,cov,dates=prepare(d);cap=number(d.get('maxWeight',1));n=len(mean)
    if not 0<cap<=1 or cap*n<1-1e-12:raise ValueError('权重上限不可行')
    mvp=solve(cov,mean,cap)
    w=np.zeros(n);remaining=1.0
    for i in np.argsort(-mean):w[i]=min(cap,remaining);remaining-=w[i]
    top=float(w@mean);start=mvp['historicalArithmeticMeanPct']/100
    points=d.get('frontierPoints',15)
    if isinstance(points,bool) or not isinstance(points,int) or not 2<=points<=40:raise ValueError('前沿点数2至40')
    frontier=[solve(cov,mean,cap,float(t)) for t in np.linspace(start,top,points)]
    return {'type':'historical-portfolio-frontier','codes':[a['code'] for a in d['assets']],'sampleStart':dates[0],'sampleEnd':dates[-1],'observations':len(r),'minimumVariance':mvp,'frontier':frontier,'covariance':cov.tolist(),'limitations':['历史算术均值不是未来收益','只支持无杠杆、非负权重及统一单资产上限','未含交易成本、流动性、信用跳跃或收益估计误差','前沿为当前样本及约束下计算结果，不是交易方案；日频未核交易日历']}

def simulate(d):
    r,mean,cov,dates=prepare(d)
    if not isinstance(d.get('weights'),list):raise ValueError('模拟权重须为数组')
    weights=np.array([number(x) for x in d['weights']])
    if weights.shape!=(r.shape[1],) or min(weights)<0 or abs(sum(weights)-1)>1e-10:raise ValueError('权重非负合计1')
    paths=d.get('paths',5000);steps=d.get('steps',120);block=d.get('blockLength',6);seed=d.get('seed',42)
    for value,lo,hi in [(paths,100,10000),(steps,1,1200),(block,1,len(r)),(seed,0,2**32-1)]:
        if isinstance(value,bool) or not isinstance(value,int) or not lo<=value<=hi:raise ValueError('模拟参数越界')
    rng=np.random.default_rng(seed);wealth=np.ones(paths);peak=wealth.copy();drawdown=np.zeros(paths)
    for t in range(steps):
        if t%block==0:starts=rng.integers(0,len(r)-block+1,size=paths)
        sampled=r[starts+t%block]
        with np.errstate(over='raise',invalid='raise',under='raise'):
            try:wealth*=1+sampled@weights
            except FloatingPointError as exc:raise ValueError('模拟财富路径溢出或下溢，缩短期限或检查样本') from exc
        if not np.isfinite(wealth).all() or (wealth<=0).any():raise ValueError('模拟财富路径无效')
        peak=np.maximum(peak,wealth);drawdown=np.maximum(drawdown,1-wealth/peak)
    return {'type':'joint-block-bootstrap-simulation','method':'历史联合分块重采样蒙特卡洛','paths':paths,'steps':steps,'blockLength':block,'seed':seed,'sampleStart':dates[0],'sampleEnd':dates[-1],'terminalReturnPercentilesPct':{str(q):float(np.quantile(wealth-1,q))*100 for q in [.05,.5,.95]},'simulatedMaxDrawdownPercentilesPct':{str(q):float(np.quantile(drawdown,q))*100 for q in [.5,.95,.99]},'limitations':['模拟分位不是未来亏损上限或置信保证','历史未出现的危机不会自动生成；联合抽样保留样本内相关性，不能预见相关性跳升','区块长度和历史窗口影响结果，每观察期无成本恢复权重','不包含停牌、折价、税费、信用违约及动态状态模型；日频未核交易日历']}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['optimize','simulate']);p.add_argument('input');p.add_argument('--out',required=True);a=p.parse_args()
    if Path(a.out).exists():raise FileExistsError('不覆盖首次结果')
    blob=Path(a.input).read_bytes();d=json.loads(blob.decode('utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant);result={'optimize':optimize,'simulate':simulate}[a.mode](d)
    result['inputSha256']=hashlib.sha256(blob).hexdigest();result['input']=d
    with Path(a.out).open('x',encoding='utf8') as f:json.dump(result,f,ensure_ascii=False,indent=2,allow_nan=False)
