"""Annual BSE scenario projection: explicit inputs, bounded thresholds, no forecasts/orders."""
import argparse,copy,datetime as dt,json,math,sys
from decimal import Decimal,ROUND_FLOOR
from pathlib import Path
from allocation_cash import number
from trading_calendar import is_open,next_open

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'scripts'))
from collection_validation import unique_pairs,reject_constant,finite_json_float
from research_brief_html import render


def access_check(spec):
    eligibility=spec.get('eligibility',{});reasons=[]
    if not isinstance(eligibility,dict):raise ValueError('权限信息须为对象')
    if eligibility.get('bsePermission') is not True:reasons.append('北交所权限未确认；由券商确认已开通后再计算客户方案')
    star=eligibility.get('starPermission') is True
    if not star:
        assets=eligibility.get('averageAssets20TradingDays');months=eligibility.get('experienceMonths')
        if assets is None or number(assets,'averageAssets20TradingDays')<500000:reasons.append('申请条件中的20交易日日均资产未达到或未确认50万元')
        if months is None or number(months,'experienceMonths')<24:reasons.append('证券交易经验未达到或未确认24个月')
    risk=eligibility.get('riskLevel');score=eligibility.get('knowledgeScore')
    if risk is None or number(risk,'riskLevel',maximum=Decimal(5))<4:reasons.append('本方案券商风险等级C4要求未达到或未确认')
    if score is None or number(score,'knowledgeScore',maximum=Decimal(100))<80:reasons.append('本方案券商知识测试80分要求未达到或未确认')
    accounts=spec.get('accounts',[])
    if not isinstance(accounts,list) or len(accounts)>50 or any(not isinstance(a,dict) or not isinstance(a.get('identityKey'),str) or not a['identityKey'].strip() for a in accounts):raise ValueError('账户需匿名投资者标识，不输入身份证原号码，最多50条声明')
    keys=[a['identityKey'].strip() for a in accounts]
    if not keys:reasons.append('尚未声明单一投资者账户，不能完成重复账户前置检查')
    if len(keys)!=len(set(keys)):reasons.append('同一投资者多账户重复申购不会提高获配，本次拦截重复输入')
    if len(set(keys))>1:reasons.append('本年度模块只研究单个投资者，不把不同主体资金合并计算')
    return {'passed':not reasons,'reasons':reasons,'basis':eligibility.get('basis','调用者声明，未核券商权限'),
            'starProcedureExemptionDeclared':star,'brokerThresholdsAreNotUniversalExchangeRules':True}


def load_calendar(year):
    path=Path(__file__).resolve().parents[1]/'assets'/f'bse-trading-calendar-{year}.json'
    if not path.is_file():raise ValueError('没有该年份内置已核交易日历，不用普通工作日或在线临时结果补造')
    calendar=json.loads(path.read_text('utf-8'))
    if calendar.get('verificationStatus')!='original-calendar-rechecked':raise ValueError('日历缺少原文核对状态')
    return calendar


def repo_days(apply,refund,calendar):
    start=dt.date.fromisoformat(apply);end=dt.date.fromisoformat(refund)
    if not start<end or (end-start).days>40:raise ValueError('代表冻结日期须递增且不超过40日')
    if not is_open(apply,calendar) or not is_open(refund,calendar):raise ValueError('申购和退款代表日期须为日历覆盖中的开市日')
    rows=[];day=start
    while day<end:
        if is_open(day.isoformat(),calendar):
            first=next_open(day.isoformat(),calendar);maturity=next_open(first,calendar)
            rows.append({'tradeDate':day.isoformat(),'firstSettlementDate':first,'maturitySettlementDate':maturity,
                         'accrualDays':(dt.date.fromisoformat(maturity)-dt.date.fromisoformat(first)).days})
        day+=dt.timedelta(days=1)
    return sum(row['accrualDays'] for row in rows),rows


def hand_distribution(amount,price,threshold,sigma_pct):
    # Threshold >= price*100 is necessary for allocation ratio <=100%; no negative normal tail.
    lower=price*100;cap=int(Decimal(str(amount))/Decimal(str(lower)))
    if cap>100000:raise ValueError('分布计算超出支持的十万手物理上限')
    if threshold<lower:raise ValueError('中心比例百股门槛低于一手发行款，对应配售率超过100%')
    sigma=threshold*sigma_pct
    if not sigma:return [(min(cap,int(Decimal(str(amount))/Decimal(str(threshold)))),1.0)]
    cdf=lambda z:.5*math.erfc(-z/math.sqrt(2))
    floor_cdf=cdf((lower-threshold)/sigma);normalizer=1-floor_cdf
    def bounded(x):
        if x<lower:return 0.0
        return min(1.0,max(0.0,(cdf((x-threshold)/sigma)-floor_cdf)/normalizer))
    tail=[bounded(amount/k) for k in range(1,cap+1)]
    probabilities=[(0,1-(tail[0] if tail else 0))]
    probabilities += [(k,max(0.0,tail[k-1]-(tail[k] if k<cap else 0))) for k in range(1,cap+1)]
    if abs(sum(p for _,p in probabilities)-1)>1e-9:raise ValueError('手数分布概率质量不守恒')
    return probabilities


def single(amount,scenario,fees,cost_rate,cost_days,post_cost_days=0):
    price=float(scenario['p0']);threshold=float(scenario['a_star']);sigma=float(scenario['sigma_pct']);gain=float(scenario['r'])
    probabilities=hand_distribution(amount,price,threshold,sigma)
    expected_hands=sum(k*p for k,p in probabilities);gross=expected_hands*100*price*gain
    second_moment=sum(k*k*p for k,p in probabilities)
    hand_sd=math.sqrt(max(0.0,second_moment-expected_hands**2))
    sale_cost=0.0
    for k,p in probabilities:
        proceeds=k*100*price*(1+gain)
        if k and proceeds>0:
            sale_cost+=p*(max(proceeds*fees['comm_rate'],fees['comm_min'])+proceeds*(fees['stamp']+fees['transfer']+fees['slippage']))
    fund_cost=(amount*cost_days+expected_hands*100*price*post_cost_days)*cost_rate/365
    return {'subscriptionAmount':amount,'expectedHands':expected_hands,'expectedShares':expected_hands*100,
            'handsStandardDeviation':hand_sd,'handsSecondMoment':second_moment,
            'zeroProportionalHandsProbability':sum(p for k,p in probabilities if k==0),
            'thresholdDistribution':'normal-truncated-at-one-lot-cost; caller-assumption-not-fitted',
            'grossProfit':gross,'sellCost':sale_cost,'fundCost':fund_cost,'netProfit':gross-sale_cost-fund_cost,
            'modelProportionalHundredShareProbability':sum(p for k,p in probabilities if k>=1),
            'allocationScope':'proportional-only; unknown-fragments-excluded'}


def candidate_z(market,fees,cost_rate,cost_days):
    sigma=market['a_star']*market['sigma_pct'];unit_cost=cost_rate*cost_days/365
    proceeds=100*market['p0']*(1+market['r'])
    gain=100*market['p0']*market['r']-(max(proceeds*fees['comm_rate'],fees['comm_min'])+proceeds*(fees['stamp']+fees['transfer']+fees['slippage']))
    if sigma<=0 or unit_cost<=0 or gain<=0:return None
    lower=(100*market['p0']-market['a_star'])/sigma;floor=.5*math.erfc(-lower/math.sqrt(2));target=gain/(sigma*unit_cost)
    def ratio(z):return (.5*math.erfc(-z/math.sqrt(2))-floor)/(math.exp(-z*z/2)/math.sqrt(2*math.pi))
    low=max(-12,lower);high=12
    if ratio(high)<target:return None
    for _ in range(80):
        mid=(low+high)/2
        if ratio(mid)<target:low=mid
        else:high=mid
    return (low+high)/2


def market_scenario(row):
    if not isinstance(row,dict) or not isinstance(row.get('basis'),str) or not row['basis'].strip():raise ValueError('每档市场参数须有明确假设依据')
    result=copy.deepcopy(row)
    price=number(row['p0'],'p0',Decimal('.000001')) if row.get('p0') is not None else None
    threshold=number(row['a_star'],'a_star',Decimal('.000001')) if row.get('a_star') is not None else None
    rate=number(row['allocationRatio'],'allocationRatio',Decimal('.000000000001'),Decimal(1)) if row.get('allocationRatio') is not None else None
    if sum(value is not None for value in (price,threshold,rate))<2:raise ValueError('发行价、门槛、配售率至少给两个，派生第三个')
    if price is None:price=threshold*rate/100
    derived=price*100/rate if rate is not None else threshold
    if threshold is not None and rate is not None and abs(threshold-derived)>max(Decimal('.01'),derived*Decimal('0.00000001')):raise ValueError('发行价、中心百股门槛与配售率不自洽，拒绝拼用不同样本均值')
    result.update(p0=float(price),a_star=float(derived),allocationRatio=float(price*100/derived),
                  a_max=float(number(row['a_max'],'a_max')),r=float(number(row['r'],'r',Decimal(-1))),
                  sigma_pct=float(number(row['sigma_pct'],'sigma_pct',maximum=Decimal(1))))
    count=row.get('n_per_year')
    if isinstance(count,bool) or not isinstance(count,int) or not 1<=count<=366:raise ValueError('年参与只数须为1至366明确整数，不自动预测')
    result['n_per_year']=count
    return result


def comparisons(spec,neutral_rate):
    rows=spec.get('alternatives',[])
    if not isinstance(rows,list) or len(rows)>10:raise ValueError('资产对照最多10项')
    output=[];seen=set()
    for row in rows:
        if not isinstance(row,dict) or not isinstance(row.get('name'),str) or not row['name'].strip() or row['name'] in seen:raise ValueError('对照名称须非空且唯一')
        seen.add(row['name'])
        if not isinstance(row.get('basis'),str) or not row['basis'].strip():raise ValueError('对照数据必须有依据，缺收益不填零')
        rate=float(number(row['annualRate'],'annualRate',Decimal(-1))) if row.get('annualRate') is not None else None
        output.append({**row,'annualRate':rate,'neutralDifference':neutral_rate-rate if rate is not None else None,
                       'interpretation':'仅比较所给收益口径，风险和流动性不等价，不形成优选或低风险保证'})
    return output


def regime_checks(spec,neutral_rate):
    cutoff=dt.date.fromisoformat(spec['asOf']);checks=[]
    recent=spec.get('recentListings',[])
    if not isinstance(recent,list) or len(recent)>100:raise ValueError('近期上市观察须为最多100项')
    dated=[];seen=set();excluded=[]
    for row in recent:
        if not isinstance(row,dict):raise ValueError('上市表现观察须为对象')
        key=row.get('code')
        if not isinstance(key,str) or not key or key in seen:raise ValueError('上市样本代码缺失或重复')
        seen.add(key)
        if row.get('listingDate') is None or row.get('firstDayReturn') is None or not isinstance(row.get('source'),str) or not row['source'].strip():
            excluded.append({'code':key,'reason':'上市日期、表现或来源缺失，不计入市场观察'});continue
        day=dt.date.fromisoformat(row['listingDate'])
        if day>cutoff:excluded.append({'code':key,'reason':'上市日期超过研究截止日'});continue
        dated.append((day,float(number(row['firstDayReturn'],'firstDayReturn',Decimal(-1)))))
    dated.sort();tail=dated[-5:]
    ratio=sum(value<0 for _,value in tail)/5 if len(tail)==5 and spec.get('recentListingsComplete') is True and not excluded else None
    checks.append({'name':'所给连续五只样本破发占比','triggered':ratio>.3 if ratio is not None else None,'value':ratio})
    benchmark=spec.get('cashBenchmark')
    if benchmark is not None:
        if not isinstance(benchmark,dict) or not isinstance(benchmark.get('basis'),str) or not benchmark['basis'].strip():raise ValueError('现金对照须有依据')
        rate=float(number(benchmark['annualRate'],'cashBenchmark',Decimal(-1)))
    else:rate=None
    checks.append({'name':'中性累计收益低于所给现金对照','triggered':neutral_rate<rate if rate is not None else None,'value':neutral_rate-rate if rate is not None else None})
    rates=spec.get('rateComparison');decline=None
    if rates is not None:
        if not isinstance(rates,dict) or not isinstance(rates.get('source'),str) or not rates['source'].strip():raise ValueError('配售率变化缺依据')
        first=dt.date.fromisoformat(rates['baselineDate']);last=dt.date.fromisoformat(rates['currentDate'])
        if not first<last<=cutoff or not 75<=(last-first).days<=105:raise ValueError('配售率参照需约三个月且不超截止日')
        before=number(rates['baselineRatio'],'baselineRatio',Decimal('.000000000001'),Decimal(1));after=number(rates['currentRatio'],'currentRatio',maximum=Decimal(1))
        decline=float(1-after/before)
    checks.append({'name':'所给配售率较约三个月前下降超过50%','triggered':decline>.5 if decline is not None else None,'value':decline})
    return {'checks':checks,'excludedObservations':excluded,'status':'reassess-under-declared-thresholds' if any(row['triggered'] is True for row in checks) else 'insufficient-observations' if any(row['triggered'] is None for row in checks) else 'no-declared-threshold-trigger',
            'restartObservations':['跟踪新增真实破发样本及配售率，不能仅看五只的小样本','重新核对费用、参与范围与同期现金对照','用事前留存参数复查收益假设，触发解除不等于交易安全'],
            'limitations':'只检查输入样本和模型阈值，不认证全市场状态或提供交易执行'}


def evaluate(spec):
    gate=access_check(spec)
    if not gate['passed']:return {'type':'bjx-annual-yield','status':'blocked-eligibility','access':gate,'scenarios':None}
    capital=float(number(spec['s_capital'],'s_capital',Decimal('.01')));transit=float(number(spec.get('s_in_transit',0),'s_in_transit'))
    if transit>capital:raise ValueError('在途资金超过账户预算，不能假定融资补足')
    available=capital-transit
    cost_rate=float(number(spec['c_annual'],'c_annual',maximum=Decimal(1)))
    alternative=spec.get('cash_alternative','repo_timing')
    if alternative not in ('repo_timing','idle'):raise ValueError('资金替代用途不支持')
    apply=spec['representativeApplyDate'];refund=spec['representativeRefundDate']
    calendar=load_calendar(dt.date.fromisoformat(apply).year)
    effective,repo_rows=repo_days(apply,refund,calendar)
    if alternative=='repo_timing' and spec.get('repoDailyReuseDeclared') is not True:raise ValueError('逆回购对照须声明次日资金可用的每日滚动假设，不由日历认证券商可用时间')
    days=effective if alternative=='repo_timing' else (dt.date.fromisoformat(refund)-dt.date.fromisoformat(apply)).days
    post_days=0;post_rows=[];sale=spec.get('representativeSaleAvailableDate')
    if sale is not None:
        if dt.date.fromisoformat(sale)<dt.date.fromisoformat(refund):raise ValueError('卖出结算不得早于退款可用日')
        if sale!=refund:
            accrued,post_rows=repo_days(refund,sale,calendar)
            post_days=accrued if alternative=='repo_timing' else (dt.date.fromisoformat(sale)-dt.date.fromisoformat(refund)).days
    supplied=spec.get('fees',{})
    fees={key:float(number(supplied[key],key,maximum=Decimal(1) if key!='comm_min' else None)) for key in ('stamp','comm_rate','comm_min','transfer','slippage')}
    if sum(fees[key] for key in ('stamp','comm_rate','transfer','slippage'))>1:raise ValueError('比例费用合计不能超过成交金额')
    sensitivity_returns=spec.get('sensitivityReturns',[0.0,0.5,1.0])
    if not isinstance(sensitivity_returns,list) or not 1<=len(sensitivity_returns)<=20:raise ValueError('收益敏感性需要1至20个明确涨幅')
    scenarios=spec.get('scenarios')
    if not isinstance(scenarios,dict) or set(scenarios)!=set(('pessimistic','neutral','optimistic')):raise ValueError('需要三档明确参数，不内置未经验证的市场默认预测')
    output={}
    for label,row in scenarios.items():
        market=market_scenario(row);lot=market['p0']*100
        cap=float((Decimal(str(min(available,market['a_max'])))/Decimal(str(lot))).to_integral_value(rounding=ROUND_FLOOR)*Decimal(str(lot)))
        base=single(cap,market,fees,cost_rate,days,post_days)
        candidates={0.0,cap}
        # Evaluate finite declared/model breakpoints; never claim global optimum or a fixed 2.2-sigma rule.
        z=candidate_z(market,fees,cost_rate,days)
        levels=[market['a_star']]
        if z is not None:levels.append(max(lot,market['a_star']*(1+z*market['sigma_pct'])))
        for k in range(1,min(30,math.ceil(cap/market['a_star'])+1)):
            for level in levels:
                candidate=float((Decimal(str(k*level))/Decimal(str(lot))).to_integral_value(rounding='ROUND_CEILING')*Decimal(str(lot)))
                if candidate<=cap:candidates.add(candidate)
        evaluated=[single(amount,market,fees,cost_rate,days,post_days) for amount in sorted(candidates)]
        best=max(evaluated,key=lambda item:(item['netProfit'],-item['subscriptionAmount']))
        sensitivity=[]
        for gain in sensitivity_returns:
            changed={**market,'r':float(number(gain,'sensitivityReturn',Decimal(-1)))}
            value=single(cap,changed,fees,cost_rate,days,post_days)
            sensitivity.append({'returnAssumption':changed['r'],'annualNet':value['netProfit']*market['n_per_year'],'annualCumulativeRate':value['netProfit']*market['n_per_year']/capital})
        annual=base['netProfit']*market['n_per_year']
        output[label]={'market':market,'atAvailableCap':base,'annualNet':annual,'annualCumulativeRate':annual/capital,
                       'candidateComparison':evaluated,'bestAmongEnumeratedCandidates':best,'sensitivity':sensitivity,
                       'candidateZProxy':z,'candidateRule':'one-lot-rounded centre and model loss-equation proxy breakpoints plus zero/cap; argmax over this set only, no global or allocation guarantee'}
    alternatives=comparisons(spec,output['neutral']['annualCumulativeRate'])
    regime=regime_checks(spec,output['neutral']['annualCumulativeRate'])
    data_status=spec.get('dataStatus',{'offeringFacts':'manual-assumptions','allocationResults':'scenario-not-backfilled'})
    if not isinstance(data_status,dict) or any(value not in ('manual-assumptions','declared-original-unverified','scenario-not-backfilled','missing') for value in data_status.values()):raise ValueError('数据状态须区分人工假设、输入声称原文、未回填情景或缺失')
    return {'type':'bjx-annual-yield','status':'calculated-scenarios-not-forecast','access':gate,'capital':capital,'availableCapital':available,
            'scenarios':output,'annualCumulativeRange':[min(row['annualCumulativeRate'] for row in output.values()),max(row['annualCumulativeRate'] for row in output.values())],
            'cashAlternative':alternative,'effectiveCostDays':days,'repoAccrualRows':repo_rows,'calendarSource':calendar['sourceUrl'],
            'postRefundCostDays':post_days,'postRefundRepoRows':post_rows,'postRefundCostIncluded':sale is not None,
            'fees':fees,'costAnnualRate':cost_rate,'exampleType':spec.get('exampleType'),
            'alternatives':alternatives,'regimeChecks':regime,'dataStatus':data_status,
            'limitations':['年度聚合按声明参与次数重复代表冻结窗口，不是实际年度排程或可全额参与证明',
                           '仅比例获配，未知余股未纳入；分布为物理下界截断的正态假设，不是已校准真实分布',
                           '候选最优只限枚举集，不证明资金充分时顶格总是最优；不是申购金额指令',
                           '回购对照假设每日资金次日可用，交易日历不认证结算与券商到账',
                           '没有把涨跌幅、参与只数和费率默认值称实际预测；不恢复E1–E5模型或卖出引擎',
                           '年度累计情景不是持续复利年化，不构成收益承诺或投资建议']}


def markdown(result):
    if result['status']=='blocked-eligibility':return ('# 北交所年度收益情景\n\n> 权限或账户条件尚未确认，本次没有计算年度收益。先补齐以下声明，再沿用市场参数重算。\n\n## 需要确认什么\n\n'+'\n'.join('- '+reason for reason in result['access']['reasons'])+'\n\n## 接下来怎样继续\n\n请用自然语言确认缺少的条件，由AI更新研究输入；不需要填写完整JSON。不收身份证号码，使用匿名投资者标识。权限由券商确认，本工具只检查声明，不能代办或认证开户。\n\n资料确认后另存新报告，保留本次未计算记录。不能通过提高模拟本金代替历史日均资产证明，也不能用多个账户增加获配。\n\n## 计算前仍需核对\n\n发行价、配售与卖出涨幅假设、年度参与只数、费用、退款和卖出资金可用日期均须有明确口径。当前内置2026交易日历，其他年份不能猜日期。\n\n未计算时不提供收益区间或敏感性数字，不把空值填成零。本报告不构成投资建议或账户权限认证。')
    low,high=result['annualCumulativeRange']
    lines=['# 北交所年度收益情景','',f'> 在本次声明参数下，按可用资金上限试算的年度累计收益率为{low*100:.2f}%至{high*100:.2f}%；这不是实际年度回测或承诺年化。','',
           f"账户预算{result['capital']:,.2f}元，可用资金{result['availableCapital']:,.2f}元；替代用途{ {'repo_timing':'通用回购（逆回购方向）','idle':'闲置现金'}[result['cashAlternative']] }，代表窗口计息/成本天数{result['effectiveCostDays']}天。",'',
           '|情景|模拟申购额|期望比例手数|毛收益/只|卖出成本/只|资金成本/只|净收益/只|年累计净收益|年累计收益率|', '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    labels={'pessimistic':'悲观参数','neutral':'中性参数','optimistic':'乐观参数'}
    if result.get('exampleType')=='teaching-only':lines[4:4]=['**设计参数教学情景，不是真实市场预测或你的账户认证。**','']
    neutral=result['scenarios']['neutral']
    used=neutral['atAvailableCap']['subscriptionAmount']
    opening=f"中性参数下，年累计净收益{neutral['annualNet']:,.2f}元、收益率{neutral['annualCumulativeRate']*100:.2f}%；单次模拟使用{used:,.2f}元，可用但未进入申购的资金{result['availableCapital']-used:,.2f}元。"
    opening+='当前只能回答这些假设下的打新净收益，尚不能证明这笔资金全年放在打新更合适。'
    lines[4:4]=[opening,'']
    lines[4:4]=['权限与账户按原输入声明检查，不是券商认证；本次模拟本金不代表过去20个交易日日均资产。','']
    for name in ('pessimistic','neutral','optimistic'):
        row=result['scenarios'][name];base=row['atAvailableCap']
        lines.append(f"|{labels[name]}|{base['subscriptionAmount']:,.2f}|{base['expectedHands']:.3f}|{base['grossProfit']:.2f}|{base['sellCost']:.2f}|{base['fundCost']:.2f}|{base['netProfit']:.2f}|{row['annualNet']:.2f}|{row['annualCumulativeRate']*100:.2f}%|")
    lines+=['','## 假设与收益敏感性']
    lines+=['','## 拿不到比例整手的风险','期望手数不是实际到账。下表只计算比例配售整手，不包含未知余股；零手概率不等于实际零获配概率。','',
            '|情景|期望手数|手数标准差|比例整手为零的概率|','|---|---:|---:|---:|']
    for name in ('pessimistic','neutral','optimistic'):
        base=result['scenarios'][name]['atAvailableCap']
        lines.append(f"|{labels[name]}|{base['expectedHands']:.3f}|{base['handsStandardDeviation']:.3f}|{base['zeroProportionalHandsProbability']*100:.2f}%|")
    lines+=['','这些概率来自输入假设的截断正态门槛分布，尚未经历史选型或样本外校准；不能作为个人获配承诺。']
    for name,row in result['scenarios'].items():
        market=row['market'];best=row['bestAmongEnumeratedCandidates']
        lines += ['',labels[name]+f"：发行价{market['p0']:.2f}元，中心比例百股资金{market['a_star']:,.2f}元，中心配售率{market['allocationRatio']*100:.5f}%，卖出涨幅{market['r']*100:.1f}%，门槛相对标准差{market['sigma_pct']*100:.1f}%，年参与{market['n_per_year']}只。",'依据：'+market['basis'],
                  f"枚举候选中的较高净收益金额为{best['subscriptionAmount']:,.2f}元；仅供模型对照，不是推荐申购额。"]
        for value in row['sensitivity']:lines.append(f"- 若卖出涨幅为{value['returnAssumption']*100:.1f}%，其他参数不变，年累计净收益{value['annualNet']:.2f}元、收益率{value['annualCumulativeRate']*100:.2f}%。")
    fees=result['fees']
    lines+=['','## 口径与风险',f"资金成本年率假设{result['costAnnualRate']*100:.2f}%；卖出印花税{fees['stamp']*100:.4f}%、佣金{fees['comm_rate']*100:.4f}%（最低{fees['comm_min']:.2f}元）、过户费{fees['transfer']*100:.4f}%、滑点{fees['slippage']*100:.4f}%。这些是输入假设，不认证当前账单。",
            '退款后获配本金继续占用已按额外'+str(result['postRefundCostDays'])+'个替代成本日计入。' if result['postRefundCostIncluded'] else '没有提供卖出结算日期，本次尚未计退款后获配本金继续占用成本，净收益可能高估。',
            '最低佣金按每种获配手数下比例佣金与最低值取大，再按概率加权；不在比例佣金之外再次叠加最低佣金。','资金成本为声明替代用途的机会成本，不替代实际融资或费用账单。与券商收益数字比较须对齐分母、参与范围、取整、费用和资金日；不存在通用40%–60%折减比例。',
            '[内置交易日历依据]('+result['calendarSource']+')','不构成投资建议；结果为未校准市场参数与概率分布下的情景测算。']+['- '+text for text in result['limitations']]
    lines+=['','## 这笔资金与其他用途怎样比较','收益数字只能比较输入口径，不能把波动与流动性不同的资产当等价现金管理。']
    for row in result['alternatives']:
        rate=f"{row['annualRate']*100:.2f}%" if row['annualRate'] is not None else '未提供，不填零'
        lines.append('- '+row['name']+'：声明年收益口径 '+rate+'；依据 '+row['basis']+'；风险 '+str(row.get('riskNote','待补'))+'；流动性 '+str(row.get('liquidityNote','待补')))
        if row['neutralDifference'] is not None:
            lines.append(f"  中性打新净收益率比所给该用途年收益率{'高' if row['neutralDifference']>=0 else '低'}{abs(row['neutralDifference'])*100:.2f}个百分点。打新已扣冻结期间机会成本，而对照是所给全年收益；此差额只作口径对照，不是组合增量收益或已证明的优劣。")
    lines.append('要判断全年资金用途，还需核对实际参与窗口、未申购期间资金收益、同一费用口径与承受破发的能力；本次没有把未用资金收益补入。')
    lines.append('不固化“1000万元以上优于逆回购”或“打新低波动”的结论；需要依真实参与、余股、破发与资金占用资料重新判断。')
    lines+=['','## 阶段性重新评估提示']
    regime=result['regimeChecks']
    if regime['status']=='reassess-under-declared-thresholds':lines.append('所给样本或中性参数触发了阶段性暂停建议；按这些假设应暂停该方案的采用并复查策略适用性，不能把模型提示当作账户交易指令。')
    elif regime['status']=='insufficient-observations':lines.append('部分市场观察缺失，不能据此判断策略正常或适合继续参与。')
    else:lines.append('所给观察未触发预设条件，不等于已证明策略安全或未来有效。')
    for check in regime['checks']:lines.append('- '+check['name']+'：'+('触发' if check['triggered'] is True else '未触发' if check['triggered'] is False else '资料不足，未判断'))
    lines+=['后续观察：']+['- '+text for text in regime['restartObservations']]
    lines+=['','## 数据取得与降级']
    states={'manual-assumptions':'手工参数/假设，未自动原文核验','declared-original-unverified':'输入声称来自原文，本入口未独立认证','scenario-not-backfilled':'使用声明情景，实际结果未回填','missing':'缺失，不能当零'}
    labels={'offeringFacts':'发行要素','allocationResults':'发行配售结果'}
    for key,value in result['dataStatus'].items():lines.append('- '+labels.get(key,key)+'：'+states[value])
    for row in regime['excludedObservations']:lines.append('- '+row['code']+'：'+row['reason'])
    return '\n'.join(lines)


def publish(spec,out):
    out=Path(out)
    if out.exists():raise FileExistsError('报告目录已存在')
    result=evaluate(spec);body=markdown(result);out.mkdir(parents=True)
    files={'input.json':json.dumps(spec,ensure_ascii=False,indent=2,allow_nan=False),'result.json':json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),
           '北交所年度收益情景.md':body,'北交所年度收益情景.html':render(body,'北交所年度收益情景')}
    for name,text in files.items():(out/name).write_text(text,'utf-8')
    (out/'report-manifest.json').write_text(json.dumps({'files':{name:None for name in files},'primaryReport':'北交所年度收益情景.html','savedAt':dt.datetime.now(dt.timezone.utc).isoformat(),'followup':'bjx-annual'},ensure_ascii=False,indent=2),'utf-8')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('input',type=Path);parser.add_argument('--out-dir',required=True)
    parser.add_argument('--capital',help='明确人民币元资金规模，其他输入沿用，不改市场假设');args=parser.parse_args()
    spec=json.loads(args.input.read_text('utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float)
    if args.capital is not None:spec['s_capital']=str(number(args.capital,'s_capital',Decimal('.01')))
    publish(spec,args.out_dir)
