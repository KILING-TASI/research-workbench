import unittest
from observation_brief import brief
class MacroObservationBrief(unittest.TestCase):
 def data(self):return {'indicators':[{'id':'x','name':'测试指标','value':1,'data_period':'2026-08','sourceUrl':'https://www.stats.gov.cn/test','official_release_date':None,'fetched_at':'2026-10-05','unit':'%'}]}
 def test_unknown_publication_not_replaced_with_fetch_date(self):
  text=brief(self.data());self.assertIn('未确认',text);self.assertNotIn('| 2026-10-05 |',text)
 def test_missing_kept_blank_not_zero(self):
  d=self.data();d['indicators'][0]['value']=None;text=brief(d);self.assertIn('0项有观测',text);self.assertIn('未填零',text)
 def test_invalid_value_rejected(self):
  d=self.data();d['indicators'][0]['value']=float('nan')
  with self.assertRaises(ValueError):brief(d)
 def test_nonofficial_host_rejected(self):
  d=self.data();d['indicators'][0]['sourceUrl']='https://www.stats.gov.cn.example.org/test'
  with self.assertRaises(ValueError):brief(d)
