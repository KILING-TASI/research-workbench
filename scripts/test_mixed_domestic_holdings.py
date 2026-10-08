import unittest,re
from decimal import Decimal
from fund_report_holdings import domestic_rows,domestic_result
class Tests(unittest.TestCase):
 def doc(self,hk=True):
  class Table:
   bbox=[0,20,100,80]
   def extract(self):return [['1','00700','腾讯控股','1','60.00','60.00'],['2','600519','贵州茅台','1','30.00','30.00']]
  class Page:
   def extract_text(self):return ('8.2.2 报告期末按行业分类的港股通投资股票投资组合\n' if hk else '')+'8.3 期末按公允价值占基金资产净值比例大小排序的所有股票投资明细\n8.4 报告期内股票投资组合的重大变动'
   def search(self,pattern):return [dict(top=90)] if re.search(pattern,self.extract_text()) else []
   def find_tables(self):return [Table()]
  class Doc:pages=[Page()]
  return Doc()
 def test_reported_h_prefix_keeps_raw_code(self):
  doc=self.doc();page=doc.pages[0];table=page.find_tables()[0];table.extract=lambda:[['1','H00700','腾讯控股','1','60.00','60.00'],['2','600519','贵州茅台','1','30.00','30.00']];page.find_tables=lambda:[table]
  r=domestic_result(doc,b'fixture','015931','2026-06-30','2026-08-31','https://example.org/pdf',Decimal(100),Decimal(90));self.assertEqual(r['holdings'][0]['code'],'00700');self.assertEqual(r['holdings'][0]['components'][0]['reportedCode'],'H00700')
 def test_hk_section_after_active_investment(self):
  doc=self.doc();page=doc.pages[0];original=page.extract_text;page.extract_text=lambda:original().replace('8.2.2 报告期末按行业分类的港股通','8.2.3 报告期末按行业分类的港股通')
  self.assertEqual(domestic_rows(doc)[0][0]['cells'][1],'00700')
 def test_reporting_period_heading_variant(self):
  doc=self.doc();page=doc.pages[0];original=page.extract_text;page.extract_text=lambda:original().replace('8.3 期末按','8.3 报告期末按')
  self.assertEqual(len(domestic_rows(doc)[0]),2)
 def test_mixed_rank_sequence(self):self.assertEqual([x['cells'][1] for x in domestic_rows(self.doc())[0]],['00700','600519'])
 def test_five_digit_without_hk_evidence_not_accepted(self):
  with self.assertRaises(ValueError):domestic_rows(self.doc(False))
 def test_market_namespace_preserved(self):
  r=domestic_result(self.doc(),b'fixture','005827','2025-12-31','2026-03-31','https://example.org/report',Decimal(100),Decimal(90))
  self.assertEqual(r['holdings'][0]['code'],'00700');self.assertEqual(r['holdings'][0]['securityNamespace'],'HK-equity');self.assertEqual(r['holdings'][1]['securityNamespace'],'CN-equity')
 def test_shared_rank_cross_market_keeps_securities_separate(self):
  doc=self.doc();table=doc.pages[0].find_tables()[0];table.extract=lambda:[['1','00700','港股','1','60.00','60.00'],['1','600519','境内','1','30.00','30.00'],['2','000001','其他','1','5.00','5.00']]
  doc.pages[0].find_tables=lambda:[table]
  r=domestic_result(doc,b'fixture','005827','2026-06-30','2026-08-31','https://example.org/pdf',Decimal(100),Decimal(95))
  self.assertEqual(len(r['holdings']),3);self.assertEqual(r['rankTies'][0]['basis'],'reported-shared-rank-distinct-securities');self.assertIsNone(r['rankTies'][0]['marketValueCNY'])
 def test_unequal_same_market_duplicate_rank_rejected(self):
  doc=self.doc();table=doc.pages[0].find_tables()[0];table.extract=lambda:[['1','600519','A','1','60.00','60.00'],['1','000001','B','1','30.00','30.00']];doc.pages[0].find_tables=lambda:[table]
  with self.assertRaises(ValueError):domestic_rows(doc)
 def ah_order_doc(self,declared=True,same_name=True):
  doc=self.doc();page=doc.pages[0];old=page.extract_text
  note='对于同时在A+H股上市的股票，合并计算公允价值参与排序，并按照不同股票分别披露。'
  page.extract_text=lambda:old()+('\n'+note if declared else '')
  table=page.find_tables()[0]
  table.extract=lambda:[['1','600519','第一','1','50.00','25.00'],['2','688981','同名','1','40.00','20.00'],['3','00981','同名' if same_name else '其他','1','5.00','2.50'],['4','600176','第四','1','42.00','21.00']]
  page.find_tables=lambda:[table];return doc
 def test_explicit_ah_order_keeps_separate_securities(self):
  r=domestic_result(self.ah_order_doc(),b'fixture','011034','2026-06-30','2026-08-31','https://example.org/pdf',Decimal(200),Decimal(137))
  self.assertEqual(len(r['holdings']),4)
  a=next(x for x in r['holdings'] if x['code']=='688981');h=next(x for x in r['holdings'] if x['code']=='00981')
  self.assertEqual(a['components'][0]['issuerOrderPairCodes'],['688981','00981']);self.assertNotEqual(a['securityNamespace'],h['securityNamespace'])
 def test_ah_order_without_declaration_rejected(self):
  with self.assertRaisesRegex(ValueError,'排序逆序'):domestic_rows(self.ah_order_doc(False))
 def test_declaration_does_not_group_different_names(self):
  with self.assertRaisesRegex(ValueError,'排序逆序'):domestic_rows(self.ah_order_doc(True,False))
 def test_equal_value_competition_rank_is_not_missing_row(self):
  doc=self.doc(False);table=doc.pages[0].find_tables()[0];table.extract=lambda:[['1','600519','甲','1','60.00','30.00'],['1','000001','乙','1','60.00','30.00'],['3','000002','丙','1','50.00','25.00']];doc.pages[0].find_tables=lambda:[table]
  r=domestic_result(doc,b'fixture','011730','2026-06-30','2026-08-31','https://example.org/pdf',Decimal(200),Decimal(170));self.assertEqual(len(r['holdings']),3)
 def test_unequal_cross_market_tie_does_not_allow_skip(self):
  doc=self.doc();table=doc.pages[0].find_tables()[0];table.extract=lambda:[['1','00700','甲','1','60.00','30.00'],['1','600519','乙','1','30.00','15.00'],['3','000002','丙','1','20.00','10.00']];doc.pages[0].find_tables=lambda:[table]
  with self.assertRaisesRegex(ValueError,'序号缺失'):domestic_rows(doc)
if __name__=='__main__':unittest.main()


