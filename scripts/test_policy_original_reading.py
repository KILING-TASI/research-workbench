import json,tempfile,unittest
from pathlib import Path
from policy_original_reading import parse,prepare,build,verified_archive
class Tests(unittest.TestCase):
 def test_english_effective_date_is_bound_to_explicit_wording(self):
  for phrase,accepted in [('Effective September 17, 2026, the rate changes.',True),('Published September 17, 2026; effective date unknown.',False)]:
   with tempfile.TemporaryDirectory() as d:
    b=Path(d);raw=b/'raw.html';raw.write_text('<div class="body"><p>'+phrase+'</p><p>'+('Scope still requires review. '*8)+'</p></div>',encoding='utf-8')
    prepare(dict(asOf='2026-10-06',sourceUrl='https://example.org',title='Policy',htmlPath=str(raw),contentClass='body'),b/'archive')
    spec=dict(archive=str(b/'archive/result.json'),scope=[dict(text='仅核对测试日期。',basis='policy-statement',evidence=[dict(paragraph=1,quote=phrase)])],clocks=[dict(text='原文明示日期。',basis='policy-statement',kind='effective-date',date='2026-09-17',evidence=[dict(paragraph=1,quote=phrase)])])
    if accepted:self.assertEqual(build(spec,b/'reading')['clocks'][0]['date'],'2026-09-17')
    else:
     with self.assertRaises(ValueError):build(spec,b/'reading')
 def source(self):return ('<html><p>导航不能引用</p><div class="time">发布时间：2025/02/09</div><div class="body"><p>2025年6月1日起投产的项目按给定政策条件处理。'+('原文条件不意味着收益保证。'*8)+'</p><script>任意伪造政策</script><p>地方实施范围仍需另行核对。</p></div></html>').encode()
 def setup_archive(self,base):
  p=base/'raw.html';p.write_bytes(self.source());return prepare(dict(asOf='2026-10-05',sourceUrl='https://example.org/policy',title='验收政策',htmlPath=str(p),contentClass='body',metadataClass='time'),base/'archive')
 def spec(self,base):return dict(archive=str(base/'archive/result.json'),scope=[dict(text='政策条件须核对。',basis='policy-statement',evidence=[dict(paragraph=1,quote='2025年6月1日起投产的项目按给定政策条件处理。')])],clocks=[dict(text='项目分界日，非全国生效日。',basis='policy-statement',kind='project-cutoff',date='2025-06-01',evidence=[dict(paragraph=1,quote='2025年6月1日起投产的项目')])])
 def test_scoped_paragraphs_exclude_navigation_and_script(self):
  rows,_=parse(self.source(),'utf-8','body');text=''.join(r['text'] for r in rows);self.assertNotIn('导航',text);self.assertNotIn('伪造',text);self.assertEqual(len(rows),2)
 def test_duplicate_container_rejected(self):
  with self.assertRaises(ValueError):parse(self.source()*2,'utf-8','body')
 def test_quote_and_date_verified_not_validity(self):
  with tempfile.TemporaryDirectory() as d:
   b=Path(d);self.setup_archive(b);r=build(self.spec(b),b/'reading');self.assertEqual(r['validityStatus'],'not-assessed');self.assertTrue(r['gaps']);self.assertEqual(r['clocks'][0]['kind'],'project-cutoff')
 def test_metadata_publication_separate_from_body(self):
  with tempfile.TemporaryDirectory() as d:
   b=Path(d);self.setup_archive(b);s=self.spec(b);s['clocks'].append(dict(text='网页公布日。',basis='policy-statement',kind='publication-date',date='2025-02-09',evidence=[dict(locatorType='metadata',paragraph=1,quote='发布时间：2025/02/09')]))
   self.assertEqual(build(s,b/'reading')['clocks'][1]['date'],'2025-02-09')
 def test_wrong_date_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   b=Path(d);self.setup_archive(b);s=self.spec(b);s['clocks'][0]['date']='2025-05-31'
   with self.assertRaises(ValueError):build(s,b/'reading')
   self.assertFalse((b/'reading').exists())
 def test_saved_paragraph_mutation_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   b=Path(d);a=self.setup_archive(b);a['paragraphs'][0]['text']='篡改的政策文字';(b/'archive/result.json').write_text(json.dumps(a))
   with self.assertRaises(ValueError):verified_archive(b/'archive/result.json')
 def test_raw_mutation_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   b=Path(d);a=self.setup_archive(b);Path(a['rawPath']).write_bytes(b'changed')
   with self.assertRaises(ValueError):build(self.spec(b),b/'reading')
 def test_effective_date_cannot_replace_project_cutoff(self):
  with tempfile.TemporaryDirectory() as d:
   b=Path(d);self.setup_archive(b);s=self.spec(b);s['clocks'][0]['kind']='effective-date'
   with self.assertRaises(ValueError):build(s,b/'reading')
 def test_explicit_effective_wording_allowed_without_validity_verdict(self):
  with tempfile.TemporaryDirectory() as d:
   b=Path(d);self.setup_archive(b);raw=b/'raw.html';raw.write_bytes(self.source().replace('2025年6月1日起投产的项目按给定政策条件处理。'.encode(),'本政策自2025年6月1日起施行。'.encode()))
   s=dict(asOf='2026-10-05',sourceUrl='https://example.org/policy',title='验收政策',htmlPath=str(raw),contentClass='body');prepare(s,b/'other-archive')
   spec=self.spec(b);spec['archive']=str(b/'other-archive/result.json');spec['scope']=[];spec['clocks'][0].update(kind='effective-date',text='原文明示施行时点。',evidence=[dict(paragraph=1,quote='本政策自2025年6月1日起施行。')])
   spec['risks']=[dict(text='文字仅为测试输入。',basis='research-explanation',evidence=[dict(paragraph=2,quote='地方实施范围仍需另行核对。')])]
   self.assertEqual(build(spec,b/'reading')['validityStatus'],'not-assessed')
 def test_table_not_silently_full_verified(self):
  rows,unsupported=parse(self.source().replace(b'</div></html>',b'<table><tr><td>100</td></tr></table></div></html>'),'utf-8','body');self.assertIn('table',unsupported)
 def test_missing_body_does_not_use_whole_page(self):
  with self.assertRaises(ValueError):parse(self.source(),'utf-8','unknown')

 def test_source_not_automatically_official(self):
  with tempfile.TemporaryDirectory() as d:
   b=Path(d);self.setup_archive(b);build(self.spec(b),b/'reading')
   text=(b/'reading/政策原文研究.md').read_text('utf-8');self.assertIn('查看来源网页',text);self.assertNotIn('查看官方网页',text)
 def test_credentials_missing_host_and_duplicate_json_rejected(self):
  from policy_original_reading import source_url,load_json
  for url in ['https://','https://user:password@example.org','https://example.org:bad','https://example.org/ bad']:
   with self.assertRaises(ValueError):source_url(url)
  for text in ['{"title":1,"title":2}','{"value":1e999}']:
   with self.assertRaises(ValueError):load_json(text)
