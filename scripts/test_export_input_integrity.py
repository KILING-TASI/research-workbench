import json,os,shutil,subprocess,tempfile,unittest
from pathlib import Path

class ExportIntegrity(unittest.TestCase):
 def run_export(self,directory,script,text,scan=''):
  package=directory/'node_modules/@oai/artifact-tool';package.mkdir(parents=True,exist_ok=True)
  (package/'package.json').write_text(json.dumps({'name':'@oai/artifact-tool','type':'module','main':'index.js'}),encoding='utf-8')
  # Controlled component response, not a real workbook/visual acceptance.
  (package/'index.js').write_text("import fs from 'node:fs/promises';const range={format:{font:{},autofitRows(){}},setNumberFormat(){}};const sheet={freezePanes:{freezeRows(){}},getRange(){return range},getCell(){return range},getRangeByIndexes(){return range}};export const Workbook={create(){return {worksheets:{add(){return sheet}},async inspect(){return {ndjson:"+json.dumps(scan)+"}}}}};export const SpreadsheetFile={async exportXlsx(){return {async save(p){await fs.writeFile(p,'should-not-save')}}}};",encoding='utf-8')
  inp=directory/'input.json';out=directory/'result.xlsx';inp.write_text(text,encoding='utf-8')
  env={**os.environ,'ARTIFACT_NODE_MODULES':str(directory/'node_modules')}
  result=subprocess.run([shutil.which('node'),str(Path(__file__).parent/script),str(inp),str(out)],env=env,capture_output=True,text=True,encoding='utf-8')
  self.assertNotEqual(result.returncode,0);self.assertFalse(out.exists());return result.stderr
 @unittest.skipUnless(shutil.which('node'),'Node required')
 def test_duplicate_and_overflow_rejected_in_both_exports(self):
  for script in ['export_research_xlsx.mjs','export_financial_workbook.mjs']:
   for text,error in [('{"title":"first","title":"second"}','Duplicate JSON property'),('{"value":1e999}','Non-finite JSON number')]:
    with tempfile.TemporaryDirectory() as directory:self.assertIn(error,self.run_export(Path(directory),script,text))
 @unittest.skipUnless(shutil.which('node'),'Node required')
 def test_error_or_unconfirmed_scan_stops_snapshot_export(self):
  data={'title':'研究','rows':[['缺失指标',None]],'sources':[],'limitations':['资料不全'],'userNotes':[],'notice':'历史不代表未来'}
  for scan in ['',json.dumps({'kind':'match','value':'#REF!'}),json.dumps({'kind':'notice','message':'Cell search matched 1 entries.'})]:
   with tempfile.TemporaryDirectory() as directory:self.assertIn('停止导出',self.run_export(Path(directory),'export_research_xlsx.mjs',json.dumps(data),scan))

if __name__=='__main__':unittest.main()
