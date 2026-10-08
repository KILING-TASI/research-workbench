import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import research_workflow as f
class Tests(unittest.TestCase):
 def fixture(self,d,asof='2026-10-05'):
  root=Path(d);ctx={'type':'research-context','parameters':{'asOf':'2026-10-05'}};ctx['contextHash']=f.digest(ctx['parameters'])
  pdf=root/'original.pdf';pdf.write_bytes(b'original')
  files={'context.json':ctx,'archive.json':{'asOf':asof,'reports':[{'id':'report','pdfPath':str(pdf)}]},'input.json':{'archive':str(root/'archive.json')}}
  for name,data in files.items():(root/name).write_text(json.dumps(data),encoding='utf8')
  return {'template':'report-translation-review','contextPath':str(root/'context.json'),'inputPath':str(root/'input.json'),'outDir':str(root/'out')}
 def test_cutoff_mismatch_rejects_before_translation(self):
  with tempfile.TemporaryDirectory() as d,patch('report_translation.build') as build:
   with self.assertRaisesRegex(ValueError,'截止日'):f.run_template(self.fixture(d,'2026-10-04'),Path(d))
   build.assert_not_called()
 def test_coverage_and_numeric_gaps_survive_wrapper(self):
  result={'reportId':'report','missingPages':[2],'lowTextPages':[3],'pages':[{'page':1,'numericWarnings':['数字需核对']}],'limitations':[]}
  with tempfile.TemporaryDirectory() as d,patch('report_translation.build',return_value=result):
   r=f.run_template(self.fixture(d),Path(d));self.assertEqual(r['status'],'calculated-with-gaps')
   self.assertEqual(len(r['gaps']),4);self.assertTrue(any('语义' in g['reason'] for g in r['gaps']))
   self.assertTrue(any(n['role']=='original-pdf' for n in r['lineage']['files']))
   self.assertTrue(any(c['module']=='report_translation.py' for c in r['lineage']['calculations'][0]['code']))
