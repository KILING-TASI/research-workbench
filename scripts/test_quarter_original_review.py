import unittest
from quarter_original_review import review
class IdentityTests(unittest.TestCase):
 def test_changed_or_missing_method_version_requires_review(self):
  import tempfile,json
  from pathlib import Path
  from unittest.mock import patch
  from quarter_original_review import method_versions,verified_saved_result
  versions=method_versions()
  self.assertIn('company_report_batch.py',versions)
  changed=dict(versions,**{'company_report_batch.py':'old-parser'})
  with tempfile.TemporaryDirectory() as d,patch('quarter_original_review.load_inputs') as loader:
   p=Path(d)/'saved.json'
   for v in [None,changed]:
    p.write_text(json.dumps(dict(input={},methodVersions=v)))
    with self.assertRaisesRegex(ValueError,'方法版本'):verified_saved_result(p,{}, {},'2026-06-30')
   loader.assert_not_called()
 def report(self,text,period='2026-06-30'):
  return dict(period=period,pages=[dict(text=text)])
 def test_title_without_year_character(self):
  from quarter_original_review import report_identity_confirmed
  self.assertTrue(report_identity_confirmed(self.report('工商银行 601398 2026半年度报告'),'601398'))
 def test_short_quarter_title(self):
  from quarter_original_review import report_identity_confirmed
  self.assertTrue(report_identity_confirmed(self.report('证券代码600036 2026年一季度报告','2026-03-31'),'600036'))
 def test_wrong_period_or_code_rejected(self):
  from quarter_original_review import report_identity_confirmed
  for text in ['601398 2025半年度报告','601399 2026半年度报告','16013980 2026半年度报告']:
   self.assertFalse(report_identity_confirmed(self.report(text),'601398'))
 def test_late_reference_is_not_identity(self):
  from quarter_original_review import report_identity_confirmed
  r=self.report('正文');r['pages']=r['pages']*12+[dict(text='601398 2026半年度报告')]
  self.assertFalse(report_identity_confirmed(r,'601398'))
class Tests(unittest.TestCase):
 def inputs(self):
  periods=['2026-06-30','2026-03-31','2025-06-30','2025-03-31']
  vals=[100,40,80,30]
  rows=[dict(period=p,publishedAt=p,currency='CNY',raw=dict(SECURITY_CODE='600690',SECUCODE='600690.SH',ORG_TYPE='通用',OPERATE_INCOME=v)) for p,v in zip(periods,vals)]
  a=dict(code='600690',asOf='2026-10-05',tables={k:dict(rows=rows,sources=[]) for k in ['income','balance','cashflow']})
  meta=dict(scope='consolidated',currency='CNY',unit='元',classificationVersion='test')
  reports=[dict(code='600690',asOf=a['asOf'],period=p,parseStatus='parsed',pages=[dict(page=1,text=f'合并利润表\n单位：元\n营业收入 {v}.00 1.00\n母公司利润表')]) for p,v in zip(periods,vals)]
  return a,meta,reports
 def test_all_difference_inputs_required(self):
  a,m,r=self.inputs();f=review(a,m,'2026-06-30',r)['fields'][0]
  self.assertEqual(f['parts']['current']['value'],60);self.assertEqual(f['parts']['yoy']['value'],50)
  self.assertTrue(all(x['status']=='supported-inputs-matched' for x in f['parts'].values()))
  f=review(a,m,'2026-06-30',r[:2])['fields'][0]
  self.assertEqual(f['parts']['current']['status'],'supported-inputs-matched');self.assertEqual(f['parts']['yoy']['status'],'not-verified')
 def test_changed_prior_amount_not_verified(self):
  a,m,r=self.inputs();r[1]['pages'][0]['text']=r[1]['pages'][0]['text'].replace('40.00','41.00')
  f=review(a,m,'2026-06-30',r)['fields'][0]
  self.assertEqual(f['parts']['current']['status'],'not-verified');self.assertEqual(f['parts']['qoq']['status'],'not-verified')
 def test_duplicate_period_rejected(self):
  a,m,r=self.inputs()
  with self.assertRaises(ValueError):review(a,m,'2026-06-30',r+[r[0]])
 def test_restatement_kept(self):
  a,m,r=self.inputs();r[0]['pages'].append(dict(page=2,text='本报告期比较期间财务数据追溯调整'))
  result=review(a,m,'2026-06-30',r);self.assertTrue(result['comparabilityWarnings']);self.assertEqual(result['fields'][0]['parts']['current']['status'],'supported-inputs-matched-with-comparability-warning')
 def test_unrelated_period_warning_not_applied_to_current_inputs(self):
  a,m,r=self.inputs();r[2]['pages'].append(dict(page=2,text='本报告期比较期间财务数据追溯调整'))
  result=review(a,m,'2026-06-30',r);parts=result['fields'][0]['parts']
  self.assertTrue(result['comparabilityWarnings'])
  self.assertEqual(parts['current']['status'],'supported-inputs-matched');self.assertEqual(parts['current']['comparabilityWarnings'],[])
  self.assertEqual(parts['yoy']['status'],'supported-inputs-matched-with-comparability-warning')
  self.assertEqual(parts['yoy']['comparabilityWarnings'][0]['period'],'2025-06-30')
  self.assertEqual(parts['qoq']['status'],'supported-inputs-matched')
 def test_late_scope_note_reaches_matched_quarter_inputs(self):
  a,m,r=self.inputs()
  r[0]['pages'].append(dict(page=174,text='其他原因的合并范围变动\n√适用 □不适用\n本期新设子公司，金额影响未量化。'))
  result=review(a,m,'2026-06-30',r)
  warning=result['comparabilityWarnings'][0]
  self.assertEqual(warning['kind'],'other-consolidation-scope-change-disclosed')
  self.assertEqual(warning['page'],174)
  self.assertEqual(warning['period'],'2026-06-30')
  self.assertEqual(result['fields'][0]['parts']['current']['value'],60)
  self.assertEqual(result['fields'][0]['parts']['current']['status'],'supported-inputs-matched-with-comparability-warning')
 def test_inactive_scope_note_does_not_downgrade_matched_inputs(self):
  a,m,r=self.inputs()
  r[0]['pages'].append(dict(page=174,text='其他原因的合并范围变动\n□适用 √不适用'))
  result=review(a,m,'2026-06-30',r)
  self.assertEqual(result['comparabilityWarnings'],[])
  self.assertEqual(result['fields'][0]['parts']['current']['status'],'supported-inputs-matched')
 def test_saved_state_cannot_be_promoted_by_editing_json(self):
  import tempfile,json,hashlib
  from pathlib import Path
  from unittest.mock import patch
  from quarter_original_review import verified_saved_result,method_versions
  a,m,reports=self.inputs();raw=json.dumps(a).encode();saved=review(a,m,'2026-06-30',reports)
  saved.update(input={'metadata':m,'period':'2026-06-30'},archiveSha256=hashlib.sha256(raw).hexdigest(),originalBindings=[],methodVersions=method_versions())
  with tempfile.TemporaryDirectory() as d,patch('quarter_original_review.load_inputs',return_value=(a,raw,reports,[])):
   p=Path(d)/'saved.json';p.write_text(json.dumps(saved));verified_saved_result(p,a,m,'2026-06-30')
   saved['fields'][0]['parts']['current']['status']='precise';p.write_text(json.dumps(saved))
   with self.assertRaises(ValueError):verified_saved_result(p,a,m,'2026-06-30')
 def test_saved_metadata_cannot_switch_scope(self):
  import tempfile,json
  from pathlib import Path
  from quarter_original_review import verified_saved_result
  a,m,r=self.inputs()
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'saved.json';p.write_text(json.dumps({'input':{'metadata':dict(m,scope='parent'),'period':'2026-06-30'}}))
   with self.assertRaises(ValueError):verified_saved_result(p,a,m,'2026-06-30')

class DependencyExplanationTests(unittest.TestCase):
 def test_difference_is_disclosed_without_resolving(self):
  from quarter_original_review import dependency_note
  text=dependency_note('营业收入',dict(period='2025-06-30',status='difference',channelValue=110,difference='10',originalValues=[dict(convertedValueCNY='100')]))
  for phrase in ['110元','100元','渠道减原文','10元','原因尚未确认']:self.assertIn(phrase,text)
 def test_missing_unit_is_not_zero_or_numeric_difference(self):
  from quarter_original_review import dependency_note
  text=dependency_note('营业收入',dict(period='2025-03-31',status='unit-unconfirmed'))
  self.assertIn('无法换算',text);self.assertNotIn('差额',text)
