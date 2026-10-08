import tempfile,unittest
from pathlib import Path
from unittest.mock import MagicMock,patch
from fund_report_holdings import extract,number

class Tests(unittest.TestCase):
 def test_nonfinite_original_token_rejected(self):
  for token in ['NaN','Infinity','-Infinity']:
   with self.assertRaises(ValueError):number(token)
 def test_nine_column_stock_row_does_not_use_domestic_code_variable(self):
  with tempfile.TemporaryDirectory() as directory:
   p=Path(directory)/'report.pdf';p.write_bytes(b'%PDF-fixture')
   page=MagicMock();page.extract_text.return_value='159941 年度报告 2025年12月31日\n8.4 期末按公允价值所有权益投资明细\n8.5 报告期内权益投资组合的重大变动'
   page.extract_tables.return_value=[[['1','Apple','苹果','AAPL US','纳斯达克','美国','10','50.00','50.00']]]
   doc=MagicMock();doc.__enter__.return_value=doc;doc.pages=[page]
   with patch('fund_report_holdings.pdfplumber.open',return_value=doc):r=extract(p,'159941','2025-12-31','2026-03-31','https://example.org/report','100','50')
   self.assertEqual(r['holdings'][0]['code'],'AAPL');self.assertEqual(r['holdings'][0]['quantity'],10);self.assertEqual(r['equityMarketValueCNY'],50)
   page.extract_tables.return_value[0][0][6]='10.5'
   with patch('fund_report_holdings.pdfplumber.open',return_value=doc):fractional=extract(p,'159941','2025-12-31','2026-03-31','https://example.org/report','100','50')
   self.assertEqual(fractional['holdings'][0]['quantity'],10.5)

if __name__=='__main__':unittest.main()
