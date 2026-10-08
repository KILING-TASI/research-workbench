import hashlib,importlib.util,json,shutil,subprocess,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS=Path(__file__).resolve().parents[1]/'modules/bjx-newshare-toolkit/scripts'
class RefreshScope(unittest.TestCase):
 def test_refresh_preserves_history_without_automatic_prediction_capture(self):
  spec=importlib.util.spec_from_file_location('toolkit_scope_test',SCRIPTS/'toolkit.py');module=importlib.util.module_from_spec(spec)
  with patch.dict('sys.modules',{'announcements':types.SimpleNamespace(enrich=lambda *a:None),'etf_embed':types.SimpleNamespace(embed=lambda page,*a:page)}):spec.loader.exec_module(module)
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);assets=root/'assets';assets.mkdir()
   old={'predictionArchive':[{'code':'920162','mode':'historical-test'}],'modelValidation':{'count':1}}
   (assets/'data.json').write_text(json.dumps(old),encoding='utf-8');blob=b'{"count":1}';(assets/'模型验证.json').write_bytes(blob)
   (assets/'workbench.template.html').write_text('/*ENGINE*/ /*SNAPSHOT*/',encoding='utf-8');(assets/'engine.js').write_text('',encoding='utf-8')
   rows=[{'SECURITY_CODE':'920162','SECURITY_NAME_ABBR':'测试输入','ISSUE_PRICE':17.37}]
   with patch.object(module,'ROOT',root),patch.object(module.subprocess,'run',side_effect=AssertionError('automatic model execution forbidden')):
    first=module.save(rows);second=module.save(rows)
   self.assertEqual(first['predictionArchive'],old['predictionArchive']);self.assertEqual(second['predictionArchive'],old['predictionArchive']);self.assertEqual(first['modelValidation']['status'],'not-run')
   archive=assets/'historical-model-validation'/(hashlib.sha256(blob).hexdigest()+'.json');self.assertEqual(archive.read_bytes(),blob)
 @unittest.skipUnless(shutil.which('node'),'Node required')
 def test_explicit_legacy_review_cannot_add_freeze_records(self):
  data={'fetchedAt':'2026-10-08T10:00:00+08:00','records':[],'predictionArchive':[{'code':'920162','mode':'historical-test'}]}
  result=subprocess.run([shutil.which('node'),str(SCRIPTS/'validate_model.js')],input=json.dumps(data),capture_output=True,text=True,encoding='utf-8')
  self.assertEqual(result.returncode,0,result.stderr);parsed=json.loads(result.stdout);self.assertEqual(parsed['predictionArchive'],data['predictionArchive']);self.assertEqual(parsed['modelValidation']['frozenChecks'],[])

if __name__=='__main__':unittest.main()
