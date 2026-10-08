import unittest
from fund_document_archive import report_period
class PeriodEvidence(unittest.TestCase):
 def test_explicit_period_and_omitted_year(self):
  for text in ['本报告期自2026年1月1日起至6月30日止。','本报告期自2026年1月1日至2026年6月30日止。']:
   r=report_period([(2,text)],'2026-01-01','2026-06-30');self.assertEqual(r['status'],'matched');self.assertEqual(r['evidence'][0]['page'],2)
 def test_cover_and_dispatch_dates_not_period(self):
  self.assertEqual(report_period([(1,'2026年中期报告 2026年6月30日 送出日期2026年8月31日')],'2026-01-01','2026-06-30')['status'],'missing')
 def test_conflicting_periods_not_selected(self):
  r=report_period([(2,'本报告期自2026年1月1日至6月30日止。'),(4,'本报告期自2025年1月1日至6月30日止。')],'2026-01-01','2026-06-30');self.assertEqual(r['status'],'conflict')
 def test_wrong_window_is_conflict(self):
  self.assertEqual(report_period([(2,'本报告期自2026年1月1日至6月30日止。')],'2026-04-01','2026-06-30')['status'],'conflict')
 def test_invalid_date_retained(self):
  r=report_period([(2,'本报告期自2026年2月30日至6月30日止。')],'2026-01-01','2026-06-30');self.assertEqual(r['status'],'conflict');self.assertTrue(r['evidence'][0]['invalid'])
