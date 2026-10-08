import unittest
from fund_investment_reconcile import reconcile,extract
from fund_report_fof import money
class Tests(unittest.TestCase):
 def rows(self,pct='50.00'):return dict(rows=[dict(name='ETF',marketValueCNY='50.00',reportedWeightPct=pct)])
 def test_exact_total_not_complete_portfolio(self):
  r=reconcile(self.rows(),'50.00','100.00');self.assertTrue(r['accountingTotalVerified']);self.assertFalse(r['completeAssetPortfolio'])
 def test_missing_amount_preserved(self):
  r=reconcile(self.rows(),'70','100');self.assertEqual(r['differenceCNY'],'20.00');self.assertFalse(r['accountingTotalVerified'])
 def test_wrong_denominator(self):
  with self.assertRaises(ValueError):reconcile(self.rows(),'50','200')
 def test_rounding(self):self.assertTrue(reconcile(self.rows('49.995'),'50','100')['accountingTotalVerified'])
 def test_invalid_total(self):
  for v in ['NaN','-1']:
   with self.assertRaises(ValueError):reconcile(self.rows(),v,'100')
 def test_unverified_identity_rejected_before_pdf(self):
  for state in ['pending','mismatch',True]:
   with self.assertRaisesRegex(ValueError,'身份未核验'):extract({'reportDate':'2025-12-31','asOf':'2026-10-07','metadata':{'publishedAt':'2026-03-31'},'identityStatus':state})
 def test_complete_fof_nonfinite_rejected(self):
  for value in ['NaN','Infinity','-Infinity']:
   with self.assertRaises(ValueError):money(value)
if __name__=='__main__':unittest.main()
