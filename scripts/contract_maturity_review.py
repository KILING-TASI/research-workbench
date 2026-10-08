"""Review explicitly selected undiscounted maturity table, not solvency."""
import argparse,hashlib,json,re
from decimal import Decimal,InvalidOperation
from pathlib import Path
from pypdf import PdfReader
from pdf_structure_review import review
from collection_validation import unique_pairs,reject_constant

def compact(text):return re.sub(r"\s+","",text)
def amount(value):
 if isinstance(value,bool) or not isinstance(value,(str,int,float)):raise ValueError("金额必须明确")
 try:x=Decimal(str(value))
 except InvalidOperation as exc:raise ValueError('金额格式无效') from exc
 if not x.is_finite() or x<0:raise ValueError("到期金额须有限非负")
 return x

def calculate(rows,total,column_count=4):
 if column_count not in (4,5):raise ValueError("仅支持已定义四列或五列期限")
 if not isinstance(rows,list) or not rows:raise ValueError("缺少到期行")
 if not isinstance(total,dict) or any(not isinstance(r,dict) for r in rows):raise ValueError('到期行及合计须为对象')
 labels=[r.get("label") for r in rows]
 if any(not isinstance(x,str) or not x.strip() for x in labels) or len(set(labels))!=len(labels):raise ValueError("到期行名称缺失或重复")
 parsed=[]
 for row in rows+[total]:
  if len(row.get("amounts",[]))!=column_count:raise ValueError("期限列金额数不一致")
  cells=list(map(amount,row["amounts"]))
  if sum(cells[:-1])!=cells[-1]:raise ValueError("行内期限合计不一致")
  parsed.append(cells)
 sums=[sum(x[i] for x in parsed[:-1]) for i in range(column_count)]
 if sums!=parsed[-1]:raise ValueError("期限列合计不一致")
 return dict(columnTotals=[str(x) for x in sums],scope="所选未折现金融负债期限表；不代表全部现金需求、偿债能力或未来兑付")

def token_value(token,policy='reject'):
 if policy not in ('reject','assumed-zero-for-explicit-dash'):raise ValueError('破折号处理口径无效')
 if token in ('—','-'):
  if policy=='reject':raise ValueError('原表破折号含义未确认，不能自动填零')
  return Decimal(0)
 return amount(token.replace(',',''))

def run(spec,base=Path(".")):
 if not isinstance(spec,dict):raise ValueError('期限表核验输入须为对象')
 policy=spec.get('dashPolicy','reject');token_value('0',policy);dash_assumptions=[]
 path=Path(base)/spec["path"]
 if hashlib.sha256(path.read_bytes()).hexdigest()!=spec["sha256"]:raise ValueError("原件哈希变化")
 structure=review(path)
 if structure["reviewRequired"]:raise ValueError("原件结构待复核")
 if spec.get("basis")!="undiscounted-contractual" or spec.get("currency")!="CNY" or spec.get("unit") not in ("yuan","thousand-yuan"):raise ValueError("仅支持声明人民币元或千元未折现合同口径")
 doc=PdfReader(path);front=compact("\n".join(p.extract_text() or "" for p in doc.pages[:12]))
 code=spec["code"]
 if not isinstance(code,str) or not re.fullmatch(r"\d{6}",code) or not re.search(r"(?<!\d)"+re.escape(code)+r"(?!\d)",front):raise ValueError("前页证券代码未确认")
 period=spec["reportDate"]
 cover=compact(doc.pages[0].extract_text() or "")
 if not re.fullmatch(r"20\d{2}-06-30",period) or period[:4]+"年半年度报告" not in cover:raise ValueError("仅支持封面已确认自然年半年报")
 def original(item):
  n=item["page"]
  if isinstance(n,bool) or not isinstance(n,int) or n<1 or n>len(doc.pages):raise ValueError("物理页非法")
  quote=item["quote"]
  normalize=lambda t:re.sub(r"\s+"," ",t).strip()
  if not isinstance(quote,str) or not quote.strip() or normalize(quote) not in normalize(doc.pages[n-1].extract_text() or ""):raise ValueError("引句不在原页或金额分隔不一致")
  return compact(quote)
 heading=original(spec["tableHeading"])
 if "未折现" not in heading or "合同现金流量" not in heading:raise ValueError("未折现表头未确认")
 header=original(spec["columnHeader"])
 layouts={"1年以内1年至5年5年以上合计":4,"一年以内一到二年二到五年五年以上合计":5}
 if header not in layouts:raise ValueError("期限列顺序未确认")
 column_count=layouts[header]
 selected_page=spec["tableHeading"]["page"]
 if any(item["page"]!=selected_page for item in [spec["columnHeader"],*spec["rows"],spec["total"]]):raise ValueError("本入口仅支持同一物理页期限表；跨页需另行核验")
 page_text=compact(doc.pages[selected_page-1].extract_text() or "")
 if page_text.count(heading)!=1:raise ValueError("期限表定位不唯一")
 section=page_text.split(heading,1)[1]
 if column_count==5:
  period_quote=original(spec["tablePeriod"])
  end_quote=original(spec["tableEnd"])
  if spec["tablePeriod"]["page"]!=selected_page or spec["tableEnd"]["page"]!=selected_page:raise ValueError("双期表边界须同页")
  if period_quote!=period[:4]+"年6月30日" or end_quote!=str(int(period[:4])-1)+"年12月31日":raise ValueError("本期与上年末边界未确认")
  if section.count(period_quote)!=1 or section.count(end_quote)!=1:raise ValueError("双期日期定位不唯一")
  if section.index(period_quote)>=section.index(end_quote):raise ValueError("双期日期顺序不一致")
  section=section.split(period_quote,1)[1].split(end_quote,1)[0]
 if section.count(header)!=1:raise ValueError("期限表列标题定位不唯一")
 section=section.split(header,1)[1]
 total_quote=original(spec["total"])
 if section.count(total_quote)!=1:raise ValueError("期限表合计定位不唯一")
 section=section.split(total_quote,1)[0]
 cursor=0
 for row in spec["rows"]:
  quote=original(row)
  if section.count(quote)!=1:raise ValueError("原行不在选定表头与合计之间或不唯一")
  position=section.index(quote)
  if position<cursor:raise ValueError("原行次序与期限表不一致")
  cursor=position+len(quote)
 for row in spec["rows"]+[spec["total"]]:
  quote=original(row)
  if row["label"] and not quote.startswith(compact(row["label"])):raise ValueError("原行名称不一致")
  normalized=re.sub(r"\s+"," ",row["quote"]).strip()
  tail=normalized[len(row["label"]):].strip() if row["label"] else normalized
  tokens=tail.split()
  if len(tokens)!=column_count or any(not re.fullmatch(r"(?:\d{1,3}(?:,\d{3})+(?:\.\d{2})?|\d+(?:\.\d{2})?|—|-)",t) for t in tokens):raise ValueError("原行金额分隔或列数不明确")
  values=[token_value(t,policy) for t in tokens]
  dash_assumptions.extend(dict(page=row['page'],label=row['label'],column=i+1,token=t,interpretation='conditional-assumed-zero') for i,t in enumerate(tokens) if t in ('—','-'))
  if values!=list(map(amount,row["amounts"])):raise ValueError("金额与原行顺序不一致")
 result=calculate(spec["rows"],spec["total"],column_count);result.update(columnCount=column_count,sourceSha256=spec["sha256"],reportDate=period,code=code,basis=spec["basis"],sourceStructure=structure,inputUnit=spec["unit"],dashAssumptions=dash_assumptions,status='conditional-dash-assumption' if dash_assumptions else 'selected-original-rows-matched',currencyUnitStatus="输入声明CNY及单位；本入口未独立确认所选表的币种单位适用范围",limits="破折号默认拒绝；显式零值假设须保留条件结果，不作原文确认。币种单位另核，输入声明不作原文认证。身份及选定金额核对不是全文或信用认证。")
 return result
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("input",type=Path);p.add_argument("--out",type=Path,required=True);a=p.parse_args()
 if a.out.exists():raise ValueError("输出路径已存在；使用新结果路径，不覆盖输入、原件或旧结果")
 result=run(json.loads(a.input.read_text(encoding="utf-8-sig"),object_pairs_hook=unique_pairs,parse_constant=reject_constant),a.input.resolve().parent)
 with a.out.open("x",encoding="utf-8") as output:output.write(json.dumps(result,ensure_ascii=False,indent=2))
