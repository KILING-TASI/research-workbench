"""Historical correlation and user-defined one-period shocks; no forecasts."""
import argparse, datetime, json, math, statistics
from pathlib import Path
from decimal import Decimal,ROUND_CEILING
from collection_validation import day as validated_day,unique_pairs,reject_constant

def num(x):
    if isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x): raise ValueError('数值必须有限且非布尔值')
    return x

def day(x): return validated_day(x)
def corr(a,b):
    if len(a)!=len(b):raise ValueError('相关性序列长度不一致')
    if len(a)<3: return None
    scale_a=max(abs(num(x)) for x in a);scale_b=max(abs(num(x)) for x in b)
    if not scale_a or not scale_b:return None
    a=[x/scale_a for x in a];b=[x/scale_b for x in b]
    ma,mb=statistics.mean(a),statistics.mean(b)
    sa=sum((x-ma)**2 for x in a); sb=sum((x-mb)**2 for x in b)
    return sum((x-ma)*(y-mb) for x,y in zip(a,b))/math.sqrt(sa*sb) if sa*sb>0 else None

def portfolio_path(mode, common, intervals, histories, weights, minimum):
    if mode is None:return {'status':'not-requested'}
    if mode not in ('buy-and-hold','fixed-observation-weights'):raise ValueError('历史组合模式无效')
    if len(intervals)<minimum:return {'status':'insufficient-observations','mode':mode}
    if len(intervals)!=len(common)-1 or any(a[1]!=b[0] for a,b in zip(intervals,intervals[1:])):
        return {'status':'disconnected-observations','mode':mode,'limitation':'共同收益区间不连续，不能拼接遗漏区间计算组合回撤'}
    values=[1.0]
    for a,b in intervals:
        value=(sum(w*histories[k][b]/histories[k][common[0]] for k,w in weights.items()) if mode=='buy-and-hold' else
               values[-1]*(1+sum(w*(histories[k][b]/histories[k][a]-1) for k,w in weights.items())))
        if not math.isfinite(value) or value<=0:raise ValueError('历史组合路径溢出或无效')
        values.append(value)
    peak=values[0];peak_date=common[0];drawdown=0;worst_peak=worst_trough=None
    for date,value in zip(common,values):
        if value>peak:peak=value;peak_date=date
        loss=value/peak-1
        if loss<drawdown:drawdown=loss;worst_peak=peak_date;worst_trough=date
    return {'status':'calculated-observed-path','mode':mode,'totalReturnPct':(values[-1]-1)*100,
            'maximumDrawdownPct':drawdown*100,'peakDate':worst_peak,'troughDate':worst_trough,
            'path':[{'date':date,'wealth':value} for date,value in zip(common,values)],
            'basis':'期初权重买入持有，权重随收益漂移' if mode=='buy-and-hold' else '每个观察区间保持输入权重，隐含再平衡',
            'limitations':['仅输入观测路径，不还原真实账户交易','分红复权与交易日完整性未独立核验','未计交易费用与再平衡摩擦，观察日期之间低点未知']}

def analyze(d):
    if not isinstance(d,dict):raise ValueError('组合输入须为对象')
    if not isinstance(d.get('baseCurrency'),str) or not d['baseCurrency'].strip():raise ValueError('组合本位币缺失')
    if not isinstance(d.get('holdings'),list) or any(not isinstance(r,dict) or not isinstance(r.get('code'),str) or not r['code'].strip() for r in d['holdings']):raise ValueError('持仓须为有代码的对象列表')
    for key in ('windows','scenarios'):
        if not isinstance(d.get(key,[]),list) or any(not isinstance(item,dict) or not isinstance(item.get('name'),str) or not item['name'].strip() for item in d.get(key,[])):raise ValueError(key+'须为具有名称的对象列表')
    for scenario in d.get('scenarios',[]):
        if not isinstance(scenario.get('returnShocksPct',{}),dict):raise ValueError('情景冲击须为代码与数值对象')
        if not isinstance(scenario.get('assumptions',[]),list) or any(not isinstance(x,str) or not x.strip() for x in scenario.get('assumptions',[])):raise ValueError('情景假设须为非空文字列表')
    cutoff=day(d['asOf']); currency=d['baseCurrency']; holdings=d['holdings']
    if not holdings or len({r['code'] for r in holdings})!=len(holdings): raise ValueError('持仓须非空且代码唯一')
    histories={}; values={}
    for r in holdings:
        if r['currency']!=currency: raise ValueError('须先统一市值和收益序列币种')
        v=num(r['marketValue'])
        if v<=0: raise ValueError('目前只支持正市值无杠杆持仓')
        values[r['code']]=v
        h=r.get('history',[])
        if not isinstance(h,list) or any(not isinstance(x,dict) for x in h):raise ValueError('历史须为观测对象列表')
        if h and (r.get('basis')!='total-return' or not isinstance(r.get('sourceUrl'),str) or not r['sourceUrl'].strip()): raise ValueError('历史需要总收益口径和来源')
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
    positions={k:{date:i for i,date in enumerate(sorted(histories[k]))} for k in codes}
    intervals=[(a,b) for a,b in zip(common,common[1:]) if all(positions[k][b]==positions[k][a]+1 for k in codes)]
    returns={k:[histories[k][b]/histories[k][a]-1 for a,b in intervals] for k in codes}
    def matrix(indices):
        return {a:{b:corr([returns[a][i] for i in indices],[returns[b][i] for i in indices]) for b in codes} for a in codes}
    if any(not math.isfinite(x) for rs in returns.values() for x in rs):raise ValueError('收益计算溢出')
    minobs=d.get('minimumObservations',60)
    if not isinstance(minobs,int) or isinstance(minobs,bool) or minobs<3: raise ValueError('最少观测数须为大于等于3的整数')
    def covariance(indices):
        if len(indices)<2:return None
        means={k:statistics.mean(returns[k][i] for i in indices) for k in codes}
        return {a:{b:num(sum((returns[a][i]-means[a])*(returns[b][i]-means[b]) for i in indices)/(len(indices)-1)) for b in codes} for a in codes}
    def tails(indices):
        confidence=num(d.get('tailConfidence',.95));minimum=d.get('minimumTailObservations',10)
        if not .8<=confidence<1 or isinstance(minimum,bool) or not isinstance(minimum,int) or minimum<3:raise ValueError('尾部分位及最小尾部样本无效')
        count=int((Decimal(len(indices))*(Decimal(1)-Decimal(str(confidence)))).to_integral_value(rounding=ROUND_CEILING))
        if len(indices)<minobs or count<minimum:return {'status':'insufficient-tail-sample','observations':len(indices),'tailObservations':count,'minimumTailObservations':minimum,'confidence':confidence,'worstTailMeanReturnPct':None}
        sample=sorted(sum(weights[k]*returns[k][i] for k in codes) for i in indices)
        return {'status':'empirical-observed-intervals','observations':len(indices),'tailObservations':count,'confidence':confidence,'worstTailMeanReturnPct':statistics.mean(sample[:count])*100,'cutoffReturnPct':sample[count-1]*100,'basis':'固定当前权重的观察区间收益；不是用户真实收益或未来损失概率'}
    allidx=list(range(len(intervals)))
    rolling=[];rolling_size=d.get('rollingWindowObservations');stride=d.get('rollingStride',5)
    if rolling_size is not None:
        if isinstance(rolling_size,bool) or not isinstance(rolling_size,int) or rolling_size<minobs or isinstance(stride,bool) or not isinstance(stride,int) or stride<1:raise ValueError('滚动窗口须不少于最小观测数，步长为正整数')
        if max(0,(len(intervals)-rolling_size)//stride+1)>2000:raise ValueError('滚动输出过大，请增加步长或缩短区间')
        ends=list(range(rolling_size,len(intervals)+1,stride))
        if ends and ends[-1]!=len(intervals):ends.append(len(intervals))
        for end in ends:
            idx=list(range(end-rolling_size,end))
            rolling.append({'start':intervals[idx[0]][0],'end':intervals[idx[-1]][1],'observations':rolling_size,'correlations':matrix(idx),'covariance':covariance(idx),'tail':tails(idx)})

    groups=[]
    for window in d.get('windows',[]):
        start,end=day(window['start']),day(window['end'])
        if start>end or end>cutoff: raise ValueError('窗口日期无效')
        idx=[i for i,(a,b) in enumerate(intervals) if start<=day(a) and day(b)<=end]
        groups.append({'name':window['name'],'observations':len(idx),'correlations':matrix(idx) if len(idx)>=minobs else None,'status':'已计算' if len(idx)>=minobs else '样本不足','start':window['start'],'end':window['end'],'covariance':covariance(idx) if len(idx)>=minobs else None,'tail':tails(idx)})
    scenarios=[]
    for scenario in d.get('scenarios',[]):
        shocks=scenario.get('returnShocksPct',{}); unknown=set(shocks)-set(codes)
        if unknown: raise ValueError('冲击包含未知持仓代码')
        for v in shocks.values():
            if num(v)<-100: raise ValueError('无杠杆冲击不能低于-100%')
        missing=[k for k in codes if k not in shocks]
        pnl=sum(values[k]*shocks[k]/100 for k in shocks)
        num(pnl)
        scenarios.append({'name':scenario['name'],'assumptions':scenario.get('assumptions',[]),'coveragePct':sum(weights[k] for k in shocks)*100,'missingCodes':missing,'coveredPnl':pnl,'portfolioPnl':None if missing else pnl,'portfolioReturnPct':None if missing else pnl/total*100,'maximumDrawdown':None,'note':'用户给定的一次冲击，不是价格预测；无时间路径不能计算最大回撤'})
    path=portfolio_path(d.get('historicalPortfolioMode'),common,intervals,histories,weights,minobs)
    return {'version':2,'asOf':d['asOf'],'currency':currency,'totalValue':total,'weights':weights,'historical':{'portfolioPath':path,'observations':len(intervals),'intervalStart':intervals[0][0] if intervals else None,'intervalEnd':intervals[-1][1] if intervals else None,'correlations':matrix(allidx) if len(intervals)>=minobs else None,'windows':groups,'rolling':rolling,'rollingRequested':rolling_size is not None,'covariance':covariance(allidx) if len(intervals)>=minobs else None,'tail':tails(allidx),'frequencyBasis':'各输入序列共同相邻的观察区间，未认证完整交易日；协方差未年化','note':'共同连续观测的历史皮尔逊相关，不代表未来；窗口由使用者预先定义，危机窗口少量样本不作稳定性结论'},'scenarios':scenarios,'risk':'仅客观历史及假设压力分析，不构成投资建议；可能本金亏损。未含自动行业穿透、利率久期映射、动态再平衡或蒙特卡洛。'}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('input');ap.add_argument('--out',required=True);args=ap.parse_args()
    raw=Path(args.input).read_text(encoding='utf-8-sig');result=analyze(json.loads(raw,object_pairs_hook=unique_pairs,parse_constant=reject_constant))
    import hashlib
    result['inputSha256']=hashlib.sha256(raw.encode('utf-8')).hexdigest()
    path=Path(args.out);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2,allow_nan=False)
if __name__=='__main__':main()
