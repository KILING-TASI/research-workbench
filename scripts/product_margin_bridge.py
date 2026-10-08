"""Disclosed product mix / within-group margin arithmetic, not economic causality."""
import argparse,json,hashlib,re,datetime
from pathlib import Path
from decimal import Decimal
from cash_flow_reconciliation import number as monetary_decimal
from collection_validation import day,unique_pairs,reject_constant

def number(v):
    if isinstance(v,bool) or not isinstance(v,(str,int,float)):raise ValueError('收入成本数值类型无效')
    x=monetary_decimal(v) if isinstance(v,str) else Decimal(str(v))
    if not x.is_finite() or x<0:raise ValueError('收入成本须为非负有限数')
    return x

def check_row(row,label):
    quote=row['quote'];compact=lambda s:re.sub(r'\s+','',s)
    if row.get('name',label)!=label or not compact(quote).startswith(compact(label)):raise ValueError('产品名或合计标签与原行不一致')
    tokens=[monetary_decimal(x) for x in re.findall(r'(?<![\d.,eE+\-−－])-?\d[\d,]*\.\d{2}(?![\d.,eE%％])',quote)]
    pair=row.get('amountColumnPair','current')
    if pair not in ('current','prior'):raise ValueError('金额列组须明确为current或prior')
    selected=tokens[:2] if pair=='current' else tokens[2:4]
    if pair=='prior' and len(tokens)!=4:raise ValueError('比较列须为明确四金额行')
    if len(selected)!=2 or selected!=[number(row['revenueCNY']),number(row['costCNY'])]:raise ValueError('收入与成本须按原行前两金额顺序一致，不互换或匹配其他字段；比较列另按第三第四金额核对')

def check_report_period(period,front):
    rows=list(period['items'].values())+[period['total']]
    pairs={row.get('amountColumnPair','current') for row in rows}
    if len(pairs)!=1 or not pairs.issubset({'current','prior'}):raise ValueError('同一期不得混用本期与上期列')
    basis=period['periodBasis'];definitions={'half-year':('半年度报告',6,30),'full-year':('年度报告',12,31)}
    if basis not in definitions:raise ValueError('原文期间核对暂限自然年半年报与年报')
    title,month,day=definitions[basis];text=re.sub(r'\s+','',front)
    years=set(re.findall(r'(20\d{2})年'+title,text))
    if len(years)!=1:raise ValueError('原件报告年份与类型未唯一确认')
    expected=int(next(iter(years)))-(1 if 'prior' in pairs else 0)
    actual=datetime.date.fromisoformat(period['period'])
    if actual!=datetime.date(expected,month,day):raise ValueError('声明期间与原件年份及本期/上期列不一致')

def calculate(spec):
    if not isinstance(spec,dict):raise ValueError('产品毛利输入须为对象')
    if spec.get('currency')!='CNY' or spec.get('unit')!='元':raise ValueError('当前入口只接受人民币元')
    if spec.get('groupMappingReviewed') is not True or not isinstance(spec.get('comparabilityNotes'),str) or not spec['comparabilityNotes'].strip():raise ValueError('须明确产品分组对应关系及可比性限制')
    periods=spec['periods']
    if not isinstance(periods,list) or len(periods)!=2 or any(not isinstance(p,dict) or not isinstance(p.get('items'),dict) or not isinstance(p.get('total'),dict) for p in periods):raise ValueError('只接受两期完整分组对象')
    old,new=periods
    if day(old.get('period'))>=day(new.get('period')):raise ValueError('报告期须由早到晚')
    if not old.get('periodBasis') or old['periodBasis']!=new.get('periodBasis'):raise ValueError('累计期间口径不一致')
    if set(old['items'])!=set(new['items']) or not old['items']:raise ValueError('两期产品分组不同，不自动配对或补零')
    totals=[]
    for period in periods:
        for field in ('revenueCNY','costCNY'):
            total=number(period['total'][field])
            if sum((number(r[field]) for r in period['items'].values()),Decimal(0))!=total:raise ValueError('分产品金额与合计不一致：'+field)
        revenue=number(period['total']['revenueCNY'])
        if revenue<=0 or any(number(r['revenueCNY'])<=0 for r in period['items'].values()):raise ValueError('收入为零，不能计算产品毛利率')
        totals.append((revenue-number(period['total']['costCNY']))/revenue)
    mix=Decimal(0);within=Decimal(0);rows=[]
    for name in old['items']:
        a=old['items'][name];b=new['items'][name]
        r0=number(a['revenueCNY']);r1=number(b['revenueCNY']);w0=r0/number(old['total']['revenueCNY']);w1=r1/number(new['total']['revenueCNY']);m0=(r0-number(a['costCNY']))/r0;m1=(r1-number(b['costCNY']))/r1
        x=(w1-w0)*m0;y=w1*(m1-m0);mix+=x;within+=y
        rows.append(dict(name=name,priorRevenueWeight=str(w0),currentRevenueWeight=str(w1),priorGrossMargin=str(m0),currentGrossMargin=str(m1),mixContributionPercentagePoints=str(x*100),withinContributionPercentagePoints=str(y*100)))
    residual=totals[1]-totals[0]-mix-within
    if abs(residual)>Decimal('1e-24'):raise ValueError('分解与整体毛利率变化不勾稽')
    return dict(priorGrossMargin=str(totals[0]),currentGrossMargin=str(totals[1]),changePercentagePoints=str((totals[1]-totals[0])*100),mixContributionPercentagePoints=str(mix*100),withinContributionPercentagePoints=str(within*100),residual=str(residual),rows=rows,formula='Σ(本期权重−上期权重)×上期毛利率 + Σ本期权重×(本期−上期毛利率)',scope='分组算术且路径相关；可比性为调用者复查声明，不认证量价、客户或并表因果')

def verify_sources(spec,base):
    from pypdf import PdfReader
    from pdf_structure_review import review
    dependencies=[]
    for period in spec['periods']:
        p=Path(period['sourcePath']);p=p if p.is_absolute() else base/p
        digest=hashlib.sha256(p.read_bytes()).hexdigest()
        if digest!=period['sourceSha256']:raise ValueError('原件哈希变化')
        structure=review(p)
        if structure['reviewRequired']:raise ValueError('原件结构待复核')
        reader=PdfReader(p)
        check_report_period(period,'\n'.join(page.extract_text() or '' for page in reader.pages[:3]))
        if any(row.get('amountColumnPair')=='prior' for row in list(period['items'].values())+[period['total']]):
            header=period.get('columnHeader',{});n=header.get('physicalPage');q=header.get('quote','');compact=lambda s:re.sub(r'\s+','',s)
            if isinstance(n,bool) or not isinstance(n,int) or not 1<=n<=len(reader.pages) or not q or compact(q) not in compact(reader.pages[n-1].extract_text() or ''):raise ValueError('比较列表头原页未确认')
            if '本期发生额' not in q or '上期发生额' not in q or q.index('本期发生额')>=q.index('上期发生额') or '收入成本收入成本' not in compact(q):raise ValueError('比较列收入成本顺序不明确')
        for label,row in list(period['items'].items())+[('合计',period['total'])]:
            n=row['physicalPage'];quote=row['quote']
            if isinstance(n,bool) or not isinstance(n,int) or not 1<=n<=len(reader.pages):raise ValueError('原页越界')
            if not quote or re.sub(r'\s+','',quote) not in re.sub(r'\s+','',reader.pages[n-1].extract_text() or ''):raise ValueError('引句不在原页')
            check_row(row,label)
        dependencies.append(dict(path=str(p.resolve()),sha256=digest,structureReview=structure))
    return dependencies

def main():
    parser=argparse.ArgumentParser();parser.add_argument('input');parser.add_argument('--out',required=True);args=parser.parse_args();p=Path(args.input).resolve();spec=json.loads(p.read_text(encoding='utf-8'),object_pairs_hook=unique_pairs,parse_constant=reject_constant)
    result=calculate(spec);sources=verify_sources(spec,p.parent)
    with Path(args.out).open('x',encoding='utf-8') as f:json.dump(dict(result=result,sources=sources,inputSha256=hashlib.sha256(p.read_bytes()).hexdigest(),comparabilityNotes=spec['comparabilityNotes']),f,ensure_ascii=False,indent=2)
if __name__=='__main__':main()
