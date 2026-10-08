import unittest,copy
from multi_intent import allocate
class MultiIntentTests(unittest.TestCase):
 def setUp(self):
  from test_investment_intent import IntentTests
  t=IntentTests();t.setUp();i=copy.deepcopy(t.s['intent']);i['allowedAssetClasses']=['cash'];i['maximumAssetWeightPct']=100;i['minimumCash']=0
  j=copy.deepcopy(i);j.update(id='i2',purpose='购房资金')
  self.s={'asOf':t.s['asOf'],'currency':'CNY','holdings':t.s['holdings'],'intents':[{'intent':i,'allocations':[{'assetId':'cash:cny','marketValue':10}]},{'intent':j,'allocations':[{'assetId':'cash:cny','marketValue':20}]}]}
 def test_exact_split_not_double_count(self):
  r=allocate(self.s);self.assertEqual([x['result']['totalValue'] for x in r['intents']],['10','20']);self.assertEqual(r['unallocated'][0]['marketValue'],'70')
 def test_overallocation_rejected(self):
  self.s['intents'][1]['allocations'][0]['marketValue']=21
  with self.assertRaises(ValueError):allocate(self.s)
 def test_no_implicit_unallocated_cash(self):
  self.s['intents'][0]['cashNeeds']=[{'date':'2027-10-05','amount':11}];self.assertEqual(allocate(self.s)['intents'][0]['result']['status'],'constraints-not-met')
 def test_duplicate_intent_rejected(self):
  self.s['intents'][1]['intent']['id']='i1'
  with self.assertRaises(ValueError):allocate(self.s)
 def test_duplicate_source_rejected(self):
  self.s['holdings']*=2
  with self.assertRaises(ValueError):allocate(self.s)
 def test_different_currency_rejected(self):
  self.s['intents'][1]['intent']['currency']='USD'
  with self.assertRaises(ValueError):allocate(self.s)
 def test_input_not_mutated(self):
  old=copy.deepcopy(self.s);allocate(self.s);self.assertEqual(self.s,old)
 def test_report_keeps_issuer_evidence_and_local_denominator(self):
  import tempfile
  from pathlib import Path
  from multi_intent import export
  s=copy.deepcopy(self.s);s['holdings'][0].update(assetId='stock:a',assetClass='stock')
  for entry in s['intents']:
   entry['intent']['allowedAssetClasses']=['stock'];entry['intent']['maximumIssuerWeightPct']=100;entry['allocations'][0]['assetId']='stock:a'
  s['issuerRelations']=[dict(assetId='stock:a',issuerId='issuer:one',source='教学资料',publishedAt='2026-09-01',acquiredAt='2026-09-02')]
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'report';export(allocate(s),p);text=(p/'资金用途分组.md').read_text('utf-8')
   self.assertEqual(text.count('### 发行人关联与原文依据'),2);self.assertIn('未定位原文',text);self.assertIn('不是全账户比例',text)

class MultiIntentReplayTests(unittest.TestCase):
 setUp=MultiIntentTests.setUp
 def test_moved_package_replays(self):
  import tempfile,shutil
  from pathlib import Path
  from multi_intent import build,replay
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'package';build(self.s,p);m=Path(d)/'moved';shutil.move(p,m);self.assertEqual(replay(m)['status'],'replayed-identical')
 def test_modified_input_rejected(self):
  import tempfile
  from pathlib import Path
  from multi_intent import build,replay
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'package';build(self.s,p);(p/'input.json').write_text('{}','utf-8')
   with self.assertRaises(ValueError):replay(p)
 def test_missing_report_rejected(self):
  import tempfile
  from pathlib import Path
  from multi_intent import build,replay
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'package';build(self.s,p);(p/'资金用途分组.html').unlink()
   with self.assertRaises(ValueError):replay(p)

class MultiIntentRelationValidationTests(unittest.TestCase):
 setUp=MultiIntentTests.setUp
 def test_unknown_relation_not_silently_dropped(self):
  self.s['issuerRelations']=[{'assetId':'stock:missing'}]
  with self.assertRaises(ValueError):allocate(self.s)
 def test_duplicate_global_relation_rejected(self):
  self.s['issuerRelations']=[{'assetId':'fund:example'},{'assetId':'fund:example'}]
  with self.assertRaises(ValueError):allocate(self.s)
 def test_invalid_relation_list_rejected(self):
  self.s['issuerRelations']={}
  with self.assertRaises(ValueError):allocate(self.s)
 def test_report_leads_with_unmet_purpose(self):
  import tempfile
  from pathlib import Path
  from multi_intent import build
  self.s['intents'][0]['cashNeeds']=[{'date':'2027-10-05','amount':11}]
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'package';build(self.s,p);m=(p/'资金用途分组.md').read_text('utf-8');self.assertLess(m.index('目前不满足所给约束'),m.index('## 教育资金'))

class MultiIntentOriginalTests(unittest.TestCase):
 def test_move_without_source_and_tamper_rejection(self):
  import tempfile,hashlib,shutil
  from pathlib import Path
  from pypdf import PdfWriter
  from multi_intent import build,replay
  from test_issuer_exposure import IssuerExposureTests
  t=IssuerExposureTests();t.setUp();s=t.s;s['intent'].update(allowedAssetClasses=['stock','bond'],minimumCash=0)
  multi={'asOf':s['asOf'],'currency':'CNY','holdings':s['holdings'],'issuerRelations':s['issuerRelations'],'intents':[{'intent':s['intent'],'allocations':[{'assetId':'stock:a','marketValue':30},{'assetId':'bond:b','marketValue':70}]}]}
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'raw.pdf';w=PdfWriter();w.add_blank_page(width=200,height=200)
   with p.open('wb') as f:w.write(f)
   multi['issuerRelations'][0]['locator']={'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'page':1}
   package=Path(d)/'package';build(multi,package,True);moved=Path(d)/'moved';shutil.move(package,moved);p.unlink();self.assertEqual(replay(moved)['status'],'replayed-identical')
   next((moved/'sources').glob('*.pdf')).write_bytes(b'changed')
   with self.assertRaises(ValueError):replay(moved)

class SharedScenarioTests(unittest.TestCase):
 setUp=MultiIntentTests.setUp
 def shared(self):self.s['sharedScenarios']=[{'name':'统一冲击','returnShocksPct':{'cash:cny':-20,'fund:example':-30}}]
 def test_same_shock_each_purpose(self):
  self.shared();r=allocate(self.s);self.assertTrue(all(x['allocatedInput']['scenarios'][0]['returnShocksPct']=={'cash:cny':-20} for x in r['intents']))
 def test_no_overwrite_existing_scenario(self):
  self.shared();self.s['intents'][0]['scenarios']=[{'name':'自有情景'}]
  with self.assertRaises(ValueError):allocate(self.s)
 def test_unknown_global_asset_rejected(self):
  self.shared();self.s['sharedScenarios'][0]['returnShocksPct']['missing']=0
  with self.assertRaises(ValueError):allocate(self.s)
 def test_missing_shock_keeps_unknown(self):
  self.shared();del self.s['sharedScenarios'][0]['returnShocksPct']['cash:cny'];r=allocate(self.s);self.assertTrue(all(x['result']['status']=='needs-data' for x in r['intents']))
 def test_duplicate_name_rejected(self):
  self.shared();self.s['sharedScenarios']*=2
  with self.assertRaises(ValueError):allocate(self.s)
 def test_unallocated_invalid_shock_not_hidden(self):
  self.shared();self.s['sharedScenarios'][0]['returnShocksPct']['fund:example']=-101
  with self.assertRaises(ValueError):allocate(self.s)
