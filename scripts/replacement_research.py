"""Evidence-gated ETF replacement research. Stdlib; never executes a trade."""
import argparse
import datetime as dt
import hashlib
import json
import math
from etf_evaluation import evaluate_layers,date as iso_day
from collection_validation import unique_pairs,reject_constant,finite_json_float
from pathlib import Path
from research_library import url as validate_source

def number(x):
    return isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x)

def evaluate(d):
    asof=iso_day(d['asOf']);a,b=d['current'],d['candidate']
    if a['code']==b['code']:raise ValueError('当前持仓与候选必须不同')
    if d.get('positionCurrency')!='CNY' or any(p.get('currency')!='CNY' for p in [a,b]):
        raise ValueError('当前成本入口仅支持统一人民币计价，不混加其他币种')
    amount=d['positionValue'];years=d['holdingYears']
    if not number(amount) or amount<=0 or not number(years) or years<=0:raise ValueError('金额和持有年限须为正数')
    gates=[];sources=[]
    def fact(p,key):
        evidence=p.get(key)
        if not isinstance(evidence,dict):gates.append(p['code']+' 缺少 '+key);return None
        try:
            observed=iso_day(evidence['observedAt']);available=iso_day(evidence['availableAt'])
            validate_source(evidence.get('sourceUrl'))
        except (ValueError,KeyError,TypeError):gates.append(p['code']+' '+key+' 来源或时间字段无效');return None
        if observed>available or observed>asof or available>asof or not evidence.get('sourceUrl','').startswith('https://') or not evidence.get('locator'):
            gates.append(p['code']+' '+key+' 来源/时点不完整或在未来');return None
        if evidence.get('verification') not in ['official-reviewed','third-party-observed']:
            gates.append(p['code']+' '+key+' 尚未核验');return None
        sources.append({'code':p['code'],'field':key,**evidence})
        return evidence
    identities=[fact(p,'identity') for p in [a,b]]
    comparable=all(i and i['verification']=='official-reviewed' for i in identities)
    if comparable:
        required=['indexId','indexVariant','currency','replication']
        comparable=all(a.get(k) and a[k]==b.get(k) for k in required)
    if not comparable:gates.append('尚未确认同指数版本、币种和复制方式，不能按同类替换评价')
    fees=[fact(p,'annualFeePct') for p in [a,b]]
    fv=[]
    for p,e in zip([a,b],fees):
        if not e or not number(e.get('value')) or not 0<=e['value']<=10 or e['verification']!='official-reviewed':
            gates.append(p['code']+' 年费率缺有效官方证据');fv.append(None)
        else:fv.append(e['value'])
    valid_components=all(e and isinstance(e.get('components'),list) and e['components'] and all(isinstance(k,str) and k.strip() for k in e['components']) and len(set(e['components']))==len(e['components']) for e in fees)
    if not valid_components or set(fees[0]['components'])!=set(fees[1]['components']):
        gates.append('两只ETF费用覆盖项缺失或不同，不能计算同口径节约');fv=[None,None]
    # Do not add fee savings to observed NAV performance: NAV already deducts fees.
    annual_saving=amount*(fv[0]-fv[1])/100 if all(v is not None for v in fv) else None
    quotes=[fact(p,'quote') for p in [a,b]];valid_quotes=True;execution=[]
    for p,e in zip([a,b],quotes):
        q=e.get('value',{}) if e else {}
        if not all(number(q.get(k)) and q[k]>0 for k in ['bid','ask']) or q.get('bid',1)>q.get('ask',0):
            valid_quotes=False;gates.append(p['code']+' 买卖盘无效');execution.append(None);continue
        spread=(q['ask']-q['bid'])/((q['ask']+q['bid'])/2)
        execution.append({'spreadPct':spread*100,'halfSpreadCost':amount*spread/2})
    if valid_quotes and quotes[0]['observedAt']!=quotes[1]['observedAt']:gates.append('买卖盘不在同一日期');valid_quotes=False
    if any(e and e['observedAt']!=d['asOf'] for e in quotes):gates.append('报价不是研究日可执行报价，需交易前复核')
    assumptions=d.get('costAssumptions',{});cost=None
    keys=['sellCommissionPct','buyCommissionPct','sellMinimum','buyMinimum','sellSlippageBps','buySlippageBps','otherCashCosts']
    if any(not number(assumptions.get(k)) or assumptions[k]<0 for k in keys):gates.append('替换成本假设不完整')
    elif valid_quotes:
        sell=max(amount*assumptions['sellCommissionPct']/100,assumptions['sellMinimum'])
        buy=max(amount*assumptions['buyCommissionPct']/100,assumptions['buyMinimum'])
        spread=sum(x['halfSpreadCost'] for x in execution)
        slip=amount*(assumptions['sellSlippageBps']+assumptions['buySlippageBps'])/10000
        cost={'sellCommission':sell,'buyCommission':buy,'spreadProxy':spread,'slippageAssumption':slip,'other':assumptions['otherCashCosts'],'total':sell+buy+spread+slip+assumptions['otherCashCosts']}
    tracking=[fact(p,'tracking') for p in [a,b]]
    tracking_comparable=all(e and e.get('value',{}).get('basis')=='nav-total-return-minus-index-total-return' for e in tracking)
    if tracking_comparable:
        x,y=[e['value'] for e in tracking]
        tracking_comparable=all(x.get(k)==y.get(k) and x.get(k) is not None for k in ['start','end','count','indexId']) and type(x['count']) is int and x['count']>=120
        tracking_comparable=tracking_comparable and all(number(t.get('annualTrackingDifferencePct')) and number(t.get('trackingErrorPct')) and t['trackingErrorPct']>=0 for t in [x,y])
        try:
            tracking_comparable=tracking_comparable and iso_day(x['start'])<iso_day(x['end'])<=asof and x['indexId']==a.get('indexId')
        except (KeyError,TypeError,ValueError):tracking_comparable=False
    if not tracking_comparable:gates.append('缺少同区间、同全收益基准的跟踪质量验证')
    tracking_advantage=None
    if tracking_comparable:
        tracking_advantage=tracking[1]['value']['annualTrackingDifferencePct']-tracking[0]['value']['annualTrackingDifferencePct']
        if tracking_advantage<0:gates.append('候选历史净值跟踪差更差，费率优势不能独立支持替换')
    liquidity_windows=[]
    participation=[]
    for p in [a,b]:
        premium=fact(p,'premium')
        if not premium or not number(premium.get('value')) or premium['observedAt']!=d['asOf']:gates.append(p['code']+' 缺当日匹配时点折溢价')
        liquidity=fact(p,'liquidity')
        v=liquidity.get('value',{}) if liquidity else {}
        dates=v.get('dates',[])
        try:
            window_ok=isinstance(dates,list) and len(set(dates))==len(dates)>=20 and len(dates)==v.get('count') and all(iso_day(x)<=asof for x in dates)
        except (ValueError,TypeError):window_ok=False
        if not number(v.get('averageAmount')) or v['averageAmount']<=0 or not window_ok:
            gates.append(p['code']+' 缺至少20期可核对日期的成交金额');liquidity_windows.append(None);participation.append(None)
        else:
            liquidity_windows.append(sorted(dates));participation.append(amount/v['averageAmount']*100)
    if not all(liquidity_windows) or liquidity_windows[0]!=liquidity_windows[1]:gates.append('成交金额没有相同的历史观察日期')
    breakeven=cost['total']/annual_saving if cost and annual_saving is not None and annual_saving>0 else None
    if gates:decision='暂缓判断：关键证据或时点尚未满足'
    elif annual_saving is not None and annual_saving<=0:decision='不能以降低年费为由支持替换；其他理由需独立论证'
    elif breakeven is not None and breakeven>years:decision='费率节约不足以在计划持有期内覆盖估算替换成本'
    else:decision='可进入人工复核；成本测算不是买卖指令'
    return {'type':'etf-replacement-research','version':1,'asOf':d['asOf'],'currentCode':a['code'],'candidateCode':b['code'],
        'evaluationLayers':evaluate_layers(d),
        'inputSha256':hashlib.sha256(json.dumps(d,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),
        'decision':decision,'sameExposureConfirmed':comparable,'evidenceGaps':list(dict.fromkeys(gates)),
        'annualFeeSaving':annual_saving,'holdingPeriodFeeSaving':annual_saving*years if annual_saving is not None else None,
        'switchCost':cost,'feeOnlyBreakevenYears':breakeven,'quoteComparisons':execution,'orderToAverageDailyAmountPct':participation,'trackingComparable':tracking_comparable,'historicalNetTrackingAdvantagePctPoints':tracking_advantage,'evidence':sources,
        'inputAssumptions':{'positionValue':amount,'holdingYears':years,'costAssumptions':assumptions,'purpose':d.get('purpose'),'disclosure':d.get('assumptionDisclosure')},
        'verificationBoundary':'核验状态由证据登记者提供；程序检查字段和时点，不独立证明原文真实性。年费项不是完整TER，历史跟踪优势不是未来预期。',
        'counterarguments':['同指数替换不改变主要指数风险','单日价差不能证明长期成交成本','净值跟踪差已含费用，不再叠加费用节约','历史跟踪差可能反转，不能当未来收益预测','金额模型未模拟订单深度、整手余款和执行失败'],
        'reviewConditions':['交易前重新核实买卖盘、折溢价及实际券商收费','费率、指数版本、复制方式变更后重新研究','补齐共同区间跟踪质量；独立复核来源摘录与数值','保存首次依据和实际执行成本，后续用同基准对照；不自动交易']}

def main():
    p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    if a.out.exists():raise ValueError('首次研究不覆盖，请使用新文件名')
    result=evaluate(json.loads(a.input.read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float))
    a.out.parent.mkdir(parents=True,exist_ok=True)
    with a.out.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2,allow_nan=False)
    print(json.dumps({'output':str(a.out),'decision':result['decision']},ensure_ascii=False))
if __name__=='__main__':main()
