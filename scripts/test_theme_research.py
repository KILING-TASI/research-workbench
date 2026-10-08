import unittest,tempfile,json
from pathlib import Path
from theme_research import run
class Tests(unittest.TestCase):
 def spec(self):return dict(terms=['科技'],start='2023-01-01',end='2025-12-31',asOf='2026-10-03',conditions=[dict(kind="metric",field="returnPct",op="gt",value=0)],maxCandidates=2)
 def raw(self):return 'var r = [["000001","X","科技A","股票"],["000002","X","科技C","股票"]];'
 def mock(self,s,d,resume=False):Path(d).mkdir(exist_ok=True);return dict(selected=[],excluded=[],unknown=[dict(code=x) for x in s['codes']])
 def test_pipeline_freezes(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'new';r=run(self.spec(),p,catalog_fetch=self.raw,batch_runner=self.mock);self.assertEqual(len(r['result']['unknown']),2)
   run(self.spec(),p,True,catalog_fetch=lambda:(_ for _ in ()).throw(Exception()),batch_runner=self.mock)
 def test_cap_no_silent_selection(self):
  s=self.spec();s['maxCandidates']=1
  with tempfile.TemporaryDirectory() as t:
   with self.assertRaises(ValueError):run(s,Path(t)/'n',catalog_fetch=self.raw,batch_runner=self.mock)
 def test_changed_params(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'n';run(self.spec(),p,catalog_fetch=self.raw,batch_runner=self.mock);s=self.spec();s['end']='2025-12-30'
   with self.assertRaises(ValueError):run(s,p,True,batch_runner=self.mock)
 def test_tampered_catalog(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'n';run(self.spec(),p,catalog_fetch=self.raw,batch_runner=self.mock);(p/'catalog.js').write_text('changed')
   with self.assertRaises(ValueError):run(self.spec(),p,True,batch_runner=self.mock)
if __name__=='__main__':unittest.main()
