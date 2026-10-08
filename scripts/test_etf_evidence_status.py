import unittest,datetime as dt,copy
from etf_evaluation import evaluate_layers
class Tests(unittest.TestCase):
 def spec(self):
  dates=[(dt.date(2025,1,1)+dt.timedelta(days=i)).isoformat() for i in range(121)]
  e=dict(observedAt="2026-10-02",availableAt="2026-10-02",sourceUrl="https://example.com/test",locator="fixture",verification="third-party-observed")
  nav=dict(e,value=[dict(date=t,value=100+i) for i,t in enumerate(dates)],basis="nav-total-return",currency="CNY")
  p=dict(code="a",navTotalReturn=nav,valuation=dict(e,value=dict(PE=20)))
  return dict(asOf="2026-10-05",positionCurrency="CNY",positionValue=100,holdingYears=1,current=p,candidate=dict(p,code="b"))
 def metrics(self,d):return {m["id"]:m for l in evaluate_layers(d)["products"][0]["layers"] for m in l["metrics"]}
 def test_third_party_not_reviewed(self):self.assertEqual(self.metrics(self.spec())["valuation"]["status"],"第三方观测，未核验官方原文")
 def test_nav_risk_provisional(self):self.assertEqual(self.metrics(self.spec())["navRisk"]["status"],"研究测算，待分红核验")
 def test_monthly_not_annualized_as_daily(self):
  d=self.spec();d["current"]["navTotalReturn"]["frequency"]="monthly";self.assertIsNone(self.metrics(d)["navRisk"]["value"])

class EvidenceShapeTests(unittest.TestCase):
 spec=Tests.spec
 metrics=Tests.metrics
 def test_series_cannot_extend_after_observed_date(self):
  s=self.spec();s['current']['navTotalReturn']['observedAt']='2025-01-31'
  self.assertIsNone(self.metrics(s)['navRisk']['value'])
 def test_invalid_source_url_becomes_gap(self):
  s=self.spec();s['current']['valuation']['sourceUrl']=123
  self.assertIsNone(self.metrics(s)['valuation']['value'])
 def test_credentials_or_compact_source_date_becomes_gap(self):
  for key,value in [('sourceUrl','https://user:secret@example.com/a'),('observedAt','20261002')]:
   s=self.spec();s['current']['valuation'][key]=value;self.assertIsNone(self.metrics(s)['valuation']['value'])
 def test_liquidity_after_observed_day_is_not_available(self):
  s=self.spec();e=s['current']['valuation'];dates=[(dt.date(2026,9,1)+dt.timedelta(days=i)).isoformat() for i in range(20)]
  s['current']['liquidity']=dict(e,observedAt='2026-09-10',value=dict(dates=dates,count=20,averageAmount=1000))
  self.assertIsNone(self.metrics(s)['liquidity']['value'])
 def test_cash_per_share_used_when_cash_total_is_null(self):
  s=self.spec();e=s['current']['valuation'];s['current']['constituents']=dict(e,value=[dict(code='600000',weight=1)])
  s['current']['financials']=dict(e,unit='CNY',value=[dict(code='600000',period='2026-06-30',publishedAt='2026-08-01',netProfit=1,operatingCash=None,operatingCashPerShare=.5)])
  self.assertEqual(self.metrics(s)['earningsQuality']['value']['positiveOperatingCashCoveredWeightPct'],100)
 def test_invalid_quote_and_assets_no_attribute_crash(self):
  s=self.spec();e=s['current']['valuation'];s['current']['quote']=dict(e,value=[]);s['current']['assets']=dict(e,value=[])
  m=self.metrics(s);self.assertIsNone(m['spread']['value']);self.assertIsNone(m['assets']['value'])
 def test_invalid_portfolio_and_position_rejected(self):
  for k,v in [('portfolio',[None]),('positionValue',float('nan')),('holdingYears',True)]:
   s=self.spec();s[k]=v
   with self.assertRaises(ValueError):evaluate_layers(s)

class OverflowTests(unittest.TestCase):
 spec=Tests.spec
 def test_extreme_nav_cannot_deliver_nonfinite_risk(self):
  s=self.spec();s['current']['navTotalReturn']['value'][0]['value']=1e-308;s['current']['navTotalReturn']['value'][1]['value']=1e308
  with self.assertRaisesRegex(ValueError,'溢出'):evaluate_layers(s)

if __name__=="__main__":unittest.main()
