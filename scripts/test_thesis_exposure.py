import unittest,copy,tempfile
from pathlib import Path
from buy_side_bundle import thesis_exposure,build,replay
from buy_side_thesis import freeze
class ThesisExposureTests(unittest.TestCase):
 def setUp(self):
  from test_investment_intent import IntentTests
  from test_buy_side_thesis import ThesisTests
  i=IntentTests();i.setUp();t=ThesisTests();t.setUp();self.i=i.s;t.s['entityId']='fund:example';self.t=freeze(t.s)
 def test_direct_weight(self):
  r=thesis_exposure(self.i,self.t);self.assertEqual(r['portfolioWeightPct'],70);self.assertEqual(r['linkedMarketValue'],70)
 def test_unknown_entity_rejected(self):
  self.i['holdings'][1]['assetId']='fund:other'
  with self.assertRaises(ValueError):thesis_exposure(self.i,self.t)
 def test_snapshot_change_rejected(self):
  self.t['snapshot']['question']='changed'
  with self.assertRaises(ValueError):thesis_exposure(self.i,self.t)
 def test_bundle_replays_link(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'bundle';r=build(self.i,p,thesis=self.t);self.assertIn('thesisExposure',r);self.assertEqual(replay(p)['status'],'replayed-identical');self.assertIn('与组合资金的联系',(p/'研究包.md').read_text('utf-8'))

class ThesisCurrentEvidenceTests(unittest.TestCase):
 setUp=ThesisExposureTests.setUp
 def changed(self,**changes):
  from buy_side_thesis import digest
  self.t['snapshot']['hypotheses'][0]['evidence'][0].update(changes);self.t['snapshotSha256']=digest(self.t['snapshot'])
 def test_expired_evidence_visible(self):
  self.changed(applicableUntil='2026-09-30');r=thesis_exposure(self.i,self.t);self.assertTrue(r['hypotheses'][0]['evidenceNeedsRecheck'])
 def test_future_withdrawal_keeps_current(self):
  self.changed(withdrawnAt='2026-11-01');self.assertFalse(thesis_exposure(self.i,self.t)['hypotheses'][0]['evidenceNeedsRecheck'])
 def test_no_evidence_requires_recheck(self):
  from buy_side_thesis import digest
  self.t['snapshot']['hypotheses'][0]['evidence']=[];self.t['snapshotSha256']=digest(self.t['snapshot']);self.assertTrue(thesis_exposure(self.i,self.t)['hypotheses'][0]['evidenceNeedsRecheck'])
 def test_snapshot_immutable_and_bundle_replay(self):
  self.changed(applicableUntil='2026-09-30');old=copy.deepcopy(self.t)
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'bundle';build(self.i,p,thesis=self.t);self.assertEqual(replay(p)['status'],'replayed-identical');self.assertIn('当前依据需要重查',(p/'研究包.md').read_text('utf-8'))
  self.assertEqual(self.t,old)
