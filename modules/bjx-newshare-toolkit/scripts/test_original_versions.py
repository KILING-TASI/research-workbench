import unittest
from compare_original_versions import compare,difference_hint,extract
from unittest.mock import patch,Mock

class OriginalVersionTests(unittest.TestCase):
    def test_changed_numbers_and_insertions_located(self):
        def doc(lines):return {'sha256':'test','pageCount':2,'lines':[{'page':p,'text':s,'normalized':s} for p,s in lines]}
        r=compare(doc([(1,'same'),(2,'27,867,250')]),doc([(1,'same'),(2,'29,817,250'),(2,'new')]))
        self.assertEqual(len(r['changes']),1)
        self.assertEqual(r['changes'][0]['before'][0]['page'],2)
        self.assertEqual(r['changes'][0]['after'][0]['text'],'29,817,250')
        self.assertFalse(r['semanticReviewComplete'])

    def test_wrap_hint_retains_percent_and_numbers(self):
        def lines(*values):return [{'normalized':v,'page':1,'text':v} for v in values]
        self.assertIn('only',difference_hint({'before':lines('original','text','1-1-20'),'after':lines('originaltext','1-1-21')}))
        for old,new in [('22.61','22.61%'),('130.60','0.00'),('1-2-20','1-2-21')]:
            self.assertEqual(difference_hint({'before':lines(old),'after':lines(new)}),'content-difference-needs-review')

    def test_code_substring_not_identity(self):
        with patch('compare_original_versions.PdfReader') as reader:
            page=Mock();page.extract_text.return_value='Company code 9200019'
            reader.return_value.pages=[page]
            with self.assertRaisesRegex(ValueError,'identity'):extract(None,'Company','920001')

if __name__=='__main__':unittest.main()
