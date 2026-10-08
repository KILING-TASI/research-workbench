import json,tempfile,unittest
from pathlib import Path
from fof_parent_child_balance import run
class Tests(unittest.TestCase):
 def test_duplicate_parent_details_and_negative_liabilities_rejected(self):
  for case in ['duplicate','negative']:
   with tempfile.TemporaryDirectory() as d:
    spec,_=self.fixture(d);p=Path(spec['parentFundDetails'] if case=='duplicate' else spec['parentBalance']);x=json.loads(p.read_text('utf-8'))
    if case=='duplicate':x['holdings'].append(dict(code='000001',marketValueCNY='0'))
    else:x['amountsCNY'].update({'资产总计':'90','负债合计':'-10'})
    p.write_text(json.dumps(x),'utf-8')
    with self.assertRaises(ValueError):run(spec,d)
 def fixture(self,d):
  period='2026-06-30';parent=dict(type='selected-fund-balance-snapshot',reportDate=period,currency='CNY',amountsCNY={'净资产合计':'100','资产总计':'110','负债合计':'10','交易性金融资产/基金投资':'60'});details=dict(reportDate=period,netAssetsCNY='100',holdings=[dict(code='000001',marketValueCNY='40'),dict(code='000002',marketValueCNY='20')]);bridge=dict(input=dict(reportDate=period,currency='CNY',parentHoldings=[dict(code='000001',weight='.4'),dict(code='000002',weight='.2')]),result=dict(type='disclosed-gross-assets-liabilities',reportDate=period,coveredParentNAVWeight='.4',parentGrossAssets='.5',parentLiabilities='.1'))
  spec={}
  for key,data in [('parentBalance',parent),('parentFundDetails',details),('childGrossBridge',bridge)]:
   p=Path(d)/(key+'.json');p.write_text(json.dumps(data),encoding='utf-8');spec[key]=str(p)
  return spec,bridge
 def test_unexpanded_value_preserved_and_fund_not_counted_twice(self):
  with tempfile.TemporaryDirectory() as d:
   spec,_=self.fixture(d);r=run(spec,d);self.assertEqual(r['unexpandedFundCarryingWeight'],'0.2');self.assertEqual(r['reportedGrossIncludingUnexpandedFundCarryingWeight'],'1.2');self.assertEqual(r['netNAVWeight'],'1.0')
 def test_missing_parent_share_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   spec,bridge=self.fixture(d);bridge['input']['parentHoldings'].pop();Path(spec['childGrossBridge']).write_text(json.dumps(bridge),encoding='utf-8')
   with self.assertRaisesRegex(ValueError,'全部父基金'):run(spec,d)
 def test_negative_unexpanded_weight_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   spec,bridge=self.fixture(d);bridge['result'].update(coveredParentNAVWeight='.7',parentGrossAssets='.8');Path(spec['childGrossBridge']).write_text(json.dumps(bridge),encoding='utf-8')
   with self.assertRaisesRegex(ValueError,'覆盖权重'):run(spec,d)
if __name__=='__main__':unittest.main()
