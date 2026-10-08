"""Bridge selected balance rows to single-level gross exposure without double counts."""
import argparse,hashlib,json,re
from pathlib import Path
from gross_asset_lookthrough import calculate
from collection_validation import unique_pairs,reject_constant
ASSETS={'货币资金':'bank','结算备付金':'settlement','存出保证金':'margin','交易性金融资产':'tradingFinancialAssets','衍生金融资产':'derivativeAssets','买入返售金融资产':'reverseRepo','债权投资':'debtInvestments','其他债权投资':'otherDebtInvestments','其他权益工具投资':'otherEquityInvestments','应收清算款':'settlementReceivable','应收股利':'dividendReceivable','应收申购款':'subscriptionReceivable','递延所得税资产':'deferredTaxAssets','其他资产':'otherAssets'}
LIABILITIES={'短期借款':'shortBorrowing','交易性金融负债':'tradingFinancialLiabilities','衍生金融负债':'derivativeLiabilities','卖出回购金融资产款':'repoFunding','应付清算款':'settlementPayable','应付赎回款':'redemptionPayable','应付管理人报酬':'managementFeePayable','应付托管费':'custodyFeePayable','应付销售服务费':'salesFeePayable','应付投资顾问费':'advisoryFeePayable','应交税费':'taxPayable','应付利润':'profitPayable','递延所得税负债':'deferredTaxLiabilities','其他负债':'otherLiabilities'}

def explicit_categories(snapshot,mapping):
 values=snapshot['amountsCNY'];known={};unknown=[]
 legacy_dashes={e.get('label') for e in snapshot.get('evidence',[]) if e.get('reportedCurrentCell') in ('-','－','—')}
 for label,key in mapping.items():
  if label not in values:continue
  if values[label] is None or label in legacy_dashes:
   unknown.append({'label':label,'category':key,'status':'reported-dash-unconfirmed'})
  else:known[key]=values[label]
 return known,unknown

def run(spec,base):
 if not isinstance(spec,dict) or not isinstance(spec.get('balanceSnapshots'),dict) or not isinstance(spec.get('parentHoldings'),list) or any(not isinstance(h,dict) or not isinstance(h.get('code'),str) or not isinstance(h.get('pool'),str) for h in spec['parentHoldings']):raise ValueError('余额桥接须含快照映射及父份额对象数组')
 pools={};bindings=[];code_checks=[];unknown_fields=[]
 for pool,filename in spec['balanceSnapshots'].items():
  p=Path(base)/filename;raw=p.read_bytes();s=json.loads(raw.decode('utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant)
  if not isinstance(s,dict) or s.get('type')!='selected-fund-balance-snapshot' or not isinstance(s.get('source'),dict) or not isinstance(s.get('amountsCNY'),dict):raise ValueError('需要已提取资产负债表结果')
  from pypdf import PdfReader
  original=Path(base)/s['source']['path']
  if hashlib.sha256(original.read_bytes()).hexdigest()!=s['source']['sha256']:raise ValueError('原件哈希变化')
  from pdf_structure_review import review
  structure=review(original)
  if structure['reviewRequired']:
   code_checks.append(dict(pool=pool,status='source-review-required',sourceStructureReview=structure,limitation='保留该父份额为未展开，不当现金或已确认资产池'))
   bindings.append(dict(pool=pool,path=str(p.resolve()),sha256=hashlib.sha256(raw).hexdigest(),code=s['code'],sourceReviewRequired=True))
   continue
  doc=PdfReader(original);front='\n'.join(p.extract_text() or '' for p in doc.pages[:12])
  selected=[h['code'] for h in spec['parentHoldings'] if h['pool']==pool]
  for code in selected:
   if not re.fullmatch(r'\d{6}',code) or not re.search(r'(?<!\d)'+re.escape(code)+r'(?!\d)',front):raise ValueError('父份额代码未出现在子报告前12页：'+code)
  code_checks.append(dict(pool=pool,selectedShareCodes=selected,status='front-code-text-matched',limitation='代码文字出现仍需结合基金基本信息表人工确认共用资产池'))
  asset_categories,unknown_assets=explicit_categories(s,ASSETS);liability_categories,unknown_liabilities=explicit_categories(s,LIABILITIES)
  unknown_fields.append({'pool':pool,'assets':unknown_assets,'liabilities':unknown_liabilities})
  v=s['amountsCNY'];pools[pool]=dict(reportDate=s['reportDate'],publishedAt=s['publishedAt'],currency=s['currency'],totalAssetsCNY=v['资产总计'],totalLiabilitiesCNY=v['负债合计'],netAssetsCNY=v['净资产合计'],assetsCNY=asset_categories,liabilitiesCNY=liability_categories,source=s['source'])
  bindings.append(dict(pool=pool,path=str(p.resolve()),sha256=hashlib.sha256(raw).hexdigest(),code=s['code']))
 inputs=dict(reportDate=spec['reportDate'],currency=spec['currency'],parentHoldings=spec['parentHoldings'],pools=pools);result=calculate(inputs,base);result['balanceSnapshotBindings']=bindings;result['shareCodeChecks']=code_checks;result['unconfirmedBalanceFields']=unknown_fields;result['limitations'].append('横线字段不作零值，只用明确金额组成分类；未分类差额是报表合计减明确金额，差额为零不认证各横线科目为零');result['limitations'].append('交易性金融资产保留报表大类，不按产品名称推断全部是债券；子项不重复求和')
 return dict(input=inputs,result=result)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args();r=run(json.loads(a.input.read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant),a.input.resolve().parent)
 with a.out.open('x',encoding='utf-8') as f:json.dump(r,f,ensure_ascii=False,indent=2)
