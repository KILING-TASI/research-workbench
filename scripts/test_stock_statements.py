import unittest,tempfile
from pathlib import Path
from stock_statements import select,collect
class Tests(unittest.TestCase):
 def test_cutoff_identity_null(self):
  row=dict(SECURITY_CODE='600519',REPORT_DATE='2025-12-31',NOTICE_DATE='2026-03-01',CURRENCY='CNY',TOTAL_ASSETS=None)
  self.assertEqual(select([row],'600519','2025-01-01','2026-02-01'),[])
  self.assertIsNone(select([row],'600519','2025-01-01','2026-10-05')[0]['raw']['TOTAL_ASSETS'])
  with self.assertRaises(ValueError):select([row],'600036','2025-01-01','2026-10-05')
 def test_all_fields_and_no_overwrite(self):
  row=dict(SECURITY_CODE='600519',REPORT_DATE='2025-12-31',NOTICE_DATE='2026-03-01',CURRENCY='CNY',CUSTOM_FIELD=123,TOTAL_ASSETS=100,TOTAL_LIABILITIES=60,TOTAL_EQUITY=40)
  with tempfile.TemporaryDirectory() as d:
   out=Path(d)/'result';r=collect('600519','2025-01-01','2026-10-05',out,loader=lambda url:dict(result=dict(pages=1,data=[row])))
   self.assertEqual(r['commonPeriods'],['2025-12-31']);self.assertEqual(r['tables']['income']['rows'][0]['raw']['CUSTOM_FIELD'],123)
   self.assertEqual(r['balanceChecks'][0]['difference'],0)
   with self.assertRaises(FileExistsError):collect('600519','2025-01-01','2026-10-05',out)
 def test_failures_are_explicit(self):
  with tempfile.TemporaryDirectory() as d:
   r=collect('600519','2025-01-01','2026-10-05',Path(d)/'result',loader=lambda url:{},text_loader=lambda url:'')
   self.assertEqual(r['status'],'partial');self.assertEqual(len(r['gaps']),3);self.assertEqual(r['commonPeriods'],[])
 def test_provider_text_cannot_become_csv_formula(self):
  import csv
  row=dict(SECURITY_CODE='600519',REPORT_DATE='2025-12-31',NOTICE_DATE='2026-03-01',CURRENCY='CNY',CUSTOM_FIELD='=HYPERLINK("https://example.com")',NEGATIVE=-12)
  with tempfile.TemporaryDirectory() as d:
   out=Path(d)/'result';collect('600519','2025-01-01','2026-10-05',out,loader=lambda url:dict(result=dict(pages=1,data=[row])))
   with (out/'income/全部字段.csv').open(encoding='utf-8-sig',newline='') as f:rows=list(csv.reader(f))
   values={r[3]:r[4] for r in rows[1:]};self.assertTrue(values['CUSTOM_FIELD'].startswith("'="));self.assertEqual(values['NEGATIVE'],'-12')
 def test_malformed_records_explicit(self):
  for rows in [None,{},[None]]:
   with self.assertRaises(ValueError):select(rows,'600519','2025-01-01','2026-10-05')
if __name__=='__main__':unittest.main()
