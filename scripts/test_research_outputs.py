import copy,json,tempfile,unittest
from pathlib import Path
from research_outputs import screen,snapshot,markdown
from research_tasks import import_records,append_note,task_path,read

class Tests(unittest.TestCase):
 def test_review_reopens_all_steps_before_next_completion(self):
  import hashlib
  from unittest.mock import patch
  from research_tasks import main,record_result
  with tempfile.TemporaryDirectory() as directory:
   store=Path(directory)/'tasks';row={'id':'t','title':'研究','snapshot':{'value':1}}
   import_records(store,{'type':'research-journal','version':1,'rows':[row]})
   for step in read(task_path(store,'t'))['steps']:record_result(store,'t',step['id'],'已核对',['原文定位'],True)
   changes=Path(directory)/'changes.json';changes.write_text(json.dumps({'type':'research-review','beforeSha256':hashlib.sha256(json.dumps(row['snapshot'],sort_keys=True).encode()).hexdigest()}),encoding='utf-8')
   with patch('sys.argv',['tasks','--store',str(store),'review','t','--changes',str(changes),'--conclusion','继续核对','--next-review','2026-11-01','--invalidation-status','unknown']):main()
   current=read(task_path(store,'t'));self.assertTrue(all(s['status']=='pending' for s in current['steps']))
   updated=record_result(store,'t',current['steps'][0]['id'],'复查一项',['新原文定位'],True)
   self.assertEqual(updated['status'],'pending');self.assertEqual(updated['sourceRecord'],row)
 def test_changed_import_reopens_review_and_preserves_first_evidence(self):
  from research_tasks import record_result
  with tempfile.TemporaryDirectory() as directory:
   store=Path(directory);row={'id':'t','title':'研究','snapshot':{'value':1},'claim':'观察'}
   import_records(store,{'type':'research-journal','version':1,'rows':[row]})
   task=read(task_path(store,'t'))
   for step in task['steps']:record_result(store,'t',step['id'],'已核对',['原文定位'],True)
   self.assertEqual(read(task_path(store,'t'))['status'],'completed')
   updated={**row,'snapshot':{'value':2}}
   import_records(store,{'type':'research-journal','version':1,'rows':[updated]})
   current=read(task_path(store,'t'));self.assertEqual(current['status'],'pending')
   self.assertTrue(all(s['status']=='pending' for s in current['steps']))
   self.assertEqual(current['sourceRecord'],row);self.assertEqual(current['importVersions'],[updated])
   self.assertEqual(len(current['evidence']),4)
   before=task_path(store,'t').read_bytes()
   import_records(store,{'type':'research-journal','version':1,'rows':[updated]})
   self.assertEqual(task_path(store,'t').read_bytes(),before)
 def test_note_only_import_does_not_invalidate_completed_review(self):
  from research_tasks import record_result
  with tempfile.TemporaryDirectory() as directory:
   store=Path(directory);row={'id':'t','title':'研究','snapshot':{'value':1}}
   import_records(store,{'type':'research-journal','version':1,'rows':[row]})
   for step in read(task_path(store,'t'))['steps']:record_result(store,'t',step['id'],'已核对',['原文定位'],True)
   import_records(store,{'type':'research-journal','version':1,'rows':[{**row,'note':'增加观察'}]})
   self.assertEqual(read(task_path(store,'t'))['status'],'completed')
 def test_record_rejects_false_completion_without_changing_task(self):
  from research_tasks import record_result
  with tempfile.TemporaryDirectory() as directory:
   store=Path(directory);import_records(store,{'type':'research-journal','version':1,'rows':[{'id':'test','title':'研究','snapshot':{'value':1}}]});p=task_path(store,'test');before=p.read_bytes()
   for refs,completed in [('source',True),([' '],True),(['source','source'],True),([],True),(['source'],'false')]:
    with self.assertRaises(ValueError):record_result(store,'test','核对来源与口径','说明',refs,completed)
    self.assertEqual(p.read_bytes(),before);self.assertFalse((store/'.research.lock').exists())
   r=record_result(store,'test','核对来源与口径','已记录指定来源',['原文第20页，所选净资产行'],True);self.assertEqual(r['steps'][0]['status'],'completed');self.assertEqual(r['sourceRecord']['snapshot'],{'value':1})
 def test_snapshot_identity_survives_archive_handoff(self):
  from research_library import archive
  r=snapshot({'subjectCodes':['000001'],'value':1},'研究');self.assertEqual(r['subjectCodes'],['000001'])
  with tempfile.TemporaryDirectory() as directory:
   store=Path(directory);p=store/'snapshot.json';p.write_text(json.dumps(r))
   self.assertEqual(len(archive({'code':'000001','resultFiles':[str(p)]},store)['results']),1)
   with self.assertRaisesRegex(ValueError,'主体不一致'):archive({'code':'000002','resultFiles':[str(p)]},store)
 def test_embedded_notes_preserve_text_and_binding_not_limitations(self):
  result={'notes':[{'kind':'user-note','text':'继续观察现金','conclusionIds':['cash']}],'limitations':['仅本期']}
  r=snapshot(result,'研究');self.assertEqual(r['limitations'],['仅本期']);self.assertIn('继续观察现金；关联记录：cash',markdown(r))
 def test_strict_reader_rejects_ambiguous_and_overflow_json(self):
  from research_outputs import read as read_result
  with tempfile.TemporaryDirectory() as directory:
   p=Path(directory)/'input.json'
   for raw in ['{"value":1,"value":2}','{"value":NaN}','{"value":1e999}']:
    p.write_text(raw)
    with self.assertRaises(ValueError):read_result(p)
 def test_strict_threshold_and_missing(self):
  s={'result':{'assets':[{'code':'a','maximumDrawdownPct':19,'Sharpe':1.3},{'code':'b','maximumDrawdownPct':20,'Sharpe':2},{'code':'c','maximumDrawdownPct':10,'Sharpe':None}]},'conditions':[{'metric':'maximumDrawdownPct','op':'lt','value':20},{'metric':'Sharpe','op':'gt','value':1.2}]}
  r=screen(s);self.assertEqual(r['selectedCodes'],['a']);self.assertEqual(r['excluded'][0]['code'],'b');self.assertEqual(r['unknown'][0]['code'],'c')
 def test_handoff_no_mutation(self):
  h={'assets':[{'code':'a','weight':.3},{'code':'b','weight':.7}],'reference':{'code':'x'}};old=copy.deepcopy(h)
  r=screen({'result':{'assets':[{'code':'a','Sharpe':2},{'code':'b','Sharpe':0}]},'conditions':[{'metric':'Sharpe','op':'gt','value':1.2}],'historyInput':h})
  self.assertEqual(r['comparisonInput']['assets'],[{'code':'a','weight':1}]);self.assertEqual(h,old)
 def test_bad_missing_history(self):
  with self.assertRaises(ValueError):screen({'result':{'assets':[{'code':'a','Sharpe':2}]},'conditions':[{'metric':'Sharpe','op':'gt','value':1}],'historyInput':{'assets':[]}})
 def test_snapshot_provenance_unknown_internal(self):
  r=snapshot({'acceptance':{'sourceVerification':'未核验'},'value':None,'inputSnapshot':{'assets':[{'code':'000311','sourceUrl':'https://example.org/a'}]}},'研究')
  self.assertEqual(r['sources'],[['000311','https://example.org/a']]);self.assertEqual(r['rows'],[['数值','待核验']]);self.assertNotIn('acceptance',markdown(r))
 def test_append_note_retains_snapshot(self):
  with tempfile.TemporaryDirectory() as folder:
   folder=Path(folder);import_records(folder,{'type':'research-journal','version':1,'rows':[{'id':'t','title':'研究','snapshot':{'value':42}}]});old=read(task_path(folder,'t'))['sourceRecord'];append_note(folder,'t','我的观察');new=read(task_path(folder,'t'));self.assertEqual(new['sourceRecord'],old);self.assertEqual(new['notes'][0]['kind'],'user-note')
 def test_notes_separated_escape(self):
  r=snapshot({'value':1},'研究',[{'kind':'user-note','text':'a|b\n下一行'}]);self.assertIn('a\\|b<br>下一行',markdown(r));self.assertEqual(r['rows'],[['数值',1]])
 def test_task_note_subject_must_match_current_result(self):
  from research_outputs import task_notes
  note={'kind':'user-note','text':'我的观察'};task={'sourceRecord':{'snapshot':{'code':'000001'}},'notes':[note]}
  self.assertEqual(task_notes(task,{'code':'000001'}),[note])
  with self.assertRaisesRegex(ValueError,'主体'):task_notes(task,{'code':'000002'})
  task['sourceRecord']['snapshot']={'value':1}
  with self.assertRaisesRegex(ValueError,'尚未确认'):task_notes(task,{'code':'000001'})
  self.assertEqual(task_notes(task,{'value':1}),[note])
if __name__=='__main__': unittest.main()
