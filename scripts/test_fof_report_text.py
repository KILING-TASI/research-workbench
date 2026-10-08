import unittest
from research_workflow import fof_review_markdown

class Tests(unittest.TestCase):
 def test_copy_retains_bytes_and_rejects_changed_source(self):
  import tempfile,hashlib
  from pathlib import Path
  from research_workflow import copy_fof_sources
  with tempfile.TemporaryDirectory() as d:
   base=Path(d);p=base/'original.pdf';p.write_bytes(b'%PDF-test')
   binding=dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
   rows=copy_fof_sources([binding],base/'delivery')
   self.assertEqual((base/'delivery'/rows[0]['relativePath']).read_bytes(),p.read_bytes())
   p.write_bytes(b'changed')
   with self.assertRaisesRegex(ValueError,'交付前已变化'):copy_fof_sources([binding],base/'other')
 def test_unknown_is_not_relabelled_or_renormalized(self):
  result=dict(knownWeight=.1,unknownWeight=.9,assetExposure=dict(stock=.1,bond=0,cash=0,other=0),unknown=[dict(path=['root','missing'],weight=.9,reason='子基金资料缺失')],limitations=[])
  spec=dict(root='root',asOf='2026-10-05',nodes={})
  text=fof_review_markdown(result,spec)
  for phrase in ['10.00%','90.00%','未知部分未当作现金','root → missing','子基金资料缺失','当前实时持仓']:self.assertIn(phrase,text)
  self.assertIn('|现金|0.0000%|',text)
 def test_full_input_still_requires_source_review(self):
  result=dict(knownWeight=1,unknownWeight=0,assetExposure=dict(stock=1,bond=0,cash=0,other=0),unknown=[],limitations=[])
  text=fof_review_markdown(result,dict(root='root',asOf='2026-10-05',nodes={}))
  self.assertIn('仍需核验资料完整性',text)
