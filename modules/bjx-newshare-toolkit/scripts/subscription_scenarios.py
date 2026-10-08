"""Declared joint BSE scenarios; no forecast fitting, fractional-rank prediction or orders."""
import argparse,copy,json,sys
from decimal import Decimal
from pathlib import Path
from allocation_cash import calculate,number,LABELS

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'scripts'))
from collection_validation import unique_pairs,reject_constant,finite_json_float
from research_brief_html import render


def evaluate(spec):
    if not isinstance(spec,dict) or not isinstance(spec.get('allocation'),dict):raise ValueError('需要发行事实与明确资金/日期输入')
    if spec['allocation'].get('additionalSharesAssumptions'):raise ValueError('联合情景以比例部分为基线；余股由条件分支单列，不混入基线')
    declared=spec.get('scenarios')
    if not isinstance(declared,list) or not 1<=len(declared)<=50:raise ValueError('需要1至50个明确联合情景')
    seen=set();rows=[];overview=None
    weighted=any('probability' in row for row in declared if isinstance(row,dict))
    if weighted and (not isinstance(spec.get('probabilityBasis'),str) or not spec['probabilityBasis'].strip()):
        raise ValueError('情景权重需要明确依据，不能把三档情景默认当概率')
    for row in declared:
        if not isinstance(row,dict) or not isinstance(row.get('id'),str) or not row['id'].strip() or row['id'] in seen:raise ValueError('情景名称须非空且唯一')
        seen.add(row['id'])
        for key in ('rateBasis','gainBasis'):
            if not isinstance(row.get(key),str) or not row[key].strip():raise ValueError('每个情景需配售率和卖出涨跌幅依据')
        allocation=copy.deepcopy(spec['allocation'])
        allocation['ratesPct']={label:row['ratePct'] for label in LABELS}
        allocation['gainPct']={label:row['gainPct'] for label in LABELS}
        allocation['rateBasis']=row['rateBasis']
        result=calculate(allocation)
        overview={'price':result['price'],'maxShares':result['maxShares'],'dates':result['dates'],'factEvidence':result['factEvidence']}
        selected=result['scenarios']['P50']
        fragment_branch=None
        if selected['possibleAdditionalSharesUpperBound']==100:
            assumed=copy.deepcopy(allocation);assumed['additionalSharesAssumptions']={label:100 for label in LABELS}
            fragment_branch=calculate(assumed)['scenarios']['P50']
        if weighted and 'probability' not in row:raise ValueError('有权重时每个情景都须填写，不把缺值补零')
        probability=number(row['probability'],'probability',maximum=Decimal(1)) if weighted else None
        rows.append({'id':row['id'],'weight':str(probability) if weighted else None,'rateBasis':row['rateBasis'],
                     'gainBasis':row['gainBasis'],'subscriptionFunds':result['subscriptionFunds'],'unusedBudget':result['unusedBudget'],
                     'declaredBudget':str(spec['allocation']['budget']),'additionalHundredShareBranch':fragment_branch,**selected})
    if weighted and sum((Decimal(row['weight']) for row in rows),Decimal(0))!=1:raise ValueError('情景权重须精确合计1')
    profits=[Decimal(row['profitAfterOpportunityCost']) for row in rows]
    summary={'allocationScope':'proportional-whole-lots-only-unknown-fragments-excluded',
             'minimumDeclaredNetProfit':str(min(profits)),'maximumDeclaredNetProfit':str(max(profits)),
             'weightedNetProfit':None,'proportionalHundredShareScenarioWeight':None}
    if weighted:
        summary['weightedNetProfit']=str(sum((Decimal(row['weight'])*Decimal(row['profitAfterOpportunityCost']) for row in rows),Decimal(0)))
        summary['proportionalHundredShareScenarioWeight']=str(sum((Decimal(row['weight']) for row in rows if row['wholeLotShares']>=100),Decimal(0)))
    return {'type':'bjx-declared-joint-scenarios','code':spec['allocation']['code'],'rows':rows,'summary':summary,
            'allocationOverview':overview,
            'exampleType':spec.get('exampleType'),
            'probabilityBasis':spec.get('probabilityBasis') if weighted else None,
            'mode':'input-assumptions-not-forecast-or-subscription-advice',
            'limitations':['比例整手之外的余股排序未知；低于比例百股门槛不自动写成零获配',
                           '权重覆盖仅在声明情景下成立，不是实际获配概率；未输入权重不计算期望收益',
                           '配售率与涨跌幅成对声明，不假定相互独立；同日不同新股相关性未估计',
                           '资金占用使用输入可用日期的半开自然日区间，不默认T+2到账或固定3天',
                           '未获配仍可能产生机会/融资成本；卖出费用按输入假设，未核券商结算',
                           '不求推荐申购额、报童最优、首日卖点或按年发行只数外推收益']}


def markdown(result):
    rows=result['rows'];summary=result['summary']
    if all(row['wholeLotShares']==0 for row in rows):
        lead='本次各情景均未跨过比例配售百股门槛；余股是否获配仍未知，资金占用成本也不会因此消失。'
    elif all(Decimal(row['profitAfterOpportunityCost'])<=0 for row in rows):
        lead='本次各情景扣除卖出费用、融资及机会成本后均未得到正收益；获配并不等于有利可图。'
    else:
        lead='本次收益取决于配售率与卖出价格的共同假设；先看资金能否跨过比例整手阶梯，再看费用和破发情景的代价。'
    body=['# 北交所资金与收益情景','', '> '+lead,'','标的代码：'+result['code']+'。本报告计算输入假设，不预测发行结果或提供申购指令。','',
          '|情景|申购资金（元）|比例整手股数|扣除机会成本后净收益（元）|余股状态|','|---|---:|---:|---:|---|']
    if result.get('exampleType')=='teaching-only':body[4:4]=['**教学输入，不是真实新股或你的账户。**','']
    overview=result.get('allocationOverview')
    if overview:
        body[6:6]=['发行价'+overview['price']+'元/股，申购上限'+str(overview['maxShares'])+'股；参数来自本次输入，有原文事实库时在结果中保留匹配记录，没有事实库不视为核验通过。',
                    '申购日'+overview['dates']['applyDate']+'；退款可用日'+overview['dates']['refundDate']+'；卖出结算日'+overview['dates']['saleSettlementDate']+'。可用日期不自动认证券商到账。','']
    clean=lambda text:str(text).replace('|','／').replace('\n',' ').replace('\r',' ')
    for row in rows:
        body.append('|'+clean(row['id'])+'|'+row['subscriptionFunds']+'|'+str(row['wholeLotShares'])+'|'+str(Decimal(row['profitAfterOpportunityCost']).quantize(Decimal('.01')))+'|'+('未知，不填零' if row['oddLotOutcome']=='unknown-not-probability' else '本比例无零头')+'|')
    body+=['','## 收益口径不要混用','|情景|扣机会成本后收益/声明预算%|资金日简单年化%（未扣机会成本）|未使用预算（元）|','|---|---:|---:|---:|']
    for row in rows:
        budget=Decimal(row['declaredBudget']);account_return=Decimal(row['profitAfterOpportunityCost'])/budget*100 if budget else None
        annual=Decimal(row['capitalDaySimpleAnnualizedPct']) if row['capitalDaySimpleAnnualizedPct'] is not None else None
        show=lambda value:format(value,'.4f') if value is not None else '未计算'
        body.append('|'+clean(row['id'])+'|'+show(account_return)+'|'+show(annual)+'|'+row['unusedBudget']+'|')
    body.append('声明预算收益率会受闲置资金稀释；闲置现金利息未计入。资金日年化按分段金额×自然日换算，仅为这次情景的简单年化，不是账户全年收益或可持续复利；不能乘假定全年发行只数冒充实测。')
    body+=['','## 余股会怎样改变收益','|情景|仅比例部分净收益（元）|假设额外百股后净收益（元）|','|---|---:|---:|']
    for row in rows:
        branch=row.get('additionalHundredShareBranch')
        extra=format(Decimal(branch['profitAfterOpportunityCost']),'.2f') if branch else '本比例无适用余股分支'
        body.append('|'+clean(row['id'])+'|'+format(Decimal(row['profitAfterOpportunityCost']),'.2f')+'|'+extra+'|')
    body.append('两列是条件假设，不是获配概率或损失界。额外获配需要更多本金留存至卖出结算，佣金、税费、滑点及资金成本均重新计算；破发时多获配也可能增加损失。没有完整排序或账户结果，不能选择其中一列当作实际收益。')
    body+=['','## 成本怎样影响结果','未填写的费用字段按零假设计算，不代表免税或券商免费；应按实际收费与历史生效日期核对。']
    for row in rows:
        parts=row['saleCostBreakdown']
        body+=['',clean(row['id'])+'：佣金'+parts['commission']+'，印花税'+parts['stampTax']+'，过户费'+parts['transferFee']+'，滑点'+parts['slippage']+'；融资成本'+row['financingCost']+'，机会成本'+row['opportunityCost']+'元。',
               '资金日采用申购至退款、获配本金至卖出结算两段；实际可用日期须有依据。机会成本和融资成本可能重叠，按资金来源解释。']
    if summary['weightedNetProfit'] is not None:
        body+=['','## 输入权重下的汇总','加权净收益（仅比例整手，未知余股未计）：'+str(Decimal(summary['weightedNetProfit']).quantize(Decimal('.01')))+'元。比例获配至少百股的情景权重：'+summary['proportionalHundredShareScenarioWeight']+'；这不是已验证的获配概率。','权重依据：'+clean(result['probabilityBasis'])]
    else:body+=['','未提供情景概率权重，因此不输出期望收益、p90成功率或破发概率。']
    body+=['','## 依据与限制']
    for row in rows:body+=['- '+clean(row['id'])+'：配售率依据 '+clean(row['rateBasis'])+'；涨跌幅依据 '+clean(row['gainBasis'])]
    body+=['- '+text for text in result['limitations']]
    return '\n'.join(body)


def publish(spec,out):
    out=Path(out)
    if out.exists():raise FileExistsError('输出目录已存在，不覆盖旧报告')
    result=evaluate(spec);body=markdown(result)
    out.mkdir(parents=True)
    files={'input.json':json.dumps(spec,ensure_ascii=False,indent=2,allow_nan=False),
           'result.json':json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),
           '北交所资金与收益情景.md':body,'北交所资金与收益情景.html':render(body,'北交所资金与收益情景')}
    for name,text in files.items():(out/name).write_text(text,'utf-8')
    (out/'report-manifest.json').write_text(json.dumps({'files':{name:None for name in files}},ensure_ascii=False,indent=2),'utf-8')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('input',type=Path);parser.add_argument('--out-dir',required=True);args=parser.parse_args()
    publish(json.loads(args.input.read_text('utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float),args.out_dir)
