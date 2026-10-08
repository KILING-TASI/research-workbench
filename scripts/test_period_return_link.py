import unittest,copy
from period_return_link import calculate,brief
class Tests(unittest.TestCase):
 def test_input_shape_and_strict_dates(self):
  for invalid in [None,[],1]:
   with self.subTest(invalid=invalid),self.assertRaises(ValueError):calculate(invalid)
  s=self.spec();s['periods']=[None]
  with self.assertRaises(ValueError):calculate(s)
  for value in [None,True,'20250101','2025-1-1']:
   s=self.spec();s['periods'][0]['start']=value
   with self.subTest(value=value),self.assertRaises(ValueError):calculate(s)
 def spec(self):
  basis=dict(currency='CNY',returnBasis='total-return',benchmarkId='declared-index',benchmarkVersion='v1')
  return dict(**basis,inputPrecision='reported-rounded',periods=[dict(**basis,start='2025-01-01',end='2025-12-31',fundReturnPct='4.38',benchmarkReturnPct='16.80',source='report1'),dict(**basis,start='2026-01-01',end='2026-06-30',fundReturnPct='-19.91',benchmarkReturnPct='9.39',source='report2')])
 def test_compounding(self):
  r=calculate(self.spec());self.assertEqual(r['linkedFundReturnPct'],'-16.40205800');self.assertEqual(r['linkedGapPp'],'-44.16957800')
 def test_overlap_or_gap(self):
  for start in ['2025-12-31','2026-01-02']:
   s=self.spec();s['periods'][1]['start']=start
   with self.assertRaises(ValueError):calculate(s)
 def test_basis_change(self):
  for key in ['currency','returnBasis','benchmarkVersion','benchmarkId']:
   s=self.spec();s['periods'][1][key]='changed'
   with self.assertRaises(ValueError):calculate(s)
 def test_invalid_numbers(self):
  for value in ['NaN','Infinity','-100.01',True]:
   s=self.spec();s['periods'][1]['fundReturnPct']=value
   with self.assertRaises(ValueError):calculate(s)
 def test_zero_fund_allowed_not_zero_benchmark(self):
  s=self.spec();s['periods'][1]['fundReturnPct']='-100';self.assertEqual(calculate(s)['linkedFundReturnPct'],'-100.0000')
  s['periods'][1]['benchmarkReturnPct']='-100'
  with self.assertRaises(ValueError):calculate(s)
 def test_declared_rounding_envelope(self):
  from decimal import Decimal
  s=self.spec()
  for row in s['periods']:row['returnPctDecimalPlaces']=2
  r=calculate(s);low,high=map(Decimal,r['roundingEnvelope']['gapPp']);self.assertLess(low,Decimal(r['linkedGapPp']));self.assertGreater(high,Decimal(r['linkedGapPp']))
 def test_missing_precision_not_invented(self):
  s=self.spec();s['periods'][0]['returnPctDecimalPlaces']=2;self.assertIsNone(calculate(s)['roundingEnvelope'])
 def test_false_precision_rejected(self):
  for precision in [True,-1,9]:
   s=self.spec();s['periods'][0]['returnPctDecimalPlaces']=precision
   with self.assertRaises(ValueError):calculate(s)
  s=self.spec();s['periods'][0].update(returnPctDecimalPlaces=2,fundReturnPct='4.381')
  with self.assertRaises(ValueError):calculate(s)
 def test_report_computed_values(self):
  text=brief(calculate(self.spec()));self.assertIn('累计落后44.17个百分点',text)
  self.assertIn('-16.40%',text);self.assertIn('不是经理个人贡献',text)
 def test_report_no_invented_range(self):
  self.assertIn('不给舍入范围',brief(calculate(self.spec())))
 def test_report_disclosed_range(self):
  s=self.spec()
  for row in s['periods']:row['returnPctDecimalPlaces']=2
  text=brief(calculate(s));self.assertIn('-16.4113%至-16.3928%',text);self.assertIn('不是统计置信区间',text)
if __name__=='__main__':unittest.main()
