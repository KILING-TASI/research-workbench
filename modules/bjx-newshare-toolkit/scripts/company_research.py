"""Evidence-linked company and issuance valuation card; no price predictions or recommendation."""
import argparse,datetime as dt,hashlib,json,re,statistics
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse
from issuance_facts import HOSTS,compact,view
TOPICS=['business','customers','fundraising','risks','inquiry']
def dec(value):
    if isinstance(value,bool):raise ValueError('数值不能为布尔值')
    v=Decimal(str(value))
    if not v.is_finite():raise ValueError('非有限数值')
    return v

def run(spec):
    code=spec['code'];asof=dt.date.fromisoformat(spec['asOf'])
    if not re.fullmatch(r'[0-9]{6}',code):raise ValueError('代码无效')
    evidence={};documents={};gaps=[]
    docs=spec.get('documents',[])
    if not isinstance(docs,list) or len(docs)>20:raise ValueError('documents最多20项')
    if docs:
        import pdfplumber
        for d in docs:
            if d['id'] in documents:raise ValueError('文档ID重复')
            published=dt.date.fromisoformat(d['publishedAt']);url=urlparse(d['sourceUrl'])
            if published>asof or url.scheme!='https' or url.hostname not in HOSTS:raise ValueError('文档日期越界或来源域名未支持')
            blob=Path(d['path']).read_bytes()
            if len(blob)>100*1024*1024 or not blob.startswith(b'%PDF-'):raise ValueError('PDF无效')
            sha=hashlib.sha256(blob).hexdigest()
            if d.get('sha256') and d['sha256']!=sha:raise ValueError('PDF哈希不符')
            with pdfplumber.open(d['path']) as pdf:
                cache={i+1:compact(p.extract_text()) for i,p in enumerate(pdf.pages[:12])}
                front=''.join(cache.values())
                if not d.get('issuer') or not d.get('title') or compact(d['issuer']) not in front or compact(d['title']) not in front:raise ValueError('文档发行人与标题不匹配')
                # Company document code association may be supplied if no printed code; disclose this distinction.
                identity='issuer-title-code-matched' if code in front else 'issuer-title-matched-code-association-supplied'
                for e in d.get('excerpts',[]):
                    if e['id'] in evidence or e.get('topic') not in TOPICS+['financial','valuation']:raise ValueError('摘录ID重复或topic无效')
                    page=e['page']
                    if type(page)!=int or not 1<=page<=len(pdf.pages):raise ValueError('页码无效')
                    if page not in cache:cache[page]=compact(pdf.pages[page-1].extract_text())
                    if e.get('kind')=='table-cell':
                        page_obj=pdf.pages[page-1];tables=page_obj.find_tables();ti=e['tableIndex'];ri=e['rowIndex'];ci=e['column']
                        for index in [ti,ri,ci,e['headerRow'],e['headerColumn'],e['labelColumn']]:
                            if type(index)!=int or index<0:raise ValueError('表格定位索引无效')
                        if ti>=len(tables):raise ValueError('表格不存在')
                        table=tables[ti];grid=table.extract()
                        try:
                            token=compact(grid[ri][ci]).replace(',','');value=dec(token)
                            label=''.join(compact(grid[i][e['labelColumn']]) for i in e['labelRows'])
                            header=compact(grid[e['headerRow']][e['headerColumn']])
                            cellbox=table.rows[ri].cells[ci];headbox=table.rows[e['headerRow']].cells[e['headerColumn']]
                        except (IndexError,TypeError):raise ValueError('表格行列不存在')
                        if label!=compact(e['label']) or header!=compact(e['periodHeader']) or value!=dec(e['value']):raise ValueError('单元格标签/期间/数值不符')
                        if not cellbox or not headbox or not cellbox[0]<=(headbox[0]+headbox[2])/2<=cellbox[2]:raise ValueError('期间表头未与数值列对齐')
                        per=dt.date.fromisoformat(e['period']);expected_header=f'{per.year}年{per.month}月{per.day}日'
                        if expected_header not in header:raise ValueError('期间声明与表头冲突')
                        if e['unit']=='CNY' and '(元)' not in label:raise ValueError('标签未明确元单位')
                        if e['unit']=='pct' and '%' not in label:raise ValueError('标签未明确百分数单位')
                        evidence[e['id']]={**e,'documentId':d['id'],'sourceUrl':d['sourceUrl'],'documentSha256':sha,'publishedAt':d['publishedAt'],'verification':'exact-table-cell-with-header','originalLabel':label,'originalValue':token}
                        continue
                    text=compact(e['text'])
                    if len(text)<8 or cache[page].count(text)!=1:raise ValueError('摘录不在原文指定页唯一匹配')
                    evidence[e['id']]={**e,'documentId':d['id'],'sourceUrl':d['sourceUrl'],'documentSha256':sha,'publishedAt':d['publishedAt'],'verification':'exact-text-excerpt-not-semantic-numeric-validation'}
            documents[d['id']]={'path':str(Path(d['path']).resolve()),'sha256':sha,'sourceUrl':d['sourceUrl'],'publishedAt':d['publishedAt'],'identity':identity}
    def observation(obj):
        if obj is None:return None,None
        if not isinstance(obj,dict) or obj.get('unit') not in ['CNY','shares','pct','multiple']:raise ValueError('观测需value/unit/evidenceIds，单位显式统一')
        ids=obj.get('evidenceIds',[])
        if any(i not in evidence for i in ids):raise ValueError('指标引用不存在证据')
        for i in ids:
            proof=evidence[i]
            if proof.get('kind')=='table-cell' and (dec(proof['value'])!=dec(obj['value']) or proof['unit']!=obj['unit']):raise ValueError('观测与证据数值单位不一致')
        if obj.get('publishedAt') and dt.date.fromisoformat(obj['publishedAt'])>asof:raise ValueError('观测发布晚于截止日')
        return dec(obj['value']),{'evidenceIds':ids,'verification':'exact-table-cell-mapped' if ids and all(evidence[i]['verification']=='exact-table-cell-with-header' for i in ids) else 'user-mapped-observation-with-excerpt' if ids else 'user-supplied-unverified','unit':obj['unit']}
    financial=[];seen=set()
    for row in spec.get('financials',[]):
        period=dt.date.fromisoformat(row['period'])
        if period>asof or row.get('periodBasis')!='FY' or row.get('scope')!='consolidated':raise ValueError('财务仅支持已结束完整年/合并口径')
        if (period.month,period.day)!=(12,31):raise ValueError('本入口年度口径须为12月31日；半年/季度不能标作FY计算年度PE')
        if row['period'] in seen:raise ValueError('财务年度重复')
        seen.add(row['period']);values={};lineage={}
        for key in ['revenue','netProfit','adjustedProfit','cfo','rdExpense','customerTop5Pct','fundraisingTotal','workingCapitalUse']:
            val,proof=observation(row.get(key))
            for eid in proof['evidenceIds'] if proof else []:
                if evidence[eid].get('kind')=='table-cell' and evidence[eid].get('period')!=row['period']:raise ValueError('财务观测与证据年度冲突')
            expected='pct' if key=='customerTop5Pct' else 'CNY'
            if proof and proof['unit']!=expected:raise ValueError('字段单位不符:'+key)
            if key=='customerTop5Pct' and val is not None and not 0<=val<=100:raise ValueError('集中度越界')
            values[key]=val;lineage[key]=proof
        def ratio(a,b):return str(a/b*100) if a is not None and b is not None and b>0 else None
        financial.append({'period':row['period'],'values':{k:str(v) if v is not None else None for k,v in values.items()},'lineage':lineage,
            'cfoToNetProfitPct':ratio(values['cfo'],values['netProfit']),
            'nonRecurringProfitSharePct':ratio(values['netProfit']-values['adjustedProfit'] if values['netProfit'] is not None and values['adjustedProfit'] is not None else None,values['netProfit']),
            'rdToRevenuePct':ratio(values['rdExpense'],values['revenue']),
            'workingCapitalUsePct':ratio(values['workingCapitalUse'],values['fundraisingTotal']),
            'signals':['正利润但经营现金流为负，需核查回款与营运资本'] if values['netProfit'] is not None and values['cfo'] is not None and values['netProfit']>0 and values['cfo']<0 else []})
    financial.sort(key=lambda r:r['period'])
    for i,row in enumerate(financial):
        for field in ['revenue','adjustedProfit']:
            prior=financial[i-1] if i else None
            consecutive=prior and int(row['period'][:4])-int(prior['period'][:4])==1 and row['period'][5:]==prior['period'][5:]
            a=row['values'][field];b=prior['values'][field] if consecutive else None
            row[field+'GrowthPct']=str((Decimal(a)/Decimal(b)-1)*100) if a is not None and b is not None and Decimal(b)>0 else None
    price=None;price_proof=None
    if spec.get('factsStore'):
        price_proof=view({'code':code,'asOf':spec['asOf']},Path(spec['factsStore']))['facts']['price']
        price=dec(price_proof['value']) if price_proof else None
    if spec.get('price') is not None:
        supplied,proof=observation(spec['price'])
        if proof['unit']!='CNY':raise ValueError('发行价须CNY/单股，按value说明')
        if price is not None and price!=supplied:raise ValueError('发行价与原文事实冲突')
        price=supplied;price_proof=price_proof or proof
    if price is not None and price<=0:raise ValueError('发行价须正数')
    shares,shareproof=observation(spec.get('postIssueShares'))
    if shares is not None and (shares<=0 or shares!=shares.to_integral_value() or shareproof['unit']!='shares'):raise ValueError('发行后股本须正整股')
    sharebasis=spec.get('shareBasis')
    if shares is not None and sharebasis not in ['before-greenshoe','full-greenshoe']:raise ValueError('发行后股本需明确绿鞋口径')
    selected=next((r for r in financial if r['period']==spec.get('valuationPeriod')),None)
    profit=dec(selected['values']['adjustedProfit']) if selected and selected['values']['adjustedProfit'] is not None else None
    marketcap=price*shares if price is not None and shares is not None else None
    pe=marketcap/profit if marketcap is not None and profit is not None and profit>0 else None
    peers=[];excluded=[]
    for p in spec.get('peers',[]):
        if any(p.get(k)!=v for k,v in {'period':spec.get('valuationPeriod'),'basis':'adjusted-FY-consolidated','currency':'CNY','valuationDate':spec['asOf']}.items()) or not p.get('comparabilityReason'):
            excluded.append({'code':p.get('code'),'reason':'日期、利润口径、币种或可比依据不一致'});continue
        value,proof=observation(p.get('pe'))
        if proof and proof['unit']!='multiple':raise ValueError('同行PE单位须multiple')
        if value is None or value<=0:excluded.append({'code':p.get('code'),'reason':'PE非正或缺失'});continue
        peers.append({'code':p['code'],'pe':str(value),'comparabilityReason':p['comparabilityReason'],'evidence':proof})
    if len({p['code'] for p in peers})!=len(peers):raise ValueError('可比公司重复')
    median=statistics.median([Decimal(p['pe']) for p in peers]) if len(peers)>=3 else None
    topics={k:[e for e in evidence.values() if e['topic']==k] for k in TOPICS}
    gaps += ['缺少原文主题:'+k for k,v in topics.items() if not v]
    if not financial:gaps.append('缺少年度财务数据')
    if pe is None:gaps.append('扣非发行PE不可计算：价格、股本、对应年度或正利润不足')
    if median is None:gaps.append('统一口径可比公司少于3家，不给出相对估值结论')
    gaps.append('文本摘录不核验数值列；table-cell证据已匹配行列、单位和年度，但指标语义映射仍需复核')
    if shareproof and shareproof['verification']=='user-supplied-unverified':gaps.append('发行后股本为输入观测，未逐项原文核验')
    sensitivity=[]
    for scenario in spec.get('profitStress',[]):
        change=dec(scenario['changePct'])
        stressed=profit*(1+change/100) if profit is not None else None
        sensitivity.append({'label':scenario['label'],'profitChangePctAssumption':str(change),'adjustedProfit':str(stressed) if stressed is not None else None,'fixedIssuePricePe':str(marketcap/stressed) if marketcap is not None and stressed is not None and stressed>0 else None,'interpretation':'固定发行价与股本下的盈利敏感性，不是盈利或价格预测'})
    return {'type':'bjx-company-research-card','code':code,'asOf':spec['asOf'],'topics':topics,'financials':financial,
        'valuation':{'issuePrice':str(price) if price is not None else None,'priceEvidence':price_proof,'postIssueShares':str(shares) if shares is not None else None,'shareEvidence':shareproof,'shareBasis':sharebasis,'marketCap':str(marketcap) if marketcap is not None else None,'adjustedFYPe':str(pe) if pe is not None else None,'period':spec.get('valuationPeriod'),'peerMedianPe':str(median) if median else None,'relativePePct':str((pe/median-1)*100) if pe is not None and median else None,'peers':peers,'excludedPeers':excluded},
        'profitSensitivity':sensitivity,'inputSha256':hashlib.sha256(json.dumps(spec,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),'documents':documents,'evidence':evidence,'gaps':gaps,'riskNotice':'仅为基本面与发行定价研究，不构成申购建议；历史盈利不保证未来',
        'limitations':['不输出综合推荐分、破发概率或股价预测','PE比较不等于合理价格或涨幅空间','风险信号不等于财务造假；客户集中与募投补流须结合业务解释','目录披露日期与当前PDF不能证明历史时点可得性']}

def discover(spec):
    import pdfplumber
    asof=dt.date.fromisoformat(spec['asOf']);limit=spec.get('maxPages',30)
    if type(limit)!=int or not 1<=limit<=60:raise ValueError('maxPages仅1至60，默认前30页')
    patterns={'business':'主营业务','customers':'客户集中','fundraising':'募集资金','risks':'风险','inquiry':'问询','financial':'主要财务数据'}
    rows=[];coverage=[]
    for d in spec['documents']:
        if dt.date.fromisoformat(d['publishedAt'])>asof or urlparse(d['sourceUrl']).hostname not in HOSTS:raise ValueError('文档日期或来源不符')
        with pdfplumber.open(d['path']) as pdf:
            front=''.join(compact(p.extract_text()) for p in pdf.pages[:12])
            if compact(d['issuer']) not in front or compact(d['title']) not in front:raise ValueError('发行人或标题不符')
            coverage.append({'documentId':d['id'],'totalPages':len(pdf.pages),'scannedPages':min(limit,len(pdf.pages))})
            for i,page in enumerate(pdf.pages[:limit]):
                text=page.extract_text() or ''
                for topic,term in patterns.items():
                    if term in text:
                        pos=text.index(term);rows.append({'documentId':d['id'],'topic':topic,'page':i+1,'keyword':term,'candidateText':text[max(0,pos-50):pos+700],'status':'candidate-not-reviewed','sourceUrl':d['sourceUrl']})
    return {'type':'bjx-prospectus-candidates','candidates':rows,'coverage':coverage,
            'limitations':['关键词定位可能命中目录或重复章节；不是完整摘要或原文数值核验','默认前30页，未扫描章节不能宣称无风险或无问询','选定摘录与表格后再调用研究卡核验']}

def main():
    p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--out',type=Path,required=True);p.add_argument('--discover',action='store_true');a=p.parse_args()
    if a.out.exists():raise ValueError('输出存在')
    spec=json.loads(a.input.read_text(encoding='utf-8-sig'));r=discover(spec) if a.discover else run(spec);a.out.parent.mkdir(parents=True,exist_ok=True)
    with a.out.open('x',encoding='utf-8') as f:json.dump(r,f,ensure_ascii=False,indent=2,allow_nan=False)
if __name__=='__main__':main()
