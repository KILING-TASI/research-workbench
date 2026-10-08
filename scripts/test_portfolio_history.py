import unittest,datetime as dt
from portfolio_stress import analyze
from portfolio_history_report import markdown
from accounting_basis import validate
class Tests(unittest.TestCase):
 def test_display_names_do_not_split_table_columns(self):
  d=self.doc();d['holdings'][0]['name']='A|B\n份额';body=markdown(analyze(d),d)
  self.assertIn('A／B 份额',body);self.assertNotIn('A|B',body)
  d['holdings'][0]['name']=[]
  with self.assertRaises(ValueError):markdown(analyze(d),d)
 def test_scaled_correlation_does_not_turn_overflow_into_zero(self):
  from portfolio_stress import corr
  self.assertAlmostEqual(corr([1e100,2e100,3e100],[-1e100,-2e100,-3e100]),-1)
  self.assertIsNone(corr([0,0,0],[1,2,3]))
  with self.assertRaises(ValueError):corr([1,2,3],[1,2])
 def test_scenario_and_window_shapes(self):
  for key,value in [('windows',[None]),('scenarios',{}),('scenarios',[dict(name='')]),('scenarios',[dict(name='test',returnShocksPct=[])]),('scenarios',[dict(name='test',assumptions='guess')])]:
   d=self.doc();d[key]=value
   with self.subTest(key=key,value=value),self.assertRaises(ValueError):analyze(d)
 def test_invalid_shapes_dates_and_overflow_fail_explicitly(self):
  for value in [None,[],True]:
   with self.subTest(value=value),self.assertRaises(ValueError):analyze(value)
  for key,value in [('baseCurrency',''),('asOf','20261006'),('holdings',[None])]:
   d=self.doc();d[key]=value
   with self.subTest(key=key),self.assertRaises(ValueError):analyze(d)
  d=self.doc();d['scenarios']=[dict(name='overflow',returnShocksPct={'a':1e308})];d['holdings'][0]['marketValue']=1e308
  with self.assertRaises(ValueError):analyze(d)
 def test_portfolio_path_modes_and_drawdown_not_average(self):
  d=self.doc(4);d['minimumObservations']=3;d.pop('rollingWindowObservations')
  for r,vs in zip(d['holdings'],[[100,200,100,100,100],[100,100,200,200,200]]):
   for point,value in zip(r['history'],vs):point['value']=value
  d['historicalPortfolioMode']='buy-and-hold';p=analyze(d)['historical']['portfolioPath']
  self.assertAlmostEqual(p['totalReturnPct'],50);self.assertEqual(p['maximumDrawdownPct'],0)
  d['historicalPortfolioMode']='fixed-observation-weights';p=analyze(d)['historical']['portfolioPath']
  self.assertAlmostEqual(p['totalReturnPct'],87.5)
 def test_portfolio_path_refuses_gaps(self):
  d=self.doc();d['historicalPortfolioMode']='buy-and-hold';d['holdings'][1]['history'].pop(10)
  p=analyze(d)['historical']['portfolioPath'];self.assertEqual(p['status'],'disconnected-observations');self.assertNotIn('maximumDrawdownPct',p)
 def test_portfolio_invalid_mode(self):
  d=self.doc();d['historicalPortfolioMode']='guess'
  with self.assertRaises(ValueError):analyze(d)
 def doc(self,n=80):
  rs=[.01,-.02,.03,-.01]*((n+3)//4);rows=[]
  for k,sign in [('a',1),('b',-1)]:
   value=100;history=[dict(date='2025-01-01',value=value)]
   for i,r in enumerate(rs[:n]):
    value*=1+r*sign;history.append(dict(date=(dt.date(2025,1,1)+dt.timedelta(days=i+1)).isoformat(),value=value))
   rows.append(dict(code=k,currency='CNY',marketValue=50,basis='total-return',sourceUrl='https://example.org/history',history=history))
  return dict(asOf='2026-10-06',baseCurrency='CNY',holdings=rows,minimumObservations=20,rollingWindowObservations=40,rollingStride=20,tailConfidence=.9,minimumTailObservations=3)
 def test_covariance_and_opposite_assets(self):
  r=analyze(self.doc());h=r['historical'];self.assertAlmostEqual(h['correlations']['a']['b'],-1);self.assertAlmostEqual(h['covariance']['a']['b'],-h['covariance']['a']['a']);self.assertEqual(len(h['rolling']),3)
 def test_last_rolling_window_ends_at_latest_observation(self):
  d=self.doc(83);r=analyze(d);self.assertEqual(r['historical']['rolling'][-1]['end'],d['holdings'][0]['history'][-1]['date'])
 def test_tail_count_exact_not_float_ceil(self):
  h=analyze(self.doc(100))['historical'];self.assertEqual(h['tail']['tailObservations'],10);self.assertAlmostEqual(h['tail']['worstTailMeanReturnPct'],0)
 def test_short_tail_not_zero(self):
  d=self.doc(40);d['tailConfidence']=.99;r=analyze(d);self.assertIsNone(r['historical']['tail']['worstTailMeanReturnPct'])
 def test_alignment_gaps_not_filled(self):
  d=self.doc();d['holdings'][1]['history'].pop(10);r=analyze(d);self.assertEqual(r['historical']['observations'],78)
 def test_invalid_parameters(self):
  for k,v in [('rollingWindowObservations',10),('rollingStride',0),('tailConfidence',1),('minimumTailObservations',True)]:
   d=self.doc();d[k]=v
   with self.assertRaises(ValueError):analyze(d)
 def test_no_crisis_claim_without_windows(self):
  d=self.doc();body=markdown(analyze(d),d);self.assertIn('不声称完成危机复盘',body);self.assertIn('不代表未来损失概率',body)
 def test_unaudited_cannot_be_certified(self):
  quote='本半年度报告未经审计。';report=dict(fileSha256='x',pages=[dict(page=2,text=quote)])
  with self.assertRaises(ValueError):validate(dict(auditStatus='audited',evidence=[dict(page=2,quote=quote)]),report)
  self.assertEqual(validate(dict(auditStatus='unaudited',evidence=[dict(page=2,quote=quote)]),report)['auditStatus'],'unaudited')
 def test_arbitrary_quote_not_audit_evidence(self):
  quote='本公司营业收入同比增长。';report=dict(fileSha256='x',pages=[dict(page=2,text=quote)])
  with self.assertRaises(ValueError):validate(dict(auditStatus='audited',evidence=[dict(page=2,quote=quote)]),report)
 def test_same_path_contributions_use_linking_for_fixed_weights(self):
  d=self.doc(4);d['minimumObservations']=3;d.pop('rollingWindowObservations')
  for row,values in zip(d['holdings'],[[100,200,100,100,100],[100,100,200,200,200]]):
   for point,value in zip(row['history'],values):point['value']=value
  for mode,expected in [('buy-and-hold',[0,50]),('fixed-observation-weights',[12.5,75])]:
   d['historicalPortfolioMode']=mode;p=analyze(d)['historical']['portfolioPath']
   self.assertEqual([x['contributionPp'] for x in p['returnContributions']],expected)
   self.assertAlmostEqual(sum(expected),p['totalReturnPct'])
 def test_positive_return_can_remain_below_old_peak(self):
  d=self.doc(4);d['minimumObservations']=3;d.pop('rollingWindowObservations');d['historicalPortfolioMode']='buy-and-hold'
  for row,values in zip(d['holdings'],[[100,200,100,150,160],[100,100,100,100,100]]):
   for point,value in zip(row['history'],values):point['value']=value
  result=analyze(d);p=result['historical']['portfolioPath'];self.assertAlmostEqual(p['totalReturnPct'],30)
  self.assertAlmostEqual(p['endDrawdownPct'],-100*2/15);self.assertEqual(p['highestWealthDate'],'2025-01-02')
  body=markdown(result,d);self.assertIn('13.33%',body);self.assertIn('不是单品收益率',body);self.assertIn('尚未恢复',body)
if __name__=='__main__':unittest.main()
