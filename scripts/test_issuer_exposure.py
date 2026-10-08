import unittest,copy
from investment_intent import issuer_exposure,analyze
class IssuerExposureTests(unittest.TestCase):
 def setUp(self):
  from test_investment_intent import IntentTests
  t=IntentTests();t.setUp();self.s=t.s
  self.s['holdings'][0].update(assetId='stock:a',assetClass='stock',availableBy='2026-10-05')
  self.s['holdings'][1].update(assetId='bond:b',assetClass='bond')
  self.s['intent']['maximumIssuerWeightPct']=80
  self.s['issuerRelations']=[{'assetId':key,'issuerId':'issuer:one','source':'教学发行文件','publishedAt':'2026-09-01','acquiredAt':'2026-09-02'} for key in ['stock:a','bond:b']]
 def test_same_issuer_combines(self):
  r=issuer_exposure(self.s);self.assertEqual(r['groups'][0]['weightPct'],'100');self.assertEqual(r['status'],'fail')
 def test_unknown_not_zero_or_pass(self):
  self.s['issuerRelations']=self.s['issuerRelations'][:1];r=issuer_exposure(self.s);self.assertEqual(r['status'],'unknown');self.assertEqual(len(r['unknown']),1)
 def test_late_relation_excluded(self):
  self.s['issuerRelations'][0]['acquiredAt']='2026-10-06';r=issuer_exposure(self.s);self.assertEqual(len(r['excludedRelations']),1)
 def test_duplicate_relation_rejected(self):
  self.s['issuerRelations']*=2
  with self.assertRaises(ValueError):issuer_exposure(self.s)
 def test_fund_manager_not_underlying_issuer(self):
  self.s['holdings'][1]['assetClass']='fund'
  with self.assertRaises(ValueError):issuer_exposure(self.s)
 def test_distinct_issuers_can_pass(self):
  self.s['issuerRelations'][1]['issuerId']='issuer:two';self.assertEqual(issuer_exposure(self.s)['status'],'pass')
 def test_no_cap_keeps_unknown(self):
  del self.s['intent']['maximumIssuerWeightPct'];self.assertEqual(issuer_exposure(self.s)['status'],'unknown')
 def test_declared_coverage_not_original_verification(self):
  r=issuer_exposure(self.s);self.assertEqual(r['knownCoveragePct'],'100');coverage={x['status']:x for x in r['evidenceCoverage']};self.assertEqual(coverage['not-located']['portfolioWeightPct'],'100');self.assertEqual(coverage['quote-located']['portfolioWeightPct'],'0')
 def test_unknown_direct_upper_bound_not_actual_failure(self):
  self.s['issuerRelations']=self.s['issuerRelations'][:1];r=issuer_exposure(self.s);self.assertEqual(r['status'],'unknown');self.assertEqual(r['groups'][0]['directWeightUpperPct'],'100');self.assertTrue(r['groups'][0]['couldExceedFromUnknownDirect']);self.assertEqual(r['exceededIssuers'],[])
 def test_fund_unknown_not_added_to_direct_bound(self):
  self.s['issuerRelations']=self.s['issuerRelations'][:1];self.s['holdings'][1]['assetClass']='fund';r=issuer_exposure(self.s);self.assertEqual(r['directBounds']['unknownDirectValue'],'0');self.assertEqual(r['groups'][0]['directWeightUpperPct'],r['groups'][0]['weightPct']);self.assertEqual(r['status'],'unknown')
 def test_complete_direct_bounds_equal_known_weights(self):
  r=issuer_exposure(self.s);self.assertEqual(r['directBounds']['unknownDirectValue'],'0');self.assertEqual(r['groups'][0]['directWeightUpperPct'],'100')
 def test_excluded_relation_not_in_evidence_coverage(self):
  self.s['issuerRelations'][0]['withdrawnAt']='2026-10-01';r=issuer_exposure(self.s)
  from decimal import Decimal
  self.assertEqual(sum(Decimal(x['marketValue']) for x in r['evidenceCoverage'])+Decimal(r['unknownValue']),Decimal('100'))
 def test_does_not_mutate_inputs(self):
  old=copy.deepcopy(self.s);issuer_exposure(self.s);self.assertEqual(old,self.s)

class IssuerLocatorTests(unittest.TestCase):
 setUp=IssuerExposureTests.setUp
 def test_no_locator_remains_declared(self):
  r=issuer_exposure(self.s);self.assertEqual(r['groups'][0]['assets'][0]['locationCheck']['status'],'not-located')
 def test_wrong_quote_keeps_unknown(self):
  import tempfile,hashlib
  from pathlib import Path
  from pypdf import PdfWriter
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'blank.pdf';w=PdfWriter();w.add_blank_page(width=200,height=200)
   with p.open('wb') as f:w.write(f)
   self.s['issuerRelations'][0]['locator']={'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'page':1,'quote':'不存在'}
   r=issuer_exposure(self.s);self.assertTrue(r['unknown']);self.assertEqual(r['status'],'unknown');self.assertIn('引句',r['excludedRelations'][0]['reason'])
 def test_hash_mismatch_rejected(self):
  self.s['issuerRelations'][0]['locator']={'path':'missing.pdf','sha256':'bad','page':1}
  with self.assertRaises(ValueError):issuer_exposure(self.s)

class RelationBundleTests(unittest.TestCase):
 def test_move_and_remove_original_replays(self):
  import tempfile,hashlib,shutil
  from pathlib import Path
  from pypdf import PdfWriter
  from buy_side_bundle import build,replay
  t=IssuerExposureTests();t.setUp();s=t.s;s['intent'].update(allowedAssetClasses=['stock','bond'],minimumCash=0);s['scenarios'][0]['returnShocksPct']={'stock:a':-10,'bond:b':-10}
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'source.pdf';w=PdfWriter();w.add_blank_page(width=200,height=200)
   with p.open('wb') as f:w.write(f)
   s['issuerRelations'][0]['locator']={'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'page':1}
   out=Path(d)/'bundle';build(s,out,include_originals=True);moved=Path(d)/'moved';shutil.move(out,moved);p.unlink()
   self.assertEqual(replay(moved)['status'],'replayed-identical')
   next((moved/'sources').glob('*.pdf')).write_bytes(b'changed')
   with self.assertRaises(ValueError):replay(moved)

class IssuerRoleTests(unittest.TestCase):
 setUp=IssuerExposureTests.setUp
 def test_trustee_not_issuer(self):
  self.s['issuerRelations'][0]['relationRole']='trustee'
  with self.assertRaises(ValueError):issuer_exposure(self.s)
 def test_underwriter_not_issuer(self):
  self.s['issuerRelations'][0]['relationRole']='underwriter'
  with self.assertRaises(ValueError):issuer_exposure(self.s)
 def test_explicit_issuer_accepted(self):
  self.s['issuerRelations'][0]['relationRole']='issuer';self.assertEqual(issuer_exposure(self.s)['status'],'fail')

class IssuerTemporalTests(unittest.TestCase):
 setUp=IssuerExposureTests.setUp
 def test_future_effective_unknown(self):
  self.s['issuerRelations'][0]['effectiveAt']='2026-11-01';r=issuer_exposure(self.s);self.assertEqual(r['status'],'unknown');self.assertEqual(r['knownCoveragePct'],'70.0')
 def test_withdrawn_relation_unknown(self):
  self.s['issuerRelations'][0]['withdrawnAt']='2026-10-01';self.assertTrue(issuer_exposure(self.s)['unknown'])
 def test_superseded_relation_unknown(self):
  self.s['issuerRelations'][0].update(supersededAt='2026-10-01',supersededBy='new-version');self.assertTrue(issuer_exposure(self.s)['excludedRelations'])
 def test_expiry_before_effective_rejected(self):
  self.s['issuerRelations'][0].update(effectiveAt='2026-11-01',applicableUntil='2026-10-31')
  with self.assertRaises(ValueError):issuer_exposure(self.s)
 def test_zero_total_rejected(self):
  for h in self.s['holdings']:h['marketValue']=0
  with self.assertRaises(ValueError):issuer_exposure(self.s)
 def test_duplicate_holdings_rejected(self):
  self.s['holdings']*=2
  with self.assertRaises(ValueError):issuer_exposure(self.s)
