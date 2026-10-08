import unittest,re
from unittest.mock import patch
from report_manager_products import company_rows,COMPANY_START,COMPANY_END,run,markdown
class Tests(unittest.TestCase):
 def test_future_report_rejected_before_pdf_helpers(self):
  dossier=dict(code='000001',asOf='2026-10-03',report=dict(code='000001',asOf='2026-10-03',reportDate='2025-12-31',metadata=dict(publishedAt='2026-11-01')))
  with patch('report_manager_products.company') as company,patch('report_manager_products.extract_archive') as extract:
   result=run([dossier],'2026-10-03')
   self.assertEqual(result['status'],'unavailable');self.assertIn('截止日',result['gaps'][0]['reason']);company.assert_not_called();extract.assert_not_called()
 def test_bad_query_name_rejected(self):
  for name in ['',True,[]]:
   with self.subTest(name=name),self.assertRaises(ValueError):run([dict(code='000001')],'2026-10-03',name)
 def test_all_missing_preserves_candidates(self):
  r=run([{'code':'000001','asOf':'2026-10-03'},{'code':'000002','asOf':'2026-10-03'}],'2026-10-03')
  self.assertEqual(r['status'],'unavailable');self.assertEqual(r['requestedCodes'],['000001','000002']);self.assertEqual(len(r['gaps']),2);self.assertEqual(r['managers'],[]);self.assertIn('未找到匹配任职记录',markdown(r))
 def test_body_headers_and_toc(self):
  for v in ['基金管理人和基金托管人','2.3 基金管理人和基金托管人']:self.assertIsNotNone(re.search(COMPANY_START,v))
  for v in ['信息披露方式','2.4 信息披露方式','2.5 信息披露方式']:self.assertIsNotNone(re.search(COMPANY_END,v))
  self.assertIsNone(re.search(COMPANY_START,'基金管理人和基金托管人 ........ 7'))
  self.assertIsNone(re.search(COMPANY_END,'信息披露方式 ........ 8'))
 def test_manager_column_not_custodian(self):
  x=company_rows([(6,[1,2,3,4],[['项目',None,'基金管理人','基金托管人'],['名称',None,'某基金公司','某银行']])]);self.assertEqual(x[0]['value'],'某基金公司');self.assertEqual(x[0]['page'],6)
 def test_conflict_not_silent(self):
  with self.assertRaises(ValueError):company_rows([(6,[],[['项目','基金管理人'],['名称','公司甲'],['名称','公司乙']])])
 def test_no_header_not_guess(self):
  with self.assertRaises(ValueError):company_rows([(6,[],[['名称','某基金公司']])])
if __name__=='__main__':unittest.main()
