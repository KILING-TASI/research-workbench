import unittest
from fund_comparison_brief import report
class ComparisonBrief(unittest.TestCase):
 def data(self):return {'asOf':'2026-09-30','start':'2026-09-01','rows':[{'code':c,'basis':'nav-with-distributions','frequency':'trading_day','comparisonGroup':'输入研究组','history':[{'date':'2026-09-01','nav':1},{'date':'2026-09-02','nav':v}]} for c,v in [('006113',1.1),('009342',.9)]]}
 def test_report_explains_short_data_and_unverified_peer(self):
  result,text=report(self.data());self.assertIsNone(result['rows'][0]['annualizedVolPct']);self.assertIn('未计算',text);self.assertIn('未独立核验为同类',text);self.assertIn('红利再投',text)
 def test_different_group_rejected_before_report(self):
  d=self.data();d['rows'][0]['comparisonGroup']='另一类'
  with self.assertRaises(ValueError):report(d)
 def test_unhandled_distribution_cannot_produce_report(self):
  d=self.data();d['rows'][0]['history'][1]['distribution']='拆分'
  with self.assertRaises(ValueError):report(d)
 def test_findings_bind_to_calculated_differences(self):
  r,text=report(self.data());f=r['findings'][0];a,b=r['rows']
  self.assertAlmostEqual(f['returnDifferencePctPoints'],a['totalReturnPct']-b['totalReturnPct'])
  self.assertAlmostEqual(f['drawdownMagnitudeDifferencePctPoints'],abs(a['drawdownPct'])-abs(b['drawdownPct']))
  self.assertEqual(f['codes'],['006113','009342']);self.assertEqual(f['type'],'calculated-history')
  self.assertTrue(any(f['type']=='calculation-limit' for f in r['findings']))
 def test_alignment_loss_remains_visible_with_summary(self):
  d=self.data();d['rows'][0]['history'].append({'date':'2026-09-03','nav':1.0});d['rows'][1]['history'].append({'date':'2026-09-04','nav':1.0})
  d['rows'][0]['history'].append({'date':'2026-09-04','nav':1.0})
  r,text=report(d);self.assertTrue(r['findings']);self.assertIsNone(r['rows'][0]['annualizedVolPct'])
  self.assertEqual(r['alignment'][0]['excludedObservations'],1)
 def test_conclusion_follows_tradeoff_not_a_buy_recommendation(self):
  d=self.data();d['rows'][0]['history']=[{'date':'2026-09-01','nav':1},{'date':'2026-09-02','nav':.7},{'date':'2026-09-03','nav':1.3}]
  d['rows'][1]['history']=[{'date':'2026-09-01','nav':1},{'date':'2026-09-02','nav':.9},{'date':'2026-09-03','nav':1.1}]
  r,text=report(d);self.assertIn('收益更高，但回撤也更深',r['findings'][0]['conclusion']);self.assertIn('> ',text)

 def test_three_fund_tradeoff_is_explained(self):
  import copy
  d=self.data();third=copy.deepcopy(d['rows'][0]);third['code']='000003';third['history'][1]['nav']=1.05;d['rows'].append(third)
  # A high-return product first falls sharply; the modest-return product never falls.
  d['rows'][0]['history']=[{'date':'2026-09-01','nav':1},{'date':'2026-09-02','nav':.7},{'date':'2026-09-03','nav':1.3}]
  d['rows'][1]['history'].append({'date':'2026-09-03','nav':.95});third['history'].append({'date':'2026-09-03','nav':1.05})
  r,text=report(d);self.assertIn('优势分属不同产品',r['findings'][0]['conclusion']);self.assertEqual(r['findings'][0]['returnLeaderCodes'],['006113']);self.assertEqual(r['findings'][0]['smallestDrawdownCodes'],['000003'])
 def test_ties_not_silently_given_single_winner(self):
  import copy
  d=self.data();third=copy.deepcopy(d['rows'][0]);third['code']='000003';d['rows'].append(third)
  r,text=report(d);self.assertIn('存在并列',r['findings'][0]['conclusion']);self.assertEqual(len(r['findings'][0]['returnLeaderCodes']),2)
