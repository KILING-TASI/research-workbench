import unittest
from financial_research_pipeline import quarter_verification_summary,CHECK_FIELDS
class Tests(unittest.TestCase):
 def test_matched_fields_do_not_erase_research_gaps(self):
  from financial_research_pipeline import verification_summary,delivery_assessment
  checks=[dict(status='matched') for _ in CHECK_FIELDS]
  data=dict(companies=[dict(code='600309',checks=checks,comparativeChecks=checks,gaps=['金额单位声明尚未明确'])])
  summary=verification_summary(data,['600309'])
  quarter=quarter_verification_summary([self.review()],['600309'],True)
  assessment=delivery_assessment(dict(reports='completed',financials='completed',commentary='completed',excel='completed'),summary,quarter,[])
  self.assertEqual(assessment['status'],'partial')
  self.assertIn('600309：金额单位声明尚未明确',assessment['gaps'])
 def test_final_report_keeps_assessed_gaps_without_stage_error(self):
  from financial_research_pipeline import delivery_gaps
  result=dict(issues=['下载失败'],deliveryAssessment=dict(status='partial',gaps=['下载失败','600276：待核实问题：核对收款时点']))
  self.assertEqual(delivery_gaps(result),['下载失败','600276：待核实问题：核对收款时点'])
 def test_report_resume_path_is_batch_option_not_company_identity(self):
  from financial_research_pipeline import report_request
  companies=[dict(code='600887')]
  r=report_request('2026-06-30','2026-10-05',companies,'prior/result.json')
  self.assertEqual(r['resumeFrom'],'prior/result.json');self.assertNotIn('resumeFrom',r['companies'][0])
  self.assertNotIn('resumeFrom',report_request('2026-06-30','2026-10-05',companies))
  for invalid in ['',3,{}]:
   with self.assertRaises(ValueError):report_request('2026-06-30','2026-10-05',companies,invalid)
 def review(self):return dict(code='600309',fields=[dict(metric=m,parts={p:dict(value=1,status='supported-inputs-matched',dependencies=[dict(status='matched')]) for p in ['current','yoy','qoq']}) for m in CHECK_FIELDS])
 def test_all_groups_and_missing_request(self):
  r=quarter_verification_summary([self.review()],['600309'],True)['companies'][0];self.assertEqual(r['matched'],len(CHECK_FIELDS)*3)
  r=quarter_verification_summary([],['600309'],False)['companies'][0];self.assertFalse(r['requested']);self.assertEqual(r['unverified'],len(CHECK_FIELDS)*3)
 def test_label_alone_not_proof(self):
  r=self.review();r['fields'][0]['parts']['current']['dependencies']=[]
  self.assertEqual(quarter_verification_summary([r],['600309'],True)['companies'][0]['unverified'],1)
 def test_warning_separate(self):
  r=self.review();r['fields'][0]['parts']['yoy']['status']='supported-inputs-matched-with-comparability-warning'
  row=quarter_verification_summary([r],['600309'],True)['companies'][0];self.assertEqual((row['matched'],row['comparabilityWarning']),(len(CHECK_FIELDS)*3-1,1))
 def test_duplicate_rejected(self):
  r=self.review();r['fields'].append(r['fields'][0])
  with self.assertRaises(ValueError):quarter_verification_summary([r],['600309'],True)
if __name__=='__main__':unittest.main()
