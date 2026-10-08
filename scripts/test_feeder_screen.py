import unittest
from multidimensional_screen import check
class Tests(unittest.TestCase):
 def test_actual_report_cutoff_not_relabelled_as_pool_cutoff(self):
  from feeder_holdings_screen import run_many
  from unittest.mock import patch
  dossier=dict(code='000001',asOf='2026-10-03',report=dict(code='000001'))
  with patch('feeder_holdings_screen.run',return_value=dict(screeningInput=dict(asOf='2026-09-30'))):r=run_many([dossier],[self.rule()],'2026-10-03')
  self.assertEqual(len(r['unknown']),1);self.assertIn('实际截止日',r['unknown'][0]['checks'][0]['reason'])
 def holding(self):return dict(holdings=dict(basis='verified-feeder-equity-lookthrough',sourceUrl='https://example.org/a',observedAt='2025-12-31',complete=False,coveredSecurityNamespaces=['CN-equity'],value=[dict(code='600001',market='CN-equity',weightPct=2)]))
 def rule(self,code='600001',weight=0):return dict(kind='holding',code=code,market='CN-equity',minimumWeightPct=weight)
 def test_pool_all_missing_kept_unknown(self):
  from feeder_holdings_screen import run_many
  r=run_many([dict(code='000001',asOf='2026-10-03'),dict(code='000002',asOf='2026-09-30')],[self.rule()],'2026-10-03')
  self.assertEqual(len(r['unknown']),2);self.assertEqual(r['candidateCount'],2);self.assertEqual(r['coverage'][0]['usable'],0)
 def test_pool_duplicate_rejected(self):
  from feeder_holdings_screen import run_many
  with self.assertRaises(ValueError):run_many([dict(code='000001'),dict(code='000001')],[self.rule()],'2026-10-03')
 def test_positive_known_weight(self):self.assertTrue(check(self.holding(),self.rule(weight=1),'2026-10-03')[0])
 def test_absent_unknown(self):self.assertIsNone(check(self.holding(),self.rule('600002'),'2026-10-03')[0])
 def test_below_threshold_unknown(self):self.assertIsNone(check(self.holding(),self.rule(weight=3),'2026-10-03')[0])
 def test_fake_complete_rejected(self):
  x=self.holding();x['holdings']['complete']=True
  with self.assertRaises(ValueError):check(x,self.rule(),'2026-10-03')
if __name__=='__main__':unittest.main()
