import unittest,tempfile,json
from pathlib import Path
from unittest.mock import patch
from refresh import refresh,save_json
from observation_brief import brief
from types import SimpleNamespace
class BuildPreparation(unittest.TestCase):
 def test_write_failure_restores_prior_outputs_and_cleans_temps(self):
  import build
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);first=root/'first.html';second=root/'second.json';first.write_bytes(b'old first');second.write_bytes(b'old second')
   replace=build.os.replace;calls=[]
   def fail_second(source,target):
    calls.append(target)
    if len(calls)==2:raise OSError('teaching write interruption')
    return replace(source,target)
   with patch.object(build.os,'replace',side_effect=fail_second):
    with self.assertRaises(OSError):build.publish({first:'new first',second:'new second'})
   self.assertEqual(first.read_bytes(),b'old first');self.assertEqual(second.read_bytes(),b'old second')
   self.assertEqual(sorted(p.name for p in root.iterdir()),['first.html','second.json'])
 def setup_assets(self,root):
  assets=root/'macro-indicator/assets';assets.mkdir(parents=True)
  for name,value in {'data.json':'{}','model-config.json':'{}','education.json':'{}','style.css':'style','panel.html':'panel','engine.js':'engine','ui.js':'ui','standalone.template.html':'/*MACRO_SNAPSHOT*/','workbench.html':'existing page'}.items():
   (assets/name).write_text(value,encoding='utf-8')
  return assets
 def test_missing_platform_resource_does_not_update_standalone(self):
  import build
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);assets=self.setup_assets(root);(root/'bjx-newshare-toolkit/assets').mkdir(parents=True)
   with patch.object(build,'ROOT',assets.parent),patch.dict('sys.modules',{'etf_embed':SimpleNamespace(embed=lambda page,assets:page)}):
    with self.assertRaises(FileNotFoundError):build.build()
   self.assertEqual((assets/'workbench.html').read_text(encoding='utf-8'),'existing page')
   self.assertFalse((root/'bjx-newshare-toolkit/assets/macro-data.json').exists())
 def test_standalone_build_without_platform(self):
  import build
  with tempfile.TemporaryDirectory() as directory:
   assets=self.setup_assets(Path(directory))
   with patch.object(build,'ROOT',assets.parent):build.build()
   self.assertEqual((assets/'workbench.html').read_text(encoding='utf-8'),'{}')
class RefreshRequest(unittest.TestCase):
 def handler(self):
  import serve,io
  from unittest.mock import Mock
  h=object.__new__(serve.Handler);h.path='/api/macro-refresh';h.headers={'Host':'127.0.0.1:8767'};h.server=SimpleNamespace(server_address=('127.0.0.1',8767));h.wfile=io.BytesIO();h.send_response=Mock();h.send_header=Mock();h.end_headers=Mock();return h
 def test_get_never_updates(self):
  with patch('serve.refresh') as update:
   h=self.handler();h.do_GET();update.assert_not_called();h.send_response.assert_called_once_with(405)
 def test_foreign_origin_never_updates(self):
  with patch('serve.refresh') as update:
   h=self.handler();h.headers.update({'Origin':'https://outside.example','X-Research-Action':'macro-refresh'});h.do_POST();update.assert_not_called();h.send_response.assert_called_once_with(403)
 def test_local_explicit_post_updates(self):
  with patch('serve.refresh',return_value={'fetchedAt':'teaching'}) as update,patch('serve.build') as render:
   h=self.handler();h.headers['X-Research-Action']='macro-refresh';h.do_POST();update.assert_called_once();render.assert_called_once();h.send_response.assert_called_once_with(200)
class RegistryIsolation(unittest.TestCase):
 def run_case(self,raw,fail=False):
  with tempfile.TemporaryDirectory() as root:
   p=Path(root);(p/'data.json').write_text(json.dumps({'indicators':[{'id':'x','name':'指标','frequency':'月','value':None,'history':[],'missing':'缺失'}]}),'utf-8');(p/'source-registry.json').write_text(raw,'utf-8')
   obs={'x':[{'period':'2026-08','value':1,'sourceUrl':'https://www.stats.gov.cn/test','official_release_date':None}]}
   def saving(path,value):
    if fail and Path(path).name=='source-registry.json':raise OSError('写入失败')
    return save_json(path,value)
   with patch('refresh.fetch_all',return_value=(obs,{},{})),patch('refresh.save_json',side_effect=saving):d=refresh(p)
   self.assertEqual(d['fetchHealth']['fresh'],1);self.assertEqual(json.loads((p/'data.json').read_text('utf-8'))['indicators'][0]['value'],1)
   if fail or raw!='[{"id":"x"}]':self.assertTrue(d['maintenanceWarnings']);self.assertEqual((p/'source-registry.json').read_text('utf-8'),raw)
   else:self.assertFalse(d['maintenanceWarnings']);self.assertTrue(json.loads((p/'source-registry.json').read_text('utf-8'))[0]['verifiedAdapter'])
 def test_corrupt_registry_preserved(self):self.run_case('{bad')
 def test_duplicate_registry_preserved(self):self.run_case('[{"id":"x"},{"id":"x"}]')
 def test_registry_write_failure_isolated(self):self.run_case('[{"id":"x"}]',True)
 def test_valid_registry_saved(self):self.run_case('[{"id":"x"}]')
 def test_report_inherited_date_explained(self):
  text=brief({'indicators':[{'id':'x','name':'指标','value':1,'data_period':'2026-08','sourceUrl':'https://www.stats.gov.cn/test','official_release_date':'2026-09-15','history':[{'period':'2026-08','releaseDateBasis':'retained-prior-unchanged-value'}]}],'maintenanceWarnings':['来源登记未更新']})
  self.assertIn('不能当作本次重新核验通过',text);self.assertIn('来源登记未更新',text)
