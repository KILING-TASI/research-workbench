"""Reconcile selected original profit-to-cash rows; not a causal or audit opinion."""
import argparse
import hashlib
import json
import re
from decimal import Decimal
from pathlib import Path
from collection_validation import day,unique_pairs,reject_constant


def number(value):
    if not isinstance(value, str):raise ValueError('金额须为明确的十进制字符串')
    if not re.fullmatch(r'-?(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d+)?',value):
        raise ValueError('金额格式不合法：仅接受十进制及正确千分位，不接受百分号、科学计数或空白')
    result=Decimal(value.replace(',',''))
    if not result.is_finite():raise ValueError('金额必须有限')
    return result


def direct_cash_bridge(rows, totals):
    """Selected direct-method rows in one declared currency/unit and period.

    This arithmetic helper does not extract or verify original documents.
    Missing amounts remain missing; subtotal agreement is not completeness proof.
    """
    if not isinstance(rows,list) or not rows:raise ValueError('须提供实际收付款行')
    seen=set();checked=[];missing=[]
    for row in rows:
        if not isinstance(row,dict):raise ValueError('收付款行须为对象')
        key=row.get('key');direction=row.get('direction')
        if not isinstance(key,str) or not key.strip() or key in seen:raise ValueError('收付款编号为空或重复')
        if direction not in ('inflow','outflow'):raise ValueError('须明确流入或流出，不接受任意符号')
        seen.add(key);values={}
        for period in ('current','prior'):
            value=row.get(period)
            if value is None:missing.append(key+':'+period);values[period]=None
            else:values[period]=number(value)
        sign=1 if direction=='inflow' else -1
        delta=None if None in values.values() else str((values['current']-values['prior'])*sign)
        checked.append(dict(row,netChangeContribution=delta))
    if not isinstance(totals,dict):raise ValueError('须声明两期流入、流出及净额小计')
    sums={};differences={}
    for period in ('current','prior'):
        stated=totals.get(period)
        if not isinstance(stated,dict):raise ValueError('须声明两期小计')
        for name in ('inflow','outflow','net'):
            value=stated.get(name)
            if value is None:missing.append('total:'+period+':'+name)
            else:number(value)
    if missing:
        return dict(status='missing-data',missing=missing,rows=checked,sums=None,differences=None,netChange=None,originalVerified=False)
    for period in ('current','prior'):
        inflow=sum((number(r[period]) for r in rows if r['direction']=='inflow'),Decimal(0))
        outflow=sum((number(r[period]) for r in rows if r['direction']=='outflow'),Decimal(0))
        computed=dict(inflow=inflow,outflow=outflow,net=inflow-outflow)
        sums[period]={k:str(v) for k,v in computed.items()}
        differences[period]={k:str(v-number(totals[period][k])) for k,v in computed.items()}
    matched=all(Decimal(v)==0 for p in differences.values() for v in p.values())
    return dict(status='selected-subtotals-reconciled' if matched else 'reconciliation-mismatch',rows=checked,
                sums=sums,differences=differences,missing=[],netChange=str(Decimal(sums['current']['net'])-Decimal(sums['prior']['net'])),
                originalVerified=False,fullTableCoverageVerified=False,
                limitations=['仅核对输入金额，不核实原文或收付款分类','收付款同比贡献不等于经济原因','直接收付款分解与利润调节表不能重复相加'])


def reconcile(spec, original):
    if not isinstance(spec,dict) or not isinstance(original,dict):raise ValueError('现金核验输入与原文记录须为对象')
    day(spec.get('period'))
    if not isinstance(spec.get('sourceSha256'),str) or not spec['sourceSha256'].strip():raise ValueError('原文版本哈希缺失')
    if spec.get('unit')!='元' or spec.get('currency')!='CNY':raise ValueError('当前仅接受已确认人民币元口径')
    if spec.get('sourceSha256')!=original.get('fileSha256'):raise ValueError('原文版本不一致')
    page_rows=original.get('pages')
    if not isinstance(page_rows,list) or not page_rows or any(not isinstance(x,dict) or type(x.get('page')) is not int or x['page']<1 or not isinstance(x.get('text'),str) for x in page_rows):raise ValueError('原文页记录须为正整数物理页及文字')
    if len({x['page'] for x in page_rows})!=len(page_rows):raise ValueError('原文物理页重复，不能覆盖旧页内容')
    pages={x['page']:re.sub(r'\s+','',x['text']) for x in page_rows}
    reported_unit=spec.get('reportedUnit','元')
    if reported_unit not in ('元','千元','万元'):raise ValueError('原文金额单位不支持')
    scale={'元':Decimal(1),'千元':Decimal(1000),'万元':Decimal(10000)}[reported_unit]
    if scale!=1:
        evidence=spec.get('unitEvidence',{})
        quote=re.sub(r'\s+','',evidence.get('quote',''))
        if not quote or quote not in pages.get(evidence.get('page'),'') or ('单位：'+reported_unit) not in quote or '人民币' not in quote:
            raise ValueError('换算须匹配原文单位及人民币声明')
    rows=spec.get('rows');seen=set();checked=[]
    if not isinstance(rows,list) or not rows:raise ValueError('须提供调节表行')
    for row in rows+[spec['cashTotal']]:
        if not isinstance(row,dict) or not isinstance(row.get('key'),str) or not row['key'].strip():raise ValueError('调节项目须为具有编号的对象')
        if type(row.get('page')) is not int or row['page']<1 or not isinstance(row.get('quote'),str):raise ValueError('调节项目须给出物理页及引句')
        key=row['key']
        if key in seen:raise ValueError('调节项目重复')
        seen.add(key)
        quote=re.sub(r'\s+','',row['quote'])
        if not quote or quote not in pages.get(row['page'],''):raise ValueError('原文行摘录未匹配')
        current=number(row['current']);prior=number(row['prior'])
        # Do not accept a numeric substring of malformed money, percentages,
        # scientific notation or an unsupported Unicode minus sign.
        left=r'(?<![\d.,eE+\-−－])'
        right=r'(?![\d.,eE%％])'
        pattern=left+r'-?\d[\d,]*(?:\.\d+)?'+right if scale!=1 else left+r'-?\d[\d,]*\.\d+'+right
        tokens=re.findall(pattern,row['quote'])
        if len(tokens)!=2 or [number(x)*scale for x in tokens]!=[current,prior]:raise ValueError('原文行两列金额、单位换算或顺序不匹配')
        checked.append(dict(row,change=str(current-prior),reportedAmounts=tokens,reportedUnit=reported_unit,verification='两列金额与选定摘录匹配'))
    if rows[0]['key']!='netProfit':raise ValueError('调节表须以合并净利润开头，不是归母净利润')
    sums={k:sum((number(r[k]) for r in rows),Decimal(0)) for k in ('current','prior')}
    differences={k:sums[k]-number(spec['cashTotal'][k]) for k in sums}
    return dict(status='selected-table-reconciled' if all(v==0 for v in differences.values()) else 'reconciliation-mismatch',
                rows=checked[:-1],cashTotal=checked[-1],sums={k:str(v) for k,v in sums.items()},
                differences={k:str(v) for k,v in differences.items()},unit='元',currency='CNY',
                period=spec['period'],sourceSha256=spec['sourceSha256'],semanticCertification=False,
                reportedUnit=reported_unit,amountScale=str(scale),unitEvidence=spec.get('unitEvidence'),
                limitations=['调节项与现金之间为会计勾稽，不是独立经济因果识别','项目覆盖完整性仍需对照原表逐行复查','经营性应收应付并非单一资产负债表科目','累计期调节不直接解释单季度'])


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('input');p.add_argument('--out',required=True);a=p.parse_args()
    input_path=Path(a.input).resolve()
    spec=json.loads(input_path.read_text(encoding='utf-8'),object_pairs_hook=unique_pairs,parse_constant=reject_constant)
    original_path=Path(spec['originalResult'])
    if not original_path.is_absolute():original_path=input_path.parent/original_path
    original=json.loads(original_path.read_text(encoding='utf-8'),object_pairs_hook=unique_pairs,parse_constant=reject_constant)
    matches=[x for x in original['companies'] if x['code']==spec['code']]
    if len(matches)!=1:raise ValueError('原文公司匹配不唯一')
    result=reconcile(spec,matches[0]);result['inputSha256']=hashlib.sha256(Path(a.input).read_bytes()).hexdigest()
    with Path(a.out).open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
