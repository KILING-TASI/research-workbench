import copy,unittest
from fund_specialists import allocation,behavior,style,conditions,research
class Tests(unittest.TestCase):
 def report(self,date='2025-12-31'):
  return {'code':'000001','reportDate':date,'publishedAt':'2026-08-31','sourceUrl':'https://example.org/report','scope':'completeEquity','equityWeight':.8,'holdings':[{'market':'SZSE','code':'300001','shareClass':'ordinary','weight':.8}]}
 def test_missing_reports_and_impossible_top10_coverage_rejected(self):
  for fn in (allocation,behavior,style):
   for reports in ([],None,[None]):
    with self.subTest(fn=fn.__name__,reports=reports),self.assertRaises(ValueError):fn({'code':'000001','asOf':'2026-10-03','reports':reports})
  r=self.report();r['scope']='top10';r['equityWeight']=.5
  with self.assertRaisesRegex(ValueError,'超过权益'):behavior({'code':'000001','asOf':'2026-10-03','reports':[r]})
  r['equityWeight']=True
  with self.assertRaises(ValueError):behavior({'code':'000001','asOf':'2026-10-03','reports':[r]})
 def test_unknown_allocation_not_cash(self):
  r=self.report();r['weights']={'aEquity':.8,'unknown':.2};t=self.report('2026-06-30');t['weights']={'aEquity':.7,'unknown':.3};out=allocation({'code':'000001','asOf':'2026-10-03','reports':[r,t]});self.assertIsNone(out['pairs'][0]['observedAllocationDistancePct'])
 def test_top10_not_trades(self):
  r=self.report();r['scope']='top10';t=self.report('2026-06-30');t['scope']='top10';t['holdings'][0]['code']='300002';out=behavior({'code':'000001','asOf':'2026-10-03','reports':[r,t]});self.assertIsNone(out['pairs'][0]['weightAbsoluteChangePp']);self.assertIn('不能认定',out['pairs'][0]['scopeMeaning'])
 def test_style_unknown_and_future(self):
  r=self.report();r['classification']={'taxonomy':'user-style','version':'1','verified':False,'effectiveAt':'2025-12-31','sourceUrl':'https://example.org/style','securities':[{'market':'SZSE','code':'300001','shareClass':'ordinary','styleLabel':'大盘价值'}]};out=style({'code':'000001','asOf':'2026-10-03','reports':[r]});self.assertEqual(out['rows'][0]['coveragePct'],0);r['classification']['effectiveAt']='2026-01-01'
  with self.assertRaises(ValueError):style({'code':'000001','asOf':'2026-10-03','reports':[r]})
 def test_duplicate_fact_not_arbitrarily_selected(self):
  f={'field':'规模','value':30,'observedAt':'2026-09-30','sourceUrl':'https://example.org'};out=conditions({'code':'000001','asOf':'2026-10-03','facts':[f,f],'rules':[{'field':'规模','op':'lt','threshold':50}]});self.assertEqual(out['checks'][0]['status'],'unknown')
 def test_expired_style_not_current_snapshot(self):
  r=self.report('2026-06-30');r['classification']={'taxonomy':'style','version':'1','verified':True,'effectiveAt':'2025-01-01','effectiveTo':'2026-01-01','sourceUrl':'https://example.org/style','securities':[]}
  with self.assertRaisesRegex(ValueError,'已失效'):style({'code':'000001','asOf':'2026-10-03','reports':[r]})
 def test_invalid_rule_not_hidden_by_missing_fact(self):
  with self.assertRaisesRegex(ValueError,'规则字段'):conditions({'code':'000001','asOf':'2026-10-03','facts':[],'rules':[{'field':'规模','op':'typo','threshold':1}]})
 def test_one_bad_module_keeps_other_results(self):
  s={'code':'000001','asOf':'2026-10-03','inputs':{'manager':None,'conditions':{'facts':[],'rules':[]}}};r=research(s)
  self.assertTrue(any(x['module']=='manager' for x in r['gaps']));self.assertTrue(any(x['type']=='fund-research-conditions' for x in r['depthResults']))
  self.assertTrue(any(x['module']=='conditions' for x in r['gaps']));self.assertEqual(r['depthResults'][0]['status'],'partial-or-not-assessed')
 def test_conflicting_namespace_not_merged_as_same_security(self):
  r=self.report();r['holdings'][0].update(market='HKEX',securityNamespace='CN-equity')
  with self.assertRaisesRegex(ValueError,'冲突'):behavior({'code':'000001','asOf':'2026-10-03','reports':[r]})
 def test_duplicate_gap_report_period_not_silently_accepted(self):
  r=self.report();r['scope']='top10'
  with self.assertRaisesRegex(ValueError,'递增'):style({'code':'000001','asOf':'2026-10-03','reports':[r,copy.deepcopy(r)]})
 def test_style_later_publication_is_retrospective(self):
  r=self.report('2026-06-30');r['classification']={'taxonomy':'style','version':'1','verified':True,'effectiveAt':'2026-06-30','publishedAt':'2026-09-30','sourceUrl':'https://example.org/style','securities':[{'market':'SZSE','code':'300001','shareClass':'ordinary','styleLabel':'大盘价值'}]}
  out=style({'code':'000001','asOf':'2026-10-03','reports':[r]});self.assertEqual(out['rows'][0]['classificationPublicationStatus'],'retrospective-only')
if __name__=='__main__':unittest.main()
