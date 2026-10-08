"""Selected paid-in-fund quantity column; never infer settlement cash flow."""
import argparse,json,re,hashlib
from decimal import Decimal
from pathlib import Path
from fund_holder_units_review import signed_number
from verify_original import compact,dates_in
from pdf_structure_review import review
from collection_validation import day,unique_pairs,reject_constant

def parse(rows,dash_policy='reject'):
 if dash_policy not in ('reject','assumed-zero-for-explicit-dash'):raise ValueError('破折号解释声明无效')
 if not isinstance(rows,list) or len(rows)<6 or any(not isinstance(row,list) or len(row)!=3 for row in rows):raise ValueError('仅支持三列完整实收基金表')
 heading=[compact(x) for x in rows[1]]
 if heading[1]!='基金份额（份）' or heading[2]!='账面金额':raise ValueError('份额数量列与账面金额列未确认')
 values={};dash_rows=[];labels={'上年度末':'opening','本期申购':'subscription','本期末':'closing'}
 for row in rows[2:]:
  name=compact(row[0]);key=labels.get(name)
  if re.fullmatch(r'本期赎回[（(]以[“"‘\']?[-－][”"’\']?号填列[）)]',name):key='redemption-signed'
  if not key or key in values:raise ValueError('实收基金行缺失、重复或未支持，不忽略额外行')
  token=compact(row[1]).replace(',','')
  if token in ('-','—','－'):
   if dash_policy=='reject':raise ValueError('数量为破折号，含义未核；默认不当零')
   n=Decimal(0);dash_rows.append(key)
  else:
   if not re.fullmatch(r'-?\d+\.\d{2}',token):raise ValueError('份额原行不是明确两位数量')
   n=signed_number(token)
  if (key=='redemption-signed' and n>0) or (key!='redemption-signed' and n<0):raise ValueError('数量正负方向与行名不符')
  values[key]=n
 if set(values)!=set(['opening','subscription','redemption-signed','closing']):raise ValueError('实收基金四行不完整')
 delta=values['closing']-values['opening'];difference=values['opening']+values['subscription']+values['redemption-signed']-values['closing']
 if difference:raise ValueError('份额数量未勾稽，不用账面金额替代')
 return {'values':{k:str(v) for k,v in values.items()},'netShareChange':str(delta),'changePct':str(delta/values['opening']*100) if values['opening'] else None,'ledgerDifference':'0','rawRows':rows,'dashRows':dash_rows,'dashPolicy':dash_policy,'status':'conditional-reconciliation-with-dash-assumption' if dash_rows else 'explicit-quantity-reconciliation','scope':'原文实收基金份额列，非账面金额、真实现金流或投资者收益；破折号按零解释仅在明确声明假设时使用，空白不填零。'}

def run(spec,base):
 if not isinstance(spec,dict):raise ValueError('份额核验输入须为对象')
 if not isinstance(spec.get('path'),str) or not spec['path'].strip():raise ValueError('原文路径缺失')
 if not isinstance(spec.get('sha256'),str) or not re.fullmatch(r'[0-9a-f]{64}',spec['sha256']):raise ValueError('原文哈希须为64位小写十六进制')
 if not isinstance(spec.get('code'),str) or not re.fullmatch(r'\d{6}',spec['code']):raise ValueError('代码须为六位字符串')
 if day(spec.get('start'))>day(spec.get('end')):raise ValueError('份额期间起止倒置')
 if type(spec.get('page')) is not int or spec['page']<1:raise ValueError('物理页无效')
 if spec.get('dashPolicy','reject') not in ('reject','assumed-zero-for-explicit-dash'):raise ValueError('破折号解释声明无效')
 p=Path(spec['path']);p=p if p.is_absolute() else Path(base)/p
 if hashlib.sha256(p.read_bytes()).hexdigest()!=spec['sha256']:raise ValueError('原文哈希不同')
 structure=review(p)
 if structure['reviewRequired']:raise ValueError('PDF结构待复核')
 import pdfplumber
 with pdfplumber.open(p) as doc:
  page=spec['page']
  if not isinstance(page,int) or isinstance(page,bool) or not 1<=page<=len(doc.pages):raise ValueError('物理页无效')
  front='\n'.join(x.extract_text() or '' for x in doc.pages[:12]);code=spec['code']
  if not re.fullmatch(r'\d{6}',code) or not re.search(r'(?<!\d)'+code+r'(?!\d)',front):raise ValueError('代码身份未匹配')
  if spec['end'] not in dates_in(front):raise ValueError('报告期末未匹配')
  source=doc.pages[page-1];tables=[]
  for t in source.find_tables():
   rows=t.extract()
   if len(rows)>1 and len(rows[1])==3 and compact(rows[1][1])=='基金份额（份）':
    dates=dates_in(''.join(str(v or '') for v in rows[0]))
    if spec['start'] not in dates or spec['end'] not in dates:raise ValueError('实收表期间未匹配')
    tables.append((t.bbox,parse(rows,spec.get('dashPolicy','reject'))))
  if len(tables)!=1:raise ValueError('数量表未唯一定位')
  bbox,result=tables[0]
 methods={name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() for name in ('fund_share_ledger.py','fund_holder_units_review.py','verify_original.py','pdf_structure_review.py','collection_validation.py','cash_flow_reconciliation.py')}
 return {'code':code,'start':spec['start'],'end':spec['end'],'sourcePath':str(p.resolve()),'sha256':spec['sha256'],'physicalPage':page,'tableBBox':bbox,'structureReview':structure,'result':result,'methodFilesSha256':methods,'formula':'期初份额+申购份额+负号填列赎回份额=期末份额；(期末/期初-1)*100，期初为0时比例留空','limitations':['仅三列、四条数量变动行；拆分等额外行拒绝，需要另核完整变动','报告身份、合计通过不认证会计合规、真实账户或当前份额','来源获取与有效版本仍分别核验','方法摘要只记录选定脚本，不冻结第三方依赖或证明未来环境复现']}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 if a.out.exists():raise ValueError('输出已存在')
 result=run(json.loads(a.input.read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant),a.input.resolve().parent)
 with a.out.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
