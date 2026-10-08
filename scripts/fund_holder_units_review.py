"""Cross-check holder units against disclosed share movements, never cash flows."""
import argparse,json,hashlib,re,datetime
from pathlib import Path
from decimal import Decimal
from collection_validation import unique_pairs,reject_constant,finite_json_float

def strict_json(text):
    return json.loads(text,object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float)
from cash_flow_reconciliation import number as monetary_decimal

def number(value):
    if isinstance(value,bool) or not isinstance(value,(str,int,float)):raise ValueError('份额和比例数值类型无效')
    n=monetary_decimal(value) if isinstance(value,str) else Decimal(str(value))
    if not n.is_finite() or n<0:raise ValueError('份额和比例须为非负有限数')
    return n

def signed_number(value):
    if isinstance(value,bool) or not isinstance(value,(str,int,float)):raise ValueError('拆分数量类型无效')
    n=monetary_decimal(value) if isinstance(value,str) else Decimal(str(value))
    if not n.is_finite():raise ValueError('拆分变动须为有限数')
    return n

def disclosed_number(token,policy='reject',percentage=False):
    if policy not in ('reject','assumed-zero-for-explicit-dash'):raise ValueError('破折号解释声明无效')
    if token in ('-','－','—'):
        if policy=='reject':raise ValueError('原文破折号含义未核，不自动填零')
        return Decimal(0)
    if not isinstance(token,str):raise ValueError('原文数字须为文字')
    if token.endswith('%'):
        if not percentage:raise ValueError('份额数量不能使用百分比')
        token=token[:-1]
    return monetary_decimal(token)

def explicit_flow_residual(flows,order):
    """Arithmetic on four explicit fields; never resolve an unknown split symbol."""
    if not isinstance(flows,dict) or not isinstance(flows.get('flowRows'),dict):raise ValueError('需结构化份额变动输入')
    if not isinstance(order,list) or not order or any(not isinstance(x,str) or not x.strip() for x in order) or len(order)!=len(set(order)):raise ValueError('份额类别须明确且不重复')
    rows=flows['flowRows'];required={'opening':'期初','closing':'期末','subscription':'申购','redemption':'赎回'}
    values={}
    for key,label in required.items():
        row=rows.get(key)
        if not isinstance(row,dict) or not isinstance(row.get('label'),str) or label not in row['label'] or not isinstance(row.get('values'),list) or len(row['values'])!=len(order):raise ValueError('明确份额行缺失、标签或列数不一致：'+key)
        values[key]=[number(v) for v in row['values']]
    result=[]
    for i,share in enumerate(order):
        residual=values['closing'][i]-values['opening'][i]-values['subscription'][i]+values['redemption'][i]
        result.append(dict(shareClass=share,unexplainedNetShareMovement=str(residual),explicitFieldsNetConsistent=residual==0,splitReportedValue=None,splitEventAbsenceVerified=False))
    return dict(classes=result,status='explicit-four-field-arithmetic-only',originalVerification='not-performed-by-this-function',formula='closing - opening - subscription + redemption',limitations=['净残差为零不证明无拆分或没有抵消变化；不得回填拆分栏','输入份额不是现金资金流，未核原页、申赎时点或完整事件'])

def calculate(holders,flows,order):
    if holders['code']!=flows['code'] or holders['reportDate']!=flows['reportDate'] or holders['sourceSha256']!=flows['sourceSha256']:raise ValueError('代码、报告期或来源不一致')
    datetime.date.fromisoformat(holders['reportDate'])
    if not isinstance(order,list) or not order or any(not isinstance(x,str) or not x.strip() for x in order) or len(set(order))!=len(order):raise ValueError('份额类别顺序须为非空且不重复文字列表')
    rows=flows['flowRows']
    if set(rows)!={'opening','closing','subscription','redemption','split'}:raise ValueError('份额变动缺行，不填零')
    labels={'opening':'期初','closing':'期末','subscription':'申购','redemption':'赎回','split':'拆分'}
    if any(labels[k] not in row.get('label','') for k,row in rows.items()):raise ValueError('份额变动行名与计算项目不对应')
    if any(len(r['values'])!=len(order) for r in rows.values()):raise ValueError('类别数量与份额列不一致')
    leaves=[h for h in holders['entries'] if h['shareClass']!='合计']
    if len(leaves)!=len(order):raise ValueError('持有人与份额类别覆盖不同')
    totals=[h for h in holders['entries'] if h['shareClass']=='合计']
    if len(totals)>1:raise ValueError('持有人合计行重复')
    for total in totals:
        for field in ('institutionUnits','personalUnits','totalUnits'):
            if number(total[field])!=sum((number(row[field]) for row in leaves),Decimal(0)):raise ValueError('持有人合计与各类别不一致')
    output=[]
    for i,share in enumerate(order):
        matches=[h for h in leaves if h['shareClass'].endswith(share)]
        if len(matches)!=1:raise ValueError('份额类别歧义')
        holder=matches[0];inst=number(holder['institutionUnits']);personal=number(holder['personalUnits']);total=inst+personal
        if total<=0:raise ValueError('持有人份额总数为零')
        v={k:(signed_number(r['values'][i]) if k=='split' else number(r['values'][i])) for k,r in rows.items()}
        if v['opening']+v['subscription']-v['redemption']+v['split']!=v['closing']:raise ValueError('份额变动不勾稽')
        if total!=v['closing'] or number(holder['totalUnits'])!=total:raise ValueError('持有人份额与期末份额不一致')
        if abs(inst/total*100-number(holder['reportedInstitutionPercentage']))>Decimal('0.0051') or abs(personal/total*100-number(holder['reportedPersonalPercentage']))>Decimal('0.0051'):raise ValueError('原披露比例与份额分母不匹配')
        output.append(dict(shareClass=share,closingUnits=str(total),institutionPercentage=str(inst/total*100),personalPercentage=str(personal/total*100),holderVsClosingDifferenceUnits='0',netShareChangeUnits=str(v['closing']-v['opening']),netShareChangePercentage=str((v['closing']/v['opening']-1)*100) if v['opening'] else None))
    return dict(code=holders['code'],reportDate=holders['reportDate'],classes=output,scope='份额数量与披露比例核对；类别顺序须按原表复查，非净资金流、去重人数或流动性安全')

def verify_tables(holders,flows):
    import pdfplumber
    from pdf_structure_review import review
    path=Path(holders['sourcePath']);digest=hashlib.sha256(path.read_bytes()).hexdigest()
    if digest!=holders['sourceSha256'] or digest!=flows['sourceSha256'] or holders['code']!=flows['code'] or holders['reportDate']!=flows['reportDate'] or Path(flows['sourcePath']).resolve()!=path.resolve():raise ValueError('原件路径或哈希不一致')
    structure=review(path)
    if structure['reviewRequired']:raise ValueError('原件结构待复核')
    compact=lambda v:re.sub(r'\s+','',v or '')
    cache={};dash_assumptions=[]
    with pdfplumber.open(path) as doc:
        front='\n'.join(page.extract_text() or '' for page in doc.pages[:12]);compact_front=compact(front)
        if not re.search(r'(?<!\d)'+re.escape(holders['code'])+r'(?!\d)',front):raise ValueError('原报告前页代码未匹配')
        titles=set(re.findall(r'(20\d{2})年(中期|年度)报告',compact(''.join(page.extract_text() or '' for page in doc.pages[:3]))))
        if len(titles)!=1:raise ValueError('原件年份及报告类型未唯一确认')
        year,kind=next(iter(titles));expected_period=year+('-06-30' if kind=='中期' else '-12-31')
        if holders['reportDate']!=expected_period:raise ValueError('声明期末与原件报告年份不一致')
        for row in list(holders['entries'])+list(flows['flowRows'].values()):
            n=row['physicalPage'];bbox=row['tableBBox']
            if isinstance(n,bool) or not isinstance(n,int) or not 1<=n<=len(doc.pages):raise ValueError('原页越界')
            if n not in cache:cache[n]=doc.pages[n-1].find_tables()
            tables=[t for t in cache[n] if len(bbox)==4 and all(abs(a-b)<0.001 for a,b in zip(t.bbox,bbox))]
            if len(tables)!=1:raise ValueError('原表坐标未唯一匹配')
            expected=[compact(c) for c in row['originalCells'] if compact(c)]
            if expected not in [[compact(c) for c in r if compact(c)] for r in tables[0].extract()]:raise ValueError('归档行与PDF原表不一致')
            policy=(holders if 'shareClass' in row else flows).get('dashPolicy','reject')
            if any(value in ('-','－','—') for value in expected[1:]):dash_assumptions.append(dict(physicalPage=n,policy=policy,originalCells=row['originalCells']))
            parse=lambda x,percentage=False:disclosed_number(x,policy,percentage)
            if 'shareClass' in row:
                if len(expected)!=7 or expected[0]!=row['shareClass']:raise ValueError('持有人原行类别未对应')
                for field,index in [('institutionUnits',3),('reportedInstitutionPercentage',4),('personalUnits',5),('reportedPersonalPercentage',6)]:
                    if number(row[field])!=parse(expected[index],index in (4,6)):raise ValueError('持有人字段与原行不一致')
                if number(row['totalUnits'])!=parse(expected[3])+parse(expected[5]):raise ValueError('持有人总份额与原行不一致')
                for field,index in [('holderCount',1),('reportedAverageUnits',2)]:
                    if field in row and number(row[field])!=parse(expected[index]):raise ValueError('持有人数量字段与原行不一致')
            else:
                if expected[0]!=row['label']:raise ValueError('份额变动标签与原行不一致')
                convert=signed_number if '拆分' in row['label'] else number
                if [convert(v) for v in row['values']]!=[parse(c) for c in expected[1:]]:raise ValueError('份额字段与原行不一致')
    return dict(path=str(path.resolve()),sha256=digest,structureReview=structure,dashAssumptions=dash_assumptions,status='conditional-with-dash-assumption' if dash_assumptions else 'original-row-fields-matched',scope='所选原表坐标和行字段核对；非官方真实性或完整报告认证，破折号假设不升级为披露零值')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('input');parser.add_argument('--out',required=True);args=parser.parse_args();p=Path(args.input).resolve();spec=strict_json(p.read_text(encoding='utf-8-sig'));dependencies=[]
    def read(name):
        q=Path(spec[name]);q=q if q.is_absolute() else p.parent/q;dependencies.append(dict(path=str(q.resolve()),sha256=hashlib.sha256(q.read_bytes()).hexdigest()));data=strict_json(q.read_text(encoding='utf-8-sig'))
        original=Path(data['sourcePath']);data['sourcePath']=str(original if original.is_absolute() else (q.resolve().parent/original).resolve())
        return data
    holders=read('holderSnapshot');flows=read('shareFlowSnapshot');result=calculate(holders,flows,spec['shareClassOrder']);source=verify_tables(holders,flows)
    with Path(args.out).open('x',encoding='utf-8') as f:json.dump(dict(result=result,source=source,dependencies=dependencies),f,ensure_ascii=False,indent=2)
if __name__=='__main__':main()
