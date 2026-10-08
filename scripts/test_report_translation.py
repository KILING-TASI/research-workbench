import unittest
from report_translation import translated_page
class Tests(unittest.TestCase):
 def entry(self,source,translation):return {'page':1,'blocks':[{'sourceText':source,'translation':translation}]}
 def test_all_source_text_required(self):
  with self.assertRaisesRegex(ValueError,'完整覆盖'):translated_page(self.entry('Rate 3.5','利率3.5'),'Rate 3.5. Effective tomorrow.')
 def test_number_changes_warn_not_verified(self):
  r=translated_page(self.entry('Rate 3.5','利率3.6'),'Rate 3.5')
  self.assertTrue(r['numericWarnings']);self.assertEqual(r['semanticVerification'],'not-independently-verified')
 def test_numbers_match_not_semantic_proof(self):
  r=translated_page(self.entry('Rate 3.5','利率3.5'),'Rate 3.5')
  self.assertEqual(r['numericWarnings'],[]);self.assertEqual(r['semanticVerification'],'not-independently-verified')
 def test_cannot_self_declare_verified(self):
  e=self.entry('Rate 3.5','利率3.5');e['verified']=True
  with self.assertRaises(ValueError):translated_page(e,'Rate 3.5')

class NumericContextTests(unittest.TestCase):
 def check(self,source,translation):
  return translated_page({'page':1,'blocks':[{'sourceText':source,'translation':translation}]},source)['numericWarnings']
 def test_negative_sign_change_warns(self):self.assertTrue(self.check('Return -2%','收益2%'))
 def test_percent_removed_warns(self):self.assertTrue(self.check('Rate 3.5 percent','利率3.5'))
 def test_magnitude_change_warns(self):self.assertTrue(self.check('Amount 160 billion','金额160 million'))
 def test_percent_word_and_symbol_are_equivalent(self):self.assertEqual(self.check('Rate 3.5 percent','利率3.5%'),[])
 def test_unicode_negative_sign_is_equivalent(self):self.assertEqual(self.check('Return −2%','收益-2%'),[])

class DeliveryTests(unittest.TestCase):
 def test_low_text_recomputed_not_declared(self):
  import tempfile,json,hashlib
  from pathlib import Path
  from unittest.mock import patch
  from report_translation import build
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);pdf=root/'p.pdf';pdf.write_bytes(b'original');archive=root/'a.json';archive.write_text(json.dumps(dict(asOf='2026-09-30',reports=[dict(id='a',status='readable',pdfPath=str(pdf),sha256=hashlib.sha256(pdf.read_bytes()).hexdigest(),pages=[dict(page=1,text='Rate 3.5')],lowTextPages=[])])),encoding='utf8')
   with patch('report_translation.verify_pdf_pages',return_value='pdf-reparsed-pages-matched'):
    r=build(dict(archive=str(archive),reportId='a',pages=[dict(page=1,blocks=[dict(sourceText='Rate 3.5',translation='利率3.5')])]),root/'out')
   self.assertEqual(r['lowTextPages'],[1]);self.assertEqual(r['coverage'],'partial-or-low-text');self.assertEqual((root/'out/sources/original.pdf').read_bytes(),b'original')
