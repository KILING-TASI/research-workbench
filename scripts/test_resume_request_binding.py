import unittest,tempfile,json
from unittest.mock import patch
from pathlib import Path
import batch_collect as b
class ResumeRequestBinding(unittest.TestCase):
 def test_fund_without_start_still_respects_cutoff(self):
  with tempfile.TemporaryDirectory() as root:
   doc={'asOf':'2026-09-30','requests':[{'kind':'fund','code':'006113'}]}
   out=b.run(root,doc,lambda *a:{'rows':[{'history':[{'date':'2026-09-29','nav':1},{'date':'2026-10-01','nav':2}]}]})
   self.assertEqual([h['date'] for h in out['rows'][0]['history']],['2026-09-29'])
 def test_bad_component_does_not_abort_later_fund(self):
  with tempfile.TemporaryDirectory() as root:
   doc={'asOf':'2026-09-30','requests':[{'kind':'fund','code':'006113'},{'kind':'fund','code':'000991'}]}
   def legacy(workspace,kind,codes,*args):
    return {'rows':[{'history':[{'date':'2026-09-29','nav':1}], 'components':[] if codes[0]=='006113' else {}}]}
   out=b.run(root,doc,legacy)
   self.assertEqual(out['rows'][0]['collectionStatus'],'unavailable')
   self.assertIn('组件状态结构',out['rows'][0]['errors'])
   self.assertEqual(out['rows'][1]['collectionStatus'],'cached')
 def test_matching_hash_cannot_override_request_identity_or_window(self):
  for change in ['code','kind','scope','future','early']:
   with self.subTest(change=change),tempfile.TemporaryDirectory() as root:
    doc={'asOf':'2026-09-30','refresh':True,'jobId':'bound','requests':[{'kind':'fund','code':'006113','start':'2026-09-01'}]}
    legacy=lambda *a:{'rows':[{'history':[{'date':'2026-09-02','nav':1}]}]}
    out=b.run(root,doc,legacy);p=Path(out['checkpoint']);s=json.loads(p.read_text('utf-8'));row=s['rows']['0']
    if change=='code':row['code']='009342'
    elif change=='kind':row['kind']='stock'
    elif change=='scope':row['requestScope']['start']='2026-08-01'
    elif change=='future':row['history'][0]['date']='2026-10-01'
    else:row['history'][0]['date']='2026-08-31'
    s['rowHashes']['0']=b.row_hash(row);p.write_text(json.dumps(s),'utf-8')
    result=b.run(root,{**doc,'resume':True},legacy)['rows'][0]
    self.assertFalse(result['resumed']);self.assertEqual(result['code'],'006113');self.assertEqual(result['history'][0]['date'],'2026-09-02');self.assertIn('请求区间',result['resumeValidation'])

 def test_ambiguous_or_nonfinite_checkpoint_preserves_file_and_never_collects(self):
  for suffix in ['duplicate-root','duplicate-nested','NaN','overflow']:
   with self.subTest(suffix=suffix),tempfile.TemporaryDirectory() as root:
    doc={'asOf':'2026-09-30','jobId':'strict','requests':[{'kind':'fund','code':'006113'}]}
    out=b.run(root,doc,lambda *a:{'rows':[{'history':[{'date':'2026-09-02','nav':1}]}]})
    p=Path(out['checkpoint']); raw=p.read_text('utf-8')
    if suffix=='duplicate-root': raw='{"rows":{},'+raw[1:]
    elif suffix=='duplicate-nested': raw=raw[:-1]+',"extra":{"code":"006113","code":"000991"}}'
    elif suffix=='NaN': raw=raw[:-1]+',"extra":NaN}'
    else: raw=raw[:-1]+',"extra":1e999}'
    p.write_text(raw,encoding='utf-8'); original=p.read_bytes(); calls=[]
    with self.assertRaisesRegex(ValueError,'断点文件不可读'):
     b.run(root,{**doc,'resume':True},lambda *a:calls.append(a))
    self.assertEqual(calls,[]);self.assertEqual(p.read_bytes(),original)
 def test_utf8_bom_checkpoint_resumes_without_collection(self):
  with tempfile.TemporaryDirectory() as root:
   doc={'asOf':'2026-09-30','jobId':'bom','requests':[{'kind':'fund','code':'006113'}]}
   out=b.run(root,doc,lambda *a:{'rows':[{'history':[{'date':'2026-09-02','nav':1}]}]})
   p=Path(out['checkpoint']);p.write_bytes(b'\xef\xbb\xbf'+p.read_bytes());calls=[]
   result=b.run(root,{**doc,'resume':True},lambda *a:calls.append(a))
   self.assertEqual(calls,[]);self.assertTrue(result['rows'][0]['resumed'])

 def test_invalid_nav_cannot_succeed_and_does_not_abort_next_fund(self):
  for nav in [0,-1,True,'1',None,float('inf'),10**400]:
   with self.subTest(nav=str(nav)[:20]),tempfile.TemporaryDirectory() as root:
    doc={'asOf':'2026-09-30','requests':[{'kind':'fund','code':'006113'},{'kind':'fund','code':'000991'}]}
    def legacy(workspace,kind,codes,*args):
     return {'rows':[{'history':[{'date':'2026-09-01','nav':nav if codes[0]=='006113' else 1}]}]}
    out=b.run(root,doc,legacy)
    self.assertEqual(out['rows'][0]['collectionStatus'],'unavailable')
    self.assertIn('基金净值无效',out['rows'][0]['errors'])
    self.assertEqual(out['rows'][1]['collectionStatus'],'cached')
 def test_matching_checkpoint_hash_does_not_validate_negative_nav(self):
  with tempfile.TemporaryDirectory() as root:
   doc={'asOf':'2026-09-30','jobId':'badnav','requests':[{'kind':'fund','code':'006113'}]}
   legacy=lambda *a:{'rows':[{'history':[{'date':'2026-09-01','nav':1}]}]}
   out=b.run(root,doc,legacy);p=Path(out['checkpoint']);s=json.loads(p.read_text('utf-8'))
   s['rows']['0']['history'][0]['nav']=-1;s['rowHashes']['0']=b.row_hash(s['rows']['0']);p.write_text(json.dumps(s),encoding='utf-8')
   out=b.run(root,{**doc,'resume':True},legacy)
   self.assertFalse(out['rows'][0]['resumed']);self.assertEqual(out['rows'][0]['history'][0]['nav'],1)

 def test_malformed_checkpoint_history_is_refetched_not_batch_abort(self):
  for history in [[None],[1],['bad'],{},'bad',None,[]]:
   with self.subTest(history=history),tempfile.TemporaryDirectory() as root:
    doc={'asOf':'2026-09-30','jobId':'structure','requests':[{'kind':'fund','code':'006113'}]}
    legacy=lambda *a:{'rows':[{'history':[{'date':'2026-09-01','nav':1}]}]}
    out=b.run(root,doc,legacy);p=Path(out['checkpoint']);state=json.loads(p.read_text('utf-8'))
    state['rows']['0']['history']=history;state['rowHashes']['0']=b.row_hash(state['rows']['0']);p.write_text(json.dumps(state),encoding='utf-8')
    result=b.run(root,{**doc,'resume':True},legacy)
    self.assertFalse(result['rows'][0]['resumed']);self.assertEqual(result['rows'][0]['history'][0]['nav'],1)

 def test_market_history_with_matching_hash_is_revalidated_before_resume(self):
  good={'date':'2026-09-01','open':10,'close':10,'high':10,'low':10,'volume':0,'amount':0}
  for kind,code in [('stock','600406'),('etf','510880')]:
   for field,value in [('close',-1),('close',True),('high',9),('volume',-1),('close',10**400)]:
    with self.subTest(kind=kind,field=field,value=str(value)[:12]),tempfile.TemporaryDirectory() as root:
     doc={'asOf':'2026-09-30','jobId':'market','requests':[{'kind':kind,'code':code,'start':'2026-09-01'}]}
     valid={'code':code,'kind':kind,'history':[dict(good)]}
     with patch.object(b,'collect_market',return_value=valid):out=b.run(root,doc,None)
     p=Path(out['checkpoint']);state=json.loads(p.read_text('utf-8'));state['rows']['0']['history'][0][field]=value;state['rowHashes']['0']=b.row_hash(state['rows']['0']);p.write_text(json.dumps(state),encoding='utf-8')
     with patch.object(b,'collect_market',return_value=valid) as fetch:out=b.run(root,{**doc,'resume':True},None)
     fetch.assert_called_once();self.assertFalse(out['rows'][0]['resumed']);self.assertEqual(out['rows'][0]['history'],[good])

 def test_market_component_dates_and_identity_survive_recomputed_hash(self):
  for change in ['future-financial','early-financial','future-announcement','wrong-company']:
   with self.subTest(change=change),tempfile.TemporaryDirectory() as root:
    doc={'asOf':'2026-09-30','jobId':'components','requests':[{'kind':'stock','code':'600406','start':'2026-09-01','financialStart':'2025-01-01'}]}
    valid={'code':'600406','kind':'stock','history':[],'financials':[{'period':'2026-06-30','publishedAt':'2026-08-27','raw':{'SECURITY_CODE':'600406'}}],'announcements':[{'id':'a','date':'2026-09-02'}]}
    with patch.object(b,'collect_market',return_value=valid):out=b.run(root,doc,None)
    p=Path(out['checkpoint']);state=json.loads(p.read_text('utf-8'));row=state['rows']['0']
    if change=='future-financial':row['financials'][0]['publishedAt']='2026-10-27'
    elif change=='early-financial':row['financials'][0]['period']='2024-12-31'
    elif change=='future-announcement':row['announcements'][0]['date']='2026-10-01'
    else:row['financials'][0]['raw']['SECURITY_CODE']='000001'
    state['rowHashes']['0']=b.row_hash(row);p.write_text(json.dumps(state),encoding='utf-8')
    with patch.object(b,'collect_market',return_value=valid) as fetch:out=b.run(root,{**doc,'resume':True},None)
    fetch.assert_called_once();self.assertFalse(out['rows'][0]['resumed']);self.assertEqual(out['rows'][0]['financials'],valid['financials'])
