"""Reconcile prepared fund asset snapshots; not an original-PDF parser."""
import argparse,datetime,hashlib,json,re
from decimal import Decimal,InvalidOperation
from pathlib import Path
from collection_validation import day,unique_pairs,reject_constant
FIELDS=('stockCNY','bondCNY','bankAndSettlementCashCNY','otherAssetsCNY')
def amount(value):
 if not isinstance(value,str):raise ValueError('金额与权重须十进制字符串')
 try:n=Decimal(value)
 except InvalidOperation as exc:raise ValueError('金额与权重须十进制字符串') from exc
 if not n.is_finite() or n<0:raise ValueError('金额与权重须有限且非负')
 return n
def calculate(spec):
 if not isinstance(spec,dict):raise ValueError('基金资产桥接输入须为对象')
 date=spec.get('asOf');day(date)
 if spec.get('currency')!='CNY':raise ValueError('本入口仅接受人民币同日快照')
 assets=spec.get('assets')
 if not isinstance(assets,list) or not assets:raise ValueError('需基金资产快照')
 seen=set();weights=[];components={f:Decimal(0) for f in FIELDS+('liabilitiesCNY',)};counts={f:0 for f in FIELDS};checks=[]
 for a in assets:
  if not isinstance(a,dict):raise ValueError('基金资产快照须为对象')
  if any(k not in a for k in ['weight','netAssetsCNY','totalAssetsCNY','liabilitiesCNY']):raise ValueError('基金资产快照缺少权重或资产负债金额')
  reasons=a.get('missingReasons',{})
  if not isinstance(reasons,dict) or any(not isinstance(v,str) or not v.strip() for v in reasons.values()):raise ValueError('缺项原因须为非空文字')
  code=a.get('code')
  if not isinstance(code,str) or not re.fullmatch(r'\d{6}',code) or code in seen:raise ValueError('代码须唯一且六位')
  seen.add(code)
  if a.get('reportDate')!=date or a.get('currency')!='CNY':raise ValueError('资产快照日期或币种不一致')
  weight=amount(a['weight']);weights.append(weight);nav=amount(a['netAssetsCNY']);gross=amount(a['totalAssetsCNY']);liabilities=amount(a['liabilitiesCNY'])
  if nav<=0:raise ValueError('基金净资产须正')
  prepared={};missing=[]
  for f in FIELDS:
   if a.get(f) is None:
    if not reasons.get(f):raise ValueError('空金额须说明原文缺项，不填零')
    missing.append(f);continue
   prepared[f]=amount(a[f])
  if sum(prepared.values())!=gross:raise ValueError('所列资产金额未能桥接总资产，需保留缺项或差异')
  if gross-liabilities!=nav:raise ValueError('总资产扣负债与净资产不一致')
  for f in FIELDS:
   if f in prepared:components[f]+=weight*prepared[f]/nav*100;counts[f]+=1
  components['liabilitiesCNY']+=weight*liabilities/nav*100
  checks.append(dict(code=code,amountsReconcile=True,missingFields=missing,sourceVerification='prepared-input-not-independently-parsed'))
 if sum(weights)!=1:raise ValueError('组合权重合计须为1')
 total=sum(components[f] for f in FIELDS)-components['liabilitiesCNY']
 if abs(total-100)>Decimal('1e-20'):raise ValueError('组合净额桥接存在差异')
 return dict(asOf=date,currency='CNY',componentPctOfPortfolioNAV={f:(None if f in counts and counts[f]==0 else str(v)) for f,v in components.items()},componentStatus={f:('all-missing' if count==0 else 'known-amounts-only' if count<len(assets) else 'all-input-amounts-present') for f,count in counts.items()},netBridgeTotalPct=str(total),checks=checks,originalParsingPerformed=False,limitations='已整理金额的同日静态桥接；空白不填零，不证明原文覆盖、账户现金可用性或资产安全。资产项比例可能合计超过100%，扣负债后才对应净资产。')
def build(spec):
 result=calculate(spec);sources=[]
 for a in spec['assets']:
  pages=a.get('assetPages',[a['assetPage']])
  if not isinstance(pages,list) or not pages or any(type(x)!=int or x<1 for x in pages) or pages!=sorted(set(pages)) or pages[0]!=a['assetPage']:raise ValueError('资产表物理页须唯一、递增并含起始页')
  if type(a['balancePage'])!=int or a['balancePage']<1:raise ValueError('资产负债表物理页无效')
  p=Path(a['source']);digest=hashlib.sha256(p.read_bytes()).hexdigest()
  if digest!=a['sha256']:raise ValueError('来源文件版本变化')
  sources.append(dict(code=a['code'],path=str(p.resolve()),sha256=digest,assetPage=a['assetPage'],assetPages=pages,balancePage=a['balancePage'],verification='file-hash-matched-not-original-parsing'))
 result['sources']=sources;return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args();spec=json.loads(a.input.read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant)
 calculate(spec)
 for row in spec['assets']:
  source=Path(row['source']);row['source']=str(source if source.is_absolute() else a.input.resolve().parent/source)
 result=build(spec);a.out.parent.mkdir(parents=True,exist_ok=True)
 with a.out.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
