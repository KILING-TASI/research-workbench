import re,unittest
from unittest.mock import patch,MagicMock
from decimal import Decimal
from fof_reports import industry_equity_evidence
class IndustrySegments(unittest.TestCase):
 def check(self,active=True,extra=None,note=True,reverse_order=False):
  page=MagicMock();page.extract_text.return_value='§7 投资组合报告\n'+('注：股票投资含可退替代款估值增值。' if note else '')
  def search(pattern):
   first='指数投资期末' if reverse_order else '期末指数投资'
   second='积极投资期末' if reverse_order else '期末积极投资'
   headings=[(10,'7.2.1 '+first+'按行业分类的境内股票投资组合'),(100,'7.3 期末按公允价值占基金资产净值比例大小排序的所有股票投资明细')]
   if active:headings.append((50,'7.2.2 '+second+'按行业分类的境内股票投资组合'))
   return [{'top':top} for top,title in headings if re.search(pattern,title)]
  page.search.side_effect=search
  tables=[]
  for top,value in [(20,'1,000.00')]+([(60,'2,000.00')] if active else [])+(extra or []):
   table=MagicMock();table.bbox=[0,top,100,top+10];table.extract.return_value=[['合计',value,'1.00']];tables.append(table)
  page.find_tables.return_value=tables;doc=MagicMock();doc.pages=[page]
  with patch('fof_reports.pdfplumber.open') as op:
   op.return_value.__enter__.return_value=doc
   return industry_equity_evidence('unused')
 def test_distinct_segments_added_once(self):
  value,evidence,notes=self.check();self.assertEqual(value,Decimal('3000.00'));self.assertEqual({e['segment'] for e in evidence},{'indexInvestment','activeInvestment'})
 def test_missing_active_not_accepted(self):
  with self.assertRaisesRegex(ValueError,'分表缺失'):self.check(active=False)
 def test_conflicting_same_segment_rejected(self):
  with self.assertRaisesRegex(ValueError,'唯一'):self.check(extra=[(70,'3,000.00')])
 def test_note_required_not_difference_explanation(self):
  with self.assertRaisesRegex(ValueError,'口径说明'):self.check(note=False)

 def test_report_index_active_prefix_order_supported(self):
  value,evidence,notes=self.check(reverse_order=True)
  self.assertEqual(value,Decimal('3000.00'))
  self.assertEqual({e['segment'] for e in evidence},{'indexInvestment','activeInvestment'})
 def test_alternate_order_still_rejects_missing_segment(self):
  with self.assertRaisesRegex(ValueError,'分表缺失'):self.check(active=False,reverse_order=True)
