import unittest,datetime as dt
import research_pipeline as r

class AlignmentTests(unittest.TestCase):
 def spec(self):
  history=[{'date':(dt.date(2025,1,1)+dt.timedelta(days=i)).isoformat(),'nav':1+i/1000} for i in range(130)]
  return {'asOf':'2025-05-10','rows':[{'code':c,'basis':'nav-with-distributions','comparisonGroup':'test','frequency':'trading_day','history':[dict(x) for x in history]} for c in ['001938','003095']]}
 def test_requested_start_honored(self):
  s=self.spec();s['start']='2025-05-01';out=r.compare(s)
  self.assertEqual(out['start'],'2025-05-01');self.assertEqual(out['rows'][0]['observationCount'],9)
 def test_alignment_loss_blocks_annual_volatility(self):
  s=self.spec();del s['rows'][1]['history'][50];out=r.compare(s)
  self.assertIsNone(out['rows'][0]['annualizedVolPct']);self.assertEqual(out['alignment'][0]['excludedObservations'],1)
  self.assertIsNone(out['rows'][1]['annualizedVolPct'])
 def test_bad_start_rejected(self):
  s=self.spec();s['start']='2026-01-01'
  with self.assertRaisesRegex(ValueError,'起始'):r.compare(s)
 def test_duplicate_date_and_invalid_nav_rejected(self):
  for mode in ['duplicate','nan']:
   s=self.spec()
   if mode=='duplicate':s['rows'][0]['history'].append(dict(s['rows'][0]['history'][0]))
   else:s['rows'][0]['history'][0]['nav']=float('nan')
   with self.assertRaises(ValueError):r.compare(s)
 def test_overflow_rejected(self):
  with self.assertRaisesRegex(ValueError,'溢出'):r.series([{'date':'2025-01-01','nav':1e-300},{'date':'2025-01-02','nav':1e300}],'2025-01-02','nav-with-distributions')

if __name__=='__main__':unittest.main()
