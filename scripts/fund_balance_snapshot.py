"""Extract explicitly selected fund balance pages; do not infer complete holdings."""
import argparse,datetime,hashlib,json,re
from pathlib import Path
from decimal import Decimal
import pdfplumber
from verify_original import compact,dates_in
from fof_reports import normalized_year_title
from collection_validation import unique_pairs,reject_constant

def scoped_balance_label(label,parent):
    roots={'交易性金融资产','债权投资','其他债权投资'}
    children={'股票投资','基金投资','债券投资','资产支持证券投资','贵金属投资','其他投资'}
    plain=re.sub(r'^其中[:：]','',label)
    if label in roots:return label,label
    if plain in children and parent:return parent+'/'+plain,parent
    return label,None

def balance_amount(cell):
 token=compact(cell)
 if token in ('-','－','—'):return None
 if not re.fullmatch(r'-?(?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2}',token):raise ValueError('本期金额格式或列位置未确认')
 return Decimal(token.replace(',',''))

def column_cell(row,boxes,center):
 if len(row)!=len(boxes):raise ValueError('原行与单元格坐标数量不一致')
 candidates=[i for i,b in enumerate(boxes) if b is not None and b[0]<=center<b[2]]
 if len(candidates)!=1:raise ValueError('无法按已确认表头位置唯一定位金额单元格')
 i=candidates[0];return i,compact(row[i])

def extract(spec,base=Path('.')):
 period=datetime.date.fromisoformat(spec['reportDate']);published=datetime.date.fromisoformat(spec['publishedAt'])
 if published<period:raise ValueError('送出日期早于截止日')
 path=Path(base)/spec['path'];raw=path.read_bytes()
 if hashlib.sha256(raw).hexdigest()!=spec['sha256']:raise ValueError('原件哈希变化')
 pages=spec['balancePages']
 if not pages or len(set(pages))!=len(pages) or any(isinstance(p,bool) or not isinstance(p,int) or p<1 for p in pages):raise ValueError('资产负债表物理页非法')
 if sorted(pages)!=list(range(min(pages),max(pages)+1)) or len(pages)>4:raise ValueError('只接受明确连续最多四页的资产负债表')
 from pdf_structure_review import review
 source_review=review(path)
 values={};evidence=[];parent_label=None;column_order_confirmed=False;current_index=None;prior_index=None;column_count=None;current_center=prior_center=None
 with pdfplumber.open(path) as doc:
  front='\n'.join(p.extract_text() or '' for p in doc.pages[:12])
  if not re.search(r'(?<!\d)'+re.escape(spec['code'])+r'(?!\d)',front):raise ValueError('前页代码未确认')
  if compact(normalized_year_title(spec['title'])) not in normalized_year_title(compact(front)):raise ValueError('标题未匹配')
  if spec['publishedAt'] not in dates_in(doc.pages[0].extract_text() or ''):raise ValueError('送出日期未确认')
  if max(pages)>len(doc.pages):raise ValueError('物理页超出原件范围')
  text='\n'.join(doc.pages[i-1].extract_text() or '' for i in pages)
  cutoff=re.search(r'报告截止日[:：]?(20\d{2}年0?\d{1,2}月0?\d{1,2}日)',compact(text))
  if not cutoff or spec['reportDate'] not in dates_in(cutoff.group(1)):raise ValueError('明确报告截止日未匹配，不能使用上年度比较日期')
  if not re.search(r'(?m)^6\.1\s*资产负债表\s*$',text) or spec['reportDate'] not in dates_in(text) or '单位：人民币元' not in compact(text):raise ValueError('资产负债表、报告期或人民币单位未确认')
  for page in pages:
   p=doc.pages[page-1];starts=p.search(r'(?m)^6\.1\s*资产负债表\s*$');start=starts[0]['top'] if starts else float('-inf');ends=p.search(r'(?m)^6\.2\s*利润表\s*$');end=ends[0]['top'] if ends else float('inf')
   for table in p.find_tables():
    if table.bbox[1]>=end or table.bbox[3]<=start:continue
    table_rows=table.extract()
    for header_number,header in enumerate(table_rows):
     tokens=[compact(x) for x in header]
     current=[i for i,x in enumerate(tokens) if x.startswith('本期末')]
     prior=[i for i,x in enumerate(tokens) if x.startswith('上年度末')]
     if current and prior:
      if len(current)!=1 or len(prior)!=1 or current[0]>=prior[0]:raise ValueError('本期末与上年度末列顺序不明确或相反，不猜金额列')
      current_index=current[0];prior_index=prior[0];column_count=len(tokens)
      boxes=table.rows[header_number].cells
      if not boxes[current_index] or not boxes[prior_index]:raise ValueError('表头金额列物理位置未取得')
      current_center=(boxes[current_index][0]+boxes[current_index][2])/2;prior_center=(boxes[prior_index][0]+boxes[prior_index][2])/2
      column_order_confirmed=True
    for row_number,row in enumerate(table_rows):
     cells=[compact(x) for x in row]
     if not cells or not cells[0]:continue
     label=cells[0]
     if not column_order_confirmed:continue
     boxes=table.rows[row_number].cells
     current_position,current_cell=column_cell(row,boxes,current_center);prior_position,prior_cell=column_cell(row,boxes,prior_center)
     if current_position==prior_position:raise ValueError('本期和比较期金额落入同一单元格，不能拆猜')
     if not re.fullmatch(r'-?\d[\d,]*\.\d{2}|-|－|—',current_cell):continue
     original_label=label;label,parent_label=scoped_balance_label(label,parent_label)
     amount=balance_amount(current_cell)
     if label in values and values[label]!=amount:raise ValueError('同名字段多值歧义：'+label)
     values[label]=amount;evidence.append(dict(label=label,originalLabel=original_label,currentAmountCNY=None if amount is None else str(amount),reportedCurrentCell=current_cell,currentCellBBox=list(boxes[current_position]),priorCellBBox=list(boxes[prior_position]),physicalPage=page,originalCells=row,tableBBox=list(table.bbox)))
 for label in ('资产总计','负债合计','净资产合计'):
  if label not in values or values[label] is None:raise ValueError('缺少'+label)
 if values['资产总计']-values['负债合计']!=values['净资产合计']:raise ValueError('资产负债与净资产不勾稽')
 return dict(currentPriorColumnOrderConfirmed=column_order_confirmed,sourceStructureReview=source_review,type='selected-fund-balance-snapshot',code=spec['code'],reportDate=spec['reportDate'],publishedAt=spec['publishedAt'],currency='CNY',amountsCNY={k:None if v is None else str(v) for k,v in values.items()},unconfirmedDashFields=[k for k,v in values.items() if v is None],evidence=evidence,source=dict(path=str(path.resolve()),sha256=spec['sha256'],physicalPages=pages),limitations=['仅指定资产负债表范围的两期列提取，不等于完整报告核验','横线含义未确认，金额留空而不填零；合计勾稽不认证空白子项','包含合计与子项，调用者须避免重复求和','非完整逐券持仓或风险评价'])
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args();r=extract(json.loads(a.input.read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant),a.input.resolve().parent)
 with a.out.open('x',encoding='utf-8') as f:json.dump(r,f,ensure_ascii=False,indent=2)
