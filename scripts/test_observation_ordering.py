import unittest
from research_pipeline import series
from fund_comparison_brief import report
class ObservationOrdering(unittest.TestCase):
 def spec(self):return {'asOf':'2026-09-30','rows':[{'code':c,'basis':'nav-with-distributions','comparisonGroup':'指定比较','history':[{'date':'2026-09-02','nav':1.1},{'date':'2026-09-01','nav':1}]} for c in ['A','B']]}
 def test_sorting_exposed_in_result_and_report(self):
  result,text=report(self.spec());self.assertTrue(result['alignment'][0]['inputWasReordered']);self.assertIn('计算前已按日期排序',text);self.assertAlmostEqual(result['rows'][0]['totalReturnPct'],10)
 def test_duplicate_dates_not_overwritten(self):
  d=self.spec();d['rows'][0]['history'][0]['date']='2026-09-01'
  with self.assertRaisesRegex(ValueError,'日期重复'):report(d)
 def test_wrong_history_shape_rejected(self):
  for value in ['text',[None],[{}]]:
   with self.subTest(value=value),self.assertRaisesRegex(ValueError,'观测列表'):series(value,'2026-09-30','nav-with-distributions')
