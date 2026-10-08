import unittest
from generate_repo_scenario import schedule
class Scheduling(unittest.TestCase):
 def base(self):return {'capital':'100000','start':'2026-10-08','end':'2026-10-12','issues':[],'repos':[]}
 def test_weekend_accrual_and_fees(self):
  r=schedule(self.base(),{'year':2026,'closedRanges':[]},'3.65',100,1)
  self.assertEqual(len(r['plan']['repos']),1);self.assertEqual(r['ledger']['repos'][0]['actualAccrualDays'],3)
  self.assertEqual(r['incrementalEndCash'],'28.70');self.assertTrue(r['ledger']['feasible'])
  self.assertFalse(r['plan']['repoScenario']['tradeTermsVerified'])
 def test_upcoming_subscription_reserved(self):
  p=self.base();p['issues']=[{'id':'ipo','applyDate':'2026-10-12','refundAvailableDate':'2026-10-13','saleAvailableDate':'2026-10-14','subscriptionFunds':'100000','allocatedPrincipal':'1000','saleNetProceeds':'1100'}]
  r=schedule(p,{'year':2026,'closedRanges':[]},'3.65',100)
  self.assertEqual(len(r['plan']['repos']),0);self.assertTrue(r['ledger']['feasible'])
 def test_omitted_repo_orders_matches_explicit_empty_without_mutation(self):
  p=self.base();del p['repos']
  r=schedule(p,{'year':2026,'closedRanges':[]},'3.65',100,1)
  expected=schedule(self.base(),{'year':2026,'closedRanges':[]},'3.65',100,1)
  self.assertEqual(r,expected);self.assertNotIn('repos',p)
 def test_false_empty_repo_types_rejected(self):
  for value in [None,False,0,'',{}]:
   with self.subTest(value=value):
    with self.assertRaisesRegex(ValueError,'list'):schedule({**self.base(),'repos':value},{'year':2026,'closedRanges':[]},'3.65')
if __name__=='__main__':unittest.main()
