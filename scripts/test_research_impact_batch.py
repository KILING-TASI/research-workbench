import unittest,tempfile,json,copy
from pathlib import Path
from research_impact_batch import analyze,export
from research_workflow import digest,file_digest
class BatchImpactTests(unittest.TestCase):
 def setUp(self):
  from test_research_impact_integrity import Tests
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.source=self.root/'source';self.source.write_text('old');self.spec={'researches':[]}
  for n in range(2):
   x=Tests().sample();x['lineage']['files']=[{'role':'original','path':str(self.source),'sha256':file_digest(self.source)}];del x['envelopeSha256'];x['envelopeSha256']=digest(x);p=self.root/(str(n)+'.json');p.write_text(json.dumps(x),'utf-8');self.spec['researches'].append({'id':str(n),'label':'研究'+str(n),'resultPath':str(p)})
 def tearDown(self):self.temp.cleanup()
 def test_shared_source_affects_both(self):
  self.source.write_text('new');r=analyze(self.spec);self.assertEqual(r['affectedResearchIds'],['0','1']);self.assertEqual(r['sourceImpacts'][0]['researchIds'],['0','1'])
 def test_invalid_request_has_clear_failure(self):
  for spec in [None,[],{}, {'researches':None}]:
   with self.subTest(spec=spec),self.assertRaises(ValueError):analyze(spec)
 def test_missing_source_report_explains_next_step(self):
  self.source.unlink();r=analyze(self.spec);out=self.root/'report';export(r,out)
  text=(out/'研究影响复查.md').read_text('utf-8')
  self.assertIn('先恢复或补取已登记来源',text);self.assertIn('不能作为已复核结果引用',text)
 def test_unchanged_not_remote_certification(self):self.assertFalse(analyze(self.spec)['affectedResearchIds'])
 def test_unknown_replacement_rejected(self):
  self.spec['replacements']={'missing':'new'}
  with self.assertRaises(ValueError):analyze(self.spec)
 def test_tampered_record_rejected(self):
  p=Path(self.spec['researches'][0]['resultPath']);x=json.loads(p.read_text('utf-8'));x['status']='verified';p.write_text(json.dumps(x),'utf-8')
  with self.assertRaises(ValueError):analyze(self.spec)
 def test_duplicate_ids_rejected(self):
  self.spec['researches'][1]['id']='0'
  with self.assertRaises(ValueError):analyze(self.spec)

 def test_changed_file_identifies_registered_calculation(self):
  for row in self.spec['researches']:
   p=Path(row['resultPath']);x=json.loads(p.read_text('utf-8'));x['lineage']['calculations'][0]['dependsOnFiles']=[str(self.source)];del x['envelopeSha256'];x['envelopeSha256']=digest(x);p.write_text(json.dumps(x),'utf-8')
  self.source.write_text('new');r=analyze(self.spec);self.assertTrue(r['researches'][0]['affectedCalculations']);self.assertIn('未自动推断',r['researches'][0]['affectedCalculations'][0]['scope'])
 def test_invalid_new_context_rejected(self):
  self.spec['researches'][0]['newContextPath']=42
  with self.assertRaises(ValueError):analyze(self.spec)
