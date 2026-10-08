"""Observed account valuation/flow review; not an execution or allocation engine."""
import argparse,json,math
from decimal import Decimal
from collections import defaultdict
from pathlib import Path
from fund_dca import xirr
from collection_validation import unique_pairs,reject_constant,finite_json_float
from research_brief_html import render

def number(value):
    if isinstance(value,bool):raise ValueError('金额不能是布尔值')
    try:result=float(value)
    except (ValueError,TypeError) as error:raise ValueError('金额须为有限数字') from error
    if not math.isfinite(result):raise ValueError('金额须为有限数字')
    return result

def calculate(spec):
    from datetime import date
    if not isinstance(spec,dict) or spec.get('cashFlowCoverage')!='declared-complete':raise ValueError('需要声明本区间外部现金流完整；未知不能按零处理')
    if not isinstance(spec.get('basis'),str) or not spec['basis'].strip():raise ValueError('请提供账户估值与现金流的依据')
    if not isinstance(spec.get('currency'),str) or len(spec['currency'])!=3 or not spec['currency'].isalpha() or not spec['currency'].isupper():raise ValueError('需要三位大写币种声明，不能假定人民币')
    if spec.get('amountUnit') not in ('base','thousand','million'):raise ValueError('金额单位须明确为base、thousand或million；不自动缩放')
    label=spec.get('accountLabel')
    if label is not None and (not isinstance(label,str) or not label.strip() or len(label)>100 or '\n' in label or '\r' in label):raise ValueError('账户研究名称须为1至100字单行文字，不必提供真实账号')
    unit_scale={'base':1,'thousand':1000,'million':1000000}[spec['amountUnit']]
    rows=spec.get('observations')
    if not isinstance(rows,list) or not 2<=len(rows)<=20000:raise ValueError('需要2至20000条流入前后估值记录')
    ledger=[];previous=None;product=1.;flows=defaultdict(float);external=0.
    for row in rows:
        if not isinstance(row,dict):raise ValueError('估值记录须为对象')
        day=row['date'];date.fromisoformat(day)
        if date.fromisoformat(day).isoformat()!=day or (previous and day<=previous['date']):raise ValueError('日期须唯一、严格递增且为YYYY-MM-DD')
        before=number(row['beforeFlowValue']);flow=number(row['externalFlow']);after=number(row['afterFlowValue'])
        tolerance=max(.01/unit_scale,math.ulp(max(abs(before),abs(after),abs(flow)))*8)
        if before<0 or after<0 or abs(after-before-flow)>tolerance:raise ValueError('外部现金流前后估值不勾稽；交易成本不得伪装成外部出入金')
        period=None
        if previous:
            if previous['afterFlowValue']<=0:raise ValueError('前次出入金后资产为零，不能拼接时间加权收益')
            period=before/previous['afterFlowValue']-1;product*=1+period
        else:flows[day]-=before
        flows[day]-=flow;external+=flow
        previous={'date':day,'beforeFlowValue':before,'externalFlow':flow,'afterFlowValue':after,'periodReturnPct':None if period is None else period*100}
        ledger.append(previous)
    flows[ledger[-1]['date']]+=ledger[-1]['afterFlowValue']
    ordered=[(day,value) for day,value in sorted(flows.items()) if value]
    signs=[1 if value>0 else -1 for _,value in ordered];changes=sum(a!=b for a,b in zip(signs,signs[1:]))
    rate=xirr(ordered) if changes==1 and signs[0]<0 and signs[-1]>0 else None
    twr=(product-1)*100
    if not math.isfinite(twr):raise ValueError('时间加权收益超出支持数值范围')
    return {'type':'portfolio-observed-cashflow-review','start':ledger[0]['date'],'end':ledger[-1]['date'],'twrPct':twr,'xirrPct':rate,'xirrStatus':'calculated-conventional-flows' if rate is not None else 'unresolved-or-nonconventional-flows','netExternalFlow':external,'openingValue':ledger[0]['beforeFlowValue'],'endingValue':ledger[-1]['afterFlowValue'],'profit':ledger[-1]['afterFlowValue']-ledger[0]['beforeFlowValue']-external,'ledger':ledger,'basis':spec['basis']}

def publish(spec,out):
    from datetime import datetime,timezone
    out=Path(out)
    if out.exists():raise FileExistsError('请另存新的研究目录')
    result=calculate(spec);rate='未输出：现金流非传统或求解未通过' if result['xirrPct'] is None else f"{result['xirrPct']:.2f}%"
    scale=Decimal({'base':1,'thousand':1000,'million':1000000}[spec['amountUnit']])
    def money(value,signed=False):return format(Decimal(str(value))*scale,'+,.2f' if signed else ',.2f')
    profit=result['profit'];flow=result['netExternalFlow'];change=result['endingValue']-result['openingValue']
    profit_text=('盈利'+money(profit) if profit>0 else '亏损'+money(abs(profit)) if profit<0 else '盈亏持平')
    headline='按本次记录，期末较期初'+('增加' if change>=0 else '减少')+money(abs(change))+' '+spec['currency']+'；其中净'+('转入' if flow>=0 else '取出')+money(abs(flow))+'，剔除出入金后'+profit_text+'。累计时间加权收益为'+format(result['twrPct'],'.2f')+'%，不把追加本金当作投资收益。'
    result['headline']=headline
    body=f"# 组合出入金与收益观察\n\n> {headline}\n\n论据（收益口径）：累计时间加权收益{result['twrPct']:.2f}%；资金加权年化XIRR为{rate}。二者周期不同，不能直接相减判断择时能力。\n\n期初资产{money(result['openingValue'])}，净投入{money(flow)}，期末资产{money(result['endingValue'])}，区间损益{money(profit)}。本页金额统一显示为{spec['currency']}基本货币单位，不换汇；原输入单位见下表说明。\n\n## 这些数字说明什么\n\n时间加权收益衡量已观察账户路径，按每笔外部出入金前后估值分段链接；XIRR考虑客户投入和收回时点，使用实际天数及365.25日年化。现金流后买入还是保留现金已体现在提供的账户估值中，本入口不模拟成交。\n\n## 依据与限制\n\n{result['basis']}\n\n记录区间：{result['start']}至{result['end']}。完整性只是输入声明，未认证真实账单。期末资产按假设变现作为XIRR现金流，不等于到手款；估值需包含现金和已计费用。没有流入前估值时不猜TWR，多次现金流符号变化时不选择任意IRR根。不构成投资建议。"
    units={'base':'基本货币单位','thousand':'千单位','million':'百万单位'}
    body=body.replace('二者周期不同，不能直接相减判断择时能力。','一个是区间累计表现，另一个考虑投入时点并年化，不能直接比大小来判断择时好坏。',1)
    body=body.replace('现金流后买入还是保留现金已体现在提供的账户估值中，本入口不模拟成交。','转入的钱后来买了资产还是留着现金，要看你提供的账户估值；这里没有替你模拟买卖。',1)
    body+='\n\n## 逐期出入金明细\n\n币种：'+spec['currency']+'；本页显示基本货币单位，原输入为'+units[spec['amountUnit']]+'，JSON结果保留原输入单位。正数是投入，负数是取出；期初没有前一段收益。\n\n|日期|出入金前资产|外部投入/取出|出入金后资产|上次流后至本次流前收益|\n|---|---:|---:|---:|---:|\n'
    for row in result['ledger']:
        period='期初，不计算' if row['periodReturnPct'] is None else f"{row['periodReturnPct']:.2f}%"
        body+=f"|{row['date']}|{money(row['beforeFlowValue'])}|{money(row['externalFlow'],True)}|{money(row['afterFlowValue'])}|{period}|\n"
    result.update(currency=spec['currency'],amountUnit=spec['amountUnit'])
    if spec.get('accountLabel'):
        result['accountLabel']=spec['accountLabel'].strip()
        body+='\n\n本次研究名称：'+result['accountLabel']+'。这是你给研究起的名字，不认证账户身份。'
    if spec.get('exampleType') is not None:
        if spec['exampleType']!='teaching-only':raise ValueError('示例标记仅支持teaching-only')
        result['exampleType']='teaching-only'
        body=body.replace('# 组合出入金与收益观察\n','# 组合出入金与收益观察\n\n**教学估值和出入金，不是真实账户账单。**\n',1)
    out.mkdir(parents=True)
    files={'input.json':json.dumps(spec,ensure_ascii=False,allow_nan=False,indent=2),'result.json':json.dumps(result,ensure_ascii=False,allow_nan=False,indent=2),'组合出入金与收益观察.md':body,'组合出入金与收益观察.html':render(body,'组合出入金与收益观察')}
    for name,text in files.items():(out/name).write_text(text,'utf-8')
    (out/'research-request.json').write_text(json.dumps({'command':'cashflow','start':result['start'],'asOf':result['end'],'names':[result['accountLabel']] if result.get('accountLabel') else []},ensure_ascii=False,indent=2),'utf-8')
    files['research-request.json']=None
    (out/'report-manifest.json').write_text(json.dumps({'files':{name:None for name in files},'primaryReport':'组合出入金与收益观察.html','savedAt':datetime.now(timezone.utc).isoformat()},ensure_ascii=False,indent=2),'utf-8')
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('input',type=Path);parser.add_argument('--out-dir',required=True);args=parser.parse_args()
    spec=json.loads(args.input.read_text('utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float);publish(spec,args.out_dir)
