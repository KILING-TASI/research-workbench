import copy,unittest
from buy_side_thesis import freeze,review
class ThesisTests(unittest.TestCase):
 def setUp(self):
  self.e={'id':'e1','source':'公开报告','summary':'收入增长','kind':'original','publishedAt':'2026-08-01','acquiredAt':'2026-08-02','stance':'support'}
  self.s={'entityId':'stock:example','question':'增长能否兑现为现金流？','asOf':'2026-09-01','hypotheses':[{'id':'h1','claim':'收入增长带动回款','invalidation':'回款持续落后收入','verificationMetric':'收入与经营现金流','reviewBy':'2026-11-01','evidence':[self.e]}]}
 def test_freeze_does_not_mutate_input(self):
  original=copy.deepcopy(self.s);r=freeze(self.s);self.assertEqual(original,self.s);self.assertEqual(r['snapshot']['hypotheses'][0]['status'],'unverified')
 def test_future_acquisition_excluded(self):
  self.e['acquiredAt']='2026-10-01';h=freeze(self.s)['snapshot']['hypotheses'][0];self.assertFalse(h['evidence']);self.assertEqual(len(h['excludedEvidence']),1)
 def test_future_publication_excluded(self):
  self.e.update(publishedAt='2026-10-01',acquiredAt='2026-10-02');self.assertFalse(freeze(self.s)['snapshot']['hypotheses'][0]['evidence'])
 def test_invalid_acquisition_rejected(self):
  self.e['acquiredAt']='2026-07-01'
  with self.assertRaises(ValueError):freeze(self.s)
 def test_duplicate_hypothesis_rejected(self):
  self.s['hypotheses']*=2
  with self.assertRaises(ValueError):freeze(self.s)
 def test_duplicate_evidence_rejected(self):
  self.s['hypotheses'][0]['evidence']*=2
  with self.assertRaises(ValueError):freeze(self.s)
 def test_missing_invalidation_rejected(self):
  del self.s['hypotheses'][0]['invalidation']
  with self.assertRaises(ValueError):freeze(self.s)
 def test_tampered_snapshot_rejected(self):
  r=freeze(self.s);r['snapshot']['question']='修改'
  with self.assertRaises(ValueError):review(r,{'asOf':'2026-10-05'})
 def test_missing_review_remains_unknown(self):
  r=review(freeze(self.s),{'asOf':'2026-10-05'});self.assertEqual(r['assessments'][0]['outcome'],'unverified')
 def test_assertion_requires_evidence(self):
  with self.assertRaises(ValueError):review(freeze(self.s),{'asOf':'2026-10-05','assessments':[{'hypothesisId':'h1','outcome':'supported','explanation':'测试','evidence':[]}]})
 def test_assumption_not_verification(self):
  e=copy.deepcopy(self.e);e['kind']='assumption'
  with self.assertRaises(ValueError):review(freeze(self.s),{'asOf':'2026-10-05','assessments':[{'hypothesisId':'h1','outcome':'supported','explanation':'测试','evidence':[e]}]})
 def test_review_keeps_original(self):
  r=freeze(self.s);old=copy.deepcopy(r);review(r,{'asOf':'2026-10-05','assessments':[{'hypothesisId':'h1','outcome':'contradicted','explanation':'回款没有跟上','evidence':[self.e]}]});self.assertEqual(r,old)

class LocatorTests(unittest.TestCase):
 def setUp(self):
  import tempfile,hashlib
  from pypdf import PdfWriter
  self.temp=tempfile.TemporaryDirectory();self.p=__import__('pathlib').Path(self.temp.name)/'blank.pdf'
  w=PdfWriter();w.add_blank_page(width=200,height=200)
  with self.p.open('wb') as f:w.write(f)
  self.row={'kind':'original','locator':{'path':str(self.p),'sha256':hashlib.sha256(self.p.read_bytes()).hexdigest(),'page':1}}
 def tearDown(self):self.temp.cleanup()
 def test_file_page_does_not_certify_quote(self):
  from buy_side_thesis import locate
  self.assertEqual(locate(self.row)['status'],'file-page-only')
 def test_missing_quote_visible(self):
  from buy_side_thesis import locate
  self.row['locator']['quote']='不存在的引句';self.assertEqual(locate(self.row)['status'],'quote-not-found')
 def review_with_missing_quote(self,outcome):
  self.row['locator']['quote']='不存在的引句'
  e={**self.row,'id':'e1','source':'教学PDF','summary':'教学摘要','publishedAt':'2026-08-01','acquiredAt':'2026-08-02','stance':'support'}
  s={'entityId':'stock:example','question':'教学逻辑是否兑现','asOf':'2026-09-01','hypotheses':[{'id':'h1','claim':'教学增长','invalidation':'教学失效','verificationMetric':'教学指标','reviewBy':'2026-11-01','evidence':[]}]}
  return review(freeze(s),{'asOf':'2026-10-05','assessments':[{'hypothesisId':'h1','outcome':outcome,'explanation':'教学复查','evidence':[e]}]})
 def test_missing_quote_cannot_confirm_or_contradict(self):
  for outcome in ('supported','contradicted'):
   with self.subTest(outcome=outcome),self.assertRaisesRegex(ValueError,'引句未找到'):self.review_with_missing_quote(outcome)
 def test_missing_quote_can_remain_unverified(self):
  r=self.review_with_missing_quote('unverified')
  self.assertEqual(r['assessments'][0]['evidence'][0]['locationCheck']['status'],'quote-not-found')
  self.assertEqual(r['assessments'][0]['outcome'],'unverified')
 def test_hash_change_rejected(self):
  from buy_side_thesis import locate
  self.row['locator']['sha256']='bad'
  with self.assertRaises(ValueError):locate(self.row)
 def test_page_overflow_rejected(self):
  from buy_side_thesis import locate
  self.row['locator']['page']=2
  with self.assertRaises(ValueError):locate(self.row)
 def test_bool_page_rejected(self):
  from buy_side_thesis import locate
  self.row['locator']['page']=True
  with self.assertRaises(ValueError):locate(self.row)
 def test_assumption_cannot_be_original(self):
  from buy_side_thesis import locate
  self.row['kind']='assumption'
  with self.assertRaises(ValueError):locate(self.row)

class TimingTests(unittest.TestCase):
 setUp=ThesisTests.setUp
 def test_effective_date_is_not_publication(self):
  self.e['effectiveAt']='2026-10-01';h=freeze(self.s)['snapshot']['hypotheses'][0]
  self.assertEqual(h['evidence'][0]['timingCheck']['effectiveStatus'],'not-yet-effective')
 def test_backfilled_evidence_not_historical_retention(self):
  self.e['recordedAt']='2026-10-01';e=freeze(self.s)['snapshot']['hypotheses'][0]['evidence'][0]
  self.assertEqual(e['timingCheck']['historicalRetention'],'not-demonstrated')
 def test_retention_before_acquisition_rejected(self):
  self.e['recordedAt']='2026-07-01'
  with self.assertRaises(ValueError):freeze(self.s)
 def test_declared_retention_not_certified(self):
  self.e['recordedAt']='2026-08-03';e=freeze(self.s)['snapshot']['hypotheses'][0]['evidence'][0]
  self.assertEqual(e['timingCheck']['historicalRetention'],'declared-retained-by-cutoff');self.assertIn('输入声明',e['timingCheck']['limitation'])
 def test_reused_context_visible(self):
  r=review(freeze(self.s),{'asOf':'2026-10-05','assessments':[{'hypothesisId':'h1','outcome':'unverified','explanation':'原材料复查','evidence':[self.e]}]})
  self.assertEqual(r['assessments'][0]['evidence'][0]['reviewRole'],'reused-original-context')
 def test_new_historical_material_not_original(self):
  e=copy.deepcopy(self.e);e['summary']='后来补充的历史信息';e['acquiredAt']='2026-10-01'
  r=review(freeze(self.s),{'asOf':'2026-10-05','assessments':[{'hypothesisId':'h1','outcome':'unverified','explanation':'待验证','evidence':[e]}]})
  self.assertEqual(r['assessments'][0]['evidence'][0]['reviewRole'],'newly-supplied-context')
 def test_invalid_gaps_rejected(self):
  self.s['hypotheses'][0]['gaps']='缺数据'
  with self.assertRaises(ValueError):freeze(self.s)
 def test_report_shows_opposing_evidence(self):
  from buy_side_thesis import markdown
  self.e['stance']='oppose';self.assertIn('反对材料',markdown(freeze(self.s)))
 def test_no_opposition_not_absence_of_risk(self):
  from buy_side_thesis import markdown
  self.assertIn('不代表没有反对证据',markdown(freeze(self.s)))
 def test_future_review_evidence_disclosed(self):
  from buy_side_thesis import markdown
  e=copy.deepcopy(self.e);e.update(publishedAt='2026-12-01',acquiredAt='2026-12-02')
  r=review(freeze(self.s),{'asOf':'2026-10-05','assessments':[{'hypothesisId':'h1','outcome':'unverified','explanation':'待验证','evidence':[e]}]})
  self.assertIn('未用于本次复盘',markdown(r))

class EvidenceExpiryTests(unittest.TestCase):
 setUp=ThesisTests.setUp
 def test_expired_current_evidence_excluded(self):
  self.e['applicableUntil']='2026-08-31';h=freeze(self.s)['snapshot']['hypotheses'][0];self.assertFalse(h['evidence']);self.assertIn('期限已过',h['excludedEvidence'][0]['exclusionReason'])
 def test_expiry_date_inclusive(self):
  self.e['applicableUntil']='2026-09-01';self.assertTrue(freeze(self.s)['snapshot']['hypotheses'][0]['evidence'])
 def test_withdrawn_evidence_excluded(self):
  self.e['withdrawnAt']='2026-09-01';self.assertFalse(freeze(self.s)['snapshot']['hypotheses'][0]['evidence'])
 def test_future_withdrawal_does_not_rewrite_past(self):
  self.e['withdrawnAt']='2026-10-01';self.assertTrue(freeze(self.s)['snapshot']['hypotheses'][0]['evidence'])
 def test_supersession_needs_version_and_date(self):
  self.e['supersededAt']='2026-09-01'
  with self.assertRaises(ValueError):freeze(self.s)
 def test_superseded_evidence_excluded(self):
  self.e.update(supersededAt='2026-09-01',supersededBy='e2');self.assertFalse(freeze(self.s)['snapshot']['hypotheses'][0]['evidence'])
 def test_old_expiry_recheck_preserves_snapshot(self):
  self.e['applicableUntil']='2026-09-30';f=freeze(self.s);before=copy.deepcopy(f);r=review(f,{'asOf':'2026-10-05'});self.assertEqual(f,before);self.assertTrue(r['originalEvidenceCurrentValidity'][0]['timingCheck']['reasons'])
 def test_expired_evidence_cannot_verify(self):
  e=copy.deepcopy(self.e);e['applicableUntil']='2026-09-30'
  with self.assertRaises(ValueError):review(freeze(self.s),{'asOf':'2026-10-05','assessments':[{'hypothesisId':'h1','outcome':'supported','explanation':'测试','evidence':[e]}]})

class NumericConditionTests(unittest.TestCase):
 setUp=ThesisTests.setUp
 def result(self,value=0.7,**changes):
  self.s['hypotheses'][0]['invalidationCondition']={'metric':'现金利润比','unit':'倍','periodBasis':'Q1','operator':'lt','threshold':0.8}
  o={'entityId':self.s['entityId'],'metric':'现金利润比','unit':'倍','periodBasis':'Q1','value':value,'observedAt':'2026-10-01','evidenceId':'e1'};o.update(changes)
  r=review(freeze(self.s),{'asOf':'2026-10-05','assessments':[{'hypothesisId':'h1','outcome':'unverified','explanation':'只检查阈值','observation':o,'evidence':[self.e]}]});return r['assessments'][0]
 def test_trigger_does_not_decide_outcome(self):
  r=self.result();self.assertEqual(r['conditionCheck']['status'],'threshold-met');self.assertEqual(r['outcome'],'unverified')
 def test_strict_boundary(self):self.assertEqual(self.result(0.8)['conditionCheck']['status'],'threshold-not-met')
 def test_unit_mismatch_unknown(self):self.assertEqual(self.result(unit='%')['conditionCheck']['status'],'unknown')
 def test_period_mismatch_unknown(self):self.assertEqual(self.result(periodBasis='H1')['conditionCheck']['status'],'unknown')
 def test_wrong_entity_unknown(self):self.assertEqual(self.result(entityId='stock:other')['conditionCheck']['status'],'unknown')
 def test_future_observation_unknown(self):self.assertEqual(self.result(observedAt='2026-10-06')['conditionCheck']['status'],'unknown')
 def test_missing_evidence_unknown(self):self.assertEqual(self.result(evidenceId='missing')['conditionCheck']['status'],'unknown')
 def test_invalid_number_rejected(self):
  with self.assertRaises(ValueError):self.result(float('nan'))
 def test_no_observation_unknown(self):
  self.s['hypotheses'][0]['invalidationCondition']={'metric':'现金利润比','unit':'倍','periodBasis':'Q1','operator':'lt','threshold':0.8};r=review(freeze(self.s),{'asOf':'2026-10-05'});self.assertEqual(r['assessments'][0]['conditionCheck']['status'],'unknown')

class MultiPeriodConditionTests(unittest.TestCase):
 setUp=ThesisTests.setUp
 def run_case(self,values=(0.6,0.7)):
  self.s['hypotheses'][0]['invalidationCondition']={'metric':'现金利润比','unit':'倍','periodBasis':'Q1','operator':'lt','threshold':0.8,'requiredPeriods':['2025-03-31','2026-03-31']}
  rows=[{'entityId':self.s['entityId'],'metric':'现金利润比','unit':'倍','periodBasis':'Q1','value':v,'periodEnd':p,'observedAt':'2026-10-01','evidenceId':'e1'} for p,v in zip(['2025-03-31','2026-03-31'],values)]
  return rows
 def evaluate(self,rows):
  return review(freeze(self.s),{'asOf':'2026-10-05','assessments':[{'hypothesisId':'h1','outcome':'unverified','explanation':'教学条件','observation':rows,'evidence':[self.e]}]})['assessments'][0]
 def test_all_met_not_automatic_conclusion(self):
  r=self.evaluate(self.run_case());self.assertEqual(r['conditionCheck']['status'],'threshold-met');self.assertEqual(r['outcome'],'unverified')
 def test_missing_period_unknown(self):self.assertEqual(self.evaluate(self.run_case()[:1])['conditionCheck']['status'],'unknown')
 def test_one_not_met(self):self.assertEqual(self.evaluate(self.run_case((0.6,0.9)))['conditionCheck']['status'],'threshold-not-met')
 def test_duplicate_observation_rejected(self):
  rows=self.run_case()
  with self.assertRaises(ValueError):self.evaluate(rows+[rows[0]])
 def test_unknown_period_rejected(self):
  rows=self.run_case();rows[0]['periodEnd']='2024-03-31'
  with self.assertRaises(ValueError):self.evaluate(rows)
 def test_unit_mismatch_unknown(self):
  rows=self.run_case();rows[1]['unit']='%';self.assertEqual(self.evaluate(rows)['conditionCheck']['status'],'unknown')
 def test_invalid_period_type_rejected(self):
  self.run_case();self.s['hypotheses'][0]['invalidationCondition']['requiredPeriods']=[{},'2026-03-31']
  with self.assertRaises(ValueError):freeze(self.s)
 def test_period_after_observation_rejected(self):
  rows=self.run_case();rows[0]['observedAt']='2024-01-01'
  with self.assertRaises(ValueError):self.evaluate(rows)
 def test_report_lists_each_period(self):
  from buy_side_thesis import markdown
  rows=self.run_case();r=review(freeze(self.s),{'asOf':'2026-10-05','assessments':[{'hypothesisId':'h1','outcome':'unverified','explanation':'教学条件','observation':rows,'evidence':[self.e]}]});m=markdown(r);self.assertIn('2025-03-31',m);self.assertIn('2026-03-31',m)

class EvidenceImpactTests(unittest.TestCase):
 setUp=ThesisTests.setUp
 def spec(self):return {'asOf':'2026-10-05','evidenceUpdates':[{'hypothesisId':'h1','evidenceId':'e1','changes':{'withdrawnAt':'2026-10-01'},'publishedAt':'2026-10-01','acquiredAt':'2026-10-02','reason':'教学撤回','source':'用户提供的更正说明'}]}
 def test_update_preserves_first_snapshot(self):
  f=freeze(self.s);old=copy.deepcopy(f);r=review(f,self.spec());self.assertEqual(f,old);self.assertEqual(len(r['evidenceImpact']),1)
 def test_future_change_not_current_impact(self):
  s=self.spec();s['evidenceUpdates'][0]['changes']['withdrawnAt']='2026-11-01';self.assertFalse(review(freeze(self.s),s)['evidenceImpact'])
 def test_unknown_reference_rejected(self):
  s=self.spec();s['evidenceUpdates'][0]['evidenceId']='missing'
  with self.assertRaises(ValueError):review(freeze(self.s),s)
 def test_cannot_change_original_amount_or_summary(self):
  s=self.spec();s['evidenceUpdates'][0]['changes']={'summary':'改写历史'}
  with self.assertRaises(ValueError):review(freeze(self.s),s)
 def test_duplicate_update_rejected(self):
  s=self.spec();s['evidenceUpdates']*=2
  with self.assertRaises(ValueError):review(freeze(self.s),s)
 def test_source_required(self):
  s=self.spec();del s['evidenceUpdates'][0]['source']
  with self.assertRaises(ValueError):review(freeze(self.s),s)
 def test_report_explains_impact(self):
  from buy_side_thesis import markdown
  m=markdown(review(freeze(self.s),self.spec()));self.assertIn('需要重新核对的判断',m);self.assertIn('首次判断保留',m)
 def test_unchanged_evidence_not_impacted(self):self.assertFalse(review(freeze(self.s),{'asOf':'2026-10-05'})['evidenceImpact'])
 def test_updated_withdrawal_blocks_reused_confirmation(self):
  s=self.spec();s['assessments']=[{'hypothesisId':'h1','outcome':'supported','explanation':'复用','evidence':[self.e]}]
  with self.assertRaises(ValueError):review(freeze(self.s),s)

class EvidenceTimingConsistencyTests(unittest.TestCase):
 setUp=ThesisTests.setUp
 def test_expiry_before_publication_rejected(self):
  self.e['applicableUntil']='2026-07-31'
  with self.assertRaises(ValueError):freeze(self.s)
 def test_expiry_before_effective_rejected(self):
  self.e.update(effectiveAt='2026-10-01',applicableUntil='2026-09-30')
  with self.assertRaises(ValueError):freeze(self.s)
 def test_future_update_visible_in_current_evidence(self):
  s={'asOf':'2026-10-05','evidenceUpdates':[{'hypothesisId':'h1','evidenceId':'e1','changes':{'withdrawnAt':'2026-11-01'},'publishedAt':'2026-10-01','acquiredAt':'2026-10-02','reason':'教学','source':'教学声明'}],'assessments':[{'hypothesisId':'h1','outcome':'unverified','explanation':'教学','evidence':[self.e]}]}
  r=review(freeze(self.s),s);self.assertEqual(r['assessments'][0]['evidence'][0]['timingCheck']['withdrawnAt'],'2026-11-01')
 def test_current_updated_expiry_consistent(self):
  s={'asOf':'2026-10-05','evidenceUpdates':[{'hypothesisId':'h1','evidenceId':'e1','changes':{'applicableUntil':'2026-10-05'},'publishedAt':'2026-10-01','acquiredAt':'2026-10-02','reason':'教学','source':'教学声明'}],'assessments':[{'hypothesisId':'h1','outcome':'unverified','explanation':'教学','evidence':[self.e]}]}
  r=review(freeze(self.s),s);self.assertEqual(r['assessments'][0]['evidence'][0]['timingCheck']['applicableUntil'],'2026-10-05');self.assertFalse(r['evidenceImpact'])

class UpdateAvailabilityTests(unittest.TestCase):
 setUp=ThesisTests.setUp
 def spec(self):
  return {'asOf':'2026-10-05','evidenceUpdates':[{'hypothesisId':'h1','evidenceId':'e1','changes':{'withdrawnAt':'2026-10-01'},'reason':'教学更正','source':'教学原文','publishedAt':'2026-10-01','acquiredAt':'2026-10-02'}]}
 def test_late_acquisition_not_backdated(self):
  s=self.spec();s['evidenceUpdates'][0]['acquiredAt']='2026-10-06';r=review(freeze(self.s),s);self.assertFalse(r['evidenceImpact']);self.assertEqual(len(r['excludedEvidenceUpdates']),1)
 def test_missing_dates_deferred(self):
  s=self.spec();del s['evidenceUpdates'][0]['publishedAt'];r=review(freeze(self.s),s);self.assertFalse(r['evidenceImpact']);self.assertTrue(r['excludedEvidenceUpdates'])
 def test_acquisition_before_publication_rejected(self):
  s=self.spec();s['evidenceUpdates'][0]['acquiredAt']='2026-09-30'
  with self.assertRaises(ValueError):review(freeze(self.s),s)
 def test_known_on_cutoff_applies(self):
  s=self.spec();s['evidenceUpdates'][0]['acquiredAt']='2026-10-05';self.assertTrue(review(freeze(self.s),s)['evidenceImpact'])
 def test_duplicate_deferred_rejected(self):
  s=self.spec();del s['evidenceUpdates'][0]['publishedAt'];s['evidenceUpdates']*=2
  with self.assertRaises(ValueError):review(freeze(self.s),s)
