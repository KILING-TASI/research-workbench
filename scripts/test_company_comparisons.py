import unittest
from company_financial_report import checked_comparisons
class Tests(unittest.TestCase):
 def setUp(self):
  self.reports={c:dict(parseStatus='parsed',fileSha256='hash',pages=[dict(page=1,text='公司报告的经营与风险披露原文')]) for c in ['600031','000425']}
  self.row=dict(codes=list(self.reports),kind='difference',basis='research-explanation',text='经营逻辑对照，非因果证明',evidence=[dict(code=c,page=1,quote='公司报告的经营与风险披露原文') for c in self.reports])
 def test_all_company_quotes_checked(self):
  result=checked_comparisons([self.row],self.reports,set(self.reports))
  self.assertEqual(len(result[0]['evidence']),2)
  self.assertEqual(result[0]['status'],'quote-located-not-causal-proof')
 def test_one_sided_evidence_rejected(self):
  self.row['evidence']=self.row['evidence'][:1]
  with self.assertRaisesRegex(ValueError,'每家'):checked_comparisons([self.row],self.reports,set(self.reports))
 def test_source_basis_not_company_statement(self):
  self.row['basis']='company-statement'
  with self.assertRaisesRegex(ValueError,'研究解释'):checked_comparisons([self.row],self.reports,set(self.reports))
 def test_wrong_pool_rejected(self):
  with self.assertRaisesRegex(ValueError,'本次公司'):checked_comparisons([self.row],self.reports,{'600031'})
 def test_shared_underlying_source_not_independent(self):
  self.row['underlyingSources']={c:['同一行业数据'] for c in self.reports}
  row=checked_comparisons([self.row],self.reports,set(self.reports))[0]
  self.assertEqual(row['underlyingSourceAssessment']['sharedDeclaredSources'],['同一行业数据'])
  self.assertFalse(row['underlyingSourceAssessment']['independentEvidenceConfirmed'])
  self.row['underlyingSources'].pop('000425')
  with self.assertRaises(ValueError):checked_comparisons([self.row],self.reports,set(self.reports))
if __name__=='__main__':unittest.main()
