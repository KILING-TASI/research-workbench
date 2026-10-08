"""Explicit fund-series quality, distributions, benchmarks and snapshot comparison."""
import argparse, hashlib, json, math, statistics
from urllib.parse import urlsplit
from datetime import date
from pathlib import Path
from observation_calendar import assess as assess_calendar
from collection_validation import unique_pairs,reject_constant,finite_json_float

NOTICE = '客观历史研究，不构成投资建议；本金可能亏损，历史结果不代表未来。'

def day(v):
    if not isinstance(v, str) or date.fromisoformat(v).isoformat() != v:
        raise ValueError('日期须为YYYY-MM-DD')
    return v

def num(v, positive=False):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or (positive and v <= 0):
        raise ValueError('数值无效')
    return v

def source(v):
    try:u=urlsplit(v) if isinstance(v,str) else None
    except ValueError:u=None
    if u is None or u.scheme not in ['https','http'] or not u.hostname or u.username is not None or u.password is not None:
        raise ValueError('缺来源URL')

def annualized_pct(value,years):
    num(value,True);num(years,True)
    try:result=math.expm1(math.log(value)/years)*100
    except OverflowError:return None
    return result if math.isfinite(result) else None

def history(s):
    day(s['asOf']); source(s['sourceUrl'])
    if not s.get('code') or not isinstance(s.get('history'), list) or len(s['history']) < 2:
        raise ValueError('需代码及至少两期净值')
    last = ''
    for r in s['history']:
        d = day(r['date']); num(r['nav'], True)
        if d <= last or d > s['asOf']:
            raise ValueError('净值日期重复、乱序或超过截止日')
        if r.get('accumulatedNav') is not None: num(r['accumulatedNav'], True)
        last = d
    return s['history']

def events(s, rows):
    if s.get('eventCoverage') != 'verified-complete-for-window':
        raise ValueError('分红/拆分记录未核验完整，不能假设缺失为无事件')
    es = s.get('events')
    if not isinstance(es, list): raise ValueError('需显式事件清单，已核验无事件时用空清单')
    dates = {r['date'] for r in rows}; seen = set(); by = {}
    for e in es:
        if not isinstance(e,dict):raise ValueError('事件清单须为结构化条目')
        if not any(key in e for key in ('cashPerOldUnit','newUnitsPerOldUnit')):raise ValueError('事件未给出分红或拆分数量，不默认无事件')
        d = day(e['date']); source(e['sourceUrl'])
        if d not in dates or d == rows[0]['date'] or d in seen:
            raise ValueError('事件须落在观察日及起点之后；同日现金与拆分请合并为一条事件')
        seen.add(d); cash = num(e.get('cashPerOldUnit', 0)); split = num(e.get('newUnitsPerOldUnit', 1), True)
        if cash < 0: raise ValueError('分红不能为负')
        by[d] = (cash, split)
    return by

def distributions(s):
    rows = history(s); by = events(s, rows)
    initial = rows[0]['nav']; reinvest_units = 1.0; cash_units = 1.0; balance = 0.0; out = []
    # Cash is paid per pre-event unit; reinvestment assumed at ex-date NAV.
    for r in rows:
        cash, split = by.get(r['date'], (0, 1))
        balance += cash_units * cash
        cash_units *= split
        reinvest_units *= split + cash / r['nav']
        for v in [balance,cash_units,reinvest_units]:num(v)
        out.append({'date': r['date'], 'nav': r['nav'], 'reinvestValue': reinvest_units*r['nav']/initial,
                    'cashAccountValue': (cash_units*r['nav']+balance)/initial,
                    'cashBalancePerInitialUnit': balance, 'reinvestmentUnits': reinvest_units,
                    'splitAdjustedUnits': cash_units})
        for key,value in out[-1].items():
            if key!='date':num(value)
    years = (date.fromisoformat(rows[-1]['date'])-date.fromisoformat(rows[0]['date'])).days/365.25
    def metrics(key):
        values = [r[key] for r in out]; peak=values[0]; dd=0
        for v in values: peak=max(peak,v); dd=max(dd,1-v/peak)
        total=num((values[-1]-1)*100);annual=annualized_pct(values[-1],years)
        return {'totalReturnPct': total,
                'annualizedReturnPct': annual,'annualizationGap':'短区间年度换算超出数值范围' if annual is None else None,
                'maximumDrawdownPct': dd*100}
    factor_version=hashlib.sha256(json.dumps({'history':rows,'events':s['events']},sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    return {'type':'fund-distribution-bases','code':s['code'],'asOf':s['asOf'],'sourceUrl':s['sourceUrl'],
            'series':out,'reinvest':metrics('reinvestValue'),'cashDividend':metrics('cashAccountValue'),
            'cashDividendsPerInitialUnit':balance,'cashDistributionYieldOnInitialCapitalPct':balance/initial*100,
            'events':s['events'],'factorVersion':factor_version,'defaultBasis':'reinvest', 'riskNotice':NOTICE,
            'eventCoverageVerification':'input-declared-not-independently-verified',
            'limitations':['单笔初始持有，无外部申赎；现金分红保留为无息现金，不是单位净值序列',
                            '红利再投假设除息日净值可立即再投，实际到账/再投日期可能不同',
                            '现金按事件前单位计，拆分比为新份额/旧份额；税费未计',
                            '除息日现金余额包含应收红利，不等于已到账可用资金；再投列不证明产品允许该分红方式',
                            '累计净值不是红利再投净值；分红收益率以初始本金为分母，不冒称当前股息率']}

def quality(s):
    rows=history(s); findings=[]; calendar=s.get('calendar'); completeness=None
    if calendar is not None:
        if 'applicabilityConfirmed' in calendar and not isinstance(calendar['applicabilityConfirmed'],bool):raise ValueError('日历适用性须为布尔值')
        source(calendar['sourceUrl']); ds=calendar['dates']
        if not isinstance(ds,list) or not ds or ds!=sorted(set(ds)):raise ValueError('日历须非空、唯一且有序')
        for d in ds:day(d)
        start=day(calendar['start']); end=day(calendar['end'])
        if start>end or end>s['asOf'] or any(d<start or d>end for d in ds):raise ValueError('日历区间无效')
        expected=set(ds); actual={r['date'] for r in rows if start<=r['date']<=end}
        missing=sorted(expected-actual); extra=sorted(actual-expected)
        completeness={'start':start,'end':end,'expectedObservations':len(ds),'matchedObservations':len(expected&actual),
                      'missingDates':missing,'outsideCalendarDates':extra,
                      'dateCoveragePct':len(expected&actual)/len(ds)*100,
                      'calendarApplicabilityConfirmed':calendar.get('applicabilityConfirmed') is True}
        if calendar.get('applicabilityConfirmed') is not True:completeness['dateCoveragePct']=None
    threshold=num(s.get('jumpThresholdPct',10),True); run_min=s.get('flatRunObservations',5)
    if not isinstance(run_min,int) or isinstance(run_min,bool) or run_min<2:raise ValueError('连续不变阈值至少2个观测点')
    run=1; begin=rows[0]['date']
    for a,b in zip(rows,rows[1:]):
        jump=(b['nav']/a['nav']-1)*100
        num(jump)
        if abs(jump)>=threshold:findings.append({'kind':'raw-nav-jump','date':b['date'],
            'previousDate':a['date'],'calendarDayGap':(date.fromisoformat(b['date'])-date.fromisoformat(a['date'])).days,
            'observationBasis':'相邻有效观测区间，非必然相邻自然日；不按跨度摊平收益',
            'changePct':jump,'status':'需核对分红、拆分、估值或数据错误，不直接判错'})
        if b['nav']==a['nav']:run+=1
        else:
            if run>=run_min:findings.append({'kind':'flat-run','start':begin,'end':a['date'],'observations':run,'status':'停牌、低波动或舍入均可能造成；需核实'})
            run=1;begin=b['date']
    if run>=run_min:findings.append({'kind':'flat-run','start':begin,'end':rows[-1]['date'],'observations':run,'status':'需核实，不认定异常'})
    check=None
    if s.get('eventCoverage')=='verified-complete-for-window':
        result=distributions(s); tol=num(s.get('consistencyTolerance',1e-6),True);checks=[]
        for raw,derived in zip(rows,result['series']):
            if raw.get('adjustmentFactor') is not None:
                factor=num(raw['adjustmentFactor'],True)
                checks.append({'date':raw['date'],'field':'adjustmentFactor','difference':factor-derived['reinvestmentUnits'],'consistent':abs(factor-derived['reinvestmentUnits'])<=tol})
        # Cumulative NAV is additive cash, not compound total return. Only plain non-split history has this check.
        split=any(e.get('newUnitsPerOldUnit',1)!=1 for e in s['events'])
        if not split and rows[0].get('accumulatedNav') is not None:
            offset=rows[0]['accumulatedNav']-rows[0]['nav']
            for raw,derived in zip(rows,result['series']):
                if raw.get('accumulatedNav') is not None:
                    diff=raw['accumulatedNav']-(raw['nav']+offset+derived['cashBalancePerInitialUnit'])
                    checks.append({'date':raw['date'],'field':'accumulatedNav','difference':diff,'consistent':abs(diff)<=tol})
        check={'rows':checks,'factorVersion':result['factorVersion'],'splitCumulativeNavCheck':'not-applicable' if split else 'additive-cash-with-initial-offset',
               'adjustmentFactorDefinition':'初始1份红利再投单位数；其他平台因子定义需先转换'}
    return {'type':'fund-series-quality','code':s['code'],'asOf':s['asOf'],'sourceUrl':s['sourceUrl'],
            'observations':len(rows),'dateCompleteness':completeness,'findings':findings,'distributionConsistency':check,
            'riskNotice':NOTICE,'limitations':['日期覆盖率不是综合数据质量或准确率评分；适用交易日历未核实则留空',
                '异常标记仅核查线索，不推断停牌原因；没有完整事件记录不计算复权核对',
                'adjustmentFactor仅接受本工具明示定义；需确认累计净值口径及显示精度容差']}

def benchmarks(s):
    if not isinstance(s,dict):raise ValueError('基准请求须为对象')
    if not isinstance(s.get('currency'),str) or not s['currency'].strip():raise ValueError('基准比较须明确同币种，未知币种不可视为一致')
    day(s['asOf']);freq={'daily':252,'monthly':12}.get(s.get('frequency'))
    if not freq:raise ValueError('需daily或monthly频率')
    rf=num(s.get('riskFreeAnnualPct',0))/100
    if rf<=-1:raise ValueError('无风险利率无效')
    fund=s['fund']; specs=s['benchmarks']
    if not isinstance(fund,dict) or not isinstance(specs,list) or any(not isinstance(x,dict) or not isinstance(x.get('name'),str) or not x['name'].strip() for x in specs):raise ValueError('基金与基准结构无效')
    if any(not isinstance(x.get('components'),list) or not x['components'] or any(not isinstance(a,dict) for a in x['components']) for x in specs):raise ValueError('基准须有结构化组成资产')
    if not specs or len({x['name'] for x in specs})!=len(specs):raise ValueError('基准名称须非空唯一')
    all_assets=[fund]+[a for b in specs for a in b['components']]; maps=[]
    for a in all_assets:
        source(a['sourceUrl'])
        if a.get('basis')!='total-return' or a.get('currency')!=s['currency']:raise ValueError('需同币种、总收益口径')
        if not isinstance(a.get('history'),list) or len(a['history'])<2:raise ValueError('资产须至少两期历史')
        last='';mp={}
        for r in a['history']:
            d=day(r['date']);num(r['value'],True)
            if d<=last or d>s['asOf']:raise ValueError('历史日期无效')
            last=d;mp[d]=r['value']
        maps.append(mp)
    if s.get('start') and s.get('end') and day(s['start'])>day(s['end']):raise ValueError('请求起止日期倒置')
    dates=sorted(set.intersection(*(set(m) for m in maps)))
    dates=[d for d in dates if (not s.get('start') or d>=day(s['start'])) and (not s.get('end') or d<=day(s['end']))]
    if len(dates)<4:raise ValueError('所有基准联合共同区间不足四期')
    union_dates={d for mp in maps for d in mp if dates[0]<=d<=dates[-1]}
    daily_gap=s['frequency']=='daily' and len(union_dates)>len(dates)
    calendar_check=assess_calendar(dates,dates[0],dates[-1],s.get('calendar'),s.get('calendarMarket')) if s['frequency']=='daily' else None
    if calendar_check and calendar_check['status'] in ('calendar-not-provided','date-gaps','calendar-applicability-unconfirmed','no-observation-days'):daily_gap=True
    if s['frequency']=='monthly':
        ids=[int(d[:4])*12+int(d[5:7]) for d in dates]
        if any(b-a!=1 for a,b in zip(ids,ids[1:])):raise ValueError('月频共同样本不连续')
    def returns(mp):return [num(mp[b]/mp[a]-1) for a,b in zip(dates,dates[1:])]
    fr=returns(maps[0]);out=[];pos=1;years=(date.fromisoformat(dates[-1])-date.fromisoformat(dates[0])).days/365.25
    for b in specs:
        if b.get('rebalance') not in ['each-observation','buy-and-hold']:raise ValueError('须明示基准再平衡方式')
        weights=[num(a['weight']) for a in b['components']]
        if not weights or any(w<0 for w in weights) or abs(sum(weights)-1)>1e-8:raise ValueError('基准权重非负合计1')
        ms=maps[pos:pos+len(weights)];pos+=len(weights)
        if b['rebalance']=='each-observation':
            rs=[returns(m) for m in ms];br=[sum(w*r[i] for w,r in zip(weights,rs)) for i in range(len(fr))]
        else:
            wealth=[sum(w*m[d]/m[dates[0]] for w,m in zip(weights,ms)) for d in dates]
            br=[v/u-1 for u,v in zip(wealth,wealth[1:])]
        active=[f-b for f,b in zip(fr,br)];sd=statistics.stdev(active);te=sd*math.sqrt(freq)
        rfperiod=(1+rf)**(1/freq)-1;xx=[r-rfperiod for r in br];yy=[r-rfperiod for r in fr]
        variance=statistics.variance(xx);beta=None if variance==0 else sum((x-statistics.mean(xx))*(y-statistics.mean(yy)) for x,y in zip(xx,yy))/((len(xx)-1)*variance)
        alpha=None if beta is None else (statistics.mean(yy)-beta*statistics.mean(xx))*freq*100
        ft=math.prod(1+r for r in fr);bt=math.prod(1+r for r in br)
        out.append({'name':b['name'],'rebalance':b['rebalance'],'contractBenchmarkStatus':b.get('contractBenchmarkStatus','unverified'),
                    'rebalanceCoverage': 'observed-intervals-not-verified-daily' if daily_gap and b['rebalance']=='each-observation' else 'aligned-observations',
                    'benchmarkPathLimitation': '日期缺失或适用日历未确认：按相邻已知观察点再平衡，不能认证合同要求的每日再平衡累计收益；不得将总收益标签升级为合同基准独立复算通过。' if daily_gap and b['rebalance']=='each-observation' else None,
                    'totalReturnPct':(bt-1)*100,'fundTotalReturnPct':(ft-1)*100,'excessTotalReturnPp':(ft-bt)*100,
                    'annualizedReturnPct':annualized_pct(bt,years),'annualTrackingErrorPct':None if daily_gap else te*100,
                    'informationRatio':None if daily_gap else statistics.mean(active)*freq/te if te else None,'beta':beta,'jensenAlphaAnnualizedPp':None if daily_gap else alpha,
                    'annualizedMetricGap':'共同日期或适用日历存在缺项/适用性未确认，不能将间隔收益当作每日收益' if daily_gap else None,
                    'components':[{'code':a['code'],'weight':a['weight'],'sourceUrl':a['sourceUrl']} for a in b['components']]})
        for key,value in out[-1].items():
            if isinstance(value,(int,float)) and not isinstance(value,bool):num(value)
        if out[-1]['contractBenchmarkStatus'] not in ['verified-match','verified-different','unverified']:raise ValueError('合同基准状态无效')
    return {'type':'fund-multi-benchmark','code':fund['code'],'asOf':s['asOf'],'sourceUrl':fund['sourceUrl'],
            'alignment':{'start':dates[0],'end':dates[-1],'observations':len(dates),'calendarCheck':calendar_check},'benchmarks':out,'riskNotice':NOTICE,
            'limitations':['自定义基准非合同基准；状态须由合同核验提供，不凭名称匹配','联合共同日期不插值，可能缩短区间；数据频率与交易日完整性另核',
                            'Jensen Alpha为周期超额收益线性回归截距乘年频数，不是几何超额收益或能力证明',
                            '无交易成本；基准每观察期再平衡/买入持有假设明确区分']}

def snapshot_diff(s):
    if not isinstance(s,dict) or any(not isinstance(s.get(k),dict) for k in ['before','after']):raise ValueError('需前后快照对象')
    a,b=s['before'],s['after']
    for x in [a,b]:
        codes=x.get('subjectCodes')
        if not isinstance(codes,list) or not codes or any(not isinstance(c,str) or not c.strip() for c in codes) or len(codes)!=len(set(codes)):raise ValueError('快照主体须为非空唯一文字列表')
    if a.get('subjectCodes')!=b.get('subjectCodes') or not a.get('subjectCodes'):raise ValueError('快照主体或顺序不一致')
    if day(a['asOf'])>=day(b['asOf']):raise ValueError('快照截止日须递增')
    for x in [a,b]:
        if not isinstance(x.get('metrics'),dict) or not isinstance(x.get('methodology'),dict) or not x['methodology']:raise ValueError('需指标及完整口径元数据')
        for key in ['returnBasis','frequency','window','classificationVersion']:
            if not isinstance(x['methodology'].get(key),str) or not x['methodology'][key].strip():raise ValueError('口径元数据缺少非空说明：'+key)
    changes=[{'field':k,'before':a['methodology'].get(k),'after':b['methodology'].get(k)} for k in sorted(a['methodology'].keys()|b['methodology'].keys()) if a['methodology'].get(k)!=b['methodology'].get(k)]
    rows=[]
    for k in sorted(a['metrics'].keys()|b['metrics'].keys()):
        av=a['metrics'].get(k);bv=b['metrics'].get(k)
        for v in [av,bv]:
            if v is not None:num(v)
        difference=bv-av if av is not None and bv is not None and not changes else None
        overflow=difference is not None and not math.isfinite(difference)
        rows.append({'metric':k,'before':av,'after':bv,'difference':None if overflow else difference,
                     'status':'口径变化，仅并列' if changes else '缺值不计算差异' if av is None or bv is None else '差异超出数值范围' if overflow else '数值差异，非因果归因'})
    return {'type':'fund-research-snapshot-diff','subjectCodes':a['subjectCodes'],'beforeAsOf':a['asOf'],'afterAsOf':b['asOf'],
            'methodologyChanges':changes,'metrics':rows,'sourceChanges':{'before':a.get('sources',[]),'after':b.get('sources',[])},
            'reportVersions':{'before':a.get('reportVersions',[]),'after':b.get('reportVersions',[])},'riskNotice':NOTICE,
            'limitations':['不改写原快照；输入口径元数据不能由缺失推断','同口径跨期差异也可能来自滚动样本变化，不直接认定经理能力变化']}

COMMANDS={'quality':quality,'distributions':distributions,'benchmarks':benchmarks,'snapshot-diff':snapshot_diff}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=COMMANDS);p.add_argument('input',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    spec=json.loads(a.input.read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float);result=COMMANDS[a.command](spec)
    result['inputSha256']=hashlib.sha256(a.input.read_bytes()).hexdigest();a.out.parent.mkdir(parents=True,exist_ok=True)
    payload=json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)
    with a.out.open('x',encoding='utf8') as f:f.write(payload)
