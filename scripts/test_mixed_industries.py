import unittest,tempfile,re
from pathlib import Path
from decimal import Decimal
from fund_report_industries import mixed_result,extract,amount
from unittest.mock import patch
class Tests(unittest.TestCase):
 def test_nonfinite_denominators_rejected_before_pdf(self):
  base=dict(netAssetsCNY='100',equityMarketValueCNY='30',reportDate='2026-06-30',publishedAt='2026-08-30',sourceUrl='https://example.org/a.pdf')
  for key in ['netAssetsCNY','equityMarketValueCNY']:
   for value in ['Infinity','NaN','-Infinity']:
    with self.subTest(key=key,value=value),patch('fund_report_industries.pdfplumber.open') as opened,self.assertRaises(ValueError):extract('unused',{**base,key:value})
    opened.assert_not_called()
 def test_source_and_dates_rejected_before_pdf(self):
  base=dict(netAssetsCNY='100',equityMarketValueCNY='30',reportDate='2026-06-30',publishedAt='2026-08-30',sourceUrl='https://example.org/a.pdf')
  invalid=[{'sourceUrl':url} for url in ['https://user:secret@example.org/a','https:///a','https://example.org:bad/a','https://example.org/ a']]+[{'reportDate':'20260630'},{'publishedAt':'20260830'}]
  for override in invalid:
   with self.subTest(override=override),patch('fund_report_industries.pdfplumber.open') as opened,self.assertRaises(ValueError):extract('unused',{**base,**override})
   opened.assert_not_called()
 def test_original_amount_rejects_nonfinite(self):
  for value in ['NaN','Infinity','-Infinity']:
   with self.subTest(value=value),self.assertRaises(ValueError):amount(value)
  self.assertEqual(amount('1,234.50'),Decimal('1234.50'))
 def doc(self,gics=True):
  class Table:
   def __init__(self,bbox,rows):self.bbox=bbox;self.rows=rows
   def extract(self):return self.rows
  class Page:
   def extract_text(self):return '8.2.1 报告期末按行业分类的境内股票投资组合\n8.2.2 报告期末按行业分类的港股通投资股票投资组合\n8.3 期末按公允价值排序的所有股票投资明细\n'+('GICS' if gics else '')
   def search(self,pattern):
    if not re.search(pattern,self.extract_text()):return []
    return [dict(top=10 if '.1' in pattern else 50 if '.2' in pattern else 90)]
   def find_tables(self):
    cn=[[k,'同名行业','10.00' if k=='A' else '-','10.00' if k=='A' else '-'] for k in 'ABCDEFGHIJKLMNOPQRS']+[['合计','10.00','10.00']]
    return [Table([0,20,100,40],cn),Table([0,60,100,80],[['同名行业','20.00','20.00'],['合计','20.00','20.00']])]
  class Doc:pages=[Page()]
  return Doc()
 def test_same_name_kept_separate(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'a.pdf';p.write_bytes(b'fixture');r=mixed_result(self.doc(),p,{},Decimal(100),Decimal(30));self.assertEqual(len(r['sectors']),20);self.assertEqual(r['sectors'][0]['name'],'境内：同名行业');self.assertEqual(r['sectors'][-1]['name'],'港股GICS：同名行业')
 def test_no_gics_not_inferred(self):
  with self.assertRaises(ValueError):mixed_result(self.doc(False),'unused',{},Decimal(100),Decimal(30))
 def test_total_mismatch(self):
  with self.assertRaises(ValueError):mixed_result(self.doc(),'unused',{},Decimal(100),Decimal(31))
 def no_hk_doc(self,statement):
  d=self.doc(False);page=d.pages[0];original_tables=page.find_tables
  page.extract_text=lambda:'8.2.1 报告期末按行业分类的境内股票投资组合\n8.2.2 报告期末按行业分类的港股通投资股票投资组合\n'+statement+'\n8.3 期末按公允价值排序的所有股票投资明细'
  page.find_tables=lambda:original_tables()[:1]
  return d
 def test_explicit_no_hk(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'a.pdf';p.write_bytes(b'fixture')
   r=mixed_result(self.no_hk_doc('无。'),p,{},Decimal(100),Decimal(10))
   self.assertEqual(r['taxonomy'],'report-native-A-S');self.assertEqual(r['emptyMarketEvidence']['quote'],'无。');self.assertEqual(r['componentTotalsCNY'],['10.00','0'])
 def test_missing_hk_not_zero(self):
  for statement in ['', '资料缺失', '无。另有持仓待核实']:
   with self.subTest(statement=statement),self.assertRaises(ValueError):mixed_result(self.no_hk_doc(statement),'unused',{},Decimal(100),Decimal(10))
if __name__=='__main__':unittest.main()
