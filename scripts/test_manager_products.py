import unittest,copy
from manager_products import build,markdown
class Tests(unittest.TestCase):
 def test_end_conflicts_with_later_open_confirmation(self):
  s=self.spec();other=copy.deepcopy(s['products'][0]);other['evaluationInput']['managers'][0]['end']='2025-10-01';s['products'].append(other)
  result=build(s);self.assertTrue(result['conflicts']);self.assertFalse(result['managers'][0]['knownManagementIntervals'])
 def test_earlier_open_record_is_not_false_conflict(self):
  s=self.spec();s['products'][0]['evaluationInput']['managers'][0]['confirmedThrough']='2025-06-30';other=copy.deepcopy(s['products'][0]);other['evaluationInput']['managers'][0].update(end='2025-10-01',confirmedThrough='2025-12-31');s['products'].append(other)
  self.assertFalse(build(s)['conflicts'])
 def test_named_query_retains_co_manager_evidence(self):
  s=self.spec();s['managerName']='某经理';m=copy.deepcopy(s['products'][0]['evaluationInput']['managers'][0]);m.update(name='共同经理',start='2023-01-01',end='2024-01-01',sourceUrl='https://example.org/co',locator='第11页');s['products'][0]['evaluationInput']['managers'].append(m)
  r=build(s);self.assertEqual(len(r['managers']),1);o=r['managers'][0]['products'][0]['performance']['coManagementIntervals'][0]
  self.assertEqual(o['sourceUrl'],'https://example.org/co');text=markdown(r);self.assertIn('共同经理',text);self.assertIn('不能把两位经理',text)
 def test_no_overlap_not_proof_of_solo_management(self):
  self.assertIn('不能据此确认全程独立管理',markdown(build(self.spec())))
 def spec(self):
  e=dict(code='000001',asOf='2026-10-03',managers=[dict(name='某经理',start='2020-01-01',confirmedThrough='2025-12-31',publishedAt='2026-03-31',sourceUrl='https://example.org/report',locator='p10')])
  return dict(asOf='2026-10-03',products=[dict(managerCompany='甲公司',name='产品',evaluationInput=e)])
 def test_stale_not_current(self):
  r=build(self.spec());self.assertIn('待核验',r['managers'][0]['products'][0]['currentStatus'])
 def test_left_not_current(self):
  s=self.spec();s['products'][0]['evaluationInput']['managers'][0]['end']='2025-10-01';self.assertEqual(build(s)['managers'][0]['products'][0]['currentStatus'],'已披露离任')
 def test_same_name_company_not_merge(self):
  s=self.spec();b=copy.deepcopy(s['products'][0]);b['managerCompany']='乙公司';b['evaluationInput']['code']='000002';s['products'].append(b);r=build(s);self.assertEqual(len(r['managers']),2);text=markdown(r);self.assertIn('乙公司',text);self.assertIn('身份匹配方式',text)
 def test_conflict(self):
  s=self.spec();b=copy.deepcopy(s['products'][0]);b['evaluationInput']['managers'][0]['start']='2021-01-01';s['products'].append(b);self.assertTrue(build(s)['conflicts'])
 def test_conflict_not_summarized_as_confirmed_interval(self):
  s=self.spec();b=copy.deepcopy(s['products'][0]);b['evaluationInput']['managers'][0]['start']='2021-01-01';s['products'].append(b)
  r=build(s);self.assertFalse(r['managers'][0]['knownManagementIntervals']);self.assertIsNone(r['managers'][0]['earliestKnownAppointment']);self.assertIn('任职起止记录冲突',markdown(r))
 def test_empty_query_explained(self):
  s=self.spec();s['managerName']='另一经理';self.assertIn('不代表该经理没有管理产品',markdown(build(s)))
 def test_table_not_interrupted_and_code_count_not_strategy_count(self):
  s=self.spec();b=copy.deepcopy(s['products'][0]);b['evaluationInput']['code']='000002';s['products'].append(b);r=build(s)
  self.assertEqual(r['managers'][0]['knownCodeCount'],2);self.assertIsNone(r['managers'][0]['strategyCount']);self.assertIn('不能作为独立策略数量',markdown(r))
 def test_duplicate(self):
  s=self.spec();s['products']*=2
  with self.assertRaises(ValueError):build(s)
 def test_name_query(self):
  s=self.spec();s['managerName']='另一经理';self.assertFalse(build(s)['managers'])
if __name__=='__main__':unittest.main()
