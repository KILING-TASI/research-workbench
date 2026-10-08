import unittest,subprocess,sys,tempfile,json
from pathlib import Path
from research_topics import resolve,ROOT
class Tests(unittest.TestCase):
 def test_unknown_action_rejected(self):
  with self.assertRaises(ValueError):resolve('macro','build')
  with self.assertRaises(ValueError):resolve('../macro','standalone')
 def test_routes_are_local(self):
  from research_topics import ROUTES
  for t,(_,actions) in ROUTES.items():
   for a in actions:self.assertTrue(resolve(t,a).is_relative_to(ROOT/'modules'))
 def test_macro_initializes_without_author_cache(self):
  with tempfile.TemporaryDirectory() as d:
   p=subprocess.run([sys.executable,str(ROOT/'scripts/research_topics.py'),'macro','standalone','--','--data-dir',d],capture_output=True,text=True,encoding='utf-8')
   self.assertEqual(p.returncode,0,p.stderr)
   rows=json.loads((Path(d)/'data.json').read_text(encoding='utf-8'))['indicators'];self.assertTrue(rows)
   self.assertTrue(all(row['value'] is None and row['history']==[] for row in rows))
 def test_bjx_empty_evidence_stays_unknown(self):
  with tempfile.TemporaryDirectory() as d:
   src=ROOT/'modules/bjx-newshare-toolkit/assets/example-panel-input.json';out=Path(d)/'panel.json'
   p=subprocess.run([sys.executable,str(ROOT/'scripts/research_topics.py'),'bjx','research','--','panel',str(src),'--out',str(out)],capture_output=True,text=True,encoding='utf-8')
   self.assertEqual(p.returncode,0,p.stderr)
   data=json.loads(out.read_text(encoding='utf-8'));self.assertEqual(data['quality']['missingCount'],3)
 def test_copied_package_runs_away_from_project(self):
  import shutil
  with tempfile.TemporaryDirectory() as d:
   package=Path(d)/'package';(package/'scripts').mkdir(parents=True)
   shutil.copy2(ROOT/'scripts/research_topics.py',package/'scripts/research_topics.py')
   shutil.copytree(ROOT/'modules/macro-indicator',package/'modules/macro-indicator',ignore=shutil.ignore_patterns('__pycache__'))
   p=subprocess.run([sys.executable,str(package/'scripts/research_topics.py'),'macro','standalone','--','--data-dir','user-cache'],cwd=d,capture_output=True,text=True,encoding='utf-8')
   self.assertEqual(p.returncode,0,p.stderr);self.assertTrue((Path(d)/'user-cache/data.json').is_file())
if __name__=='__main__':unittest.main()
