import unittest,tempfile,logging
from pathlib import Path
from unittest.mock import patch
from pdf_structure_review import review
class Tests(unittest.TestCase):
 def reader(self):
  class Reader:pages=[object()]
  return Reader()
 def test_silent_reader_does_not_hide_trailing_fragment(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'report.pdf';p.write_bytes(b'%PDF-1.7\n%%EOF\ntrailer unfinished')
   with patch('pdf_structure_review.PdfReader',return_value=self.reader()):r=review(p)
   self.assertTrue(r['reviewRequired']);self.assertGreater(r['nonWhitespaceBytesAfterLastEOF'],0);self.assertEqual(r['warnings'],[])
 def test_whitespace_after_eof_not_extra_fragment(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'report.pdf';p.write_bytes(b'%PDF-1.7\n%%EOF\r\n   ')
   with patch('pdf_structure_review.PdfReader',return_value=self.reader()):r=review(p)
   self.assertFalse(r['reviewRequired']);self.assertEqual(r['nonWhitespaceBytesAfterLastEOF'],0)
 def test_reader_warning_captured(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'report.pdf';p.write_bytes(b'%PDF-1.7\n%%EOF')
   def read(*args,**kwargs):logging.getLogger('pypdf').warning('test structural warning');return self.reader()
   with patch('pdf_structure_review.PdfReader',side_effect=read):r=review(p)
   self.assertTrue(r['reviewRequired']);self.assertEqual(r['warnings'],['test structural warning'])
 def test_structure_failure_remains_review_required(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'report.pdf';p.write_bytes(b'%PDF-1.7\n%%EOF')
   with patch('pdf_structure_review.PdfReader',side_effect=ValueError('invalid xref')):r=review(p)
   self.assertTrue(r['reviewRequired']);self.assertEqual(r['strictStructureRead'],'failed')
if __name__=='__main__':unittest.main()
