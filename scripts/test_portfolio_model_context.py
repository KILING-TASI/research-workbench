import unittest,tempfile,json
from pathlib import Path
from research_workflow import context,run_template

class Tests(unittest.TestCase):
 def test_constraint_failure_is_findable_without_success_result(self):
  from portfolio_allocation_report import explain_failure
  from research_results import publish as find
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);explain_failure(ValueError('类别与资产约束无可行稳定解'),root/'failed')
   rows=find(root,root/'found.md')
   self.assertEqual(rows[0]['status'],'blocked');self.assertFalse((root/'failed/result.json').exists())
   self.assertIn('不会自动放宽',(root/'failed/下一步.md').read_text('utf-8'))
 def test_constant_correlation_shrink_preserves_variances_and_psd(self):
  import numpy as np
  from portfolio_models import constant_correlation_shrink
  sample=np.array([[1,.1,.2],[.1,4,.3],[.2,.3,9]])
  value,meta=constant_correlation_shrink(sample,1)
  self.assertTrue(np.allclose(np.diag(value),np.diag(sample)));self.assertGreater(np.linalg.eigvalsh(value).min(),0)
  corr=value/np.outer(np.sqrt(np.diag(value)),np.sqrt(np.diag(value)))
  self.assertAlmostEqual(corr[0,1],corr[1,2]);self.assertEqual(meta['intensityBasis'],'caller-declared-not-automatic-Ledoit-Wolf')
  self.assertTrue(np.allclose(constant_correlation_shrink(sample,0)[0],sample))
  with self.assertRaises(ValueError):constant_correlation_shrink(sample,1.1)
 def test_risk_parity_diagonal_and_constraint_rejection(self):
  from portfolio_models import risk_parity
  result=risk_parity([[.01,0],[0,.04]])
  self.assertEqual(result['status'],'calculated-candidate');self.assertAlmostEqual(result['weights'][0],2/3,places=7)
  self.assertTrue(all(abs(x-.5)<1e-8 for x in result['riskContributionShares']))
  self.assertEqual(risk_parity([[.01,0],[0,.04]],.6)['status'],'constraints-not-met')
  self.assertEqual(risk_parity([[1,1],[1,1]])['status'],'not-calculated-non-positive-definite')
 def test_aligned_total_return_model_keeps_constraints(self):
  from portfolio_models import optimize,simulate
  dates=[str(2023+i//12)+'-'+str(i%12+1).zfill(2)+'-01' for i in range(25)]
  assets=[dict(code=code,currency='CNY',basis='total-return',sourceUrl='https://example.org/history',history=[dict(date=day,value=1+(i*.01 if code=='a' else i*.005)+(i%2)*.002) for i,day in enumerate(dates)]) for code in ['a','b']]
  data=dict(asOf='2025-01-01',currency='CNY',frequency='monthly',assets=assets,maxWeight=.7,frontierPoints=3,weights=[.5,.5],paths=100,steps=12)
  result=optimize(data)
  for candidate in (result['minimumVariance'],result['equalWeightBaseline']):
   self.assertAlmostEqual(sum(candidate['riskContributionShares']),1)
   self.assertAlmostEqual(sum(candidate['volatilityContributionPp']),candidate['annualizedVolatilityPct'])
  auto=optimize(dict(data,covarianceMethod='ledoit-wolf-constant-correlation'))
  self.assertEqual(auto['covarianceEstimator'],'ledoit-wolf-constant-correlation')
  with self.assertRaises(ValueError):optimize(dict(data,covarianceMethod='ledoit-wolf-constant-correlation',shrinkageIntensity=.5))
  self.assertEqual(result['equalWeightBaseline']['weights'],[.5,.5])
  self.assertGreaterEqual(result['baselineComparison']['sampleVarianceReduction'],-1e-12)
  self.assertEqual(result['covarianceEstimator'],'sample-unshrunk')
  self.assertIn('in-sample-only',result['baselineComparison']['status'])
  with self.assertRaises(ValueError):optimize(dict(data,maxWeight=.4))
  bounded=optimize(dict(data,minWeight=.4))
  self.assertTrue(all(.39999999<=weight<=.70000001 for weight in bounded['minimumVariance']['weights']))
  class_data=dict(data,classConstraints={'equity':{'min':0,'max':.4}})
  class_data['assets']=[dict(asset,assetClass='equity' if i==0 else 'bond') for i,asset in enumerate(data['assets'])]
  class_result=optimize(class_data)
  self.assertLessEqual(class_result['minimumVariance']['weights'][0],.40000001)
  self.assertEqual(class_result['equalWeightBaseline']['status'],'constraints-not-met');self.assertTrue(all(point['weights'][0]<=.40000001 for point in class_result['frontier']))
  for key,value in [('minWeight',.6),('classConstraints',{'equity':{'max':.4}}),('cashBuffer',.1),('allowShort',False)]:
   with self.subTest(key=key),self.assertRaises(ValueError):optimize(dict(data,**{key:value}))
  from portfolio_allocation_report import publish
  from research_results import publish as find
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);data['scopeNotes']=['净值代理不是实际成交价格'];data['sensitivityWindows']=[24,50];data['exampleType']='teaching-only';publish(data,root/'allocation')
   body=(root/'allocation/组合配置候选比较.md').read_text('utf-8')
   self.assertIn('等权|最小方差|风险平价',body);self.assertIn('不是完整配置决策引擎',body)
   self.assertIn('净值代理不是实际成交价格',body)
   self.assertIn('不是独立风险来源数',body);self.assertIn('ERC估计风险贡献占比',body)
   self.assertIn('现有仅24个，不计算、不补齐',body);self.assertIn('不是样本外检验',body)
   self.assertEqual(len(find(root,root/'index.md','组合配置')),1)
   from start import execute
   unified=execute('allocation',root/'unified',continue_from=root/'allocation')
   self.assertEqual(unified['status'],'partial');self.assertTrue((root/'unified/打开这里.html').is_file())
   self.assertEqual(unified['exampleType'],'teaching-only');self.assertIn('虚构资产',(root/'unified/组合配置候选比较.md').read_text('utf-8'))
   import builtins
   from unittest.mock import patch
   normal_import=builtins.__import__
   def absent(name,*args,**kwargs):
    if name=='portfolio_allocation_report':raise ImportError('配置组件缺失测试')
    return normal_import(name,*args,**kwargs)
   with patch('builtins.__import__',side_effect=absent):failure=execute('allocation',root/'missing-component',input_path=root/'allocation/input.json')
   self.assertEqual(failure['failureKind'],'missing-dependency');self.assertTrue((root/'missing-component/research-request.json').is_file())
   self.assertNotIn('组件缺失测试',failure['message']);self.assertIn('组件缺失测试',(root/'missing-component/环境诊断.txt').read_text('utf-8'))
   recovered=execute('allocation',root/'component-recovered',continue_from=root/'missing-component')
   self.assertEqual(recovered['status'],'partial')
   from portfolio_allocation_report import replay
   previous=(root/'allocation/input.json').read_bytes()
   changed=replay(root/'allocation',root/'changed',.6)
   self.assertTrue(all(w<=.60000001 for w in changed['minimumVariance']['weights']))
   self.assertEqual((root/'allocation/input.json').read_bytes(),previous)
   self.assertIn('权重变化',(root/'changed/复用说明.md').read_text('utf-8'));self.assertTrue((root/'changed/复用说明.html').is_file())
   with self.assertRaises(ValueError):replay(root/'allocation',root/'impossible',.4)
   self.assertFalse((root/'impossible').exists())
   from portfolio_allocation_report import explain_failure
   impossible=dict(data,maxWeight=.4);explain_failure(ValueError('上限不可行'),root/'failed-cap',impossible)
   recovered=replay(root/'failed-cap',root/'recovered',.6)
   self.assertTrue(all(weight<=.60000001 for weight in recovered['minimumVariance']['weights']))
   self.assertIn('没有旧可行方案',(root/'recovered/复用说明.md').read_text('utf-8'))
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
