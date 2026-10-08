import unittest,tempfile
from pathlib import Path
from fund_document_archive import catalog_from_bundle,run
class AnnouncementArchiveBridge(unittest.TestCase):
 def bundle(self):return {'asOf':'2026-09-30','rows':[{'code':'159869','kind':'etf','announcements':[{'id':'a','date':'2026-08-30','title':'基金中期报告','provenance':'third-party-fund-catalog'}]}]}
 def test_bridge_identity_only_and_page_report(self):
  catalog=catalog_from_bundle(self.bundle(),'159869')
  with tempfile.TemporaryDirectory() as root:
   p=Path(root)/'archive';result=run(catalog,'a',p,resolve_fn=lambda _:dict(sourceUrl='https://example.org/a.pdf'),download_fn=lambda _:b'%PDFsample',pages_fn=lambda _:[(1,'基金中期报告'),(3,'基金代码159869')])
   self.assertEqual(result['catalogItemKind'],'catalog-announcement');self.assertTrue(result['identity']['matched']);self.assertIsNone(result['reportFees']);self.assertIn('物理页：3',(p/'原文资料.md').read_text('utf-8'))
 def test_stock_cannot_be_converted(self):
  b=self.bundle();b['rows'][0]['kind']='stock'
  with self.assertRaisesRegex(ValueError,'基金或ETF'):catalog_from_bundle(b,'159869')
 def test_wrong_source_cannot_be_converted(self):
  b=self.bundle();b['rows'][0]['announcements'][0].pop('provenance')
  with self.assertRaisesRegex(ValueError,'来源类型'):catalog_from_bundle(b,'159869')
 def test_missing_catalog_does_not_download(self):
  b=self.bundle();b['rows'][0]['announcements']=[]
  with self.assertRaisesRegex(ValueError,'未取得'):catalog_from_bundle(b,'159869')
