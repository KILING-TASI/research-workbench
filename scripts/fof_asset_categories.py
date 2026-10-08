"""Parent and confirmed child gross asset categories; not a risk rating."""
import argparse,hashlib,json
from pathlib import Path
from decimal import Decimal
from disclosed_rate_scenario import numeric
from collection_validation import day,unique_pairs,reject_constant
ROOT_CATEGORIES={'货币资金':'银行存款','结算备付金':'结算备付金','存出保证金':'保证金','买入返售金融资产':'买入返售资产','应收清算款':'应收清算款','应收股利':'应收股利','应收申购款':'应收申购款','其他资产':'其他资产','衍生金融资产':'衍生金融资产','债权投资':'债权投资','其他债权投资':'其他债权投资','其他权益工具投资':'其他权益工具投资','递延所得税资产':'递延所得税资产'}

def run(spec,base):
 if not isinstance(spec,dict):raise ValueError('FOF类别输入须为对象')
 paths={k:Path(base)/spec[k] for k in ('parentBalance','childGrossBridge','parentChildNet')};raw_inputs={k:p.read_bytes() for k,p in paths.items()};data={k:json.loads(raw.decode('utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant) for k,raw in raw_inputs.items()}
 if any(not isinstance(v,dict) for v in data.values()):raise ValueError('父余额、资产池与净额快照须为对象')
 parent=data['parentBalance'];bridge=data['childGrossBridge'];net=data['parentChildNet']
 if not isinstance(parent.get('amountsCNY'),dict) or not isinstance(bridge.get('result'),dict):raise ValueError('父金额与子池结果结构无效')
 period=parent['reportDate'];day(period);nav=numeric(parent['amountsCNY']['净资产合计'])
 if nav<=0 or parent['currency']!='CNY' or net['reportDate']!=period or bridge['result']['reportDate']!=period:raise ValueError('净资产、币种或报告期不一致')
 dependencies=net.get('bindings')
 if dependencies is not None:
  if not isinstance(dependencies,list) or any(not isinstance(x,dict) for x in dependencies):raise ValueError('父子净额来源绑定结构无效')
  for role in ['parentBalance','childGrossBridge']:
   matches=[x for x in dependencies if x.get('role')==role]
   if len(matches)!=1 or matches[0].get('sha256')!=hashlib.sha256(raw_inputs[role]).hexdigest():raise ValueError('父子净额与大类汇总使用的来源版本不一致：'+role)
 totals={};traces=[];bindings=[];unconfirmed=[]
 pools=bridge['result']['pools'];snapshot_bindings=bridge['result']['balanceSnapshotBindings']
 if not isinstance(pools,list) or not isinstance(snapshot_bindings,list) or any(not isinstance(p,dict) or not isinstance(p.get('pool'),str) for p in pools+snapshot_bindings):raise ValueError('资产池及余额绑定须为对象数组')
 if len({p['pool'] for p in pools})!=len(pools) or len({p['pool'] for p in snapshot_bindings})!=len(snapshot_bindings):raise ValueError('资产池或余额绑定重复，禁止重复加总')
 def add(label,amount,weight,denominator,role):
  if amount<0:raise ValueError('毛资产金额不能为负')
  value=weight*amount/denominator;totals[label]=totals.get(label,Decimal(0))+value;traces.append(dict(role=role,category=label,amountCNY=str(amount),parentWeight=str(weight),nodeNAVCNY=str(denominator),parentGrossFraction=str(value)))
 def components(values,weight,denominator,role,is_parent=False):
  for key,label in ROOT_CATEGORIES.items():
   if key in values:
    if values[key] is None:unconfirmed.append({'role':role,'label':key,'scope':'root-asset-amount-unconfirmed'})
    else:add(label,numeric(values[key]),weight,denominator,role)
  child_values={key.split('/',1)[1]:value for key,value in values.items() if key.startswith('交易性金融资产/')}
  unknown=[label for label,value in child_values.items() if value is None]
  children={label:numeric(value) for label,value in child_values.items() if value is not None}
  for label in unknown:unconfirmed.append({'role':role,'label':'交易性金融资产/'+label,'scope':'trading-subcategory-unconfirmed'})
  total=numeric(values['交易性金融资产']);known=sum(children.values(),Decimal(0))
  if not child_values or known>total or (not unknown and known!=total):raise ValueError('交易性金融资产子项缺失或不勾稽')
  if is_parent and child_values.get('基金投资') is None:raise ValueError('父基金投资金额未确认，不能剔重')
  if unknown and total>known:add('未分项交易性金融资产差额',total-known,weight,denominator,role)
  for label,amount in children.items():
   if is_parent and label=='基金投资':continue
   add(label,amount,weight,denominator,role)
 components(parent['amountsCNY'],Decimal(1),nav,'parent',True)
 for pool in bridge['result']['pools']:
  if pool['status']!='balance-bound':continue
  candidates=[x for x in snapshot_bindings if x['pool']==pool['pool']]
  if len(candidates)!=1:raise ValueError('已绑定资产池缺少唯一余额快照')
  binding=candidates[0];p=Path(binding['path']);raw=p.read_bytes()
  if hashlib.sha256(raw).hexdigest()!=binding['sha256']:raise ValueError('资产池余额快照已变化')
  snapshot=json.loads(raw.decode('utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant)
  if snapshot['reportDate']!=period or snapshot['currency']!='CNY':raise ValueError('子池期间或币种不同')
  denominator=numeric(snapshot['amountsCNY']['净资产合计']);weight=numeric(pool['parentWeight'])
  if denominator<=0 or not 0<=weight<=1:raise ValueError('子池分母或父权重非法')
  components(snapshot['amountsCNY'],weight,denominator,pool['pool']);bindings.append(dict(binding))
 pending=numeric(net['unexpandedFundCarryingWeight'])
 if pending<0:raise ValueError('未展开权重不能为负')
 totals['待复核基金账面值']=pending;gross=sum(totals.values(),Decimal(0))
 if abs(gross-numeric(net['reportedGrossIncludingUnexpandedFundCarryingWeight']))>Decimal('1e-24'):raise ValueError('大类毛额与父子勾稽总额不一致，不能忽略未知科目')
 liabilities=numeric(net['reportedLiabilitiesFraction'])
 if liabilities<0 or abs(gross-liabilities-1)>Decimal('1e-24'):raise ValueError('大类毛额扣负债未对应父净资产权重1')
 return dict(type='fof-gross-asset-categories',reportDate=period,parentNAVDenominatorCNY=str(nav),grossCategoriesFraction={k:str(v) for k,v in totals.items()},unconfirmedFields=unconfirmed,traces=traces,totalGrossFraction=str(gross),liabilitiesFraction=net['reportedLiabilitiesFraction'],bindings=[dict(role=k,path=str(p.resolve()),sha256=hashlib.sha256(raw_inputs[k]).hexdigest()) for k,p in paths.items()]+bindings,limitations=['账面毛资产大类，不是净市场风险或评级','父基金投资剔重，交易性金融资产总项与子项不重复求和','来源待复核基金账面值保留，不当现金','完整期限、发行人、衍生品和流动性研究另做','空白子项不填零；明确分类合计与总项的差额保留，差额为零不认证每个未知字段为零'])
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args();r=run(json.loads(a.input.read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant),a.input.resolve().parent)
 with a.out.open('x',encoding='utf-8') as f:json.dump(r,f,ensure_ascii=False,indent=2)
