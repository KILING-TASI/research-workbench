import unittest,tempfile,json
from unittest.mock import patch
from pathlib import Path
from research_workflow import context,run_template
class Tests(unittest.TestCase):
 def spec(self,p,dividend='price_only',asof='2026-10-05'):
  ctx=context(dict(sessionId='review',baseCurrency='USD',frequency='trading_day',dividendTreatment=dividend,asOf=asof,benchmark=None,riskFreeRate=.01,annualization=252,missingData='common_dates',timezone='UTC'))
  for name,obj in [('context',ctx),('archive',dict(asOf='2026-10-05',series=[])),('input',dict(archive=str(p/'archive.json')))]: (p/(name+'.json')).write_text(json.dumps(obj),encoding='utf8')
  return dict(template='macro-observation-review',contextPath=str(p/'context.json'),inputPath=str(p/'input.json'),outDir=str(p/'out'))
 def test_total_return_context_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)
   with self.assertRaises(ValueError):run_template(self.spec(p,'reinvest'),p)
   self.assertFalse((p/'out').exists())
 def test_cutoff_mismatch_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)
   with self.assertRaises(ValueError):run_template(self.spec(p,asof='2026-10-04'),p)
   self.assertFalse((p/'out').exists())
 def test_scenario_mode_mismatch_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);s=self.spec(p);s.update(template='industry-scenario-review',mode='exit')
   with self.assertRaises(ValueError):run_template(s,p)
   self.assertFalse((p/'out').exists())
 @patch('macro_asset_observation.build')
 def test_unverified_publication_and_raw_status_are_gaps(self,m):
  m.return_value=dict(sourceBindings=[dict(id='DGS10',rawFile=None,status='raw-source-not-bound')],missingSeries=[],assetWindows=[],sources=[dict(id='DGS10',publicationDatesVerified=False)],limitations=[])
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);r=run_template(self.spec(p),p)
   self.assertEqual(r['status'],'calculated-with-gaps')
   self.assertTrue(any('发布日期未核验' in g['reason'] for g in r['gaps']))
   self.assertTrue(any('原始观测未完整核对' in g['reason'] for g in r['gaps']))
 @patch('macro_asset_observation.build')
 def test_joint_window_gap_propagates(self,m):
  m.return_value=dict(sourceBindings=[],missingSeries=[],assetWindows=[],sources=[],limitations=[],dailyRateAssetAlignment=[dict(status='insufficient-common-observations',observationIntervals=20,includedSeries=['DGS10','TLT'])])
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);r=run_template(self.spec(p),p)
   self.assertEqual(r['status'],'calculated-with-gaps');self.assertEqual(r['gaps'][0]['seriesIds'],['DGS10','TLT']);self.assertIn('20个共同观测间隔',r['gaps'][0]['reason'])
 @patch('research_report_reading.build')
 def test_unread_original_participates_in_version_lineage(self,m):
  m.return_value=dict(analyses=[dict(reportId='a',gaps=[])],sourceFiles=[dict(reportId='a'),dict(reportId='b')],unreadReports=['b'],limitations=[])
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);spec=self.spec(p);spec['template']='report-reading-review'
   pdf=p/'original.pdf';pdf.write_bytes(b'archive-source')
   (p/'archive.json').write_text(json.dumps(dict(asOf='2026-10-05',reports=[dict(id=i,pdfPath=str(pdf)) for i in ['a','b']])),encoding='utf8')
   r=run_template(spec,p)
   self.assertEqual(r['status'],'calculated-with-gaps')
   self.assertTrue(any(f['role']=='unread-original-pdf' for f in r['lineage']['files']))
 @patch('macro_asset_observation.build')
 def test_monthly_gap_propagates_even_with_verified_sources(self,m):
  m.return_value=dict(sourceBindings=[],missingSeries=[],assetWindows=[],sources=[],limitations=[],monthlyAlignment=dict(status='common-observation-month-not-publication-aligned',monthGaps=[dict(month='2026-09',missingSeries=['INDPRO'])]))
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);r=run_template(self.spec(p),p)
   self.assertEqual(r['status'],'calculated-with-gaps');self.assertEqual(r['gaps'][0]['month'],'2026-09');self.assertEqual(r['gaps'][0]['seriesIds'],['INDPRO'])
 @patch('macro_asset_observation.build')
 def test_no_common_month_is_gap(self,m):
  m.return_value=dict(sourceBindings=[],missingSeries=[],assetWindows=[],sources=[],limitations=[],monthlyAlignment=dict(status='no-common-month'))
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);r=run_template(self.spec(p),p)
   self.assertEqual(r['status'],'calculated-with-gaps');self.assertIn('没有共同所属月',r['gaps'][0]['reason'])
 @patch('research_report_reading.build')
 def test_prepared_diligence_remains_unresolved(self,m):
  question=dict(question='回款如何验证？',respondent='customer',requestedEvidence='付款记录',status='question-prepared-not-interviewed')
  m.return_value=dict(analyses=[dict(reportId='a',gaps=[],dueDiligenceQuestions=[question])],sourceFiles=[],unreadReports=[],limitations=[])
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);spec=self.spec(p);spec['template']='report-reading-review';(p/'archive.json').write_text(json.dumps(dict(asOf='2026-10-05',reports=[])),encoding='utf-8');r=run_template(spec,p)
   self.assertEqual(r['status'],'calculated-with-gaps');self.assertEqual(r['gaps'][0]['status'],'question-prepared-not-interviewed');self.assertEqual(r['gaps'][0]['requestedEvidence'],'付款记录')
 def test_event_review_rejects_total_return_before_output(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);s=self.spec(p,'reinvest');s['template']='event-price-review';(p/'input.json').write_text(json.dumps(dict(archive=str(p/'archive.json'),assetId='A',comparisonId='B')),encoding='utf-8')
   with self.assertRaisesRegex(ValueError,'价格口径'):run_template(s,p)
   self.assertFalse((p/'out').exists())
 @patch('macro_asset_observation.build')
 def test_hypothesis_and_asynchronous_observations_remain_gaps(self,m):
  m.return_value=dict(sourceBindings=[],missingSeries=[],assetWindows=[],sources=[],limitations=[],transmissionHypotheses=[dict(mechanism='利率可能影响价格',factorIds=['DGS10'],assetIds=['TLT'],observations=[dict(latest=dict(date='2026-01-01'))],assetObservations=[dict(id='TLT',latest=dict(date='2026-01-02'))])])
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);r=run_template(self.spec(p),p)
   self.assertEqual(r['status'],'calculated-with-gaps');self.assertTrue(any('未因果验证' in g['reason'] for g in r['gaps']));self.assertTrue(any('日期不同' in g['reason'] for g in r['gaps']))

class HoldingsContextTests(unittest.TestCase):
 def test_context_mismatch_blocks_before_original_work(self):
  for field,value in [('asOf','2026-10-04'),('currency','USD')]:
   with self.subTest(field=field),tempfile.TemporaryDirectory() as d,patch('holdings_snapshot_review.run') as calculation:
    p=Path(d);ctx=context(dict(sessionId='holdings',baseCurrency='CNY',frequency='trading_day',dividendTreatment='reinvest',asOf='2026-10-05',benchmark=None,riskFreeRate=.01,annualization=252,missingData='common_dates',timezone='UTC'))
    holdings=dict(asOf='2026-10-05',currency='CNY');holdings[field]=value
    for name,obj in [('context',ctx),('holdings',holdings),('input',dict(holdingsPath=str(p/'holdings.json')))]: (p/(name+'.json')).write_text(json.dumps(obj))
    with self.assertRaises(ValueError):run_template(dict(template='holdings-snapshot-review',contextPath=str(p/'context.json'),inputPath=str(p/'input.json'),outDir=str(p/'out')),p)
    calculation.assert_not_called();self.assertFalse((p/'out').exists())

if __name__=='__main__':unittest.main()
