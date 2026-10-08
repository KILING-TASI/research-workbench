import unittest,tempfile,hashlib,copy
from pathlib import Path
from decimal import Decimal
from gross_asset_lookthrough import calculate
class Tests(unittest.TestCase):
 def test_invalid_page_declarations_not_evidence(self):
  for pages in [[True],[1,1],[0],'PDF1']:
   with tempfile.TemporaryDirectory() as d:
    s=self.fixture(d);s['pools']['same']['source']['physicalPages']=pages
    with self.assertRaises(ValueError):calculate(s)
 def test_empty_parent_does_not_claim_uncovered_portfolio(self):
  with tempfile.TemporaryDirectory() as d:
   s=self.fixture(d);s['parentHoldings']=[]
   with self.assertRaises(ValueError):calculate(s)
 def fixture(self,d):
  p=Path(d)/'report.pdf';p.write_bytes(b'original');node=dict(reportDate='2026-06-30',publishedAt='2026-08-31',currency='CNY',totalAssetsCNY='120',totalLiabilitiesCNY='20',netAssetsCNY='100',assetsCNY={'bond':'115'},liabilitiesCNY={'repo':'18'},source=dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),physicalPages=[1]))
  return dict(reportDate='2026-06-30',currency='CNY',parentHoldings=[dict(code='000001',pool='same',weight='.1'),dict(code='000002',pool='same',weight='.2')],pools={'same':node})
 def test_same_pool_merges_and_retains_gross_leverage(self):
  with tempfile.TemporaryDirectory() as d:
   r=calculate(self.fixture(d));self.assertEqual(len(r['pools']),1);self.assertEqual(Decimal(r['pools'][0]['assets'][0]['childGrossExposureAgainstNAV']),Decimal('1.15'));self.assertEqual(Decimal(r['coveredParentNAVWeight']),Decimal('.3'));self.assertEqual(r['pools'][0]['unclassifiedAssetsCNY'],'5');self.assertEqual(r['pools'][0]['unclassifiedLiabilitiesCNY'],'2')
 def test_unknown_pool_stays_unknown(self):
  with tempfile.TemporaryDirectory() as d:
   s=self.fixture(d);s['pools']={};r=calculate(s);self.assertEqual(r['coveredParentNAVWeight'],'0');self.assertEqual(r['uncoveredParentNAVWeight'],'1');self.assertEqual(r['pools'][0]['status'],'missing-pool')
 def test_subtotal_double_count_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   s=self.fixture(d);s['pools']['same']['assetsCNY']['total']='120'
   with self.assertRaisesRegex(ValueError,'分类金额超过'):calculate(s)
 def test_wrong_balance_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   s=self.fixture(d);s['pools']['same']['netAssetsCNY']='99'
   with self.assertRaisesRegex(ValueError,'不勾稽'):calculate(s)
if __name__=='__main__':unittest.main()
