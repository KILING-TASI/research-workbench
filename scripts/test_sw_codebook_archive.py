import unittest,tempfile
from pathlib import Path
from unittest.mock import patch,MagicMock
from sw_codebook_archive import extract,HEAD,fetch
class Tests(unittest.TestCase):
 def test_blank_new_side_not_old_name(self):
  entries,gaps=extract([[],HEAD,['旧','','',110000,'新','','',110000],['旧项','','',220301,None,None,None,'']],'sheet')
  self.assertEqual(entries[0]['name'],'新');self.assertEqual(gaps[0]['oldCode'],220301);self.assertEqual(len(entries),1)
 def test_existing_directory_no_network(self):
  with tempfile.TemporaryDirectory() as t,patch('sw_codebook_archive.public_download') as network:
   with self.assertRaises(FileExistsError):fetch(t)
   network.assert_not_called()
 def test_bad_workbook_keeps_download_for_review(self):
  response=MagicMock();response.__enter__.return_value=response;response.url='https://www.swsresearch.com/file.xlsx';response.read.return_value=b'PKnot-a-workbook'
  with tempfile.TemporaryDirectory() as t,patch('sw_codebook_archive.public_download',return_value={'raw':response.read.return_value,'resolvedUrl':response.url}):
   out=Path(t)/'new'
   with self.assertRaises(Exception):fetch(out)
   self.assertTrue((out/'original.xlsx').exists());self.assertTrue((out/'failure.json').exists());self.assertFalse((out/'result.json').exists())
 def test_duplicate_conflict(self):
  with self.assertRaisesRegex(ValueError,'冲突'):extract([[],HEAD,[None]*4+['A',None,None,110000],[None]*4+['B',None,None,110000]],'sheet')
 def test_duplicate_same_keeps_locators(self):
  row=[None]*4+['A',None,None,110000];entries,gaps=extract([[],HEAD,row,row],'sheet');self.assertEqual(len(entries[0]['locators']),2)
if __name__=='__main__':unittest.main()
