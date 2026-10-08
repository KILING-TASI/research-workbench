import unittest
from company_research import run
from decimal import Decimal
class Company(unittest.TestCase):
    def obs(self,value,unit='CNY'):return {'value':str(value),'unit':unit}
    def spec(self):
        return {'code':'920022','asOf':'2025-09-09','price':self.obs(10),'postIssueShares':self.obs(10000000,'shares'),'shareBasis':'before-greenshoe','valuationPeriod':'2024-12-31','financials':[{'period':'2024-12-31','periodBasis':'FY','scope':'consolidated','revenue':self.obs(100000000),'netProfit':self.obs(10000000),'adjustedProfit':self.obs(8000000),'cfo':self.obs(-1000000)}]}
    def test_pe_cash_and_nonrecurring(self):
        r=run(self.spec());self.assertEqual(Decimal(r['valuation']['adjustedFYPe']),Decimal('12.5'));self.assertEqual(Decimal(r['financials'][0]['nonRecurringProfitSharePct']),20);self.assertTrue(r['financials'][0]['signals'])
    def test_negative_profit_no_pe(self):
        s=self.spec();s['financials'][0]['adjustedProfit']=self.obs(-1);self.assertIsNone(run(s)['valuation']['adjustedFYPe'])
    def test_missing_not_zero(self):
        s=self.spec();s['financials'][0].pop('cfo');self.assertIsNone(run(s)['financials'][0]['cfoToNetProfitPct'])
    def test_peer_basis_and_date(self):
        s=self.spec();s['peers']=[{'code':'x','pe':self.obs(20,'multiple'),'period':'2024-12-31','basis':'TTM','currency':'CNY','valuationDate':'2025-09-09','comparabilityReason':'test'}]
        r=run(s);self.assertEqual(len(r['valuation']['excludedPeers']),1);self.assertIsNone(r['valuation']['peerMedianPe'])
    def test_peer_distribution(self):
        s=self.spec();s['peers']=[{'code':str(i),'pe':self.obs(v,'multiple'),'period':'2024-12-31','basis':'adjusted-FY-consolidated','currency':'CNY','valuationDate':'2025-09-09','comparabilityReason':'synthetic test'} for i,v in enumerate([10,20,30])]
        self.assertEqual(Decimal(run(s)['valuation']['peerMedianPe']),20)
    def test_mixed_scope_blocked(self):
        s=self.spec();s['financials'][0]['scope']='parent'
        with self.assertRaises(ValueError):run(s)
    def test_half_year_cannot_be_annual_profit_by_label(self):
        for period in ['2024-06-30','2024-09-30']:
            with self.subTest(period=period):
                s=self.spec();s['financials'][0]['period']=period;s['valuationPeriod']=period
                with self.assertRaisesRegex(ValueError,'年度口径'):run(s)
    def test_profit_stress_not_price_forecast(self):
        s=self.spec();s['profitStress']=[{'label':'synthetic','changePct':-20}];r=run(s);self.assertEqual(Decimal(r['profitSensitivity'][0]['fixedIssuePricePe']),Decimal('15.625'))
if __name__=='__main__':unittest.main()
