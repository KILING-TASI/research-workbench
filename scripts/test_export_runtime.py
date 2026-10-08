import os,tempfile,unittest
import json,zipfile,hashlib
from pathlib import Path
from unittest.mock import patch
from export_runtime import component_environment,verify_workbook
from financial_research_pipeline import run
class ExportRuntimeTests(unittest.TestCase):
 def test_explicit_directory_keeps_parent_environment_unchanged(self):
  with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'ARTIFACT_NODE_MODULES':'old','RESEARCH_EXPORT_QA':'1'}):
   env=component_environment(d)
   self.assertEqual(env['RESEARCH_EXPORT_QA'],'1');self.assertEqual(os.environ['ARTIFACT_NODE_MODULES'],'old')
   self.assertNotEqual(env['ARTIFACT_NODE_MODULES'],'old')
 def test_invalid_component_stops_before_collection(self):
  with tempfile.TemporaryDirectory() as d,patch('financial_research_pipeline.collect') as collect:
   with self.assertRaises(ValueError):run({},d+'/output',artifact_node_modules=d+'/missing')
   collect.assert_not_called();self.assertFalse(os.path.exists(d+'/output'))
 def test_environment_directory_is_validated(self):
  with patch.dict(os.environ,{'ARTIFACT_NODE_MODULES':' '}):
   with self.assertRaises(ValueError):component_environment()
 def test_exit_success_does_not_replace_file_and_hash_checks(self):
  with tempfile.TemporaryDirectory() as d:
   workbook=Path(d)/'a.xlsx';inp=Path(d)/'input.json';input_text=json.dumps(dict(rows=[{}],companies=[{}],groups=[{}]));inp.write_text(input_text,encoding='utf-8')
   with self.assertRaises(OSError):verify_workbook(workbook,inp)
   with zipfile.ZipFile(workbook,'w') as z:
    for name in ['[Content_Types].xml','_rels/.rels','xl/workbook.xml']:z.writestr(name,'fixture')
   qa=dict(formulaDifferences=[],quarterValueChecks=3,growthChecks=2,summaryChecks=4,groupChecks=4,errorScan=json.dumps(dict(kind='notice',message='Cell search matched 0 entries.')),inputSha256=hashlib.sha256(inp.read_bytes()).hexdigest(),workbookSha256=hashlib.sha256(workbook.read_bytes()).hexdigest())
   saved=Path(str(workbook)+'.qa.json');saved.write_text(json.dumps(qa),encoding='utf-8');self.assertEqual(verify_workbook(workbook,inp),qa)
   inp.write_text('{"changed":1}',encoding='utf-8')
   with self.assertRaisesRegex(OSError,'不匹配'):verify_workbook(workbook,inp)
   inp.write_text(input_text,encoding='utf-8')
   for key,value in [('quarterValueChecks',0),('growthChecks',True),('errorScan',''),('errorScan',json.dumps(dict(kind='notice',message='Cell search matched 1 entries.')))]:
    changed=dict(qa);changed[key]=value;saved.write_text(json.dumps(changed),encoding='utf-8')
    with self.assertRaises(OSError):verify_workbook(workbook,inp)
   qa['formulaDifferences']=[['D8',1,2]];saved.write_text(json.dumps(qa),encoding='utf-8')
   with self.assertRaisesRegex(OSError,'差异'):verify_workbook(workbook,inp)
