import unittest,tempfile,json,copy
from pathlib import Path
from unittest.mock import patch
import collection_quality_brief as q
import verify_collection_report as v
from collection_validation import market_rows

class Tests(unittest.TestCase):
 def bundle(self):return {'asOf':'2026-09-30','rows':[{'kind':'stock','code':'600009','history':[{'date':'2026-09-01','close':10}]}]}
 def bad(self,change):
  b=self.bundle();change(b)
  with self.assertRaises(ValueError):q.brief(b)
 def report(self,root):
  f=Path(root)/'input.json';f.write_text(json.dumps(self.bundle()),encoding='utf-8');out=Path(root)/'report';q.publish(f,out);return f,out/'report-manifest.json'
 def test_r61_root_type(self):
  for value in [None,[],False]:
   with self.assertRaises(ValueError):q.brief(value)
 def test_r95_duplicate_input_keys(self):
  with tempfile.TemporaryDirectory() as root:
   f=Path(root)/'input.json';f.write_text('{"rows":[],"rows":[]}',encoding='utf-8')
   with self.assertRaises(ValueError):q.publish(f,Path(root)/'report')
   self.assertFalse((Path(root)/'report').exists())
 def test_r96_nonfinite_input_json(self):
  with tempfile.TemporaryDirectory() as root:
   f=Path(root)/'input.json';f.write_text('{"unused":NaN}',encoding='utf-8')
   with self.assertRaises(ValueError):q.publish(f,Path(root)/'report')
 def test_r97_manifest_boolean_version(self):
  with tempfile.TemporaryDirectory() as root:
   f,m=self.report(root);d=json.loads(m.read_text(encoding='utf-8'));d['schemaVersion']=True;m.write_text(json.dumps(d),encoding='utf-8');self.assertEqual(v.verify(m,f)['status'],'invalid-manifest')
 def test_r98_unreadable_report(self):
  with tempfile.TemporaryDirectory() as root:
   f,m=self.report(root);original=v.digest
   def check(p):
    if p.suffix=='.html':raise PermissionError('injected')
    return original(p)
   with patch.object(v,'digest',side_effect=check):result=v.verify(m,f)
   self.assertEqual(result['status'],'content-mismatch');self.assertTrue(any('不可读取' in s for s in result['problems']))
 def test_r99_missing_method_file(self):
  with tempfile.TemporaryDirectory() as root:
   f,m=self.report(root);original=v.digest
   def check(p):
    if p.name=='atomic_json.py':raise FileNotFoundError('injected')
    return original(p)
   with patch.object(v,'digest',side_effect=check):result=v.verify(m,f)
   self.assertEqual(result['status'],'content-mismatch');self.assertIn('atomic_json.py',result['methodChanges'])
 def test_r100_summary_and_row_errors_visible(self):
  b=self.bundle();b['rows'][0]['errors']={'history':'TimeoutError: service'}
  text=q.brief(b);self.assertIn('1个取得可展示资料',text);self.assertIn('行情： 取数超时',text);self.assertIn('不代表覆盖完整',text)

cases=[
 (62,'unknown_kind',lambda b:b['rows'][0].update(kind='unknown')),
 (63,'unknown_collection_status',lambda b:b['rows'][0].update(collectionStatus='complete')),
 (64,'identity_array',lambda b:b['rows'][0].update(identity=[])),
 (65,'boolean_name',lambda b:b['rows'][0].update(identity={'name':False})),
 (66,'errors_array',lambda b:b['rows'][0].update(errors=[])),
 (67,'numeric_error',lambda b:b['rows'][0].update(errors={'history':7})),
 (68,'gaps_string',lambda b:b['rows'][0].update(gaps='abc')),
 (69,'numeric_gap',lambda b:b['rows'][0].update(gaps=[0])),
 (70,'cache_flag_string',lambda b:b['rows'][0].update(cacheRetained='false')),
 (71,'resume_flag_string',lambda b:b['rows'][0].update(resumed='false')),
 (72,'source_whitespace',lambda b:b['rows'][0].update(source='https://example.org/a b')),
 (73,'source_control',lambda b:b['rows'][0].update(source='https://example.org/\tpath')),
 (74,'source_bad_port',lambda b:b['rows'][0].update(source='https://example.org:invalid')),
 (75,'components_array',lambda b:b['rows'][0].update(components=[])),
 (76,'unknown_component',lambda b:b['rows'][0].update(components={'unknown':{}})),
 (77,'component_scalar',lambda b:b['rows'][0].update(components={'history':1})),
 (78,'component_status',lambda b:b['rows'][0].update(components={'history':{'status':'full'}})),
 (79,'sources_scalar',lambda b:b['rows'][0].update(components={'history':{'status':'success','sources':'https://example.org'}})),
 (80,'component_naive_timestamp',lambda b:b['rows'][0].update(components={'history':{'status':'success','retrievedAt':'2026-09-01T00:00:00'}})),
 (81,'component_numeric_error',lambda b:b['rows'][0].update(components={'history':{'status':'success','error':1}})),
 (82,'component_numeric_reason',lambda b:b['rows'][0].update(components={'history':{'status':'success','reason':1}})),
 (83,'component_boolean_count',lambda b:b['rows'][0].update(components={'history':{'status':'success','count':True}})),
 (84,'component_wrong_count',lambda b:b['rows'][0].update(components={'history':{'status':'success','count':2}})),
 (85,'unsupported_with_data',lambda b:b['rows'][0].update(components={'history':{'status':'unsupported'}})),
 (86,'unavailable_with_data',lambda b:b['rows'][0].update(collectionStatus='unavailable')),
 (87,'financial_missing_date',lambda b:b['rows'][0].update(financials=[{}])),
 (88,'future_financial_publication',lambda b:b['rows'][0].update(financials=[{'period':'2026-06-30','publishedAt':'2026-10-01'}])),
 (89,'financial_wrong_identity',lambda b:b['rows'][0].update(financials=[{'period':'2026-06-30','publishedAt':'2026-08-30','raw':{'SECURITY_CODE':'600036'}}])),
 (90,'announcement_numeric_title',lambda b:b['rows'][0].update(announcements=[{'id':'a','date':'2026-09-01','title':1}])),
 (91,'financial_duplicate',lambda b:b['rows'][0].update(financials=[{'period':'2026-06-30','publishedAt':'2026-08-30'}]*2)),
 (92,'financial_raw_array',lambda b:b['rows'][0].update(financials=[{'period':'2026-06-30','publishedAt':'2026-08-30','raw':[]}])),
 (93,'blank_announcement_id',lambda b:b['rows'][0].update(announcements=[{'id':' ','date':'2026-09-01'}])),
]
for number,name,change in cases:
 def check(self,change=change):self.bad(change)
 setattr(Tests,'test_r'+str(number)+'_'+name,check)
def unknown(self):
 with self.assertRaises(ValueError):market_rows('unknown',[{}])
setattr(Tests,'test_r94_unknown_market_component',unknown)
if __name__=='__main__':unittest.main()
