import json,hashlib,tempfile,unittest
from pathlib import Path
from fof_asset_categories import run
class Tests(unittest.TestCase):
 def test_registered_net_source_must_match_category_source(self):
  with tempfile.TemporaryDirectory() as d:
   spec,_,_=self.fixture(d);p=Path(spec['parentChildNet']);x=json.loads(p.read_text('utf-8'));x['bindings']=[dict(role='parentBalance',sha256='wrong')];p.write_text(json.dumps(x),'utf-8')
   with self.assertRaisesRegex(ValueError,'来源版本不一致'):run(spec,d)
 def test_inconsistent_liabilities_and_missing_binding_rejected(self):
  for case in ['liabilities','binding']:
   with tempfile.TemporaryDirectory() as d:
    spec,_,_=self.fixture(d)
    p=Path(spec['parentChildNet'] if case=='liabilities' else spec['childGrossBridge']);data=json.loads(p.read_text('utf-8'))
    if case=='liabilities':data['reportedLiabilitiesFraction']='.3'
    else:data['result']['balanceSnapshotBindings']=[]
    p.write_text(json.dumps(data),'utf-8')
    with self.subTest(case=case),self.assertRaises(ValueError):run(spec,d)
 def test_duplicate_asset_pool_cannot_be_counted_twice(self):
  with tempfile.TemporaryDirectory() as d:
   spec,_,_=self.fixture(d);p=Path(spec['childGrossBridge']);bridge=json.loads(p.read_text('utf-8'));bridge['result']['pools']*=2;p.write_text(json.dumps(bridge),'utf-8')
   with self.assertRaisesRegex(ValueError,'重复'):run(spec,d)
 def fixture(self,d):
  p=Path(d)/'child.json';child=dict(reportDate='2026-06-30',currency='CNY',amountsCNY={'净资产合计':'100','货币资金':'10','交易性金融资产':'100','交易性金融资产/股票投资':'40','交易性金融资产/债券投资':'60'});p.write_text(json.dumps(child),encoding='utf-8')
  parent=dict(reportDate='2026-06-30',currency='CNY',amountsCNY={'净资产合计':'100','货币资金':'50','交易性金融资产':'70','交易性金融资产/股票投资':'10','交易性金融资产/基金投资':'60'})
  bridge=dict(result=dict(reportDate='2026-06-30',pools=[dict(pool='child',status='balance-bound',parentWeight='.6')],balanceSnapshotBindings=[dict(pool='child',path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())]))
  net=dict(reportDate='2026-06-30',unexpandedFundCarryingWeight='0',reportedGrossIncludingUnexpandedFundCarryingWeight='1.26',reportedLiabilitiesFraction='.26');spec={}
  for key,data in [('parentBalance',parent),('childGrossBridge',bridge),('parentChildNet',net)]:
   q=Path(d)/(key+'.json');q.write_text(json.dumps(data),encoding='utf-8');spec[key]=str(q)
  return spec,p,parent
 def test_parent_fund_not_added_twice(self):
  with tempfile.TemporaryDirectory() as d:
   spec,_,_=self.fixture(d);r=run(spec,d);self.assertEqual(r['totalGrossFraction'],'1.26');self.assertEqual(r['grossCategoriesFraction']['股票投资'],'0.34');self.assertNotIn('基金投资',r['grossCategoriesFraction'])
 def test_missing_subcategory_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   spec,_,parent=self.fixture(d);parent['amountsCNY'].pop('交易性金融资产/股票投资');Path(spec['parentBalance']).write_text(json.dumps(parent),encoding='utf-8')
   with self.assertRaisesRegex(ValueError,'子项缺失或不勾稽'):run(spec,d)
 def test_changed_snapshot_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   spec,p,_=self.fixture(d);p.write_text('{}',encoding='utf-8')
   with self.assertRaisesRegex(ValueError,'快照已变化'):run(spec,d)
 def test_explicit_unknown_field_not_zero_imputed(self):
  with tempfile.TemporaryDirectory() as d:
   spec,_,parent=self.fixture(d);parent['amountsCNY']['交易性金融资产/贵金属投资']=None;parent['amountsCNY']['应收股利']=None;Path(spec['parentBalance']).write_text(json.dumps(parent),'utf-8')
   r=run(spec,d);self.assertNotIn('贵金属投资',r['grossCategoriesFraction']);self.assertEqual(len(r['unconfirmedFields']),2);self.assertEqual(r['totalGrossFraction'],'1.26')
if __name__=='__main__':unittest.main()
