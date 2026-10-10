import unittest,json,sys,copy,tempfile
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from research_review import forecast_actual,public_qa,hypothesis_diff,archive_index
from review_io import publish,digest
class ExtensionsTests(unittest.TestCase):
 def spec(self,name):return json.loads((ROOT/'examples/expansion-teaching'/(name+'.json')).read_text(encoding='utf-8'))
 def test_forecast_error_and_restated(self):
  r=forecast_actual(self.spec('forecast-actual'));self.assertEqual(r['forecastMinusFirstActual'],'100000');self.assertEqual(r['restatement']['differenceFromFirst'],'50000')
 def test_late_forecast_blocked(self):
  s=self.spec('forecast-actual');s['forecast']['acquiredAt']=s['firstActual']['acquiredAt']
  with self.assertRaises(ValueError):forecast_actual(s)
 def test_unknown_basis_blocked(self):
  s=self.spec('forecast-actual');s['forecast']['scope']=None
  with self.assertRaises(ValueError):forecast_actual(s)
 def test_restated_not_overwrite(self):
  s=self.spec('forecast-actual');s['restatedActual']['supersedesId']='different'
  with self.assertRaises(ValueError):forecast_actual(s)
 def test_zero_actual_no_ratio(self):
  s=self.spec('forecast-actual');s['firstActual']['value']=0;self.assertIsNone(forecast_actual(s)['absoluteErrorRatio'])
 def test_forward_qa_label(self):self.assertEqual(public_qa(self.spec('public-qa'))['records'][0]['statementType'],'forward-looking')
 def test_private_qa_rejected(self):
  s=self.spec('public-qa');s['records'][0]['access']='private'
  with self.assertRaises(ValueError):public_qa(s)
 def test_late_qa_excluded(self):
  s=self.spec('public-qa');s['records'][0]['acquiredAt']='2027-01-01T10:00:00+08:00';self.assertEqual(len(public_qa(s)['excluded']),1)
 def test_hypothesis_diff(self):self.assertEqual(hypothesis_diff(self.spec('hypothesis-diff'))['changes'][0]['status'],'changed')
 def test_archive_blocked_preserved(self):self.assertEqual(archive_index(self.spec('archive-index'))['entries'][0]['status'],'blocked')
 def test_archive_tampering(self):
  s=self.spec('archive-index');s['entries'][0]['result']['status']='success'
  with self.assertRaises(ValueError):archive_index(s)
 def test_no_overwrite(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'report';publish({}, {'conclusion':'教学'},p,'教学')
   old=(p/'result.json').read_bytes()
   with self.assertRaises(ValueError):publish({}, {},p,'教学')
   self.assertEqual(old,(p/'result.json').read_bytes())
 def test_windows_transient_lock_retry(self):
  import research_tasks,os
  if os.name!='nt':self.skipTest('Windows only')
  real=os.open;calls=[0]
  def first_fail(*a,**kw):
   if calls[0]==0:
    calls[0]+=1;e=PermissionError('教学瞬时共享竞争');e.winerror=32;raise e
   return real(*a,**kw)
  with tempfile.TemporaryDirectory() as d:
   with patch.object(research_tasks.os,'open',side_effect=first_fail):self.assertEqual(research_tasks.transaction(lambda folder:42)(d),42)
 def test_genuine_permission_preserved(self):
  import research_tasks
  with tempfile.TemporaryDirectory() as d:
   with patch.object(research_tasks.os,'open',side_effect=PermissionError('真正权限不足')):
    with self.assertRaises(PermissionError):research_tasks.transaction(lambda folder:42)(d)
