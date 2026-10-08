import unittest
from decimal import Decimal
from allocation_cash import calculate,collision
class Cash(unittest.TestCase):
    def spec(self,**changes):
        return {'code':'920022','price':'10','budget':'1000000','maxShares':200000,'rateBasis':'synthetic assumptions','ratesPct':{'P75':'0.2','P50':'0.1','P25':'0.05'},'gainPct':{'P75':'10','P50':'10','P25':'-20'},'applyDate':'2026-10-01','refundDate':'2026-10-03','saleSettlementDate':'2026-10-11','opportunityRatePct':'3','fees':{'commissionPct':'0.01','minimumCommission':'5'},**changes}
    def test_exact_allocation_cash_days(self):
        r=calculate(self.spec());s=r['scenarios']['P50']
        self.assertEqual(s['wholeLotShares'],100);self.assertEqual(Decimal(s['capitalDays']),Decimal(2008000));self.assertEqual(Decimal(s['netProfit']),Decimal(95));self.assertEqual(s['hundredShareThreshold'],100000)
    def test_missing_costs_are_explicit_assumptions(self):
        r=calculate(self.spec());missing=r['costInputCoverage']['assumedZeroFields']
        self.assertIn('fees.taxPct',missing);self.assertIn('fees.slippagePct',missing)
        self.assertNotIn('fees.commissionPct',missing)
        self.assertIn('不表示券商实际免收费用',r['costInputCoverage']['scope'])
    def test_zero_and_small_budget(self):
        r=calculate(self.spec(budget='999'));self.assertEqual(r['subscriptionShares'],0);self.assertEqual(Decimal(r['scenarios']['P50']['saleCosts']),0)
        r=calculate(self.spec(ratesPct={'P75':0,'P50':0,'P25':0}));self.assertIsNone(r['scenarios']['P50']['hundredShareThreshold'])
    def test_unused_cash_gap(self):
        s=calculate(self.spec(budget='999995'))['scenarios']['P50'];self.assertEqual(Decimal(s['thresholdAdditionalFunds']),5);self.assertEqual(Decimal(s['thresholdAdditionalSubscriptionFunds']),1000)
    def test_limit_unreachable(self):
        s=calculate(self.spec(maxShares=1000))['scenarios']['P50'];self.assertFalse(s['thresholdReachable']);self.assertIsNone(s['nextWholeLotAdditionalFunds'])
    def test_next_lot_cannot_cross_subscription_cap(self):
        s=calculate(self.spec(maxShares=150000))['scenarios']['P50']
        self.assertEqual(s['wholeLotShares'],100);self.assertEqual(s['nextWholeLotSubscriptionShares'],200000)
        self.assertFalse(s['nextWholeLotReachable']);self.assertEqual(s['maxProportionalWholeLotShares'],100)
        self.assertIn('增加预算也不可达',s['nextWholeLotExplanation']);self.assertIn('未知零股',s['nextWholeLotExplanation'])
        self.assertIsNone(s['nextWholeLotAdditionalFunds'])
        capped=calculate(self.spec(maxShares=150000,budget='9000000'))['scenarios']['P50']
        self.assertEqual(capped['wholeLotShares'],100);self.assertFalse(capped['nextWholeLotReachable'])
    def test_zero_rate_has_no_next_threshold(self):
        s=calculate(self.spec(ratesPct={'P75':0,'P50':0,'P25':0}))['scenarios']['P50']
        self.assertIsNone(s['nextWholeLotSubscriptionShares']);self.assertIsNone(s['nextWholeLotThresholdFunds'])
        self.assertFalse(s['nextWholeLotReachable']);self.assertEqual(s['maxProportionalWholeLotShares'],0)
        self.assertIn('配售率为零',s['nextWholeLotExplanation'])
    def test_loss_settlement(self):
        s=calculate(self.spec())['scenarios']['P25'];self.assertEqual(s['wholeLotShares'],0)
        s=calculate(self.spec(gainPct={'P75':-100,'P50':-100,'P25':-100}))['scenarios']['P50'];self.assertEqual(Decimal(s['netSettlementCash']),-5)
    def test_collision(self):
        a=self.spec();b=self.spec(code='920111')
        r=collision({'totalFunds':'1000000','issues':[a,b]});self.assertFalse(r['scenarios']['P50']['feasible']);self.assertEqual(Decimal(r['scenarios']['P50']['additionalStartingFunds']),1000000)
    def test_same_day_release(self):
        a=self.spec();b=self.spec(code='920111',applyDate='2026-10-11',refundDate='2026-10-13',saleSettlementDate='2026-10-20')
        self.assertFalse(collision({'totalFunds':'1000000','issues':[a,b]})['scenarios']['P50']['feasible'])
        self.assertTrue(collision({'totalFunds':'1000000','issues':[a,b],'sameDayReleasedFundsUsable':True})['scenarios']['P50']['feasible'])
    def test_invalid_scenario_and_dates(self):
        with self.assertRaises(ValueError):calculate(self.spec(ratesPct={'P75':1,'P50':2,'P25':1}))
        with self.assertRaises(ValueError):calculate(self.spec(refundDate='2026-09-30'))
        with self.assertRaises(ValueError):calculate(self.spec(maxShares=101))
if __name__=='__main__':unittest.main()
