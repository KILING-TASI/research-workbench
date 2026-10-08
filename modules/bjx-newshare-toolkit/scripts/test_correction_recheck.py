import hashlib, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from recheck_correction_notices import check

class CorrectionCheckTests(unittest.TestCase):
    def test_empty_excerpts_and_boolean_page_cannot_pass(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/'a.pdf';f.write_bytes(b'test')
            base={'sha256':hashlib.sha256(b'test').hexdigest(),'issuerName':'company','documentCode':'920001'}
            with patch('recheck_correction_notices.PdfReader') as reader:
                page=reader.return_value.pages[0];page.extract_text.return_value='company 920001 changed';reader.return_value.pages=[page]
                for excerpts in [[],[{'page':True,'text':'changed'}]]:
                    with self.subTest(excerpts=excerpts),self.assertRaises(ValueError):check({**base,'excerpts':excerpts},f)
    def test_hash_and_wrong_page_fail(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/'a.pdf';f.write_bytes(b'test')
            e={'sha256':'wrong'}
            with self.assertRaisesRegex(ValueError,'hash'):check(e,f)
            e.update(sha256=hashlib.sha256(b'test').hexdigest(),issuerName='company',documentCode='920001',excerpts=[{'page':2,'text':'changed'}])
            with patch('recheck_correction_notices.PdfReader') as reader:
                reader.return_value.pages[0].extract_text.return_value='company 920001 changed'
                reader.return_value.pages=[reader.return_value.pages[0]]
                with self.assertRaisesRegex(ValueError,'page'):check(e,f)

if __name__=='__main__':unittest.main()
