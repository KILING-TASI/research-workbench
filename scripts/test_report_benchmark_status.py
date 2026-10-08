import unittest
from report_benchmark_status import inspect
class Tests(unittest.TestCase):
 def test_absence_not_missing(self):
  r=inspect([dict(page=3,text='业绩比较基准 本基金无业绩比较基准。')]);self.assertEqual(r['status'],'explicitly-not-defined');self.assertIsNone(r['benchmarkReturns'])
  self.assertEqual(inspect([dict(page=3,text='基金净值表现')])['status'],'not-located')
 def test_formula_and_conflict(self):
  formula='业绩比较基准 沪深300指数收益率×80%+债券指数收益率×20%'
  self.assertEqual(inspect([dict(page=3,text=formula)])['status'],'formula-located-not-verified')
  r=inspect([dict(page=3,text=formula+'\n本基金无业绩比较基准。')]);self.assertEqual(r['status'],'conflicting-report-statements')
 def test_note_and_no_inference(self):
  self.assertEqual(inspect([dict(page=4,text='注：本基金未规定业绩比较基准。')])['status'],'explicitly-not-defined')
  self.assertEqual(inspect([dict(page=3,text='业绩比较基准收益率')])['status'],'not-located')

 def test_two_formulas_not_silently_same_status(self):
  r=inspect([dict(page=1,text='业绩比较基准 沪深300指数收益率×80%+债券指数收益率×20%'),dict(page=2,text='业绩比较基准 沪深300指数收益率×60%+债券指数收益率×40%')]);self.assertEqual(r['status'],'conflicting-report-statements');self.assertEqual(r['distinctLocatedFormulaCount'],2)
 def test_wrapped_formula_located_not_calculated(self):
  r=inspect([dict(page=1,text='业绩比较基准\n沪深300指数收益率×80%+债券指数收益率×20%')]);self.assertEqual(r['status'],'formula-located-not-verified');self.assertIn('\n',r['evidence'][0]['quote']);self.assertIsNone(r['benchmarkReturns'])
 def test_same_formula_repeat_not_conflict(self):
  row=dict(page=1,text='业绩比较基准 沪深300指数收益率×80%+债券指数收益率×20%');self.assertEqual(inspect([row,dict(row,page=2)])['distinctLocatedFormulaCount'],1)
 def test_duplicate_pages_rejected(self):
  row=dict(page=1,text='本基金无业绩比较基准。')
  with self.assertRaises(ValueError):inspect([row,row])
