import unittest,tempfile,shutil,json
from pathlib import Path
from buy_side_bundle import build,replay
class BundleTests(unittest.TestCase):
 def setUp(self):
  from test_investment_intent import BridgeTests
  c=BridgeTests();c.setUp();self.s,self.p=c.s,c.p;self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.out=self.root/'bundle'
 def tearDown(self):self.temp.cleanup()
 def test_portable_replay(self):
  build(self.s,self.out,self.p);copy=self.root/'moved';shutil.copytree(self.out,copy);shutil.rmtree(self.out);self.assertEqual(replay(copy)['status'],'replayed-identical')
 def test_duplicate_manifest_fields_rejected(self):
  build(self.s,self.out,self.p);p=self.out/'manifest.json';text=p.read_text('utf-8')
  p.write_text(text.replace('{','{"version":0,',1),'utf-8')
  with self.assertRaises(ValueError):replay(self.out)
 def test_overflow_input_rejected(self):
  from buy_side_bundle import read_json
  p=self.root/'invalid.json';p.write_text('{"marketValue":1e999}','utf-8')
  with self.assertRaises(ValueError):read_json(p)
 def test_report_opens_with_constraint_judgment(self):
  r=build(self.s,self.out,self.p);text=(self.out/'研究包.md').read_text('utf-8')
  self.assertIn('存在未满足的约束',text);self.assertIn('当前最需要解释',text)
  for c in r['checks']:
   if c['status']=='fail':self.assertIn(c['detail'],text)
  self.assertIn(self.s['intent']['purpose'],text)
 def test_input_change_rejected(self):
  build(self.s,self.out,self.p);(self.out/'intent-input.json').write_text('{}','utf-8')
  with self.assertRaises(ValueError):replay(self.out)
 def test_missing_file_rejected(self):
  build(self.s,self.out,self.p);(self.out/'portfolio-input.json').unlink()
  with self.assertRaises(ValueError):replay(self.out)
 def test_method_change_rejected(self):
  build(self.s,self.out,self.p);p=self.out/'manifest.json';m=json.loads(p.read_text('utf-8'));m['methods']['portfolio_stress.py']='changed';p.write_text(json.dumps(m),'utf-8')
  with self.assertRaises(ValueError):replay(self.out)
 def test_path_escape_rejected(self):
  build(self.s,self.out,self.p);p=self.out/'manifest.json';m=json.loads(p.read_text('utf-8'));m['files']['../outside']='bad';p.write_text(json.dumps(m),'utf-8')
  with self.assertRaises(ValueError):replay(self.out)
 def test_no_overwrite(self):
  build(self.s,self.out,self.p)
  with self.assertRaises(FileExistsError):build(self.s,self.out,self.p)

 def thesis(self):
  from buy_side_thesis import freeze
  from pypdf import PdfWriter
  from buy_side_bundle import sha
  pdf=self.root/'original.pdf';w=PdfWriter();w.add_blank_page(width=200,height=200)
  with pdf.open('wb') as f:w.write(f)
  return freeze({'asOf':'2026-10-05','entityId':'fund:example','question':'验证','hypotheses':[{'id':'h','claim':'测试假设','invalidation':'条件变化','verificationMetric':'原文指标','reviewBy':'2026-11-05','evidence':[{'id':'e','kind':'original','source':'教学PDF','summary':'教学背景','stance':'context','publishedAt':'2026-10-01','acquiredAt':'2026-10-05','locator':{'path':str(pdf),'sha256':sha(pdf),'page':1}}]}]})
 def test_originals_move_and_preserve_snapshot(self):
  t=self.thesis();before=json.dumps(t,sort_keys=True);build(self.s,self.out,self.p,t,True);moved=self.root/'moved';shutil.copytree(self.out,moved);(self.root/'original.pdf').unlink();self.assertEqual(replay(moved)['status'],'replayed-identical');self.assertEqual(before,json.dumps(t,sort_keys=True))
 def test_original_mutation_rejected(self):
  build(self.s,self.out,self.p,self.thesis(),True);next((self.out/'sources').glob('*.pdf')).write_bytes(b'changed')
  with self.assertRaises(ValueError):replay(self.out)
 def test_original_mode_requires_thesis(self):
  with self.assertRaises(ValueError):build(self.s,self.out,self.p,include_originals=True)
 def test_missing_locator_is_explicit(self):
  t=self.thesis();del t['snapshot']['hypotheses'][0]['evidence'][0]['locator']
  from buy_side_thesis import digest
  t['snapshotSha256']=digest(t['snapshot']);build(self.s,self.out,self.p,t,True);self.assertIn('覆盖不完整',(self.out/'研究包.md').read_text('utf-8'));self.assertEqual(replay(self.out)['status'],'replayed-identical')
