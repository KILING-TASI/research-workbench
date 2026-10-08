"""Reconcile parent balance and selected child gross pools without double counting."""
import argparse,hashlib,json
from pathlib import Path
from decimal import Decimal
from disclosed_rate_scenario import numeric
from collection_validation import day,unique_pairs,reject_constant

def run(spec,base):
 if not isinstance(spec,dict):raise ValueError('父子余额请求须为对象')
 paths={k:Path(base)/spec[k] for k in ('parentBalance','parentFundDetails','childGrossBridge')};raw_inputs={k:p.read_bytes() for k,p in paths.items()};data={k:json.loads(raw.decode('utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant) for k,raw in raw_inputs.items()}
 if any(not isinstance(x,dict) for x in data.values()):raise ValueError('父子余额快照须为对象')
 parent=data['parentBalance'];details=data['parentFundDetails'];bridge=data['childGrossBridge'];child=bridge['result'];inputs=bridge['input'];day(parent.get('reportDate'))
 if not isinstance(child,dict) or not isinstance(inputs,dict):raise ValueError('子池输入与结果须为对象')
 for rows in [details.get('holdings'),inputs.get('parentHoldings')]:
  if not isinstance(rows,list) or any(not isinstance(h,dict) or not isinstance(h.get('code'),str) or not h['code'].strip() for h in rows):raise ValueError('父份额明细须为代码对象数组')
  if len({h['code'] for h in rows})!=len(rows):raise ValueError('父代码重复')
 if parent.get('type')!='selected-fund-balance-snapshot' or child.get('type')!='disclosed-gross-assets-liabilities':raise ValueError('需要已提取父报表和子资产池毛额结果')
 if any(x['reportDate']!=parent['reportDate'] for x in (details,child,inputs)) or parent['currency']!='CNY' or inputs['currency']!='CNY':raise ValueError('报告期或币种不一致')
 v=parent['amountsCNY'];nav=numeric(v['净资产合计']);assets=numeric(v['资产总计']);liabilities=numeric(v['负债合计']);fund=numeric(v['交易性金融资产/基金投资'])
 if nav<=0 or assets<0 or liabilities<0 or assets-liabilities!=nav or fund<0 or fund>assets:raise ValueError('父报表余额非法')
 if any(numeric(h['marketValueCNY'])<0 for h in details['holdings']):raise ValueError('父份额市值不能为负')
 if numeric(details['netAssetsCNY'])!=nav or sum((numeric(h['marketValueCNY']) for h in details['holdings']),Decimal(0))!=fund:raise ValueError('父基金投资明细与余额不匹配')
 expected={h['code']:numeric(h['marketValueCNY'])/nav for h in details['holdings']};actual={}
 for h in inputs['parentHoldings']:
  code=h['code']
  if code in actual:raise ValueError('父代码重复')
  actual[code]=numeric(h['weight'])
 if set(expected)!=set(actual) or any(abs(expected[k]-actual[k])>Decimal('1e-24') for k in expected):raise ValueError('子资产池输入未对应全部父基金份额权重')
 covered=numeric(child['coveredParentNAVWeight']);gross=numeric(child['parentGrossAssets']);debt=numeric(child['parentLiabilities']);pending=fund/nav-covered;direct=(assets-fund)/nav
 if covered<0 or pending<0 or gross<0 or debt<0 or abs(gross-debt-covered)>Decimal('1e-24'):raise ValueError('子资产池净额或覆盖权重非法')
 totalgross=direct+gross+pending;totaldebt=liabilities/nav+debt
 if abs(totalgross-totaldebt-1)>Decimal('1e-24'):raise ValueError('父子净额不守恒')
 return dict(type='parent-child-gross-net-reconciliation',reportDate=parent['reportDate'],directParentGrossAssetsFraction=str(direct),confirmedChildGrossAssetsFraction=str(gross),unexpandedFundCarryingWeight=str(pending),parentLiabilitiesFraction=str(liabilities/nav),confirmedChildLiabilitiesFraction=str(debt),reportedGrossIncludingUnexpandedFundCarryingWeight=str(totalgross),reportedLiabilitiesFraction=str(totaldebt),netNAVWeight=str(totalgross-totaldebt),bindings=[dict(role=k,path=str(p.resolve()),sha256=hashlib.sha256(raw_inputs[k]).hexdigest()) for k,p in paths.items()],formulas=['父直接毛资产=(父总资产-基金投资)/父净资产','未展开基金账面权重=父基金投资/父净资产-已确认子池净权重','合并毛额=父直接毛资产+子池毛资产+未展开账面权重','合并负债=父负债/父净资产+子池负债'],limitations=['报表分解自洽不等于原件完整、估值正确或风险可接受','未展开账面值不当现金、零风险或已确认底层资产','父基金投资剔重，不能再叠加原基金投资比例','输入原文与同池身份仍需独立核验，不提供完整逐券风险判断'])
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args();r=run(json.loads(a.input.read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant),a.input.resolve().parent)
 with a.out.open('x',encoding='utf-8') as f:json.dump(r,f,ensure_ascii=False,indent=2)

