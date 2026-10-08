import unittest
from valuation_percentile import calculate
class Tests(unittest.TestCase):
 def test_invalid_history_and_empty_publication_rejected(self):
  for history in [None,{},[None]]:
   s=self.spec();s['history']=history
   with self.assertRaisesRegex(ValueError,'对象列表'):calculate(s)
  s=self.spec();s['history'][0]['publishedAt']=''
  with self.assertRaises(ValueError):calculate(s)
 def test_observation_before_window_rejected(self):
  s=self.spec();s['observedAt']='2026-09-30'
  with self.assertRaisesRegex(ValueError,'不在研究区间'):calculate(s)
 def spec(self):return dict(code='588000',market='SSE',subject='tracking-index',metric='PE-TTM',method='aggregate',frequency='daily',asOf='2026-10-03',start='2026-10-01',observedAt='2026-10-03',sourceUrl='https://example.org/data',minimumSamples=2,history=[dict(date='2026-10-01',value=10),dict(date='2026-10-02',value=20),dict(date='2026-10-03',value=20)])
 def test_tie(self):self.assertAlmostEqual(calculate(self.spec())['valuationPercentile']['value'],100*2/3)
 def test_missing_current(self):
  s=self.spec();s['history'][-1]['value']=None;self.assertIsNone(calculate(s)['valuationPercentile']['value'])
 def test_negative(self):
  s=self.spec();s['history'][0]['value']=-10;self.assertEqual(calculate(s)['excluded'][0]['reason'],'非正估值，不能解释为低估')
 def test_future_publication(self):
  s=self.spec();s['history'][-1]['publishedAt']='2026-10-04';self.assertIsNone(calculate(s)['valuationPercentile']['value'])
 def test_duplicate(self):
  s=self.spec();s['history'][1]['date']='2026-10-01'
  with self.assertRaises(ValueError):calculate(s)
if __name__=='__main__':unittest.main()
