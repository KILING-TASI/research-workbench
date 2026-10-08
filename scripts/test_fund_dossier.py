import unittest,tempfile
from pathlib import Path
from fund_dossier import run,fee_context,coverage_summary,presentation_details
class Tests(unittest.TestCase):
 def test_share_fee_zero_missing_and_conflict_stay_separate(self):
  r=fee_context(None,dict(fees={},salesServiceFees={'A':dict(value=0,unit='annual-pct',status='明确不收取'), 'C':dict(value=None,unit='annual-pct',status='多费率冲突',evidence=[1,2])}))
  self.assertEqual(r['rows'][0]['value'],0);self.assertIsNone(r['rows'][1]['value']);self.assertEqual(r['rows'][1]['evidence'],[1,2]);self.assertFalse(r['rows'][0]['effectiveVerified']);self.assertEqual(r['rows'][0]['shareClass'],'A')
 def test_human_gap_scope_keeps_original_evidence(self):
  d=dict(gaps=['持仓股票/债券仅代码线索，缺报告日权重及合计核对','经理任职起止、在管与历史产品清单需任职公告核验'])
  r=presentation_details(d,dict(status='副本身份及股票持仓勾稽完成',holdings={'holdings':[1]}),dict(managers=[1]))
  self.assertIn('已另行核验',r['gaps'][0]);self.assertIn('仍需',r['gaps'][1]);self.assertIn('缺报告日',d['gaps'][0]);self.assertIsNot(r['gaps'],d['gaps'])
 def test_partial_report_does_not_resolve_stock_gap(self):
  d=dict(gaps=['持仓股票/债券仅代码线索，缺报告日权重及合计核对'])
  self.assertEqual(presentation_details(d,dict(status='会计差额待核验',holdings={'holdings':[1]}),None)['gaps'],d['gaps'])
 def test_nested_report_gaps_preserved(self):
  r=dict(details={},report=dict(status='副本身份及股票持仓勾稽完成',holdings={'holdings':[1]},gaps=['官方发布页未核验']),gaps=['其他缺项'],reportIndustries=None,managerTenure={'managers':[]})
  c=coverage_summary(r);self.assertEqual(c['gaps'],['其他缺项','官方发布页未核验']);self.assertIn('勾稽完成',c['rows'][1]['status']);self.assertEqual(c['rows'][-1]['status'],'尚未核验')
 def test_partial_holdings_not_complete(self):
  c=coverage_summary(dict(report=dict(status='会计差额待核验',holdings={'holdings':[1]},gaps=[])))
  self.assertEqual(c['rows'][1]['status'],'部分取得，核验未完成')
 def test_investment_failure_keeps_disclosure(self):
  with tempfile.TemporaryDirectory() as t:
   report=dict(metadata=dict(title='年报',publishedAt='2026-03-31',sourceUrl='https://example.org/a'),status='下载',gaps=[],holdings=None,fundInvestmentDisclosure=dict(rows=[],limitations=[]))
   r=run('110022','2025-12-31','2026-10-03',Path(t)/'r',fetch=self.fail,report_runner=lambda *a:report,tenure_runner=self.fail,fee_runner=self.fail,investment_runner=self.fail)
   self.assertEqual(r['report'],report);self.assertIsNone(r['fundInvestmentAccounting']);self.assertTrue(any('基金投资会计核对' in x for x in r['gaps']))
 def test_target_failure_keeps_parent_and_explicit_link(self):
  with tempfile.TemporaryDirectory() as t:
   report=dict(metadata=dict(title='年报',publishedAt='2026-03-31',sourceUrl='https://example.org/a'),status='下载',gaps=[],holdings=None,hasTargetFundSection=True)
   link=dict(parentCode='110022',reportDate='2025-12-31',target=dict(code='159941',name='目标ETF',fields={}),sourceUrl='https://example.org/a',limitations=[])
   r=run('110022','2025-12-31','2026-10-03',Path(t)/'r',self.fail,lambda *a:report,self.fail,self.fail,lambda r:link,self.fail)
   self.assertEqual(r['targetFundLink'],link);self.assertEqual(r['report'],report);self.assertIsNone(r['targetReport']);self.assertTrue(any('目标基金报告关联' in g for g in r['gaps']))
 def test_ordinary_report_does_not_fetch_child(self):
  with tempfile.TemporaryDirectory() as t:
   report=dict(metadata=dict(title='年报',publishedAt='2026-03-31',sourceUrl='https://example.org/a'),status='下载',gaps=[],holdings=None)
   def unexpected(*a):raise AssertionError('不应调用')
   r=run('110022','2025-12-31','2026-10-03',Path(t)/'r',self.fail,lambda *a:report,self.fail,self.fail,unexpected,unexpected)
   self.assertIsNone(r['targetFundLink']);self.assertFalse(any('目标基金报告关联' in g for g in r['gaps']))
 def test_fee_types_not_compared_as_same_field(self):
  d=dict(facts=dict(subscriptionClues=dict(providerOriginalRate='1.5',providerDiscountedRate='0.15',sourceUrl='https://example.org/channel',retrievedAt=None)))
  f=dict(reportDate='2025-12-31',publishedAt='2026-03-31',sourceUrl='https://example.org/report',fees={'管理费':dict(value=1.2,unit='annual-pct',currentEffectiveVerified=False,evidence=[])})
  r=fee_context(d,f);self.assertEqual(len(r['rows']),3);self.assertEqual(r['rows'][0]['unit'],'provider-raw-not-normalized');self.assertEqual(r['rows'][2]['feeType'],'fund-recurring');self.assertFalse(any(x['effectiveVerified'] for x in r['rows']));self.assertIn('不能直接判定',r['comparisonStatus'])
 def test_no_fee_data_keeps_empty(self):self.assertFalse(fee_context(None,None)['rows'])
 def fail(self,*a):raise OSError('不可用')
 def test_both_fail_explicit(self):
  with tempfile.TemporaryDirectory() as t:
   r=run('110022','2025-12-31','2026-10-03',Path(t)/'r',self.fail,self.fail);self.assertEqual(len(r['gaps']),2);self.assertIsNone(r['report'])
 def test_report_survives_nav_failure(self):
  with tempfile.TemporaryDirectory() as t:
   report=dict(metadata=dict(title='年报',publishedAt='2026-03-31',sourceUrl='https://example.org/a'),status='下载',gaps=[],holdings=None)
   r=run('110022','2025-12-31','2026-10-03',Path(t)/'r',self.fail,lambda *a:report,lambda r:dict(managers=[]));self.assertEqual(r['report'],report);self.assertIsNone(r['details'])
 def test_accounting_gap_visible_in_human_reports(self):
  with tempfile.TemporaryDirectory() as t:
   h=dict(netAssetsCNY=100,equityMarketValueCNY=90,equityWeight=.9,holdings=[],accountingReconciliation=dict(status='unresolved',portfolioEquityCNY='90',accountingEquityCNY='91',differenceCNY='1',explanation='差额尚未解释',scopeNotes=[dict(page=4,quote='口径原文')]))
   report=dict(metadata=dict(title='年报',publishedAt='2026-03-31',sourceUrl='https://example.org/a'),status='会计差额待核验',gaps=[],holdings=h)
   folder=Path(t)/'r'
   run('110022','2025-12-31','2026-10-03',folder,self.fail,lambda *a:report,self.fail,self.fail)
   for name in ['基金研究简报.md','基金研究简报.html']:
    text=(folder/name).read_text(encoding='utf-8');self.assertIn('差额尚未解释',text);self.assertIn('口径原文',text);self.assertIn('91.00',text)
 def test_future(self):
  with tempfile.TemporaryDirectory() as t:
   with self.assertRaises(ValueError):run('110022','2026-12-31','2026-10-03',Path(t)/'r')
 def test_tenure_failure_preserves_report(self):
  with tempfile.TemporaryDirectory() as t:
   report=dict(metadata=dict(title='年报',publishedAt='2026-03-31',sourceUrl='https://example.org/a'),status='下载',gaps=[],holdings=None)
   r=run('110022','2025-12-31','2026-10-03',Path(t)/'r',self.fail,lambda *a:report,self.fail);self.assertEqual(r['report'],report);self.assertIsNone(r['managerTenure']);self.assertTrue(any('经理任职' in x for x in r['gaps']))
 def test_complete_fof_section_triggers_accounting(self):
  with tempfile.TemporaryDirectory() as t:
   report={'metadata':{'title':'中报','publishedAt':'2026-08-31','sourceUrl':'https://example.org/r'},'status':'下载','gaps':[],'holdings':None,'hasCompleteFundInvestmentSection':True};calls=[]
   def accounting(r):calls.append(r);raise ValueError('管理人身份资料缺失')
   r=run('005215','2026-06-30','2026-10-03',Path(t)/'r',fetch=self.fail,report_runner=lambda *args:report,tenure_runner=self.fail,fee_runner=self.fail,investment_runner=accounting)
   self.assertEqual(len(calls),1);self.assertTrue(any('管理人身份资料缺失' in x for x in r['gaps']))
 def test_context_only_fee_does_not_break_report(self):
  with tempfile.TemporaryDirectory() as t:
   report={'metadata':{'title':'年报','publishedAt':'2026-03-31','sourceUrl':'https://example.org/r'},'status':'下载','gaps':[],'holdings':None};fees={'sourceUrl':'https://example.org/r','fees':{'管理费':{'value':1,'unit':'annual-pct','evidence':[{'page':3,'context':'管理费按年费率1%计提'}]}}}
   out=Path(t)/'r';run('110022','2025-12-31','2026-10-03',out,fetch=self.fail,report_runner=lambda *args:report,tenure_runner=self.fail,fee_runner=lambda r:fees)
   self.assertIn('管理费按年费率1%计提',(out/'基金研究简报.md').read_text('utf8'))
if __name__=='__main__':unittest.main()
