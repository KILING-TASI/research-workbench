import json,unittest,tempfile
from pathlib import Path
from research_workflow import context,run_etf_closing_premium_review
from etf_closing_premium import calculate
class Tests(unittest.TestCase):
 def test_overflow_and_invalid_rows_not_exported_as_premium(self):
  with self.assertRaisesRegex(ValueError,'溢出'):calculate('512010',[dict(date='2026-01-02',close=1e308)],self.raw(rows=[dict(x=1767312000000,y=1e-308)]),'2026-01-01','2026-01-03')
  for prices in [None,[None]]:
   with self.assertRaises(ValueError):calculate('512010',prices,self.raw(),'2026-01-01','2026-01-03')
 def raw(self,code='512010',rows=None):return 'var fS_code='+json.dumps(code)+';var fS_name="ETF";var Data_netWorthTrend='+json.dumps(rows or [{'x':1767312000000,'y':2}])+';'
 def test_same_date_and_missing(self):
  r=calculate('512010',[{'date':'2026-01-02','close':2.2},{'date':'2026-01-03','close':2.3}],self.raw(),'2026-01-01','2026-01-03')
  self.assertAlmostEqual(r['history'][0]['closingPremiumPct'],10);self.assertEqual(r['missingNavDates'],['2026-01-03']);self.assertEqual(r['eventCoverage'],'provider-events-unverified')
 def test_identity_and_duplicate(self):
  with self.assertRaises(ValueError):calculate('512010',[],self.raw('512170'),'2026-01-01','2026-01-03')
  with self.assertRaises(ValueError):calculate('512010',[],self.raw(rows=[{'x':1767312000000,'y':2}]*2),'2026-01-01','2026-01-03')
 def test_invalid_close_and_no_common(self):
  with self.assertRaises(ValueError):calculate('512010',[{'date':'2026-01-02','close':False}],self.raw(),'2026-01-01','2026-01-03')
  r=calculate('512010',[{'date':'2026-01-03','close':2}],self.raw(),'2026-01-01','2026-01-03');self.assertEqual(r['status'],'missing')

 def test_unified_context_conflicts_before_output(self):
  with tempfile.TemporaryDirectory() as directory:
   p=Path(directory);spec={'end':'2026-10-05'};(p/'input.json').write_text(json.dumps(spec),'utf8')
   for basis,currency,asof in [('reinvest','CNY','2026-10-05'),('price_only','USD','2026-10-05'),('price_only','CNY','2026-10-04')]:
    ctx=context(dict(sessionId='test',baseCurrency=currency,frequency='trading_day',dividendTreatment=basis,asOf=asof,benchmark=None,riskFreeRate=0,annualization=252,missingData='common_dates',timezone='UTC'));(p/'context.json').write_text(json.dumps(ctx),'utf8')
    with self.assertRaises(ValueError):run_etf_closing_premium_review(dict(contextPath=str(p/'context.json'),inputPath=str(p/'input.json'),outDir=str(p/'out')))
   self.assertFalse((p/'out').exists())
