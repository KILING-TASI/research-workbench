"""Aggregate selected disclosed bonds through child funds; not issuer risk."""
import json,argparse,hashlib
from pathlib import Path
from decimal import Decimal
from bond_topfive_concentration import amount,calculate,verify_original
from fund_balance_snapshot import extract as extract_balance

def aggregate(parent_nav,children):
    if not isinstance(children,list) or not children or any(not isinstance(c,dict) or not isinstance(c.get('childCode'),str) or not c['childCode'].strip() for c in children):raise ValueError('须明确提供子份额清单，空清单不等于零暴露')
    nav=amount(parent_nav)
    if nav<=0:raise ValueError('父净资产须大于零')
    if len({c['childCode'] for c in children})!=len(children):raise ValueError('同一子份额重复输入')
    securities={};selected=Decimal(0)
    for child in children:
        holding=amount(child['parentHoldingAmountCNY']);selected+=holding
        child_nav=amount(child['childNetAssetsCNY'])
        if child_nav<=0:raise ValueError('子净资产须大于零')
        calculate(child['topFive'])
        for row in child['topFive']['entries']:
            contribution=holding/nav*amount(row['amountCNY'])/child_nav
            record=securities.setdefault(row['code'],dict(code=row['code'],fraction=Decimal(0),paths=[]))
            record['fraction']+=contribution
            record['paths'].append(dict(childCode=child['childCode'],parentHoldingAmountCNY=str(holding),childNetAssetsCNY=str(child_nav),bondAmountCNY=row['amountCNY'],parentNAVPercentage=str(contribution*100)))
    if selected>nav:raise ValueError('所选子份额金额超过父净资产；此入口暂不支持该杠杆口径')
    result=[]
    for r in securities.values():
        r['parentNAVPercentage']=str(r.pop('fraction')*100);result.append(r)
    result.sort(key=lambda r:Decimal(r['parentNAVPercentage']),reverse=True)
    return dict(securities=result,totalSelectedParentNAVPercentage=str(sum((Decimal(r['parentNAVPercentage']) for r in result),Decimal(0))),formula='父持仓金额/父净资产 × 子债券金额/子净资产；相同精确债券代码贡献相加',scope='仅指定子份额的披露前五名；不同代码不视为发行人独立，不认证完整债券风险')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('input');parser.add_argument('--out',required=True);args=parser.parse_args()
    input_path=Path(args.input).resolve();spec=json.loads(input_path.read_text(encoding='utf-8'));dependencies=[]
    def read(value):
        p=Path(value);p=p if p.is_absolute() else input_path.parent/p
        dependencies.append(dict(path=str(p.resolve()),sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
        return json.loads(p.read_text(encoding='utf-8')),p
    parent,_=read(spec['parentFundDetails']);children=[]
    for c in spec['children']:
        top,p=read(c['topFiveInput']);balance,_=read(c['balanceSnapshot'])
        if 'balanceInput' not in c:raise ValueError('须提供余额原文提取输入balanceInput，以复核分母')
        balance_input,balance_input_path=read(c['balanceInput'])
        fresh_balance=extract_balance(balance_input,balance_input_path.parent)
        for field in ('code','reportDate','currency','amountsCNY'):
            if fresh_balance[field]!=balance[field]:raise ValueError('余额快照与当前原表重提取不一致：'+field)
        holding=next((h for h in parent['holdings'] if h['code']==c['code']),None)
        if holding is None:raise ValueError('父基金不存在指定子份额')
        if top['code']!=c['code'] or balance['code']!=c['code']:raise ValueError('子份额代码不匹配')
        if parent['reportDate']!=top['reportDate'] or top['reportDate']!=balance['reportDate'] or balance['currency']!='CNY':raise ValueError('报告期或币种不一致')
        verify_original(top,p.parent)
        # The balance source must be the same selected original, with unchanged bytes.
        source=balance.get('sourceStructureReview',{})
        if source.get('sha256')!=top['sourceSha256'] or source.get('reviewRequired') is not False:raise ValueError('余额原件身份或结构状态不匹配')
        children.append(dict(childCode=c['code'],parentHoldingAmountCNY=holding['marketValueCNY'],childNetAssetsCNY=balance['amountsCNY']['净资产合计'],topFive=top))
    result=aggregate(parent['netAssetsCNY'],children)
    with Path(args.out).open('x',encoding='utf-8') as f:json.dump(dict(result=result,dependencies=dependencies,scope='已选原文输入与余额快照复算；不重新认证全部父余额或子报表金额'),f,ensure_ascii=False,indent=2)

if __name__=='__main__':main()
