import unittest
from collection_quality_brief import brief
from research_brief_html import render
class Tests(unittest.TestCase):
 def test_financial_raw_overflow_rejected_before_publication(self):
  import tempfile
  from pathlib import Path
  from collection_quality_brief import publish
  with tempfile.TemporaryDirectory() as directory:
   p=Path(directory)/'input.json';out=Path(directory)/'report'
   p.write_text('{"rows":[{"code":"600000","kind":"stock","financials":[{"period":"2026-03-31","publishedAt":"2026-04-30","raw":{"amount":1e999}}]}]}')
   with self.assertRaisesRegex(ValueError,'浮点数超出有限范围'):publish(p,out)
   self.assertFalse(out.exists())
 def test_financial_period_outside_requested_window_rejected(self):
  row=self.row();row['requestScope']={'asOf':'2026-09-30','financialStart':'2026-01-01'}
  row['financials']=[{'period':'2025-12-31','publishedAt':'2026-04-01'}]
  with self.assertRaisesRegex(ValueError,'财务报告期早于请求起始日'):brief({'asOf':'2026-09-30','rows':[row]})
  row['financials'][0]['period']='2026-03-31'
  self.assertIn('资料获取与质量说明',brief({'asOf':'2026-09-30','rows':[row]}))
 def row(self):return {'code':'001938','kind':'fund','identity':{'code':'001938','name':'A|C'},'history':[{'date':'2026-09-01','nav':1}],'source':'https://example.org/a','retrievedAt':'2026-09-02T00:00:00Z','gaps':['原文未核验']}
 def test_table_source_and_gap_preserved(self):
  text=brief({'rows':[self.row()]});markup=render(text)
  self.assertIn('<td>A|C</td>',markup);self.assertIn('<td>1</td>',markup);self.assertIn('href="https://example.org/a"',markup);self.assertIn('原文未核验',text)
 def test_identity_conflict_rejected(self):
  row=self.row();row['identity']['code']='999999'
  with self.assertRaises(ValueError):brief({'rows':[row]})
 def test_duplicate_history_rejected(self):
  row=self.row();row['history']*=2
  with self.assertRaises(ValueError):brief({'rows':[row]})
 def test_empty_history_not_filled(self):
  row=self.row();row['history']=[];markup=render(brief({'rows':[row]}));self.assertIn('<td>0</td><td></td><td></td>',markup)
 def test_split_limitation_visible(self):
  row=self.row();row['history'][0]['distribution']='拆分：每份折算2份'
  self.assertIn('基础收益入口会停止计算',brief({'rows':[row]}))
if __name__=='__main__':unittest.main()
