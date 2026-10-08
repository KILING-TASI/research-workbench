import unittest
from standalone import annotate_quote_dates
class Tests(unittest.TestCase):
 def test_stress_partial_scenario_preserves_unknown_assets(self):
  from portfolio_stress import analyze
  d=dict(asOf='2026-10-07',baseCurrency='CNY',holdings=[dict(code=k,currency='CNY',marketValue=50) for k in ['a','b']],scenarios=[dict(name='测试',returnShocksPct={'a':-20},assumptions=['仅冲击a'])])
  r=analyze(d)['scenarios'][0];self.assertEqual(r['coveredPnl'],-10);self.assertIsNone(r['portfolioPnl']);self.assertEqual(r['missingCodes'],['b'])
  d['scenarios'][0]['returnShocksPct']=[]
  with self.assertRaises(ValueError):analyze(d)
 def test_stress_correlation_extreme_values_preserve_sign(self):
  from portfolio_stress import corr
  self.assertAlmostEqual(corr([1e100,2e100,3e100],[-1e100,-2e100,-3e100]),-1)
  with self.assertRaises(ValueError):corr([1,2,3],[1,2])
 def test_stress_overflow_is_not_portfolio_zero(self):
  from portfolio_stress import analyze
  doc=dict(asOf='2026-10-07',baseCurrency='CNY',holdings=[dict(code='a',currency='CNY',marketValue=1e308),dict(code='b',currency='CNY',marketValue=1e308)])
  with self.assertRaises(ValueError):analyze(doc)
 def test_old_quote_is_not_relabelled(self):
  d={'asOf':'2026-10-05','rows':[{'quote':{'asOf':'2026-09-30','price':1},'gaps':[]}]}
  annotate_quote_dates(d);row=d['rows'][0];self.assertEqual(row['quote']['asOf'],'2026-09-30');self.assertEqual(row['quoteDateAssessment'],'different-date');self.assertEqual(len(row['gaps']),1)
  annotate_quote_dates(d);self.assertEqual(len(row['gaps']),1)
 def test_no_date_stays_unknown(self):
  d={'asOf':'2026-10-05','rows':[{'quote':None}]};annotate_quote_dates(d);self.assertEqual(d['rows'][0]['quoteDateAssessment'],'unknown')
 def test_matching_date(self):
  d={'asOf':'2026-10-05','rows':[{'quote':{'asOf':'2026-10-05'}}]};annotate_quote_dates(d);self.assertEqual(d['rows'][0]['quoteDateAssessment'],'same-date')
if __name__=='__main__':unittest.main()
