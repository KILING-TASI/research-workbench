import unittest,tempfile,sys,datetime
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
from sw_classification_archive import parse,fetch
class Sheet:
 name='Sheet1';nrows=3
 def row_values(self,i):return [['股票代码','计入日期','行业代码','更新日期'],['000001',1,'480301',2],['000001',3,'480101',4]][i]
 def cell_type(self,i,j):return 3
class Tests(unittest.TestCase):
 def fake(self,sheet=None):return SimpleNamespace(XL_CELL_DATE=3,open_workbook=lambda **kw:SimpleNamespace(datemode=0,sheets=lambda:[sheet or Sheet()]),xldate_as_datetime=lambda x,mode:datetime.datetime(2025 if x<3 else 2027,1,1))
 def test_versions_future_and_locator(self):
  with tempfile.TemporaryDirectory() as t,patch.dict(sys.modules,{'xlrd':self.fake()}):
   p=Path(t)/'data.xls';p.write_bytes(b'test');r=parse(p,'2026-10-03')
   self.assertEqual(len(r['rows']),1);self.assertEqual(len(r['excludedAfterCutoff']),1);self.assertEqual(r['rows'][0]['locator']['row'],2);self.assertIsNone(r['rows'][0]['effectiveTo'])
 def test_missing_dependency_explained(self):
  with patch.dict(sys.modules,{'xlrd':None}),self.assertRaisesRegex(RuntimeError,'xlrd'):parse('missing.xls','2026-10-03')
 def test_invalid_date_and_existing_archive_do_not_download(self):
  with tempfile.TemporaryDirectory() as t,patch('sw_classification_archive.public_download') as network:
   with self.assertRaises(ValueError):fetch('bad',t+'/new')
   with self.assertRaises(FileExistsError):fetch('2026-10-03',t)
   network.assert_not_called()
 def test_html_response_rejected_before_archive(self):
  from unittest.mock import MagicMock
  response=MagicMock();response.__enter__.return_value=response;response.url='https://www.swsresearch.com/file.xls';response.read.return_value=b'<html>error</html>'
  with tempfile.TemporaryDirectory() as t,patch('sw_classification_archive.public_download',return_value={'raw':response.read.return_value,'resolvedUrl':response.url}):
   out=Path(t)/'new'
   with self.assertRaisesRegex(ValueError,'Excel'):fetch('2026-10-03',out)
   self.assertFalse(out.exists())
 def test_changed_header_rejected(self):
  sheet=Sheet();sheet.row_values=lambda i:['错误表头']
  with tempfile.TemporaryDirectory() as t,patch.dict(sys.modules,{'xlrd':self.fake(sheet)}):
   p=Path(t)/'data.xls';p.write_bytes(b'test')
   with self.assertRaisesRegex(ValueError,'标题'):parse(p,'2026-10-03')
 def test_redirect_cannot_leave_official_domain(self):
  from public_download import PublicRedirect,check_host
  check_host('https://www.swsresearch.com/file',{'www.swsresearch.com'})
  with self.assertRaisesRegex(ValueError,'允许范围'):PublicRedirect({'www.swsresearch.com'}).redirect_request(None,None,302,'',{},'https://example.org/file')
if __name__=='__main__':unittest.main()
