"""Extract nine-column QDII or six-column domestic complete-equity tables.
Requires pdfplumber. Report identity, publication date and totals must be checked
against the original by the caller. Does not infer industry or current holdings.
"""
import argparse,datetime,hashlib,json,re
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse
import pdfplumber

def clean(s): return re.sub(r'\s+','',s or '')
def number(s):
    value=Decimal(clean(s).replace(',',''))
    if not value.is_finite():raise ValueError('原文金额或数量为非有限值')
    return value

def issuer_order_values(groups,values,declared,hk_scope):
    """Validate the explicitly disclosed A/H ranking convention, not issuer identity."""
    result=[];i=0
    while i<len(groups):
        group=groups[i]
        if declared and hk_scope and len(group)==1 and i+1<len(groups) and len(groups[i+1])==1:
            a,b=group[0],groups[i+1][0]
            if a['cells'][2]==b['cells'][2] and sorted([len(a['cells'][1]),len(b['cells'][1])])==[5,6]:
                if i+2<len(groups) and any(x['cells'][2]==a['cells'][2] for x in groups[i+2]):raise ValueError('A/H排序组超过明确双行，需复核')
                pair=[a['cells'][1],b['cells'][1]]
                a['issuerOrderPairCodes']=pair;b['issuerOrderPairCodes']=pair
                result.append(values[i]+values[i+1]);i+=2;continue
        result.append(values[i]);i+=1
    return result

def domestic_rows(doc):
    rows=[];started=False;finished=False;segment='indexInvestment';sequences={}
    hk_scope=any(re.search(r'(?m)^[78]\.2\.[23]\s*报告期末按行业分类的港股通投资股票投资组合\s*$',p.extract_text() or '') for p in doc.pages)
    issuer_order_declared=any('对于同时在A+H股上市的股票，合并计算公允价值参与排序，并按照不同股票分别披露。' in clean(p.extract_text() or '') for p in doc.pages)
    for page_no,page in enumerate(doc.pages,1):
        text=page.extract_text() or '';normalized=clean(text)
        if re.search(r'^(?:[78]\.3(?:\.[12])?\s*)?(?:报告)?期末按[^\n]*所有股票投资明细\s*$',text,re.M):
            started=True
            segment='indexInvestment' if '指数投资' in normalized else 'allEquity'
        if not started or finished:continue
        ends=page.search(r'(?m)^(?:[78]\.4\s*)?报告期内股票投资组合的重大变动\s*$')
        end_top=ends[0]['top'] if ends else float('inf')
        for table in page.find_tables():
            if table.bbox[1]>=end_top:continue
            for cells in table.extract():
                c=[clean(x) for x in cells if clean(x)]
                reported_code=c[1] if len(c)>1 else None
                if hk_scope and len(c)==6 and re.fullmatch(r'H\d{5}',c[1]):c[1]=c[1][1:]
                if len(c)!=6 or not c[0].isdigit() or not (re.fullmatch(r'\d{6}',c[1]) or hk_scope and re.fullmatch(r'\d{5}',c[1])):continue
                rank=int(c[0])
                if rank==1 and rows and rows[-1]["rank"]!=1:
                    if segment!='indexInvestment' or 'activeInvestment' in sequences:raise ValueError('出现未知排名重置，不能合并股票表')
                    segment='activeInvestment'
                sequences.setdefault(segment,[]).append(rank)
                rows.append({'rank':rank,'segment':segment,'cells':c,'reportedCode':reported_code,'pages':[page_no]})
        if ends and rows:finished=True
    if not started or not finished or not rows:raise ValueError('未找到完整7.3股票表至7.4边界')
    for segment,ranks in sequences.items():
        # Some reports use dense ranks for exactly equal fair values.
        section=[r for r in rows if r['segment']==segment]
        if ranks[0]!=1:raise ValueError(segment+'未从1开始')
        groups=[]
        for row in section:
            if not groups or groups[-1][0]['rank']!=row['rank']:groups.append([row])
            else:groups[-1].append(row)
        ranked_values=[]
        for group in groups:
            amounts=[number(x['cells'][4]) for x in group]
            if len(set(amounts))>1:
                if not hk_scope or len(group)!=2 or sorted(len(x['cells'][1]) for x in group)!=[5,6]:raise ValueError(segment+'非等值共享序号缺少明确境内/港股双行结构')
                ranked_values.append(sum(amounts,Decimal(0)))
            else:ranked_values.append(amounts[0])
        for before,after in zip(groups,groups[1:]):
            delta=after[0]['rank']-before[0]['rank']
            competition_tie=len(before)>1 and len({number(x['cells'][4]) for x in before})==1 and delta==len(before)
            if delta!=1 and not competition_tie:raise ValueError(segment+'股票序号缺失或逆序')
        ordered_values=issuer_order_values(groups,ranked_values,issuer_order_declared,hk_scope)
        if any(b>a for a,b in zip(ordered_values,ordered_values[1:])):raise ValueError(segment+'权益公允价值排序逆序')
    if 'indexInvestment' in sequences and 'activeInvestment' not in sequences:raise ValueError('指数/积极双表未完整取得')
    return rows,sequences

def domestic_result(doc,raw,code,report_date,published_at,source_url,net_assets,equity_value):
    rows,sequences=domestic_rows(doc);total=sum((number(r['cells'][4]) for r in rows),Decimal(0))
    if total!=equity_value:raise ValueError(f'权益市值合计不一致：{total} vs {equity_value}')
    merged={};segments={}
    for r in rows:
        c=r['cells'];mv=number(c[4]);weight=mv/net_assets;shown=number(c[5]);qty=number(c[3])
        if mv<0 or qty<0 or qty!=qty.to_integral_value():raise ValueError('市值/股数不合法')
        if abs(weight*100-shown)>Decimal('.00501'):raise ValueError(c[1]+'权重与金额分母不匹配')
        segments[r['segment']]=segments.get(r['segment'],Decimal(0))+mv
        component={'reportedCode':r.get('reportedCode',c[1]),'segment':r['segment'],'rank':r['rank'],'quantity':int(qty),'marketValueCNY':float(mv),'reportedWeightPct':float(shown),'locator':'PDF页'+str(r['pages'][0])}
        if r.get('issuerOrderPairCodes'):component['issuerOrderPairCodes']=r['issuerOrderPairCodes'];component['rankingBasis']='报告明示A/H合并公允价值排序，证券仍分列；非全市场发行人身份认证'
        if c[1] not in merged:merged[c[1]]={'code':c[1],'name':c[2],'market':'HK-exchange-unresolved' if len(c[1])==5 else 'CN-exchange-unresolved','securityNamespace':'HK-equity' if len(c[1])==5 else 'CN-equity','shareClass':'ordinary','industry':'','components':[],'amount':Decimal(0),'quantity':0}
        h=merged[c[1]]
        if h['name']!=c[2]:raise ValueError('同代码跨表名称冲突')
        if any(x['segment']==r['segment'] for x in h['components']):raise ValueError('同表股票代码重复')
        h['components'].append(component);h['amount']+=mv;h['quantity']+=int(qty)
    holdings=[]
    for h in merged.values():
        amount=h.pop('amount');h.update({'weight':float(amount/net_assets),'marketValueCNY':float(amount),'locator':'；'.join(x['locator'] for x in h['components'])});holdings.append(h)
    holdings.sort(key=lambda h:-h['weight'])
    rank_ties=[{'segment':x['segment'],'rank':x['rank'],'codes':[p['cells'][1],x['cells'][1]],'marketValueCNY':float(number(x['cells'][4])) if number(p['cells'][4])==number(x['cells'][4]) else None,'valuesCNY':[float(number(p['cells'][4])),float(number(x['cells'][4]))],'basis':'equal-values' if number(p['cells'][4])==number(x['cells'][4]) else 'reported-shared-rank-distinct-securities','locator':'PDF页'+str(x['pages'][0])} for p,x in zip(rows,rows[1:]) if p['segment']==x['segment'] and p['rank']==x['rank']]
    return {'id':code,'allocation':1,'currency':'CNY','reportDate':report_date,'publishedAt':published_at,'sourceUrl':source_url,'locator':'中报§7.3/年报§8.3全部股票表；金额为人民币','disclosureScope':'completeEquity','equityWeight':float(equity_value/net_assets),'netAssetsCNY':float(net_assets),'equityMarketValueCNY':float(equity_value),'holdings':holdings,'rawRowCount':len(rows),'segments':{k:{'rows':len(sequences[k]),'marketValueCNY':float(v)} for k,v in segments.items()},'rankTies':rank_ties,'portfolioScope':'fund-all-share-classes','sourceSha256':hashlib.sha256(raw).hexdigest(),'parserVersion':'complete-equity-9','verification':'逐行权重、各表序号、跨表合并与总市值逐分勾稽通过；报告身份/日期/分母仍需原文核验','limitations':['持仓分母为基金全部份额合计净资产，不是某份额类净资产','市场命名空间依据原文股票代码及明确港股通章节区分；具体交易所尚未核验，不猜板块','非股票资产未穿透；不是实时持仓或交易流水','行业未分类，不输出行业集中度结论']}
def extract(pdf,code,report_date,published_at,source_url,net_assets,equity_value):
    if not re.fullmatch(r'\d{6}',code): raise ValueError('基金代码须为六位数字')
    if datetime.date.fromisoformat(report_date)>datetime.date.fromisoformat(published_at): raise ValueError('发布日期早于报告日')
    if urlparse(source_url).scheme!='https': raise ValueError('需HTTPS原文地址')
    net_assets,equity_value=Decimal(str(net_assets)),Decimal(str(equity_value))
    if net_assets<=0 or equity_value<0 or equity_value>net_assets: raise ValueError('净资产或股票总额不合法')
    raw=Path(pdf).read_bytes(); rows=[]; started=False; finished=False
    with pdfplumber.open(pdf) as doc:
        texts=[p.extract_text() or '' for p in doc.pages]
        alltext='\n'.join(texts)
        if code not in alltext or '中期报告' not in alltext and '年度报告' not in alltext: raise ValueError('代码/报告类型未在原文中找到')
        rd=datetime.date.fromisoformat(report_date)
        # Some managers print leading zeroes in month/day.
        if not re.search(rf'{rd.year}年0?{rd.month}月0?{rd.day}日',clean(alltext)): raise ValueError('报告日未在原文找到')
        if re.search(r'^(?:[78]\.3(?:\.[12])?\s*)?(?:报告)?期末按.*所有股票投资明细',alltext,re.M):
            return domestic_result(doc,raw,code,report_date,published_at,source_url,net_assets,equity_value)
        for page_no,(page,text) in enumerate(zip(doc.pages,texts),1):
            normalized=clean(text)
            if re.search(r'^[78]\.4\s*期末按',text,re.M) and '所有权益投资明细' in normalized: started=True
            if not started or finished: continue
            for table in page.extract_tables():
                for cells in table:
                    if len(cells)!=9: continue
                    c=[clean(x) for x in cells]
                    if c[0].isdigit() and re.fullmatch(r'(?:\d+(?:CH|HK)|[A-Z][A-Z0-9./-]*US)',c[3]):
                        rows.append({'rank':int(c[0]),'cells':c,'reportedCode':c[3],'pages':[page_no]})
                    elif not c[0] and rows and re.fullmatch(r'(?:\d+(?:CH|HK)|[A-Z][A-Z0-9./-]*US)',c[3]) and c[6] and c[7] and c[8]:
                        # Merged issuer/rank cells may cover separate A/H securities.
                        if c[1] or c[2]: raise ValueError('无序号新证券却有独立公司名称，不能推断同发行人')
                        previous=rows[-1]
                        c[0]=str(previous['rank']);c[1]=previous['cells'][1];c[2]=previous['cells'][2]
                        if c[3]==previous['cells'][3]: raise ValueError('合并序号证券重复')
                        rows.append({'rank':previous['rank'],'cells':c,'pages':[page_no],'sharedIssuerRank':True})
                    elif not c[0] and rows and any(c) and not c[3] and not c[7] and not c[8]:
                        for i in range(1,9): rows[-1]['cells'][i]+=c[i]
                        rows[-1]['pages'].append(page_no)
            if rows and re.search(r'^[78]\.5\s*报告期内权益投资组合的重大变动',text,re.M): finished=True
    if not started or not finished or not rows: raise ValueError('未找到完整7.4权益表至7.5边界；此版仅支持九列QDII布局')
    if rows[0]['rank']!=1: raise ValueError('排名未从1开始')
    for previous,current in zip(rows,rows[1:]):
        delta=current['rank']-previous['rank']
        if delta!=1 and not (delta==0 and current.get('sharedIssuerRank')): raise ValueError('排名不连续，可能漏行或误识别')
    total=sum((number(r['cells'][7]) for r in rows),Decimal(0))
    if total!=equity_value: raise ValueError(f'权益市值合计不一致：{total} vs {equity_value}')
    holdings=[];security_keys=set()
    for r in rows:
        c=r['cells'];m=re.fullmatch(r'(\d+)(CH|HK)|([A-Z][A-Z0-9./-]*)(US)',c[3]);code_value,region=(m.group(1),m.group(2)) if m.group(1) else (m.group(3),m.group(4))
        market=('NASDAQ' if '纳斯达' in c[4] else 'NYSE' if '纽约' in c[4] else 'US-exchange-unresolved') if region=='US' else 'HKEX' if region=='HK' else 'SSE' if '上海' in c[4] else 'SZSE' if '深圳' in c[4] else 'BSE' if '北京' in c[4] else None
        if not market: raise ValueError('交易市场无法识别')
        security=code_value if region=='US' else code_value.zfill(5 if region=='HK' else 6)
        security_key=(region,security)
        if security_key in security_keys: raise ValueError('完整权益表证券重复，不能重复计入金额')
        security_keys.add(security_key)
        mv=number(c[7]);weight=mv/net_assets;shown=number(c[8]);quantity=number(c[6])
        if mv<0 or quantity<0:raise ValueError('权益市值或股数为负，须复核')
        if abs(weight*100-shown)>Decimal('.00501'): raise ValueError(f'{security}权重与公允价值不匹配')
        holdings.append({'market':market,'securityNamespace':'US-equity' if region=='US' else 'HK-equity' if region=='HK' else 'CN-equity','code':security,'shareClass':'ordinary','name':c[2],'weight':float(weight),'quantity':int(quantity) if quantity==quantity.to_integral_value() else float(quantity),'marketValueCNY':float(mv),'reportedWeightPct':float(shown),'industry':'','locator':'PDF页'+','.join(map(str,sorted(set(r['pages'])))),'rank':r['rank']})
    return {'id':code,'allocation':1,'currency':'CNY','reportDate':report_date,'publishedAt':published_at,'sourceUrl':source_url,'locator':'中报§7.4/年报§8.4完整权益明细；金额为人民币','disclosureScope':'completeEquity','equityWeight':float(equity_value/net_assets),'netAssetsCNY':float(net_assets),'equityMarketValueCNY':float(equity_value),'holdings':holdings,'portfolioScope':'fund-all-share-classes','sourceSha256':hashlib.sha256(raw).hexdigest(),'parserVersion':'complete-equity-9','verification':'逐行权重与金额勾稽、连续序号及权益合计通过；输入身份/日期/总额仍需原文人工核验','limitations':['仅报告日股票快照，不是当前持仓或交易流水','行业未分类，不输出行业集中度结论','权重用人民币市值/净资产，保留报告中0.00%的非零小额持仓']}

def main():
    p=argparse.ArgumentParser();p.add_argument('pdf');p.add_argument('--code',required=True);p.add_argument('--report-date',required=True);p.add_argument('--published-at',required=True);p.add_argument('--source-url',required=True);p.add_argument('--net-assets',required=True);p.add_argument('--equity-value',required=True);p.add_argument('--out',required=True);a=p.parse_args()
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    if out.exists():raise FileExistsError('输出文件已存在，请使用新文件名；首次依据不覆盖')
    result=extract(a.pdf,a.code,a.report_date,a.published_at,a.source_url,a.net_assets,a.equity_value)
    with out.open('x',encoding='utf8') as f:json.dump(result,f,ensure_ascii=False,indent=2,allow_nan=False)
    print(f'Extracted {len(result["holdings"])} equities; amount reconciled; source archived separately')
if __name__=='__main__': main()



