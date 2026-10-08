import unittest,copy
from fund_enhancements import pool_snapshot,attribution_panel,clauses,export_template
class Tests(unittest.TestCase):
 def test_missing_pool_member(self):
  s={'pool':{'name':'观察池','codes':['000001','000002']},'cards':[{'code':'000001','metrics':{'Sharpe':1},'sourceUrl':'https://example.org'}]};r=pool_snapshot(s);self.assertEqual(r['cards'][1]['status'],'missing');self.assertIn('maximumDrawdownPct',r['cards'][0]['gaps'])
 def test_missing_period_not_filled(self):
  r=attribution_panel({'periods':[{'start':'2025-12-31','end':'2026-03-31','reason':'未取得'},{'start':'2026-03-31','end':'2026-06-30'}]});self.assertEqual(len(r['rows']),2);self.assertEqual(r['signCounts']['selectionPp']['availablePeriods'],0)
 def test_clause_is_candidate(self):
  r=clauses({'query':'巨额赎回','documentResult':{'sourceUrl':'https://example.org','documentSha256':'abc','candidates':[{'excerpt':'巨额赎回条款','page':5}]}});self.assertEqual(r['items'][0]['tags'],['巨额赎回']);self.assertIn('candidate',r['items'][0]['status'])
 def test_template_type_boundary(self):
  with self.assertRaises(ValueError):export_template({'template':'fof','result':{'type':'fund-comparison'}})
 def test_all_null_metrics_not_described_as_obtained(self):
  r=pool_snapshot({'pool':{'name':'池','codes':['000001']},'cards':[{'code':'000001','metrics':{'Sharpe':None,'CAGRPct':None}}]})
  self.assertIn('历史指标未取得',r['cards'][0]['summary'])
 def test_panel_cannot_combine_different_benchmarks(self):
  from test_research_library import Tests as Fixture
  a=Fixture().spec();a.update(benchmarkId='index-a',portfolioId='fund',weightScope='equity',currency='CNY');b=copy.deepcopy(a);b.update(start=a['end'],end='2026-06-30',asOf='2026-07-31',weightDate='2026-03-31',benchmarkId='index-b')
  r=attribution_panel({'periods':[{'start':a['start'],'end':a['end'],'input':a},{'start':b['start'],'end':b['end'],'input':b}]})
  self.assertEqual(len(r['rows']),2);self.assertIsNone(r['signCounts']['selectionPp']['positivePeriods']);self.assertEqual(r['comparisonStatus'],'not-established');self.assertEqual(r['rows'][0]['informationTiming']['status'],'publication-date-missing')
if __name__=='__main__':unittest.main()
