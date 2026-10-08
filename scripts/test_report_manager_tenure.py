import unittest
from report_manager_tenure import table_records,classify_role,extract_archive
class Tests(unittest.TestCase):
 def table(self):return [["姓\n名","职务","任本基金的基金经理期限",None,"证券从业年限","说明"],["某经理","本基金的基金经理","2020-01-01","-","10年","经历"]]
 def test_current_role_wording(self):
  self.assertEqual(classify_role('本基金现任基金经理'),'manager')
  self.assertEqual(classify_role('本基金现任基金经理助理'),'assistant')
  self.assertEqual(classify_role('其他基金现任基金经理'),'ambiguous')
  t=self.table();t[1][1]='本基金现任基金经理';self.assertEqual(table_records([(17,t)],'2025-12-31','2026-03-31','https://example.org')[0]['roleCategory'],'manager')
 def test_assistant_not_manager(self):
  self.assertEqual(classify_role('本基金的基金经理助理'),'assistant');self.assertEqual(classify_role('本基金的基金经理、其他基金的基金经理助理'),'manager');self.assertEqual(classify_role('本基金的基金经理及本基金的基金经理助理'),'ambiguous')
 def test_role_after_page_continuation(self):
  t=self.table();t[1][1]='本基金的基金经理'
  r=table_records([(9,t),(10,[['','助理','','','','后续']])],'2025-12-31','2026-03-31','https://example.org')
  self.assertEqual(r[0]['roleCategory'],'assistant')
 def test_continuation(self):
  r=table_records([(9,self.table()),(10,[["","其他职务","","","","后续经历"]])],'2025-12-31','2026-03-31','https://example.org');self.assertEqual(r[0]['locator'],'PDF页9,10');self.assertIsNone(r[0]['end'])
 def test_eight_columns_and_chinese_date(self):
  t=[['姓名','职务','','任本基金的基金经理',None,'','证券从业年限','说明'],['某经理','本基金的基金经理','2013 年10 月29日',None,'-',None,'22年','履历']]
  r=table_records([(11,t)],'2025-12-31','2026-03-31','https://example.org');self.assertEqual(r[0]['start'],'2013-10-29')
 def test_no_header(self):self.assertFalse(table_records([(9,self.table()[1:])],'2025-12-31','2026-03-31','https://example.org'))
 def test_role_generic_continues_on_next_page_under_fund_header(self):
  t=self.table();t[1][1]='投资总监/权益投资组组长'
  r=table_records([(10,t),(11,[['','/基金经理/投资经理','','','','']])],'2025-12-31','2026-03-31','https://example.org')
  self.assertEqual(r[0]['roleCategory'],'manager');self.assertEqual(r[0]['pages'],[10,11])
 def test_incomplete_role_stays_ambiguous(self):
  t=self.table();t[1][1]='投资总监'
  self.assertEqual(table_records([(10,t)],'2025-12-31','2026-03-31','https://example.org')[0]['roleCategory'],'ambiguous')
 def test_publication_before_reporting_end_rejected(self):
  with self.assertRaises(ValueError):table_records([(10,self.table())],'2025-12-31','2025-03-31','https://example.org')
 def test_metadata_missing_fails_before_opening_pdf(self):
  with self.assertRaisesRegex(ValueError,'披露日期与来源地址'):extract_archive(dict(code='000991',metadata={},documentPath='missing.pdf'))
 def test_invalid_date(self):
  t=self.table();t[1][2]='2027-01-01'
  with self.assertRaises(ValueError):table_records([(9,t)],'2025-12-31','2026-03-31','https://example.org')
 def test_compact_leave_date_not_treated_as_standard(self):
  t=self.table();t[1][3]='20251201'
  with self.assertRaisesRegex(ValueError,'离任日期'):table_records([(9,t)],'2025-12-31','2026-03-31','https://example.org')
 def test_invalid_source_rejected_before_file_access(self):
  for url in ['https://user:secret@example.org/a','https:///a','https://example.org/ a']:
   with self.subTest(url=url),self.assertRaises(ValueError):extract_archive(dict(code='000991',reportDate='2025-12-31',metadata=dict(publishedAt='2026-03-31',sourceUrl=url),documentPath='missing.pdf'))
 def test_later_unrelated_table_not_appended(self):
  r=table_records([(9,self.table()),(30,[["","无关文本","","","","无关备注"]])],'2025-12-31','2026-03-31','https://example.org');self.assertEqual(r[0]['pages'],[9]);self.assertNotIn('无关',r[0]['roleText'])

class TableBoundaryTests(unittest.TestCase):
 table=Tests.table
 def test_unrelated_name_header_stops_old_manager_scope(self):
  other=[['姓名','职务','任职起点','结束','经验','说明'],['其他人员','基金经理','2021-01-01','-','5年','其他表']]
  r=table_records([(9,self.table()),(10,other)],'2025-12-31','2026-03-31','https://example.org')
  self.assertEqual([x['name'] for x in r],['某经理'])
 def test_boolean_or_reverse_pages_rejected(self):
  for tables in [[(True,self.table())],[(10,self.table()),(9,[])]]:
   with self.assertRaises(ValueError):table_records(tables,'2025-12-31','2026-03-31','https://example.org')
 def test_non_text_cells_rejected(self):
  t=self.table();t[1][4]=10
  with self.assertRaises(ValueError):table_records([(9,t)],'2025-12-31','2026-03-31','https://example.org')

if __name__=='__main__':unittest.main()
