import unittest,tempfile,json
from pathlib import Path
from research_workflow import context,run_template

class Tests(unittest.TestCase):
 def test_aligned_total_return_model_keeps_constraints(self):
  from portfolio_models import optimize,simulate
  dates=[str(2023+i//12)+'-'+str(i%12+1).zfill(2)+'-01' for i in range(25)]
  assets=[dict(code=code,currency='CNY',basis='total-return',sourceUrl='https://example.org/history',history=[dict(date=day,value=1+(i*.01 if code=='a' else i*.005)+(i%2)*.002) for i,day in enumerate(dates)]) for code in ['a','b']]
  data=dict(asOf='2025-01-01',currency='CNY',frequency='monthly',assets=assets,maxWeight=.7,frontierPoints=3,weights=[.5,.5],paths=100,steps=12)
  result=optimize(data)
  for point in [result['minimumVariance'],*result['frontier']]:
   self.assertAlmostEqual(sum(point['weights']),1);self.assertTrue(all(-1e-8<=w<=.70000001 for w in point['weights']))
  simulation=simulate(data);self.assertTrue(all(0<=v<=100 for v in simulation['simulatedMaxDrawdownPercentilesPct'].values()))
 def test_model_structure_errors_are_explicit(self):
  from portfolio_models import prepare
  for data in [None,[],{},dict(asOf='2026-10-05',frequency='monthly',assets=None),dict(asOf='2026-10-05',frequency='monthly',assets=[None])]:
   with self.subTest(data=data),self.assertRaises(ValueError):prepare(data)
 def prepare(self,p,**changes):
  params=dict(sessionId='model',baseCurrency='CNY',frequency='monthly',dividendTreatment='reinvest',asOf='2026-10-05',benchmark=None,riskFreeRate=.01,annualization=12,missingData='common_dates',timezone='Asia/Shanghai');params.update(changes)
  (p/'context.json').write_text(json.dumps(context(params)))
  (p/'input.json').write_text(json.dumps(dict(asOf='2026-10-05',currency='CNY',frequency='monthly',assets=[])))
  return dict(template='portfolio-model-review',contextPath=str(p/'context.json'),inputPath=str(p/'input.json'),mode='simulate')
 def test_monthly_252_rejected_before_model(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)
   with self.assertRaisesRegex(ValueError,'年化因子'):run_template(self.prepare(p,annualization=252),p)
 def test_price_series_context_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)
   with self.assertRaisesRegex(ValueError,'总收益再投'):run_template(self.prepare(p,dividendTreatment='price_only'),p)
 def test_daily_context_for_monthly_input_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)
   with self.assertRaisesRegex(ValueError,'频率'):run_template(self.prepare(p,frequency='trading_day'),p)
 def test_cutoff_change_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)
   with self.assertRaisesRegex(ValueError,'截止日'):run_template(self.prepare(p,asOf='2026-10-04'),p)
if __name__=='__main__':unittest.main()
