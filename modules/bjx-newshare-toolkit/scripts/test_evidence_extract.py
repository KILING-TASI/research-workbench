import unittest
from extract_issuance_evidence import candidates, supplement_ocr
class Extraction(unittest.TestCase):
 def test_conflicts_not_selected(self):
  r=candidates(['发行价格为10元/股。','发行价格为11元/股。'],['price'])
  self.assertEqual(r['price']['status'],'conflicting-candidates')
 def test_units_and_missing(self):
  r=candidates(['申购上限为12.3万股。'],['maxShares','price'])
  self.assertEqual(r['maxShares']['candidates'][0]['value'],'123000.0')
  self.assertEqual(r['price']['status'],'missing-or-layout-unsupported')
 def test_ocr_hash_bound_and_cannot_override_embedded_text(self):
  sidecar={'sourceSha256':'original','engine':'external OCR','pages':[{'page':1,'text':'发行价格为99元/股'},{'page':2,'text':'网上获配比例为0.1%'}]}
  pages,used=supplement_ocr(['发行价格为10元/股',''],sidecar,'original')
  self.assertEqual(pages[0],'发行价格为10元/股');self.assertEqual(used,[2])
  with self.assertRaises(ValueError):supplement_ocr(['',''],sidecar,'wrong')
 def test_invalid_ocr_page_rejected(self):
  for pages in [[{'page':2,'text':'x'}],[{'page':1,'text':'x'},{'page':1,'text':'y'}],[{'page':True,'text':'x'}]]:
   with self.assertRaises(ValueError):supplement_ocr([''],{'sourceSha256':'h','engine':'external','pages':pages},'h')
if __name__=='__main__':unittest.main()
