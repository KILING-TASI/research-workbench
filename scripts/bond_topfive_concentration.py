"""Check disclosed top-five arithmetic and original quotes, not full credit risk."""
import argparse, hashlib, json, re
from pathlib import Path
from decimal import Decimal
from cash_flow_reconciliation import number as monetary_decimal

def amount(value):
    if isinstance(value,bool) or not isinstance(value,(str,int,float)):raise ValueError('金额或比例数值类型无效')
    result=monetary_decimal(value) if isinstance(value,str) else Decimal(str(value))
    if not result.is_finite() or result<0:raise ValueError('金额或比例须为非负有限数')
    return result

def check_quote_fields(row):
    quote=row['originalQuote'].strip()
    if 'code' in row:
        match=re.fullmatch(r'([1-5])\s+(\d{6})\s+(.+?)\s+([\d,]+)\s+([\d,]+\.\d{2})\s+(\d+\.\d{2})',quote)
        if not match:raise ValueError('引句不是可识别的前五名原表行')
        if int(match[1])!=row['rank'] or match[2]!=row['code'] or amount(match[5])!=amount(row['amountCNY']) or amount(match[6])!=amount(row['reportedNAVPercentage']):
            raise ValueError('排名、代码、金额或比例与原行不一致')
    else:
        match=re.fullmatch(r'10\s+合计\s+([\d,]+\.\d{2})\s+(\d+\.\d{2})',quote)
        if not match or amount(match[1])!=amount(row['amountCNY']):
            raise ValueError('分母与债券品种合计原行不一致')

def calculate(spec):
    if not isinstance(spec,dict):raise ValueError('债券集中度输入须为对象')
    if spec.get('denominatorBasis')!='disclosed-bond-portfolio':
        raise ValueError('分母须明确为披露债券组合金额，不混用净资产')
    denominator=amount(spec['bondPortfolioAmountCNY'])
    if denominator<=0:raise ValueError('债券分母须大于零')
    rows=spec['entries']
    if not isinstance(rows,list) or len(rows)!=5 or any(not isinstance(r,dict) or type(r.get('rank')) is not int for r in rows) or [r.get('rank') for r in rows]!=[1,2,3,4,5]:
        raise ValueError('须提供连续前五名，不补缺行')
    codes=[r.get('code') for r in rows]
    if any(not isinstance(c,str) or not re.fullmatch(r'\d{6}',c) for c in codes) or len(set(codes))!=5:
        raise ValueError('债券代码须为不同的六位字符串；其他代码格式暂不支持')
    values=[amount(r['amountCNY']) for r in rows]
    if any(values[i]<values[i+1] for i in range(4)):raise ValueError('公允价值顺序与排名不一致')
    total=sum(values,Decimal(0))
    if total>denominator:raise ValueError('前五名合计超过债券组合分母')
    percentages=[amount(r['reportedNAVPercentage']) for r in rows]
    return dict(topFiveAmountCNY=str(total),topFiveBondPortfolioPercentage=str(total/denominator*100),topFiveReportedNAVPercentageSum=str(sum(percentages,Decimal(0))),scope='仅披露前五名集中度；净资产比例为原报告舍入值之和，不代表完整发行人集中度或信用评级')

def verify_original(spec,base):
    from pypdf import PdfReader
    from pdf_structure_review import review
    path=Path(spec['sourcePath'])
    if not path.is_absolute():path=base/path
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    if digest!=spec['sourceSha256']:raise ValueError('原件哈希变化')
    structure=review(path)
    if structure['reviewRequired']:raise ValueError('原件结构待复核，不输出已核集中度')
    reader=PdfReader(path)
    compact=lambda s:re.sub(r'\s+','',s)
    denominator=spec['denominatorOriginal']
    checks=list(spec['entries'])+[dict(physicalPage=denominator['physicalPage'],originalQuote=denominator['originalQuote'],amountCNY=spec['bondPortfolioAmountCNY'])]
    for row in checks:
        page=row['physicalPage'];quote=row['originalQuote']
        if isinstance(page,bool) or not isinstance(page,int) or not 1<=page<=len(reader.pages):raise ValueError('原页超界')
        if not isinstance(quote,str) or not quote.strip() or compact(quote) not in compact(reader.pages[page-1].extract_text() or ''):raise ValueError('引句不在原页')
        check_quote_fields(row)
    return dict(path=str(path.resolve()),sha256=digest,structureReview=structure,scope='核对指定页文字及逐行字段；不认证官方原件、表格完整或债券身份')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('input');parser.add_argument('--out',required=True)
    args=parser.parse_args();p=Path(args.input);spec=json.loads(p.read_text(encoding='utf-8'))
    result=calculate(spec);source=verify_original(spec,p.resolve().parent)
    payload=dict(inputSha256=hashlib.sha256(p.read_bytes()).hexdigest(),result=result,source=source)
    with Path(args.out).open('x',encoding='utf-8') as f:json.dump(payload,f,ensure_ascii=False,indent=2)

if __name__=='__main__':main()
