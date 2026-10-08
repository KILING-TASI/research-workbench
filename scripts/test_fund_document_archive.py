import tempfile,unittest
from pathlib import Path
from fund_document_archive import run,identity
class Tests(unittest.TestCase):
 def test_catalog_candidates_alias_and_conflict(self):
  s=self.spec();s['candidates']=s.pop('rows')
  with tempfile.TemporaryDirectory() as t:
   r=run(s,'a',Path(t)/'archive',resolve_fn=lambda _:dict(sourceUrl='https://example.org/x.pdf'),download_fn=lambda _:b'%PDFtest',pages_fn=lambda _:[(1,'某基金招募说明书 110022')]);self.assertTrue(r['identity']['matched'])
  s['rows']=[]
  with tempfile.TemporaryDirectory() as t,self.assertRaises(ValueError):run(s,'a',Path(t)/'archive')
 def test_amendment_not_generic_fee(self):
  s=self.spec();s['amendmentClues']=[dict(id='b',title='费率调整公告',publishedAt='2026-01-01')]
  with tempfile.TemporaryDirectory() as t:
   r=run(s,'b',Path(t)/'archive',resolve_fn=lambda _:dict(sourceUrl='https://example.org/x.pdf'),download_fn=lambda _:b'%PDFtest',pages_fn=lambda _:[(1,'费率调整公告 110022 管理费1.2%')]);self.assertEqual(r['catalogItemKind'],'amendment-clue');self.assertIsNone(r['reportFees'])
  s['amendmentClues']=[s['rows'][0]]
  with tempfile.TemporaryDirectory() as t,self.assertRaises(ValueError):run(s,'a',Path(t)/'archive')
 def spec(self):return dict(code='110022',asOf='2026-10-03',rows=[dict(id='a',title='某基金招募说明书',publishedAt='2026-01-01')])
 def test_identity(self):self.assertTrue(identity([(1,'某基金招募说明书'),(2,'基金代码110022')],'110022','某基金招募说明书')['matched'])
 def test_wrong_code(self):self.assertFalse(identity([(1,'某基金招募说明书 000001')],'110022','某基金招募说明书')['matched'])
 def test_failed_identity_preserves_pdf(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'out';r=run(self.spec(),'a',p,lambda x:dict(sourceUrl='https://example.org/a'),lambda u:b'%PDF-test',lambda p:[(1,'其他文档')])
   self.assertTrue((p/'document.pdf').exists());self.assertIsNone(r['reportFees']);self.assertFalse(r['effectiveVersionVerified'])
 def test_download_failure_report(self):
  def fail(u):raise TimeoutError('超时')
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'out';r=run(self.spec(),'a',p,lambda x:dict(sourceUrl='https://example.org/a'),fail);self.assertTrue(r['gaps']);self.assertTrue((p/'result.json').exists())
 def test_identity_cannot_use_blank_title_or_bad_pages(self):
  for pages,title in [([(1,'110022')],' '),([(0,'某基金110022')],'某基金'),([(1,'某基金110022'),(1,'重复')],'某基金')]:
   with self.assertRaises(ValueError):identity(pages,'110022',title)
 def test_catalog_blank_title_rejected_before_directory(self):
  with tempfile.TemporaryDirectory() as t:
   s=self.spec();s['rows'][0]['title']=' ';out=Path(t)/'out'
   with self.assertRaisesRegex(ValueError,'目录条目'):run(s,'a',out)
   self.assertFalse(out.exists())
 def test_empty_text_pages_remain_gap_after_identity_match(self):
  with tempfile.TemporaryDirectory() as t:
   out=Path(t)/'out';r=run(self.spec(),'a',out,resolve_fn=lambda _:dict(sourceUrl='https://example.org/x.pdf'),download_fn=lambda _:b'%PDFtest',pages_fn=lambda _:[(1,'某基金招募说明书 110022'),(2,'')])
   self.assertTrue(r['identity']['matched']);self.assertEqual(r['textExtractionSummary']['emptyTextPages'],[2]);self.assertTrue(any('不据此认定缺页' in x for x in r['gaps']));self.assertIn('取得文本1/2页',(out/'原文资料.md').read_text('utf-8'))
if __name__=='__main__':unittest.main()
