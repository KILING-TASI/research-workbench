"""Extract complete §7/8.12.2 FOF holdings and reconcile cents."""
import hashlib,re
from collection_validation import unique_pairs,reject_constant
from decimal import Decimal
from pathlib import Path
import pdfplumber
from verify_original import compact,dates_in

def money(s):
    value=Decimal(compact(s).replace(',',''))
    if not value.is_finite():raise ValueError('基金投资金额或比例不是有限数值')
    return value
def extract(pdf,metadata):
    raw=Path(pdf).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=metadata['sha256']:raise ValueError('原文哈希不符')
    rows=[];started=False;finished=False;section=None
    with pdfplumber.open(pdf) as doc:
        front=''.join(compact(x.extract_text()) for x in doc.pages[:8])
        for key in ['title','issuer']:
            if not metadata.get(key) or compact(metadata[key]) not in front:raise ValueError('标题/发行人不符')
        if metadata['reportDate'] not in dates_in(front) or metadata['publishedAt'] not in dates_in(doc.pages[0].extract_text()):raise ValueError('封面日期不符')
        if not re.search(r'基金主代码'+re.escape(metadata['code']),front):raise ValueError('主代码不符')
        for page_no,page in enumerate(doc.pages,1):
            text=page.extract_text() or ''
            starts=page.search(r'[78]\.12\.2\s*报告期末按公允价值')
            if starts:started=True;section=starts[0]['text'][0]
            if not started:continue
            ends=page.search(re.escape(section)+r'\.13\s*投资组合报告附注');bottom=ends[0]['top'] if ends else float('inf')
            for table in page.find_tables():
                if table.bbox[1]>=bottom or (starts and table.bbox[1]<starts[0]['top']):continue
                for c in table.extract():
                    if len(c)!=8:continue
                    cells=[compact(x) for x in c]
                    if cells[0].isdigit() and re.fullmatch(r'\d{6}',cells[1]):rows.append({'cells':cells,'pages':[page_no]})
                    elif rows and not cells[0] and not cells[1] and any(cells[2:]):
                        for i in range(2,8):rows[-1]['cells'][i]+=cells[i]
                        rows[-1]['pages'].append(page_no)
            if ends:finished=True;break
    if not started or not finished or not rows:raise ValueError('完整基金表边界缺失')
    nav=Decimal(str(metadata['netAssetsCNY']));expected=Decimal(str(metadata['fundInvestmentCNY']))
    if not nav.is_finite() or not expected.is_finite() or nav<=0 or expected<0:raise ValueError('非法分母或总值')
    holdings=[];seen=set()
    for rank,r in enumerate(rows,1):
        c=r['cells']
        if int(c[0])!=rank or c[1] in seen:raise ValueError('序号缺失或代码重复')
        seen.add(c[1]);value=money(c[5]);quantity=money(c[4]);shown=money(c[6])
        if value<0 or quantity<0 or shown<0 or abs(value/nav*100-shown)>Decimal('.00501'):raise ValueError('金额/权重分母不匹配')
        holdings.append({'rank':rank,'code':c[1],'name':c[2],'quantity':str(quantity),'marketValueCNY':str(value),'reportedWeightPct':str(shown),'weight':float(value/nav),'locator':'PDF页'+','.join(map(str,r['pages'])),'originalCells':c})
    total=sum((Decimal(h['marketValueCNY']) for h in holdings),Decimal(0))
    if total!=expected:raise ValueError('基金投资总额逐分勾稽不通过')
    return {**metadata,'holdings':holdings,'count':len(holdings),'fundInvestmentReconciledCNY':str(total),'verification':'完整序号、逐行金额与权重、表合计勾稽','limitations':['子基金不同份额须核对是否共用资产池','未自动取得全部子基金报告；前十大不替代完整披露','净资产分母，其他资产负债残余不推定现金']}


if __name__=='__main__':
    import argparse,json
    p=argparse.ArgumentParser();p.add_argument('pdf');p.add_argument('--metadata',required=True);p.add_argument('--out',required=True);a=p.parse_args()
    if Path(a.out).exists():raise FileExistsError('不覆盖首次结果')
    result=extract(a.pdf,json.loads(Path(a.metadata).read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant))
    with Path(a.out).open('x',encoding='utf8') as f:json.dump(result,f,ensure_ascii=False,indent=2,allow_nan=False)
