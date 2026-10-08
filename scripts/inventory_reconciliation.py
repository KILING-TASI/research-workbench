"""Reconcile selected original inventory rows; never infer missing allowances."""
import argparse,hashlib,json,re,math
from decimal import Decimal,InvalidOperation
from pathlib import Path

COLUMN_ORDER=['期末余额','期末减值','期末净额','期初余额','期初减值','期初净额']

def validate_column_order(spec):
 if 'columns' in spec and spec['columns']!=COLUMN_ORDER:
  raise ValueError('本入口固定按期末三列、期初三列核对；列顺序或定义不同需另行定位，不可沿用')

def validate_boxes(boxes,width,height):
 if not isinstance(boxes,list) or len(boxes)!=6:raise ValueError('需六个原文单元格坐标')
 previous=None;vertical=None
 for box in boxes:
  if not isinstance(box,list) or len(box)!=4 or any(type(x) not in (int,float) or not math.isfinite(x) for x in box):raise ValueError('单元格坐标无效')
  x0,y0,x1,y1=box
  if not 0<=x0<x1<=width or not 0<=y0<y1<=height:raise ValueError('单元格坐标越界')
  if previous is not None and x0<previous:raise ValueError('六列须按原文从左到右排列且不重叠')
  if vertical is not None and (y0,y1)!=vertical:raise ValueError('六列须来自同一原文行范围')
  previous=x1;vertical=(y0,y1)

def cell_amount(text):
 text=text.strip()
 if text in ('','/'):return None
 if not re.fullmatch(r'(?:\d+|\d{1,3}(?:,\d{3})+)\.\d{2}',text):raise ValueError('单元格存在歧义或非数值内容')
 return str(Decimal(text.replace(',','')))

def quote_amounts(quote):
 tokens=re.findall(r'(?<![\d.,−－-])[-−－]?\d[\d,]*\.\d+(?:[eE][+-]?\d+)?(?:[%％])?(?![\d.,eE])|/',quote)
 return [cell_amount(token) for token in tokens]

def require_unique_quote(quote,text):
 if not isinstance(quote,str) or not quote.strip():raise ValueError('分类引句不能为空')
 compact=lambda value:''.join(value.split())
 count=compact(text).count(compact(quote))
 if count==0:raise ValueError('分类引句未定位')
 if count!=1:raise ValueError('分类引句在指定页有多处匹配，需进一步定位，不作为唯一证据')

def load_spec(path):
 path=Path(path).resolve();spec=json.loads(path.read_text(encoding='utf-8-sig'))
 source=Path(spec['source'])
 if not source.is_absolute():source=path.parent/source
 spec['source']=str(source.resolve());return spec

def calculate(rows):
 if not isinstance(rows,list) or len(rows)<2:raise ValueError('需分类行与合计行')
 seen=set();parsed=[]
 for row in rows:
  if not isinstance(row,dict):raise ValueError('每个存货分类行须为对象，不能用空行或字符串代替')
  if not isinstance(row.get('name'),str) or not row['name'].strip() or row['name'] in seen:raise ValueError('分类名为空或重复')
  seen.add(row['name']);values=row.get('values')
  if not isinstance(values,list) or len(values)!=6:raise ValueError('需六列：期末/期初余额、减值、净额')
  nums=[]
  for value in values:
   if value is None:nums.append(None);continue
   if not isinstance(value,str):raise ValueError('数值须为十进制字符串或空值')
   try:number=Decimal(value)
   except InvalidOperation as exc:raise ValueError('存货金额不是有效十进制数；未知或空白须保留为明确空值') from exc
   if not number.is_finite() or number<0:raise ValueError('存货数值须有限且非负')
   nums.append(number)
  parsed.append(nums)
 if rows[-1]['name']!='合计':raise ValueError('最后一行须为合计')
 columns=[]
 for i in range(6):
  complete=all(r[i] is not None for r in parsed)
  diff=sum(r[i] for r in parsed[:-1])-parsed[-1][i] if complete else None
  columns.append(dict(column=i,status='matched' if complete and diff==0 else 'conflict' if complete else 'missing',difference=str(diff) if complete else None))
 checks=[]
 for row,nums in zip(rows,parsed):
  periods=[]
  for i in (0,3):
   complete=all(x is not None for x in nums[i:i+3]);diff=nums[i]-nums[i+1]-nums[i+2] if complete else None
   periods.append(dict(status='matched' if complete and diff==0 else 'conflict' if complete else 'missing',difference=str(diff) if complete else None))
  change=nums[2]-nums[5] if nums[2] is not None and nums[5] is not None else None
  checks.append(dict(name=row['name'],periodChecks=periods,netChange=str(change) if change is not None else None))
 return dict(columns=columns,rows=checks,limitations='选定分类核对；空白不填零。余额变化不是现金调节同比，不证明库存安全、积压或订单覆盖。')

def allowance_movement(opening,provision,reversal_or_writeoff,closing):
 """Check an explicitly mapped four-field movement, without splitting reductions."""
 inputs=dict(opening=opening,provision=provision,reversalOrWriteoff=reversal_or_writeoff,closing=closing)
 values={}
 for key,value in inputs.items():
  if value is None:values[key]=None;continue
  if not isinstance(value,str):raise ValueError('准备变动金额须为十进制字符串或空值')
  try:amount=Decimal(value)
  except Exception as exc:raise ValueError('准备变动金额无效') from exc
  if not amount.is_finite() or amount<0:raise ValueError('准备变动金额须有限且非负')
  values[key]=amount
 complete=all(v is not None for v in values.values())
 difference=(values['opening']+values['provision']-values['reversalOrWriteoff']-values['closing']) if complete else None
 return dict(inputs=inputs,status='matched' if complete and difference==0 else 'conflict' if complete else 'missing',
             difference=str(difference) if difference is not None else None,
             formula='期初准备 + 本期计提 - 转回或转销 = 期末准备',
             limitations='已明确映射的四字段计算；不自动定位原文或验证列头，不拆分转回与转销，不证明库存安全、利润回补或现金支付。')

def verify(spec):
 validate_column_order(spec)
 from pypdf import PdfReader
 p=Path(spec['source']);raw=p.read_bytes()
 if hashlib.sha256(raw).hexdigest()!=spec['sha256']:raise ValueError('原文版本不一致')
 page=spec.get('page');reader=PdfReader(p)
 if type(page)!=int or not 1<=page<=len(reader.pages):raise ValueError('原文页码无效')
 text=reader.pages[page-1].extract_text() or '';compact=lambda x:''.join(x.split())
 if spec.get('unit')!='人民币元' or not re.search(r'单位[:：]元币种[:：]人民币',compact(text)):raise ValueError('本入口仅支持已在原文定位的人民币元口径')
 for row in spec['rows']:
  quote=row.get('quote','')
  require_unique_quote(quote,text)
  values=quote_amounts(quote)
  if 'cellBoxes' in row:
   import pdfplumber
   boxes=row['cellBoxes']
   values=[]
   with pdfplumber.open(p) as doc:
    physical=doc.pages[page-1]
    validate_boxes(boxes,physical.width,physical.height)
    for box in boxes:
     cell=(physical.crop(tuple(box)).extract_text() or '').strip()
     values.append(cell_amount(cell))
  if values!=row['values'] or not compact(quote).startswith(compact(row['name'])):raise ValueError('引句与分类数值不一致；特殊版式需人工处理')
 result=calculate(spec['rows']);result.update(source=str(p.resolve()),sha256=spec['sha256'],page=page,originalQuotesLocated=True,fullTableCoverageVerified=False,
     methodSha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
     methodScope='原页引句及所选六列核对；方法哈希不证明完整覆盖或经济解释',
     columnOrder=COLUMN_ORDER,columnOrderDeclared='columns' in spec,
     headerLayoutAutomaticallyVerified=False)
 return result

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('input',type=Path);parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
 if args.out.exists():parser.error('输出已存在；请使用新结果路径，保留旧版本')
 try:result=verify(load_spec(args.input))
 except ModuleNotFoundError as exc:parser.error('缺少可选依赖 '+str(exc.name)+'；文字核验需pypdf，单元格坐标核验另需pdfplumber')
 except (OSError,ValueError,KeyError,TypeError) as exc:parser.error('存货原文核验未完成：'+str(exc))
 args.out.parent.mkdir(parents=True,exist_ok=True)
 with args.out.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
