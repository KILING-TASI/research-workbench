import unittest
from research_report_plan import plan,PROFILES
from company_one_page import build,markdown
class Tests(unittest.TestCase):
 def base(self):return {'asOf':'2026-09-30','identity':{'name':'测试','market':'CN','code':'000333'}}
 def item(self):return {'text':'测试来源内容','observedAt':'2026-06-30','publishedAt':'2026-08-29','sourceUrl':'https://example.org/report.pdf','locator':'PDF第7页','basis':'research-explanation'}
 def test_planning_never_certifies_data_gaps(self):
  r=plan(dict(asOf='2026-09-30',kind='stock',subject='测试',code='000333'));self.assertEqual(r['dataGapStatus'],'capability-limitations-not-subject-acquisition-audit');self.assertEqual(len(r['sectionEvidenceStatus']),len(r['sections']));self.assertTrue(all(x['status']=='not-acquired-or-reviewed-by-this-planner' for x in r['sectionEvidenceStatus']))
 def test_output_mutation_cannot_change_next_plan(self):
  spec=dict(asOf='2026-09-30',kind='stock',subject='测试',code='000333');r=plan(spec);r['sections'].clear();r['dataGaps'].clear();self.assertTrue(plan(spec)['sections']);self.assertTrue(plan(spec)['dataGaps'])
 def test_bad_code_not_serialized_as_identity(self):
  with self.assertRaises(ValueError):plan(dict(asOf='2026-09-30',kind='concept',subject='测试',code={'code':'x'}))
 def test_all_profiles_distinct(self):
  for key,p in PROFILES.items():
   result=plan({'asOf':'2026-09-30','kind':p['kinds'][0],'subject':'测试','code':'000333'})
   self.assertEqual(result['profile'],key);self.assertEqual(result['status'],'planned-not-executed');self.assertEqual(result['externalInterfaces']['mx_and_MQL'],'not-connected')
 def test_etf_does_not_enter_fund(self):self.assertEqual(plan({'asOf':'2026-09-30','kind':'fund','subject':'测试','code':'001938','question':'ETF研究'})['status'],'needs-kind-confirmation')
 def test_multiple_products_keep_comparison(self):self.assertEqual(plan({'asOf':'2026-09-30','kind':'etf','subject':'测试','question':'两只ETF对比'})['status'],'use-existing-multi-object-entry')
 def test_no_invented_identity(self):self.assertEqual(plan({'asOf':'2026-09-30','kind':'stock','subject':'测试'})['status'],'needs-identity')
 def test_profile_conflict(self):
  with self.assertRaises(ValueError):plan({'asOf':'2026-09-30','kind':'stock','subject':'测试','code':'000333','profile':'fund'})
 def test_company_optional_fields(self):
  s=self.base();s['supplyChain']=[self.item()];r=build(s);self.assertIn('产销链与供应链',markdown(r));self.assertNotIn('forecast',r['sections'])
 def test_deep_company_missing_sections_stay_gaps(self):
  s=self.base();s['deepResearch']=True;r=build(s);self.assertEqual(len(r['sections']),12);self.assertIn('盈利预测假设未取得带来源资料',r['gaps'])
 def test_forecast_cannot_be_fact(self):
  s=self.base();i=self.item();i.update(basis='source-statement',targetPeriod='2027-12-31',assumptions=['假设']);s['forecast']=[i]
  with self.assertRaises(ValueError):build(s)
 def test_forecast_requires_assumptions(self):
  s=self.base();i=self.item();i.update(basis='assumption',targetPeriod='2027-12-31');s['forecast']=[i]
  with self.assertRaises(ValueError):build(s)
 def test_forecast_explains_target(self):
  s=self.base();i=self.item();i.update(basis='assumption',targetPeriod='2027-12-31',assumptions=['需求情景']);s['forecast']=[i];self.assertIn('需求情景',markdown(build(s)))
 def test_forecast_past_target_rejected(self):
  s=self.base();i=self.item();i.update(basis='assumption',targetPeriod='2025-12-31',assumptions=['假设']);s['forecast']=[i]
  with self.assertRaises(ValueError):build(s)
 def test_catalyst_needs_counter_evidence(self):
  s=self.base();i=self.item();i['trigger']='条件';s['catalysts']=[i]
  with self.assertRaises(ValueError):build(s)
 def test_catalyst_stays_conditional(self):
  s=self.base();i=self.item();i.update(trigger='订单兑现',counterEvidence='订单取消');s['catalysts']=[i];text=markdown(build(s));self.assertIn('尚未确认触发',text);self.assertIn('订单取消',text)
 def test_deep_flag_string_rejected(self):
  s=self.base();s['deepResearch']='false'
  with self.assertRaises(ValueError):build(s)
if __name__=='__main__':unittest.main()
