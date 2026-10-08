import unittest
from cash_repo_ledger import run
class Ledger(unittest.TestCase):
 def base(self):return {'capital':'100000','start':'2026-01-01','end':'2026-01-10','repos':[{'id':'r','tradeDate':'2026-01-02','firstSettlementDate':'2026-01-03','maturitySettlementDate':'2026-01-06','availableDate':'2026-01-06','principal':'100000','annualRatePct':'3.65','commission':'1','dateBasis':'test scenario'}]}
 def test_actual_days_and_fee(self):
  r=run(self.base());self.assertEqual(r['repos'][0]['grossInterest'],'30.00');self.assertEqual(r['endCash'],'100029.00');self.assertEqual(r['additionalFundsRequired'],'1')
 def test_same_day_not_reused(self):
  s=self.base();s['repos'][0]['principal']='50000';s['repos'][0]['commission']='0';s['issues']=[{'id':'i','applyDate':'2026-01-06','refundAvailableDate':'2026-01-07','saleAvailableDate':'2026-01-08','subscriptionFunds':'100000','allocatedPrincipal':'100','saleNetProceeds':'150'}]
  r=run(s);self.assertFalse(r['feasible']);self.assertEqual(r['additionalFundsRequired'],'50000')
 def test_unknown_early_release_rejected(self):
  s=self.base();s['repos'][0]['availableDate']='2026-01-04'
  with self.assertRaises(ValueError):run(s)
 def test_end_before_release(self):
  s=self.base();s['end']='2026-01-04';r=run(s);self.assertEqual(len(r['unsettledEvents']),1)
 def test_missing_commission_not_assumed_zero(self):
  for empty in [False,True]:
   s=self.base()
   if empty:s['repos'][0]['commission']=None
   else:s['repos'][0].pop('commission')
   with self.subTest(empty=empty),self.assertRaisesRegex(ValueError,'commission'):run(s)
class Calendar(unittest.TestCase):
 def test_holiday_and_weekend(self):
  from trading_calendar import next_open,is_open
  c={'year':2026,'closedRanges':[['2026-10-01','2026-10-07']]}
  self.assertEqual(next_open('2026-09-30',c),'2026-10-08')
  self.assertEqual(next_open('2026-10-09',c),'2026-10-12')
  self.assertFalse(is_open('2026-10-10',c))
  with self.assertRaises(ValueError):next_open('2026-12-31',c)
if __name__=='__main__':unittest.main()
