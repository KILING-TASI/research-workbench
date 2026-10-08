import json,tempfile,unittest
from pathlib import Path
from fund_balance_gross_bridge import run,explicit_categories

class Tests(unittest.TestCase):
 def test_malformed_requests_fail_before_source_access(self):
  for spec in [None,[],{},dict(balanceSnapshots={},parentHoldings=[None])]:
   with self.assertRaises(ValueError):run(spec,Path('.'))
 def test_duplicate_snapshot_fields_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'snapshot.json';p.write_text('{"type":"selected-fund-balance-snapshot","type":"other"}','utf-8')
   with self.assertRaisesRegex(ValueError,'重复字段'):run(dict(balanceSnapshots={'pool':str(p)},parentHoldings=[]),Path(d))

 def test_unknown_and_legacy_dash_not_zero_categories(self):
  s={'amountsCNY':{'货币资金':'10.00','衍生金融资产':None,'买入返售金融资产':'0'},'evidence':[{'label':'买入返售金融资产','reportedCurrentCell':'-'}]}
  known,unknown=explicit_categories(s,{'货币资金':'bank','衍生金融资产':'derivatives','买入返售金融资产':'repo'})
  self.assertEqual(known,{'bank':'10.00'});self.assertEqual(len(unknown),2)
if __name__=='__main__':unittest.main()
