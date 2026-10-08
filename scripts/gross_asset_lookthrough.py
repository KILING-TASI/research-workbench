"""Single-level disclosed gross assets and liabilities, not security risk attribution."""
import argparse,datetime,hashlib,json
from decimal import Decimal
from pathlib import Path
from disclosed_rate_scenario import numeric
from collection_validation import day,unique_pairs,reject_constant

def calculate(spec,base=Path('.')):
 if not isinstance(spec,dict) or not isinstance(spec.get('parentHoldings'),list) or not spec['parentHoldings'] or not isinstance(spec.get('pools'),dict):raise ValueError('须明确父持仓对象数组和资产池映射')
 if any(not isinstance(h,dict) or not isinstance(h.get('code'),str) or not h['code'].strip() or not isinstance(h.get('pool'),str) or not h['pool'].strip() for h in spec['parentHoldings']):raise ValueError('父持仓须含明确代码与资产池身份')
 period=spec.get('reportDate');day(period)
 if spec['currency']!='CNY':raise ValueError('金额币种须统一人民币')
 seen=set();pools={};total=Decimal(0)
 for h in spec['parentHoldings']:
  code=h['code'];weight=numeric(h['weight'])
  if not code or code in seen or not 0<=weight<=1:raise ValueError('父持仓身份重复或权重非法')
  seen.add(code);pool=h['pool'];pools[pool]=pools.get(pool,Decimal(0))+weight;total+=weight
 if total>1:raise ValueError('父基金持仓权重超过1')
 rows=[];asset_sum=Decimal(0);liability_sum=Decimal(0);covered=Decimal(0)
 for pool,w in pools.items():
  node=spec['pools'].get(pool)
  if node is None:rows.append(dict(pool=pool,parentWeight=str(w),status='missing-pool'));continue
  if not isinstance(node,dict) or any(not isinstance(node.get(k),dict) for k in ['source','assetsCNY','liabilitiesCNY']):raise ValueError('资产池须含来源及资产负债分类对象')
  if node['reportDate']!=period or node['currency']!='CNY':raise ValueError('资产池期间或币种不一致')
  if day(node.get('publishedAt'))<day(period):raise ValueError('发布日期早于报告期')
  assets=numeric(node['totalAssetsCNY']);liabilities=numeric(node['totalLiabilitiesCNY']);nav=numeric(node['netAssetsCNY'])
  if assets<0 or liabilities<0 or nav<=0 or assets-liabilities!=nav:raise ValueError('资产负债与净资产不勾稽')
  source=node['source'];p=Path(base)/source['path']
  if hashlib.sha256(p.read_bytes()).hexdigest()!=source['sha256']:raise ValueError('资产池原件哈希变化')
  pages=source.get('physicalPages')
  if not isinstance(pages,list) or not pages or any(type(page)!=int or page<1 for page in pages) or pages!=sorted(set(pages)):raise ValueError('原页位置须为唯一递增的正整数数组')
  classes=[];classified=Decimal(0);known_liabilities=Decimal(0)
  for category,amount in node['assetsCNY'].items():
   n=numeric(amount)
   if n<0:raise ValueError('毛资产金额不能为负')
   classified+=n;classes.append(dict(category=category,amountCNY=str(n),childGrossExposureAgainstNAV=str(n/nav),parentGrossExposure=str(w*n/nav)))
  debt=[]
  for category,amount in node['liabilitiesCNY'].items():
   n=numeric(amount)
   if n<0:raise ValueError('负债金额不能为负')
   known_liabilities+=n;debt.append(dict(category=category,amountCNY=str(n),childLiabilityAgainstNAV=str(n/nav),parentLiabilityExposure=str(w*n/nav)))
  if classified>assets or known_liabilities>liabilities:raise ValueError('分类金额超过总额，可能重复计算小计')
  asset_sum+=w*assets/nav;liability_sum+=w*liabilities/nav;covered+=w
  rows.append(dict(pool=pool,status='balance-bound',parentWeight=str(w),assets=classes,liabilities=debt,unclassifiedAssetsCNY=str(assets-classified),unclassifiedLiabilitiesCNY=str(liabilities-known_liabilities),parentGrossAssets=str(w*assets/nav),parentLiabilities=str(w*liabilities/nav),source=dict(source,path=str(p.resolve()))))
 if abs(asset_sum-liability_sum-covered)>Decimal('1e-24'):raise ValueError('父权重净额不守恒')
 return dict(type='disclosed-gross-assets-liabilities',reportDate=period,pools=rows,parentGrossAssets=str(asset_sum),parentLiabilities=str(liability_sum),coveredParentNAVWeight=str(covered),uncoveredParentNAVWeight=str(1-covered),limitations=['仅单层已披露资产大类，非逐券或递归完整风险穿透','来源哈希及人工提供页码不等于自动原文金额核验','同一资产池份额合并父权重，不能当作独立风险来源','毛资产可超过100%，负债单列，不归一化；未知余额不填现金','不提供久期、信用评级或未来损失判断'])
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args();r=calculate(json.loads(a.input.read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant),a.input.resolve().parent)
 with a.out.open('x',encoding='utf-8') as f:json.dump(r,f,ensure_ascii=False,indent=2)
