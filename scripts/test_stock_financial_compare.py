import unittest
from stock_financial_compare import compare
class Tests(unittest.TestCase):
 def archive(self,code,period,value,published='2026-08-30'):return dict(code=code,sources=['https://example.org'],rows=[dict(period=period,publishedAt=published,raw=dict(SECURITY_CODE=code,PARENTNETPROFIT=value))])
 def test_common_period_not_latest_per_company(self):
  a=self.archive('600036','2026-06-30',1);a['rows']+=self.archive('600036','2026-09-30',2,published='2026-10-30')['rows'];b=self.archive('601166','2026-06-30',3)
  self.assertEqual(compare([a,b],'2026-10-05')['comparisonPeriod'],'2026-06-30')
 def test_missing_not_zero_and_versions_preserved(self):
  a=self.archive('600036','2026-06-30',1);a['rows']+=self.archive('600036','2026-06-30',2)['rows'];b=self.archive('601166','2026-06-30',None)
  r=compare([a,b],'2026-10-05');self.assertTrue(r['companies'][0]['fields']['PARENTNETPROFIT']['conflict']);self.assertIsNone(r['companies'][1]['fields']['PARENTNETPROFIT']['observations'][0]['value'])
 def test_invalid_same_period_version_cannot_join_valid_record(self):
  a=self.archive('600036','2026-06-30',1);a['rows']+=self.archive('600036','2026-06-30',999,published='2026-06-29')['rows'];b=self.archive('601166','2026-06-30',3)
  with self.assertRaisesRegex(ValueError,'早于报告期'):compare([a,b],'2026-10-05')
 def test_oversized_integer_is_explicit_invalid_financial_value(self):
  a=self.archive('600036','2026-06-30',10**400);b=self.archive('601166','2026-06-30',3)
  with self.assertRaisesRegex(ValueError,'财务数值非法'):compare([a,b],'2026-10-05')
if __name__=='__main__':unittest.main()
