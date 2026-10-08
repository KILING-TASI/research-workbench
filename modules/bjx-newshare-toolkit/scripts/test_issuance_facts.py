import unittest,tempfile,json
from pathlib import Path
from unittest.mock import patch
from issuance_facts import register,view
class Page:
    def extract_text(self):return '发行人股份有限公司 920022 发行公告 2025年9月5日 发行价格为10.90元/股 其他价格为11.00元/股'
class PDF:
    pages=[Page()]
    def __enter__(self):return self
    def __exit__(self,*a):pass
class Facts(unittest.TestCase):
    def setup_spec(self,folder):
        p=Path(folder)/'test.pdf';p.write_bytes(b'%PDF-test')
        return {'code':'920022','issuer':'发行人股份有限公司','title':'发行公告','publishedAt':'2025-09-05','asOf':'2025-09-09','sourceUrl':'https://www.bse.cn/test.pdf','documentPath':str(p),'publicationPage':1,'publicationExcerpt':'2025年9月5日','fields':[{'field':'price','value':'10.90','originalUnit':'元/股','page':1,'label':'发行价格','excerpt':'发行价格为10.90元/股','basis':'发行价'}]}
    def test_version_and_asof(self):
        with tempfile.TemporaryDirectory() as f,patch('pdfplumber.open',return_value=PDF()):
            s=self.setup_spec(f);a=register(s,f);b=register(s,f);self.assertTrue(b['duplicate'])
            self.assertIsNone(view({'code':'920022','asOf':'2025-09-04'},f)['facts']['price'])
            s['fields'][0]['basis']='冲突口径';register(s,f)
            self.assertIsNone(view({'code':'920022','asOf':'2025-09-09'},f)['facts']['price'])
            s['supersedes']=a['versionHash'];register(s,f)
            self.assertIsNotNone(view({'code':'920022','asOf':'2025-09-09'},f)['facts']['price'])
    def test_ambiguous_values(self):
        with tempfile.TemporaryDirectory() as f,patch('pdfplumber.open',return_value=PDF()):
            s=self.setup_spec(f);s['fields'][0]['excerpt']='发行价格为10.90元/股 其他价格为11.00元/股'
            with self.assertRaises(ValueError):register(s,f)
    def test_wrong_value(self):
        with tempfile.TemporaryDirectory() as f,patch('pdfplumber.open',return_value=PDF()):
            s=self.setup_spec(f);s['fields'][0]['value']='12'
            with self.assertRaises(ValueError):register(s,f)
    def test_signed_exponent_and_malformed_grouping_not_reinterpreted(self):
        for token,value in [('-10.90','10.90'),('−10.90','10.90'),('1e1','1'),('10,90','1090')]:
            with self.subTest(token=token),tempfile.TemporaryDirectory() as f:
                s=self.setup_spec(f);excerpt='发行价格为'+token+'元/股'
                s['fields'][0].update(value=value,excerpt=excerpt)
                with patch.object(Page,'extract_text',return_value='发行人股份有限公司 920022 发行公告 2025年9月5日 '+excerpt),patch('pdfplumber.open',return_value=PDF()):
                    with self.assertRaises(ValueError):register(s,f)
                self.assertFalse((Path(f)/'research-data').exists())
    def test_valid_thousands_grouping_preserved(self):
        with tempfile.TemporaryDirectory() as f:
            s=self.setup_spec(f);excerpt='发行价格为1,090.00元/股';s['fields'][0].update(value='1090.00',excerpt=excerpt)
            with patch.object(Page,'extract_text',return_value='发行人股份有限公司 920022 发行公告 2025年9月5日 '+excerpt),patch('pdfplumber.open',return_value=PDF()):
                result=register(s,f)
            self.assertEqual(result['facts']['price']['value'],'1090.00')
    def test_wrong_identity(self):
        with tempfile.TemporaryDirectory() as f,patch('pdfplumber.open',return_value=PDF()):
            s=self.setup_spec(f);s['code']='920111'
            with self.assertRaises(ValueError):register(s,f)
    def test_future_disclosure(self):
        with tempfile.TemporaryDirectory() as f:
            s=self.setup_spec(f);s['asOf']='2025-09-04'
            with self.assertRaises(ValueError):register(s,f)
    def test_archive_tampering(self):
        with tempfile.TemporaryDirectory() as f,patch('pdfplumber.open',return_value=PDF()):
            a=register(self.setup_spec(f),f);Path(a['documentPath']).write_bytes(b'%PDF-changed')
            with self.assertRaises(ValueError):view({'code':'920022','asOf':'2025-09-09'},f)
if __name__=='__main__':unittest.main()
