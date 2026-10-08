import unittest,tempfile
from pathlib import Path
from huatai_report_catalog import select,run
class Tests(unittest.TestCase):
 title='上证红利交易型开放式指数证券投资基金2026年中期报告'
 def test_exact_product_and_official_pdf_only(self):
  raw=('<a title="'+self.title+'" href="/upload/pdf/a.pdf">x</a><a title="'+self.title+'" href="https://other.test/upload/pdf/b.pdf">x</a><a title="'+self.title.replace('指数证券','指数证券联接')+'" href="/upload/pdf/c.pdf">x</a>').encode()
  self.assertEqual(len(select(raw,self.title)),1)
 def test_bounded_missing_and_failure_preserved(self):
  with tempfile.TemporaryDirectory() as d:
   result=run(self.title,Path(d)/'missing',2,lambda u:b'<html></html>');self.assertEqual(len(result['attempts']),2);self.assertFalse(result['completeCatalogVerified'])
   def bad(u):raise TimeoutError('timeout')
   result=run(self.title,Path(d)/'failed',2,bad);self.assertIn('error',result['attempts'][0]);self.assertFalse(result['pdfVerified']);self.assertEqual(result['status'],'failed')
 def test_found_stops_and_archive_not_overwritten(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'out';result=run(self.title,p,20,lambda u:('<a title="'+self.title+'" href="/upload/pdf/a.pdf">x</a>').encode());self.assertEqual(len(result['attempts']),1)
   with self.assertRaises(FileExistsError):run(self.title,p)
