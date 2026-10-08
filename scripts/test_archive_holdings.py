import unittest,tempfile,json,hashlib
from pathlib import Path
from unittest.mock import patch
from archive_holdings import run
class ArchiveHoldings(unittest.TestCase):
 def test_truthy_identity_is_not_verified(self):
  with tempfile.TemporaryDirectory() as root:
   source,pdf=self.fixture(root);data=json.loads(source.read_text('utf-8'));data['identity']['matched']='false';source.write_text(json.dumps(data),'utf-8')
   with self.assertRaises(ValueError):run(source,Path(root)/'out')
 def test_malformed_parser_output_is_preserved_as_gap(self):
  with tempfile.TemporaryDirectory() as root:
   source,pdf=self.fixture(root)
   with patch('archive_holdings.read_pages',return_value=[(1,'报告 159869 本报告期自2026年1月1日至6月30日止。')]):
    result=run(source,Path(root)/'out',parse_fn=lambda *args:[])
   self.assertEqual(result['status'],'unparsed');self.assertIsNone(result['holdings'])
 def fixture(self,root):
  path=Path(root)/'document.pdf';path.write_bytes(b'%PDFtest');record={'code':'159869','documentPath':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'identity':{'matched':True},'catalogItem':{'title':'报告','publishedAt':'2026-08-31'},'asOf':'2026-09-30','reportPeriod':{'status':'matched','expectedStart':'2026-01-01','expectedEnd':'2026-06-30'},'metadata':{'sourceUrl':'https://example.org/a.pdf'}}
  source=Path(root)/'archive.json';source.write_text(json.dumps(record),'utf-8');return source,path
 def test_changed_pdf_does_not_parse_or_publish(self):
  with tempfile.TemporaryDirectory() as root:
   source,pdf=self.fixture(root);pdf.write_bytes(b'%PDFchanged')
   with patch('archive_holdings.inspect_and_parse') as parse,self.assertRaisesRegex(ValueError,'摘要'):run(source,Path(root)/'out',parse_fn=parse)
   parse.assert_not_called();self.assertFalse((Path(root)/'out').exists())
 def test_period_requires_original_sentence(self):
  with tempfile.TemporaryDirectory() as root:
   source,pdf=self.fixture(root)
   with patch('archive_holdings.read_pages',return_value=[(1,'报告 159869。2026年6月30日')]),self.assertRaisesRegex(ValueError,'明示报告期'):run(source,Path(root)/'out')
 def test_parse_failure_is_gap_report_no_holdings(self):
  with tempfile.TemporaryDirectory() as root:
   source,pdf=self.fixture(root)
   with patch('archive_holdings.read_pages',return_value=[(1,'报告 159869 本报告期自2026年1月1日至6月30日止。')]):
    result=run(source,Path(root)/'out',parse_fn=lambda *args:(_ for _ in ()).throw(ValueError('布局未支持')))
   self.assertIsNone(result['holdings']);self.assertEqual(result['status'],'unparsed');self.assertIn('布局未支持',(Path(root)/'out/持仓核对.md').read_text('utf-8'))

