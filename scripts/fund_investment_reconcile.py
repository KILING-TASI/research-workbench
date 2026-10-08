"""Reconcile disclosed fund investments against current report accounting totals."""
import argparse,hashlib,json,re,datetime as dt
from decimal import Decimal
from pathlib import Path
import pdfplumber
from verify_original import compact,dates_in
from fund_report_archive import top_fund_rows,identity
from research_brief_html import render
from collection_validation import unique_pairs,reject_constant
from fund_report_fof import extract as extract_complete_fof

def reconcile(disclosure,fund_total,nav):
 total=Decimal(str(fund_total));nav=Decimal(str(nav))
 if not total.is_finite() or not nav.is_finite() or total<0 or nav<=0:raise ValueError('会计分母无效')
 rows=disclosure['rows'];amounts=[];checked=[]
 if not rows:raise ValueError('基金投资明细为空')
 for x in rows:
  amount=Decimal(x['marketValueCNY']);reported=Decimal(x['reportedWeightPct'])
  if not amount.is_finite() or not reported.is_finite() or amount<0 or reported<0:raise ValueError('明细数值无效')
  pct=amount/nav*100
  if abs(pct-reported)>Decimal('0.00501'):raise ValueError('披露比例与净资产分母不符')
  amounts.append(amount);checked.append(dict(x,verifiedNAVWeight=str(amount/nav)))
 summed=sum(amounts,Decimal(0));difference=total-summed
 return dict(rows=checked,fundInvestmentTotalCNY=str(total),netAssetsCNY=str(nav),disclosedSumCNY=str(summed),differenceCNY=str(difference),accountingTotalVerified=difference==0,status='基金投资金额合计及净资产比例核对完成' if difference==0 else '披露金额未覆盖基金投资会计总额',completeAssetPortfolio=False)

def extract(report):
 for v in [report['reportDate'],report['asOf'],report['metadata']['publishedAt']]:dt.date.fromisoformat(v)
 if not report['reportDate']<=report['metadata']['publishedAt']<=report['asOf']:raise ValueError('报告披露日期越界')
 if report.get('identityStatus') not in ('matched','代码、标题、所属期、送出日期匹配；非官方网页核验'):raise ValueError('报告身份未核验')
 path=Path(report['documentPath']);digest=hashlib.sha256(path.read_bytes()).hexdigest()
 if digest!=report['sha256']:raise ValueError('报告哈希变化')
 identity_evidence=identity(path,report['code'],report['reportDate'],report['metadata'])
 values={'fund':{},'nav':{}};started=False;unit=False
 with pdfplumber.open(path) as doc:
  disclosure=top_fund_rows(doc)

  for number,page in enumerate(doc.pages,1):
   text=page.extract_text() or ''
   starts=page.search(r'(?m)^[67]\.1\s*资产负债表\s*$')
   if starts and report['reportDate'] in dates_in(text) and '单位：人民币元' in compact(text):started=True;unit=True
   if not started:continue
   ends=page.search(r'(?m)^[67]\.2\s*利润表\s*$')
   for table in page.find_tables():
    if starts and table.bbox[3]<=starts[0]['top']:continue
    if ends and table.bbox[1]>=ends[0]['top']:continue
    for row in table.extract():
     if not row:continue
     label=compact(row[0]);key='fund' if label=='基金投资' else 'nav' if label in ['净资产合计','所有者权益合计'] else None
     if key and unit:
      # Preserve the current-period column; never shift a prior-period value into a blank cell.
      current=compact(row[2]).replace(',','') if len(row)==4 else ''
      if not re.fullmatch(r'\d+\.\d{2}',current):raise ValueError('会计表当前期金额或列位置未确认')
      values[key].setdefault(current,[]).append(dict(page=number,tableBBox=list(table.bbox),originalCells=row))
   if ends:break
 if any(len(x)!=1 for x in values.values()):raise ValueError('当前基金投资总额或净资产缺失/冲突')
 total=next(iter(values['fund']));nav=next(iter(values['nav']))
 if not disclosure:
  complete=extract_complete_fof(path,{**report['metadata'],'sha256':digest,'code':report['code'],'reportDate':report['reportDate'],'netAssetsCNY':nav,'fundInvestmentCNY':total})
  disclosure={'rows':[{'name':h['name'],'code':h['code'],'marketValueCNY':h['marketValueCNY'],'reportedWeightPct':h['reportedWeightPct'],'page':h['locator'],'originalCells':h['originalCells']} for h in complete['holdings']],'disclosureScope':'complete-disclosed-fund-investments'}
 r=reconcile(disclosure,total,nav)
 r['disclosureScope']=disclosure.get('disclosureScope','top-ten-fund-investments')
 r.update(code=report['code'],reportDate=report['reportDate'],asOf=report['asOf'],publishedAt=report['metadata']['publishedAt'],sourceUrl=report['metadata']['sourceUrl'],sourceSha256=digest,accountingEvidence=values,identityRecheck=identity_evidence,limitations=['仅核对基金投资表，不代表全资产组合核验','未核验子基金代码身份和底层完整报告，不自动计算全组合敞口','第三方报告副本不等同官方发布网页核验'])
 return r

def markdown(r):
 lines=['# 基金投资金额核对','',r['code']+'；报告期'+r['reportDate']+'。',r['status'],f"披露合计{r['disclosedSumCNY']}元，会计基金投资总额{r['fundInvestmentTotalCNY']}元，差额{r['differenceCNY']}元。",'净资产分母：'+r['netAssetsCNY']+'元。','','| 基金原文名称 | 金额（元） | 披露占净资产 | PDF页码 |','| --- | ---: | ---: | ---: |']
 for x in r['rows']:lines.append('| '+x['name']+' | '+x['marketValueCNY']+' | '+x['reportedWeightPct']+'% | '+str(x['page'])+' |')
 lines+=['',r['sourceUrl'],'']+['- '+x for x in r['limitations']]
 return '\n'.join(lines)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('report');p.add_argument('--out',required=True);a=p.parse_args();out=Path(a.out)
 if any(x.exists() for x in [out,out.with_suffix('.md'),out.with_suffix('.html')]):raise FileExistsError('输出已存在')
 r=extract(json.loads(Path(a.report).read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant));out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8');text=markdown(r);out.with_suffix('.md').write_text(text,encoding='utf-8');out.with_suffix('.html').write_text(render(text),encoding='utf-8')
