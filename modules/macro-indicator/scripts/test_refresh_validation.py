import unittest,tempfile,json,copy
from pathlib import Path
from unittest.mock import patch
from refresh import refresh,validate_observations
import datetime as dt
class MacroRefreshValidation(unittest.TestCase):
 def observation(self,value=1):return {'period':'2026-08','value':value,'official_release_date':'2026-09-15','sourceUrl':'https://www.stats.gov.cn/test'}
 def seed(self,root):
  old=self.observation();old['fetched_at']='2026-09-16T00:00:00+08:00';data={'indicators':[{'id':'test','name':'测试','frequency':'月','value':1,'history':[old],'fetched_at':old['fetched_at'],'official_release_date':old['official_release_date'],'missing':None,'modelEligible':False}]}
  (Path(root)/'data.json').write_text(json.dumps(data),'utf-8');return data
 def test_empty_or_invalid_new_preserves_old_value_and_time(self):
  for new in [[],[self.observation(float('nan'))],[self.observation(True)]]:
   with self.subTest(new=new),tempfile.TemporaryDirectory() as root:
    old=self.seed(root)
    with patch('refresh.fetch_all',return_value=({'test':new},{},{})):result=refresh(root)
    row=result['indicators'][0];self.assertEqual(row['value'],1);self.assertEqual(row['fetched_at'],old['indicators'][0]['fetched_at']);self.assertEqual(result['fetchHealth']['fresh'],0);self.assertEqual(row['refreshStatus'],'retained-after-failure')
 def test_revised_value_does_not_inherit_prior_publication(self):
  with tempfile.TemporaryDirectory() as root:
   self.seed(root);incoming=self.observation(2);incoming['official_release_date']=None;incoming['observed_release_date']='2026-09-30'
   with patch('refresh.fetch_all',return_value=({'test':[incoming]},{},{})):result=refresh(root)
   self.assertIsNone(result['indicators'][0]['official_release_date']);self.assertEqual(incoming['official_release_date'],None)
 def test_same_value_prior_date_retains_explicit_basis(self):
  with tempfile.TemporaryDirectory() as root:
   self.seed(root);incoming=self.observation();incoming['official_release_date']=None
   with patch('refresh.fetch_all',return_value=({'test':[incoming]},{},{})):result=refresh(root)
   self.assertEqual(result['indicators'][0]['history'][0]['releaseDateBasis'],'retained-prior-unchanged-value')
 def test_future_period_duplicate_and_frequency_rejected(self):
  for items,freq in [([{'period':'2100-01','value':1,'sourceUrl':'https://www.stats.gov.cn/test'}],'月'),([self.observation(),self.observation()],'月'),([self.observation()],'季')]:
   with self.assertRaises(ValueError):validate_observations(items,freq,dt.date(2026,10,5))
 def test_one_failure_does_not_remove_another_success(self):
  with tempfile.TemporaryDirectory() as root:
   data=self.seed(root);data['indicators'].append({**copy.deepcopy(data['indicators'][0]),'id':'other'});(Path(root)/'data.json').write_text(json.dumps(data),'utf-8')
   with patch('refresh.fetch_all',return_value=({'test':[],'other':[self.observation(3)]},{},{})):result=refresh(root)
   self.assertEqual(result['fetchHealth']['fresh'],1);self.assertEqual(result['indicators'][1]['value'],3)

class SourceDuplicateEvidence(unittest.TestCase):
 def test_same_source_exact_rows_counted(self):
  from official_cycles import deduplicate_observations
  item={'period':'2026-08','value':1,'sourceUrl':'https://www.stats.gov.cn/test'}
  result=deduplicate_observations({'x':[item,dict(item)]})
  self.assertEqual(len(result['x']),1);self.assertEqual(result['x'][0]['repeatedSourceRowCount'],2)
 def test_conflicting_values_not_overwritten(self):
  from official_cycles import deduplicate_observations
  with self.assertRaisesRegex(ValueError,'冲突'):deduplicate_observations({'x':[{'period':'2026-08','value':1},{'period':'2026-08','value':2}]})
