"""Explicit nine-column US QDII equity table; not issuer or net-risk certification."""
import argparse,hashlib,json,re
from decimal import Decimal,ROUND_HALF_UP
from pathlib import Path
import pdfplumber
from pdf_structure_review import review
from collection_validation import unique_pairs,reject_constant,finite_json_float

def load_json(text):
 return json.loads(text,object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float)

def compact(text):return re.sub(r"\s+","",text or "")
def numeric(text):
 s=compact(text)
 if not re.fullmatch(r"\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?",s):raise ValueError("持仓金额、数量或比例不明确")
 x=Decimal(s.replace(",",""))
 if not x.is_finite() or x<0:raise ValueError("持仓金额须有限非负")
 return x

def parse_row(raw,last):
 if len(raw)!=9:raise ValueError("仅支持九列持仓表")
 if compact(raw[0])=="序号":return None,last,"header"
 if not compact(raw[3]) and not any(compact(x) for x in raw[6:]):return None,last,"fragment"
 code=compact(raw[3]);match=re.fullmatch(r"([A-Z0-9.\-]+)US",code)
 if not match:raise ValueError("不支持的证券市场代码或代码缺失")
 if compact(raw[0]):
  if not compact(raw[0]).isdigit() or int(compact(raw[0]))<1:raise ValueError("序号非法")
  if not compact(raw[1]) or not compact(raw[2]):raise ValueError("新序号公司名称缺失")
  last=dict(rank=int(compact(raw[0])),reportedEnglish=compact(raw[1]),reportedChinese=compact(raw[2]))
 elif any(compact(x) for x in raw[:3]) or last is None:raise ValueError("同序号多证券关系存在歧义")
 qty=numeric(raw[6]);value=numeric(raw[7]);pct=numeric(raw[8])
 if qty!=qty.to_integral_value():raise ValueError("数量不是整数")
 return dict(**last,securityCode="US:"+match[1],rawSecurityCell=raw[3],market=compact(raw[4]),country=compact(raw[5]),quantity=str(qty),value=str(value),reportedNavPct=str(pct),rawCells=raw),last,"row"

def reported_groups(rows,nav):
 if not isinstance(nav,Decimal) or not nav.is_finite() or nav<=0:raise ValueError("净资产须为有限正Decimal值")
 groups={}
 for row in rows:
  rank=row["rank"]
  if rank not in groups:groups[rank]=dict(rank=rank,reportedEnglish=row["reportedEnglish"],reportedChinese=row["reportedChinese"],securityCodes=[],value=Decimal(0))
  group=groups[rank]
  if (group["reportedEnglish"],group["reportedChinese"])!=(row["reportedEnglish"],row["reportedChinese"]):raise ValueError("同报告序号名称冲突")
  group["securityCodes"].append(row["securityCode"]);group["value"]+=Decimal(row["value"])
 ordered=[groups[k] for k in sorted(groups)]
 if any(ordered[i]["value"]>ordered[i-1]["value"] for i in range(1,len(ordered))):raise ValueError("报告组金额未按披露顺序递减")
 for group in ordered:
  group["navPct"]=str(group["value"]/nav*100);group["value"]=str(group["value"])
 return ordered

def run(spec,base=Path(".")):
 path=Path(base)/spec["path"]
 if hashlib.sha256(path.read_bytes()).hexdigest()!=spec["sha256"]:raise ValueError("原件哈希变化")
 structure=review(path)
 if structure["reviewRequired"]:raise ValueError("原件结构待复核")
 pages=spec["holdingsPages"]
 if not pages or any(isinstance(x,bool) or not isinstance(x,int) or x<1 for x in pages) or pages!=list(range(pages[0],pages[-1]+1)) or len(pages)>20:raise ValueError("持仓页须明确连续最多20页")
 rows=[];fragments=[];last=None;leaders=[]
 with pdfplumber.open(path) as doc:
  if pages[-1]>len(doc.pages):raise ValueError("物理页超出原件")
  front=compact("\n".join(p.extract_text() or "" for p in doc.pages[:12]));cover=compact(doc.pages[0].extract_text() or "")
  code=spec["code"];period=spec["reportDate"]
  if not isinstance(code,str) or not re.fullmatch(r"\d{6}",code) or not re.search(r"(?<!\d)"+re.escape(code)+r"(?!\d)",front):raise ValueError("代码未确认")
  if not isinstance(period,str) or not re.fullmatch(r"20\d{2}-06-30",period) or period[:4]+"年中期报告" not in cover:raise ValueError("仅支持封面明确自然年中期报告")
  def evidence(item,label):
   n=item["page"]
   if isinstance(n,bool) or not isinstance(n,int) or n<1 or n>len(doc.pages):raise ValueError("原页非法")
   quote=compact(item["quote"])
   if quote not in compact(doc.pages[n-1].extract_text() or ""):raise ValueError("证据引句不在原页")
   match=re.fullmatch(label+r"([\d,]+\.\d{2})(?:.*)?",quote)
   if not match:raise ValueError("原值字段未明确")
   value=numeric(match[1])
   if value!=numeric(item["value"]):raise ValueError("原值与输入不一致")
   return value
  nav=evidence(spec["navEvidence"],"期末基金资产净值");equity=evidence(spec["equityEvidence"],"合计")
  if nav<=0:raise ValueError("净资产须为正")
  texts=[p.extract_text() or "" for p in [doc.pages[i-1] for i in pages]]
  heading="7.4.1期末指数投资按公允价值占基金资产净值比例大小排序的所有权益投资明细"
  if heading not in compact(texts[0]) or "金额单位：人民币元" not in compact(texts[0]):raise ValueError("持仓段及人民币元单位未确认")
  end_heading="7.4.2期末积极投资按公允价值占基金资产净值比例大小排序的所有权益投资明细"
  if end_heading not in compact(texts[-1]):raise ValueError("持仓结束段未确认")
  def boundary(page,prefix):
   found=[w for w in page.extract_words() if re.match(re.escape(prefix)+r"(?:\D|$)",compact(w['text']))]
   if len(found)!=1:raise ValueError("持仓章节坐标不唯一")
   return found[0]['top']
  start_y=boundary(doc.pages[pages[0]-1],"7.4.1")
  end_y=boundary(doc.pages[pages[-1]-1],"7.4.2")
  for number in pages:
   page=doc.pages[number-1]
   for table in page.find_tables():
    if number==pages[0] and table.bbox[1]<start_y:continue
    if number==pages[-1] and table.bbox[3]>end_y:continue
    for raw in table.extract():
     if len(raw)!=9:continue
     row,next_last,kind=parse_row(raw,last)
     if kind=="fragment":
      if any(compact(x) for x in raw):fragments.append(dict(page=number,rawCells=raw,bbox=table.bbox))
      continue
     if row is None:continue
     if compact(raw[0]):leaders.append(row["rank"])
     last=next_last;row.update(page=number,tableBBox=table.bbox);rows.append(row)
  if not rows or leaders!=list(range(1,len(leaders)+1)):raise ValueError("报告序号不连续或重复")
  if len(set(r["securityCode"] for r in rows))!=len(rows):raise ValueError("证券代码重复")
  total=sum(Decimal(r["value"]) for r in rows)
  if total!=equity:raise ValueError("持仓金额与权益合计不一致")
  for row in rows:
   if (Decimal(row["value"])/nav*100).quantize(Decimal(".01"),rounding=ROUND_HALF_UP)!=Decimal(row["reportedNavPct"]):raise ValueError("逐行净资产比例不一致")
 groups=reported_groups(rows,nav)
 top_ten=sum(Decimal(g["value"]) for g in groups[:10])
 return dict(code=code,reportDate=period,sourceSha256=spec["sha256"],rows=rows,continuationFragments=fragments,securityCount=len(rows),reportedRankGroups=len(leaders),reportedGroups=groups,firstTenReportedGroupsValue=str(top_ten),firstTenReportedGroupsToNetPct=str(top_ten/nav*100),securityValueSum=str(total),equityTotal=str(equity),nav=str(nav),scope="九列美股指数持仓原表、连续序号、金额及比例；报告序号不认证法律发行人，碎片不静默补名，非衍生品净敞口")
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("input",type=Path);p.add_argument("--out",type=Path,required=True);a=p.parse_args()
 if a.out.exists():raise ValueError("输出已存在，使用新路径")
 r=run(load_json(a.input.read_text(encoding="utf-8-sig")),a.input.resolve().parent)
 with a.out.open("x",encoding="utf-8") as f:f.write(json.dumps(r,ensure_ascii=False,indent=2))
