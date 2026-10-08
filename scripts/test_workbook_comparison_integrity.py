import copy,unittest
from company_financial_report import checked_comparisons
from financial_workbook_inputs import verify_saved_comparisons
class Tests(unittest.TestCase):
 def sample(self):
  reports={k:dict(parseStatus='parsed',fileSha256=k,pages=[dict(page=1,text='公司披露上半年市场需求持续承压')]) for k in ['A','B']}
  row=dict(text='两个样本转引同一来源，不当作独立验证。',kind='agreement',basis='research-explanation',codes=['A','B'],evidence=[dict(code=k,page=1,quote='上半年市场需求持续承压') for k in reports],underlyingSources={'A':['same'],'B':['same']})
  return reports,dict(comparisons=checked_comparisons([row],reports,set(reports)))
 def test_shared_source_preserved(self):
  reports,saved=self.sample();r=verify_saved_comparisons(saved,reports,set(reports));self.assertFalse(r[0]['underlyingSourceAssessment']['independentEvidenceConfirmed'])
 def test_quote_page_and_status_mutations(self):
  for key,value in [('page',2),('status','verified'),('sha256','changed')]:
   reports,saved=self.sample();saved['comparisons'][0]['evidence'][0][key]=value
   with self.assertRaises(ValueError):verify_saved_comparisons(saved,reports,set(reports))
 def test_independence_mutation(self):
  reports,saved=self.sample();saved['comparisons'][0]['underlyingSourceAssessment']['independentEvidenceConfirmed']=True
  with self.assertRaisesRegex(ValueError,'底层来源'):verify_saved_comparisons(saved,reports,set(reports))
if __name__=='__main__':unittest.main()
