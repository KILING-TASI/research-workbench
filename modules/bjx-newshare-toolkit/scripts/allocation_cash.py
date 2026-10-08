"""Exact allocation scenarios and dated principal/settlement cash conflicts; no predictions."""
import argparse,datetime as dt,json,re
from decimal import Decimal,ROUND_FLOOR,ROUND_CEILING
from pathlib import Path
LABELS=['P75','P50','P25']
def number(value,name,minimum=Decimal(0),maximum=None):
    if isinstance(value,bool):raise ValueError(name+'不能为布尔值')
    d=Decimal(str(value))
    if not d.is_finite() or d<minimum or (maximum is not None and d>maximum):raise ValueError(name+'越界')
    return d

def calculate(spec):
    evidence={}
    if spec.get('factsStore'):
        from issuance_facts import view
        facts=view({'code':spec['code'],'asOf':spec['asOf']},Path(spec['factsStore']))
        spec=dict(spec)
        for key in ['price','maxShares','refundDate']:
            field=facts['facts'][key]
            if field is None:raise ValueError('原文事实缺失或冲突:'+key)
            if key in spec and str(spec[key])!=field['value']:
                if key=='refundDate' or Decimal(str(spec[key]))!=Decimal(field['value']):raise ValueError('输入与原文事实冲突:'+key)
            spec[key]=field['value'];evidence[key]=field
        # Final allocation rate stays an explicit scenario: never silently import actual rate.
    if not re.fullmatch(r'[0-9]{6}',spec['code']):raise ValueError('代码无效')
    price=number(spec['price'],'price',Decimal('0.00000001'));budget=number(spec['budget'],'budget')
    if budget*100!=(budget*100).to_integral_value():raise ValueError('预算最多两位小数')
    limit=number(spec['maxShares'],'maxShares',Decimal(100));minimum=number(spec.get('minShares',100),'minShares',Decimal(100))
    if limit%100 or minimum%100 or minimum>limit:raise ValueError('申购上下限须100股倍数且不倒置')
    rates=spec.get('ratesPct',{})
    if set(rates)!=set(LABELS) or not spec.get('rateBasis'):raise ValueError('需P75/P50/P25及配售率依据，不生成固定预测值')
    r={k:number(v,'ratePct',maximum=Decimal(100)) for k,v in rates.items()}
    if not r['P75']>=r['P50']>=r['P25']:raise ValueError('配售率情景顺序须P75>=P50>=P25')
    q=min((budget/(price*100)).to_integral_value(rounding=ROUND_FLOOR)*100,limit)
    if q<minimum:q=Decimal(0)
    funds=q*price
    apply=dt.date.fromisoformat(spec['applyDate']);refund=dt.date.fromisoformat(spec['refundDate']);release=dt.date.fromisoformat(spec['saleSettlementDate'])
    if not apply<refund<=release:raise ValueError('申购、退款及卖出结算日期矛盾')
    gains=spec.get('gainPct',{})
    if set(gains)!=set(LABELS):raise ValueError('每个情景需明确假设卖出涨跌幅')
    fees=spec.get('fees',{});commission=number(fees.get('commissionPct',0),'commissionPct',maximum=Decimal(100))/100
    tax=number(fees.get('taxPct',0),'taxPct',maximum=Decimal(100))/100
    slip=number(fees.get('slippagePct',0),'slippagePct',maximum=Decimal(100))/100
    if commission+tax+slip>1:raise ValueError('费用率合计不能超过100%')
    min_fee=number(fees.get('minimumCommission',0),'minimumCommission')
    opportunity=number(spec.get('opportunityRatePct',0),'opportunityRatePct',maximum=Decimal(100))/100
    financing=number(spec.get('financingRatePct',0),'financingRatePct',maximum=Decimal(100))/100
    borrowed=number(spec.get('borrowedFraction',0),'borrowedFraction',maximum=Decimal(1))
    scenarios={}
    for k in LABELS:
        rate=r[k]/100;gain=number(gains[k],'gainPct',Decimal(-100))/100
        allocated=(q*rate/100).to_integral_value(rounding=ROUND_FLOOR)*100
        retained=allocated*price;d1=Decimal((refund-apply).days);d2=Decimal((release-refund).days)
        capital_days=funds*d1+retained*d2;opp=capital_days*opportunity/365;finance=capital_days*borrowed*financing/365
        gross=retained*(1+gain);cost=(max(gross*commission,min_fee)+gross*(tax+slip)) if allocated else Decimal(0)
        net=gross-cost-finance;profit=net-retained
        threshold=(Decimal(100)/r[k]).to_integral_value(rounding=ROUND_CEILING)*100 if rate else None
        next_lot=( (allocated+100)/(100*rate)).to_integral_value(rounding=ROUND_CEILING)*100 if rate else None
        gap=max(Decimal(0),threshold*price-budget) if threshold else None
        residual=q*rate-allocated
        scenarios[k]={'ratePct':str(r[k]),'gainPctAssumption':str(gain*100),'wholeLotShares':int(allocated),
            'oddLotOutcome':'unknown-not-probability' if residual>0 else 'no-fractional-remainder',
            'possibleAdditionalSharesUpperBound':int(min(Decimal(100),q-allocated)) if residual>0 else 0,
            'hundredShareThreshold':int(threshold) if threshold else None,'thresholdFunds':str(threshold*price) if threshold else None,
            'thresholdReachable':threshold<=limit if threshold else False,'thresholdAdditionalFunds':str(gap) if gap is not None else None,
            'thresholdAdditionalSubscriptionFunds':str(max(Decimal(0),threshold*price-funds)) if threshold else None,
            'nextWholeLotAdditionalFunds':str(max(Decimal(0),next_lot*price-budget)) if next_lot and next_lot<=limit else None,
            'nextWholeLotSubscriptionShares':int(next_lot) if next_lot else None,
            'nextWholeLotThresholdFunds':str(next_lot*price) if next_lot else None,
            'nextWholeLotReachable':next_lot<=limit if next_lot else False,
            'maxProportionalWholeLotShares':int((limit*rate/100).to_integral_value(rounding=ROUND_FLOOR)*100),
            'nextWholeLotExplanation':('配售率为零，本情景无法计算下一比例整手门槛。' if next_lot is None else
                '下一比例整手需申购'+str(int(next_lot))+'股，超过申购上限'+str(int(limit))+'股；增加预算也不可达。未知零股分配另行核对。' if next_lot>limit else
                '下一比例整手需申购'+str(int(next_lot))+'股，未超过申购上限；对应申购资金'+str(next_lot*price)+'元。仅给定比例的条件测算，不保证实际获配。'),
            'refundPrincipal':str(funds-retained),'retainedPrincipal':str(retained),'capitalDays':str(capital_days),
            'segments':[{'start':str(apply),'endExclusive':str(refund),'capital':str(funds),'days':int(d1)},
                        {'start':str(refund),'endExclusive':str(release),'capital':str(retained),'days':int(d2)}],
            'grossSaleProceeds':str(gross),'saleCosts':str(cost),'financingCost':str(finance),
            'netSettlementCash':str(net),'netProfit':str(profit),'opportunityCost':str(opp),'profitAfterOpportunityCost':str(profit-opp),
            'subscriptionFundsReturnPct':str(profit/funds*100) if funds else None,
            'capitalDaySimpleAnnualizedPct':str(profit/capital_days*365*100) if capital_days else None}
    return {'type':'bjx-allocation-cash-scenarios','code':spec['code'],'subscriptionShares':int(q),'subscriptionFunds':str(funds),
        'costInputCoverage':{'assumedZeroFields':['fees.'+k for k in ['commissionPct','minimumCommission','taxPct','slippagePct'] if k not in fees]+[k for k in ['opportunityRatePct','financingRatePct','borrowedFraction'] if k not in spec], 'scope':'缺省零值仅为计算假设，不表示券商实际免收费用、无滑点或资金没有机会成本；已填值也未认证账单。'},
        'factEvidence':evidence,'currency':'CNY','unusedBudget':str(budget-funds),'atLimit':q==limit,'rateBasis':spec['rateBasis'],'scenarios':scenarios,
        'dates':{'applyDate':str(apply),'refundDate':str(refund),'saleSettlementDate':str(release)},
        'riskNotice':'仅为给定假设的计算，不保证获配或收益，不构成申购指令',
        'limitations':['排除未知零股，获配为整手比例情景而非实际结果','涨跌幅为输入假设，不预测上市表现',
          '自然日分段占用；退款与卖出结算日期由输入提供，未自动核对交易日历',
          '费用未按券商账单核验；机会成本与融资成本分列，可能存在经济口径重叠，需按资金来源解释',
          '资金日简单年化不是可持续复利收益；短占用期可能放大年化数字']}

def collision(spec):
    total=number(spec['totalFunds'],'totalFunds');requests=spec['issues']
    if not isinstance(requests,list) or not 1<=len(requests)<=50:raise ValueError('issues须1至50项')
    results=[calculate(r) for r in requests]
    if len({r['code'] for r in results})!=len(results):raise ValueError('同一股票不可重复申购')
    same_day=spec.get('sameDayReleasedFundsUsable',False)
    if type(same_day) is not bool:raise ValueError('同日可用标记须布尔值')
    rows={}
    for k in LABELS:
        ledger=[]
        for r in results:
            s=r['scenarios'][k];dates=r['dates']
            ledger += [(dates['applyDate'],'apply',r['code'],-Decimal(r['subscriptionFunds'])),
                (dates['refundDate'],'refund',r['code'],Decimal(s['refundPrincipal'])),
                (dates['saleSettlementDate'],'settlement',r['code'],Decimal(s['netSettlementCash']))]
        # Default conservative: all subscriptions on a date precede released funds.
        ledger.sort(key=lambda x:(x[0],(0 if x[1]!='apply' else 1) if same_day else (0 if x[1]=='apply' else 1),x[2]))
        cash=total;minimum=total;steps=[]
        for day,event,code,change in ledger:
            cash+=change;minimum=min(minimum,cash)
            steps.append({'date':day,'event':event,'code':code,'cashChange':str(change),'cashAfter':str(cash),'shortfall':str(max(Decimal(0),-cash))})
        rows[k]={'feasible':minimum>=0,'additionalStartingFunds':str(max(Decimal(0),-minimum)),
            'minimumCash':str(minimum),'endCash':str(cash),'ledger':steps}
    return {'type':'bjx-funding-collision','totalFunds':str(total),'sameDayReleasedFundsUsable':same_day,'scenarios':rows,'issues':results,
        'limitations':['仅检查输入方案，不自动分配资金或推荐申购','卖出结算含假设盈亏与费用，不把亏损本金全额释放',
            '同日可用需证券公司与结算时间证据；默认先申购后释放','融资成本在卖出结算统一扣除，非真实每日付息账单；零股仍未知']}

def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=['single','collision']);p.add_argument('input',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    if a.out.exists():raise ValueError('输出已存在')
    spec=json.loads(a.input.read_text(encoding='utf-8-sig'));r=calculate(spec) if a.command=='single' else collision(spec)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    with a.out.open('x',encoding='utf-8') as f:json.dump(r,f,ensure_ascii=False,indent=2,allow_nan=False)
if __name__=='__main__':main()
