import copy,unittest
from fof_batch_merge import merge
class Tests(unittest.TestCase):
 def test_malformed_records_and_future_report_fail_clearly(self):
  p,b=self.data()
  for value in [None,[],{},dict(holdings=[None])]:
   with self.assertRaises(ValueError):merge(value,b)
  b[0]['result']['asOf']='2026-01-01'
  with self.assertRaisesRegex(ValueError,'早于报告期'):merge(p,b)
 def data(self):
  p=dict(reportDate='2026-06-30',holdings=[dict(code=c,weight=.1) for c in ['000001','000002']])
  def batch(start):
   rows=[dict(code=h['code'],reportDate=p['reportDate'],fofWeight=.1,status='parsed-equity' if i==start else 'missing') for i,h in enumerate(p['holdings'])]
   return dict(startIndex=start,limit=1,result=dict(asOf='2026-10-06',reportDate=p['reportDate'],rows=rows,nodes={rows[start]['code']:dict(holdings=[])}))
  return p,[batch(0),batch(1)]
 def test_outside_batch_missing_does_not_erase_success(self):
  p,b=self.data();r=merge(p,b);self.assertEqual(r['counts']['parsed'],2);self.assertEqual(r['counts']['pending'],0)
 def test_overlap_rejected(self):
  p,b=self.data()
  with self.assertRaisesRegex(ValueError,'重叠'):merge(p,[b[0],b[0]])
 def test_changed_parent_weight_rejected(self):
  p,b=self.data();b[1]['result']['rows'][1]['fofWeight']=.2
  with self.assertRaisesRegex(ValueError,'父快照'):merge(p,b)
 def test_missing_parsed_node_rejected(self):
  p,b=self.data();b[1]['result']['nodes']={}
  with self.assertRaisesRegex(ValueError,'子节点'):merge(p,b)
 def test_different_cutoff_rejected(self):
  p,b=self.data();b[1]['result']['asOf']='2026-10-05'
  with self.assertRaisesRegex(ValueError,'截止日'):merge(p,b)
 def test_explicit_subset_does_not_import_unselected_nodes(self):
  p,b=self.data();full=b[0]['result'];full['rows'][1]['status']='parsed-equity';full['nodes']['000002']=dict(holdings=[]);full['batch']=dict(startIndex=0,limit=2)
  r=merge(p,[dict(result=full,startIndex=1,limit=1)])
  self.assertEqual(set(r['nodes']),{'000002'});self.assertEqual(r['counts']['notAttempted'],1)
 def test_subset_cannot_claim_outside_executed_range(self):
  p,b=self.data();b[0]['result']['batch']=dict(startIndex=0,limit=1);b[0]['startIndex']=1
  with self.assertRaisesRegex(ValueError,'超出'):merge(p,[b[0]])
if __name__=='__main__':unittest.main()
