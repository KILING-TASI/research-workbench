import json,tempfile,unittest
import hashlib,subprocess
from unittest.mock import patch
from pathlib import Path
from update_delivery_candidate import inspect_outputs,main
class Status(unittest.TestCase):
 def test_timeout_records_failure_without_touching_previous_delivery(self):
  with tempfile.TemporaryDirectory() as t:
   source=Path(t)/'previous.json';source.write_text('{"records":[]}',encoding='utf-8');before=source.read_bytes();out=Path(t)/'new'
   with patch('sys.argv',['update','--previous',str(source),'--out-dir',str(out)]),patch('update_delivery_candidate.inspect_resources',return_value={'missingResources':[]}),patch('update_delivery_candidate.subprocess.run',side_effect=subprocess.TimeoutExpired(['step'],300)) as request:
    with self.assertRaises(SystemExit):main()
   report=json.loads((out/'update-report.json').read_text(encoding='utf-8'));self.assertEqual(report['status'],'failed-old-delivery-retained');self.assertEqual(report['steps'][0]['status'],'timeout');self.assertEqual(source.read_bytes(),before);self.assertEqual(request.call_args.kwargs['timeout'],300)
 def test_bad_partial_artifacts_remain_explicit_gaps(self):
  for text in ['{','[]']:
   with tempfile.TemporaryDirectory() as t:
    p=Path(t);(p/'data.json').write_text(text,encoding='utf-8');summary,gaps=inspect_outputs(p);self.assertEqual(gaps[0]['stage'],'invalid-artifact')
 def test_collection_failure_keeps_successful_delivery(self):
  with tempfile.TemporaryDirectory() as t:
   source=Path(t)/'previous.json';source.write_text('{"fetchedAt":"2026-10-03","records":[]}',encoding='utf-8')
   before=hashlib.sha256(source.read_bytes()).hexdigest()
   out=Path(t)/'new'
   with patch('sys.argv',['update','--previous',str(source),'--out-dir',str(out)]),patch('update_delivery_candidate.inspect_resources',return_value={'missingResources':[]}),patch('update_delivery_candidate.subprocess.run',return_value=subprocess.CompletedProcess([],1,'','network failure')) as request:
    with self.assertRaises(SystemExit):main()
   report=json.loads((out/'update-report.json').read_text(encoding='utf-8'))
   self.assertEqual(report['status'],'failed-old-delivery-retained');self.assertEqual(request.call_count,1)
   self.assertFalse(report['liveFilesOverwritten']);self.assertFalse(report['originalEvidenceApproved'])
   self.assertEqual(before,hashlib.sha256(source.read_bytes()).hexdigest())
 def test_partial_download_and_field_conflict_visible(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);(p/'originals').mkdir()
   (p/'originals/manifest.json').write_text(json.dumps({'documents':[{}],'details':[{'code':'1','status':'failed','reason':'403'}],'missing':[{'code':'2','status':'no-supported-original-link'}]}))
   (p/'original-candidates.json').write_text(json.dumps({'documents':[{'code':'3','status':'extracted-for-review','fields':{'price':{'status':'conflicting-candidates','candidates':[1,2]}}}]}))
   s,g=inspect_outputs(p);self.assertEqual(s['downloaded'],1);self.assertEqual({x['stage'] for x in g},{'download','original-link','field'})
 def test_no_documents_not_success(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);(p/'original-candidates.json').write_text('{"documents":[]}')
   s,g=inspect_outputs(p);self.assertEqual(g[0]['stage'],'extraction')
 def test_unqueried_batch_objects_are_a_gap(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);(p/'data.json').write_text(json.dumps({'announcementRefresh':{'queried':2,'failed':0,'pending':36,'covered':349}}))
   s,g=inspect_outputs(p)
   self.assertEqual(s['announcementRefresh']['pending'],36)
   self.assertEqual(g,[{'stage':'announcements-pending','pending':36,'reason':'Bounded batch left objects unqueried; this is not a completed refresh'}])
 def test_original_conflict_is_not_only_a_summary_count(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);(p/'data-diff.json').write_text(json.dumps({'requiresReview':True,'originalConflicts':[{'code':'920001','field':'price','status':'needs-review'}]}))
   s,g=inspect_outputs(p)
   self.assertEqual(s['originalConflictCount'],1);self.assertEqual(g[0]['stage'],'original-conflict')
   self.assertEqual(g[0]['field'],'price')
if __name__=='__main__':unittest.main()
