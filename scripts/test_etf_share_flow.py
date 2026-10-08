import unittest,copy
from etf_share_flow import calculate
class Tests(unittest.TestCase):
 def test_overflow_and_non_object_inputs_rejected(self):
  for value in [None,[],{},dict(code='588000',startShares=None)]:
   with self.assertRaises(ValueError):calculate(value)
  s=self.sample();s['endShares']['value']=1e308;s['endNav']['value']=1e308
  with self.assertRaises(ValueError):calculate(s)
 def test_published_before_observation_is_not_historical_evidence(self):
  s=self.sample();s['endShares']['publishedAt']='2026-09-29'
  with self.assertRaises(ValueError):calculate(s)
 def sample(self):
  e=dict(code='588000',sourceUrl='https://example.org/shares',basis='exchange-end-shares',unit='shares')
  return dict(code='588000',asOf='2026-10-03',startShares=dict(e,value=100,observedAt='2026-09-29'),endShares=dict(e,value=120,observedAt='2026-09-30'),endNav=dict(code='588000',sourceUrl='https://example.org/nav',basis='unit-nav',unit='CNY/share',value=2,observedAt='2026-09-30'),shareEventStatus='assumed-no-share-events')
 def test_proxy(self):self.assertEqual(calculate(self.sample())['netFlowCNY']['value'],40)
 def test_unknown_not_zero(self):
  s=self.sample();s['shareEventStatus']='unknown';self.assertIsNone(calculate(s)['netFlowCNY']['value'])
 def test_units(self):
  s=self.sample();s['startShares']['unit']='万份'
  with self.assertRaises(ValueError):calculate(s)
 def test_nav_date(self):
  s=self.sample();s['endNav']['observedAt']='2026-09-29'
  with self.assertRaises(ValueError):calculate(s)
 def test_future_event_evidence_rejected(self):
  s=self.sample();s['shareEventStatus']='verified-no-share-events';s['shareEventEvidence']=dict(sourceUrl='https://example.org/events',window='2026-09-29/2026-09-30',observedAt='2027-01-01',quote='无事件')
  with self.assertRaises(ValueError):calculate(s)
 def test_negative_flow_valid(self):
  s=self.sample();s['endShares']['value']=90;self.assertEqual(calculate(s)['netFlowCNY']['value'],-20)
if __name__=='__main__':unittest.main()
