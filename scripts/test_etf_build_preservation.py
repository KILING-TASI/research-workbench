import importlib.util,json,tempfile,types,unittest,os
from pathlib import Path
from unittest.mock import patch

def builder():
 path=Path(__file__).resolve().parents[1]/'modules/etf-sector-rotation/scripts/build.py'
 spec=importlib.util.spec_from_file_location('etf_build_test',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

class BuildPreservation(unittest.TestCase):
 def test_success_uses_new_tracking_data_in_prepared_ui(self):
  m=builder()
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory)/'etf';assets=root/'assets';assets.mkdir(parents=True)
   resources={'ui.js':'const ETFMarketSnapshot={};','market-data.json':'{"old":true}','data.json':'{}','style.css':'style','panel.html':'panel','engine.js':'engine','standalone.template.html':'/*ETF_STYLE*/ <!--ETF_PANEL--> /*ETF_ENGINE*/ /*ETF_UI*/ /*ETF_SNAPSHOT*/'}
   for name,text in resources.items():(assets/name).write_text(text,encoding='utf-8')
   with patch.object(m,'ROOT',root),patch.dict('sys.modules',{'build_market_tracking':types.SimpleNamespace(build=lambda write:{'new':True})}):text=m.build()
   self.assertIn('"new": true',text);self.assertNotIn('"old":true',text);self.assertEqual(text,(assets/'workbench.html').read_text(encoding='utf-8'));self.assertEqual(json.loads((assets/'market-data.json').read_text(encoding='utf-8')),{'new':True})
 def test_preparation_failure_keeps_ui_tracking_and_page(self):
  m=builder()
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory)/'etf';assets=root/'assets';assets.mkdir(parents=True)
   for name,text in [('ui.js','const ETFMarketSnapshot={};'),('market-data.json','{"old":true}'),('workbench.html','old page'),('data.json','{}')]: (assets/name).write_text(text,encoding='utf-8')
   before={p.name:p.read_bytes() for p in assets.iterdir()}
   with patch.object(m,'ROOT',root),patch.dict('sys.modules',{'build_market_tracking':types.SimpleNamespace(build=lambda write:{'new':True})}),self.assertRaises(FileNotFoundError):m.build()
   self.assertEqual(before,{p.name:p.read_bytes() for p in assets.iterdir()})
 def test_commit_failure_restores_already_replaced_files(self):
  m=builder()
  with tempfile.TemporaryDirectory() as directory:
   a=Path(directory)/'a';b=Path(directory)/'b';a.write_bytes(b'old-a');b.write_bytes(b'old-b');original=os.replace;calls=0
   def replace(source,target):
    nonlocal calls
    calls+=1
    if calls==2:raise OSError('controlled write failure')
    return original(source,target)
   with patch.object(m.os,'replace',side_effect=replace),self.assertRaises(OSError):m.publish({a:'new-a',b:'new-b'})
   self.assertEqual(a.read_bytes(),b'old-a');self.assertEqual(b.read_bytes(),b'old-b');self.assertEqual({p.name for p in Path(directory).iterdir()},{'a','b'})

if __name__=='__main__':unittest.main()
