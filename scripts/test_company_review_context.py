import unittest,tempfile,json
from pathlib import Path
from research_workflow import context,run_company_financial_review,quarter_review_markdown
from unittest.mock import patch
class Tests(unittest.TestCase):
 def test_readable_quarter_report_preserves_unknown_and_warning(self):
  field=dict(label='营业收入',parts={key:dict(status=state,dependencies=[dict(period='2026-06-30',pages=[51])]) for key,state in [('current','supported-inputs-matched'),('yoy','not-verified'),('qoq','supported-inputs-matched-with-comparability-warning')]})
  reviews=[dict(code='603986',fields=[field],reportMetadataWarnings=[dict(period='2026-06-30',warning='公告版本尚未核验')])]
  text=quarter_review_markdown(reviews,[dict(code=c,metadata=dict(name=c)) for c in ['603986','603501']])
  for expected in ['输入已匹配','输入尚未完整确认','跨期口径待复核','公告版本尚未核验','本次未提供相邻期核验','quarter-sources/603986-2026-06-30.pdf#page=51']:self.assertIn(expected,text)
 def test_comparisons_forwarded_and_registered(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);ctx=context(dict(sessionId='review',baseCurrency='CNY',frequency='trading_day',dividendTreatment='reinvest',asOf='2026-10-05',benchmark=None,riskFreeRate=.01,annualization=252,missingData='common_dates',timezone='UTC'))
   rows=[dict(text='公开原文中的样本对照')]
   for name,obj in [('ctx',ctx),('fin',dict(period='2026-06-30',companies=[])),('original',dict(asOf='2026-10-05',companies=[])),('comparisons',rows)]:(p/(name+'.json')).write_text(json.dumps(obj),encoding='utf8')
   s=dict(contextPath=str(p/'ctx.json'),financialResult=str(p/'fin.json'),originalResult=str(p/'original.json'),archives=[],outDir=str(p/'out'),comparisonsPath=str(p/'comparisons.json'))
   with patch('financial_source_binding.bound_archives',return_value=({},{})),patch('company_financial_report.run',return_value=dict(companies=[],originalBindings=[],comparisons=rows)) as run:
    result=run_company_financial_review(s)
   self.assertEqual(run.call_args.args[0]['comparisons'],rows)
   modules={c['module'] for c in result['lineage']['calculations'][0]['code']}
   self.assertIn('company_report_batch.py',modules)
   self.assertTrue(any(n['role']=='research-comparisons' and Path(n['path'])==(p/'comparisons.json').resolve() for n in result['lineage']['files']))
   s['quarterReviewResults']=['same.json','same.json']
   with patch('financial_source_binding.bound_archives',return_value=({},{})),patch('company_financial_report.run') as run:
    with self.assertRaises(ValueError):run_company_financial_review(s)
    run.assert_not_called()
   s.pop('quarterReviewResults')
   (p/'comparisons.json').write_text('{}',encoding='utf8')
   with self.assertRaises(ValueError):run_company_financial_review(s)
 def test_original_cutoff_mismatch_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);ctx=context(dict(sessionId='review',baseCurrency='CNY',frequency='trading_day',dividendTreatment='reinvest',asOf='2026-10-05',benchmark=None,riskFreeRate=.01,annualization=252,missingData='common_dates',timezone='UTC'))
   for name,obj in [('ctx',ctx),('fin',dict(period='2026-06-30',companies=[])),('original',dict(asOf='2026-10-04',companies=[]))]:(p/(name+'.json')).write_text(json.dumps(obj),encoding='utf8')
   s=dict(contextPath=str(p/'ctx.json'),financialResult=str(p/'fin.json'),originalResult=str(p/'original.json'),archives=[],outDir=str(p/'out'))
   with self.assertRaises(ValueError):run_company_financial_review(s)
   self.assertFalse((p/'out').exists())
if __name__=='__main__':unittest.main()
