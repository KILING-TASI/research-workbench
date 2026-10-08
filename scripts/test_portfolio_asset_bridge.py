import unittest,copy,tempfile,hashlib
from pathlib import Path
from portfolio_asset_bridge import calculate,build
class Tests(unittest.TestCase):
 def test_malformed_input_and_missing_reason_not_silently_accepted(self):
  for value in [None,[],{},dict(asOf='2026-06-30',currency='CNY',assets=[None])]:
   with self.assertRaises(ValueError):calculate(value)
  for reason in [True,[], ' ']:
   s=self.fixture();s['assets'][0]['missingReasons']={'bondCNY':reason}
   with self.assertRaises(ValueError):calculate(s)
  s=self.fixture();s['assets'][0]['weight']='not-a-number'
  with self.assertRaises(ValueError):calculate(s)
 def test_cross_page_positions_and_changed_file_hash(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'prepared-source.txt';p.write_text('teaching source; not a parsed PDF')
   s=self.fixture();a=s['assets'][0];a.update(source=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),assetPage=2,assetPages=[2,3],balancePage=1)
   self.assertEqual(build(s)['sources'][0]['assetPages'],[2,3])
   for pages in ([3,2],[2,2],[2,0],[True,3]):
    a['assetPages']=pages
    with self.assertRaises(ValueError):build(s)
   a['assetPages']=[2,3];p.write_text('changed source')
   with self.assertRaisesRegex(ValueError,'来源文件版本变化'):build(s)
 def fixture(self):return dict(asOf='2026-06-30',currency='CNY',assets=[dict(code='000001',reportDate='2026-06-30',currency='CNY',weight='1',stockCNY='80',bondCNY=None,bankAndSettlementCashCNY='25',otherAssetsCNY='5',totalAssetsCNY='110',liabilitiesCNY='10',netAssetsCNY='100',missingReasons={'bondCNY':'原表未列金额'})])
 def test_assets_exceed_nav_with_liabilities_and_missing_not_zero(self):
  r=calculate(self.fixture());self.assertEqual(r['componentPctOfPortfolioNAV']['bankAndSettlementCashCNY'],'25.00');self.assertEqual(r['netBridgeTotalPct'],'100.00');self.assertEqual(r['checks'][0]['missingFields'],['bondCNY']);self.assertIsNone(r['componentPctOfPortfolioNAV']['bondCNY']);self.assertFalse(r['originalParsingPerformed'])
 def test_mismatch_wrong_date_weight_or_duplicate_rejected(self):
  for field,value in [('netAssetsCNY','99'),('reportDate','2026-03-31'),('currency','USD'),('weight','0.5'),('stockCNY','NaN')]:
   s=self.fixture();s['assets'][0][field]=value
   with self.subTest(field=field),self.assertRaises(ValueError):calculate(s)
  s=self.fixture();s['assets'].append(copy.deepcopy(s['assets'][0]))
  with self.assertRaises(ValueError):calculate(s)
 def test_missing_without_reason_or_asset_gap_rejected(self):
  s=self.fixture();s['assets'][0]['missingReasons']={}
  with self.assertRaises(ValueError):calculate(s)
  s=self.fixture();s['assets'][0]['otherAssetsCNY']='4'
  with self.assertRaises(ValueError):calculate(s)
