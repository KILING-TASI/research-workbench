import unittest
from generate_cash_plan import generate
class Generation(unittest.TestCase):
 def source(self):return {'fetchedAt':'2026-01-20T00:00:00+08:00','records':[{'code':'a','applyDate':'2026-01-06','refundDate':'2026-01-08','listingDate':'2026-01-09','price':10,'ratePct':10,'gainPct':20,'maxShares':1000,'minShares':100},{'code':'b','applyDate':'2026-01-08','refundDate':'2026-01-12','listingDate':'2026-01-13','price':10,'ratePct':10,'gainPct':20,'maxShares':1000,'minShares':100}]}
 def test_same_day_refund_not_reused(self):
  r=generate(self.source(),{}, {'year':2026,'closedRanges':[]},10000,'2026-01-01','2026-01-20')
  self.assertEqual(len(r['plan']['issues']),1);self.assertIn('Insufficient',r['excluded'][0]['reason'])
  self.assertEqual(r['ledger']['endCash'],'10200.00');self.assertTrue(r['ledger']['feasible'])
 def test_missing_and_future_data_are_not_invented(self):
  s=self.source();s['records'][0]['ratePct']=None
  r=generate(s,{}, {'year':2026,'closedRanges':[]},10000,'2026-01-01','2026-01-20')
  self.assertIn('missing',r['excluded'][0]['reason']);self.assertFalse(r['plan']['accountAvailabilityVerified'])
  with self.assertRaises(ValueError):generate(s,{}, {'year':2026,'closedRanges':[]},10000,'2026-01-01','2026-01-21')
if __name__=='__main__':unittest.main()
