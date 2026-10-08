import hashlib,tempfile,unittest
from pathlib import Path
from unittest.mock import patch,MagicMock
from report_fee_evidence import extract_archive as fees
from report_manager_tenure import extract_archive as managers
class Tests(unittest.TestCase):
 def test_accounting_gap_does_not_block_independent_document_fields(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'a.pdf';p.write_bytes(b'%PDF-test')
   r=dict(code='159915',status='股票明细与行业表勾稽完成，会计差额待核验',documentPath=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),reportDate='2026-06-30',metadata=dict(publishedAt='2026-08-31',sourceUrl='https://example.org/a'))
   for module,extract in [('report_fee_evidence',fees),('report_manager_tenure',managers)]:
    with self.subTest(module=module):
     doc=MagicMock();doc.__enter__.return_value.pages=[]
     with patch(module+'.pdfplumber.open',return_value=doc):self.assertIsInstance(extract(r),dict)
     with self.assertRaises(ValueError):extract(dict(r,status='已下载待核验'))
     with self.assertRaises(ValueError):extract(dict(r,sha256='invalid'))
if __name__=='__main__':unittest.main()
