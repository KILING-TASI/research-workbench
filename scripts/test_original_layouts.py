import unittest
from unittest.mock import patch
from original_layouts import check_field,number,ocr_page

class Page:
    def __init__(self,tables):self.tables=tables
    def extract_tables(self,*args):return self.tables
    def extract_text(self):return '2025年度 单位：万元 合并利润表'
    def crop(self,box,strict=True):return self

class LayoutTests(unittest.TestCase):
    def test_v2_credentials_and_dates_rejected_before_file(self):
        from original_layouts import verify_v2
        spec=dict(documentPath='missing.pdf',sourceUrl='https://example.org/a',trustedPublisherHosts=['example.org'],sha256='hash',title='报告',issuer='公司',publishedAt='2026-08-31',asOf='2026-10-06',publicationExcerpt='2026年8月31日',fields=[{}])
        for key,value in [('sourceUrl','https://user:password@example.org/a'),('publishedAt','20260831'),('reportDate','')]:
            with patch('original_layouts.Path.read_bytes') as read:
                with self.assertRaises(ValueError):verify_v2(dict(spec,**{key:value}))
                read.assert_not_called()
    def field(self,**kw):return dict(id='revenue',page=1,label='营业收入',column=1,columnHeader='本期',unitText='单位：万元',periodText='2025年度',value='100',**kw)
    def test_conflict_before_value(self):
        p=Page([[['项目','本期'],['营业收入','100']],[['项目','本期'],['营业收入','200']]])
        r=check_field(self.field(),p,p.extract_text(),False)
        self.assertEqual(r['status'],'ambiguous');self.assertEqual(len(r['candidates']),2)
        self.assertEqual(check_field(self.field(tableIndex=0),p,p.extract_text(),False)['status'],'matched')
    def test_wrong_header_and_unit(self):
        p=Page([[['项目','上期'],['营业收入','100']]])
        self.assertEqual(check_field(self.field(),p,p.extract_text(),False)['status'],'context-mismatch')
        p.tables[0][0][1]='本期'
        self.assertEqual(check_field(self.field(),p,'2025年度 单位：元',False)['status'],'context-mismatch')
    def test_negative_and_blank(self):
        self.assertEqual(number('(1,234.50)'),-1234.50)
        p=Page([[['项目','本期'],['营业收入','—']]])
        self.assertEqual(check_field(self.field(),p,p.extract_text(),False)['status'],'reported-empty')
    def test_announcement_excerpt_and_ocr(self):
        f={'id':'event','page':1,'mode':'text','label':'董事会','excerpt':'董事会审议通过回购方案'}
        p=Page([])
        self.assertEqual(check_field(f,p,f['excerpt'],False)['status'],'matched')
        self.assertEqual(check_field(f,p,f['excerpt'],True)['status'],'needs-review')
        self.assertEqual(check_field(f,p,f['excerpt']*2,False)['status'],'ambiguous')
    def test_ocr_removed(self):
        with self.assertRaisesRegex(RuntimeError,'已移除'):ocr_page('unused',1,{'executable':'untrusted'})
    def test_ocr_table_never_passes(self):
        p=Page([])
        self.assertEqual(check_field(self.field(),p,'100',True)['status'],'needs-review')
    def test_missing_negative_sign(self):
        p=Page([[['项目','本期'],['营业收入','-100']]])
        self.assertEqual(check_field(self.field(),p,p.extract_text(),False)['status'],'mismatch')

if __name__=='__main__':unittest.main()
