import copy,json,unittest,tempfile,subprocess,sys
from pathlib import Path
from event_review import review
class Tests(unittest.TestCase):
 def spec(self):return json.loads((Path(__file__).resolve().parents[1]/'references/examples/event-evidence-example.json').read_text(encoding='utf-8'))
 def test_public_chain_keeps_unknown_and_unverified_status(self):
  r=review(self.spec());self.assertIsNone(r['events'][0]['eventDate']);self.assertEqual(r['relations'][0]['status'],'explicit-link-not-causal-proof');self.assertEqual(r['events'][0]['evidence']['pageVerification'],'declared-not-original-verified');self.assertNotIn('delistingProbability',r)
 def test_wrong_entity_future_date_and_wrong_relation_rejected(self):
  for key in ['entity','future','type']:
   s=self.spec()
   if key=='entity':s['events'][0]['entity']='另一主体'
   if key=='future':s['events'][0]['eventDate']='2026-06-10'
   if key=='type':s['events'][1]['kind']='penalty'
   with self.assertRaises(ValueError):review(s)
 def test_auditor_change_is_not_audit_opinion(self):
  s=self.spec();s['relations']=[];s['events'][1]['kind']='audit-opinion'
  with self.assertRaises(ValueError):review(s)
  s['events'][1]['opinionText']='教学意见原文';s['events'][1]['auditScope']='financial-statements';r=review(s);self.assertEqual(r['events'][1]['kind'],'audit-opinion')
  s['events'][1]['kind']='auditor-change'
  with self.assertRaises(ValueError):review(s)
 def test_empty_auditor_change_and_duplicate_relationship_rejected(self):
  s=self.spec();s['events'][1].update(kind='auditor-change',auditorChange={});s['relations']=[]
  with self.assertRaises(ValueError):review(s)
  s=self.spec();s['relations'].append(copy.deepcopy(s['relations'][0]))
  with self.assertRaises(ValueError):review(s)
 def test_html_cli_saves_input_and_method_hashes(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(__file__).resolve().parents[1];out=Path(tmp)/'result.html'
   run=subprocess.run([sys.executable,str(root/'scripts/event_review.py'),str(root/'references/examples/event-evidence-example.json'),'--format','html','--out',str(out)],capture_output=True)
   self.assertEqual(run.returncode,0,run.stderr);text=out.read_text(encoding='utf-8');self.assertIn('methodSha256',text);self.assertIn('未核本地原件',text)
   again=subprocess.run([sys.executable,str(root/'scripts/event_review.py'),str(root/'references/examples/event-evidence-example.json'),'--format','html','--out',str(out)],capture_output=True);self.assertNotEqual(again.returncode,0);self.assertEqual(out.read_text(encoding='utf-8'),text)
 def test_audit_scope_and_real_correction_declaration(self):
  s=self.spec();s['relations']=[];s['events'][1].update(kind='audit-opinion',opinionText='教学意见')
  with self.assertRaises(ValueError):review(s)
  s['events'][1]['auditScope']='internal-control';self.assertEqual(review(s)['events'][1]['auditScope'],'internal-control')
  path=Path(__file__).resolve().parents[1]/'references/examples/correction-evidence-example.json';case=json.loads(path.read_text(encoding='utf-8'));r=review(case)
  self.assertTrue(all(e['kind']=='correction' and e['eventDate'] is None for e in r['events']));self.assertEqual(r['events'][1]['affectedFields'][0]['after'],'元');self.assertEqual(r['events'][0]['evidence']['pageVerification'],'declared-not-original-verified')
 def test_html_controls_escape_and_do_not_mutate_results(self):
  from event_html_controls import table
  rows=[['<img src=x>','缺失']];before=copy.deepcopy(rows);html=table(['事件','状态'],rows);self.assertIn('&lt;img',html);self.assertEqual(rows,before);self.assertIn('不重新计算',html)
if __name__=='__main__':unittest.main()
