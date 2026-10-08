"""Extract annual report profit statement §7.2 to §7.3, with exact reconciliation.
Requires pdfplumber. Report identity/dates must be verified separately by caller.
Does not infer investor returns, fee rates, trades or performance attribution.
"""
from pathlib import Path
from decimal import Decimal
import re,json,hashlib,argparse
import pdfplumber
from datetime import date
from collection_validation import unique_pairs,reject_constant

def clean(s):return re.sub(r'\s+','',s or '')
def statement_amount(token,policy='reject'):
 if policy not in ('reject','assumed-zero-for-explicit-dash'):raise ValueError('利润表破折号口径无效')
 if token=='-':
  if policy=='reject':raise ValueError('利润表破折号含义未确认，不能自动填零')
  return Decimal(0)
 if not re.fullmatch(r'-?(?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2}',token):raise ValueError('利润表金额格式无效')
 return Decimal(token.replace(',',''))
def validate_metadata(metadata):
 if not isinstance(metadata,dict):raise ValueError('利润表元数据须为对象')
 for key in ('periodStart','periodEnd','publishedAt'):
  value=metadata.get(key)
  if not isinstance(value,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',value):raise ValueError('利润表日期缺失或格式无效：'+key)
  date.fromisoformat(value)
 if metadata['periodStart']>metadata['periodEnd'] or metadata['publishedAt']<metadata['periodEnd']:raise ValueError('利润表期间或披露日期顺序无效')
 if metadata.get('reportDate',metadata['periodEnd'])!=metadata['periodEnd']:raise ValueError('利润表截止日与报告日期不一致')

def verify_currency_unit(text):
 units=re.findall(r'(?:金额)?单位[:：]?(人民币(?:亿元|万元|千元|元))',clean(text))
 if not units or set(units)!={'人民币元'}:raise ValueError('利润表人民币元单位未确认或存在冲突，不能直接输出amountCNY')

def extract(pdf,metadata):
 validate_metadata(metadata)
 policy=metadata.get('dashPolicy','reject');statement_amount('0.00',policy)
 rows=[];started=finished=False;statement_text=[]
 with pdfplumber.open(pdf) as doc:
  for number,page in enumerate(doc.pages,1):
   text=page.extract_text() or ''
   if re.search(r'^7\.2\s*利润表\s*$',text,re.M):started=True
   if not started or finished:continue
   statement_text.append(text)
   ends=page.search(r'7\.3\s*净资产变动表');end_top=ends[0]['top'] if ends else float('inf')
   for table in page.find_tables():
    if table.bbox[1]>=end_top:continue
    for c in table.extract():
     if len(c)!=4:continue
     c=[clean(x) for x in c]
     if not re.fullmatch(r'-?\d[\d,]*\.\d{2}|-',c[2]):continue
     rows.append({'label':c[0],'amount':statement_amount(c[2],policy),'reportedEmpty':c[2]=='-','locator':'PDF页'+str(number)})
   if ends:finished=True;break
 if not started or not finished:raise ValueError('未取得完整利润表正文边界')
 verify_currency_unit('\n'.join(statement_text))
 def pick(prefix):
  selected=[r for r in rows if r['label'].replace('．','.').startswith(prefix.replace('．','.'))]
  if len(selected)!=1:raise ValueError('利润表字段缺失/重复：'+prefix)
  r=selected[0];return {'name':r['label'],'amountCNY':str(r['amount']),'reportedEmpty':r['reportedEmpty'],'locator':r['locator']}
 income=[pick(prefix) for prefix in ['1.利息收入','2.投资收益','3.公允价值变动收益','4.汇兑收益','5.其他收入']]
 expenses=[pick(prefix) for prefix in ['1．管理人报酬','2．托管费','3．销售服务费','4．投资顾问费','5．利息支出','6．信用减值损失','7．税金及附加','8．其他费用']]
 investmentDetails=[pick(prefix) for prefix in ['其中：股票投资收益','基金投资收益','债券投资收益','资产支持证券投资收益','贵金属投资收益','衍生工具收益','股利收益','其他投资收益']]
 totals={key:pick(prefix) for key,prefix in [('income','一、营业总收入'),('expenses','减：二、营业总支出'),('profitBeforeTax','三、利润总额'),('incomeTax','减：所得税费用'),('netProfit','四、净利润')]}
 total=lambda items:sum((Decimal(i['amountCNY']) for i in items),Decimal(0))
 if total(income)!=Decimal(totals['income']['amountCNY']) or total(expenses)!=Decimal(totals['expenses']['amountCNY']):raise ValueError('收支明细与总额不一致')
 if total(investmentDetails)!=Decimal(income[1]['amountCNY']):raise ValueError('投资收益子项与父项不一致；存在未支持科目，不补猜')
 if Decimal(totals['income']['amountCNY'])-Decimal(totals['expenses']['amountCNY'])!=Decimal(totals['profitBeforeTax']['amountCNY']):raise ValueError('营业收支与税前利润不一致')
 if Decimal(totals['profitBeforeTax']['amountCNY'])-Decimal(totals['incomeTax']['amountCNY'])!=Decimal(totals['netProfit']['amountCNY']):raise ValueError('所得税与净利润不一致')
 return {**metadata,'currency':'CNY','statementScope':'fund-all-share-classes','income':income,'investmentDetails':investmentDetails,'expenses':expenses,'totals':totals,'dashAssumptions':[dict(label=r['label'],locator=r['locator'],interpretation='conditional-assumed-zero') for r in rows if r['reportedEmpty']],'status':'conditional-dash-assumption' if any(r['reportedEmpty'] for r in rows) else 'selected-statement-reconciled','sourceSha256':hashlib.sha256(Path(pdf).read_bytes()).hexdigest(),'note':'仅当期利润表；上年可比列未作为冻结历史。破折号采用零值假设时仅为条件勾稽，不认证原文零值。投资收益中包括股利，不能把股利与投资收益再相加；费用已进入基金净值，不从投资者净值收益重复扣除。'}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('pdf');p.add_argument('--metadata',required=True);p.add_argument('--out',required=True);a=p.parse_args()
 if Path(a.out).exists():raise FileExistsError('不得覆盖首次结果')
 r=extract(a.pdf,json.loads(Path(a.metadata).read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant))
 with Path(a.out).open('x',encoding='utf8') as f:json.dump(r,f,ensure_ascii=False,indent=2)
