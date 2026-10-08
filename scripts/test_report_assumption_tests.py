import unittest
from research_report_reading import assumption_tests
class Tests(unittest.TestCase):
 def report(self):return dict(sha256='hash',pages=[dict(page=1,text='Effective June 18, 2026')])
 def entry(self):return dict(text='生效时间须与公布时间分开',evidence=[dict(page=1,quote='Effective June 18, 2026')],invalidationSignal='后续更正文件改变生效日',requestedEvidence='取得更正文件及实施指令')
 def test_retains_plan_not_verification(self):
  row=assumption_tests([self.entry()],self.report())[0];self.assertEqual(row['status'],'hypothesis-prepared-not-tested');self.assertEqual(row['evidence'][0]['sha256'],'hash')
 def test_invented_quote_rejected(self):
  row=self.entry();row['evidence'][0]['quote']='unpublished policy result'
  with self.assertRaises(ValueError):assumption_tests([row],self.report())
 def test_no_verified_status_or_empty_plan(self):
  for row in [dict(self.entry(),status='verified'),dict(self.entry(),requestedEvidence='')]:
   with self.assertRaises(ValueError):assumption_tests([row],self.report())
class WorkflowTests(unittest.TestCase):
 def test_structured_gap_keeps_required_material_without_duplicate(self):
  from research_workflow import report_reading_gaps
  entry=dict(text='待核对传导',invalidationSignal='相反数据',requestedEvidence='原始观测',evidence=[dict(page=1,sha256='h')],status='hypothesis-prepared-not-tested')
  gaps=report_reading_gaps(dict(unreadReports=[],analyses=[dict(reportId='a',gaps=['一般缺口','待核查假设：待核对传导'],assumptionTests=[entry])]))
  self.assertEqual(len(gaps),2);self.assertEqual(gaps[1]['requestedEvidence'],'原始观测');self.assertEqual(gaps[1]['evidence'][0]['sha256'],'h');self.assertEqual(gaps[1]['status'],'hypothesis-prepared-not-tested')
if __name__=='__main__':unittest.main()
